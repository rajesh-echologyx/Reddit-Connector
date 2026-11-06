from django.contrib import admin

from .models import Keyword, Monitor, Subreddit, TaskRun


class KeywordInline(admin.TabularInline):
    model = Keyword
    extra = 0


@admin.register(Monitor)
class MonitorAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "user",
        "is_active",
        "auto_analyze",
        "auto_draft",
        "poll_interval_minutes",
        "last_polled_at",
    )
    list_filter = ("is_active", "auto_analyze", "auto_draft")
    search_fields = ("name", "user__username")
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


@admin.register(TaskRun)
class TaskRunAdmin(admin.ModelAdmin):
    list_display = (
        "task_name",
        "status",
        "user",
        "monitor",
        "retries",
        "started_at",
        "finished_at",
    )
    list_filter = ("status", "task_name")
    search_fields = ("celery_task_id", "message", "task_name")
    readonly_fields = (
        "id",
        "task_name",
        "celery_task_id",
        "status",
        "user",
        "monitor",
        "post_id",
        "message",
        "result",
        "retries",
        "started_at",
        "finished_at",
        "created_at",
        "updated_at",
    )
