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
    # Phase 5: after discover, auto relevance; if relevant, auto draft → review.
    # Never auto-approve or auto-publish.
    auto_analyze = models.BooleanField(default=True)
    auto_draft = models.BooleanField(default=True)
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
    last_error = models.TextField(blank=True, default="")
    last_error_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def clear_error(self) -> None:
        if self.last_error or self.last_error_at:
            self.last_error = ""
            self.last_error_at = None
            self.save(update_fields=["last_error", "last_error_at", "updated_at"])

    def record_error(self, message: str) -> None:
        from django.utils import timezone

        self.last_error = (message or "")[:2000]
        self.last_error_at = timezone.now()
        self.save(update_fields=["last_error", "last_error_at", "updated_at"])


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


class TaskRun(models.Model):
    """Persisted Celery task run for the task monitoring UI (never auto-publishes)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        STARTED = "started", "Started"
        SUCCESS = "success", "Success"
        FAILURE = "failure", "Failure"
        RETRY = "retry", "Retry"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_runs",
        null=True,
        blank=True,
    )
    task_name = models.CharField(max_length=128, db_index=True)
    celery_task_id = models.CharField(max_length=255, blank=True, default="", db_index=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    monitor = models.ForeignKey(
        Monitor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="task_runs",
    )
    post_id = models.UUIDField(null=True, blank=True, db_index=True)
    message = models.TextField(blank=True, default="")
    result = models.JSONField(default=dict, blank=True)
    retries = models.PositiveIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["task_name", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.task_name} ({self.status})"
