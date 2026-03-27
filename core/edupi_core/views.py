"""
Views for the EDU-PI core application.
"""

from django.shortcuts import render
from django.http import HttpRequest

from core.plugin_system.models import PluginStatus


def home_view(request: HttpRequest):
    """
    Main homepage view for teachers.
    Displays all installed plugins with their names and descriptions.
    """
    # Get all enabled plugins from database
    plugins = PluginStatus.objects.filter(is_enabled=True, is_installed=True).order_by(
        "name"
    )

    # Get runtime plugin information from plugin manager
    from core.plugin_system.base import plugin_manager

    runtime_plugins = plugin_manager.get_enabled_plugins()

    context = {
        "title": "EDU-PI Dashboard",
        "plugins": plugins,
        "plugin_count": plugins.count(),
        "runtime_count": len(runtime_plugins),
    }

    return render(request, "home.html", context)
