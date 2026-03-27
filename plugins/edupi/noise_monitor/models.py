"""Django models for Noise Monitor plugin."""

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class NoiseProfile(models.Model):
    """
    Predefined noise threshold profiles for different classroom activities.
    """

    class ProfileType(models.TextChoices):
        TEST = "test", _("Test - Silent Mode")
        TEACHING = "teaching", _("Teaching - Moderate Noise")
        GROUP_WORK = "group_work", _("Group Work - Higher Tolerance")
        CUSTOM = "custom", _("Custom - User Defined")

    profile_type = models.CharField(
        max_length=20,
        choices=ProfileType.choices,
        default=ProfileType.TEACHING,
        unique=True,
        help_text=_("Type of noise profile"),
    )

    name = models.CharField(
        max_length=100,
        help_text=_("Display name for this profile"),
    )

    description = models.TextField(
        blank=True,
        help_text=_("Description of when to use this profile"),
    )

    # Threshold levels (in dB or normalized 0-100)
    # Green: Low noise (quiet work)
    yellow_threshold = models.PositiveIntegerField(
        default=40,
        help_text=_("Noise level above which LED turns yellow (0-100)"),
    )

    red_threshold = models.PositiveIntegerField(
        default=70,
        help_text=_("Noise level above which LED turns red (0-100)"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this profile is active"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_noise_monitor"
        verbose_name = _("Noise Profile")
        verbose_name_plural = _("Noise Profiles")
        ordering = ["profile_type"]

    def __str__(self):
        return f"{self.name} ({self.get_profile_type_display()})"

    def get_color_for_level(self, level):
        """
        Get the color for a given noise level.

        Returns:
            str: 'green', 'yellow', or 'red'
        """
        if level >= self.red_threshold:
            return "red"
        elif level >= self.yellow_threshold:
            return "yellow"
        else:
            return "green"


class NoiseMonitorConfig(models.Model):
    """
    Configuration for the noise monitor session.
    """

    name = models.CharField(
        max_length=100,
        default="Default Configuration",
        help_text=_("Name of this configuration"),
    )

    profile = models.ForeignKey(
        NoiseProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="configs",
        help_text=_("Noise profile to use"),
    )

    instant_window_seconds = models.PositiveIntegerField(
        default=10,
        help_text=_("Window size for instant average in seconds"),
    )

    session_window_minutes = models.PositiveIntegerField(
        default=5,
        help_text=_("Window size for session average in minutes"),
    )

    led_brightness = models.PositiveIntegerField(
        default=100,
        help_text=_("LED brightness percentage (10-100)"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this configuration is active"),
    )

    is_default = models.BooleanField(
        default=False,
        help_text=_("Use this as the default configuration"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_noise_monitor"
        verbose_name = _("Noise Monitor Configuration")
        verbose_name_plural = _("Noise Monitor Configurations")
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one default config exists
        if self.is_default:
            NoiseMonitorConfig.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    def get_session_window_seconds(self):
        """Get session window in seconds."""
        return self.session_window_minutes * 60


class NoiseReading(models.Model):
    """
    Stores individual noise level readings.
    """

    config = models.ForeignKey(
        NoiseMonitorConfig,
        on_delete=models.CASCADE,
        related_name="readings",
        help_text=_("Configuration during this reading"),
    )

    # Raw noise level (0-100 normalized)
    raw_level = models.PositiveIntegerField(
        help_text=_("Raw noise level (0-100)"),
    )

    # Instant average (over 10-second window)
    instant_average = models.PositiveIntegerField(
        help_text=_("Instant average noise level (0-100)"),
    )

    # Session average (over 5-10 minute window)
    session_average = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Session average noise level (0-100)"),
    )

    # Instant LED color
    instant_color = models.CharField(
        max_length=10,
        default="green",
        help_text=_("Color of instant LED (green/yellow/red)"),
    )

    # Session LED color
    session_color = models.CharField(
        max_length=10,
        default="green",
        help_text=_("Color of session LED (green/yellow/red)"),
    )

    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text=_("When this reading was taken"),
    )

    class Meta:
        app_label = "edupi_noise_monitor"
        verbose_name = _("Noise Reading")
        verbose_name_plural = _("Noise Readings")
        ordering = ["-timestamp"]

    def __str__(self):
        return f"Reading at {self.timestamp.strftime('%H:%M:%S')} - Instant: {self.instant_average}"

    def get_instant_color_display(self):
        """Get display color for instant LED."""
        color_map = {
            "green": "#00FF00",
            "yellow": "#FFFF00",
            "red": "#FF0000",
        }
        return color_map.get(self.instant_color, "#808080")

    def get_session_color_display(self):
        """Get display color for session LED."""
        color_map = {
            "green": "#00FF00",
            "yellow": "#FFFF00",
            "red": "#FF0000",
        }
        return color_map.get(self.session_color, "#808080")
