"""Reddit Celery tasks (token refresh lands fully in Phase 5)."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="reddit.refresh_expiring_tokens")
def refresh_expiring_tokens() -> dict:
    """Stub for Phase 5 — proactive OAuth refresh within 30 min of expiry."""
    logger.info("refresh_expiring_tokens stub — no-op in Phase 2")
    return {"ok": True, "refreshed": 0}
