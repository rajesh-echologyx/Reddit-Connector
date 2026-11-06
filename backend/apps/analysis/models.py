"""AI relevance analysis and draft response models."""

from __future__ import annotations

import uuid

from django.db import models


class RelevanceAnalysis(models.Model):
    """Structured relevance score for a RedditPost."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETE = "complete", "Complete"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.OneToOneField(
        "reddit.RedditPost",
        on_delete=models.CASCADE,
        related_name="analysis",
    )
    relevance_score = models.PositiveSmallIntegerField(default=0)
    is_relevant = models.BooleanField(default=False)
    reasons = models.JSONField(default=list, blank=True)
    matched_expertise = models.JSONField(default=list, blank=True)
    risk_flags = models.JSONField(default=list, blank=True)
    summary = models.TextField(blank=True, default="")
    model = models.CharField(max_length=64, blank=True, default="")
    prompt_version = models.CharField(max_length=32, blank=True, default="")
    raw_response = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-relevance_score", "-created_at"]
        indexes = [
            models.Index(fields=["is_relevant", "relevance_score"]),
        ]

    def __str__(self) -> str:
        return f"Analysis({self.post_id}, score={self.relevance_score}, {self.status})"


class DraftResponse(models.Model):
    """AI-generated reply draft. Never auto-published to Reddit."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        IN_REVIEW = "in_review", "In review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        DISCARDED = "discarded", "Discarded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(
        "reddit.RedditPost",
        on_delete=models.CASCADE,
        related_name="drafts",
    )
    analysis = models.ForeignKey(
        RelevanceAnalysis,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="drafts",
    )
    body = models.TextField(blank=True, default="")
    body_edited = models.TextField(
        null=True,
        blank=True,
        help_text="Reviewer edit wins for copy/export; never auto-posted.",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    tone = models.CharField(max_length=64, blank=True, default="")
    claims_made = models.JSONField(default=list, blank=True)
    needs_human_check = models.JSONField(default=list, blank=True)
    model = models.CharField(max_length=64, blank=True, default="")
    prompt_version = models.CharField(max_length=32, blank=True, default="")
    raw_response = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    generated_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-generated_at", "-created_at"]
        indexes = [
            models.Index(fields=["status", "generated_at"]),
        ]

    def __str__(self) -> str:
        return f"Draft({self.post_id}, {self.status})"

    @property
    def effective_body(self) -> str:
        if self.body_edited is not None and self.body_edited != "":
            return self.body_edited
        return self.body
