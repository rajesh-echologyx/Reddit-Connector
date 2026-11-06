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
        "monitors/<uuid:pk>/pause/",
        views.MonitorPauseView.as_view(),
        name="monitors-pause",
    ),
    path(
        "monitors/<uuid:pk>/resume/",
        views.MonitorResumeView.as_view(),
        name="monitors-resume",
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
    path("tasks/", views.TaskRunListView.as_view(), name="tasks-list"),
    path("tasks/<uuid:pk>/", views.TaskRunDetailView.as_view(), name="tasks-detail"),
    path(
        "automation/status/",
        views.AutomationStatusView.as_view(),
        name="automation-status",
    ),
]
