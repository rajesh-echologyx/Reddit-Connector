from django.contrib import admin

from .models import RedditAccount, RedditPost


@admin.register(RedditAccount)
class RedditAccountAdmin(admin.ModelAdmin):
    list_display = ("reddit_username", "user", "status", "scopes", "updated_at")
    list_filter = ("status",)
    search_fields = ("reddit_username", "user__username")
    readonly_fields = (
        "access_token_encrypted",
        "refresh_token_encrypted",
        "created_at",
        "updated_at",
    )


@admin.register(RedditPost)
class RedditPostAdmin(admin.ModelAdmin):
    list_display = (
        "reddit_fullname",
        "subreddit",
        "title",
        "score",
        "status",
        "created_utc",
    )
    list_filter = ("status", "subreddit")
    search_fields = ("reddit_fullname", "title", "author")
