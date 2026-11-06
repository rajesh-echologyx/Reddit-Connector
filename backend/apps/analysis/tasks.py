"""Celery tasks for AI relevance + draft generation."""

from __future__ import annotations

import logging
import re

from celery import shared_task
from celery.exceptions import Retry
from django.conf import settings

from apps.monitors.backoff import countdown_from_retry_after, retry_countdown
from apps.monitors.models import TaskRun
from apps.monitors.task_tracking import begin_task_run, finish_task_run, mark_task_retry
from apps.reddit.models import RedditPost

from .openai_client import OpenAIClientError
from .services import analyze_post, generate_draft

logger = logging.getLogger(__name__)

_RETRYABLE_RE = re.compile(
    r"(429|rate[_ ]?limit|timeout|temporar|unavailable|502|503|504|overloaded)",
    re.I,
)


def _is_retryable_openai_error(exc: BaseException) -> bool:
    if not isinstance(exc, OpenAIClientError):
        # OSError / connection issues — retry
        return isinstance(exc, OSError)
    text = str(exc)
    return bool(_RETRYABLE_RE.search(text))


def _extract_reset_seconds(exc: BaseException) -> float | None:
    text = str(exc)
    match = re.search(r"rate_limit_reset[=:\s]+(\d+(?:\.\d+)?)", text, re.I)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    match = re.search(r"retry[-_ ]after[=:\s]+(\d+(?:\.\d+)?)", text, re.I)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _maybe_enqueue_draft(post_id: str, analysis_result: dict, *, auto_draft: bool) -> str | None:
    """If relevant and auto_draft, enqueue draft. Never approve/publish."""
    if not auto_draft:
        return None
    if not analysis_result.get("ok"):
        return None
    if analysis_result.get("skipped") and not analysis_result.get("is_relevant"):
        return None
    if not analysis_result.get("is_relevant"):
        return None
    if not getattr(settings, "MONITOR_AUTO_DRAFT", True):
        return None
    async_result = generate_draft_response.delay(post_id, force=False)
    return async_result.id


@shared_task(
    bind=True,
    name="analysis.analyze_post_relevance",
    soft_time_limit=120,
    time_limit=180,
    max_retries=5,
    acks_late=True,
)
def analyze_post_relevance(
    self,
    post_id: str,
    force: bool = False,
    auto_draft: bool = False,
) -> dict:
    """OpenAI relevance JSON → RelevanceAnalysis. Never publishes."""
    user = None
    try:
        post = RedditPost.objects.select_related("user").get(pk=post_id)
        user = post.user
    except RedditPost.DoesNotExist:
        return {"ok": False, "error": "post_not_found", "never_auto_publish": True}

    run = begin_task_run(
        task_name="analysis.analyze_post_relevance",
        celery_task_id=getattr(self.request, "id", "") or "",
        user=user,
        post_id=post.pk,
        monitor=post.discovered_via_monitor,
        retries=int(getattr(self.request, "retries", 0) or 0),
    )

    try:
        result = analyze_post(post_id, force=force)
        if not result.get("ok") and _is_retryable_openai_error(
            OpenAIClientError(result.get("error") or "openai_error")
        ):
            # analyze_post already marked failed — for retryable, re-raise via retry
            # after clearing is handled by force on next attempt.
            mark_task_retry(
                run,
                message=str(result.get("error") or "retryable"),
                retries=self.request.retries,
            )
            raise self.retry(
                countdown=countdown_from_retry_after(
                    _extract_reset_seconds(OpenAIClientError(str(result.get("error")))),
                    retries=self.request.retries,
                )
            )

        draft_task_id = None
        if result.get("ok"):
            draft_task_id = _maybe_enqueue_draft(
                post_id, result, auto_draft=auto_draft
            )
        if draft_task_id:
            result = {**result, "draft_task_id": draft_task_id, "auto_draft": True}
        result.setdefault("never_auto_publish", True)

        status = (
            TaskRun.Status.SUCCESS
            if result.get("ok")
            else TaskRun.Status.FAILURE
        )
        if result.get("skipped"):
            status = TaskRun.Status.SKIPPED
        finish_task_run(
            run,
            status=status,
            message="ok" if result.get("ok") else str(result.get("error") or ""),
            result=result,
        )
        return result
    except Retry:
        raise
    except OpenAIClientError as exc:
        if _is_retryable_openai_error(exc):
            mark_task_retry(run, message=str(exc), retries=self.request.retries)
            raise self.retry(
                exc=exc,
                countdown=countdown_from_retry_after(
                    _extract_reset_seconds(exc),
                    retries=self.request.retries,
                ),
            ) from exc
        finish_task_run(
            run,
            status=TaskRun.Status.FAILURE,
            message=str(exc),
            result={"ok": False, "error": str(exc), "never_auto_publish": True},
        )
        return {"ok": False, "error": str(exc), "never_auto_publish": True}
    except Exception as exc:
        finish_task_run(
            run,
            status=TaskRun.Status.FAILURE,
            message=str(exc),
            result={"ok": False, "error": str(exc), "never_auto_publish": True},
        )
        raise


@shared_task(
    bind=True,
    name="analysis.generate_draft_response",
    soft_time_limit=180,
    time_limit=240,
    max_retries=5,
    acks_late=True,
)
def generate_draft_response(self, post_id: str, force: bool = False) -> dict:
    """OpenAI draft → DraftResponse status in_review. Never publishes."""
    user = None
    try:
        post = RedditPost.objects.select_related("user").get(pk=post_id)
        user = post.user
    except RedditPost.DoesNotExist:
        return {"ok": False, "error": "post_not_found", "never_auto_publish": True}

    run = begin_task_run(
        task_name="analysis.generate_draft_response",
        celery_task_id=getattr(self.request, "id", "") or "",
        user=user,
        post_id=post.pk,
        monitor=post.discovered_via_monitor,
        retries=int(getattr(self.request, "retries", 0) or 0),
    )

    try:
        result = generate_draft(post_id, force=force)
        result.setdefault("never_auto_publish", True)
        # Hard invariant — drafts land in review; never auto-approve/publish.
        result["never_auto_publish"] = True
        result["auto_published"] = False

        if not result.get("ok") and _is_retryable_openai_error(
            OpenAIClientError(result.get("error") or "openai_error")
        ):
            mark_task_retry(
                run,
                message=str(result.get("error") or "retryable"),
                retries=self.request.retries,
            )
            raise self.retry(
                countdown=countdown_from_retry_after(
                    _extract_reset_seconds(OpenAIClientError(str(result.get("error")))),
                    retries=self.request.retries,
                )
            )

        status = (
            TaskRun.Status.SUCCESS
            if result.get("ok")
            else TaskRun.Status.FAILURE
        )
        if result.get("skipped"):
            status = TaskRun.Status.SKIPPED
        finish_task_run(
            run,
            status=status,
            message="ok" if result.get("ok") else str(result.get("error") or ""),
            result=result,
        )
        return result
    except Retry:
        raise
    except OpenAIClientError as exc:
        if _is_retryable_openai_error(exc):
            mark_task_retry(run, message=str(exc), retries=self.request.retries)
            raise self.retry(
                exc=exc,
                countdown=countdown_from_retry_after(
                    _extract_reset_seconds(exc),
                    retries=self.request.retries,
                ),
            ) from exc
        finish_task_run(
            run,
            status=TaskRun.Status.FAILURE,
            message=str(exc),
            result={"ok": False, "error": str(exc), "never_auto_publish": True},
        )
        return {"ok": False, "error": str(exc), "never_auto_publish": True}
    except Exception as exc:
        finish_task_run(
            run,
            status=TaskRun.Status.FAILURE,
            message=str(exc),
            result={"ok": False, "error": str(exc), "never_auto_publish": True},
        )
        raise
