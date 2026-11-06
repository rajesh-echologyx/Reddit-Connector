"""Serializers for analysis + drafts."""

from __future__ import annotations

from rest_framework import serializers

from apps.reddit.serializers import RedditPostSerializer

from .models import DraftResponse, RelevanceAnalysis


class RelevanceAnalysisSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelevanceAnalysis
        fields = [
            "id",
            "relevance_score",
            "is_relevant",
            "reasons",
            "matched_expertise",
            "risk_flags",
            "summary",
            "model",
            "prompt_version",
            "status",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DraftResponseSerializer(serializers.ModelSerializer):
    effective_body = serializers.CharField(read_only=True)
    never_auto_publish = serializers.SerializerMethodField()

    class Meta:
        model = DraftResponse
        fields = [
            "id",
            "post",
            "analysis",
            "body",
            "body_edited",
            "private_notes",
            "effective_body",
            "status",
            "tone",
            "claims_made",
            "needs_human_check",
            "model",
            "prompt_version",
            "error_message",
            "generated_at",
            "approved_at",
            "rejected_at",
            "published_at",
            "created_at",
            "updated_at",
            "never_auto_publish",
        ]
        read_only_fields = fields

    def get_never_auto_publish(self, obj) -> bool:
        return True


class RedditPostDetailSerializer(RedditPostSerializer):
    analysis = RelevanceAnalysisSerializer(read_only=True)
    drafts = DraftResponseSerializer(many=True, read_only=True)

    class Meta(RedditPostSerializer.Meta):
        fields = list(RedditPostSerializer.Meta.fields) + ["analysis", "drafts"]
