"""Site-wide settings accessors.

Plugin settings are not stored here. Each plugin owns the page that edits its
configuration, declares it with ``PluginBase.register_settings_tab()``, and the
Settings page links to it. There used to be a second, generic registry of
plugin forms in this module; nothing ever instantiated it, so no tab rendered
and none of those forms could be reached. It was removed rather than wired,
because it would have been an editor for records the plugin pages already own.
"""

from typing import Any
import json

from django.core.cache import cache

from .models import SiteSetting


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
