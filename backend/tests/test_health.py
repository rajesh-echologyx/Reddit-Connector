"""Health endpoint tests."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_health_returns_ok_when_db_available(client: APIClient) -> None:
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    body = response.json()
    assert body["db"] is True
    assert body["never_auto_publish"] is True
    assert "reddit_mode" in body


@pytest.mark.django_db
def test_health_ready_after_migrations(client: APIClient) -> None:
    response = client.get("/api/v1/health/ready/")
    assert response.status_code == 200
    assert response.json()["ready"] is True
