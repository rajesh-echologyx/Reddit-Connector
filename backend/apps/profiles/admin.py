from django.contrib import admin

from .models import UserProfile, WritingSample


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "updated_at")
    search_fields = ("user__username", "display_name")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(WritingSample)
class WritingSampleAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "source", "is_active", "updated_at")
    list_filter = ("is_active", "source")
    search_fields = ("title", "user__username")
    readonly_fields = ("id", "created_at", "updated_at")
