"""Production settings sanity + fixture-mode hard fail."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _run_settings_snippet(env: dict[str, str], snippet: str) -> subprocess.CompletedProcess[str]:
    full_env = {**os.environ, **env, "PYTHONPATH": str(BACKEND_ROOT)}
    return subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=str(BACKEND_ROOT),
        env=full_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_fixture_mode_refused_in_production() -> None:
    result = _run_settings_snippet(
        {
            "DJANGO_ENV": "production",
            "REDDIT_MODE": "fixture",
            "DJANGO_SECRET_KEY": "x" * 40,
            "TOKEN_ENCRYPTION_KEY": "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldCEhISE=",
            "DATABASE_URL": "postgres://raddit:raddit@localhost:5432/raddit",
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "OPENAI_MODE": "mock",
            "REDIS_URL": "redis://localhost:6379/0",
        },
        "import config.settings.base",
    )
    assert result.returncode != 0
    combined = result.stderr + result.stdout
    assert "REDDIT_MODE=fixture" in combined


def test_production_requires_strong_secret() -> None:
    result = _run_settings_snippet(
        {
            "DJANGO_ENV": "production",
            "REDDIT_MODE": "live",
            "DJANGO_SECRET_KEY": "dev",
            "TOKEN_ENCRYPTION_KEY": "dGVzdC1rZXktMzItYnl0ZXMtZm9yLWZlcm5ldCEhISE=",
            "DATABASE_URL": "postgres://raddit:raddit@localhost:5432/raddit",
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "OPENAI_MODE": "mock",
            "REDIS_URL": "redis://localhost:6379/0",
        },
        "import config.settings.production",
    )
    assert result.returncode != 0
    combined = result.stderr + result.stdout
    assert "DJANGO_SECRET_KEY" in combined


def test_production_boot_ok_with_live_reddit() -> None:
    from cryptography.fernet import Fernet

    key = Fernet.generate_key().decode()
    result = _run_settings_snippet(
        {
            "DJANGO_ENV": "production",
            "REDDIT_MODE": "live",
            "DJANGO_SECRET_KEY": "prod-secret-key-with-enough-length-32+",
            "TOKEN_ENCRYPTION_KEY": key,
            "DATABASE_URL": "postgres://raddit:raddit@localhost:5432/raddit",
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "OPENAI_MODE": "mock",
            "REDIS_URL": "redis://localhost:6379/0",
            "ALLOW_BOOTSTRAP": "false",
            "CORS_ALLOWED_ORIGINS": "https://example.com",
            "CSRF_TRUSTED_ORIGINS": "https://example.com",
            "FRONTEND_ORIGIN": "https://example.com",
            "SECURE_SSL_REDIRECT": "false",
        },
        (
            "import config.settings.production as s; "
            "assert s.DEBUG is False; "
            "assert s.REDDIT_MODE == 'live'; "
            "assert s.ALLOW_BOOTSTRAP is False; "
            "print('ok')"
        ),
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_beat_includes_analytics_rollup() -> None:
    from django.conf import settings

    assert "rollup-daily-stats" in settings.CELERY_BEAT_SCHEDULE
    entry = settings.CELERY_BEAT_SCHEDULE["rollup-daily-stats"]
    assert entry["task"] == "analytics.rollup_daily_stats"


def test_auth_throttle_rates_configured() -> None:
    from django.conf import settings

    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
    assert "login" in rates
    assert "bootstrap" in rates
