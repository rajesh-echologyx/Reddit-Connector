"""Reddit account + discovered post models."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class RedditAccount(models.Model):
    """One Reddit OAuth connection (or fixture stub) per user."""

    class Status(models.TextChoices):
        CONNECTED = "connected", "Connected"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"
        DEV_FIXTURE = "dev_fixture", "Development fixture"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reddit_account",
    )
    reddit_username = models.CharField(max_length=64, blank=True, default="")
    reddit_user_id = models.CharField(max_length=64, blank=True, default="")
    access_token_encrypted = models.TextField(blank=True, default="")
    refresh_token_encrypted = models.TextField(blank=True, default="")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.CharField(max_length=255, blank=True, default="identity,read")
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.DEV_FIXTURE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        label = self.reddit_username or self.user.username
        return f"{label} ({self.status})"


class RedditPost(models.Model):
    """A Reddit submission discovered via search; deduped by reddit_fullname."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        ANALYZING = "analyzing", "Analyzing"
        SCORED = "scored", "Scored"
        SKIPPED = "skipped", "Skipped"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reddit_posts",
    )
    reddit_fullname = models.CharField(max_length=32, unique=True, db_index=True)
    reddit_id = models.CharField(max_length=16, blank=True, default="")
    subreddit = models.CharField(max_length=128, db_index=True)
    title = models.TextField()
    selftext = models.TextField(blank=True, default="")
    author = models.CharField(max_length=64, blank=True, default="")
    url = models.URLField(max_length=2048, blank=True, default="")
    permalink = models.CharField(max_length=512, blank=True, default="")
    score = models.IntegerField(default=0)
    num_comments = models.IntegerField(default=0)
    created_utc = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    discovered_via_monitor = models.ForeignKey(
        "monitors.Monitor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discovered_posts",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_utc", "-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["subreddit", "created_utc"]),
            models.Index(fields=["created_utc"]),
        ]

    def __str__(self) -> str:
        return f"{self.reddit_fullname}: {self.title[:60]}"
