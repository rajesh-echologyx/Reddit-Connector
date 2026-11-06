"""Production settings — refuse insecure defaults and fixture mode."""

from __future__ import annotations

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import SECRET_KEY, TOKEN_ENCRYPTION_KEY, env, env_bool, env_list

DEBUG = False

# Refuse known-insecure placeholders.
_INSECURE_SECRETS = {
    "",
    "change-me-to-a-long-random-string",
    "dev-insecure-change-me",
    "dev",
    "test-secret-key-not-for-production",
    "ci-test-secret",
}
if not SECRET_KEY or SECRET_KEY in _INSECURE_SECRETS or len(SECRET_KEY) < 32:
    raise ImproperlyConfigured(
        "DJANGO_SECRET_KEY must be a unique secret (≥32 chars) in production."
    )

if not TOKEN_ENCRYPTION_KEY:
    raise ImproperlyConfigured(
        "TOKEN_ENCRYPTION_KEY is required in production for Reddit token encryption."
    )

database_url = env("DATABASE_URL")
if not database_url:
    raise ImproperlyConfigured("DATABASE_URL is required in production.")

DATABASES = {
    "default": dj_database_url.parse(database_url, conn_max_age=60),
}

# Prefer Redis cache in production when REDIS_URL is set.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,  # noqa: F405
    }
}

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("DJANGO_ALLOWED_HOSTS must be set in production.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
SECURE_HSTS_SECONDS = int(env("SECURE_HSTS_SECONDS", "31536000") or "31536000")
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

ALLOW_BOOTSTRAP = env_bool("ALLOW_BOOTSTRAP", False)  # noqa: F811

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# CORS must be an explicit allowlist — never "*" with credentials.
if "*" in CORS_ALLOWED_ORIGINS:  # noqa: F405
    raise ImproperlyConfigured(
        "CORS_ALLOWED_ORIGINS must not include '*' when credentials are enabled."
    )

# Fixture Reddit mode already refused in base when DJANGO_ENV=production.
