from django.urls import path

from . import views

urlpatterns = [
    path("reddit/oauth/start/", views.oauth_start, name="reddit-oauth-start"),
    path("reddit/oauth/callback/", views.oauth_callback, name="reddit-oauth-callback"),
    path("reddit/status/", views.reddit_status, name="reddit-status"),
    path("reddit/disconnect/", views.reddit_disconnect, name="reddit-disconnect"),
    path("posts/", views.RedditPostListView.as_view(), name="reddit-posts-list"),
    # Detail + analyze/draft live in apps.analysis.urls (Phase 3).
]
