"""Django models for Activity Timer plugin."""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class TimerPreset(models.Model):
    """
    Predefined timer presets (e.g., Minute of Silence, Break Time, etc.)
    """

    class PresetType(models.TextChoices):
        MINUTE_OF_SILENCE = "minute_of_silence", _("Minute of Silence")
        BREAK_TIME = "break_time", _("Break Time")
        ACTIVITY = "activity", _("Activity")
        CUSTOM = "custom", _("Custom")

    preset_type = models.CharField(
        max_length=30,
        choices=PresetType.choices,
        default=PresetType.ACTIVITY,
        unique=True,
        help_text=_("Type of timer preset"),
    )

    name = models.CharField(
        max_length=100,
        help_text=_("Display name for this preset"),
    )

    description = models.TextField(
        blank=True,
        help_text=_("Description of when to use this preset"),
    )

    duration_minutes = models.PositiveIntegerField(
        default=10,
        help_text=_("Default duration in minutes"),
    )

    # Color for the built-in display (hex color)
    display_color = models.CharField(
        max_length=7,
        default="#3B82F6",
        help_text=_("Hex color for the preset button/display"),
    )

    # LED colors for physical LED
    led_color_start = models.CharField(
        max_length=7,
        default="#00FF00",
        help_text=_("Hex color code for timer start"),
    )

    led_color_warning = models.CharField(
        max_length=7,
        default="#FFFF00",
        help_text=_("Hex color code for warning state"),
    )

    led_color_end = models.CharField(
        max_length=7,
        default="#FF0000",
        help_text=_("Hex color code for timer end"),
    )

    # Breathing animation for Minute of Silence
    enable_breathing = models.BooleanField(
        default=False,
        help_text=_("Enable breathing circle animation"),
    )

    # Calming audio options
    enable_ambient_sound = models.BooleanField(
        default=False,
        help_text=_("Play ambient background sound"),
    )

    ambient_sound_type = models.CharField(
        max_length=50,
        blank=True,
        choices=[
            ("nature", _("Nature Sounds")),
            ("white_noise", _("White Noise")),
            ("ocean", _("Ocean Waves")),
            ("rain", _("Rain")),
        ],
        help_text=_("Type of ambient sound"),
    )

    # TTS for start/end
    announce_start = models.BooleanField(
        default=False,
        help_text=_("Announce start with TTS"),
    )

    announce_end = models.BooleanField(
        default=False,
        help_text=_("Announce end with TTS"),
    )

    start_message = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text=_("Message to announce at start"),
    )

    end_message = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text=_("Message to announce at end"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this preset is active"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_activity_timer"
        verbose_name = _("Timer Preset")
        verbose_name_plural = _("Timer Presets")
        ordering = ["preset_type"]

    def __str__(self):
        return f"{self.name} ({self.get_preset_type_display()})"


class TimerConfig(models.Model):
    """
    Timer configurations - can be based on presets or custom.
    """

    preset = models.ForeignKey(
        TimerPreset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="configs",
        help_text=_("Base preset for this configuration (optional)"),
    )

    name = models.CharField(
        max_length=100,
        help_text=_("Name of the timer configuration"),
    )

    description = models.TextField(
        blank=True,
        help_text=_("Description of when to use this timer"),
    )

    duration_minutes = models.PositiveIntegerField(
        default=10,
        help_text=_("Duration in minutes"),
    )

    warning_threshold_percent = models.PositiveIntegerField(
        default=20,
        help_text=_("Percentage remaining when warning color appears"),
    )

    enable_buzzer = models.BooleanField(
        default=True,
        help_text=_("Play buzzer sound when timer ends"),
    )

    # Color for the built-in display button
    display_color = models.CharField(
        max_length=7,
        default="#3B82F6",
        help_text=_("Hex color for display button"),
    )

    led_color_start = models.CharField(
        max_length=7,
        default="#00FF00",
        help_text=_("Hex color code for timer start (green)"),
    )

    led_color_warning = models.CharField(
        max_length=7,
        default="#FFFF00",
        help_text=_("Hex color code for warning state (yellow)"),
    )

    led_color_end = models.CharField(
        max_length=7,
        default="#FF0000",
        help_text=_("Hex color code for timer end (red)"),
    )

    # Minute of Silence specific features
    enable_breathing = models.BooleanField(
        default=False,
        help_text=_("Enable breathing circle animation"),
    )

    enable_ambient_sound = models.BooleanField(
        default=False,
        help_text=_("Play ambient background sound"),
    )

    is_default = models.BooleanField(
        default=False,
        help_text=_("Use this as the default configuration"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this configuration is active"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_activity_timer"
        verbose_name = _("Timer Configuration")
        verbose_name_plural = _("Timer Configurations")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.duration_minutes} min)"

    def save(self, *args, **kwargs):
        # Ensure only one default config exists
        if self.is_default:
            TimerConfig.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def get_duration_seconds(self):
        """Get duration in seconds."""
        return self.duration_minutes * 60


class TimerSession(models.Model):
    """
    Tracks individual timer sessions.
    """

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RUNNING = "running", _("Running")
        PAUSED = "paused", _("Paused")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")

    config = models.ForeignKey(
        TimerConfig,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
        help_text=_("Configuration used for this session"),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_("Current status of the timer"),
    )

    duration_seconds = models.PositiveIntegerField(
        help_text=_("Total duration in seconds"),
    )

    remaining_seconds = models.PositiveIntegerField(
        help_text=_("Remaining time in seconds"),
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the timer was started"),
    )

    paused_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the timer was last paused"),
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the timer completed"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_activity_timer"
        verbose_name = _("Timer Session")
        verbose_name_plural = _("Timer Sessions")
        ordering = ["-created_at"]

    def __str__(self):
        return f"Timer {self.id} - {self.get_status_display()}"

    def start(self):
        """Start the timer."""
        self.status = self.Status.RUNNING
        self.started_at = timezone.now()
        self.save()

    def pause(self):
        """Pause the timer."""
        if self.status == self.Status.RUNNING:
            self.status = self.Status.PAUSED
            self.paused_at = timezone.now()
            self.save()

    def resume(self):
        """Resume the timer from pause."""
        if self.status == self.Status.PAUSED:
            self.status = self.Status.RUNNING
            self.paused_at = None
            self.save()

    def complete(self):
        """Mark timer as completed."""
        self.status = self.Status.COMPLETED
        self.remaining_seconds = 0
        self.completed_at = timezone.now()
        self.save()

    def cancel(self):
        """Cancel the timer."""
        self.status = self.Status.CANCELLED
        self.save()

    def get_progress_percent(self):
        """Get timer progress as percentage (0-100)."""
        if self.duration_seconds == 0:
            return 100
        elapsed = self.duration_seconds - self.remaining_seconds
        return int((elapsed / self.duration_seconds) * 100)

    def get_remaining_display(self):
        """Get remaining time as formatted string (MM:SS)."""
        minutes = self.remaining_seconds // 60
        seconds = self.remaining_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def is_running(self):
        """Check if timer is currently running."""
        return self.status == self.Status.RUNNING

    def is_paused(self):
        """Check if timer is paused."""
        return self.status == self.Status.PAUSED

    def get_current_color(self):
        """Get the current LED color based on progress."""
        if not self.config:
            return "#808080"  # Gray

        progress = self.get_progress_percent()
        remaining_percent = 100 - progress

        if remaining_percent <= 0:
            return self.config.led_color_end
        elif remaining_percent <= self.config.warning_threshold_percent:
            return self.config.led_color_warning
        else:
            return self.config.led_color_start
