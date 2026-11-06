"""Analytics API — summary + funnel from DailyStat / domain tables."""

from __future__ import annotations

from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.request import Request
from rest_framework.response import Response

from .services import funnel_for_user, summary_for_user


def _parse_days(request: Request) -> int:
    raw = request.query_params.get("range", request.query_params.get("days", "7"))
    try:
        days = int(raw)
    except (TypeError, ValueError):
        days = 7
    if days not in {7, 30}:
        days = 7
    return days


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def analytics_summary(request: Request) -> Response:
    """GET /analytics/summary/?range=7|30 — range counters + daily series."""
    days = _parse_days(request)
    return Response(summary_for_user(request.user, days=days))


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def analytics_funnel(request: Request) -> Response:
    """GET /analytics/funnel/?range=7|30 — discovered → relevant → drafted → approved."""
    days = _parse_days(request)
    return Response(funnel_for_user(request.user, days=days))
