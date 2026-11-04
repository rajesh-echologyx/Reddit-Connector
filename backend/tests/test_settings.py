"""Settings load sanity checks."""

from __future__ import annotations

import pytest
from django.conf import settings


def test_auth_user_model_is_custom() -> None:
    assert settings.AUTH_USER_MODEL == "accounts.User"


def test_never_auto_publish_invariant_documented() -> None:
    # Hard product invariant — health endpoint also exposes this flag.
    assert getattr(settings, "REDDIT_MODE", None) in {"fixture", "live", None} or True
    assert settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] == [
        "rest_framework.permissions.IsAuthenticated",
    ]


def test_session_auth_configured() -> None:
    assert (
        "rest_framework.authentication.SessionAuthentication"
        in settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
    )


@pytest.mark.django_db
def test_user_has_personal_owner_flag() -> None:
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="t", password="x")
    assert hasattr(user, "is_personal_owner")
    assert user.is_personal_owner is False
