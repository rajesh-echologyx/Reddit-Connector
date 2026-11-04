"""Seed fixture Reddit account, sample monitors, and optionally discover posts."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.monitors.models import Keyword, Monitor, Subreddit
from apps.monitors.tasks import poll_monitor
from apps.reddit.services import ensure_fixture_account

User = get_user_model()


class Command(BaseCommand):
    help = "Load fixture Reddit account + sample monitors (REDDIT_MODE=fixture)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="",
            help="Owner username (defaults to first personal owner / first user).",
        )
        parser.add_argument(
            "--poll",
            action="store_true",
            help="Immediately poll sample monitors to upsert fixture posts.",
        )

    def handle(self, *args, **options):
        if settings.REDDIT_MODE != "fixture":
            self.stdout.write(
                self.style.WARNING(
                    f"REDDIT_MODE={settings.REDDIT_MODE}; still seeding fixture account for local use."
                )
            )

        username = options["username"]
        if username:
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist as exc:
                raise CommandError(f"User {username!r} not found") from exc
        else:
            user = (
                User.objects.filter(is_personal_owner=True).first()
                or User.objects.order_by("date_joined").first()
            )
            if user is None:
                raise CommandError(
                    "No users exist. Bootstrap an owner first via /api/v1/auth/bootstrap/."
                )

        account = ensure_fixture_account(user)
        self.stdout.write(f"RedditAccount ready: {account} for {user.username}")

        monitor, created = Monitor.objects.get_or_create(
            user=user,
            name="Sample research monitor",
            defaults={
                "is_active": True,
                "poll_interval_minutes": 15,
                "include_nsfw": False,
            },
        )
        for name in ("python", "learnprogramming", "webdev", "datascience", "devops"):
            sub, _ = Subreddit.objects.get_or_create(name=name)
            monitor.subreddits.add(sub)

        for phrase, mode in (
            ("django celery", Keyword.MatchMode.ALL_WORDS),
            ("reddit oauth", Keyword.MatchMode.ANY),
            ("fixture", Keyword.MatchMode.ANY),
        ):
            Keyword.objects.get_or_create(
                monitor=monitor,
                phrase=phrase,
                match_mode=mode,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Monitor {'created' if created else 'updated'}: {monitor.name} ({monitor.pk})"
            )
        )

        if options["poll"]:
            result = poll_monitor(str(monitor.pk))
            self.stdout.write(self.style.SUCCESS(f"Poll result: {result}"))
        else:
            self.stdout.write("Tip: re-run with --poll to discover fixture posts into the DB.")
