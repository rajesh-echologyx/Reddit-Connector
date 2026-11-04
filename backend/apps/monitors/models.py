"""Keyword / subreddit monitors that drive Reddit discovery."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Subreddit(models.Model):
    """Canonical subreddit name (lowercase, no r/ prefix)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, unique=True)
    reddit_id = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        self.name = self.name.strip().lstrip("r/").lower()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"r/{self.name}"


class Monitor(models.Model):
    """A user's keyword/subreddit search configuration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="monitors",
    )
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    poll_interval_minutes = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(5)],
    )
    min_score = models.IntegerField(null=True, blank=True)
    min_comments = models.IntegerField(null=True, blank=True)
    include_nsfw = models.BooleanField(default=False)
    subreddits = models.ManyToManyField(
        Subreddit,
        blank=True,
        related_name="monitors",
    )
    last_polled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Keyword(models.Model):
    """Search phrase attached to a monitor."""

    class MatchMode(models.TextChoices):
        ANY = "any", "Any word"
        ALL_WORDS = "all_words", "All words"
        EXACT_PHRASE = "exact_phrase", "Exact phrase"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    monitor = models.ForeignKey(
        Monitor,
        on_delete=models.CASCADE,
        related_name="keywords",
    )
    phrase = models.CharField(max_length=255)
    match_mode = models.CharField(
        max_length=32,
        choices=MatchMode.choices,
        default=MatchMode.ANY,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["phrase"]
        constraints = [
            models.UniqueConstraint(
                fields=["monitor", "phrase", "match_mode"],
                name="uniq_monitor_phrase_match_mode",
            )
        ]

    def __str__(self) -> str:
        return f"{self.phrase} ({self.match_mode})"
