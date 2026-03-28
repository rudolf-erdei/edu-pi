"""
Plugin settings system inspired by OctoberCMS.

This module provides a settings framework for plugins, allowing developers
to define settings with nested sections and automatic form generation.
"""

from typing import Any, Dict, List, Optional, Type, Union
from dataclasses import dataclass, field
import json
import logging

from django.db import models
from django import forms
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _

from .models import PluginConfiguration, PluginStatus, SiteSetting

logger = logging.getLogger(__name__)


@dataclass
class SettingField:
    """
    Definition of a plugin setting field.

    Attributes:
        name: Setting key (without plugin namespace)
        label: Display label
        default: Default value
        section: Section path using arrow notation (e.g., "Audio > TTS")
        field_type: Form field type
        help_text: Help text for the field
        required: Whether the field is required
        validators: List of validator functions
        choices: List of (value, label) tuples for select fields
        attrs: Additional widget attributes
    """

    name: str
    label: str
    default: Any = None
    section: str = "General"
    field_type: str = "text"  # text, number, boolean, select, email, url, textarea
    help_text: str = ""
    required: bool = False
    validators: List = field(default_factory=list)
    choices: Optional[List[tuple]] = None
    attrs: Dict = field(default_factory=dict)
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None


class PluginSettingsMeta(type):
    """Metaclass to collect setting fields from class definition."""

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)

        # Collect SettingField instances from class attributes
        settings = {}
        for key, value in list(namespace.items()):
            if isinstance(value, SettingField):
                settings[key] = value
                # Remove from namespace to avoid polluting class
                delattr(cls, key)

        cls._settings_fields = settings
        return cls


class PluginSettings(metaclass=PluginSettingsMeta):
    """
    Base class for plugin settings.

    Example:
        class RoutinesSettings(PluginSettings):
            plugin_name = "edupi.routines"

            default_tts_engine = SettingField(
                name="default_tts_engine",
                label="Default TTS Engine",
                default="pyttsx3",
                section="Audio > TTS",
                field_type="select",
                choices=[
                    ("pyttsx3", "System TTS (Offline)"),
                    ("edge_tts", "Edge TTS (Online)"),
                ],
                help_text="Default text-to-speech engine"
            )

    Usage:
        settings = RoutinesSettings()
        engine = settings.get('default_tts_engine')
        settings.set('default_tts_engine', 'edge_tts')
    """

    plugin_name: str = ""  # Must be set by subclass

    def __init__(self, plugin_name: Optional[str] = None):
        """
        Initialize settings for a plugin.

        Args:
            plugin_name: Plugin namespace (e.g., 'edupi.routines')
        """
        if plugin_name:
            self.plugin_name = plugin_name

        if not self.plugin_name:
            raise ValueError("PluginSettings must have a plugin_name defined")

        self._cache_prefix = f"plugin_settings:{self.plugin_name}:"

        # Register in global registry
        SettingsRegistry.register(self)

    def get_full_key(self, setting_name: str) -> str:
        """Get the full setting key with namespace."""
        return f"{self.plugin_name}.{setting_name}"

    def get(self, name: str, default: Any = None) -> Any:
        """
        Get a setting value.

        Args:
            name: Setting name (without plugin namespace)
            default: Default value if setting not found

        Returns:
            Setting value with proper type conversion
        """
        full_key = self.get_full_key(name)
        cache_key = self._cache_prefix + name

        # Try cache first
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value

        # Get from database
        try:
            config = PluginConfiguration.objects.get(
                plugin_status__plugin_path=self.plugin_name.replace(".", ""), key=name
            )
            value = config.get_value()
        except (PluginConfiguration.DoesNotExist, PluginStatus.DoesNotExist):
            # Return field default if available
            field = self._settings_fields.get(name)
            value = field.default if field else default

        # Cache the value
        cache.set(cache_key, value, timeout=300)
        return value

    def set(self, name: str, value: Any) -> None:
        """
        Set a setting value.

        Args:
            name: Setting name (without plugin namespace)
            value: Value to set
        """
        full_key = self.get_full_key(name)
        cache_key = self._cache_prefix + name

        # Get or create plugin status
        try:
            plugin_status = PluginStatus.objects.get(plugin_path=self.plugin_name)
        except PluginStatus.DoesNotExist:
            logger.error(f"Plugin {self.plugin_name} not found")
            return

        # Update or create configuration
        config, created = PluginConfiguration.objects.get_or_create(
            plugin_status=plugin_status, key=name, defaults={"value": json.dumps(value)}
        )

        if not created:
            config.set_value(value)
            config.save()

        # Update cache
        cache.set(cache_key, value, timeout=300)

        # Emit settings changed event
        logger.info(f"Setting changed: {full_key} = {value}")

    def get_all(self) -> Dict[str, Any]:
        """Get all settings as a dictionary."""
        result = {}
        for name in self._settings_fields:
            result[name] = self.get(name)
        return result

    def reset_to_defaults(self) -> None:
        """Reset all settings to their default values."""
        for name, field in self._settings_fields.items():
            self.set(name, field.default)

    def get_sections(self) -> Dict[str, List[SettingField]]:
        """
        Get settings organized by section.

        Returns:
            Dict mapping section paths to lists of fields
        """
        sections = {}
        for name, field in self._settings_fields.items():
            section = field.section
            if section not in sections:
                sections[section] = []
            sections[section].append(field)
        return sections

    def get_field(self, name: str) -> Optional[SettingField]:
        """Get a setting field definition."""
        return self._settings_fields.get(name)

    def invalidate_cache(self, name: Optional[str] = None) -> None:
        """
        Invalidate cache for a setting or all settings.

        Args:
            name: Setting name to invalidate, or None for all
        """
        if name:
            cache.delete(self._cache_prefix + name)
        else:
            # Clear all cached values for this plugin
            keys = [self._cache_prefix + n for n in self._settings_fields.keys()]
            cache.delete_many(keys)


class SettingsRegistry:
    """Registry for all plugin settings classes."""

    _registry: Dict[str, Type[PluginSettings]] = {}
    _instances: Dict[str, PluginSettings] = {}

    @classmethod
    def register(
        cls, settings_class_or_instance: Union[Type[PluginSettings], PluginSettings]
    ) -> None:
        """Register a settings class."""
        if isinstance(settings_class_or_instance, PluginSettings):
            # It's an instance
            plugin_name = settings_class_or_instance.plugin_name
            cls._instances[plugin_name] = settings_class_or_instance
        else:
            # It's a class
            plugin_name = settings_class_or_instance.plugin_name
            cls._registry[plugin_name] = settings_class_or_instance

    @classmethod
    def get_settings_class(cls, plugin_name: str) -> Optional[Type[PluginSettings]]:
        """Get the settings class for a plugin."""
        return cls._registry.get(plugin_name)

    @classmethod
    def get_settings(cls, plugin_name: str) -> Optional[PluginSettings]:
        """Get the settings instance for a plugin."""
        # Return existing instance if available
        if plugin_name in cls._instances:
            return cls._instances[plugin_name]

        # Create instance from registered class
        settings_class = cls._registry.get(plugin_name)
        if settings_class:
            instance = settings_class()
            cls._instances[plugin_name] = instance
            return instance

        return None

    @classmethod
    def get_all_settings(cls) -> Dict[str, PluginSettings]:
        """Get all registered settings instances."""
        # Ensure all registered classes are instantiated
        for plugin_name in list(cls._registry.keys()):
            if plugin_name not in cls._instances:
                cls.get_settings(plugin_name)
        return cls._instances.copy()

    @classmethod
    def unregister(cls, plugin_name: str) -> None:
        """Unregister a plugin's settings."""
        cls._registry.pop(plugin_name, None)
        cls._instances.pop(plugin_name, None)


# Global site settings accessor
class SiteSettings:
    """
    Accessor for global site settings.

    Usage:
        from core.plugin_system.settings import SiteSettings

        school_name = SiteSettings.get('tinko.global.school_name', 'Default School')
        SiteSettings.set('tinko.global.robot_name', 'MyRobot')
    """

    @classmethod
    def get(cls, key: str, default: Any = None) -> Any:
        """Get a site setting value."""
        cache_key = f"site_setting:{key}"

        # Try cache first
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value

        try:
            setting = SiteSetting.objects.get(key=key)
            value = setting.get_value()
        except SiteSetting.DoesNotExist:
            value = default

        # Cache the value
        cache.set(cache_key, value, timeout=300)
        return value

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set a site setting value."""
        try:
            setting = SiteSetting.objects.get(key=key)
            setting.set_value(value)
            setting.save()
        except SiteSetting.DoesNotExist:
            # Create new setting
            SiteSetting.objects.create(
                key=key,
                value=json.dumps(value) if not isinstance(value, str) else value,
                setting_type=cls._infer_type(value),
                label=key.replace("tinko.global.", "").replace("_", " ").title(),
            )

        # Invalidate cache
        cache.delete(f"site_setting:{key}")

    @classmethod
    def _infer_type(cls, value: Any) -> str:
        """Infer the setting type from value."""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, (int, float)):
            return "number"
        elif isinstance(value, dict):
            return "json"
        else:
            return "text"


# Convenience function for getting plugin settings
def get_plugin_settings(plugin_name: str) -> Optional[PluginSettings]:
    """
    Get settings instance for a plugin.

    Args:
        plugin_name: Plugin namespace (e.g., 'edupi.routines')

    Returns:
        PluginSettings instance or None if not registered
    """
    return SettingsRegistry.get_settings(plugin_name)
