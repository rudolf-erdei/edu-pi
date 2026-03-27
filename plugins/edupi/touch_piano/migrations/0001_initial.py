# Generated initial migration for Touch Piano plugin

from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PianoConfig",
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
                        help_text="Name of the piano configuration",
                        max_length=100,
                    ),
                ),
                (
                    "description",
                    models.TextField(
                        blank=True,
                        help_text="Description of this piano setup",
                    ),
                ),
                (
                    "volume",
                    models.PositiveIntegerField(
                        default=80,
                        help_text="Piano volume (0-100%)",
                    ),
                ),
                (
                    "sensitivity",
                    models.PositiveIntegerField(
                        default=5,
                        help_text="Touch sensitivity (1-10, higher = more sensitive)",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this configuration is active",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
            ],
            options={
                "verbose_name": "Piano Configuration",
                "verbose_name_plural": "Piano Configurations",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="PianoSession",
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
                    "started_at",
                    models.DateTimeField(
                        default=timezone.now,
                        help_text="When the session started",
                    ),
                ),
                (
                    "ended_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="When the session ended",
                        null=True,
                    ),
                ),
                (
                    "total_key_presses",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Total number of key presses in this session",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this session is currently active",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "config",
                    models.ForeignKey(
                        blank=True,
                        help_text="Configuration used for this session",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sessions",
                        to="edupi_touch_piano.pianoconfig",
                    ),
                ),
            ],
            options={
                "verbose_name": "Piano Session",
                "verbose_name_plural": "Piano Sessions",
                "ordering": ["-started_at"],
            },
        ),
        migrations.CreateModel(
            name="PianoKey",
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
                    "key_number",
                    models.PositiveIntegerField(
                        help_text="Key number (1-6)",
                    ),
                ),
                (
                    "note",
                    models.CharField(
                        help_text="Musical note (e.g., C4, D4, E4)",
                        max_length=10,
                    ),
                ),
                (
                    "frequency",
                    models.FloatField(
                        help_text="Note frequency in Hz",
                    ),
                ),
                (
                    "gpio_pin",
                    models.PositiveIntegerField(
                        help_text="GPIO pin number (BCM)",
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        blank=True,
                        help_text="Optional label for the key",
                        max_length=50,
                    ),
                ),
                (
                    "color",
                    models.CharField(
                        default="#3B82F6",
                        help_text="Hex color code for this key on the web interface",
                        max_length=7,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Whether this key is enabled",
                    ),
                ),
                (
                    "config",
                    models.ForeignKey(
                        help_text="Configuration this key belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="keys",
                        to="edupi_touch_piano.pianoconfig",
                    ),
                ),
            ],
            options={
                "verbose_name": "Piano Key",
                "verbose_name_plural": "Piano Keys",
                "ordering": ["key_number"],
                "unique_together": {("config", "key_number")},
            },
        ),
        migrations.CreateModel(
            name="KeyPress",
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
                    "key_number",
                    models.PositiveIntegerField(
                        help_text="Key number (1-6)",
                    ),
                ),
                (
                    "note",
                    models.CharField(
                        help_text="Musical note played",
                        max_length=10,
                    ),
                ),
                (
                    "pressed_at",
                    models.DateTimeField(
                        default=timezone.now,
                        help_text="When the key was pressed",
                    ),
                ),
                (
                    "duration_ms",
                    models.PositiveIntegerField(
                        blank=True,
                        help_text="Duration of the press in milliseconds",
                        null=True,
                    ),
                ),
                (
                    "key",
                    models.ForeignKey(
                        blank=True,
                        help_text="Key that was pressed",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="edupi_touch_piano.pianokey",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        help_text="Session this key press belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="key_presses",
                        to="edupi_touch_piano.pianosession",
                    ),
                ),
            ],
            options={
                "verbose_name": "Key Press",
                "verbose_name_plural": "Key Presses",
                "ordering": ["-pressed_at"],
            },
        ),
    ]
