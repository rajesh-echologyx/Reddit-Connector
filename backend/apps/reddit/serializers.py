"""Serializers for Reddit account status + posts."""

from __future__ import annotations

from rest_framework import serializers

from .models import RedditAccount, RedditPost


class RedditStatusSerializer(serializers.Serializer):
    connected = serializers.BooleanField()
    status = serializers.CharField(allow_null=True)
    reddit_username = serializers.CharField(allow_blank=True, allow_null=True)
    scopes = serializers.CharField(allow_blank=True, allow_null=True)
    mode = serializers.CharField()
    token_expires_at = serializers.DateTimeField(allow_null=True)
    never_auto_publish = serializers.BooleanField(default=True)


class RedditPostSerializer(serializers.ModelSerializer):
    monitor_id = serializers.UUIDField(
        source="discovered_via_monitor_id",
        allow_null=True,
        read_only=True,
    )
    reddit_url = serializers.SerializerMethodField()
    relevance_score = serializers.SerializerMethodField()
    is_relevant = serializers.SerializerMethodField()

    class Meta:
        model = RedditPost
        fields = [
            "id",
            "reddit_fullname",
            "reddit_id",
            "subreddit",
            "title",
            "selftext",
            "author",
            "url",
            "permalink",
            "reddit_url",
            "score",
            "num_comments",
            "created_utc",
            "status",
            "monitor_id",
            "relevance_score",
            "is_relevant",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_reddit_url(self, obj: RedditPost) -> str:
        if obj.permalink:
            if obj.permalink.startswith("http"):
                return obj.permalink
            return f"https://www.reddit.com{obj.permalink}"
        return obj.url or ""

    def _analysis_or_none(self, obj: RedditPost):
        try:
            return obj.analysis
        except Exception:  # RelatedObjectDoesNotExist when unscored
            return None

    def get_relevance_score(self, obj: RedditPost) -> int | None:
        analysis = self._analysis_or_none(obj)
        if analysis is None:
            return None
        return analysis.relevance_score

    def get_is_relevant(self, obj: RedditPost) -> bool | None:
        analysis = self._analysis_or_none(obj)
        if analysis is None:
            return None
        return analysis.is_relevant


class RedditAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = RedditAccount
        fields = [
            "id",
            "reddit_username",
            "reddit_user_id",
            "scopes",
            "status",
            "token_expires_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
