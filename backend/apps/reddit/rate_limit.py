"""Conservative Reddit rate-limit helpers (Redis-backed when available).

Phase 2 ships stubs that honor Retry-After / remaining headers and an
in-process / Redis token bucket. Full Beat stampede protection lands in Phase 5.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_REQUESTS_PER_MINUTE = 30
LOCK_TTL_SECONDS = 60


@dataclass
class RateLimitDecision:
    allowed: bool
    wait_seconds: float = 0.0
    remaining: int | None = None
    reason: str = ""


def _redis():
    try:
        import redis

        return redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
    except Exception:  # noqa: BLE001
        return None


def acquire_account_lock(account_id: str, ttl: int = LOCK_TTL_SECONDS) -> bool:
    """Serialize polls per RedditAccount. Returns True if lock acquired."""
    client = _redis()
    key = f"reddit:lock:{account_id}"
    if client is None:
        # No Redis (e.g. unit tests without broker) — allow.
        return True
    try:
        return bool(client.set(key, "1", nx=True, ex=ttl))
    except Exception as exc:  # noqa: BLE001
        logger.warning("reddit lock unavailable: %s", exc)
        return True


def release_account_lock(account_id: str) -> None:
    client = _redis()
    if client is None:
        return
    try:
        client.delete(f"reddit:lock:{account_id}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("reddit lock release failed: %s", exc)


def check_token_bucket(
    account_id: str,
    *,
    requests_per_minute: int = DEFAULT_REQUESTS_PER_MINUTE,
) -> RateLimitDecision:
    """Simple fixed-window counter. Fail-open when Redis is down."""
    client = _redis()
    if client is None:
        return RateLimitDecision(allowed=True, remaining=requests_per_minute)

    window = int(time.time() // 60)
    key = f"reddit:bucket:{account_id}:{window}"
    try:
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, 120)
        remaining = max(0, requests_per_minute - count)
        if count > requests_per_minute:
            wait = 60 - (time.time() % 60)
            return RateLimitDecision(
                allowed=False,
                wait_seconds=wait,
                remaining=0,
                reason="token_bucket_exhausted",
            )
        return RateLimitDecision(allowed=True, remaining=remaining)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reddit token bucket unavailable: %s", exc)
        return RateLimitDecision(allowed=True, remaining=None)


def backoff_from_headers(headers: dict) -> float:
    """Compute countdown from Reddit rate-limit / Retry-After headers."""
    retry_after = headers.get("Retry-After") or headers.get("retry-after")
    if retry_after is not None:
        try:
            return max(float(retry_after), 1.0)
        except (TypeError, ValueError):
            pass

    remaining = headers.get("X-Ratelimit-Remaining") or headers.get(
        "x-ratelimit-remaining"
    )
    reset = headers.get("X-Ratelimit-Reset") or headers.get("x-ratelimit-reset")
    try:
        if remaining is not None and float(remaining) < 1 and reset is not None:
            return max(float(reset), 1.0)
    except (TypeError, ValueError):
        pass
    return 0.0
