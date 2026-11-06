"""Serializers for profile + writing samples."""

from __future__ import annotations

from django.conf import settings
from rest_framework import serializers

from .models import UserProfile, WritingSample


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = [
            "id",
            "display_name",
            "bio_short",
            "expertise_topics",
            "tone_notes",
            "hard_constraints",
            "openai_relevance_model",
            "openai_draft_model",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_expertise_topics(self, value):
        if value is None:
            return []
        if not isinstance(value, list):
            raise serializers.ValidationError("expertise_topics must be a list of strings.")
        cleaned = []
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError("Each expertise topic must be a string.")
            topic = item.strip()
            if topic:
                cleaned.append(topic)
        return cleaned


class WritingSampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WritingSample
        fields = [
            "id",
            "title",
            "body",
            "source",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_title(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("title is required.")
        return value

    def validate_body(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("body is required.")
        return value

    def validate(self, attrs: dict) -> dict:
        user = self.context["request"].user
        becoming_active = attrs.get("is_active", True)
        if self.instance is not None:
            becoming_active = attrs.get("is_active", self.instance.is_active)
        if becoming_active:
            qs = WritingSample.objects.filter(user=user, is_active=True)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            max_active = getattr(settings, "MAX_ACTIVE_WRITING_SAMPLES", 5)
            if qs.count() >= max_active:
                raise serializers.ValidationError(
                    {
                        "is_active": (
                            f"At most {max_active} active writing samples allowed "
                            "(token budget)."
                        )
                    }
                )
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        return WritingSample.objects.create(user=user, **validated_data)
