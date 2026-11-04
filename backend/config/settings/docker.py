"""Settings used inside Docker Compose / production-like containers."""

from __future__ import annotations

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import env, env_bool

DEBUG = env_bool("DJANGO_DEBUG", False)

database_url = env("DATABASE_URL")
if not database_url:
    raise ImproperlyConfigured("DATABASE_URL is required in docker/production settings.")

DATABASES = {
    "default": dj_database_url.parse(database_url, conn_max_age=60),
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if DJANGO_ENV == "production":  # noqa: F405
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    ALLOW_BOOTSTRAP = env_bool("ALLOW_BOOTSTRAP", False)  # noqa: F811
