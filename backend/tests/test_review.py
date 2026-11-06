"""Phase 4 review stubs — store drafts without publishing."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from apps.analysis.models import DraftResponse, RelevanceAnalysis
from apps.analysis.services import analyze_post, generate_draft
from apps.profiles.models import UserProfile
from apps.reddit.models import RedditPost
from apps.review.models import ReviewAction

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
        expertise_topics=["django", "python"],
        hard_constraints="Never invent experience.",
    )
    return u


@pytest.fixture
def auth_client(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def draft(user):
    post = RedditPost.objects.create(
        user=user,
        reddit_fullname="t3_reviewstub",
        reddit_id="reviewstub",
        subreddit="python",
        title="Django Celery monitoring tips",
        selftext="How do you monitor Celery workers with Django?",
        author="op",
        status=RedditPost.Status.NEW,
    )
    analyze_post(str(post.pk))
    result = generate_draft(str(post.pk))
    assert result["ok"]
    return DraftResponse.objects.get(pk=result["draft_id"])


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_review_queue_and_approve_never_publishes(auth_client: APIClient, draft) -> None:
    queue = auth_client.get("/api/v1/review/queue/")
    assert queue.status_code == 200
    assert queue.json()["never_auto_publish"] is True
    assert queue.json()["count"] >= 1

    approve = auth_client.post(
        f"/api/v1/review/{draft.pk}/approve/",
        {"notes": "looks good"},
        format="json",
    )
    assert approve.status_code == 200
    assert "Nothing was posted to Reddit" in approve.json()["detail"]
    assert approve.json()["never_auto_publish"] is True

    draft.refresh_from_db()
    assert draft.status == DraftResponse.Status.APPROVED
    assert ReviewAction.objects.filter(
        draft=draft, action=ReviewAction.Action.APPROVE
    ).exists()


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_review_edit_reject_export(auth_client: APIClient, draft) -> None:
    edit = auth_client.post(
        f"/api/v1/review/{draft.pk}/edit/",
        {"body_edited": "Edited reply body."},
        format="json",
    )
    assert edit.status_code == 200
    assert edit.json()["effective_body"] == "Edited reply body."

    export = auth_client.get(f"/api/v1/review/{draft.pk}/export/")
    assert export.status_code == 200
    assert export.json()["text"] == "Edited reply body."
    assert export.json()["never_auto_publish"] is True

    reject = auth_client.post(
        f"/api/v1/review/{draft.pk}/reject/",
        {"notes": "too generic"},
        format="json",
    )
    assert reject.status_code == 200
    draft.refresh_from_db()
    assert draft.status == DraftResponse.Status.REJECTED
