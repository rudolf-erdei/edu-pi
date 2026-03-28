"""
Settings configuration for the Touch Piano plugin.

This module defines the plugin settings using the new OctoberCMS-style
settings system with nested sections.
"""

from django import forms
from django.utils.translation import gettext_lazy as _

from core.plugin_system.settings_forms import PluginSettingsForm


class SettingsForm(PluginSettingsForm):
    """
    Manual settings form for the Touch Piano plugin.

    This provides full control over the form layout and field definitions.
    """

    class Meta:
        plugin_name = "edupi.touch_piano"
        sections = {
            "Audio": [
                "volume",
                "audio_device",
            ],
            "Touch Sensing": [
                "sensitivity",
                "debounce_ms",
            ],
            "Visual Feedback": [
                "enable_visual_feedback",
                "show_key_labels",
            ],
            "General": [
                "auto_play_demo",
                "demo_interval_minutes",
            ],
        }

    # Audio Settings
    volume = forms.IntegerField(
        label=_("Piano Volume (%)"),
        min_value=0,
        max_value=100,
        initial=80,
        help_text=_("Master volume for piano sounds (0-100%)"),
    )

    audio_device = forms.CharField(
        label=_("Audio Output Device"),
        max_length=100,
        initial="default",
        help_text=_("ALSA audio device (e.g., default, hw:0,0, or plughw:1,0)"),
    )

    # Touch Sensing Settings
    sensitivity = forms.IntegerField(
        label=_("Touch Sensitivity"),
        min_value=1,
        max_value=10,
        initial=5,
        help_text=_("Higher values = more sensitive touch detection"),
    )

    debounce_ms = forms.IntegerField(
        label=_("Debounce Time (ms)"),
        min_value=10,
        max_value=500,
        initial=50,
        help_text=_("Time in milliseconds to debounce touch signals"),
    )

    # Visual Feedback Settings
    enable_visual_feedback = forms.BooleanField(
        label=_("Enable Visual Feedback"),
        initial=True,
        required=False,
        help_text=_("Show key presses on web interface in real-time"),
    )

    show_key_labels = forms.BooleanField(
        label=_("Show Key Labels"),
        initial=True,
        required=False,
        help_text=_("Display note names on piano keys"),
    )

    # General Settings
    auto_play_demo = forms.BooleanField(
        label=_("Auto-play Demo"),
        initial=False,
        required=False,
        help_text=_("Play demo song when no activity detected"),
    )

    demo_interval_minutes = forms.IntegerField(
        label=_("Demo Interval (minutes)"),
        min_value=1,
        max_value=60,
        initial=5,
        help_text=_("Minutes of inactivity before playing demo"),
    )
