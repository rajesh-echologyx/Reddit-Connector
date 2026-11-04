"""OAuth start/status/disconnect + state validation."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.reddit.models import RedditAccount
from apps.reddit.services import ensure_fixture_account, store_oauth_tokens
from apps.reddit.crypto import decrypt_token

User = get_user_model()


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(username="owner", password="Str0ngPass!word")


@pytest.fixture
def auth_client(api: APIClient, user) -> APIClient:
    api.force_authenticate(user=user)
    return api


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture")
def test_status_ensures_fixture_account(auth_client: APIClient) -> None:
    response = auth_client.get("/api/v1/reddit/status/")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "fixture"
    assert body["connected"] is True
    assert body["status"] == "dev_fixture"
    assert body["never_auto_publish"] is True
    assert RedditAccount.objects.filter(status="dev_fixture").exists()


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture")
def test_oauth_start_fixture_mode(auth_client: APIClient) -> None:
    response = auth_client.get("/api/v1/reddit/oauth/start/")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "fixture"
    assert body["authorize_url"] is None


@pytest.mark.django_db
@override_settings(
    REDDIT_MODE="live",
    REDDIT_CLIENT_ID="cid",
    REDDIT_CLIENT_SECRET="csecret",
    REDDIT_REDIRECT_URI="http://localhost:8000/api/v1/reddit/oauth/callback/",
)
def test_oauth_start_live_returns_authorize_url(auth_client: APIClient, user) -> None:
    response = auth_client.get("/api/v1/reddit/oauth/start/")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "live"
    assert "reddit.com/api/v1/authorize" in body["authorize_url"]
    assert "client_id=cid" in body["authorize_url"]
    assert "scope=identity+read" in body["authorize_url"] or "scope=identity%20read" in body["authorize_url"]
    state = body["state"]
    assert cache.get(f"reddit:oauth:state:{state}") == str(user.pk)


@pytest.mark.django_db
@override_settings(REDDIT_MODE="live", REDDIT_CLIENT_ID="", REDDIT_CLIENT_SECRET="")
def test_oauth_start_unconfigured(auth_client: APIClient) -> None:
    response = auth_client.get("/api/v1/reddit/oauth/start/")
    assert response.status_code == 503


@pytest.mark.django_db
@override_settings(REDDIT_MODE="live")
def test_oauth_callback_rejects_invalid_state(api: APIClient) -> None:
    response = api.get(
        "/api/v1/reddit/oauth/callback/",
        {"code": "abc", "state": "bad"},
    )
    assert response.status_code in (302, 301)
    assert "invalid_state" in response.url


@pytest.mark.django_db
def test_store_oauth_tokens_encrypts(user) -> None:
    account = store_oauth_tokens(
        user,
        access_token="access-plain",
        refresh_token="refresh-plain",
        expires_in=3600,
        scope="identity read",
        identity={"name": "u_test", "id": "rid1"},
    )
    assert account.status == RedditAccount.Status.CONNECTED
    assert account.reddit_username == "u_test"
    assert account.access_token_encrypted != "access-plain"
    assert decrypt_token(account.access_token_encrypted) == "access-plain"
    assert decrypt_token(account.refresh_token_encrypted) == "refresh-plain"


@pytest.mark.django_db
@override_settings(REDDIT_MODE="fixture")
def test_disconnect_fixture(auth_client: APIClient, user) -> None:
    ensure_fixture_account(user)
    response = auth_client.post("/api/v1/reddit/disconnect/", {}, format="json")
    assert response.status_code == 200
    account = RedditAccount.objects.get(user=user)
    assert account.status == RedditAccount.Status.DEV_FIXTURE
