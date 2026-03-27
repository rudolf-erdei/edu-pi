"""
Dynamic URL routing for plugins.

This module dynamically routes URLs to enabled plugins based on the pattern:
/plugins/<author>/<plugin_name>/
"""

from django.urls import path, include
from django.conf import settings


def get_plugin_urlpatterns():
    """
    Dynamically generate URL patterns for all enabled plugins.

    Returns a list of URL patterns like:
        path('edupi/activity_timer/', include('plugins.edupi.activity_timer.urls')),
    """
    patterns = []

    # Import here to avoid circular imports during early Django startup
    from core.plugin_system.base import plugin_manager

    # Ensure plugins are loaded
    plugin_manager.load_all()

    # Get all enabled plugins
    for import_path, plugin in plugin_manager.get_enabled_plugins().items():
        # Extract namespace: plugins.edupi.activity_timer -> edupi.activity_timer
        namespace = plugin.get_namespace()

        # Get URL patterns from plugin
        url_patterns = plugin.get_url_patterns()

        if url_patterns:
            # Include the plugin's URL configuration
            plugin_urls_path = f"{import_path}.urls"

            try:
                # Convert dots to slashes for URL path: edupi.activity_timer -> edupi/activity_timer/
                url_path = namespace.replace(".", "/")
                patterns.append(path(f"{url_path}/", include(plugin_urls_path)))
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.error(f"Failed to load URLs for plugin {import_path}: {e}")

    return patterns


# Generate URL patterns at module load time
urlpatterns = get_plugin_urlpatterns()
