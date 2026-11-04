"""Auth session + CSRF + bootstrap tests."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def client() -> APIClient:
    return APIClient(enforce_csrf_checks=True)


@pytest.mark.django_db
def test_csrf_sets_cookie(client: APIClient) -> None:
    response = client.get("/api/v1/auth/csrf/")
    assert response.status_code == 200
    assert "csrftoken" in response.cookies
    assert "csrfToken" in response.json()


@pytest.mark.django_db
@override_settings(ALLOW_BOOTSTRAP=True)
def test_bootstrap_creates_owner_and_logs_in(client: APIClient) -> None:
    # Obtain CSRF
    csrf = client.get("/api/v1/auth/csrf/")
    token = csrf.cookies["csrftoken"].value

    response = client.post(
        "/api/v1/auth/bootstrap/",
        {"username": "owner", "password": "Str0ngPass!word"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "owner"
    assert body["is_personal_owner"] is True
    assert User.objects.filter(username="owner").exists()

    me = client.get("/api/v1/auth/me/")
    assert me.status_code == 200
    assert me.json()["username"] == "owner"


@pytest.mark.django_db
@override_settings(ALLOW_BOOTSTRAP=True)
def test_bootstrap_rejected_when_users_exist(client: APIClient) -> None:
    User.objects.create_user(username="existing", password="Str0ngPass!word")
    csrf = client.get("/api/v1/auth/csrf/")
    token = csrf.cookies["csrftoken"].value

    response = client.post(
        "/api/v1/auth/bootstrap/",
        {"username": "other", "password": "Str0ngPass!word"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 409


@pytest.mark.django_db
@override_settings(ALLOW_BOOTSTRAP=False)
def test_bootstrap_disabled(client: APIClient) -> None:
    csrf = client.get("/api/v1/auth/csrf/")
    token = csrf.cookies["csrftoken"].value

    response = client.post(
        "/api/v1/auth/bootstrap/",
        {"username": "owner", "password": "Str0ngPass!word"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_login_logout_session(client: APIClient) -> None:
    User.objects.create_user(username="alice", password="Str0ngPass!word")
    csrf = client.get("/api/v1/auth/csrf/")
    token = csrf.cookies["csrftoken"].value

    login = client.post(
        "/api/v1/auth/login/",
        {"username": "alice", "password": "Str0ngPass!word"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert login.status_code == 200
    assert login.json()["username"] == "alice"

    me = client.get("/api/v1/auth/me/")
    assert me.status_code == 200

    # Refresh CSRF after login (session may rotate cookie)
    csrf = client.get("/api/v1/auth/csrf/")
    token = csrf.cookies["csrftoken"].value

    logout = client.post(
        "/api/v1/auth/logout/",
        {},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert logout.status_code == 200

    me_after = client.get("/api/v1/auth/me/")
    assert me_after.status_code == 403


@pytest.mark.django_db
def test_login_rejects_bad_credentials(client: APIClient) -> None:
    User.objects.create_user(username="alice", password="Str0ngPass!word")
    csrf = client.get("/api/v1/auth/csrf/")
    token = csrf.cookies["csrftoken"].value

    response = client.post(
        "/api/v1/auth/login/",
        {"username": "alice", "password": "wrong"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_me_requires_auth(client: APIClient) -> None:
    response = client.get("/api/v1/auth/me/")
    assert response.status_code in (401, 403)
