from django.urls import path

from . import views

urlpatterns = [
    path("monitors/", views.MonitorListCreateView.as_view(), name="monitors-list"),
    path("monitors/<uuid:pk>/", views.MonitorDetailView.as_view(), name="monitors-detail"),
    path(
        "monitors/<uuid:pk>/run/",
        views.MonitorRunView.as_view(),
        name="monitors-run",
    ),
    path(
        "monitors/<uuid:pk>/keywords/",
        views.MonitorKeywordListCreateView.as_view(),
        name="monitors-keywords",
    ),
    path(
        "monitors/<uuid:pk>/keywords/<uuid:keyword_id>/",
        views.MonitorKeywordDetailView.as_view(),
        name="monitors-keyword-detail",
    ),
    path(
        "monitors/<uuid:pk>/subreddits/",
        views.MonitorSubredditsReplaceView.as_view(),
        name="monitors-subreddits",
    ),
]
