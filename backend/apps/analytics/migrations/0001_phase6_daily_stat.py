"""Create DailyStat for Phase 6 analytics rollups."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="DailyStat",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("date", models.DateField(db_index=True)),
                ("posts_discovered", models.PositiveIntegerField(default=0)),
                ("relevant_count", models.PositiveIntegerField(default=0)),
                ("drafts_generated", models.PositiveIntegerField(default=0)),
                ("approved", models.PositiveIntegerField(default=0)),
                ("rejected", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="daily_stats",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-date"],
            },
        ),
        migrations.AddIndex(
            model_name="dailystat",
            index=models.Index(
                fields=["user", "date"],
                name="analytics_d_user_id_4f9e0a_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="dailystat",
            constraint=models.UniqueConstraint(
                fields=("user", "date"),
                name="analytics_dailystat_user_date_uniq",
            ),
        ),
    ]
