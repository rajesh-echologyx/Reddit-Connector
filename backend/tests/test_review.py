"""Phase 4 review workflow — state machine, ownership, no auto-publish."""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from apps.analysis.models import DraftResponse
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
def other_user(db):
    u = User.objects.create_user(
        username="other",
        password="Str0ngPass!word",
    )
    UserProfile.objects.create(user=u, expertise_topics=["golang"])
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
        permalink="/r/python/comments/reviewstub/django_celery/",
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
    assert queue.json()["reddit_submit_enabled"] is False
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
    assert edit.json()["reddit_url"].startswith("https://www.reddit.com/")

    export = auth_client.get(f"/api/v1/review/{draft.pk}/export/")
    assert export.status_code == 200
    assert export.json()["text"] == "Edited reply body."
    assert export.json()["never_auto_publish"] is True
    assert export.json()["permalink"].startswith("https://www.reddit.com/")

    reject = auth_client.post(
        f"/api/v1/review/{draft.pk}/reject/",
        {"notes": "too generic"},
        format="json",
    )
    assert reject.status_code == 200
    draft.refresh_from_db()
    assert draft.status == DraftResponse.Status.REJECTED


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_save_for_later_reopen_notes_mark_published(auth_client: APIClient, draft) -> None:
    later = auth_client.post(
        f"/api/v1/review/{draft.pk}/save-for-later/",
        {},
        format="json",
    )
    assert later.status_code == 200
    draft.refresh_from_db()
    assert draft.status == DraftResponse.Status.SAVED_FOR_LATER
    assert ReviewAction.objects.filter(
        draft=draft, action=ReviewAction.Action.SAVE_FOR_LATER
    ).exists()

    notes = auth_client.post(
        f"/api/v1/review/{draft.pk}/notes/",
        {"private_notes": "Tone down the CTA"},
        format="json",
    )
    assert notes.status_code == 200
    draft.refresh_from_db()
    assert draft.private_notes == "Tone down the CTA"
    assert ReviewAction.objects.filter(
        draft=draft, action=ReviewAction.Action.NOTE
    ).exists()

    reopen = auth_client.post(
        f"/api/v1/review/{draft.pk}/reopen/",
        {},
        format="json",
    )
    assert reopen.status_code == 200
    draft.refresh_from_db()
    assert draft.status == DraftResponse.Status.IN_REVIEW

    approve = auth_client.post(
        f"/api/v1/review/{draft.pk}/approve/",
        {},
        format="json",
    )
    assert approve.status_code == 200

    published = auth_client.post(
        f"/api/v1/review/{draft.pk}/mark-published/",
        {"notes": "pasted manually"},
        format="json",
    )
    assert published.status_code == 200
    assert "manually" in published.json()["detail"].lower() or "Nothing was auto-submitted" in published.json()["detail"]
    draft.refresh_from_db()
    assert draft.status == DraftResponse.Status.PUBLISHED
    assert draft.published_at is not None
    assert ReviewAction.objects.filter(
        draft=draft, action=ReviewAction.Action.MARK_PUBLISHED
    ).exists()


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_regenerate_discards_old_creates_new(auth_client: APIClient, draft) -> None:
    old_id = draft.pk
    regen = auth_client.post(
        f"/api/v1/review/{draft.pk}/regenerate/",
        {},
        format="json",
    )
    assert regen.status_code == 202
    assert regen.json()["never_auto_publish"] is True

    draft.refresh_from_db()
    assert draft.status == DraftResponse.Status.DISCARDED
    assert ReviewAction.objects.filter(
        draft_id=old_id, action=ReviewAction.Action.REGENERATE
    ).exists()

    new_drafts = DraftResponse.objects.filter(
        post_id=draft.post_id,
        status=DraftResponse.Status.IN_REVIEW,
    )
    assert new_drafts.exists()
    assert new_drafts.first().pk != old_id


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_own_drafts_only(auth_client: APIClient, draft, other_user) -> None:
    other_client = APIClient()
    other_client.force_authenticate(user=other_user)

    denied = other_client.post(
        f"/api/v1/review/{draft.pk}/approve/",
        {},
        format="json",
    )
    assert denied.status_code == 404

    detail = other_client.get(f"/api/v1/review/{draft.pk}/")
    assert detail.status_code == 404

    queue = other_client.get("/api/v1/review/queue/")
    assert queue.status_code == 200
    assert queue.json()["count"] == 0


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_invalid_transitions(auth_client: APIClient, draft) -> None:
    auth_client.post(f"/api/v1/review/{draft.pk}/approve/", {}, format="json")
    again = auth_client.post(
        f"/api/v1/review/{draft.pk}/approve/",
        {},
        format="json",
    )
    assert again.status_code == 400
    assert again.json()["code"] == "invalid_state"

    later = auth_client.post(
        f"/api/v1/review/{draft.pk}/save-for-later/",
        {},
        format="json",
    )
    assert later.status_code == 400


@pytest.mark.django_db
@override_settings(
    OPENAI_MODE="mock",
    CELERY_TASK_ALWAYS_EAGER=True,
    REDDIT_SUBMIT_ENABLED=False,
)
def test_submit_feature_flag_default_false(auth_client: APIClient, draft) -> None:
    submit = auth_client.post(
        f"/api/v1/review/{draft.pk}/submit/",
        {},
        format="json",
    )
    assert submit.status_code == 403
    assert submit.json()["code"] == "submit_disabled"
    assert submit.json()["reddit_submit_enabled"] is False
    assert submit.json()["never_auto_publish"] is True


@pytest.mark.django_db
@override_settings(
    OPENAI_MODE="mock",
    CELERY_TASK_ALWAYS_EAGER=True,
    REDDIT_SUBMIT_ENABLED=True,
)
def test_submit_flag_on_still_not_implemented(auth_client: APIClient, draft) -> None:
    submit = auth_client.post(
        f"/api/v1/review/{draft.pk}/submit/",
        {},
        format="json",
    )
    assert submit.status_code == 501
    assert submit.json()["code"] == "submit_not_implemented"
    assert submit.json()["never_auto_publish"] is True


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_csrf_required_on_mutations(user, draft) -> None:
    """Session auth without CSRF header must fail on mutating review endpoints."""
    client = APIClient(enforce_csrf_checks=True)
    assert client.login(username="owner", password="Str0ngPass!word")

    csrf = client.get("/api/v1/auth/csrf/")
    assert csrf.status_code == 200
    token = csrf.cookies["csrftoken"].value

    missing = client.post(
        f"/api/v1/review/{draft.pk}/approve/",
        {"notes": "no csrf"},
        format="json",
    )
    assert missing.status_code == 403

    ok = client.post(
        f"/api/v1/review/{draft.pk}/approve/",
        {"notes": "with csrf"},
        format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert ok.status_code == 200
    assert ok.json()["never_auto_publish"] is True


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_review_action_append_only(draft, user) -> None:
    action = ReviewAction.objects.create(
        draft=draft,
        actor=user,
        action=ReviewAction.Action.EDIT,
        notes="n",
        snapshot_body="body",
    )
    with pytest.raises(ValueError, match="append-only"):
        action.notes = "changed"
        action.save()


@pytest.mark.django_db
@override_settings(OPENAI_MODE="mock", CELERY_TASK_ALWAYS_EAGER=True)
def test_queue_status_filter(auth_client: APIClient, draft) -> None:
    auth_client.post(f"/api/v1/review/{draft.pk}/save-for-later/", {}, format="json")
    active = auth_client.get("/api/v1/review/queue/?status=in_review,draft")
    assert active.json()["count"] == 0
    saved = auth_client.get("/api/v1/review/queue/?status=saved_for_later")
    assert saved.json()["count"] == 1
    assert saved.json()["results"][0]["id"] == str(draft.pk)
