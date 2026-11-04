"""Celery tasks for polling monitors against Reddit search."""

from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from apps.reddit.client import RedditRateLimitError
from apps.reddit.models import RedditAccount
from apps.reddit.rate_limit import (
    acquire_account_lock,
    check_token_bucket,
    release_account_lock,
)
from apps.reddit.services import (
    build_search_query,
    client_for_account,
    ensure_fixture_account,
    upsert_post,
)

from .models import Monitor

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="monitors.poll_monitor",
    max_retries=5,
    soft_time_limit=120,
    time_limit=180,
)
def poll_monitor(self, monitor_id: str) -> dict:
    """Search Reddit for monitor keywords/subreddits; upsert RedditPost rows."""
    try:
        monitor = Monitor.objects.prefetch_related("keywords", "subreddits").get(pk=monitor_id)
    except Monitor.DoesNotExist:
        return {"ok": False, "error": "monitor_not_found"}

    if not monitor.is_active:
        return {"ok": False, "error": "monitor_inactive"}

    account = RedditAccount.objects.filter(user=monitor.user).first()
    if account is None:
        from django.conf import settings

        if settings.REDDIT_MODE == "fixture":
            account = ensure_fixture_account(monitor.user)
        else:
            return {"ok": False, "error": "reddit_not_connected"}

    if account.status == RedditAccount.Status.EXPIRED:
        return {"ok": False, "error": "reddit_token_expired"}
    if account.status == RedditAccount.Status.REVOKED:
        return {"ok": False, "error": "reddit_revoked"}

    account_key = str(account.pk)
    if not acquire_account_lock(account_key):
        # Soft defer — another poll is in flight
        raise self.retry(countdown=15)

    created = 0
    updated = 0
    searched = 0
    try:
        bucket = check_token_bucket(account_key)
        if not bucket.allowed:
            raise self.retry(countdown=max(int(bucket.wait_seconds), 1))

        client = client_for_account(account)
        subreddit_names = [s.name for s in monitor.subreddits.all()]
        # Empty subreddit set → global search
        targets: list[str | None] = subreddit_names or [None]
        keywords = list(monitor.keywords.all())
        if not keywords:
            return {"ok": False, "error": "no_keywords", "created": 0, "updated": 0}

        for keyword in keywords:
            query = build_search_query(keyword.phrase, keyword.match_mode)
            for sub in targets:
                try:
                    results = client.search(
                        query,
                        subreddit=sub,
                        limit=25,
                        include_nsfw=monitor.include_nsfw,
                    )
                except RedditRateLimitError as exc:
                    raise self.retry(countdown=max(int(exc.wait_seconds), 1)) from exc

                searched += 1
                for result in results:
                    if monitor.min_score is not None and result.score < monitor.min_score:
                        continue
                    if monitor.min_comments is not None and result.num_comments < monitor.min_comments:
                        continue
                    _, was_created = upsert_post(
                        user=monitor.user,
                        result=result,
                        monitor=monitor,
                    )
                    if was_created:
                        created += 1
                    else:
                        updated += 1

        monitor.last_polled_at = timezone.now()
        monitor.save(update_fields=["last_polled_at", "updated_at"])
        return {
            "ok": True,
            "monitor_id": str(monitor.pk),
            "searches": searched,
            "created": created,
            "updated": updated,
        }
    finally:
        release_account_lock(account_key)
