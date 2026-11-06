"""Shared Celery retry countdown helpers (Reddit / OpenAI)."""

from __future__ import annotations

import random

# Plan defaults: 30s, 2m, 10m (+ jitter); then hold at 10m.
_DEFAULT_STEPS = (30, 120, 600, 600, 600)


def retry_countdown(
    retries: int,
    *,
    steps: tuple[int, ...] = _DEFAULT_STEPS,
    jitter_seconds: int = 10,
    minimum: int = 1,
) -> int:
    """Exponential-ish backoff with jitter for Celery ``countdown``."""
    idx = max(0, min(int(retries), len(steps) - 1))
    base = steps[idx]
    jitter = random.randint(0, max(0, jitter_seconds))
    return max(minimum, base + jitter)


def countdown_from_retry_after(
    wait_seconds: float | int | None,
    *,
    retries: int = 0,
    jitter_seconds: int = 5,
) -> int:
    """Prefer Retry-After / rate_limit_reset, else fall back to step backoff."""
    if wait_seconds is not None:
        try:
            wait = float(wait_seconds)
        except (TypeError, ValueError):
            wait = 0.0
        if wait > 0:
            return max(1, int(wait) + random.randint(0, max(0, jitter_seconds)))
    return retry_countdown(retries, jitter_seconds=jitter_seconds)
