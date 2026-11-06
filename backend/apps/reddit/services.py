"""Domain services: token helpers, post upsert, fixture account ensure."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone as dj_timezone

from .client import RedditSearchResult, get_reddit_client
from .crypto import decrypt_token, encrypt_token
from .models import RedditAccount, RedditPost

logger = logging.getLogger(__name__)
User = get_user_model()


def ensure_fixture_account(user) -> RedditAccount:
    """Create or update a dev_fixture RedditAccount for the user."""
    account, _ = RedditAccount.objects.update_or_create(
        user=user,
        defaults={
            "reddit_username": "fixture_user",
            "reddit_user_id": "fixture",
            "status": RedditAccount.Status.DEV_FIXTURE,
            "scopes": "identity,read",
            "access_token_encrypted": "",
            "refresh_token_encrypted": "",
            "token_expires_at": None,
        },
    )
    return account


def store_oauth_tokens(
    user,
    *,
    access_token: str,
    refresh_token: str | None,
    expires_in: int | None,
    scope: str,
    identity: dict[str, Any],
) -> RedditAccount:
    expires_at = None
    if expires_in:
        expires_at = dj_timezone.now() + timedelta(seconds=int(expires_in))
    account, _ = RedditAccount.objects.update_or_create(
        user=user,
        defaults={
            "reddit_username": str(identity.get("name") or ""),
            "reddit_user_id": str(identity.get("id") or ""),
            "access_token_encrypted": encrypt_token(access_token),
            "refresh_token_encrypted": encrypt_token(refresh_token or ""),
            "token_expires_at": expires_at,
            "scopes": scope.replace(" ", ",") if scope else "identity,read",
            "status": RedditAccount.Status.CONNECTED,
        },
    )
    return account


def get_decrypted_access_token(account: RedditAccount) -> str:
    if account.status == RedditAccount.Status.DEV_FIXTURE:
        return ""
    return decrypt_token(account.access_token_encrypted)


def get_decrypted_refresh_token(account: RedditAccount) -> str:
    if account.status == RedditAccount.Status.DEV_FIXTURE:
        return ""
    return decrypt_token(account.refresh_token_encrypted)


def mark_account_expired(account: RedditAccount, *, reason: str = "") -> RedditAccount:
    """Flip account to expired so Beat skips polls until reconnect."""
    account.status = RedditAccount.Status.EXPIRED
    account.save(update_fields=["status", "updated_at"])
    if reason:
        logger.warning(
            "Reddit account %s marked expired: %s", account.pk, reason
        )
    return account


def apply_refreshed_tokens(
    account: RedditAccount,
    *,
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
) -> RedditAccount:
    """Persist a successful token refresh and restore connected status."""
    account.access_token_encrypted = encrypt_token(access_token)
    if refresh_token:
        account.refresh_token_encrypted = encrypt_token(refresh_token)
    if expires_in:
        account.token_expires_at = dj_timezone.now() + timedelta(seconds=int(expires_in))
    account.status = RedditAccount.Status.CONNECTED
    account.save(
        update_fields=[
            "access_token_encrypted",
            "refresh_token_encrypted",
            "token_expires_at",
            "status",
            "updated_at",
        ]
    )
    return account


def refresh_account_tokens(account: RedditAccount) -> dict[str, Any]:
    """Refresh one account's access token. Marks expired on auth failure."""
    from .client import RedditRateLimitError, refresh_access_token

    if account.status == RedditAccount.Status.DEV_FIXTURE:
        return {"ok": True, "skipped": True, "reason": "dev_fixture"}
    if account.status == RedditAccount.Status.REVOKED:
        return {"ok": False, "skipped": True, "reason": "revoked"}

    refresh = get_decrypted_refresh_token(account)
    if not refresh:
        mark_account_expired(account, reason="missing_refresh_token")
        return {"ok": False, "error": "missing_refresh_token", "expired": True}

    try:
        payload = refresh_access_token(refresh)
    except RedditRateLimitError:
        raise
    except Exception as exc:  # noqa: BLE001
        # Invalid grant / 401 → expire so polls pause.
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        message = str(exc).lower()
        if status_code in {400, 401, 403} or "invalid_grant" in message:
            mark_account_expired(account, reason=str(exc))
            return {"ok": False, "error": str(exc), "expired": True}
        raise

    access = payload.get("access_token")
    if not access:
        mark_account_expired(account, reason="refresh_missing_access_token")
        return {"ok": False, "error": "refresh_missing_access_token", "expired": True}

    apply_refreshed_tokens(
        account,
        access_token=access,
        refresh_token=payload.get("refresh_token"),
        expires_in=payload.get("expires_in"),
    )
    return {
        "ok": True,
        "account_id": str(account.pk),
        "expires_in": payload.get("expires_in"),
    }


def client_for_account(account: RedditAccount):
    if settings.REDDIT_MODE == "fixture" or account.status == RedditAccount.Status.DEV_FIXTURE:
        return get_reddit_client()
    token = get_decrypted_access_token(account)
    return get_reddit_client(access_token=token)


def upsert_post(
    *,
    user,
    result: RedditSearchResult,
    monitor=None,
) -> tuple[RedditPost, bool]:
    """Insert or update a RedditPost by unique reddit_fullname. Returns (post, created)."""
    created_utc = None
    if result.created_utc is not None:
        created_utc = datetime.fromtimestamp(result.created_utc, tz=timezone.utc)

    defaults = {
        "user": user,
        "reddit_id": result.reddit_id,
        "subreddit": result.subreddit,
        "title": result.title,
        "selftext": result.selftext[:10000],
        "author": result.author,
        "url": result.url[:2048],
        "permalink": result.permalink[:512],
        "score": result.score,
        "num_comments": result.num_comments,
        "created_utc": created_utc,
        "raw_payload": _truncate_payload(result.raw),
    }
    with transaction.atomic():
        post, created = RedditPost.objects.get_or_create(
            reddit_fullname=result.reddit_fullname,
            defaults={
                **defaults,
                "discovered_via_monitor": monitor,
                "status": RedditPost.Status.NEW,
            },
        )
        if not created:
            # Idempotent refresh of volatile fields; keep original discoverer.
            post.score = result.score
            post.num_comments = result.num_comments
            post.title = result.title
            post.selftext = result.selftext[:10000]
            post.raw_payload = _truncate_payload(result.raw)
            post.save(
                update_fields=[
                    "score",
                    "num_comments",
                    "title",
                    "selftext",
                    "raw_payload",
                    "updated_at",
                ]
            )
    return post, created


def _truncate_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep a modest snapshot — drop huge nested listings if present."""
    if not isinstance(raw, dict):
        return {}
    keep_keys = {
        "id",
        "name",
        "subreddit",
        "title",
        "selftext",
        "author",
        "url",
        "permalink",
        "score",
        "num_comments",
        "created_utc",
        "over_18",
        "link_flair_text",
        "ups",
        "downs",
    }
    snapshot = {k: raw[k] for k in keep_keys if k in raw}
    selftext = snapshot.get("selftext")
    if isinstance(selftext, str) and len(selftext) > 5000:
        snapshot["selftext"] = selftext[:5000]
    return snapshot


def build_search_query(phrase: str, match_mode: str) -> str:
    phrase = phrase.strip()
    if match_mode == "exact_phrase":
        return f'"{phrase}"'
    if match_mode == "all_words":
        return phrase
    # any: Reddit search treats space as AND; use OR for any-word semantics
    words = [w for w in phrase.split() if w]
    if len(words) <= 1:
        return phrase
    return " OR ".join(words)
