"""Minimal review queue serializers (Phase 4 stubs)."""

from __future__ import annotations

from rest_framework import serializers

from apps.analysis.serializers import DraftResponseSerializer

from .models import ReviewAction


class ReviewActionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewAction
        fields = [
            "id",
            "draft",
            "actor",
            "action",
            "notes",
            "snapshot_body",
            "created_at",
        ]
        read_only_fields = fields


class ReviewQueueItemSerializer(DraftResponseSerializer):
    post_title = serializers.CharField(source="post.title", read_only=True)
    post_subreddit = serializers.CharField(source="post.subreddit", read_only=True)
    relevance_score = serializers.SerializerMethodField()
    permalink = serializers.CharField(source="post.permalink", read_only=True)

    class Meta(DraftResponseSerializer.Meta):
        fields = list(DraftResponseSerializer.Meta.fields) + [
            "post_title",
            "post_subreddit",
            "relevance_score",
            "permalink",
        ]

    def get_relevance_score(self, obj) -> int | None:
        if obj.analysis_id and obj.analysis:
            return obj.analysis.relevance_score
        return None
