"""Review workflow state machine. Approve never posts to Reddit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.analysis.models import DraftResponse
from apps.analysis.tasks import generate_draft_response

from .models import ReviewAction

ACTIVE_QUEUE_STATUSES = (
    DraftResponse.Status.DRAFT,
    DraftResponse.Status.IN_REVIEW,
)

EDITABLE_STATUSES = (
    DraftResponse.Status.DRAFT,
    DraftResponse.Status.IN_REVIEW,
    DraftResponse.Status.SAVED_FOR_LATER,
    DraftResponse.Status.APPROVED,
)

APPROVABLE_STATUSES = (
    DraftResponse.Status.DRAFT,
    DraftResponse.Status.IN_REVIEW,
    DraftResponse.Status.SAVED_FOR_LATER,
)

REJECTABLE_STATUSES = (
    DraftResponse.Status.DRAFT,
    DraftResponse.Status.IN_REVIEW,
    DraftResponse.Status.SAVED_FOR_LATER,
    DraftResponse.Status.APPROVED,
)

SAVE_LATER_STATUSES = (
    DraftResponse.Status.DRAFT,
    DraftResponse.Status.IN_REVIEW,
)

REOPEN_STATUSES = (DraftResponse.Status.SAVED_FOR_LATER,)

PUBLISHABLE_STATUSES = (
    DraftResponse.Status.APPROVED,
    DraftResponse.Status.IN_REVIEW,
    DraftResponse.Status.SAVED_FOR_LATER,
)

REGENERATABLE_STATUSES = (
    DraftResponse.Status.DRAFT,
    DraftResponse.Status.IN_REVIEW,
    DraftResponse.Status.SAVED_FOR_LATER,
    DraftResponse.Status.REJECTED,
)

DISCARD_ON_REGENERATE = (
    DraftResponse.Status.DRAFT,
    DraftResponse.Status.IN_REVIEW,
    DraftResponse.Status.SAVED_FOR_LATER,
)


class ReviewStateError(ValueError):
    """Invalid draft transition."""

    def __init__(self, detail: str, code: str = "invalid_state"):
        super().__init__(detail)
        self.detail = detail
        self.code = code


@dataclass
class ReviewResult:
    draft: DraftResponse
    detail: str
    extra: dict[str, Any] | None = None


def _log(
    draft: DraftResponse,
    actor,
    action: str,
    *,
    notes: str = "",
) -> ReviewAction:
    return ReviewAction.objects.create(
        draft=draft,
        actor=actor,
        action=action,
        notes=notes or "",
        snapshot_body=draft.effective_body,
    )


def _ensure_status(draft: DraftResponse, allowed: tuple[str, ...], verb: str) -> None:
    if draft.status not in allowed:
        raise ReviewStateError(
            f"Cannot {verb} a draft in status '{draft.status}'.",
            code="invalid_state",
        )


def absolute_reddit_url(draft: DraftResponse) -> str:
    permalink = draft.post.permalink or ""
    if permalink and not permalink.startswith("http"):
        return f"https://www.reddit.com{permalink}"
    if permalink:
        return permalink
    return draft.post.url or ""


@transaction.atomic
def edit_draft(
    draft: DraftResponse,
    actor,
    *,
    body_edited: str,
    notes: str = "",
) -> ReviewResult:
    _ensure_status(draft, EDITABLE_STATUSES, "edit")
    draft.body_edited = body_edited
    draft.save(update_fields=["body_edited", "updated_at"])
    _log(draft, actor, ReviewAction.Action.EDIT, notes=notes)
    return ReviewResult(draft=draft, detail="Edit saved.")


@transaction.atomic
def approve_draft(draft: DraftResponse, actor, *, notes: str = "") -> ReviewResult:
    _ensure_status(draft, APPROVABLE_STATUSES, "approve")
    draft.status = DraftResponse.Status.APPROVED
    draft.approved_at = timezone.now()
    draft.rejected_at = None
    draft.save(update_fields=["status", "approved_at", "rejected_at", "updated_at"])
    _log(draft, actor, ReviewAction.Action.APPROVE, notes=notes)
    return ReviewResult(
        draft=draft,
        detail="Approved locally. Nothing was posted to Reddit.",
    )


@transaction.atomic
def reject_draft(draft: DraftResponse, actor, *, notes: str = "") -> ReviewResult:
    _ensure_status(draft, REJECTABLE_STATUSES, "reject")
    draft.status = DraftResponse.Status.REJECTED
    draft.rejected_at = timezone.now()
    draft.save(update_fields=["status", "rejected_at", "updated_at"])
    _log(draft, actor, ReviewAction.Action.REJECT, notes=notes)
    return ReviewResult(draft=draft, detail="Rejected.")


@transaction.atomic
def save_for_later(draft: DraftResponse, actor, *, notes: str = "") -> ReviewResult:
    _ensure_status(draft, SAVE_LATER_STATUSES, "save for later")
    draft.status = DraftResponse.Status.SAVED_FOR_LATER
    draft.save(update_fields=["status", "updated_at"])
    _log(draft, actor, ReviewAction.Action.SAVE_FOR_LATER, notes=notes)
    return ReviewResult(draft=draft, detail="Saved for later.")


@transaction.atomic
def reopen_draft(draft: DraftResponse, actor, *, notes: str = "") -> ReviewResult:
    _ensure_status(draft, REOPEN_STATUSES, "return to queue")
    draft.status = DraftResponse.Status.IN_REVIEW
    draft.save(update_fields=["status", "updated_at"])
    _log(draft, actor, ReviewAction.Action.REOPEN, notes=notes)
    return ReviewResult(draft=draft, detail="Returned to review queue.")


@transaction.atomic
def mark_published(draft: DraftResponse, actor, *, notes: str = "") -> ReviewResult:
    """Record that the operator manually published. Never calls Reddit."""
    _ensure_status(draft, PUBLISHABLE_STATUSES, "mark published")
    if draft.status != DraftResponse.Status.APPROVED:
        draft.approved_at = draft.approved_at or timezone.now()
    draft.status = DraftResponse.Status.PUBLISHED
    draft.published_at = timezone.now()
    draft.save(
        update_fields=["status", "approved_at", "published_at", "updated_at"]
    )
    _log(draft, actor, ReviewAction.Action.MARK_PUBLISHED, notes=notes)
    return ReviewResult(
        draft=draft,
        detail=(
            "Marked as published locally. Nothing was auto-submitted to Reddit "
            "— this only records that you posted manually."
        ),
    )


@transaction.atomic
def update_private_notes(
    draft: DraftResponse,
    actor,
    *,
    private_notes: str,
) -> ReviewResult:
    if draft.status == DraftResponse.Status.DISCARDED:
        raise ReviewStateError("Cannot note a discarded draft.")
    draft.private_notes = private_notes
    draft.save(update_fields=["private_notes", "updated_at"])
    _log(draft, actor, ReviewAction.Action.NOTE, notes=private_notes)
    return ReviewResult(draft=draft, detail="Private notes saved.")


def regenerate_draft(draft: DraftResponse, actor, *, notes: str = "") -> ReviewResult:
    _ensure_status(draft, REGENERATABLE_STATUSES, "regenerate")
    _log(draft, actor, ReviewAction.Action.REGENERATE, notes=notes)
    # Discard current queueable drafts before enqueue (generate_draft also does this).
    DraftResponse.objects.filter(
        post_id=draft.post_id,
        status__in=DISCARD_ON_REGENERATE,
    ).update(status=DraftResponse.Status.DISCARDED)
    async_result = generate_draft_response.delay(str(draft.post_id), force=True)
    result = None
    try:
        if async_result.successful():
            result = async_result.result
    except Exception:  # noqa: BLE001
        result = None
    return ReviewResult(
        draft=draft,
        detail="Regenerate enqueued. Previous in-review drafts discarded.",
        extra={"task_id": async_result.id, "result": result},
    )


def reddit_submit_enabled() -> bool:
    return bool(getattr(settings, "REDDIT_SUBMIT_ENABLED", False))


def export_payload(draft: DraftResponse) -> dict[str, Any]:
    return {
        "text": draft.effective_body,
        "permalink": absolute_reddit_url(draft),
        "reddit_fullname": draft.post.reddit_fullname,
        "never_auto_publish": True,
        "reddit_submit_enabled": reddit_submit_enabled(),
        "detail": "Copy locally. Nothing was posted to Reddit.",
    }
