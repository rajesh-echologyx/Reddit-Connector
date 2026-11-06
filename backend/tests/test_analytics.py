"""Phase 6 analytics rollups + API tests."""

from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from apps.analysis.models import DraftResponse, RelevanceAnalysis
from apps.analytics.logging_filters import redact_text
from apps.analytics.models import DailyStat
from apps.analytics.services import (
    compute_day_counters,
    funnel_for_user,
    live_totals_match_rollup,
    summary_for_user,
    upsert_daily_stat,
)
from apps.analytics.tasks import rollup_daily_stats
from apps.reddit.models import RedditPost

User = get_user_model()
UTC = ZoneInfo("UTC")


@pytest.fixture
def user(db):
    return User.objects.create_user(username="analyst", password="Str0ngPass!word")


@pytest.fixture
def auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _seed_activity(user) -> None:
    now = timezone.now().astimezone(UTC)
    post = RedditPost.objects.create(
        user=user,
        reddit_fullname="t3_analytics1",
        reddit_id="analytics1",
        subreddit="python",
        title="Need help with Django analytics",
        selftext="How do I roll up daily stats?",
        author="op",
        url="https://reddit.com/r/python/1",
        permalink="/r/python/comments/1/",
        score=10,
        num_comments=2,
        created_utc=now,
    )
    # Force created_at into "today" window if needed (auto_now_add).
    RedditPost.objects.filter(pk=post.pk).update(created_at=now)

    analysis = RelevanceAnalysis.objects.create(
        post=post,
        relevance_score=88,
        is_relevant=True,
        reasons=["matches expertise"],
        status=RelevanceAnalysis.Status.COMPLETE,
    )
    RelevanceAnalysis.objects.filter(pk=analysis.pk).update(created_at=now)

    draft = DraftResponse.objects.create(
        post=post,
        analysis=analysis,
        body="Try aggregating with DailyStat.",
        status=DraftResponse.Status.APPROVED,
        generated_at=now,
        approved_at=now,
    )
    DraftResponse.objects.filter(pk=draft.pk).update(created_at=now)

    rejected_post = RedditPost.objects.create(
        user=user,
        reddit_fullname="t3_analytics2",
        reddit_id="analytics2",
        subreddit="django",
        title="Off topic",
        author="op2",
        permalink="/r/django/2/",
        score=1,
    )
    RedditPost.objects.filter(pk=rejected_post.pk).update(created_at=now)
    RelevanceAnalysis.objects.create(
        post=rejected_post,
        relevance_score=20,
        is_relevant=False,
        status=RelevanceAnalysis.Status.COMPLETE,
    )
    bad = DraftResponse.objects.create(
        post=rejected_post,
        body="Nope",
        status=DraftResponse.Status.REJECTED,
        generated_at=now,
        rejected_at=now,
    )
    DraftResponse.objects.filter(pk=bad.pk).update(created_at=now)


@pytest.mark.django_db
def test_compute_and_upsert_daily_stat(user) -> None:
    _seed_activity(user)
    today = timezone.now().astimezone(UTC).date()
    counters = compute_day_counters(user, today)
    assert counters["posts_discovered"] == 2
    assert counters["relevant_count"] == 1
    assert counters["drafts_generated"] == 2
    assert counters["approved"] == 1
    assert counters["rejected"] == 1

    row = upsert_daily_stat(user, today)
    assert DailyStat.objects.filter(user=user, date=today).count() == 1
    assert row.posts_discovered == 2
    # Idempotent upsert
    upsert_daily_stat(user, today)
    assert DailyStat.objects.filter(user=user, date=today).count() == 1


@pytest.mark.django_db
def test_rollup_task_and_summary_matches_db(user) -> None:
    _seed_activity(user)
    today = timezone.now().astimezone(UTC).date()
    result = rollup_daily_stats(day_iso=today.isoformat())
    assert result["users"] >= 1

    summary = summary_for_user(user, days=7)
    assert summary["totals"]["posts_discovered"] == 2
    assert summary["totals"]["approved"] == 1
    assert summary["never_auto_publish"] is True

    funnel = funnel_for_user(user, days=7)
    assert [s["key"] for s in funnel["stages"]] == [
        "discovered",
        "relevant",
        "drafted",
        "approved",
    ]
    assert funnel["stages"][0]["count"] == 2
    assert funnel["stages"][-1]["count"] == 1

    match = live_totals_match_rollup(user, days=7)
    assert match["match"] is True


@pytest.mark.django_db
def test_analytics_api_endpoints(auth_client, user) -> None:
    _seed_activity(user)
    today = timezone.now().astimezone(UTC).date()
    upsert_daily_stat(user, today)

    summary = auth_client.get("/api/v1/analytics/summary/?range=7")
    assert summary.status_code == 200
    body = summary.json()
    assert body["totals"]["posts_discovered"] == 2
    assert body["never_auto_publish"] is True
    assert len(body["series"]) >= 1

    funnel = auth_client.get("/api/v1/analytics/funnel/?range=30")
    assert funnel.status_code == 200
    assert funnel.json()["stages"][0]["count"] == 2


@pytest.mark.django_db
def test_analytics_requires_auth() -> None:
    client = APIClient()
    assert client.get("/api/v1/analytics/summary/").status_code in (401, 403)


def test_log_redaction() -> None:
    raw = "Authorization: Bearer abc.def.ghi access_token=secret123 api_key=sk-abcdef1234567890"
    redacted = redact_text(raw)
    assert "abc.def.ghi" not in redacted
    assert "secret123" not in redacted
    assert "sk-abcdef1234567890" not in redacted
    assert "[REDACTED]" in redacted


@pytest.mark.django_db
def test_empty_day_still_upserts(user) -> None:
    yesterday = timezone.now().astimezone(UTC).date() - timedelta(days=1)
    row = upsert_daily_stat(user, yesterday)
    assert row.posts_discovered == 0
    assert DailyStat.objects.filter(user=user, date=yesterday).exists()
