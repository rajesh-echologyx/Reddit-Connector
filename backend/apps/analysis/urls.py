from django.urls import path

from . import views

urlpatterns = [
    path("posts/<uuid:pk>/", views.PostDetailWithAnalysisView.as_view(), name="posts-detail"),
    path("posts/<uuid:pk>/analyze/", views.PostAnalyzeView.as_view(), name="posts-analyze"),
    path("posts/<uuid:pk>/draft/", views.PostDraftView.as_view(), name="posts-draft"),
    path("analysis/<uuid:pk>/", views.AnalysisDetailView.as_view(), name="analysis-detail"),
    path("drafts/<uuid:pk>/", views.DraftDetailView.as_view(), name="drafts-detail"),
]
