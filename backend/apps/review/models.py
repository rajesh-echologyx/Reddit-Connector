"""Review audit log. Phase 4 expands the full workflow UI."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ReviewAction(models.Model):
    """Append-only audit log for draft decisions. Never update/delete rows."""

    class Action(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        EDIT = "edit", "Edit"
        REGENERATE = "regenerate", "Regenerate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(
        "analysis.DraftResponse",
        on_delete=models.CASCADE,
        related_name="review_actions",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_actions",
    )
    action = models.CharField(max_length=16, choices=Action.choices)
    notes = models.TextField(blank=True, default="")
    snapshot_body = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} on {self.draft_id} by {self.actor_id}"

    def save(self, *args, **kwargs):
        if self.pk and ReviewAction.objects.filter(pk=self.pk).exists():
            raise ValueError("ReviewAction is append-only and cannot be updated.")
        return super().save(*args, **kwargs)
