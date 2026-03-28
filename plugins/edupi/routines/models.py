"""Django models for Routines plugin."""

import os
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


def routine_audio_path(instance, filename):
    """Generate path for routine audio files."""
    return f"routines/audio/{instance.id}/{filename}"


class RoutineCategory(models.Model):
    """Categories for organizing routines (warm-up, transition, cooldown)."""

    class CategoryType(models.TextChoices):
        WARM_UP = "warm_up", _("Warm-up")
        TRANSITION = "transition", _("Transition")
        COOLDOWN = "cooldown", _("Cooldown")
        CUSTOM = "custom", _("Custom")

    category_type = models.CharField(
        max_length=20,
        choices=CategoryType.choices,
        default=CategoryType.CUSTOM,
        unique=True,
        help_text=_("Type of routine category"),
    )

    name = models.CharField(
        max_length=100,
        help_text=_("Display name for this category"),
    )

    description = models.TextField(
        blank=True,
        help_text=_("Description of this category"),
    )

    display_color = models.CharField(
        max_length=7,
        default="#3B82F6",
        help_text=_("Hex color for this category"),
    )

    order = models.PositiveIntegerField(
        default=0,
        help_text=_("Display order (lower numbers first)"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this category is active"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_routines"
        verbose_name = _("Routine Category")
        verbose_name_plural = _("Routine Categories")
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Routine(models.Model):
    """A classroom routine with text content and optional audio."""

    class TTSEngine(models.TextChoices):
        PYTTSX3 = "pyttsx3", _("System TTS (Offline)")
        EDGE_TTS = "edge_tts", _("Edge TTS (High Quality)")
        GTTS = "gtts", _("Google TTS (Online)")
        NONE = "none", _("Use Uploaded Audio")

    title = models.CharField(
        max_length=200,
        help_text=_("Title of the routine"),
    )

    content = models.TextField(
        help_text=_("Routine text content (one line per instruction)"),
    )

    category = models.ForeignKey(
        RoutineCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routines",
        help_text=_("Category this routine belongs to"),
    )

    # Audio file upload (optional, overrides TTS)
    audio_file = models.FileField(
        upload_to=routine_audio_path,
        blank=True,
        null=True,
        help_text=_("Upload MP3/WAV file (optional, overrides TTS)"),
    )

    # TTS Configuration
    tts_engine = models.CharField(
        max_length=20,
        choices=TTSEngine.choices,
        default=TTSEngine.PYTTSX3,
        help_text=_("Text-to-speech engine to use"),
    )

    tts_speed = models.FloatField(
        default=1.0,
        help_text=_("TTS speed multiplier (0.5 = slow, 2.0 = fast)"),
    )

    tts_voice = models.CharField(
        max_length=100,
        blank=True,
        help_text=_("Voice name (engine-specific)"),
    )

    tts_language = models.CharField(
        max_length=10,
        default="en",
        help_text=_("Language code (e.g., 'en', 'ro', 'es')"),
    )

    # Whether this is a pre-built routine
    is_pre_built = models.BooleanField(
        default=False,
        help_text=_("Whether this is a built-in routine"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this routine is active"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_routines"
        verbose_name = _("Routine")
        verbose_name_plural = _("Routines")
        ordering = ["-is_pre_built", "category__order", "title"]

    def __str__(self):
        return self.title

    def get_lines(self):
        """Split content into individual lines."""
        if not self.content:
            return []
        return [line.strip() for line in self.content.split("\n") if line.strip()]

    def get_line_count(self):
        """Get total number of lines."""
        return len(self.get_lines())

    def has_custom_audio(self):
        """Check if routine has uploaded audio file."""
        return bool(self.audio_file) and os.path.exists(self.audio_file.path)

    def get_audio_source(self):
        """Get the audio source type."""
        if self.has_custom_audio():
            return "uploaded"
        return self.tts_engine


class RoutineSession(models.Model):
    """Tracks individual routine playback sessions."""

    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        PLAYING = "playing", _("Playing")
        PAUSED = "paused", _("Paused")
        COMPLETED = "completed", _("Completed")
        STOPPED = "stopped", _("Stopped")

    routine = models.ForeignKey(
        Routine,
        on_delete=models.CASCADE,
        related_name="sessions",
        help_text=_("Routine being played"),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text=_("Current playback status"),
    )

    current_line_index = models.PositiveIntegerField(
        default=0,
        help_text=_("Current line being played (0-based)"),
    )

    started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the routine started"),
    )

    paused_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the routine was last paused"),
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When the routine completed"),
    )

    total_duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("Total duration in seconds"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_routines"
        verbose_name = _("Routine Session")
        verbose_name_plural = _("Routine Sessions")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.routine.title} - {self.get_status_display()}"

    def start(self):
        """Start the routine session."""
        self.status = self.Status.PLAYING
        self.started_at = timezone.now()
        self.current_line_index = 0
        self.save()

    def pause(self):
        """Pause the routine session."""
        if self.status == self.Status.PLAYING:
            self.status = self.Status.PAUSED
            self.paused_at = timezone.now()
            self.save()

    def resume(self):
        """Resume the routine session."""
        if self.status == self.Status.PAUSED:
            self.status = self.Status.PLAYING
            self.paused_at = None
            self.save()

    def stop(self):
        """Stop the routine session."""
        self.status = self.Status.STOPPED
        self.save()

    def complete(self):
        """Mark the routine session as completed."""
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        if self.started_at:
            duration = (self.completed_at - self.started_at).total_seconds()
            self.total_duration_seconds = int(duration)
        self.save()

    def next_line(self):
        """Advance to next line."""
        total_lines = self.routine.get_line_count()
        if self.current_line_index < total_lines - 1:
            self.current_line_index += 1
            self.save()
            return True
        return False

    def prev_line(self):
        """Go back to previous line."""
        if self.current_line_index > 0:
            self.current_line_index -= 1
            self.save()
            return True
        return False

    def get_current_line(self):
        """Get the current line text."""
        lines = self.routine.get_lines()
        if 0 <= self.current_line_index < len(lines):
            return lines[self.current_line_index]
        return ""

    def get_progress_percent(self):
        """Get playback progress as percentage."""
        total_lines = self.routine.get_line_count()
        if total_lines == 0:
            return 100
        return int((self.current_line_index / total_lines) * 100)

    def is_playing(self):
        """Check if routine is currently playing."""
        return self.status == self.Status.PLAYING

    def is_paused(self):
        """Check if routine is paused."""
        return self.status == self.Status.PAUSED


class PresenterButtonMapping(models.Model):
    """Configuration for USB presenter button mappings."""

    name = models.CharField(
        max_length=50,
        default="Default",
        help_text=_("Name of this button mapping configuration"),
    )

    # Button codes (evdev event codes)
    next_button_code = models.PositiveIntegerField(
        default=115,  # KEY_VOLUMEUP or common next
        help_text=_("Event code for Next button"),
    )

    prev_button_code = models.PositiveIntegerField(
        default=114,  # KEY_VOLUMEDOWN or common prev
        help_text=_("Event code for Previous button"),
    )

    play_pause_button_code = models.PositiveIntegerField(
        default=164,  # KEY_PLAYPAUSE
        help_text=_("Event code for Play/Pause button"),
    )

    stop_button_code = models.PositiveIntegerField(
        default=116,  # KEY_POWER or black screen
        help_text=_("Event code for Stop button"),
    )

    is_default = models.BooleanField(
        default=False,
        help_text=_("Use this as the default mapping"),
    )

    is_active = models.BooleanField(
        default=True,
        help_text=_("Whether this mapping is active"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "edupi_routines"
        verbose_name = _("Presenter Button Mapping")
        verbose_name_plural = _("Presenter Button Mappings")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Ensure only one default mapping exists
        if self.is_default:
            PresenterButtonMapping.objects.filter(is_default=True).update(
                is_default=False
            )
        super().save(*args, **kwargs)
