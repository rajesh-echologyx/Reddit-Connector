"""Fernet helpers for encrypting Reddit OAuth tokens at rest."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet, InvalidToken


def _fernet() -> Fernet:
    key = getattr(settings, "TOKEN_ENCRYPTION_KEY", "") or ""
    if not key:
        raise ImproperlyConfigured(
            "TOKEN_ENCRYPTION_KEY is required to encrypt Reddit tokens. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:  # noqa: BLE001
        raise ImproperlyConfigured(
            "TOKEN_ENCRYPTION_KEY is not a valid Fernet key."
        ) from exc


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string; returns url-safe base64 ciphertext."""
    if plaintext == "":
        return ""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a previously encrypted token string."""
    if ciphertext == "":
        return ""
    try:
        return _fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt token with TOKEN_ENCRYPTION_KEY") from exc
