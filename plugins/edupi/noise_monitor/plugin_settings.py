"""
Settings configuration for the Noise Monitor plugin.

This module defines the plugin settings using the new OctoberCMS-style
settings system with nested sections.
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from core.plugin_system.settings_forms import PluginSettingsForm


class SettingsForm(PluginSettingsForm):
    """
    Manual settings form for the Noise Monitor plugin.

    This provides full control over the form layout and field definitions.
    """

    class Meta:
        plugin_name = "edupi.noise_monitor"
        sections = {
            "Timing": [
                "instant_window_seconds",
                "session_window_minutes",
            ],
            "LED Configuration": [
                "led_brightness",
                "led_fade_duration",
            ],
            "Thresholds": [
                "yellow_threshold_percent",
                "red_threshold_percent",
            ],
            "General": [
                "enable_monitoring",
                "log_readings",
            ],
        }

    # Timing Settings
    instant_window_seconds = forms.IntegerField(
        label=_("Instant Average Window (seconds)"),
        min_value=5,
        max_value=60,
        initial=10,
        help_text=_("Time window for instant noise average calculation"),
    )

    session_window_minutes = forms.IntegerField(
        label=_("Session Average Window (minutes)"),
        min_value=1,
        max_value=30,
        initial=5,
        help_text=_("Time window for session noise average calculation"),
    )

    # LED Configuration Settings
    led_brightness = forms.IntegerField(
        label=_("LED Brightness (%)"),
        min_value=10,
        max_value=100,
        initial=100,
        help_text=_("Brightness level for RGB LEDs (10-100%)"),
    )

    led_fade_duration = forms.FloatField(
        label=_("LED Fade Duration (seconds)"),
        min_value=0,
        max_value=2,
        initial=0.3,
        help_text=_("Duration of LED color transitions"),
    )

    # Threshold Settings
    yellow_threshold_percent = forms.IntegerField(
        label=_("Yellow Threshold (%)"),
        min_value=10,
        max_value=90,
        initial=40,
        help_text=_("Noise level percentage that triggers yellow warning"),
    )

    red_threshold_percent = forms.IntegerField(
        label=_("Red Threshold (%)"),
        min_value=20,
        max_value=100,
        initial=70,
        help_text=_("Noise level percentage that triggers red alert"),
    )

    # General Settings
    enable_monitoring = forms.BooleanField(
        label=_("Enable Noise Monitoring"),
        initial=True,
        required=False,
        help_text=_("Start monitoring when plugin is enabled"),
    )

    log_readings = forms.BooleanField(
        label=_("Log Readings"),
        initial=True,
        required=False,
        help_text=_("Store noise readings in database for historical view"),
    )
