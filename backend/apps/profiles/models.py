"""User expertise profile and writing samples for AI drafting."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """One personal profile per user — expertise, tone, model overrides."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=128, blank=True, default="")
    bio_short = models.TextField(blank=True, default="")
    expertise_topics = models.JSONField(
        default=list,
        blank=True,
        help_text="JSON array of topic strings the user may speak to.",
    )
    tone_notes = models.TextField(
        blank=True,
        default="",
        help_text="Preferred voice / tone for drafted replies.",
    )
    hard_constraints = models.TextField(
        blank=True,
        default=(
            "Never invent experience, employers, credentials, metrics, or outcomes "
            "not explicitly present in this profile or writing samples."
        ),
        help_text="Non-negotiable rules injected into AI prompts.",
    )
    openai_relevance_model = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Optional override; empty uses settings default.",
    )
    openai_draft_model = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Optional override; empty uses settings default.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return f"Profile({self.user.username})"


class WritingSample(models.Model):
    """Style samples used only for draft generation (not relevance)."""

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        IMPORTED = "imported", "Imported"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="writing_samples",
    )
    title = models.CharField(max_length=200)
    body = models.TextField()
    source = models.CharField(
        max_length=16,
        choices=Source.choices,
        default=Source.MANUAL,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.title
