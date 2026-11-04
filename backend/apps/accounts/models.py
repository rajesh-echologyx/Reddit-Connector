"""Custom user model — multi-user-ready from day one."""

from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Application user. Domain rows FK to this model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_personal_owner = models.BooleanField(
        default=False,
        help_text="Convenience flag for the single personal operator bootstrap.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["username"]

    def __str__(self) -> str:
        return self.username
