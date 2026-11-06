"""Admin for DailyStat."""

from django.contrib import admin

from .models import DailyStat


@admin.register(DailyStat)
class DailyStatAdmin(admin.ModelAdmin):
    list_display = (
        "date",
        "user",
        "posts_discovered",
        "relevant_count",
        "drafts_generated",
        "approved",
        "rejected",
        "updated_at",
    )
    list_filter = ("date",)
    search_fields = ("user__username",)
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-date",)
