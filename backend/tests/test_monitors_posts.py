"""Monitors CRUD, poll upsert idempotency, posts list."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from apps.monitors.models import Keyword, Monitor
from apps.monitors.tasks import poll_monitor
from apps.reddit.client import RedditSearchResult
from apps.reddit.models import RedditPost
from apps.reddit.services import ensure_fixture_account, upsert_post

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


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", CELERY_TASK_ALWAYS_EAGER=True)
def test_monitor_crud_and_keywords(auth_client: APIClient) -> None:
    create = auth_client.post(
        "/api/v1/monitors/",
        {
            "name": "Python watch",
            "poll_interval_minutes": 15,
            "subreddit_names": ["python", "r/webdev"],
        },
        format="json",
    )
    assert create.status_code == 201
    monitor_id = create.json()["id"]
    assert len(create.json()["subreddits"]) == 2

    kw = auth_client.post(
        f"/api/v1/monitors/{monitor_id}/keywords/",
        {"phrase": "django celery", "match_mode": "all_words"},
        format="json",
    )
    assert kw.status_code == 201

    listing = auth_client.get("/api/v1/monitors/")
    assert listing.status_code == 200
    results = listing.json()["results"] if "results" in listing.json() else listing.json()
    assert any(m["name"] == "Python watch" for m in results)

    replace = auth_client.put(
        f"/api/v1/monitors/{monitor_id}/subreddits/",
        {"subreddits": ["datascience"]},
        format="json",
    )
    assert replace.status_code == 200
    assert [s["name"] for s in replace.json()["subreddits"]] == ["datascience"]


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", CELERY_TASK_ALWAYS_EAGER=True)
def test_poll_monitor_upserts_and_dedupes(user) -> None:
    ensure_fixture_account(user)
    monitor = Monitor.objects.create(user=user, name="Fixture poll", is_active=True)
    Keyword.objects.create(monitor=monitor, phrase="django", match_mode="any")

    first = poll_monitor(str(monitor.pk))
    assert first["ok"] is True
    assert first["created"] >= 1
    count_after_first = RedditPost.objects.count()
    assert count_after_first >= 1

    second = poll_monitor(str(monitor.pk))
    assert second["ok"] is True
    assert RedditPost.objects.count() == count_after_first
    assert second["created"] == 0
    assert second["updated"] >= 1


@pytest.mark.django_db
def test_upsert_idempotent_by_reddit_fullname(user) -> None:
    result = RedditSearchResult(
        reddit_fullname="t3_dupetest",
        reddit_id="dupetest",
        subreddit="python",
        title="Hello",
        selftext="body",
        author="a",
        url="https://www.reddit.com/r/python/comments/dupetest/",
        permalink="/r/python/comments/dupetest/",
        score=10,
        num_comments=1,
        created_utc=1730400000,
        over_18=False,
        raw={"id": "dupetest", "name": "t3_dupetest", "score": 10},
    )
    post1, created1 = upsert_post(user=user, result=result)
    assert created1 is True
    result.score = 99
    post2, created2 = upsert_post(user=user, result=result)
    assert created2 is False
    assert post1.pk == post2.pk
    assert RedditPost.objects.filter(reddit_fullname="t3_dupetest").count() == 1
    post2.refresh_from_db()
    assert post2.score == 99


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture", CELERY_TASK_ALWAYS_EAGER=True)
def test_run_now_and_posts_list(auth_client: APIClient, user) -> None:
    ensure_fixture_account(user)
    monitor = Monitor.objects.create(user=user, name="Run now", is_active=True)
    Keyword.objects.create(monitor=monitor, phrase="reddit", match_mode="any")

    run = auth_client.post(f"/api/v1/monitors/{monitor.pk}/run/", {}, format="json")
    assert run.status_code == 202
    assert run.json()["never_auto_publish"] is True

    posts = auth_client.get("/api/v1/posts/")
    assert posts.status_code == 200
    payload = posts.json()
    results = payload["results"] if "results" in payload else payload
    assert isinstance(results, list)
    assert len(results) >= 1
    assert "reddit_fullname" in results[0]


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture")
def test_run_requires_keywords(auth_client: APIClient, user) -> None:
    monitor = Monitor.objects.create(user=user, name="Empty", is_active=True)
    run = auth_client.post(f"/api/v1/monitors/{monitor.pk}/run/", {}, format="json")
    assert run.status_code == 400
    assert run.json()["code"] == "no_keywords"


@pytest.mark.django_db
def test_rate_limit_lock_helpers() -> None:
    from apps.reddit.rate_limit import acquire_account_lock, check_token_bucket, release_account_lock

    assert acquire_account_lock("acct-test") is True
    decision = check_token_bucket("acct-test")
    assert decision.allowed is True
    release_account_lock("acct-test")
