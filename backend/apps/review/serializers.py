"""Review queue serializers."""

from __future__ import annotations

from rest_framework import serializers

from apps.analysis.serializers import DraftResponseSerializer

from .models import ReviewAction
from .services import absolute_reddit_url, reddit_submit_enabled


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
    post_author = serializers.CharField(source="post.author", read_only=True)
    post_selftext = serializers.CharField(source="post.selftext", read_only=True)
    post_score = serializers.IntegerField(source="post.score", read_only=True)
    relevance_score = serializers.SerializerMethodField()
    permalink = serializers.SerializerMethodField()
    reddit_url = serializers.SerializerMethodField()
    reddit_submit_enabled = serializers.SerializerMethodField()

    class Meta(DraftResponseSerializer.Meta):
        fields = list(DraftResponseSerializer.Meta.fields) + [
            "post_title",
            "post_subreddit",
            "post_author",
            "post_selftext",
            "post_score",
            "relevance_score",
            "permalink",
            "reddit_url",
            "reddit_submit_enabled",
        ]

    def get_relevance_score(self, obj) -> int | None:
        if obj.analysis_id and obj.analysis:
            return obj.analysis.relevance_score
        return None

    def get_permalink(self, obj) -> str:
        return absolute_reddit_url(obj)

    def get_reddit_url(self, obj) -> str:
        return absolute_reddit_url(obj)

    def get_reddit_submit_enabled(self, obj) -> bool:
        return reddit_submit_enabled()
