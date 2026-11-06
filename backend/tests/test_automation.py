"""Phase 5 — Celery Beat, auto-chain, pause/resume, retries, task monitoring."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analysis.models import DraftResponse, RelevanceAnalysis
from apps.monitors.backoff import countdown_from_retry_after, retry_countdown
from apps.monitors.models import Keyword, Monitor, TaskRun
from apps.monitors.tasks import dispatch_due_monitors, poll_monitor
from apps.reddit.models import RedditAccount, RedditPost
from apps.reddit.services import ensure_fixture_account, mark_account_expired
from apps.reddit.tasks import refresh_expiring_tokens

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="owner",
        password="Str0ngPass!word",
        is_personal_owner=True,
    )


@pytest.fixture
def auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def monitor(user) -> Monitor:
    ensure_fixture_account(user)
    m = Monitor.objects.create(
        user=user,
        name="Beat watch",
        is_active=True,
        poll_interval_minutes=15,
        auto_analyze=True,
        auto_draft=True,
    )
    Keyword.objects.create(monitor=m, phrase="django", match_mode="any")
    return m


# ---------------------------------------------------------------------------
# Backoff helpers
# ---------------------------------------------------------------------------


def test_retry_countdown_steps_and_jitter() -> None:
    assert retry_countdown(0, jitter_seconds=0) == 30
    assert retry_countdown(1, jitter_seconds=0) == 120
    assert retry_countdown(2, jitter_seconds=0) == 600
    assert retry_countdown(99, jitter_seconds=0) == 600


def test_countdown_prefers_retry_after() -> None:
    assert countdown_from_retry_after(42, jitter_seconds=0) == 42
    assert countdown_from_retry_after(None, retries=0, jitter_seconds=0) == 30


# ---------------------------------------------------------------------------
# Beat dispatch + interval enforcement
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", CELERY_TASK_ALWAYS_EAGER=True)
def test_dispatch_due_monitors_enqueues_never_polled(monitor) -> None:
    result = dispatch_due_monitors()
    assert result["ok"] is True
    assert result["enqueued"] == 1
    assert result["never_auto_publish"] is True
    monitor.refresh_from_db()
    assert monitor.last_polled_at is not None


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", CELERY_TASK_ALWAYS_EAGER=True)
def test_dispatch_skips_monitors_inside_interval(monitor) -> None:
    monitor.last_polled_at = timezone.now()
    monitor.save(update_fields=["last_polled_at"])
    result = dispatch_due_monitors()
    assert result["enqueued"] == 0


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", CELERY_TASK_ALWAYS_EAGER=True)
def test_dispatch_enqueues_when_interval_elapsed(monitor) -> None:
    monitor.last_polled_at = timezone.now() - timedelta(minutes=20)
    monitor.save(update_fields=["last_polled_at"])
    result = dispatch_due_monitors()
    assert result["enqueued"] == 1


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", CELERY_TASK_ALWAYS_EAGER=True)
def test_dispatch_skips_paused_monitors(monitor) -> None:
    monitor.is_active = False
    monitor.save(update_fields=["is_active"])
    result = dispatch_due_monitors()
    assert result["enqueued"] == 0


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", CELERY_TASK_ALWAYS_EAGER=True)
def test_dispatch_skips_expired_reddit_and_records_error(monitor, user) -> None:
    account = RedditAccount.objects.get(user=user)
    account.status = RedditAccount.Status.CONNECTED
    account.token_expires_at = timezone.now() - timedelta(minutes=1)
    account.save()
    mark_account_expired(account, reason="test")
    result = dispatch_due_monitors()
    assert result["enqueued"] == 0
    assert result["skipped_expired"] == 1
    monitor.refresh_from_db()
    assert "expired" in monitor.last_error.lower()


# ---------------------------------------------------------------------------
# Auto-chain discover → analyze → draft (never publish)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(
    REDDIT_MODE="fixture",
    OPENAI_MODE="mock",
    CELERY_TASK_ALWAYS_EAGER=True,
    MONITOR_AUTO_ANALYZE=True,
    MONITOR_AUTO_DRAFT=True,
)
def test_poll_auto_chain_fills_review_never_publishes(monitor) -> None:
    result = poll_monitor(str(monitor.pk))
    assert result["ok"] is True
    assert result["never_auto_publish"] is True
    assert result["analyze_enqueued"] == result["created"]

    assert RedditPost.objects.filter(discovered_via_monitor=monitor).exists()
    # Relevant fixture posts should produce in_review drafts, never published.
    assert DraftResponse.objects.filter(status=DraftResponse.Status.PUBLISHED).count() == 0
    assert DraftResponse.objects.filter(status=DraftResponse.Status.APPROVED).count() == 0
    # At least one draft should land in review for django-relevant fixtures.
    assert (
        DraftResponse.objects.filter(status=DraftResponse.Status.IN_REVIEW).exists()
        or RelevanceAnalysis.objects.filter(is_relevant=False).exists()
    )


@pytest.mark.django_db
@override_settings(
    REDDIT_MODE="fixture",
    OPENAI_MODE="mock",
    CELERY_TASK_ALWAYS_EAGER=True,
    MONITOR_AUTO_ANALYZE=True,
    MONITOR_AUTO_DRAFT=True,
)
def test_auto_chain_idempotent_second_poll(monitor) -> None:
    first = poll_monitor(str(monitor.pk))
    second = poll_monitor(str(monitor.pk))
    assert first["ok"] and second["ok"]
    assert second["created"] == 0
    assert second["analyze_enqueued"] == 0
    # No duplicate in_review drafts for same post from auto-chain skips.
    for post in RedditPost.objects.filter(discovered_via_monitor=monitor):
        active = DraftResponse.objects.filter(
            post=post,
            status__in=[
                DraftResponse.Status.DRAFT,
                DraftResponse.Status.IN_REVIEW,
                DraftResponse.Status.APPROVED,
            ],
        ).count()
        assert active <= 1


@pytest.mark.django_db
@override_settings(
    REDDIT_MODE="fixture",
    OPENAI_MODE="mock",
    CELERY_TASK_ALWAYS_EAGER=True,
)
def test_auto_analyze_disabled_skips_chain(monitor) -> None:
    monitor.auto_analyze = False
    monitor.save(update_fields=["auto_analyze"])
    result = poll_monitor(str(monitor.pk))
    assert result["ok"] is True
    assert result["analyze_enqueued"] == 0
    assert RelevanceAnalysis.objects.count() == 0


# ---------------------------------------------------------------------------
# Pause / resume API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pause_and_resume_monitor(auth_client: APIClient, monitor) -> None:
    pause = auth_client.post(f"/api/v1/monitors/{monitor.pk}/pause/", {}, format="json")
    assert pause.status_code == 200
    assert pause.json()["monitor"]["is_active"] is False
    assert pause.json()["never_auto_publish"] is True
    monitor.refresh_from_db()
    assert monitor.is_active is False

    resume = auth_client.post(f"/api/v1/monitors/{monitor.pk}/resume/", {}, format="json")
    assert resume.status_code == 200
    assert resume.json()["monitor"]["is_active"] is True
    monitor.refresh_from_db()
    assert monitor.is_active is True


@pytest.mark.django_db
def test_resume_blocked_when_token_expired(auth_client: APIClient, monitor, user) -> None:
    account = RedditAccount.objects.get(user=user)
    account.status = RedditAccount.Status.EXPIRED
    account.save(update_fields=["status"])
    monitor.is_active = False
    monitor.save(update_fields=["is_active"])
    resume = auth_client.post(f"/api/v1/monitors/{monitor.pk}/resume/", {}, format="json")
    assert resume.status_code == 400
    assert resume.json()["code"] == "reddit_token_expired"


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", CELERY_TASK_ALWAYS_EAGER=True)
def test_run_now_rejects_paused(auth_client: APIClient, monitor) -> None:
    monitor.is_active = False
    monitor.save(update_fields=["is_active"])
    run = auth_client.post(f"/api/v1/monitors/{monitor.pk}/run/", {}, format="json")
    assert run.status_code == 400
    assert run.json()["code"] == "monitor_inactive"


# ---------------------------------------------------------------------------
# Task monitoring API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_task_runs_recorded_and_listed(auth_client: APIClient, monitor) -> None:
    poll_monitor(str(monitor.pk))
    assert TaskRun.objects.filter(task_name="monitors.poll_monitor").exists()

    listing = auth_client.get("/api/v1/tasks/")
    assert listing.status_code == 200
    payload = listing.json()
    results = payload["results"] if "results" in payload else payload
    assert len(results) >= 1
    assert results[0]["never_auto_publish"] is True

    status = auth_client.get("/api/v1/automation/status/")
    assert status.status_code == 200
    body = status.json()
    assert body["never_auto_publish"] is True
    assert "dispatch-due-monitors-every-5-min" in body["beat_schedule"]
    assert body["monitors_active"] >= 1


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
def test_refresh_skips_fixture_accounts(user) -> None:
    ensure_fixture_account(user)
    result = refresh_expiring_tokens()
    assert result["ok"] is True
    assert result["refreshed"] == 0
    assert result["never_auto_publish"] is True


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, REDDIT_CLIENT_ID="cid", REDDIT_CLIENT_SECRET="sec")
def test_refresh_marks_expired_on_invalid_grant(user) -> None:
    from apps.reddit.crypto import encrypt_token

    account = RedditAccount.objects.create(
        user=user,
        reddit_username="liveuser",
        status=RedditAccount.Status.CONNECTED,
        access_token_encrypted=encrypt_token("access"),
        refresh_token_encrypted=encrypt_token("refresh"),
        token_expires_at=timezone.now() + timedelta(minutes=5),
    )

    class FakeHTTPError(Exception):
        def __init__(self):
            self.response = MagicMock(status_code=400)
            super().__init__("invalid_grant")

    with patch(
        "apps.reddit.client.refresh_access_token",
        side_effect=FakeHTTPError(),
    ):
        from apps.reddit.services import refresh_account_tokens

        result = refresh_account_tokens(account)
    assert result["ok"] is False
    assert result["expired"] is True
    account.refresh_from_db()
    assert account.status == RedditAccount.Status.EXPIRED


@pytest.mark.django_db
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, REDDIT_CLIENT_ID="cid", REDDIT_CLIENT_SECRET="sec")
def test_refresh_expiring_tokens_success(user) -> None:
    from apps.reddit.crypto import encrypt_token, decrypt_token

    account = RedditAccount.objects.create(
        user=user,
        reddit_username="liveuser",
        status=RedditAccount.Status.CONNECTED,
        access_token_encrypted=encrypt_token("old-access"),
        refresh_token_encrypted=encrypt_token("refresh"),
        token_expires_at=timezone.now() + timedelta(minutes=5),
    )
    with patch(
        "apps.reddit.client.refresh_access_token",
        return_value={"access_token": "new-access", "expires_in": 3600},
    ):
        result = refresh_expiring_tokens()
    assert result["refreshed"] == 1
    account.refresh_from_db()
    assert account.status == RedditAccount.Status.CONNECTED
    assert decrypt_token(account.access_token_encrypted) == "new-access"


# ---------------------------------------------------------------------------
# Lock contention → retry
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", CELERY_TASK_ALWAYS_EAGER=True)
def test_poll_retries_when_account_lock_held(monitor) -> None:
    with patch("apps.monitors.tasks.acquire_account_lock", return_value=False):
        with pytest.raises(Exception):
            # Eager mode exhausts retries when the lock never frees.
            poll_monitor.delay(str(monitor.pk))
    assert TaskRun.objects.filter(
        task_name="monitors.poll_monitor",
        monitor=monitor,
    ).exists()


# ---------------------------------------------------------------------------
# Beat schedule settings
# ---------------------------------------------------------------------------


def test_celery_beat_schedule_configured() -> None:
    from django.conf import settings

    keys = set(settings.CELERY_BEAT_SCHEDULE.keys())
    assert "dispatch-due-monitors-every-5-min" in keys
    assert "refresh-expiring-reddit-tokens-hourly" in keys
    assert settings.CELERY_BEAT_SCHEDULE["dispatch-due-monitors-every-5-min"]["task"] == (
        "monitors.dispatch_due_monitors"
    )
    assert settings.MONITOR_AUTO_ANALYZE is True
    assert settings.MONITOR_AUTO_DRAFT is True
