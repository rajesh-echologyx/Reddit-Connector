"""Token encryption round-trip tests."""

from __future__ import annotations

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from apps.reddit.crypto import decrypt_token, encrypt_token


@pytest.mark.django_db
def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "reddit-access-token-xyz"
    cipher = encrypt_token(plaintext)
    assert cipher != plaintext
    assert decrypt_token(cipher) == plaintext


def test_encrypt_requires_key() -> None:
    with override_settings(TOKEN_ENCRYPTION_KEY=""):
        with pytest.raises(ImproperlyConfigured):
            encrypt_token("x")


def test_empty_token_passthrough() -> None:
    assert encrypt_token("") == ""
    assert decrypt_token("") == ""
