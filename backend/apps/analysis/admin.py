from django.contrib import admin

from .models import DraftResponse, RelevanceAnalysis


@admin.register(RelevanceAnalysis)
class RelevanceAnalysisAdmin(admin.ModelAdmin):
    list_display = (
        "post",
        "relevance_score",
        "is_relevant",
        "status",
        "model",
        "updated_at",
    )
    list_filter = ("status", "is_relevant")
    search_fields = ("post__reddit_fullname", "summary")
    readonly_fields = ("id", "created_at", "updated_at", "raw_response")


@admin.register(DraftResponse)
class DraftResponseAdmin(admin.ModelAdmin):
    list_display = ("post", "status", "tone", "model", "generated_at")
    list_filter = ("status",)
    search_fields = ("post__reddit_fullname", "body")
    readonly_fields = ("id", "created_at", "updated_at", "raw_response")
