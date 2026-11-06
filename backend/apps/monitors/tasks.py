"""Celery tasks for polling monitors against Reddit search + Beat dispatch."""

from __future__ import annotations

import logging
from datetime import timedelta

from celery import shared_task
from celery.exceptions import Retry
from django.conf import settings
from django.utils import timezone

from apps.reddit.client import RedditRateLimitError
from apps.reddit.models import RedditAccount
from apps.reddit.rate_limit import (
    acquire_account_lock,
    check_token_bucket,
    release_account_lock,
)
from apps.reddit.services import (
    build_search_query,
    client_for_account,
    ensure_fixture_account,
    upsert_post,
)

from .backoff import countdown_from_retry_after, retry_countdown
from .models import Monitor, TaskRun
from .task_tracking import begin_task_run, finish_task_run, mark_task_retry

logger = logging.getLogger(__name__)


def _enqueue_auto_chain(monitor: Monitor, post_ids: list[str]) -> list[str]:
    """Discover → analyze (optional) → draft if relevant. Never publish."""
    if not post_ids:
        return []
    if not getattr(monitor, "auto_analyze", True):
        return []
    if not getattr(settings, "MONITOR_AUTO_ANALYZE", True):
        return []

    from apps.analysis.tasks import analyze_post_relevance

    auto_draft = bool(
        monitor.auto_draft and getattr(settings, "MONITOR_AUTO_DRAFT", True)
    )
    enqueued: list[str] = []
    for post_id in post_ids:
        async_result = analyze_post_relevance.delay(
            post_id,
            force=False,
            auto_draft=auto_draft,
        )
        enqueued.append(async_result.id)
    return enqueued


@shared_task(
    bind=True,
    name="monitors.dispatch_due_monitors",
    soft_time_limit=60,
    time_limit=90,
)
def dispatch_due_monitors(self) -> dict:
    """Beat entry: enqueue poll_monitor for active monitors past their interval."""
    now = timezone.now()
    due_ids: list[str] = []
    skipped_expired = 0

    active = (
        Monitor.objects.filter(is_active=True)
        .select_related("user")
        .prefetch_related("keywords")
    )
    for monitor in active:
        if not monitor.keywords.exists():
            continue
        if monitor.last_polled_at is not None:
            due_at = monitor.last_polled_at + timedelta(
                minutes=monitor.poll_interval_minutes
            )
            if due_at > now:
                continue

        account = RedditAccount.objects.filter(user=monitor.user).first()
        if account is None and settings.REDDIT_MODE == "fixture":
            account = ensure_fixture_account(monitor.user)
        if account is not None and account.status == RedditAccount.Status.EXPIRED:
            skipped_expired += 1
            monitor.record_error(
                "Reddit token expired — polls paused until reconnect/refresh."
            )
            continue
        if account is not None and account.status == RedditAccount.Status.REVOKED:
            skipped_expired += 1
            continue

        async_result = poll_monitor.delay(str(monitor.pk))
        due_ids.append(async_result.id)

    return {
        "ok": True,
        "enqueued": len(due_ids),
        "task_ids": due_ids,
        "skipped_expired": skipped_expired,
        "never_auto_publish": True,
    }


@shared_task(
    bind=True,
    name="monitors.poll_monitor",
    max_retries=5,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def poll_monitor(self, monitor_id: str) -> dict:
    """Search Reddit for monitor keywords/subreddits; upsert RedditPost rows."""
    try:
        monitor = Monitor.objects.prefetch_related("keywords", "subreddits").get(
            pk=monitor_id
        )
    except Monitor.DoesNotExist:
        return {"ok": False, "error": "monitor_not_found", "never_auto_publish": True}

    run = begin_task_run(
        task_name="monitors.poll_monitor",
        celery_task_id=getattr(self.request, "id", "") or "",
        user=monitor.user,
        monitor=monitor,
        retries=int(getattr(self.request, "retries", 0) or 0),
    )

    if not monitor.is_active:
        finish_task_run(
            run,
            status=TaskRun.Status.SKIPPED,
            message="monitor_inactive",
            result={"ok": False, "error": "monitor_inactive"},
        )
        return {"ok": False, "error": "monitor_inactive", "never_auto_publish": True}

    account = RedditAccount.objects.filter(user=monitor.user).first()
    if account is None:
        if settings.REDDIT_MODE == "fixture":
            account = ensure_fixture_account(monitor.user)
        else:
            finish_task_run(
                run,
                status=TaskRun.Status.FAILURE,
                message="reddit_not_connected",
                result={"ok": False, "error": "reddit_not_connected"},
            )
            monitor.record_error("Reddit not connected.")
            return {
                "ok": False,
                "error": "reddit_not_connected",
                "never_auto_publish": True,
            }

    if account.status == RedditAccount.Status.EXPIRED:
        finish_task_run(
            run,
            status=TaskRun.Status.SKIPPED,
            message="reddit_token_expired",
            result={"ok": False, "error": "reddit_token_expired"},
        )
        return {
            "ok": False,
            "error": "reddit_token_expired",
            "never_auto_publish": True,
        }
    if account.status == RedditAccount.Status.REVOKED:
        finish_task_run(
            run,
            status=TaskRun.Status.SKIPPED,
            message="reddit_revoked",
            result={"ok": False, "error": "reddit_revoked"},
        )
        return {"ok": False, "error": "reddit_revoked", "never_auto_publish": True}

    account_key = str(account.pk)
    lock_held = False
    try:
        if not acquire_account_lock(account_key):
            mark_task_retry(
                run, message="account_lock_busy", retries=self.request.retries
            )
            raise self.retry(
                countdown=retry_countdown(
                    self.request.retries, steps=(15, 30, 60, 120, 120)
                )
            )
        lock_held = True

        bucket = check_token_bucket(account_key)
        if not bucket.allowed:
            mark_task_retry(run, message="token_bucket", retries=self.request.retries)
            raise self.retry(
                countdown=countdown_from_retry_after(
                    bucket.wait_seconds,
                    retries=self.request.retries,
                )
            )

        client = client_for_account(account)
        subreddit_names = [s.name for s in monitor.subreddits.all()]
        targets: list[str | None] = subreddit_names or [None]
        keywords = list(monitor.keywords.all())
        if not keywords:
            finish_task_run(
                run,
                status=TaskRun.Status.FAILURE,
                message="no_keywords",
                result={"ok": False, "error": "no_keywords"},
            )
            return {
                "ok": False,
                "error": "no_keywords",
                "created": 0,
                "updated": 0,
                "never_auto_publish": True,
            }

        created = 0
        updated = 0
        searched = 0
        new_post_ids: list[str] = []

        for keyword in keywords:
            query = build_search_query(keyword.phrase, keyword.match_mode)
            for sub in targets:
                try:
                    results = client.search(
                        query,
                        subreddit=sub,
                        limit=25,
                        include_nsfw=monitor.include_nsfw,
                    )
                except RedditRateLimitError as exc:
                    mark_task_retry(
                        run, message="reddit_429", retries=self.request.retries
                    )
                    raise self.retry(
                        countdown=countdown_from_retry_after(
                            exc.wait_seconds,
                            retries=self.request.retries,
                        )
                    ) from exc
                except Exception as exc:  # noqa: BLE001 — network / 5xx
                    mark_task_retry(
                        run, message=str(exc), retries=self.request.retries
                    )
                    raise self.retry(
                        exc=exc,
                        countdown=retry_countdown(self.request.retries),
                    ) from exc

                searched += 1
                for result in results:
                    if monitor.min_score is not None and result.score < monitor.min_score:
                        continue
                    if (
                        monitor.min_comments is not None
                        and result.num_comments < monitor.min_comments
                    ):
                        continue
                    post, was_created = upsert_post(
                        user=monitor.user,
                        result=result,
                        monitor=monitor,
                    )
                    if was_created:
                        created += 1
                        new_post_ids.append(str(post.pk))
                    else:
                        updated += 1

        monitor.last_polled_at = timezone.now()
        monitor.last_error = ""
        monitor.last_error_at = None
        monitor.save(
            update_fields=[
                "last_polled_at",
                "last_error",
                "last_error_at",
                "updated_at",
            ]
        )

        analyze_task_ids = _enqueue_auto_chain(monitor, new_post_ids)
        payload = {
            "ok": True,
            "monitor_id": str(monitor.pk),
            "searches": searched,
            "created": created,
            "updated": updated,
            "analyze_enqueued": len(analyze_task_ids),
            "analyze_task_ids": analyze_task_ids,
            "never_auto_publish": True,
        }
        finish_task_run(run, status=TaskRun.Status.SUCCESS, message="ok", result=payload)
        return payload
    except Retry:
        raise
    except Exception as exc:
        monitor.record_error(str(exc))
        finish_task_run(
            run,
            status=TaskRun.Status.FAILURE,
            message=str(exc),
            result={"ok": False, "error": str(exc)},
        )
        raise
    finally:
        if lock_held:
            release_account_lock(account_key)


@shared_task(name="monitors.find_due_monitor_ids")
def find_due_monitor_ids() -> list[str]:
    """Test/helper: return PKs of monitors that are due (no enqueue)."""
    now = timezone.now()
    due: list[str] = []
    for monitor in Monitor.objects.filter(is_active=True):
        if monitor.last_polled_at is None:
            due.append(str(monitor.pk))
            continue
        due_at = monitor.last_polled_at + timedelta(
            minutes=monitor.poll_interval_minutes
        )
        if due_at <= now:
            due.append(str(monitor.pk))
    return due
