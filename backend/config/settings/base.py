"""Shared Django settings for all environments."""

from __future__ import annotations

import os
from pathlib import Path

from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(key: str, default: str = "") -> list[str]:
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

DJANGO_ENV = env("DJANGO_ENV", "local") or "local"
SECRET_KEY = env("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = False
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,web")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "corsheaders",
    "rest_framework",
    # Local apps
    "apps.accounts",
    "apps.profiles",
    "apps.reddit",
    "apps.monitors",
    "apps.analysis",
    "apps.review",
    "apps.analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Default static storage; production overrides to CompressedManifest.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database (overridden per environment)
# ---------------------------------------------------------------------------

DATABASES: dict = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------------------
# Auth / passwords
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# i18n / static
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "login": "20/minute",
        "bootstrap": "5/hour",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "EXCEPTION_HANDLER": "apps.accounts.exceptions.api_exception_handler",
}

# ---------------------------------------------------------------------------
# CORS / CSRF (SPA)
# ---------------------------------------------------------------------------

FRONTEND_ORIGIN = env("FRONTEND_ORIGIN", "http://localhost:5173") or "http://localhost:5173"
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", FRONTEND_ORIGIN)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", FRONTEND_ORIGIN)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # SPA must read CSRF cookie
CSRF_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------------------
# Cache (OAuth state); prefer Redis when available
# ---------------------------------------------------------------------------

REDIS_URL = env("REDIS_URL", "redis://localhost:6379/0") or "redis://localhost:6379/0"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "raddit-default",
    }
}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_ACKS_LATE = True

# Phase 5–6 Beat schedule — discover loop, token refresh, analytics rollup.
CELERY_BEAT_SCHEDULE: dict = {
    "dispatch-due-monitors-every-5-min": {
        "task": "monitors.dispatch_due_monitors",
        "schedule": 300.0,
        "options": {"expires": 240},
    },
    "refresh-expiring-reddit-tokens-hourly": {
        "task": "reddit.refresh_expiring_tokens",
        "schedule": crontab(minute=5),
        "options": {"expires": 3500},
    },
    "rollup-daily-stats": {
        "task": "analytics.rollup_daily_stats",
        "schedule": crontab(hour=0, minute=5),
        "options": {"expires": 3500},
    },
}

# Auto-chain defaults (per-monitor flags can disable). Never auto-publish.
MONITOR_AUTO_ANALYZE = env_bool("MONITOR_AUTO_ANALYZE", True)
MONITOR_AUTO_DRAFT = env_bool("MONITOR_AUTO_DRAFT", True)

# ---------------------------------------------------------------------------
# Application settings
# ---------------------------------------------------------------------------

ALLOW_BOOTSTRAP = env_bool("ALLOW_BOOTSTRAP", True)
REDDIT_MODE = env("REDDIT_MODE", "fixture") or "fixture"
RELEVANCE_THRESHOLD = int(env("RELEVANCE_THRESHOLD", "70") or "70")
TOKEN_ENCRYPTION_KEY = env("TOKEN_ENCRYPTION_KEY", "")

REDDIT_CLIENT_ID = env("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = env("REDDIT_CLIENT_SECRET", "")
REDDIT_REDIRECT_URI = env(
    "REDDIT_REDIRECT_URI",
    "http://localhost:8000/api/v1/reddit/oauth/callback/",
)
REDDIT_USER_AGENT = env(
    "REDDIT_USER_AGENT",
    "web:raddit-connector:v0.1.0 (by /u/YOUR_USER)",
)
OPENAI_API_KEY = env("OPENAI_API_KEY", "")
# mock = fixture/deterministic responses (default local/CI). live = OpenAI API.
OPENAI_MODE = (env("OPENAI_MODE", "mock") or "mock").lower()
OPENAI_RELEVANCE_MODEL = env("OPENAI_RELEVANCE_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
OPENAI_DRAFT_MODEL = env("OPENAI_DRAFT_MODEL", "gpt-4o-mini") or "gpt-4o-mini"
MAX_ACTIVE_WRITING_SAMPLES = int(env("MAX_ACTIVE_WRITING_SAMPLES", "5") or "5")

# Phase 4+: authenticated Reddit comment submit. Default OFF.
# Even when true, submit is never automatic — only an explicit human API call.
# Phase 4 still returns 501 when the flag is on (copy/export is the publish path).
REDDIT_SUBMIT_ENABLED = env_bool("REDDIT_SUBMIT_ENABLED", False)

# Hard invariant: fixture mode must never run in production.
if DJANGO_ENV == "production" and REDDIT_MODE == "fixture":
    raise ImproperlyConfigured(
        "REDDIT_MODE=fixture is refused when DJANGO_ENV=production."
    )

# Live OpenAI without a key is a configuration error (mock mode is fine without a key).
if OPENAI_MODE == "live" and not OPENAI_API_KEY and DJANGO_ENV == "production":
    raise ImproperlyConfigured(
        "OPENAI_MODE=live requires OPENAI_API_KEY when DJANGO_ENV=production."
    )

# ---------------------------------------------------------------------------
# Logging (redact secrets / Authorization headers)
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_secrets": {
            "()": "apps.analytics.logging_filters.RedactSecretsFilter",
        },
    },
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["redact_secrets"],
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL", "INFO") or "INFO",
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": env("LOG_LEVEL", "INFO") or "INFO",
            "propagate": False,
        },
    },
}
