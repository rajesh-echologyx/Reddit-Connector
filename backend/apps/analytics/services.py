"""Aggregate helpers — source of truth is domain tables; DailyStat is a rollup cache."""

from __future__ import annotations

from datetime import date, datetime, timedelta, time
from typing import Any
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum
from django.utils import timezone

from apps.analysis.models import DraftResponse, RelevanceAnalysis
from apps.reddit.models import RedditPost

from .models import DailyStat

User = get_user_model()
UTC = ZoneInfo("UTC")


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Inclusive UTC day start → exclusive next-day start."""
    start = datetime.combine(day, time.min, tzinfo=UTC)
    end = start + timedelta(days=1)
    return start, end


def compute_day_counters(user, day: date) -> dict[str, int]:
    """Live counts for one calendar day from domain tables."""
    start, end = day_bounds(day)
    posts_discovered = RedditPost.objects.filter(
        user=user,
        created_at__gte=start,
        created_at__lt=end,
    ).count()
    relevant_count = RelevanceAnalysis.objects.filter(
        post__user=user,
        status=RelevanceAnalysis.Status.COMPLETE,
        is_relevant=True,
        created_at__gte=start,
        created_at__lt=end,
    ).count()
    drafts_generated = DraftResponse.objects.filter(
        post__user=user,
        generated_at__gte=start,
        generated_at__lt=end,
    ).exclude(status=DraftResponse.Status.DISCARDED).count()
    approved = DraftResponse.objects.filter(
        post__user=user,
        status=DraftResponse.Status.APPROVED,
        approved_at__gte=start,
        approved_at__lt=end,
    ).count()
    rejected = DraftResponse.objects.filter(
        post__user=user,
        status=DraftResponse.Status.REJECTED,
        rejected_at__gte=start,
        rejected_at__lt=end,
    ).count()
    return {
        "posts_discovered": posts_discovered,
        "relevant_count": relevant_count,
        "drafts_generated": drafts_generated,
        "approved": approved,
        "rejected": rejected,
    }


def upsert_daily_stat(user, day: date) -> DailyStat:
    """Recompute and upsert DailyStat for user/day."""
    counters = compute_day_counters(user, day)
    obj, _created = DailyStat.objects.update_or_create(
        user=user,
        date=day,
        defaults=counters,
    )
    return obj


def rollup_all_users(day: date | None = None) -> dict[str, Any]:
    """Upsert DailyStat for every user for the given day (default: yesterday UTC)."""
    if day is None:
        day = timezone.now().astimezone(UTC).date() - timedelta(days=1)
    users = User.objects.all()
    written = 0
    for user in users.iterator():
        upsert_daily_stat(user, day)
        written += 1
    return {"date": day.isoformat(), "users": written}


def range_start(days: int) -> date:
    today = timezone.now().astimezone(UTC).date()
    return today - timedelta(days=days - 1)


def ensure_rollups(user, start: date, end: date) -> None:
    """Backfill missing DailyStat rows for the inclusive date range."""
    existing = set(
        DailyStat.objects.filter(user=user, date__gte=start, date__lte=end).values_list(
            "date", flat=True
        )
    )
    cursor = start
    while cursor <= end:
        if cursor not in existing:
            upsert_daily_stat(user, cursor)
        cursor += timedelta(days=1)


def summary_for_user(user, days: int = 7) -> dict[str, Any]:
    """7d/30d counters from DailyStat (ensuring rollups exist)."""
    if days not in {7, 30}:
        days = 7
    end = timezone.now().astimezone(UTC).date()
    start = range_start(days)
    ensure_rollups(user, start, end)
    aggregates = DailyStat.objects.filter(user=user, date__gte=start, date__lte=end).aggregate(
        posts_discovered=Sum("posts_discovered"),
        relevant_count=Sum("relevant_count"),
        drafts_generated=Sum("drafts_generated"),
        approved=Sum("approved"),
        rejected=Sum("rejected"),
        days_recorded=Count("id"),
    )
    series = list(
        DailyStat.objects.filter(user=user, date__gte=start, date__lte=end)
        .order_by("date")
        .values(
            "date",
            "posts_discovered",
            "relevant_count",
            "drafts_generated",
            "approved",
            "rejected",
        )
    )
    for row in series:
        row["date"] = row["date"].isoformat()

    return {
        "range_days": days,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "totals": {
            "posts_discovered": aggregates["posts_discovered"] or 0,
            "relevant_count": aggregates["relevant_count"] or 0,
            "drafts_generated": aggregates["drafts_generated"] or 0,
            "approved": aggregates["approved"] or 0,
            "rejected": aggregates["rejected"] or 0,
        },
        "days_recorded": aggregates["days_recorded"] or 0,
        "series": series,
        "never_auto_publish": True,
    }


def funnel_for_user(user, days: int = 7) -> dict[str, Any]:
    """discovered → relevant → drafted → approved for the range."""
    summary = summary_for_user(user, days=days)
    totals = summary["totals"]
    discovered = totals["posts_discovered"]
    relevant = totals["relevant_count"]
    drafted = totals["drafts_generated"]
    approved = totals["approved"]

    def rate(num: int, den: int) -> float | None:
        if den <= 0:
            return None
        return round(num / den, 4)

    return {
        "range_days": summary["range_days"],
        "start_date": summary["start_date"],
        "end_date": summary["end_date"],
        "stages": [
            {"key": "discovered", "label": "Discovered", "count": discovered},
            {"key": "relevant", "label": "Relevant", "count": relevant},
            {"key": "drafted", "label": "Drafted", "count": drafted},
            {"key": "approved", "label": "Approved", "count": approved},
        ],
        "conversion": {
            "discovered_to_relevant": rate(relevant, discovered),
            "relevant_to_drafted": rate(drafted, relevant),
            "drafted_to_approved": rate(approved, drafted),
            "discovered_to_approved": rate(approved, discovered),
        },
        "rejected": totals["rejected"],
        "never_auto_publish": True,
    }


def live_totals_match_rollup(user, days: int = 7) -> dict[str, Any]:
    """Compare rollup totals vs live domain queries (for tests / sanity)."""
    end = timezone.now().astimezone(UTC).date()
    start = range_start(days)
    start_dt, _ = day_bounds(start)
    _, end_exclusive = day_bounds(end)

    live = {
        "posts_discovered": RedditPost.objects.filter(
            user=user, created_at__gte=start_dt, created_at__lt=end_exclusive
        ).count(),
        "relevant_count": RelevanceAnalysis.objects.filter(
            post__user=user,
            status=RelevanceAnalysis.Status.COMPLETE,
            is_relevant=True,
            created_at__gte=start_dt,
            created_at__lt=end_exclusive,
        ).count(),
        "drafts_generated": DraftResponse.objects.filter(
            post__user=user,
            generated_at__gte=start_dt,
            generated_at__lt=end_exclusive,
        )
        .exclude(status=DraftResponse.Status.DISCARDED)
        .count(),
        "approved": DraftResponse.objects.filter(
            post__user=user,
            status=DraftResponse.Status.APPROVED,
            approved_at__gte=start_dt,
            approved_at__lt=end_exclusive,
        ).count(),
        "rejected": DraftResponse.objects.filter(
            post__user=user,
            status=DraftResponse.Status.REJECTED,
            rejected_at__gte=start_dt,
            rejected_at__lt=end_exclusive,
        ).count(),
    }
    rolled = summary_for_user(user, days=days)["totals"]
    return {"live": live, "rollup": rolled, "match": live == rolled}
