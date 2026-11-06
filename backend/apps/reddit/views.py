"""Reddit OAuth + status + posts list endpoints."""

from __future__ import annotations

import secrets

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from .client import LiveRedditClient, build_authorize_url, exchange_code_for_tokens, revoke_token
from .crypto import decrypt_token
from .models import RedditAccount, RedditPost
from .serializers import RedditPostSerializer, RedditStatusSerializer
from .services import ensure_fixture_account, store_oauth_tokens

OAUTH_STATE_TTL = 600  # 10 minutes


def _state_cache_key(state: str) -> str:
    return f"reddit:oauth:state:{state}"


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def oauth_start(request: Request) -> Response:
    """Return Reddit authorize URL (state bound to session user)."""
    if settings.REDDIT_MODE == "fixture":
        account = ensure_fixture_account(request.user)
        return Response(
            {
                "authorize_url": None,
                "mode": "fixture",
                "detail": "REDDIT_MODE=fixture — use seed_dev_reddit / Run now; live OAuth disabled.",
                "account_status": account.status,
            }
        )

    if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
        return Response(
            {
                "detail": "Reddit OAuth is not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET.",
                "code": "reddit_oauth_unconfigured",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    nonce = secrets.token_urlsafe(24)
    state = f"{request.user.pk}:{nonce}"
    cache.set(_state_cache_key(state), str(request.user.pk), timeout=OAUTH_STATE_TTL)
    url = build_authorize_url(state=state, scopes="identity read")
    return Response({"authorize_url": url, "mode": "live", "state": state})


@csrf_exempt
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def oauth_callback(request: Request):
    """Exchange code for tokens; redirect to frontend settings."""
    frontend = settings.FRONTEND_ORIGIN.rstrip("/")
    error = request.query_params.get("error")
    if error:
        return redirect(f"{frontend}/settings?reddit=error&detail={error}")

    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        return redirect(f"{frontend}/settings?reddit=error&detail=missing_params")

    user_id = cache.get(_state_cache_key(state))
    cache.delete(_state_cache_key(state))
    if not user_id:
        return redirect(f"{frontend}/settings?reddit=error&detail=invalid_state")

    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return redirect(f"{frontend}/settings?reddit=error&detail=user_missing")

    try:
        token_payload = exchange_code_for_tokens(code)
        access = token_payload["access_token"]
        refresh = token_payload.get("refresh_token")
        expires_in = token_payload.get("expires_in")
        scope = token_payload.get("scope", "identity read")
        identity = LiveRedditClient(access_token=access).get_identity()
        store_oauth_tokens(
            user,
            access_token=access,
            refresh_token=refresh,
            expires_in=expires_in,
            scope=scope,
            identity=identity,
        )
    except Exception:  # noqa: BLE001
        return redirect(f"{frontend}/settings?reddit=error&detail=token_exchange_failed")

    return redirect(f"{frontend}/settings?reddit=connected")


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def reddit_status(request: Request) -> Response:
    account = RedditAccount.objects.filter(user=request.user).first()
    if settings.REDDIT_MODE == "fixture" and account is None:
        account = ensure_fixture_account(request.user)

    payload = {
        "connected": bool(
            account
            and account.status
            in {RedditAccount.Status.CONNECTED, RedditAccount.Status.DEV_FIXTURE}
        ),
        "status": account.status if account else None,
        "reddit_username": account.reddit_username if account else None,
        "scopes": account.scopes if account else None,
        "mode": settings.REDDIT_MODE,
        "token_expires_at": account.token_expires_at if account else None,
        "never_auto_publish": True,
    }
    return Response(RedditStatusSerializer(payload).data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def reddit_disconnect(request: Request) -> Response:
    account = RedditAccount.objects.filter(user=request.user).first()
    if not account:
        return Response({"detail": "No Reddit account connected."})

    if account.status == RedditAccount.Status.CONNECTED:
        try:
            refresh = decrypt_token(account.refresh_token_encrypted)
            revoke_token(refresh)
        except Exception:  # noqa: BLE001
            pass

    if settings.REDDIT_MODE == "fixture":
        account.status = RedditAccount.Status.DEV_FIXTURE
        account.access_token_encrypted = ""
        account.refresh_token_encrypted = ""
        account.reddit_username = "fixture_user"
        account.reddit_user_id = "fixture"
        account.token_expires_at = None
        account.save()
    else:
        account.status = RedditAccount.Status.REVOKED
        account.access_token_encrypted = ""
        account.refresh_token_encrypted = ""
        account.token_expires_at = None
        account.save(
            update_fields=[
                "status",
                "access_token_encrypted",
                "refresh_token_encrypted",
                "token_expires_at",
                "updated_at",
            ]
        )

    return Response(
        {
            "detail": "Disconnected.",
            "status": account.status,
            "never_auto_publish": True,
        }
    )


class RedditPostListView(generics.ListAPIView):
    serializer_class = RedditPostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = RedditPost.objects.filter(user=self.request.user).select_related("analysis")
        status_filter = self.request.query_params.get("status")
        subreddit = self.request.query_params.get("subreddit")
        q = self.request.query_params.get("q")
        min_score = self.request.query_params.get("min_score")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if subreddit:
            qs = qs.filter(subreddit__iexact=subreddit.lstrip("r/"))
        if q:
            qs = qs.filter(title__icontains=q)
        if min_score is not None and min_score != "":
            try:
                qs = qs.filter(score__gte=int(min_score))
            except ValueError:
                pass
        return qs
