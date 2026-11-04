from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "email",
        "is_personal_owner",
        "is_staff",
        "is_active",
        "date_joined",
    )
    list_filter = ("is_personal_owner", "is_staff", "is_active")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Raddit", {"fields": ("is_personal_owner",)}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("Raddit", {"fields": ("is_personal_owner",)}),
    )
