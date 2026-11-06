"""Serializers for monitors, keywords, and task runs."""

from __future__ import annotations

from rest_framework import serializers

from .models import Keyword, Monitor, Subreddit, TaskRun


class SubredditSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subreddit
        fields = ["id", "name", "reddit_id", "created_at", "updated_at"]
        read_only_fields = ["id", "reddit_id", "created_at", "updated_at"]


class KeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = Keyword
        fields = ["id", "phrase", "match_mode", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class MonitorSerializer(serializers.ModelSerializer):
    keywords = KeywordSerializer(many=True, read_only=True)
    subreddits = SubredditSerializer(many=True, read_only=True)
    subreddit_names = serializers.ListField(
        child=serializers.CharField(max_length=128),
        write_only=True,
        required=False,
    )
    never_auto_publish = serializers.SerializerMethodField()

    class Meta:
        model = Monitor
        fields = [
            "id",
            "name",
            "is_active",
            "auto_analyze",
            "auto_draft",
            "poll_interval_minutes",
            "min_score",
            "min_comments",
            "include_nsfw",
            "keywords",
            "subreddits",
            "subreddit_names",
            "last_polled_at",
            "last_error",
            "last_error_at",
            "created_at",
            "updated_at",
            "never_auto_publish",
        ]
        read_only_fields = [
            "id",
            "keywords",
            "subreddits",
            "last_polled_at",
            "last_error",
            "last_error_at",
            "created_at",
            "updated_at",
            "never_auto_publish",
        ]

    def get_never_auto_publish(self, obj) -> bool:  # noqa: ARG002
        return True

    def validate_poll_interval_minutes(self, value: int) -> int:
        if value < 5:
            raise serializers.ValidationError("poll_interval_minutes must be at least 5.")
        return value

    def _set_subreddits(self, monitor: Monitor, names: list[str] | None) -> None:
        if names is None:
            return
        subs = []
        for raw in names:
            name = raw.strip().lstrip("r/").lower()
            if not name:
                continue
            sub, _ = Subreddit.objects.get_or_create(name=name)
            subs.append(sub)
        monitor.subreddits.set(subs)

    def create(self, validated_data):
        names = validated_data.pop("subreddit_names", None)
        user = self.context["request"].user
        monitor = Monitor.objects.create(user=user, **validated_data)
        self._set_subreddits(monitor, names)
        return monitor

    def update(self, instance, validated_data):
        names = validated_data.pop("subreddit_names", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self._set_subreddits(instance, names)
        return instance


class KeywordCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Keyword
        fields = ["id", "phrase", "match_mode", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_phrase(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("phrase is required.")
        return value


class TaskRunSerializer(serializers.ModelSerializer):
    monitor_name = serializers.SerializerMethodField()
    never_auto_publish = serializers.SerializerMethodField()

    class Meta:
        model = TaskRun
        fields = [
            "id",
            "task_name",
            "celery_task_id",
            "status",
            "monitor",
            "monitor_name",
            "post_id",
            "message",
            "result",
            "retries",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
            "never_auto_publish",
        ]
        read_only_fields = fields

    def get_monitor_name(self, obj: TaskRun) -> str | None:
        if obj.monitor_id and obj.monitor:
            return obj.monitor.name
        return None

    def get_never_auto_publish(self, obj) -> bool:  # noqa: ARG002
        return True
