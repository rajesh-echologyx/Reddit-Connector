from django.contrib import admin

from .models import Keyword, Monitor, Subreddit


class KeywordInline(admin.TabularInline):
    model = Keyword
    extra = 0


@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "is_active", "poll_interval_minutes", "last_polled_at")
    list_filter = ("is_active",)
    search_fields = ("name", "user__username")
    filter_horizontal = ("subreddits",)
    inlines = [KeywordInline]


@admin.register(Subreddit)
class SubredditAdmin(admin.ModelAdmin):
    list_display = ("name", "reddit_id", "updated_at")
    search_fields = ("name",)


@admin.register(Keyword)
class KeywordAdmin(admin.ModelAdmin):
    list_display = ("phrase", "match_mode", "monitor", "created_at")
    list_filter = ("match_mode",)
    search_fields = ("phrase",)
