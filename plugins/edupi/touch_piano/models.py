"""Django models for Touch Piano plugin."""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PianoConfig(models.Model):
    """
    Configuration for the touch piano.
    """

    name = models.CharField(
        max_length=100,
        help_text=_("Name of the piano configuration"),
    )

    description = models.TextField(
        blank=True,
        help_text=_("Description of this piano setup"),
    )

    volume = models.PositiveIntegerField(
        default=80,
        help_text=_("Piano volume (0-100%)"),
    )

    sensitivity = models.PositiveIntegerField(
        default=5,
        help_text=_("Touch sensitivity (1-10, higher = more sensitive)"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this configuration is active"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_touch_piano"
        verbose_name = _("Piano Configuration")
        verbose_name_plural = _("Piano Configurations")
        ordering = ["name"]

    def __str__(self):
        return self.name


class PianoKey(models.Model):
    """
    Individual piano key configuration.
    """

    config = models.ForeignKey(
        PianoConfig,
        on_delete=models.CASCADE,
        related_name="keys",
        help_text=_("Configuration this key belongs to"),
    )

    key_number = models.PositiveIntegerField(
        help_text=_("Key number (1-6)"),
    )

    note = models.CharField(
        max_length=10,
        help_text=_("Musical note (e.g., C4, D4, E4)"),
    )

    frequency = models.FloatField(
        help_text=_("Note frequency in Hz"),
    )

    gpio_pin = models.PositiveIntegerField(
        help_text=_("GPIO pin number (BCM)"),
    )

    label = models.CharField(
        max_length=50,
        blank=True,
        help_text=_("Optional label for the key"),
    )

    color = models.CharField(
        max_length=7,
        default="#3B82F6",
        help_text=_("Hex color code for this key on the web interface"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this key is enabled"),
    )

    class Meta:
        app_label = "edupi_touch_piano"
        verbose_name = _("Piano Key")
        verbose_name_plural = _("Piano Keys")
        ordering = ["key_number"]
        unique_together = ["config", "key_number"]

    def __str__(self):
        return f"Key {self.key_number} ({self.note}) - {self.config.name}"


class PianoSession(models.Model):
    """
    Tracks piano playing sessions.
    """

    config = models.ForeignKey(
        PianoConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        help_text=_("Configuration used for this session"),
    )

    started_at = models.DateTimeField(
        default=timezone.now,
        help_text=_("When the session started"),
    )

    ended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the session ended"),
    )

    total_key_presses = models.PositiveIntegerField(
        default=0,
        help_text=_("Total number of key presses in this session"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this session is currently active"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_touch_piano"
        verbose_name = _("Piano Session")
        verbose_name_plural = _("Piano Sessions")
        ordering = ["-started_at"]

    def __str__(self):
        return f"Session {self.id} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    def end_session(self):
        """End the piano session."""
        self.ended_at = timezone.now()
        self.is_active = False
        self.save()

    def increment_presses(self):
        """Increment the total key press count."""
        self.total_key_presses += 1
        self.save()

    def get_duration(self):
        """Get session duration in seconds."""
        if self.ended_at:
            return (self.ended_at - self.started_at).total_seconds()
        return (timezone.now() - self.started_at).total_seconds()


class KeyPress(models.Model):
    """
    Records individual key presses.
    """

    session = models.ForeignKey(
        PianoSession,
        on_delete=models.CASCADE,
        related_name="key_presses",
        help_text=_("Session this key press belongs to"),
    )

    key = models.ForeignKey(
        PianoKey,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text=_("Key that was pressed"),
    )

    key_number = models.PositiveIntegerField(
        help_text=_("Key number (1-6)"),
    )

    note = models.CharField(
        max_length=10,
        help_text=_("Musical note played"),
    )

    pressed_at = models.DateTimeField(
        default=timezone.now,
        help_text=_("When the key was pressed"),
    )

    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Duration of the press in milliseconds"),
    )

    class Meta:
        app_label = "edupi_touch_piano"
        verbose_name = _("Key Press")
        verbose_name_plural = _("Key Presses")
        ordering = ["-pressed_at"]

    def __str__(self):
        return f"Key {self.key_number} ({self.note}) at {self.pressed_at.strftime('%H:%M:%S')}"
