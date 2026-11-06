# Generated manually for Phase 4 review workflow.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("review", "0001_phase3_ai_integration"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reviewaction",
            name="action",
            field=models.CharField(
                choices=[
                    ("approve", "Approve"),
                    ("reject", "Reject"),
                    ("edit", "Edit"),
                    ("regenerate", "Regenerate"),
                    ("save_for_later", "Save for later"),
                    ("mark_published", "Mark published"),
                    ("note", "Private note"),
                    ("reopen", "Return to queue"),
                ],
                max_length=32,
            ),
        ),
    ]
