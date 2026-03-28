"""Django forms for Routines plugin."""

from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Routine, RoutineCategory
from .services.tts_manager import tts_manager


class RoutineForm(forms.ModelForm):
    """Form for creating and editing routines."""

    class Meta:
        model = Routine
        fields = [
            "title",
            "content",
            "category",
            "audio_file",
            "tts_engine",
            "tts_speed",
            "tts_voice",
            "tts_language",
            "is_active",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": _("Routine title"),
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "class": "textarea textarea-bordered w-full h-64",
                    "placeholder": _("Enter routine text, one line per instruction"),
                    "rows": 10,
                }
            ),
            "category": forms.Select(attrs={"class": "select select-bordered w-full"}),
            "audio_file": forms.FileInput(
                attrs={
                    "class": "file-input file-input-bordered w-full",
                    "accept": ".mp3,.wav",
                }
            ),
            "tts_engine": forms.Select(
                attrs={"class": "select select-bordered w-full"}
            ),
            "tts_speed": forms.NumberInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "min": "0.5",
                    "max": "2.0",
                    "step": "0.1",
                }
            ),
            "tts_voice": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": _("Voice name (optional)"),
                }
            ),
            "tts_language": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": "en",
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active categories
        self.fields["category"].queryset = RoutineCategory.objects.filter(
            is_active=True
        )

        # Make category optional
        self.fields["category"].required = False

    def clean_tts_speed(self):
        """Validate TTS speed."""
        speed = self.cleaned_data.get("tts_speed", 1.0)
        if speed < 0.5:
            speed = 0.5
        elif speed > 2.0:
            speed = 2.0
        return speed

    def clean_content(self):
        """Validate content is not empty."""
        content = self.cleaned_data.get("content", "").strip()
        if not content:
            raise forms.ValidationError(_("Routine content cannot be empty"))
        return content


class TTSTestForm(forms.Form):
    """Form for testing TTS preview."""

    text = forms.CharField(
        label=_("Text to speak"),
        widget=forms.Textarea(
            attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 3,
                "placeholder": _("Enter text to preview"),
            }
        ),
        required=True,
    )

    engine = forms.ChoiceField(
        label=_("TTS Engine"),
        choices=[],
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
        required=True,
    )

    language = forms.CharField(
        label=_("Language"),
        initial="en",
        widget=forms.TextInput(
            attrs={"class": "input input-bordered w-full", "placeholder": "en"}
        ),
        required=True,
    )

    voice = forms.CharField(
        label=_("Voice (optional)"),
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "input input-bordered w-full",
                "placeholder": _("Voice name"),
            }
        ),
    )

    speed = forms.FloatField(
        label=_("Speed"),
        initial=1.0,
        min_value=0.5,
        max_value=2.0,
        widget=forms.NumberInput(
            attrs={
                "class": "input input-bordered w-full",
                "min": "0.5",
                "max": "2.0",
                "step": "0.1",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get available TTS engines
        available_engines = tts_manager.get_available_engines()
        engine_choices = [
            (name, name.replace("_", " ").title()) for name in available_engines.keys()
        ]
        self.fields["engine"].choices = engine_choices


class RoutineCategoryForm(forms.ModelForm):
    """Form for creating and editing routine categories."""

    class Meta:
        model = RoutineCategory
        fields = [
            "category_type",
            "name",
            "description",
            "display_color",
            "order",
            "is_active",
        ]
        widgets = {
            "category_type": forms.Select(
                attrs={"class": "select select-bordered w-full"}
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "placeholder": _("Category name"),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "textarea textarea-bordered w-full",
                    "rows": 3,
                    "placeholder": _("Description"),
                }
            ),
            "display_color": forms.TextInput(
                attrs={
                    "class": "input input-bordered w-full",
                    "type": "color",
                    "style": "height: 50px;",
                }
            ),
            "order": forms.NumberInput(
                attrs={"class": "input input-bordered w-full", "min": "0"}
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "checkbox"}),
        }
