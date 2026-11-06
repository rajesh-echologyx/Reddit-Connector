from django.urls import path

from . import views

urlpatterns = [
    path("review/queue/", views.ReviewQueueView.as_view(), name="review-queue"),
    path(
        "review/<uuid:draft_id>/",
        views.ReviewDetailView.as_view(),
        name="review-detail",
    ),
    path(
        "review/<uuid:draft_id>/edit/",
        views.ReviewEditView.as_view(),
        name="review-edit",
    ),
    path(
        "review/<uuid:draft_id>/approve/",
        views.ReviewApproveView.as_view(),
        name="review-approve",
    ),
    path(
        "review/<uuid:draft_id>/reject/",
        views.ReviewRejectView.as_view(),
        name="review-reject",
    ),
    path(
        "review/<uuid:draft_id>/save-for-later/",
        views.ReviewSaveForLaterView.as_view(),
        name="review-save-for-later",
    ),
    path(
        "review/<uuid:draft_id>/reopen/",
        views.ReviewReopenView.as_view(),
        name="review-reopen",
    ),
    path(
        "review/<uuid:draft_id>/mark-published/",
        views.ReviewMarkPublishedView.as_view(),
        name="review-mark-published",
    ),
    path(
        "review/<uuid:draft_id>/notes/",
        views.ReviewNotesView.as_view(),
        name="review-notes",
    ),
    path(
        "review/<uuid:draft_id>/regenerate/",
        views.ReviewRegenerateView.as_view(),
        name="review-regenerate",
    ),
    path(
        "review/<uuid:draft_id>/export/",
        views.ReviewExportView.as_view(),
        name="review-export",
    ),
    path(
        "review/<uuid:draft_id>/submit/",
        views.ReviewSubmitView.as_view(),
        name="review-submit",
    ),
    path(
        "review/<uuid:draft_id>/actions/",
        views.ReviewActionListView.as_view(),
        name="review-actions",
    ),
]
