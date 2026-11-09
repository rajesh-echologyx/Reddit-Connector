"""Fast test settings (in-memory SQLite, eager Celery)."""

from __future__ import annotations

from cryptography.fernet import Fernet

from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ALLOW_BOOTSTRAP = True  # noqa: F811
REDDIT_MODE = "fixture"  # noqa: F811
OPENAI_MODE = "mock"  # noqa: F811
OPENAI_API_KEY = ""  # noqa: F811
# Stable Fernet key for deterministic encrypt/decrypt tests
TOKEN_ENCRYPTION_KEY = Fernet.generate_key().decode()  # noqa: F811

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "raddit-test",
    }
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Faster/simpler static files in tests (avoid Manifest storage + collectstatic).
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Generous auth throttles so unit tests do not hit 429.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        "login": "1000/minute",
        "bootstrap": "1000/hour",
    },
}
