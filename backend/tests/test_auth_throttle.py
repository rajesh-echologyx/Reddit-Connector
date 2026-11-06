"""Auth endpoint rate-limit coverage."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.throttles import LoginRateThrottle

User = get_user_model()


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    cache.clear()


@pytest.mark.django_db
def test_login_throttled_after_burst(monkeypatch) -> None:
    # DRF binds THROTTLE_RATES at class import time — patch for a tight limit.
    monkeypatch.setitem(LoginRateThrottle.THROTTLE_RATES, "login", "2/minute")
    cache.clear()

    User.objects.create_user(username="alice", password="Str0ngPass!word")
    client = APIClient(enforce_csrf_checks=True)

    def attempt() -> int:
        csrf = client.get("/api/v1/auth/csrf/")
        token = csrf.cookies["csrftoken"].value
        response = client.post(
            "/api/v1/auth/login/",
            {"username": "alice", "password": "wrong"},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        return response.status_code

    assert attempt() == 400
    assert attempt() == 400
    assert attempt() == 429


def test_login_throttle_scope_configured() -> None:
    assert LoginRateThrottle.scope == "login"
    from django.conf import settings

    assert "login" in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
