"""
Django app configuration for the plugin system.
"""

from django.apps import AppConfig
from django.conf import settings


class PluginSystemConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core.plugin_system"
    verbose_name = "Plugin System"

    def ready(self):
        """Called when Django starts up. Load all plugins."""
        from .base import plugin_manager
        from pathlib import Path

        plugin_manager.load_all()

        # Add plugin locale paths to LOCALE_PATHS
        locale_paths = list(settings.LOCALE_PATHS)
        plugins_path = Path(settings.BASE_DIR) / "plugins"

        if plugins_path.exists():
            for author_dir in plugins_path.iterdir():
                if not author_dir.is_dir():
                    continue
                for plugin_dir in author_dir.iterdir():
                    if not plugin_dir.is_dir():
                        continue
                    plugin_locale = plugin_dir / "locale"
                    if plugin_locale.exists():
                        locale_paths.append(plugin_locale)

        # Update settings (need to use this approach since LOCALE_PATHS is a tuple)
        settings.LOCALE_PATHS = tuple(locale_paths)
