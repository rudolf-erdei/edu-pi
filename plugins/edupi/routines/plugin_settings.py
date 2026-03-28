"""
Settings configuration for the Routines plugin.

This module defines the plugin settings using the new OctoberCMS-style
settings system with nested sections.
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from core.plugin_system.settings_forms import PluginSettingsForm


class SettingsForm(PluginSettingsForm):
    """
    Manual settings form for the Routines plugin.

    This provides full control over the form layout and field definitions.
    """

    class Meta:
        plugin_name = "edupi.routines"
        sections = {
            "Audio > TTS": [
                "default_tts_engine",
                "default_tts_speed",
                "default_language",
            ],
            "Audio > Playback": [
                "default_volume",
                "enable_audio_fade",
            ],
            "Presenter": [
                "enable_presenter",
                "auto_detect_presenter",
            ],
            "General": [
                "auto_advance_lines",
                "line_delay_seconds",
            ],
        }

    # Audio > TTS Settings
    default_tts_engine = forms.ChoiceField(
        label=_("Default TTS Engine"),
        choices=[
            ("pyttsx3", _("System TTS (Offline)")),
            ("edge_tts", _("Edge TTS (High Quality - Online)")),
            ("gtts", _("Google TTS (Online)")),
        ],
        initial="pyttsx3",
        help_text=_("Select the default text-to-speech engine"),
    )

    default_tts_speed = forms.FloatField(
        label=_("Default TTS Speed"),
        min_value=0.5,
        max_value=2.0,
        initial=1.0,
        help_text=_("Speech speed multiplier (0.5 = slow, 1.0 = normal, 2.0 = fast)"),
    )

    default_language = forms.CharField(
        label=_("Default Language"),
        max_length=10,
        initial="en",
        help_text=_("Default language code (e.g., 'en', 'ro', 'es')"),
    )

    # Audio > Playback Settings
    default_volume = forms.IntegerField(
        label=_("Default Volume"),
        min_value=0,
        max_value=100,
        initial=80,
        help_text=_("Default volume level for audio playback (0-100%)"),
    )

    enable_audio_fade = forms.BooleanField(
        label=_("Enable Audio Fade"),
        initial=True,
        required=False,
        help_text=_("Fade audio in/out at start/end of playback"),
    )

    # Presenter Settings
    enable_presenter = forms.BooleanField(
        label=_("Enable USB Presenter"),
        initial=True,
        required=False,
        help_text=_("Allow control via USB wireless presenter"),
    )

    auto_detect_presenter = forms.BooleanField(
        label=_("Auto-detect Presenter"),
        initial=True,
        required=False,
        help_text=_("Automatically detect presenter when plugged in"),
    )

    # General Settings
    auto_advance_lines = forms.BooleanField(
        label=_("Auto-advance Lines"),
        initial=False,
        required=False,
        help_text=_("Automatically advance to next line after speech completes"),
    )

    line_delay_seconds = forms.FloatField(
        label=_("Line Delay"),
        min_value=0,
        max_value=10,
        initial=0.5,
        help_text=_("Delay in seconds before auto-advancing to next line"),
    )
