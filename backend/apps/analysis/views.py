"""Enqueue analyze/draft + post detail with analysis."""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reddit.models import RedditPost

from .models import DraftResponse, RelevanceAnalysis
from .serializers import (
    DraftResponseSerializer,
    RedditPostDetailSerializer,
    RelevanceAnalysisSerializer,
)
from .tasks import analyze_post_relevance, generate_draft_response


def _task_result_payload(async_result):
    result_payload = None
    try:
        if async_result.successful():
            result_payload = async_result.result
    except Exception:  # noqa: BLE001
        result_payload = None
    return result_payload


class PostDetailWithAnalysisView(APIView):
    """GET /posts/{id}/ — detail + analysis + drafts."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, pk) -> Response:
        post = get_object_or_404(
            RedditPost.objects.select_related("analysis").prefetch_related("drafts"),
            pk=pk,
            user=request.user,
        )
        return Response(RedditPostDetailSerializer(post).data)


class PostAnalyzeView(APIView):
    """POST /posts/{id}/analyze/ — enqueue relevance analysis."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, pk) -> Response:
        post = get_object_or_404(RedditPost, pk=pk, user=request.user)
        force = bool(request.data.get("force", False))
        async_result = analyze_post_relevance.delay(str(post.pk), force=force)
        return Response(
            {
                "detail": "Relevance analysis enqueued.",
                "task_id": async_result.id,
                "post_id": str(post.pk),
                "result": _task_result_payload(async_result),
                "never_auto_publish": True,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class PostDraftView(APIView):
    """POST /posts/{id}/draft/ — enqueue draft generation (requires relevant analysis)."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, pk) -> Response:
        post = get_object_or_404(RedditPost, pk=pk, user=request.user)
        analysis = RelevanceAnalysis.objects.filter(post=post).first()
        if analysis is None or analysis.status != RelevanceAnalysis.Status.COMPLETE:
            return Response(
                {
                    "detail": "Run relevance analysis first.",
                    "code": "analysis_required",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not analysis.is_relevant:
            return Response(
                {
                    "detail": "Post was scored not relevant; draft skipped.",
                    "code": "post_not_relevant",
                    "relevance_score": analysis.relevance_score,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        force = bool(request.data.get("force", False))
        async_result = generate_draft_response.delay(str(post.pk), force=force)
        return Response(
            {
                "detail": "Draft generation enqueued.",
                "task_id": async_result.id,
                "post_id": str(post.pk),
                "result": _task_result_payload(async_result),
                "never_auto_publish": True,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class AnalysisDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, pk) -> Response:
        analysis = get_object_or_404(
            RelevanceAnalysis,
            pk=pk,
            post__user=request.user,
        )
        return Response(RelevanceAnalysisSerializer(analysis).data)


class DraftDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, pk) -> Response:
        draft = get_object_or_404(DraftResponse, pk=pk, post__user=request.user)
        return Response(DraftResponseSerializer(draft).data)
