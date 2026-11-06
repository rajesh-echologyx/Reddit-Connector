"""Celery tasks for AI relevance + draft generation."""

from __future__ import annotations

from celery import shared_task

from .services import analyze_post, generate_draft


@shared_task(
    bind=True,
    name="analysis.analyze_post_relevance",
    soft_time_limit=120,
    time_limit=180,
    max_retries=5,
)
def analyze_post_relevance(self, post_id: str, force: bool = False) -> dict:
    """OpenAI relevance JSON → RelevanceAnalysis. Never publishes."""
    return analyze_post(post_id, force=force)


@shared_task(
    bind=True,
    name="analysis.generate_draft_response",
    soft_time_limit=180,
    time_limit=240,
    max_retries=5,
)
def generate_draft_response(self, post_id: str, force: bool = False) -> dict:
    """OpenAI draft → DraftResponse status in_review. Never publishes."""
    return generate_draft(post_id, force=force)
