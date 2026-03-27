"""Django forms for Touch Piano plugin."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import PianoConfig, PianoKey


class PianoConfigForm(forms.ModelForm):
    """Form for creating/editing piano configurations."""

    class Meta:
        model = PianoConfig
        fields = [
            "name",
            "description",
            "volume",
            "sensitivity",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": _("e.g., Classroom Piano"),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "textarea textarea-bordered w-full",
                    "rows": 3,
                    "placeholder": _("Description of this piano setup"),
                }
            ),
            "volume": forms.NumberInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "min": 0,
                    "max": 100,
                    "type": "range",
                }
            ),
            "sensitivity": forms.NumberInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "min": 1,
                    "max": 10,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].label = _("Configuration Name")
        self.fields["description"].label = _("Description")
        self.fields["volume"].label = _("Volume (%)")
        self.fields["sensitivity"].label = _("Touch Sensitivity")
        self.fields["is_active"].label = _("Active")


class PianoKeyForm(forms.ModelForm):
    """Form for editing individual piano keys."""

    class Meta:
        model = PianoKey
        fields = [
            "note",
            "frequency",
            "label",
            "color",
            "is_active",
        ]
        widgets = {
            "note": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": _("e.g., C4"),
                }
            ),
            "frequency": forms.NumberInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "step": "0.1",
                }
            ),
            "label": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": _("Optional label"),
                }
            ),
            "color": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "type": "color",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["note"].label = _("Musical Note")
        self.fields["frequency"].label = _("Frequency (Hz)")
        self.fields["label"].label = _("Label (Optional)")
        self.fields["color"].label = _("Key Color")
        self.fields["is_active"].label = _("Enabled")


class QuickPlayForm(forms.Form):
    """Quick play form for starting a piano session."""

    config_id = forms.ModelChoiceField(
        queryset=PianoConfig.objects.filter(is_active=True),
        label=_("Piano Configuration"),
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["config_id"].empty_label = _("Use Default Configuration")
