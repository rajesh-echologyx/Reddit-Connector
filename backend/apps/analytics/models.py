"""Daily aggregate counters for the analytics dashboard."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class DailyStat(models.Model):
    """Per-user daily funnel counters. Upserted by Beat rollup."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="daily_stats",
    )
    date = models.DateField(db_index=True)
    posts_discovered = models.PositiveIntegerField(default=0)
    relevant_count = models.PositiveIntegerField(default=0)
    drafts_generated = models.PositiveIntegerField(default=0)
    approved = models.PositiveIntegerField(default=0)
    rejected = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "date"],
                name="analytics_dailystat_user_date_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "date"]),
        ]

    def __str__(self) -> str:
        return f"DailyStat({self.user_id}, {self.date})"
