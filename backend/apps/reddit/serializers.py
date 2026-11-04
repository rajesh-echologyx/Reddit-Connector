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
