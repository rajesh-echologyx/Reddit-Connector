"""Fixture Reddit client + rate-limit helpers."""

from __future__ import annotations

from apps.reddit.client import FixtureRedditClient, get_reddit_client
from apps.reddit.rate_limit import backoff_from_headers
from django.test import override_settings


def test_fixture_client_loads_sample_posts() -> None:
    client = FixtureRedditClient()
    identity = client.get_identity()
    assert identity["name"] == "fixture_user"
    results = client.search("django")
    assert len(results) >= 1
    assert all(r.reddit_fullname.startswith("t3_") for r in results)


def test_fixture_client_subreddit_filter() -> None:
    client = FixtureRedditClient()
    results = client.search("oauth", subreddit="learnprogramming")
    assert results
    assert all(r.subreddit == "learnprogramming" for r in results)


def test_fixture_client_has_many_posts() -> None:
    client = FixtureRedditClient()
    # Broad query via empty-ish match: search common words across fixtures
    all_hits = client.search("a", limit=100)
    # fixture matcher requires word presence; use a very common letter carefully —
    # instead load internal list
    posts = client._load()
    assert len(posts) >= 20
    subs = {p.subreddit for p in posts}
    assert len(subs) >= 3


@override_settings(REDDIT_MODE="fixture")
def test_get_reddit_client_fixture_mode() -> None:
    client = get_reddit_client()
    assert isinstance(client, FixtureRedditClient)


def test_backoff_from_retry_after() -> None:
    assert backoff_from_headers({"Retry-After": "12"}) == 12.0
    assert backoff_from_headers({"retry-after": "5"}) == 5.0


def test_backoff_from_ratelimit_headers() -> None:
    wait = backoff_from_headers(
        {"X-Ratelimit-Remaining": "0", "X-Ratelimit-Reset": "30"}
    )
    assert wait == 30.0
