"""Django forms for Activity Timer plugin."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import TimerConfig


class TimerConfigForm(forms.ModelForm):
    """Form for creating/editing timer configurations."""

    class Meta:
        model = TimerConfig
        fields = [
            "preset",
            "name",
            "description",
            "duration_minutes",
            "warning_threshold_percent",
            "enable_buzzer",
            "display_color",
            "led_color_start",
            "led_color_warning",
            "led_color_end",
            "enable_breathing",
            "enable_ambient_sound",
            "is_default",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "e.g., Test Timer",
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
            "display_color": forms.TextInput(
                attrs={"class": "input input-bordered w-full", "type": "color"}
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
            "enable_breathing": forms.CheckboxInput(attrs={"class": "checkbox"}),
            "enable_ambient_sound": forms.CheckboxInput(attrs={"class": "checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import TimerPreset

        self.fields["preset"].label = "Base Preset (optional)"
        self.fields["preset"].queryset = TimerPreset.objects.filter(is_active=True)
        self.fields["preset"].required = False
        self.fields["name"].label = "Timer Name"
        self.fields["description"].label = "Description"
        self.fields["duration_minutes"].label = "Duration (minutes)"
        self.fields["warning_threshold_percent"].label = "Warning Threshold (%)"
        self.fields["enable_buzzer"].label = "Enable Buzzer"
        self.fields["display_color"].label = "Display Color"
        self.fields["led_color_start"].label = "Start Color (Green)"
        self.fields["led_color_warning"].label = "Warning Color (Yellow)"
        self.fields["led_color_end"].label = "End Color (Red)"
        self.fields["enable_breathing"].label = "Enable Breathing Animation"
        self.fields["enable_ambient_sound"].label = "Enable Ambient Sound"
        self.fields["is_default"].label = "Set as Default"
        self.fields["is_active"].label = "Active"

    def save(self, commit=True):
        instance = super().save(commit=False)

        # If a preset is selected, copy its values
        if instance.preset:
            preset = instance.preset
            if not instance.name or instance.name.strip() == "":
                instance.name = preset.name
            if not instance.description or instance.description.strip() == "":
                instance.description = preset.description
            instance.led_color_start = preset.led_color_start
            instance.led_color_warning = preset.led_color_warning
            instance.led_color_end = preset.led_color_end
            instance.enable_breathing = preset.enable_breathing
            instance.enable_ambient_sound = preset.enable_ambient_sound

        if commit:
            instance.save()
        return instance


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
