# Generated migration for Routines plugin

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RoutineCategory",
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
                    "category_type",
                    models.CharField(
                        choices=[
                            ("warm_up", "Warm-up"),
                            ("transition", "Transition"),
                            ("cooldown", "Cooldown"),
                            ("custom", "Custom"),
                        ],
                        default="custom",
                        max_length=20,
                        unique=True,
                    ),
                ),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                (
                    "display_color",
                    models.CharField(default="#3B82F6", max_length=7),
                ),
                ("order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Routine Category",
                "verbose_name_plural": "Routine Categories",
                "ordering": ["order", "name"],
            },
        ),
        migrations.CreateModel(
            name="Routine",
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
                ("title", models.CharField(max_length=200)),
                ("content", models.TextField()),
                (
                    "audio_file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to="routines/audio/%(instance_id)s/%(filename)s",
                    ),
                ),
                (
                    "tts_engine",
                    models.CharField(
                        choices=[
                            ("pyttsx3", "System TTS (Offline)"),
                            ("edge_tts", "Edge TTS (High Quality)"),
                            ("gtts", "Google TTS (Online)"),
                            ("none", "Use Uploaded Audio"),
                        ],
                        default="pyttsx3",
                        max_length=20,
                    ),
                ),
                ("tts_speed", models.FloatField(default=1.0)),
                ("tts_voice", models.CharField(blank=True, max_length=100)),
                ("tts_language", models.CharField(default="en", max_length=10)),
                ("is_pre_built", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "category",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="routines",
                        to="edupi_routines.routinecategory",
                    ),
                ),
            ],
            options={
                "verbose_name": "Routine",
                "verbose_name_plural": "Routines",
                "ordering": ["-is_pre_built", "category__order", "title"],
            },
        ),
        migrations.CreateModel(
            name="RoutineSession",
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
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("playing", "Playing"),
                            ("paused", "Paused"),
                            ("completed", "Completed"),
                            ("stopped", "Stopped"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("current_line_index", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("paused_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "total_duration_seconds",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "routine",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sessions",
                        to="edupi_routines.routine",
                    ),
                ),
            ],
            options={
                "verbose_name": "Routine Session",
                "verbose_name_plural": "Routine Sessions",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PresenterButtonMapping",
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
                ("name", models.CharField(default="Default", max_length=50)),
                ("next_button_code", models.PositiveIntegerField(default=115)),
                ("prev_button_code", models.PositiveIntegerField(default=114)),
                ("play_pause_button_code", models.PositiveIntegerField(default=164)),
                ("stop_button_code", models.PositiveIntegerField(default=116)),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Presenter Button Mapping",
                "verbose_name_plural": "Presenter Button Mappings",
                "ordering": ["name"],
            },
        ),
    ]
