"""CRUD + run-now for monitors and keywords."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Keyword, Monitor
from .serializers import KeywordCreateSerializer, KeywordSerializer, MonitorSerializer
from .tasks import poll_monitor


class MonitorListCreateView(generics.ListCreateAPIView):
    serializer_class = MonitorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Monitor.objects.filter(user=self.request.user).prefetch_related(
            "keywords",
            "subreddits",
        )


class MonitorDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MonitorSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Monitor.objects.filter(user=self.request.user).prefetch_related(
            "keywords",
            "subreddits",
        )


class MonitorKeywordListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_monitor(self) -> Monitor:
        return get_object_or_404(Monitor, pk=self.kwargs["pk"], user=self.request.user)

    def get_queryset(self):
        return Keyword.objects.filter(monitor=self.get_monitor())

    def get_serializer_class(self):
        if self.request.method == "POST":
            return KeywordCreateSerializer
        return KeywordSerializer

    def perform_create(self, serializer):
        serializer.save(monitor=self.get_monitor())


class MonitorKeywordDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = KeywordSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = "keyword_id"

    def get_queryset(self):
        return Keyword.objects.filter(
            monitor__user=self.request.user,
            monitor_id=self.kwargs["pk"],
        )


class MonitorSubredditsReplaceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request: Request, pk) -> Response:
        monitor = get_object_or_404(Monitor, pk=pk, user=request.user)
        names = request.data.get("subreddits", request.data.get("names", []))
        if not isinstance(names, list):
            return Response(
                {"detail": "subreddits must be a list of names.", "code": "invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = MonitorSerializer(
            monitor,
            data={"subreddit_names": names},
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MonitorSerializer(monitor, context={"request": request}).data)


class MonitorRunView(APIView):
    """Enqueue an immediate poll for this monitor (manual search trigger)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, pk) -> Response:
        monitor = get_object_or_404(Monitor, pk=pk, user=request.user)
        if not monitor.is_active:
            return Response(
                {"detail": "Monitor is inactive.", "code": "monitor_inactive"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not monitor.keywords.exists():
            return Response(
                {"detail": "Add at least one keyword before running.", "code": "no_keywords"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        async_result = poll_monitor.delay(str(monitor.pk))
        # When CELERY_TASK_ALWAYS_EAGER, result is already available.
        result_payload = None
        try:
            if async_result.successful():
                result_payload = async_result.result
        except Exception:  # noqa: BLE001
            result_payload = None

        return Response(
            {
                "detail": "Poll enqueued.",
                "task_id": async_result.id,
                "monitor_id": str(monitor.pk),
                "result": result_payload,
                "never_auto_publish": True,
            },
            status=status.HTTP_202_ACCEPTED,
        )
