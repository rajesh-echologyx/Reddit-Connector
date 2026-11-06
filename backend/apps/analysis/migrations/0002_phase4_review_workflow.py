# Generated manually for Phase 4 review workflow.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("analysis", "0001_phase3_ai_integration"),
    ]

    operations = [
        migrations.AddField(
            model_name="draftresponse",
            name="private_notes",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Operator-only notes; never sent to Reddit.",
            ),
        ),
        migrations.AddField(
            model_name="draftresponse",
            name="published_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When the operator marked the reply as manually published.",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="draftresponse",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("in_review", "In review"),
                    ("saved_for_later", "Saved for later"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                    ("published", "Published"),
                    ("discarded", "Discarded"),
                ],
                db_index=True,
                default="draft",
                max_length=32,
            ),
        ),
    ]
