"""
Manual settings forms system for plugins.

This module provides manual form classes for plugin settings with
support for nested sections and full control over form fields.
"""

import os
from io import BytesIO
from typing import Any, Dict, List, Optional, Type

from django import forms
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from PIL import Image

from .settings import PluginSettings, SettingField, SiteSettings
from .models import SiteSetting


class SettingsForm(forms.Form):
    """
    Base form for settings with nested section support.

    Example:
        class RoutinesSettingsForm(SettingsForm):
            class Meta:
                sections = {
                    'Audio': ['Audio > TTS', 'Audio > Playback'],
                    'General': ['General']
                }

            # Manual field definitions
            default_tts_engine = forms.ChoiceField(
                label="Default TTS Engine",
                choices=[...]
            )
    """

    class Meta:
        sections: Dict[str, List[str]] = {}

    def get_section_fields(self, section_path: str) -> List[str]:
        """Get field names for a specific section path."""
        fields = []
        for field_name, field in self.fields.items():
            section = getattr(field, "section", "General")
            if section == section_path:
                fields.append(field_name)
        return fields

    def get_sections(self) -> Dict[str, List[str]]:
        """
        Get fields organized by section.

        Returns:
            Dict mapping section paths to field names
        """
        sections = {}
        for field_name, field in self.fields.items():
            section = getattr(field, "section", "General")
            if section not in sections:
                sections[section] = []
            sections[section].append(field_name)
        return sections

    def get_section_hierarchy(self) -> Dict:
        """
        Get sections as a nested hierarchy.

        Returns:
            Nested dict structure like:
            {
                'Audio': {
                    'TTS': ['field1', 'field2'],
                    'Playback': ['field3']
                },
                'General': ['field4']
            }
        """
        hierarchy = {}

        for section_path, fields in self.get_sections().items():
            parts = section_path.split(" > ")
            current = hierarchy

            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]

            last_part = parts[-1]
            if last_part not in current:
                current[last_part] = []
            if isinstance(current[last_part], dict):
                current[last_part]["_fields"] = fields
            else:
                current[last_part] = fields

        return hierarchy


class PluginSettingsForm(SettingsForm):
    """
    Form for plugin settings.

    Must be subclassed and provide plugin_name in Meta.

    Example:
        class RoutinesSettingsForm(PluginSettingsForm):
            class Meta:
                plugin_name = 'edupi.routines'
                sections = {
                    'Audio > TTS': ['Audio > TTS'],
                    'Audio > Playback': ['Audio > Playback'],
                    'General': ['General']
                }

            default_tts_engine = forms.ChoiceField(
                label="Default TTS Engine",
                choices=[
                    ('pyttsx3', _('System TTS (Offline)')),
                    ('edge_tts', _('Edge TTS (Online)')),
                    ('gtts', _('Google TTS (Online)')),
                ],
                help_text="Default text-to-speech engine for routines",
            )

            default_tts_speed = forms.FloatField(
                label="Default TTS Speed",
                min_value=0.5,
                max_value=2.0,
                initial=1.0,
                help_text="Speech speed (0.5 = slow, 1.0 = normal, 2.0 = fast)",
            )
    """

    class Meta:
        plugin_name: str = ""
        sections: Dict[str, List[str]] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._load_initial_values()

    def _load_initial_values(self):
        """Load initial values from database."""
        from .settings import get_plugin_settings

        plugin_name = self.Meta.plugin_name
        settings = get_plugin_settings(plugin_name)

        if settings:
            for field_name in self.fields:
                value = settings.get(field_name)
                if value is not None:
                    self.fields[field_name].initial = value

    def save(self) -> None:
        """Save the form data to settings."""
        from .settings import get_plugin_settings

        plugin_name = self.Meta.plugin_name
        settings = get_plugin_settings(plugin_name)

        if not settings:
            raise ValueError(f"Settings not found for plugin: {plugin_name}")

        for field_name, value in self.cleaned_data.items():
            settings.set(field_name, value)

    @classmethod
    def from_plugin_settings(
        cls, settings_class: Type[PluginSettings]
    ) -> Type["PluginSettingsForm"]:
        """
        Dynamically create a form class from a PluginSettings class.

        This is useful for auto-generating forms from field definitions.
        """
        plugin_name = settings_class.plugin_name
        fields = {}

        for name, field_def in settings_class._settings_fields.items():
            # Create Django form field based on SettingField
            form_field = cls._create_form_field(field_def)
            fields[name] = form_field

        # Create the form class dynamically
        form_class = type(
            f"{settings_class.__name__}Form",
            (cls,),
            {
                "Meta": type(
                    "Meta",
                    (),
                    {
                        "plugin_name": plugin_name,
                        "sections": cls._build_sections(
                            settings_class._settings_fields
                        ),
                    },
                ),
                **fields,
            },
        )

        return form_class

    @staticmethod
    def _create_form_field(field_def: SettingField) -> forms.Field:
        """Create a Django form field from a SettingField definition."""

        if field_def.field_type == "boolean":
            return forms.BooleanField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                initial=field_def.default,
            )
        elif field_def.field_type == "number":
            return forms.FloatField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                initial=field_def.default,
                min_value=field_def.min_value,
                max_value=field_def.max_value,
            )
        elif field_def.field_type == "select":
            return forms.ChoiceField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                choices=field_def.choices or [],
                initial=field_def.default,
            )
        elif field_def.field_type == "textarea":
            return forms.CharField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                initial=field_def.default,
                widget=forms.Textarea(attrs=field_def.attrs),
            )
        elif field_def.field_type == "email":
            return forms.EmailField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                initial=field_def.default,
            )
        elif field_def.field_type == "url":
            return forms.URLField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                initial=field_def.default,
            )
        else:  # text
            return forms.CharField(
                label=field_def.label,
                required=field_def.required,
                help_text=field_def.help_text,
                initial=field_def.default,
                widget=forms.TextInput(attrs=field_def.attrs),
            )

    @staticmethod
    def _build_sections(
        settings_fields: Dict[str, SettingField],
    ) -> Dict[str, List[str]]:
        """Build section hierarchy from settings fields."""
        sections = {}
        for name, field in settings_fields.items():
            section = field.section
            if section not in sections:
                sections[section] = []
            sections[section].append(name)
        return sections


class GlobalSettingsForm(SettingsForm):
    """
    Form for global site settings.

    Example:
        class MyGlobalSettingsForm(GlobalSettingsForm):
            school_name = forms.CharField(
                label="School Name",
                max_length=200,
                help_text="The name of your school",
            )

            robot_name = forms.CharField(
                label="Robot Name",
                max_length=100,
                initial="Tinko",
                help_text="Customize the robot's name",
            )
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._load_initial_values()

    def _load_initial_values(self):
        """Load initial values from database."""
        for field_name in self.fields:
            key = f"tinko.global.{field_name}"
            value = SiteSettings.get(key)
            if value is not None:
                self.fields[field_name].initial = value

    def save(self) -> None:
        """Save the form data to site settings."""
        for field_name, value in self.cleaned_data.items():
            key = f"tinko.global.{field_name}"
            SiteSettings.set(key, value)


class LogoUploadForm(forms.Form):
    """
    Form for uploading school logo with automatic resize.
    """

    logo = forms.ImageField(
        label="School Logo",
        required=False,
        help_text=_(
            "Upload a logo image (PNG, JPG). Will be resized to 400x400px max."
        ),
    )

    # Image dimensions
    MAX_WIDTH = 400
    MAX_HEIGHT = 400
    THUMB_WIDTH = 200
    THUMB_HEIGHT = 200

    def clean_logo(self):
        """Validate the uploaded logo."""
        logo = self.cleaned_data.get("logo")

        if logo:
            # Check file size (max 5MB)
            if logo.size > 5 * 1024 * 1024:
                raise forms.ValidationError(_("Image file too large (> 5MB)"))

            # Validate image format
            try:
                img = Image.open(logo)
                if img.format not in ["JPEG", "PNG", "GIF"]:
                    raise forms.ValidationError(
                        _("Unsupported image format. Use PNG, JPG, or GIF.")
                    )
            except Exception as e:
                raise forms.ValidationError(_("Invalid image file."))

        return logo

    def process_logo(self, logo) -> tuple:
        """
        Process and resize the logo.

        Returns:
            Tuple of (full_image_data, thumbnail_data) as ContentFile objects
        """
        if not logo:
            return None, None

        img = Image.open(logo)

        # Convert to RGB if necessary
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(
                img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None
            )
            img = background

        # Resize to max dimensions while maintaining aspect ratio
        img.thumbnail((self.MAX_WIDTH, self.MAX_HEIGHT), Image.Resampling.LANCZOS)

        # Create thumbnail
        thumb = img.copy()
        thumb.thumbnail((self.THUMB_WIDTH, self.THUMB_HEIGHT), Image.Resampling.LANCZOS)

        # Save to bytes
        full_buffer = BytesIO()
        thumb_buffer = BytesIO()

        img.save(full_buffer, format="PNG")
        thumb.save(thumb_buffer, format="PNG")

        full_buffer.seek(0)
        thumb_buffer.seek(0)

        return (
            ContentFile(full_buffer.getvalue(), name="logo.png"),
            ContentFile(thumb_buffer.getvalue(), name="logo_thumb.png"),
        )

    def save(self, commit=True) -> str:
        """
        Save the processed logo.

        Returns:
            Path to the saved logo file
        """
        logo = self.cleaned_data.get("logo")

        if not logo:
            return None

        full_image, thumbnail = self.process_logo(logo)

        if commit:
            # Save to media storage
            from django.conf import settings

            logo_dir = os.path.join(settings.MEDIA_ROOT, "site", "logos")
            os.makedirs(logo_dir, exist_ok=True)

            # Save full image
            logo_path = os.path.join("site", "logos", "logo.png")
            full_path = os.path.join(settings.MEDIA_ROOT, logo_path)
            with open(full_path, "wb") as f:
                f.write(full_image.read())

            # Save thumbnail
            thumb_path = os.path.join("site", "logos", "logo_thumb.png")
            full_thumb_path = os.path.join(settings.MEDIA_ROOT, thumb_path)
            with open(full_thumb_path, "wb") as f:
                f.write(thumbnail.read())

            return logo_path

        return None


def create_global_settings_form() -> Type[GlobalSettingsForm]:
    """
    Dynamically create a global settings form with fields from database.
    """
    # Get all global settings
    settings = SiteSetting.objects.filter(key__startswith="tinko.global.")

    fields = {}
    for setting in settings:
        field_name = setting.key.replace("tinko.global.", "")

        # Create appropriate field based on setting_type
        if setting.setting_type == "boolean":
            fields[field_name] = forms.BooleanField(
                label=setting.label,
                required=False,
                help_text=setting.description,
                initial=setting.get_value(),
            )
        elif setting.setting_type == "number":
            fields[field_name] = forms.FloatField(
                label=setting.label,
                required=False,
                help_text=setting.description,
                initial=setting.get_value(),
            )
        else:
            fields[field_name] = forms.CharField(
                label=setting.label,
                required=False,
                help_text=setting.description,
                initial=setting.get_value(),
            )

    # Add logo field
    fields["logo"] = forms.ImageField(
        label="School Logo",
        required=False,
        help_text="Upload a school logo (max 400x400px)",
    )

    # Create the form class
    return type("DynamicGlobalSettingsForm", (GlobalSettingsForm,), fields)
