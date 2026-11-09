"""Settings used inside Docker Compose (local/dev containers).

Production uses ``config.settings.production`` via ``DJANGO_ENV=production``.
"""

from __future__ import annotations

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import env, env_bool

DEBUG = env_bool("DJANGO_DEBUG", False)

database_url = env("DATABASE_URL")
if not database_url:
    raise ImproperlyConfigured("DATABASE_URL is required in docker settings.")

DATABASES = {
    "default": dj_database_url.parse(database_url, conn_max_age=60),
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Prefer Redis for OAuth state / throttles when available in compose.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,  # noqa: F405
    }
}
