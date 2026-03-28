"""
Django models for the plugin system.
"""

import json
import os
from io import BytesIO

from django.db import models
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image


class PluginStatus(models.Model):
    """
    Tracks the status of installed plugins.
    """

    plugin_path = models.CharField(
        max_length=255,
        unique=True,
        help_text="Python import path (e.g., 'plugins.acme.myplugin')",
    )

    name = models.CharField(max_length=100, help_text="Plugin display name")

    description = models.TextField(blank=True, help_text="Plugin description")

    author = models.CharField(max_length=100, blank=True, help_text="Plugin author")

    version = models.CharField(max_length=20, help_text="Plugin version")

    is_enabled = models.BooleanField(
        default=True,
        help_text="Whether the plugin is currently enabled",
    )

    is_installed = models.BooleanField(
        default=True,
        help_text="Whether the plugin is installed",
    )

    created_at = models.DateTimeField(
        auto_now_add=True, help_text="When the plugin was first discovered"
    )

    updated_at = models.DateTimeField(
        auto_now=True, help_text="When the plugin was last updated"
    )

    last_enabled_at = models.DateTimeField(
        null=True, blank=True, help_text="When the plugin was last enabled"
    )

    class Meta:
        verbose_name = "Plugin Status"
        verbose_name_plural = "Plugin Statuses"
        ordering = ["-is_enabled", "name"]

    def __str__(self):
        status = "✓" if self.is_enabled else "✗"
        return f"{status} {self.name} ({self.version})"

    def enable(self):
        """Enable the plugin."""
        self.is_enabled = True
        self.last_enabled_at = timezone.now()
        self.save()

    def disable(self):
        """Disable the plugin."""
        self.is_enabled = False
        self.save()


class PluginConfiguration(models.Model):
    """
    Stores configuration values for plugins.
    """

    plugin_status = models.ForeignKey(
        PluginStatus, on_delete=models.CASCADE, related_name="configurations"
    )

    key = models.CharField(max_length=100, help_text="Configuration key")

    value = models.TextField(blank=True, help_text="Configuration value (JSON encoded)")

    description = models.TextField(blank=True, help_text="Configuration description")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plugin Configuration"
        verbose_name_plural = "Plugin Configurations"
        unique_together = ["plugin_status", "key"]
        ordering = ["key"]

    def __str__(self):
        return f"{self.plugin_status.name}.{self.key}"

    def get_value(self):
        """Get the configuration value, decoded from JSON."""
        try:
            return json.loads(self.value)
        except (json.JSONDecodeError, TypeError):
            return self.value

    def set_value(self, value):
        """Set the configuration value, encoded as JSON."""
        self.value = json.dumps(value)


class GPIOPinAllocation(models.Model):
    """
    Tracks GPIO pin allocations to prevent conflicts.
    """

    pin_number = models.PositiveSmallIntegerField(
        help_text="BCM GPIO pin number (0-27)"
    )

    plugin_status = models.ForeignKey(
        PluginStatus, on_delete=models.CASCADE, related_name="gpio_pins"
    )

    pin_name = models.CharField(
        max_length=50, help_text="Logical name for this pin in the plugin"
    )

    purpose = models.CharField(
        max_length=100, blank=True, help_text="Description of what this pin is used for"
    )

    is_active = models.BooleanField(
        default=True, help_text="Whether this allocation is currently active"
    )

    allocated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "GPIO Pin Allocation"
        verbose_name_plural = "GPIO Pin Allocations"
        unique_together = ["pin_number", "is_active"]
        ordering = ["pin_number"]

    def __str__(self):
        return f"GPIO {self.pin_number} -> {self.plugin_status.name}.{self.pin_name}"


class PluginEventLog(models.Model):
    """
    Log of plugin events for debugging and auditing.
    """

    plugin_status = models.ForeignKey(
        PluginStatus, on_delete=models.CASCADE, related_name="event_logs"
    )

    event_name = models.CharField(
        max_length=100, help_text="Event name (e.g., 'boot', 'register', 'error')"
    )

    message = models.TextField(blank=True, help_text="Event message or details")

    data = models.TextField(blank=True, help_text="Additional event data (JSON)")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plugin Event Log"
        verbose_name_plural = "Plugin Event Logs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.plugin_status.name}: {self.event_name}"


class PluginDependency(models.Model):
    """
    Tracks plugin dependencies.
    """

    plugin = models.ForeignKey(
        PluginStatus, on_delete=models.CASCADE, related_name="dependencies"
    )

    depends_on = models.ForeignKey(
        PluginStatus, on_delete=models.CASCADE, related_name="dependents"
    )

    is_optional = models.BooleanField(
        default=False, help_text="Whether this dependency is optional"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plugin Dependency"
        verbose_name_plural = "Plugin Dependencies"
        unique_together = ["plugin", "depends_on"]

    def __str__(self):
        optional = " (optional)" if self.is_optional else ""
        return f"{self.plugin.name} depends on {self.depends_on.name}{optional}"


class SiteSetting(models.Model):
    """
    Stores global system settings with namespace support.

    Keys use the format: tinko.global.<setting_name>
    Example: tinko.global.school_name, tinko.global.robot_name
    """

    SETTING_TYPE_CHOICES = [
        ("text", "Text"),
        ("number", "Number"),
        ("boolean", "Boolean"),
        ("image", "Image"),
        ("json", "JSON"),
    ]

    key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Setting key (e.g., 'tinko.global.school_name')",
    )

    value = models.TextField(
        blank=True,
        help_text="Setting value (JSON encoded for non-text types)",
    )

    setting_type = models.CharField(
        max_length=20,
        choices=SETTING_TYPE_CHOICES,
        default="text",
        help_text="Data type of the setting",
    )

    label = models.CharField(
        max_length=200,
        help_text="Display label for the setting",
    )

    description = models.TextField(
        blank=True,
        help_text="Help text for this setting",
    )

    section = models.CharField(
        max_length=100,
        blank=True,
        default="General",
        help_text="Section/group for organizing settings (e.g., 'General > Display')",
    )

    is_system = models.BooleanField(
        default=False,
        help_text="System settings cannot be deleted",
    )

    order = models.PositiveIntegerField(
        default=0,
        help_text="Display order within section",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site Setting"
        verbose_name_plural = "Site Settings"
        ordering = ["section", "order", "key"]

    def __str__(self):
        return f"{self.key} = {self.get_display_value()}"

    def get_display_value(self):
        """Get a display-friendly value."""
        if self.setting_type == "image":
            return f"[Image] {self.value}" if self.value else "[No image]"
        elif self.setting_type == "json":
            return "[JSON data]"
        elif len(str(self.value)) > 50:
            return str(self.value)[:47] + "..."
        return str(self.value)

    def get_value(self):
        """Get the setting value with proper type conversion."""
        cache_key = f"site_setting:{self.key}"
        cached_value = cache.get(cache_key)

        if cached_value is not None:
            return cached_value

        if self.setting_type == "boolean":
            result = self.value.lower() == "true"
        elif self.setting_type == "number":
            try:
                result = float(self.value)
                if result.is_integer():
                    result = int(result)
            except (ValueError, TypeError):
                result = 0
        elif self.setting_type == "json":
            try:
                result = json.loads(self.value) if self.value else {}
            except json.JSONDecodeError:
                result = {}
        elif self.setting_type == "image":
            result = self.value
        else:
            result = self.value

        # Cache for 5 minutes
        cache.set(cache_key, result, timeout=300)
        return result

    def set_value(self, value):
        """Set the setting value with proper type conversion."""
        if self.setting_type == "boolean":
            self.value = "true" if value else "false"
        elif self.setting_type == "json":
            self.value = json.dumps(value)
        else:
            self.value = str(value) if value is not None else ""

        # Invalidate cache
        cache.delete(f"site_setting:{self.key}")

    def save(self, *args, **kwargs):
        """Save and invalidate cache."""
        super().save(*args, **kwargs)
        cache.delete(f"site_setting:{self.key}")

    def delete(self, *args, **kwargs):
        """Delete and invalidate cache."""
        if self.is_system:
            raise ValueError("Cannot delete system settings")
        cache.delete(f"site_setting:{self.key}")
        super().delete(*args, **kwargs)
