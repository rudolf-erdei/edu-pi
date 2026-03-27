"""
Views for the plugin system admin interface.
"""

from django.contrib.admin.views.decorators import staff_member_required
from django.template.response import TemplateResponse
from django.shortcuts import redirect
from django.contrib import messages

from .base import plugin_manager
from .models import PluginStatus


@staff_member_required
def plugin_dashboard_view(request):
    """Custom view to display all installed plugins."""

    # Get plugins from database
    db_plugins = PluginStatus.objects.all().order_by("-is_enabled", "name")

    # Get runtime plugins from manager
    runtime_plugins = plugin_manager.get_all_plugins()

    context = {
        "title": "Installed Plugins",
        "db_plugins": db_plugins,
        "runtime_plugins": runtime_plugins,
        "total_plugins": db_plugins.count(),
        "enabled_plugins": db_plugins.filter(is_enabled=True).count(),
        "has_permission": True,
        "site_title": "EDU-PI Admin",
        "site_header": "EDU-PI Plugin Administration",
    }

    return TemplateResponse(request, "admin/plugin_dashboard.html", context)


@staff_member_required
def enable_plugin_view(request, plugin_id):
    """Enable a specific plugin."""
    try:
        plugin = PluginStatus.objects.get(id=plugin_id)
        plugin.enable()
        messages.success(request, f'Plugin "{plugin.name}" has been enabled.')
    except PluginStatus.DoesNotExist:
        messages.error(request, "Plugin not found.")

    return redirect("admin:plugin_dashboard")


@staff_member_required
def disable_plugin_view(request, plugin_id):
    """Disable a specific plugin."""
    try:
        plugin = PluginStatus.objects.get(id=plugin_id)
        plugin.disable()
        messages.success(request, f'Plugin "{plugin.name}" has been disabled.')
    except PluginStatus.DoesNotExist:
        messages.error(request, "Plugin not found.")

    return redirect("admin:plugin_dashboard")
