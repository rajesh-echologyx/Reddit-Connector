"""Profile + writing samples API."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="owner",
        password="Str0ngPass!word",
        is_personal_owner=True,
    )


@pytest.fixture
def auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
def test_profile_get_creates_and_patch(auth_client: APIClient) -> None:
    get_resp = auth_client.get("/api/v1/profile/")
    assert get_resp.status_code == 200
    assert get_resp.json()["expertise_topics"] == []

    patch = auth_client.patch(
        "/api/v1/profile/",
        {
            "display_name": "Raj",
            "expertise_topics": ["django", "celery", "  "],
            "tone_notes": "concise and practical",
            "hard_constraints": "Never invent experience.",
            "openai_relevance_model": "gpt-4o-mini",
        },
        format="json",
    )
    assert patch.status_code == 200
    body = patch.json()
    assert body["display_name"] == "Raj"
    assert body["expertise_topics"] == ["django", "celery"]
    assert body["openai_relevance_model"] == "gpt-4o-mini"


@pytest.mark.django_db
@override_settings(MAX_ACTIVE_WRITING_SAMPLES=2)
def test_writing_samples_cap_active(auth_client: APIClient) -> None:
    for i in range(2):
        resp = auth_client.post(
            "/api/v1/writing-samples/",
            {"title": f"Sample {i}", "body": f"Body {i}", "is_active": True},
            format="json",
        )
        assert resp.status_code == 201

    overflow = auth_client.post(
        "/api/v1/writing-samples/",
        {"title": "Too many", "body": "Nope", "is_active": True},
        format="json",
    )
    assert overflow.status_code == 400

    inactive = auth_client.post(
        "/api/v1/writing-samples/",
        {"title": "Inactive ok", "body": "Fine", "is_active": False},
        format="json",
    )
    assert inactive.status_code == 201

    listing = auth_client.get("/api/v1/writing-samples/")
    assert listing.status_code == 200
    results = listing.json()["results"] if "results" in listing.json() else listing.json()
    assert len(results) == 3
