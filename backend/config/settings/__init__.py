"""Load settings module based on DJANGO_ENV.

Usage:
  DJANGO_ENV=local|docker|test|production
  DJANGO_SETTINGS_MODULE=config.settings  (this package)
"""

from __future__ import annotations

import os

_env = os.environ.get("DJANGO_ENV", "local").strip().lower()

if _env in {"test", "ci"}:
    from .test import *  # noqa: F401,F403
elif _env in {"docker", "compose"}:
    from .docker import *  # noqa: F401,F403
elif _env in {"production", "prod"}:
    from .production import *  # noqa: F401,F403
else:
    from .local import *  # noqa: F401,F403
