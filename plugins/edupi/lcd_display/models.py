"""Models for LCD Display plugin."""

from django.db import models
from django.utils.translation import gettext as _


class LCDConfig(models.Model):
    """Configuration for the LCD display."""

    class Rotation(models.IntegerChoices):
        """Display rotation options."""

        ROTATION_0 = 0, _("0 degrees")
        ROTATION_90 = 90, _("90 degrees")
        ROTATION_180 = 180, _("180 degrees")
        ROTATION_270 = 270, _("270 degrees")

    name = models.CharField(max_length=100, default="Default")
    rotation = models.IntegerField(
        choices=Rotation.choices,
        default=Rotation.ROTATION_0,
        help_text=_("Display rotation"),
    )
    backlight = models.IntegerField(
        default=100,
        help_text=_("Backlight brightness (0-100%)"),
    )
    contrast = models.FloatField(
        default=1.0,
        help_text=_("Display contrast (0.5-2.0)"),
    )
    show_smile_on_startup = models.BooleanField(
        default=True,
        help_text=_("Show smiling face on startup"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("LCD Configuration")
        verbose_name_plural = _("LCD Configurations")

    def __str__(self):
        return f"{self.name} ({self.rotation}°)"


class DisplaySession(models.Model):
    """Track display sessions."""

    class DisplayMode(models.TextChoices):
        """Display mode options."""

        SMILE = "smile", _("Smiling Face")
        TEXT = "text", _("Text Message")
        IMAGE = "image", _("Custom Image")
        CLEAR = "clear", _("Clear Screen")

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    mode = models.CharField(
        max_length=20,
        choices=DisplayMode.choices,
        default=DisplayMode.SMILE,
    )
    content = models.TextField(
        blank=True,
        help_text=_("Content displayed (text or image path)"),
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Display Session")
        verbose_name_plural = _("Display Sessions")
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.mode} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    def end_session(self):
        """Mark the session as ended."""
        from django.utils import timezone

        self.ended_at = timezone.now()
        self.is_active = False
        self.save()
