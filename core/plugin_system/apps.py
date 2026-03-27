"""
Django app configuration for the plugin system.
"""

from django.apps import AppConfig


class PluginSystemConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core.plugin_system"
    verbose_name = "Plugin System"

    def ready(self):
        """Called when Django starts up. Load all plugins."""
        from .base import plugin_manager

        plugin_manager.load_all()
