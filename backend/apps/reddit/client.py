"""Reddit API client interface with live + fixture implementations."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from django.conf import settings

logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "fixtures" / "reddit"


@dataclass
class RedditSearchResult:
    """Normalized search hit used by poll/upsert."""

    reddit_fullname: str
    reddit_id: str
    subreddit: str
    title: str
    selftext: str
    author: str
    url: str
    permalink: str
    score: int
    num_comments: int
    created_utc: float | None
    over_18: bool
    raw: dict[str, Any]


def _normalize_listing_child(child: dict[str, Any]) -> RedditSearchResult | None:
    data = child.get("data") if "data" in child else child
    if not isinstance(data, dict):
        return None
    name = data.get("name") or ""
    if not name and data.get("id"):
        name = f"t3_{data['id']}"
    if not name.startswith("t3_"):
        # Skip non-link things if any slip through
        if data.get("id"):
            name = f"t3_{data['id']}"
        else:
            return None
    permalink = data.get("permalink") or ""
    if permalink and not permalink.startswith("http"):
        permalink_path = permalink
        permalink_url = f"https://www.reddit.com{permalink}"
    else:
        permalink_path = permalink.replace("https://www.reddit.com", "")
        permalink_url = permalink or data.get("url") or ""

    return RedditSearchResult(
        reddit_fullname=name,
        reddit_id=str(data.get("id") or name.removeprefix("t3_")),
        subreddit=str(data.get("subreddit") or "").lower(),
        title=str(data.get("title") or ""),
        selftext=str(data.get("selftext") or ""),
        author=str(data.get("author") or ""),
        url=str(data.get("url") or permalink_url),
        permalink=permalink_path or permalink_url,
        score=int(data.get("score") or 0),
        num_comments=int(data.get("num_comments") or 0),
        created_utc=float(data["created_utc"]) if data.get("created_utc") is not None else None,
        over_18=bool(data.get("over_18") or data.get("over18") or False),
        raw=data,
    )


class RedditClient(ABC):
    """Shared interface for live OAuth Reddit and fixture mode."""

    @abstractmethod
    def get_identity(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        subreddit: str | None = None,
        limit: int = 25,
        sort: str = "new",
        include_nsfw: bool = False,
    ) -> list[RedditSearchResult]:
        raise NotImplementedError


class FixtureRedditClient(RedditClient):
    """Reads sample posts from backend/fixtures/reddit/*.json."""

    def __init__(self, fixtures_dir: Path | None = None) -> None:
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR
        self._posts: list[RedditSearchResult] | None = None

    def _load(self) -> list[RedditSearchResult]:
        if self._posts is not None:
            return self._posts
        posts: list[RedditSearchResult] = []
        if not self.fixtures_dir.exists():
            self._posts = posts
            return posts
        for path in sorted(self.fixtures_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("skipping fixture %s: %s", path, exc)
                continue
            children = payload
            if isinstance(payload, dict):
                if "data" in payload and isinstance(payload["data"], dict):
                    children = payload["data"].get("children", [])
                elif "posts" in payload:
                    children = payload["posts"]
                else:
                    children = [payload]
            if not isinstance(children, list):
                continue
            for child in children:
                normalized = _normalize_listing_child(child)
                if normalized:
                    posts.append(normalized)
        self._posts = posts
        return posts

    def get_identity(self) -> dict[str, Any]:
        return {
            "name": "fixture_user",
            "id": "fixture",
            "mode": "fixture",
        }

    def search(
        self,
        query: str,
        *,
        subreddit: str | None = None,
        limit: int = 25,
        sort: str = "new",
        include_nsfw: bool = False,
    ) -> list[RedditSearchResult]:
        del sort  # fixtures are pre-sorted by created_utc desc
        q = query.strip().lower()
        words = [w for w in q.replace('"', "").split() if w]
        results: list[RedditSearchResult] = []
        for post in self._load():
            if subreddit and post.subreddit.lower() != subreddit.lower().lstrip("r/"):
                continue
            if post.over_18 and not include_nsfw:
                continue
            hay = f"{post.title} {post.selftext}".lower()
            if words and not all(w in hay for w in words) and q not in hay:
                # Match any word for fixture convenience when query has multiple tokens
                if not any(w in hay for w in words):
                    continue
            results.append(post)
            if len(results) >= limit:
                break
        return results


class LiveRedditClient(RedditClient):
    """Official Reddit OAuth API client (no scraping)."""

    AUTH_URL = "https://www.reddit.com/api/v1/access_token"
    API_BASE = "https://oauth.reddit.com"

    def __init__(self, access_token: str, user_agent: str | None = None) -> None:
        self.access_token = access_token
        self.user_agent = user_agent or settings.REDDIT_USER_AGENT

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": self.user_agent,
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        import httpx

        url = f"{self.API_BASE}{path}"
        with httpx.Client(timeout=30.0) as client:
            response = client.request(method, url, headers=self._headers(), **kwargs)
            if response.status_code == 429:
                from .rate_limit import backoff_from_headers

                wait = backoff_from_headers(dict(response.headers))
                raise RedditRateLimitError(wait_seconds=wait or 60.0, headers=dict(response.headers))
            response.raise_for_status()
            return response.json()

    def get_identity(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/me")

    def search(
        self,
        query: str,
        *,
        subreddit: str | None = None,
        limit: int = 25,
        sort: str = "new",
        include_nsfw: bool = False,
    ) -> list[RedditSearchResult]:
        params = {
            "q": query,
            "limit": min(max(limit, 1), 100),
            "sort": sort,
            "type": "link",
            "restrict_sr": "true" if subreddit else "false",
            "include_over_18": "on" if include_nsfw else "off",
        }
        if subreddit:
            path = f"/r/{subreddit.lstrip('r/')}/search"
        else:
            path = "/search"
        payload = self._request("GET", f"{path}?{urlencode(params)}")
        children = payload.get("data", {}).get("children", [])
        results: list[RedditSearchResult] = []
        for child in children:
            normalized = _normalize_listing_child(child)
            if normalized:
                if normalized.over_18 and not include_nsfw:
                    continue
                results.append(normalized)
        return results


class RedditRateLimitError(Exception):
    def __init__(self, wait_seconds: float, headers: dict | None = None) -> None:
        self.wait_seconds = wait_seconds
        self.headers = headers or {}
        super().__init__(f"Reddit rate limited; retry after {wait_seconds}s")


def get_reddit_client(*, access_token: str | None = None) -> RedditClient:
    """Factory: fixture client when REDDIT_MODE=fixture, else live OAuth client."""
    mode = getattr(settings, "REDDIT_MODE", "fixture")
    if mode == "fixture":
        return FixtureRedditClient()
    if not access_token:
        raise ValueError("access_token required when REDDIT_MODE=live")
    return LiveRedditClient(access_token=access_token)


def build_authorize_url(*, state: str, scopes: str = "identity read") -> str:
    params = {
        "client_id": settings.REDDIT_CLIENT_ID,
        "response_type": "code",
        "state": state,
        "redirect_uri": settings.REDDIT_REDIRECT_URI,
        "duration": "permanent",
        "scope": scopes,
    }
    return f"https://www.reddit.com/api/v1/authorize?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict[str, Any]:
    """Authorization-code exchange against Reddit's token endpoint."""
    import httpx

    auth = (settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.REDDIT_REDIRECT_URI,
    }
    headers = {"User-Agent": settings.REDDIT_USER_AGENT}
    with httpx.Client(timeout=30.0) as client:
        response = client.post(
            "https://www.reddit.com/api/v1/access_token",
            data=data,
            auth=auth,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()


def revoke_token(token: str) -> None:
    """Best-effort token revoke (ignore failures)."""
    import httpx

    if not token or not settings.REDDIT_CLIENT_ID:
        return
    try:
        with httpx.Client(timeout=15.0) as client:
            client.post(
                "https://www.reddit.com/api/v1/revoke_token",
                data={"token": token, "token_type_hint": "refresh_token"},
                auth=(settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET),
                headers={"User-Agent": settings.REDDIT_USER_AGENT},
            )
    except Exception as exc:  # noqa: BLE001
        logger.info("Reddit revoke failed (ignored): %s", exc)
