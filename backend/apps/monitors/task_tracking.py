"""Helpers to record Celery task runs for the monitoring API/UI."""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from .models import TaskRun


def begin_task_run(
    *,
    task_name: str,
    celery_task_id: str = "",
    user=None,
    monitor=None,
    post_id=None,
    retries: int = 0,
) -> TaskRun:
    return TaskRun.objects.create(
        user=user,
        task_name=task_name,
        celery_task_id=celery_task_id or "",
        status=TaskRun.Status.STARTED,
        monitor=monitor,
        post_id=post_id,
        retries=retries,
        started_at=timezone.now(),
        result={"never_auto_publish": True},
    )


def finish_task_run(
    run: TaskRun | None,
    *,
    status: str,
    message: str = "",
    result: dict[str, Any] | None = None,
) -> TaskRun | None:
    if run is None:
        return None
    payload = dict(run.result or {})
    if result:
        payload.update(result)
    payload.setdefault("never_auto_publish", True)
    run.status = status
    run.message = (message or "")[:2000]
    run.result = payload
    run.finished_at = timezone.now()
    run.save(
        update_fields=[
            "status",
            "message",
            "result",
            "finished_at",
            "updated_at",
            "retries",
        ]
    )
    return run


def mark_task_retry(run: TaskRun | None, *, message: str = "", retries: int = 0) -> None:
    if run is None:
        return
    run.status = TaskRun.Status.RETRY
    run.message = (message or "")[:2000]
    run.retries = retries
    run.save(update_fields=["status", "message", "retries", "updated_at"])
