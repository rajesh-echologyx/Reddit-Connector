"""Phase 4 review stubs — enough to list drafts and store approve/reject/edit.

Hard invariant: approve never posts to Reddit.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.models import DraftResponse
from apps.analysis.tasks import generate_draft_response

from .models import ReviewAction
from .serializers import ReviewActionSerializer, ReviewQueueItemSerializer


class ReviewQueueView(APIView):
    """GET /review/queue/ — drafts in draft|in_review (Phase 4 minimal)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        status_param = request.query_params.get("status", "in_review,draft")
        statuses = [s.strip() for s in status_param.split(",") if s.strip()]
        qs = (
            DraftResponse.objects.filter(post__user=request.user, status__in=statuses)
            .select_related("post", "analysis")
            .order_by("-analysis__relevance_score", "-generated_at")
        )
        data = ReviewQueueItemSerializer(qs, many=True).data
        return Response({"count": len(data), "results": data, "never_auto_publish": True})


class ReviewEditView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = get_object_or_404(
            DraftResponse, pk=draft_id, post__user=request.user
        )
        body = request.data.get("body_edited", request.data.get("body"))
        if body is None:
            return Response(
                {"detail": "body_edited is required.", "code": "invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        draft.body_edited = str(body)
        draft.save(update_fields=["body_edited", "updated_at"])
        ReviewAction.objects.create(
            draft=draft,
            actor=request.user,
            action=ReviewAction.Action.EDIT,
            notes=request.data.get("notes", ""),
            snapshot_body=draft.effective_body,
        )
        return Response(ReviewQueueItemSerializer(draft).data)


class ReviewApproveView(APIView):
    """Mark approved locally. Does NOT post to Reddit."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = get_object_or_404(
            DraftResponse, pk=draft_id, post__user=request.user
        )
        if draft.status == DraftResponse.Status.DISCARDED:
            return Response(
                {"detail": "Cannot approve a discarded draft.", "code": "invalid_state"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        draft.status = DraftResponse.Status.APPROVED
        draft.approved_at = timezone.now()
        draft.save(update_fields=["status", "approved_at", "updated_at"])
        ReviewAction.objects.create(
            draft=draft,
            actor=request.user,
            action=ReviewAction.Action.APPROVE,
            notes=request.data.get("notes", ""),
            snapshot_body=draft.effective_body,
        )
        return Response(
            {
                "detail": "Approved locally. Nothing was posted to Reddit.",
                "draft": ReviewQueueItemSerializer(draft).data,
                "never_auto_publish": True,
            }
        )


class ReviewRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = get_object_or_404(
            DraftResponse, pk=draft_id, post__user=request.user
        )
        draft.status = DraftResponse.Status.REJECTED
        draft.rejected_at = timezone.now()
        draft.save(update_fields=["status", "rejected_at", "updated_at"])
        ReviewAction.objects.create(
            draft=draft,
            actor=request.user,
            action=ReviewAction.Action.REJECT,
            notes=request.data.get("notes", ""),
            snapshot_body=draft.effective_body,
        )
        return Response(
            {
                "detail": "Rejected.",
                "draft": ReviewQueueItemSerializer(draft).data,
                "never_auto_publish": True,
            }
        )


class ReviewRegenerateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = get_object_or_404(
            DraftResponse, pk=draft_id, post__user=request.user
        )
        ReviewAction.objects.create(
            draft=draft,
            actor=request.user,
            action=ReviewAction.Action.REGENERATE,
            notes=request.data.get("notes", ""),
            snapshot_body=draft.effective_body,
        )
        async_result = generate_draft_response.delay(str(draft.post_id), force=True)
        result = None
        try:
            if async_result.successful():
                result = async_result.result
        except Exception:  # noqa: BLE001
            result = None
        return Response(
            {
                "detail": "Regenerate enqueued. Previous in-review drafts discarded.",
                "task_id": async_result.id,
                "result": result,
                "never_auto_publish": True,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class ReviewExportView(APIView):
    """Plain-text export + permalink for clipboard. Never posts."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, draft_id) -> Response:
        draft = get_object_or_404(
            DraftResponse.objects.select_related("post"),
            pk=draft_id,
            post__user=request.user,
        )
        permalink = draft.post.permalink or ""
        if permalink and not permalink.startswith("http"):
            permalink = f"https://www.reddit.com{permalink}"
        return Response(
            {
                "text": draft.effective_body,
                "permalink": permalink,
                "reddit_fullname": draft.post.reddit_fullname,
                "never_auto_publish": True,
                "detail": "Copy locally. Nothing was posted to Reddit.",
            }
        )


class ReviewActionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, draft_id) -> Response:
        draft = get_object_or_404(DraftResponse, pk=draft_id, post__user=request.user)
        actions = ReviewAction.objects.filter(draft=draft)
        return Response(ReviewActionSerializer(actions, many=True).data)
