"""AI relevance + draft generation with mock OpenAI fixtures."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from apps.analysis.models import DraftResponse, RelevanceAnalysis
from apps.analysis.schemas import SchemaValidationError, validate_draft_payload, validate_relevance_payload
from apps.analysis.services import analyze_post, generate_draft
from apps.analysis.tasks import analyze_post_relevance, generate_draft_response
from apps.profiles.models import UserProfile, WritingSample
from apps.reddit.models import RedditPost

User = get_user_model()


@pytest.fixture
def user(db):
    u = User.objects.create_user(
        username="owner",
        password="Str0ngPass!word",
        is_personal_owner=True,
    )
    UserProfile.objects.create(
        user=u,
        display_name="Operator",
        expertise_topics=["django", "celery", "python"],
        tone_notes="helpful and concise",
        hard_constraints="Never invent experience, employers, or metrics.",
    )
    WritingSample.objects.create(
        user=u,
        title="API style",
        body="Prefer clear boundaries and structured errors with stable codes.",
        is_active=True,
    )
    return u


@pytest.fixture
def auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _make_post(user, *, title: str, selftext: str = "", subreddit: str = "python") -> RedditPost:
    name = f"t3_{abs(hash(title)) % 10_000_000}"
    return RedditPost.objects.create(
        user=user,
        reddit_fullname=name,
        reddit_id=name.removeprefix("t3_"),
        subreddit=subreddit,
        title=title,
        selftext=selftext,
        author="op",
        url=f"https://www.reddit.com/r/{subreddit}/comments/x/",
        permalink=f"/r/{subreddit}/comments/x/",
        score=10,
        num_comments=2,
        status=RedditPost.Status.NEW,
    )


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_relevance_schema_valid() -> None:
    parsed = validate_relevance_payload(
        {
            "relevance_score": 80,
            "is_relevant": True,
            "reasons": ["matches django"],
            "matched_expertise": ["django"],
            "risk_flags": ["uncertain"],
            "summary": "good fit",
        }
    )
    assert parsed["relevance_score"] == 80


def test_relevance_schema_rejects_out_of_range() -> None:
    with pytest.raises(SchemaValidationError):
        validate_relevance_payload(
            {
                "relevance_score": 150,
                "is_relevant": True,
                "reasons": [],
                "matched_expertise": [],
            }
        )


def test_draft_schema_requires_body() -> None:
    with pytest.raises(SchemaValidationError):
        validate_draft_payload({"draft": "  ", "tone": "x", "claims_made": [], "needs_human_check": []})


# ---------------------------------------------------------------------------
# Services / tasks (mock OpenAI)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", RELEVANCE_THRESHOLD=70, CELERY_TASK_ALWAYS_EAGER=True)
def test_analyze_relevant_then_draft(user) -> None:
    post = _make_post(
        user,
        title="How do I structure Django + Celery workers?",
        selftext="Looking for advice on polling Reddit with Celery beat.",
    )
    result = analyze_post(str(post.pk))
    assert result["ok"] is True
    assert result["is_relevant"] is True
    assert result["relevance_score"] >= 70

    post.refresh_from_db()
    assert post.status == RedditPost.Status.SCORED
    analysis = RelevanceAnalysis.objects.get(post=post)
    assert analysis.status == RelevanceAnalysis.Status.COMPLETE
    assert analysis.prompt_version == "v1"

    draft_result = generate_draft(str(post.pk))
    assert draft_result["ok"] is True
    assert draft_result["status"] == DraftResponse.Status.IN_REVIEW
    draft = DraftResponse.objects.get(pk=draft_result["draft_id"])
    assert draft.body
    assert "invent" not in draft.body.lower() or "never" in draft.body.lower()
    assert draft.status == DraftResponse.Status.IN_REVIEW


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", RELEVANCE_THRESHOLD=70)
def test_irrelevant_skips_draft(user) -> None:
    post = _make_post(
        user,
        title="Best sourdough starter hydration?",
        selftext="Baking tips only, no software.",
        subreddit="sourdough",
    )
    result = analyze_post(str(post.pk))
    assert result["ok"] is True
    assert result["is_relevant"] is False
    assert result["relevance_score"] < 70
    post.refresh_from_db()
    assert post.status == RedditPost.Status.SKIPPED

    draft_result = generate_draft(str(post.pk))
    assert draft_result["ok"] is False
    assert draft_result["error"] == "post_not_relevant"
    assert DraftResponse.objects.filter(post=post).count() == 0


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", RELEVANCE_THRESHOLD=70)
def test_threshold_boundary_score_69_not_relevant(user) -> None:
    """Score below threshold must gate drafts even if model flags is_relevant."""
    post = _make_post(user, title="django celery oauth redis docker")
    # Force a low score via monkeypatch of client
    from apps.analysis import services as svc

    class LowClient:
        def complete_json(self, **kwargs):
            return {
                "relevance_score": 69,
                "is_relevant": True,  # model inconsistency
                "reasons": ["borderline"],
                "matched_expertise": ["django"],
                "risk_flags": ["uncertain"],
                "summary": "borderline",
            }

    original = svc.get_openai_client
    svc.get_openai_client = lambda: LowClient()  # type: ignore[assignment]
    try:
        result = analyze_post(str(post.pk))
    finally:
        svc.get_openai_client = original  # type: ignore[assignment]

    assert result["ok"] is True
    assert result["is_relevant"] is False
    assert result["relevance_score"] == 69


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", RELEVANCE_THRESHOLD=70)
def test_analyze_idempotent_without_force(user) -> None:
    post = _make_post(user, title="django tips")
    first = analyze_post(str(post.pk))
    second = analyze_post(str(post.pk))
    assert second["skipped"] is True
    assert second["analysis_id"] == first["analysis_id"]
    assert RelevanceAnalysis.objects.filter(post=post).count() == 1


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_celery_tasks_eager(user) -> None:
    post = _make_post(user, title="FastAPI and Redis patterns")
    analyze_post_relevance.delay(str(post.pk))
    analysis = RelevanceAnalysis.objects.get(post=post)
    if analysis.is_relevant:
        generate_draft_response.delay(str(post.pk))
        assert DraftResponse.objects.filter(post=post, status="in_review").exists()


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock")
def test_no_invented_experience_prompt_includes_constraints(user) -> None:
    from apps.analysis.services import build_draft_user_prompt

    post = _make_post(
        user,
        title="Share your personal experience shipping OAuth at FAANG",
        selftext="Need personal war stories from FAANG only.",
    )
    analyze_post(str(post.pk))
    analysis = RelevanceAnalysis.objects.get(post=post)
    prompt = build_draft_user_prompt(post, analysis)
    assert "Never invent experience" in prompt
    assert "personal experience" in prompt.lower()
    assert "API style" in prompt  # writing sample title


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_api_analyze_and_draft_endpoints(auth_client: APIClient, user) -> None:
    post = _make_post(
        user,
        title="Django REST + Celery best practices",
        selftext="How do you structure tasks?",
    )
    analyze = auth_client.post(f"/api/v1/posts/{post.pk}/analyze/", {}, format="json")
    assert analyze.status_code == 202
    assert analyze.json()["never_auto_publish"] is True
    assert analyze.json()["result"]["ok"] is True

    detail = auth_client.get(f"/api/v1/posts/{post.pk}/")
    assert detail.status_code == 200
    assert detail.json()["analysis"]["relevance_score"] >= 70

    draft = auth_client.post(f"/api/v1/posts/{post.pk}/draft/", {}, format="json")
    assert draft.status_code == 202
    assert draft.json()["never_auto_publish"] is True
    assert draft.json()["result"]["status"] == "in_review"

    detail2 = auth_client.get(f"/api/v1/posts/{post.pk}/")
    assert len(detail2.json()["drafts"]) >= 1


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_draft_rejected_for_irrelevant_via_api(auth_client: APIClient, user) -> None:
    post = _make_post(
        user,
        title="Knitting patterns for beginners",
        selftext="yarn weight questions",
        subreddit="knitting",
    )
    auth_client.post(f"/api/v1/posts/{post.pk}/analyze/", {}, format="json")
    draft = auth_client.post(f"/api/v1/posts/{post.pk}/draft/", {}, format="json")
    assert draft.status_code == 400
    assert draft.json()["code"] == "post_not_relevant"


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock")
def test_task_failure_marks_analysis_failed(user, monkeypatch) -> None:
    from apps.analysis import services as svc
    from apps.analysis.openai_client import OpenAIClientError

    class Boom:
        def complete_json(self, **kwargs):
            raise OpenAIClientError("boom")

    monkeypatch.setattr(svc, "get_openai_client", lambda: Boom())
    post = _make_post(user, title="django failure case")
    result = analyze_post(str(post.pk))
    assert result["ok"] is False
    analysis = RelevanceAnalysis.objects.get(post=post)
    assert analysis.status == RelevanceAnalysis.Status.FAILED
    post.refresh_from_db()
    assert post.status == RedditPost.Status.ERROR
