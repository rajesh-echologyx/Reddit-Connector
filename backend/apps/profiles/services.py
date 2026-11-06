"""Profile helpers."""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser

from .models import UserProfile


def get_or_create_profile(user: AbstractBaseUser) -> UserProfile:
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile
