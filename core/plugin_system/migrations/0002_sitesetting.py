# Generated manually for SiteSetting model

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("plugin_system", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteSetting",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        help_text="Setting key (e.g., 'tinko.global.school_name')",
                        max_length=255,
                        unique=True,
                    ),
                ),
                (
                    "value",
                    models.TextField(
                        blank=True,
                        help_text="Setting value (JSON encoded for non-text types)",
                    ),
                ),
                (
                    "setting_type",
                    models.CharField(
                        choices=[
                            ("text", "Text"),
                            ("number", "Number"),
                            ("boolean", "Boolean"),
                            ("image", "Image"),
                            ("json", "JSON"),
                        ],
                        default="text",
                        help_text="Data type of the setting",
                        max_length=20,
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        help_text="Display label for the setting", max_length=200
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True, help_text="Help text for this setting"
                    ),
                ),
                (
                    "section",
                    models.CharField(
                        blank=True,
                        default="General",
                        help_text="Section/group for organizing settings (e.g., 'General > Display')",
                        max_length=100,
                    ),
                ),
                (
                    "is_system",
                    models.BooleanField(
                        default=False, help_text="System settings cannot be deleted"
                    ),
                ),
                (
                    "order",
                    models.PositiveIntegerField(
                        default=0, help_text="Display order within section"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Site Setting",
                "verbose_name_plural": "Site Settings",
                "ordering": ["section", "order", "key"],
            },
        ),
    ]
