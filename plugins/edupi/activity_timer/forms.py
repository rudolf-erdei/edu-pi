"""Django forms for Activity Timer plugin."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import TimerConfig


class TimerConfigForm(forms.ModelForm):
    """Form for creating/editing timer configurations."""

    class Meta:
        model = TimerConfig
        fields = [
            "name",
            "description",
            "duration_minutes",
            "warning_threshold_percent",
            "enable_buzzer",
            "led_color_start",
            "led_color_warning",
            "led_color_end",
            "is_default",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": _("e.g., Test Timer"),
                }
            ),
            "description": forms.Textarea(
                attrs={"class": "textarea textarea-bordered w-full", "rows": 3}
            ),
            "duration_minutes": forms.NumberInput(
                attrs={"class": "input input-bordered w-full", "min": 1, "max": 120}
            ),
            "warning_threshold_percent": forms.NumberInput(
                attrs={"class": "input input-bordered w-full", "min": 5, "max": 50}
            ),
            "led_color_start": forms.TextInput(
                attrs={"class": "input input-bordered w-full", "type": "color"}
            ),
            "led_color_warning": forms.TextInput(
                attrs={"class": "input input-bordered w-full", "type": "color"}
            ),
            "led_color_end": forms.TextInput(
                attrs={"class": "input input-bordered w-full", "type": "color"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = _("Timer Name")
        self.fields["description"].label = _("Description")
        self.fields["duration_minutes"].label = _("Duration (minutes)")
        self.fields["warning_threshold_percent"].label = _("Warning Threshold (%)")
        self.fields["enable_buzzer"].label = _("Enable Buzzer")
        self.fields["led_color_start"].label = _("Start Color (Green)")
        self.fields["led_color_warning"].label = _("Warning Color (Yellow)")
        self.fields["led_color_end"].label = _("End Color (Red)")
        self.fields["is_default"].label = _("Set as Default")
        self.fields["is_active"].label = _("Active")


class QuickTimerForm(forms.Form):
    """Quick timer creation form."""

    duration_minutes = forms.IntegerField(
        min_value=1,
        max_value=120,
        initial=10,
        label=_("Duration (minutes)"),
        widget=forms.NumberInput(
            attrs={"class": "input input-bordered w-full", "min": 1, "max": 120}
        ),
    )

    use_buzzer = forms.BooleanField(
        initial=True,
        required=False,
        label=_("Enable Buzzer"),
        widget=forms.CheckboxInput(attrs={"class": "checkbox"}),
    )


class TimerControlForm(forms.Form):
    """Form for controlling timer actions."""

    action = forms.ChoiceField(
        choices=[
            ("start", _("Start")),
            ("pause", _("Pause")),
            ("resume", _("Resume")),
            ("stop", _("Stop")),
        ],
        widget=forms.HiddenInput(),
    )

    config_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )
