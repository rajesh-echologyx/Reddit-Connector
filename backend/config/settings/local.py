"""Local development settings (SQLite by default; Postgres via DATABASE_URL)."""

from __future__ import annotations

import dj_database_url

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = True

database_url = env("DATABASE_URL")
if database_url:
    DATABASES = {
        "default": dj_database_url.parse(database_url, conn_max_age=60),
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Allow local Vite + Django origins during development.
CSRF_TRUSTED_ORIGINS = list(
    {
        *CSRF_TRUSTED_ORIGINS,  # noqa: F405
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    }
)
CORS_ALLOWED_ORIGINS = list(
    {
        *CORS_ALLOWED_ORIGINS,  # noqa: F405
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
)
