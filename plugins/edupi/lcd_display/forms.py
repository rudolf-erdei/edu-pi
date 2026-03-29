"""Forms for LCD Display plugin."""

from django import forms
from django.utils.translation import gettext as _

from .models import LCDConfig


class LCDConfigForm(forms.ModelForm):
    """Form for configuring LCD display settings."""

    class Meta:
        model = LCDConfig
        fields = ["rotation", "backlight", "contrast", "show_smile_on_startup"]
        widgets = {
            "rotation": forms.Select(choices=LCDConfig.Rotation.choices),
            "backlight": forms.NumberInput(attrs={"min": 0, "max": 100, "step": 1}),
            "contrast": forms.NumberInput(attrs={"min": 0.5, "max": 2.0, "step": 0.1}),
            "show_smile_on_startup": forms.CheckboxInput(),
        }

    def clean_backlight(self):
        """Validate backlight value."""
        backlight = self.cleaned_data.get("backlight")
        if backlight is not None:
            return max(0, min(100, backlight))
        return 100

    def clean_contrast(self):
        """Validate contrast value."""
        contrast = self.cleaned_data.get("contrast")
        if contrast is not None:
            return max(0.5, min(2.0, contrast))
        return 1.0


class ShowTextForm(forms.Form):
    """Form for displaying text on LCD."""

    text = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Enter text to display"),
                "class": "input input-bordered w-full",
            }
        ),
        label=_("Text"),
    )
