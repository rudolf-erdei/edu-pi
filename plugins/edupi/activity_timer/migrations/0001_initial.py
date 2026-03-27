# Generated initial migration for Activity Timer Plugin

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="TimerConfig",
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
                    "name",
                    models.CharField(
                        help_text="Name of the timer configuration",
                        max_length=100,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Description of when to use this timer",
                    ),
                ),
                (
                    "duration_minutes",
                    models.PositiveIntegerField(
                        default=10,
                        help_text="Duration in minutes",
                    ),
                ),
                (
                    "warning_threshold_percent",
                    models.PositiveIntegerField(
                        default=20,
                        help_text="Percentage remaining when warning color appears",
                    ),
                ),
                (
                    "enable_buzzer",
                    models.BooleanField(
                        default=True,
                        help_text="Play buzzer sound when timer ends",
                    ),
                ),
                (
                    "led_color_start",
                    models.CharField(
                        default="#00FF00",
                        help_text="Hex color code for timer start (green)",
                        max_length=7,
                    ),
                ),
                (
                    "led_color_warning",
                    models.CharField(
                        default="#FFFF00",
                        help_text="Hex color code for warning state (yellow)",
                        max_length=7,
                    ),
                ),
                (
                    "led_color_end",
                    models.CharField(
                        default="#FF0000",
                        help_text="Hex color code for timer end (red)",
                        max_length=7,
                    ),
                ),
                (
                    "is_default",
                    models.BooleanField(
                        default=False,
                        help_text="Use this as the default configuration",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this configuration is active",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Timer Configuration",
                "verbose_name_plural": "Timer Configurations",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="TimerSession",
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
                            ("running", "Running"),
                            ("paused", "Paused"),
                            ("completed", "Completed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="pending",
                        help_text="Current status of the timer",
                        max_length=20,
                    ),
                ),
                (
                    "duration_seconds",
                    models.PositiveIntegerField(
                        help_text="Total duration in seconds",
                    ),
                ),
                (
                    "remaining_seconds",
                    models.PositiveIntegerField(
                        help_text="Remaining time in seconds",
                    ),
                ),
                (
                    "started_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When the timer was started",
                        null=True,
                    ),
                ),
                (
                    "paused_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When the timer was last paused",
                        null=True,
                    ),
                ),
                (
                    "completed_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When the timer completed",
                        null=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "config",
                    models.ForeignKey(
                        blank=True,
                        help_text="Configuration used for this session",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sessions",
                        to="edupi_activity_timer.timerconfig",
                    ),
                ),
            ],
            options={
                "verbose_name": "Timer Session",
                "verbose_name_plural": "Timer Sessions",
                "ordering": ["-created_at"],
            },
        ),
    ]
