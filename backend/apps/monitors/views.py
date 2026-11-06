"""CRUD + run-now + pause/resume for monitors; task monitoring API."""

from __future__ import annotations

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.models import DraftResponse, RelevanceAnalysis
from apps.reddit.models import RedditAccount, RedditPost

from .models import Keyword, Monitor, TaskRun
from .serializers import (
    KeywordCreateSerializer,
    KeywordSerializer,
    MonitorSerializer,
    TaskRunSerializer,
)
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
                {"detail": "Monitor is paused. Resume it before running.", "code": "monitor_inactive"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not monitor.keywords.exists():
            return Response(
                {"detail": "Add at least one keyword before running.", "code": "no_keywords"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        async_result = poll_monitor.delay(str(monitor.pk))
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


class MonitorPauseView(APIView):
    """Pause scheduled Beat polling for this monitor."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, pk) -> Response:
        monitor = get_object_or_404(Monitor, pk=pk, user=request.user)
        monitor.is_active = False
        monitor.save(update_fields=["is_active", "updated_at"])
        return Response(
            {
                "detail": "Monitor paused.",
                "monitor": MonitorSerializer(monitor, context={"request": request}).data,
                "never_auto_publish": True,
            }
        )


class MonitorResumeView(APIView):
    """Resume scheduled Beat polling for this monitor."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, pk) -> Response:
        monitor = get_object_or_404(Monitor, pk=pk, user=request.user)
        account = RedditAccount.objects.filter(user=request.user).first()
        if account is not None and account.status == RedditAccount.Status.EXPIRED:
            return Response(
                {
                    "detail": "Reddit token is expired. Reconnect before resuming polls.",
                    "code": "reddit_token_expired",
                    "never_auto_publish": True,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        monitor.is_active = True
        monitor.save(update_fields=["is_active", "updated_at"])
        return Response(
            {
                "detail": "Monitor resumed.",
                "monitor": MonitorSerializer(monitor, context={"request": request}).data,
                "never_auto_publish": True,
            }
        )


class TaskRunListView(generics.ListAPIView):
    """Recent Celery automation runs for the current user."""

    serializer_class = TaskRunSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = TaskRun.objects.filter(user=self.request.user).select_related("monitor")
        status_filter = self.request.query_params.get("status")
        if status_filter:
            statuses = [s.strip() for s in status_filter.split(",") if s.strip()]
            if statuses:
                qs = qs.filter(status__in=statuses)
        task_name = self.request.query_params.get("task_name")
        if task_name:
            qs = qs.filter(task_name=task_name)
        monitor_id = self.request.query_params.get("monitor")
        if monitor_id:
            qs = qs.filter(monitor_id=monitor_id)
        return qs


class TaskRunDetailView(generics.RetrieveAPIView):
    serializer_class = TaskRunSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return TaskRun.objects.filter(user=self.request.user).select_related("monitor")


class AutomationStatusView(APIView):
    """Dashboard-friendly automation summary (failures, due monitors, queue)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        user = request.user
        monitors = Monitor.objects.filter(user=user)
        active = monitors.filter(is_active=True).count()
        paused = monitors.filter(is_active=False).count()
        with_errors = monitors.exclude(last_error="").count()
        recent_failures = TaskRun.objects.filter(
            user=user, status=TaskRun.Status.FAILURE
        ).count()
        recent_runs = TaskRun.objects.filter(user=user).count()
        due_reviews = DraftResponse.objects.filter(
            post__user=user,
            status__in=[DraftResponse.Status.IN_REVIEW, DraftResponse.Status.DRAFT],
        ).count()
        analysis_failed = RelevanceAnalysis.objects.filter(
            post__user=user, status=RelevanceAnalysis.Status.FAILED
        ).count()
        posts_new = RedditPost.objects.filter(
            user=user, status=RedditPost.Status.NEW
        ).count()
        account = RedditAccount.objects.filter(user=user).first()
        reddit_status = account.status if account else None

        beat = getattr(settings, "CELERY_BEAT_SCHEDULE", {}) or {}
        schedule_names = sorted(beat.keys())

        failing_monitors = list(
            monitors.exclude(last_error="")
            .order_by("-last_error_at")
            .values("id", "name", "last_error", "last_error_at", "is_active")[:10]
        )

        return Response(
            {
                "monitors_active": active,
                "monitors_paused": paused,
                "monitors_with_errors": with_errors,
                "failing_monitors": failing_monitors,
                "task_runs_total": recent_runs,
                "task_runs_failed": recent_failures,
                "due_reviews": due_reviews,
                "analysis_failed": analysis_failed,
                "posts_awaiting_analysis": posts_new,
                "reddit_status": reddit_status,
                "beat_schedule": schedule_names,
                "auto_analyze_default": getattr(settings, "MONITOR_AUTO_ANALYZE", True),
                "auto_draft_default": getattr(settings, "MONITOR_AUTO_DRAFT", True),
                "never_auto_publish": True,
                "server_time": timezone.now().isoformat(),
            }
        )
