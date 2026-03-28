"""
Settings configuration for the Activity Timer plugin.

This module defines the plugin settings using the new OctoberCMS-style
settings system with nested sections.
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from core.plugin_system.settings_forms import PluginSettingsForm


class SettingsForm(PluginSettingsForm):
    """
    Manual settings form for the Activity Timer plugin.

    This provides full control over the form layout and field definitions.
    """

    class Meta:
        plugin_name = "edupi.activity_timer"
        sections = {
            "Defaults": [
                "default_duration",
                "warning_threshold",
            ],
            "LED Configuration": [
                "led_brightness",
                "led_color_start",
                "led_color_warning",
                "led_color_end",
            ],
            "Audio": [
                "enable_buzzer",
                "buzzer_volume",
                "enable_tts",
            ],
            "General": [
                "auto_start_timer",
                "show_remaining_time",
            ],
        }

    # Defaults
    default_duration = forms.IntegerField(
        label=_("Default Duration (minutes)"),
        min_value=1,
        max_value=120,
        initial=10,
        help_text=_("Default timer duration in minutes"),
    )

    warning_threshold = forms.IntegerField(
        label=_("Warning Threshold (%)"),
        min_value=5,
        max_value=50,
        initial=20,
        help_text=_("Percentage of time remaining when warning triggers"),
    )

    # LED Configuration
    led_brightness = forms.IntegerField(
        label=_("LED Brightness (%)"),
        min_value=10,
        max_value=100,
        initial=100,
        help_text=_("Brightness level for timer LED (10-100%)"),
    )

    led_color_start = forms.CharField(
        label=_("Start Color"),
        max_length=7,
        initial="#00FF00",
        help_text=_("LED color at timer start (hex format, e.g., #00FF00)"),
    )

    led_color_warning = forms.CharField(
        label=_("Warning Color"),
        max_length=7,
        initial="#FFFF00",
        help_text=_("LED color at warning threshold (hex format, e.g., #FFFF00)"),
    )

    led_color_end = forms.CharField(
        label=_("End Color"),
        max_length=7,
        initial="#FF0000",
        help_text=_("LED color when timer ends (hex format, e.g., #FF0000)"),
    )

    # Audio
    enable_buzzer = forms.BooleanField(
        label=_("Enable Buzzer"),
        initial=True,
        required=False,
        help_text=_("Play sound when timer completes"),
    )

    buzzer_volume = forms.IntegerField(
        label=_("Buzzer Volume (%)"),
        min_value=0,
        max_value=100,
        initial=80,
        help_text=_("Volume level for buzzer sound"),
    )

    enable_tts = forms.BooleanField(
        label=_("Enable TTS Announcements"),
        initial=False,
        required=False,
        help_text=_("Speak timer announcements using text-to-speech"),
    )

    # General
    auto_start_timer = forms.BooleanField(
        label=_("Auto-start Timer"),
        initial=False,
        required=False,
        help_text=_("Automatically start timer when preset is selected"),
    )

    show_remaining_time = forms.BooleanField(
        label=_("Show Remaining Time"),
        initial=True,
        required=False,
        help_text=_("Display remaining time on LED between minutes"),
    )
