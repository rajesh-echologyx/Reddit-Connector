"""Celery tasks for analytics rollups."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from celery import shared_task
from django.utils import timezone

from .services import rollup_all_users

logger = logging.getLogger(__name__)
UTC = ZoneInfo("UTC")


@shared_task(
    name="analytics.rollup_daily_stats",
    soft_time_limit=120,
    time_limit=180,
)
def rollup_daily_stats(day_iso: str | None = None) -> dict:
    """Upsert DailyStat for all users for a UTC calendar day.

    Default: yesterday UTC (Beat runs at 00:05).
    """
    day: date | None = None
    if day_iso:
        day = date.fromisoformat(day_iso)
    result = rollup_all_users(day=day)
    logger.info(
        "analytics.rollup_daily_stats complete date=%s users=%s",
        result["date"],
        result["users"],
    )
    return result


@shared_task(
    name="analytics.backfill_daily_stats",
    soft_time_limit=300,
    time_limit=360,
)
def backfill_daily_stats(days: int = 30) -> dict:
    """Backfill DailyStat for the last N days (inclusive of today)."""
    days = max(1, min(int(days), 365))
    today = timezone.now().astimezone(UTC).date()
    written = 0
    for offset in range(days):
        day = today - timedelta(days=offset)
        result = rollup_all_users(day=day)
        written += result["users"]
    return {"days": days, "user_day_rows": written}
