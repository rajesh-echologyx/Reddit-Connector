"""Auth endpoint rate limits."""

from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Throttle login attempts (anon scope keyed by IP)."""

    scope = "login"


class BootstrapRateThrottle(AnonRateThrottle):
    """Throttle first-run bootstrap (anon scope keyed by IP)."""

    scope = "bootstrap"
