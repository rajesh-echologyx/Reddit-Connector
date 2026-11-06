"""Pytest bootstrap — force test settings before Django loads."""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_ENV", "test")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("ALLOW_BOOTSTRAP", "true")
os.environ.setdefault("REDDIT_MODE", "fixture")
os.environ.setdefault("OPENAI_MODE", "mock")
# Placeholder; test settings override with a generated Fernet key.
os.environ.setdefault(
    "TOKEN_ENCRYPTION_KEY",
    "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldCEhISE=",
)
