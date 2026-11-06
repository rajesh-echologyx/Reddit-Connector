from django.urls import path

from . import views

urlpatterns = [
    path("review/queue/", views.ReviewQueueView.as_view(), name="review-queue"),
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
        "review/<uuid:draft_id>/actions/",
        views.ReviewActionListView.as_view(),
        name="review-actions",
    ),
]
