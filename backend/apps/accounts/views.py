"""Auth + health endpoints for Phase 1."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.db import connection
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from .serializers import BootstrapSerializer, LoginSerializer, UserSerializer

User = get_user_model()


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
def csrf(request: Request) -> Response:
    """Ensure CSRF cookie is set for the SPA."""
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def login_view(request: Request) -> Response:
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data["user"]
    login(request, user)
    return Response(UserSerializer(user).data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request: Request) -> Response:
    logout(request)
    return Response({"detail": "Logged out."})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def me(request: Request) -> Response:
    return Response(UserSerializer(request.user).data)


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def bootstrap(request: Request) -> Response:
    """Dev/first-run: create personal owner if zero users exist."""
    if not settings.ALLOW_BOOTSTRAP:
        return Response(
            {"detail": "Bootstrap is disabled.", "code": "bootstrap_disabled"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if User.objects.exists():
        return Response(
            {
                "detail": "Users already exist; bootstrap is no longer available.",
                "code": "bootstrap_unavailable",
            },
            status=status.HTTP_409_CONFLICT,
        )

    serializer = BootstrapSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    login(request, user)
    return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


def _redis_ping() -> bool:
    try:
        import redis

        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        return bool(client.ping())
    except Exception:
        return False


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health(request: Request) -> Response:
    """Liveness: DB + Redis ping."""
    db_ok = False
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    redis_ok = _redis_ping()
    payload = {
        "status": "ok" if db_ok else "degraded",
        "db": db_ok,
        "redis": redis_ok,
        "reddit_mode": getattr(settings, "REDDIT_MODE", "unknown"),
        "never_auto_publish": True,
    }
    code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response(payload, status=code)


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def health_ready(request: Request) -> Response:
    """Readiness: migrations applied."""
    from django.db.migrations.executor import MigrationExecutor

    try:
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        ready = len(plan) == 0
    except Exception as exc:
        return Response(
            {"ready": False, "detail": str(exc)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {"ready": ready, "pending_migrations": len(plan) if not ready else 0},
        status=status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
