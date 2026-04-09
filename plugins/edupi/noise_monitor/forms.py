"""Forms for Noise Monitor plugin."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import NoiseProfile, NoiseMonitorConfig


class ProfileSelectForm(forms.Form):
    """Form for selecting a noise profile."""

    profile = forms.ModelChoiceField(
        queryset=NoiseProfile.objects.filter(is_active=True),
        label=_("Select Profile"),
        help_text=_("Choose a predefined noise threshold profile"),
        empty_label=None,
    )

    instant_window_seconds = forms.IntegerField(
        min_value=5,
        max_value=60,
        initial=10,
        label=_("Instant Window (seconds)"),
        help_text=_("Time window for instant average calculation"),
    )

    session_window_minutes = forms.IntegerField(
        min_value=1,
        max_value=30,
        initial=5,
        label=_("Session Window (minutes)"),
        help_text=_("Time window for session average calculation"),
    )

    led_brightness = forms.IntegerField(
        min_value=10,
        max_value=100,
        initial=100,
        label=_("LED Brightness (%)"),
        help_text=_("Brightness percentage for RGB LEDs"),
    )

    audio_input_device = forms.CharField(
        required=False,
        max_length=255,
        label=_("Audio Input Device"),
        help_text=_("Select the microphone device to use"),
        widget=forms.TextInput(attrs={'readonly': True, 'id': 'audio-device-name'}),
    )

    audio_input_device_index = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'audio-device-index'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Order profiles by type
        self.fields["profile"].queryset = NoiseProfile.objects.filter(
            is_active=True
        ).order_by("profile_type")


class CustomThresholdForm(forms.Form):
    """Form for custom noise thresholds."""

    name = forms.CharField(
        max_length=100,
        label=_("Configuration Name"),
        help_text=_("Name for this custom configuration"),
        initial=_("Custom Configuration"),
    )

    yellow_threshold = forms.IntegerField(
        min_value=0,
        max_value=100,
        initial=40,
        label=_("Yellow Threshold"),
        help_text=_("Noise level above which LED turns yellow (0-100)"),
    )

    red_threshold = forms.IntegerField(
        min_value=0,
        max_value=100,
        initial=70,
        label=_("Red Threshold"),
        help_text=_("Noise level above which LED turns red (0-100)"),
    )

    instant_window_seconds = forms.IntegerField(
        min_value=5,
        max_value=60,
        initial=10,
        label=_("Instant Window (seconds)"),
        help_text=_("Time window for instant average calculation"),
    )

    session_window_minutes = forms.IntegerField(
        min_value=1,
        max_value=30,
        initial=5,
        label=_("Session Window (minutes)"),
        help_text=_("Time window for session average calculation"),
    )

    led_brightness = forms.IntegerField(
        min_value=10,
        max_value=100,
        initial=100,
        label=_("LED Brightness (%)"),
        help_text=_("Brightness percentage for RGB LEDs"),
    )

    audio_input_device = forms.CharField(
        required=False,
        max_length=255,
        label=_("Audio Input Device"),
        help_text=_("Select the microphone device to use"),
        widget=forms.TextInput(attrs={'readonly': True, 'id': 'audio-device-name'}),
    )

    audio_input_device_index = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'audio-device-index'}),
    )

    def clean(self):
        """Validate that yellow threshold is less than red threshold."""
        cleaned_data = super().clean()
        yellow = cleaned_data.get("yellow_threshold")
        red = cleaned_data.get("red_threshold")

        if yellow is not None and red is not None and yellow >= red:
            raise forms.ValidationError(
                _("Yellow threshold must be less than red threshold.")
            )

        return cleaned_data


class NoiseMonitorControlForm(forms.Form):
    """Form for controlling noise monitoring."""

    action = forms.ChoiceField(
        choices=[
            ("start", _("Start Monitoring")),
            ("stop", _("Stop Monitoring")),
            ("reset", _("Reset Session")),
        ],
        label=_("Action"),
    )
