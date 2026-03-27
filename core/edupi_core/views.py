"""
Views for the Tinko core application.
"""

from django.shortcuts import render
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from core.plugin_system.models import PluginStatus


def home_view(request: HttpRequest):
    """
    Main homepage view for teachers.
    Displays all installed plugins with their names and descriptions.
    """
    # Get runtime plugin information from plugin manager
    from core.plugin_system.base import plugin_manager

    plugin_manager.load_all()
    runtime_plugins = plugin_manager.get_enabled_plugins()

    # Build plugin info with URLs
    plugins_with_urls = []
    for plugin_path, plugin in runtime_plugins.items():
        # Get namespace and convert to URL path
        namespace = plugin.get_namespace()
        url_path = namespace.replace(".", "/")

        plugins_with_urls.append(
            {
                "name": _(plugin.name),
                "description": _(plugin.description),
                "version": plugin.version,
                "author": plugin.author,
                "icon": getattr(plugin, "icon", "puzzle-piece"),
                "url": f"/plugins/{url_path}/",
            }
        )

    context = {
        "title": "Tinko Dashboard",
        "plugins": plugins_with_urls,
        "plugin_count": len(plugins_with_urls),
        "runtime_count": len(runtime_plugins),
    }

    return render(request, "home.html", context)
