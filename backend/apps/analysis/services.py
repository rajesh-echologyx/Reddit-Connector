"""Relevance analysis + draft generation business logic."""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.profiles.models import WritingSample
from apps.profiles.services import get_or_create_profile
from apps.reddit.models import RedditPost

from .models import DraftResponse, RelevanceAnalysis
from .openai_client import OpenAIClientError, get_openai_client, schema_for
from .prompts import PROMPT_VERSION, load_prompt
from .schemas import SchemaValidationError, validate_draft_payload, validate_relevance_payload

logger = logging.getLogger(__name__)

SELFTEXT_TRUNCATE = 4000
TITLE_TRUNCATE = 500


def _truncate(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def resolve_relevance_model(user) -> str:
    profile = get_or_create_profile(user)
    if profile.openai_relevance_model.strip():
        return profile.openai_relevance_model.strip()
    return getattr(settings, "OPENAI_RELEVANCE_MODEL", "gpt-4o-mini")


def resolve_draft_model(user) -> str:
    profile = get_or_create_profile(user)
    if profile.openai_draft_model.strip():
        return profile.openai_draft_model.strip()
    return getattr(settings, "OPENAI_DRAFT_MODEL", "gpt-4o-mini")


def build_relevance_user_prompt(post: RedditPost) -> str:
    profile = get_or_create_profile(post.user)
    topics = profile.expertise_topics or []
    topics_line = ", ".join(topics) if topics else "(none listed)"
    threshold = settings.RELEVANCE_THRESHOLD
    return (
        f"Subreddit: r/{post.subreddit}\n"
        f"Title: {_truncate(post.title, TITLE_TRUNCATE)}\n"
        f"Body:\n{_truncate(post.selftext, SELFTEXT_TRUNCATE)}\n\n"
        f"Expertise topics: {topics_line}\n"
        f"Hard constraints: {profile.hard_constraints or '(none)'}\n"
        f"Threshold: score >= {threshold} should generally set is_relevant true "
        f"when expertise matches; below that, prefer is_relevant false.\n"
    )


def build_draft_user_prompt(post: RedditPost, analysis: RelevanceAnalysis) -> str:
    profile = get_or_create_profile(post.user)
    samples = list(
        WritingSample.objects.filter(user=post.user, is_active=True).order_by("-updated_at")[
            : settings.MAX_ACTIVE_WRITING_SAMPLES
        ]
    )
    sample_blocks = []
    for i, sample in enumerate(samples, start=1):
        sample_blocks.append(
            f"--- Sample {i}: {sample.title} ---\n{_truncate(sample.body, 1500)}"
        )
    samples_text = "\n\n".join(sample_blocks) if sample_blocks else "(no active samples)"

    return (
        f"Subreddit: r/{post.subreddit}\n"
        f"Title: {_truncate(post.title, TITLE_TRUNCATE)}\n"
        f"Body:\n{_truncate(post.selftext, SELFTEXT_TRUNCATE)}\n\n"
        f"Relevance score: {analysis.relevance_score}\n"
        f"Relevance reasons: {analysis.reasons}\n"
        f"Matched expertise: {analysis.matched_expertise}\n"
        f"Risk flags: {analysis.risk_flags}\n\n"
        f"Operator display name: {profile.display_name or '(none)'}\n"
        f"Bio: {profile.bio_short or '(none)'}\n"
        f"Expertise topics: {profile.expertise_topics or []}\n"
        f"Tone notes: {profile.tone_notes or '(none)'}\n"
        f"Hard constraints: {profile.hard_constraints or '(none)'}\n\n"
        f"Writing samples (style only):\n{samples_text}\n\n"
        "Remember: never invent personal experience. If the post asks for personal "
        "experience you do not have in the profile/samples, stay general and flag it.\n"
    )


@transaction.atomic
def analyze_post(post_id: str, *, force: bool = False) -> dict[str, Any]:
    """Run relevance analysis; persist RelevanceAnalysis; update post status."""
    try:
        post = RedditPost.objects.select_for_update().get(pk=post_id)
    except RedditPost.DoesNotExist:
        return {"ok": False, "error": "post_not_found"}

    existing = RelevanceAnalysis.objects.filter(post=post).first()
    if existing and existing.status == RelevanceAnalysis.Status.COMPLETE and not force:
        return {
            "ok": True,
            "skipped": True,
            "analysis_id": str(existing.pk),
            "is_relevant": existing.is_relevant,
            "relevance_score": existing.relevance_score,
        }

    post.status = RedditPost.Status.ANALYZING
    post.save(update_fields=["status", "updated_at"])

    analysis = existing or RelevanceAnalysis(post=post)
    analysis.status = RelevanceAnalysis.Status.PENDING
    analysis.error_message = ""
    analysis.save()

    model = resolve_relevance_model(post.user)
    client = get_openai_client()
    system = load_prompt("relevance_system.txt")
    user_prompt = build_relevance_user_prompt(post)

    try:
        raw = client.complete_json(
            model=model,
            system=system,
            user=user_prompt,
            schema=schema_for("relevance"),
            schema_name="relevance",
        )
        parsed = validate_relevance_payload(raw)
    except (OpenAIClientError, SchemaValidationError, OSError) as exc:
        analysis.status = RelevanceAnalysis.Status.FAILED
        analysis.error_message = str(exc)[:2000]
        analysis.model = model
        analysis.prompt_version = PROMPT_VERSION
        analysis.raw_response = {"error": str(exc)}
        analysis.save()
        post.status = RedditPost.Status.ERROR
        post.save(update_fields=["status", "updated_at"])
        return {"ok": False, "error": str(exc), "analysis_id": str(analysis.pk)}

    threshold = settings.RELEVANCE_THRESHOLD
    # Persist model boolean, but also enforce threshold boundary for is_relevant
    # used by draft gating when model is inconsistent with score.
    score = parsed["relevance_score"]
    is_relevant = bool(parsed["is_relevant"]) and score >= threshold
    # If model said not relevant but score is clearly high, trust score.
    if score >= threshold and not parsed["is_relevant"]:
        is_relevant = True
    if score < threshold:
        is_relevant = False

    analysis.relevance_score = score
    analysis.is_relevant = is_relevant
    analysis.reasons = parsed["reasons"]
    analysis.matched_expertise = parsed["matched_expertise"]
    analysis.risk_flags = parsed["risk_flags"]
    analysis.summary = parsed["summary"]
    analysis.model = model
    analysis.prompt_version = PROMPT_VERSION
    analysis.raw_response = raw
    analysis.status = RelevanceAnalysis.Status.COMPLETE
    analysis.error_message = ""
    analysis.save()

    post.status = RedditPost.Status.SCORED if is_relevant else RedditPost.Status.SKIPPED
    post.save(update_fields=["status", "updated_at"])

    return {
        "ok": True,
        "analysis_id": str(analysis.pk),
        "is_relevant": is_relevant,
        "relevance_score": score,
        "post_status": post.status,
        "never_auto_publish": True,
    }


@transaction.atomic
def generate_draft(post_id: str, *, force: bool = False) -> dict[str, Any]:
    """Generate a draft reply for a relevant post; status lands at in_review."""
    try:
        post = RedditPost.objects.select_for_update().get(pk=post_id)
    except RedditPost.DoesNotExist:
        return {"ok": False, "error": "post_not_found"}

    analysis = RelevanceAnalysis.objects.filter(post=post).first()
    if analysis is None or analysis.status != RelevanceAnalysis.Status.COMPLETE:
        return {"ok": False, "error": "analysis_required"}
    if not analysis.is_relevant:
        return {"ok": False, "error": "post_not_relevant"}

    active = DraftResponse.objects.filter(
        post=post,
        status__in=[
            DraftResponse.Status.DRAFT,
            DraftResponse.Status.IN_REVIEW,
            DraftResponse.Status.APPROVED,
        ],
    ).first()
    if active and not force:
        return {
            "ok": True,
            "skipped": True,
            "draft_id": str(active.pk),
            "status": active.status,
        }

    if force:
        DraftResponse.objects.filter(
            post=post,
            status__in=[
                DraftResponse.Status.DRAFT,
                DraftResponse.Status.IN_REVIEW,
                DraftResponse.Status.SAVED_FOR_LATER,
            ],
        ).update(status=DraftResponse.Status.DISCARDED)

    model = resolve_draft_model(post.user)
    client = get_openai_client()
    system = load_prompt("draft_system.txt")
    user_prompt = build_draft_user_prompt(post, analysis)

    draft = DraftResponse(
        post=post,
        analysis=analysis,
        status=DraftResponse.Status.DRAFT,
        model=model,
        prompt_version=PROMPT_VERSION,
    )
    draft.save()

    try:
        raw = client.complete_json(
            model=model,
            system=system,
            user=user_prompt,
            schema=schema_for("draft"),
            schema_name="draft",
        )
        parsed = validate_draft_payload(raw)
    except (OpenAIClientError, SchemaValidationError, OSError) as exc:
        draft.error_message = str(exc)[:2000]
        draft.raw_response = {"error": str(exc)}
        draft.status = DraftResponse.Status.DISCARDED
        draft.save()
        return {"ok": False, "error": str(exc), "draft_id": str(draft.pk)}

    draft.body = parsed["draft"]
    draft.tone = parsed["tone"]
    draft.claims_made = parsed["claims_made"]
    draft.needs_human_check = parsed["needs_human_check"]
    draft.raw_response = raw
    draft.status = DraftResponse.Status.IN_REVIEW
    draft.generated_at = timezone.now()
    draft.error_message = ""
    draft.save()

    return {
        "ok": True,
        "draft_id": str(draft.pk),
        "status": draft.status,
        "never_auto_publish": True,
    }
