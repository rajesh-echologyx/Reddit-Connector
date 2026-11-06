"""Reddit Celery tasks — proactive OAuth refresh (Phase 5)."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import Retry
from django.utils import timezone

from apps.monitors.backoff import countdown_from_retry_after, retry_countdown
from apps.monitors.models import TaskRun
from apps.monitors.task_tracking import begin_task_run, finish_task_run, mark_task_retry

from .client import RedditRateLimitError
from .models import RedditAccount
from .services import refresh_account_tokens

logger = logging.getLogger(__name__)

# Refresh tokens within this window of expiry (plan: 30 minutes).
EXPIRY_WINDOW = timedelta(minutes=30)


@shared_task(
    bind=True,
    name="reddit.refresh_expiring_tokens",
    max_retries=5,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def refresh_expiring_tokens(self) -> dict:
    """Refresh OAuth tokens within 30 min of expiry; expire account on failure."""
    run = begin_task_run(
        task_name="reddit.refresh_expiring_tokens",
        celery_task_id=getattr(self.request, "id", "") or "",
        retries=int(getattr(self.request, "retries", 0) or 0),
    )

    now = timezone.now()
    cutoff = now + EXPIRY_WINDOW
    # Connected accounts with missing expiry or expiry within the window.
    candidates = RedditAccount.objects.filter(status=RedditAccount.Status.CONNECTED)
    due = [
        account
        for account in candidates
        if account.token_expires_at is None or account.token_expires_at <= cutoff
    ]

    refreshed = 0
    expired = 0
    skipped = 0
    errors: list[str] = []

    try:
        for account in due:
            try:
                result = refresh_account_tokens(account)
            except RedditRateLimitError as exc:
                mark_task_retry(
                    run, message="reddit_429", retries=self.request.retries
                )
                raise self.retry(
                    countdown=countdown_from_retry_after(
                        exc.wait_seconds, retries=self.request.retries
                    )
                ) from exc
            except Exception as exc:  # noqa: BLE001
                mark_task_retry(run, message=str(exc), retries=self.request.retries)
                raise self.retry(
                    exc=exc, countdown=retry_countdown(self.request.retries)
                ) from exc

            if result.get("skipped"):
                skipped += 1
            elif result.get("ok"):
                refreshed += 1
            elif result.get("expired"):
                expired += 1
                errors.append(str(result.get("error") or "expired"))
            else:
                errors.append(str(result.get("error") or "unknown"))

        payload = {
            "ok": True,
            "checked": len(due),
            "refreshed": refreshed,
            "expired": expired,
            "skipped": skipped,
            "errors": errors[:20],
            "never_auto_publish": True,
        }
        finish_task_run(run, status=TaskRun.Status.SUCCESS, message="ok", result=payload)
        return payload
    except Retry:
        raise
    except Exception as exc:
        finish_task_run(
            run,
            status=TaskRun.Status.FAILURE,
            message=str(exc),
            result={"ok": False, "error": str(exc), "never_auto_publish": True},
        )
        raise
