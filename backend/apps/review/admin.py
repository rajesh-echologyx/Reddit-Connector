from django.contrib import admin

from .models import ReviewAction


@admin.register(ReviewAction)
class ReviewActionAdmin(admin.ModelAdmin):
    list_display = ("action", "draft", "actor", "created_at")
    list_filter = ("action",)
    search_fields = ("notes", "draft__post__reddit_fullname")
    readonly_fields = ("id", "draft", "actor", "action", "notes", "snapshot_body", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
