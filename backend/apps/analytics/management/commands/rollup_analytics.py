"""Manually roll up or backfill DailyStat rows."""

from __future__ import annotations

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analytics.services import rollup_all_users

UTC = ZoneInfo("UTC")


class Command(BaseCommand):
    help = "Upsert DailyStat for all users (yesterday by default, or --days backfill)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--date",
            type=str,
            default="",
            help="UTC date YYYY-MM-DD (default: yesterday).",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=0,
            help="If set, backfill this many days inclusive of today.",
        )

    def handle(self, *args, **options) -> None:
        days = int(options["days"] or 0)
        if days > 0:
            today = timezone.now().astimezone(UTC).date()
            total = 0
            for offset in range(days):
                day = today - timedelta(days=offset)
                result = rollup_all_users(day=day)
                total += result["users"]
                self.stdout.write(f"{result['date']}: {result['users']} users")
            self.stdout.write(self.style.SUCCESS(f"Backfilled {days} days ({total} rows)."))
            return

        day: date | None = None
        if options["date"]:
            day = date.fromisoformat(options["date"])
        result = rollup_all_users(day=day)
        self.stdout.write(
            self.style.SUCCESS(f"Rolled up {result['date']} for {result['users']} users.")
        )
