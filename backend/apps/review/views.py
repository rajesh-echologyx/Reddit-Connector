"""Phase 4 review workflow.

Hard invariant: approve / mark-published never posts to Reddit.
Authenticated Reddit submit stays behind REDDIT_SUBMIT_ENABLED (default false).
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.analysis.models import DraftResponse

from . import services
from .models import ReviewAction
from .serializers import ReviewActionSerializer, ReviewQueueItemSerializer


def _owned_draft(request: Request, draft_id) -> DraftResponse:
    return get_object_or_404(
        DraftResponse.objects.select_related("post", "analysis"),
        pk=draft_id,
        post__user=request.user,
    )


def _state_error_response(exc: services.ReviewStateError) -> Response:
    return Response(
        {"detail": exc.detail, "code": exc.code, "never_auto_publish": True},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _ok(result: services.ReviewResult, *, http_status: int = status.HTTP_200_OK) -> Response:
    payload: dict = {
        "detail": result.detail,
        "draft": ReviewQueueItemSerializer(result.draft).data,
        "never_auto_publish": True,
        "reddit_submit_enabled": services.reddit_submit_enabled(),
    }
    if result.extra:
        payload.update(result.extra)
    return Response(payload, status=http_status)


class ReviewQueueView(APIView):
    """GET /review/queue/ — filterable draft queue."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request) -> Response:
        status_param = request.query_params.get(
            "status",
            "in_review,draft",
        )
        statuses = [s.strip() for s in status_param.split(",") if s.strip()]
        qs = (
            DraftResponse.objects.filter(post__user=request.user, status__in=statuses)
            .select_related("post", "analysis")
            .order_by("-analysis__relevance_score", "-generated_at")
        )
        data = ReviewQueueItemSerializer(qs, many=True).data
        return Response(
            {
                "count": len(data),
                "results": data,
                "never_auto_publish": True,
                "reddit_submit_enabled": services.reddit_submit_enabled(),
            }
        )


class ReviewDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        return Response(
            {
                "draft": ReviewQueueItemSerializer(draft).data,
                "never_auto_publish": True,
                "reddit_submit_enabled": services.reddit_submit_enabled(),
            }
        )


class ReviewEditView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        body = request.data.get("body_edited", request.data.get("body"))
        if body is None:
            return Response(
                {"detail": "body_edited is required.", "code": "invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = services.edit_draft(
                draft,
                request.user,
                body_edited=str(body),
                notes=str(request.data.get("notes", "")),
            )
        except services.ReviewStateError as exc:
            return _state_error_response(exc)
        return Response(ReviewQueueItemSerializer(result.draft).data)


class ReviewApproveView(APIView):
    """Mark approved locally. Does NOT post to Reddit."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        try:
            result = services.approve_draft(
                draft,
                request.user,
                notes=str(request.data.get("notes", "")),
            )
        except services.ReviewStateError as exc:
            return _state_error_response(exc)
        return _ok(result)


class ReviewRejectView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        try:
            result = services.reject_draft(
                draft,
                request.user,
                notes=str(request.data.get("notes", "")),
            )
        except services.ReviewStateError as exc:
            return _state_error_response(exc)
        return _ok(result)


class ReviewSaveForLaterView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        try:
            result = services.save_for_later(
                draft,
                request.user,
                notes=str(request.data.get("notes", "")),
            )
        except services.ReviewStateError as exc:
            return _state_error_response(exc)
        return _ok(result)


class ReviewReopenView(APIView):
    """Return a saved-for-later draft to the active queue."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        try:
            result = services.reopen_draft(
                draft,
                request.user,
                notes=str(request.data.get("notes", "")),
            )
        except services.ReviewStateError as exc:
            return _state_error_response(exc)
        return _ok(result)


class ReviewMarkPublishedView(APIView):
    """Operator confirms they manually posted. Never calls Reddit API."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        try:
            result = services.mark_published(
                draft,
                request.user,
                notes=str(request.data.get("notes", "")),
            )
        except services.ReviewStateError as exc:
            return _state_error_response(exc)
        return _ok(result)


class ReviewNotesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        if "private_notes" not in request.data and "notes" not in request.data:
            return Response(
                {"detail": "private_notes is required.", "code": "invalid"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        notes = request.data.get("private_notes", request.data.get("notes", ""))
        try:
            result = services.update_private_notes(
                draft,
                request.user,
                private_notes=str(notes),
            )
        except services.ReviewStateError as exc:
            return _state_error_response(exc)
        return _ok(result)


class ReviewRegenerateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        try:
            result = services.regenerate_draft(
                draft,
                request.user,
                notes=str(request.data.get("notes", "")),
            )
        except services.ReviewStateError as exc:
            return _state_error_response(exc)
        return _ok(result, http_status=status.HTTP_202_ACCEPTED)


class ReviewExportView(APIView):
    """Plain-text export + permalink for clipboard. Never posts."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        return Response(services.export_payload(draft))


class ReviewSubmitView(APIView):
    """Optional Reddit submit — disabled unless REDDIT_SUBMIT_ENABLED=true.

    Default is off. Even when enabled, this endpoint still requires an
    explicit human POST and never runs from Celery/Beat.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        if not services.reddit_submit_enabled():
            return Response(
                {
                    "detail": (
                        "Authenticated Reddit comment submit is disabled. "
                        "Copy the draft and post manually, or set "
                        "REDDIT_SUBMIT_ENABLED=true (still never auto-publishes)."
                    ),
                    "code": "submit_disabled",
                    "never_auto_publish": True,
                    "reddit_submit_enabled": False,
                    "draft_id": str(draft.pk),
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        # Flag is on but Phase 4 still does not implement live submit.
        return Response(
            {
                "detail": (
                    "REDDIT_SUBMIT_ENABLED is true, but live Reddit submit is "
                    "not implemented in Phase 4. Copy/export instead."
                ),
                "code": "submit_not_implemented",
                "never_auto_publish": True,
                "reddit_submit_enabled": True,
                "draft_id": str(draft.pk),
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )


class ReviewActionListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request: Request, draft_id) -> Response:
        draft = _owned_draft(request, draft_id)
        actions = ReviewAction.objects.filter(draft=draft)
        return Response(ReviewActionSerializer(actions, many=True).data)
