"""
Custom admin views for the plugin system.
"""

from django.contrib import admin
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .base import plugin_manager
from .models import (
    PluginStatus,
    PluginConfiguration,
    GPIOPinAllocation,
    PluginEventLog,
    PluginDependency,
)


class PluginAdminSite(admin.AdminSite):
    """Custom admin site with plugin dashboard."""

    site_header = "EDU-PI Plugin Administration"
    site_title = "EDU-PI Admin"
    index_title = "Dashboard"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "plugins/",
                self.admin_view(self.plugin_dashboard_view),
                name="plugin_dashboard",
            ),
        ]
        return custom_urls + urls

    def plugin_dashboard_view(self, request):
        """Custom view to display all installed plugins."""

        # Get plugins from database
        db_plugins = PluginStatus.objects.all().order_by("-is_enabled", "name")

        # Get runtime plugins from manager
        runtime_plugins = plugin_manager.get_all_plugins()

        context = {
            **self.each_context(request),
            "title": "Installed Plugins",
            "db_plugins": db_plugins,
            "runtime_plugins": runtime_plugins,
            "total_plugins": db_plugins.count(),
            "enabled_plugins": db_plugins.filter(is_enabled=True).count(),
        }

        return TemplateResponse(request, "admin/plugin_dashboard.html", context)


# Create custom admin instance
plugin_admin = PluginAdminSite(name="plugin_admin")


@admin.register(PluginStatus)
class PluginStatusAdmin(admin.ModelAdmin):
    """Plugin status admin with custom list view."""

    list_display = [
        "name",
        "version",
        "author",
        "is_enabled",
        "is_installed",
        "updated_at",
        "actions_column",
    ]
    list_filter = ["is_enabled", "is_installed", "created_at"]
    search_fields = ["name", "author", "plugin_path"]
    actions = ["enable_plugins", "disable_plugins"]
    readonly_fields = ["plugin_path", "created_at", "updated_at", "last_enabled_at"]

    fieldsets = (
        (
            "Plugin Information",
            {"fields": ("name", "description", "version", "author")},
        ),
        ("Status", {"fields": ("is_enabled", "is_installed", "plugin_path")}),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at", "last_enabled_at"),
                "classes": ("collapse",),
            },
        ),
    )

    def actions_column(self, obj):
        """Custom actions column."""
        if obj.is_enabled:
            return format_html('<span style="color: green;">✓ Active</span>')
        else:
            return format_html('<span style="color: red;">✗ Disabled</span>')

    actions_column.short_description = "Status"

    def enable_plugins(self, request, queryset):
        """Enable selected plugins."""
        count = 0
        for plugin in queryset:
            if not plugin.is_enabled:
                plugin.enable()
                count += 1
        self.message_user(request, f"{count} plugin(s) enabled successfully.")

    enable_plugins.short_description = "Enable selected plugins"

    def disable_plugins(self, request, queryset):
        """Disable selected plugins."""
        count = 0
        for plugin in queryset:
            if plugin.is_enabled:
                plugin.disable()
                count += 1
        self.message_user(request, f"{count} plugin(s) disabled successfully.")

    disable_plugins.short_description = "Disable selected plugins"


@admin.register(PluginConfiguration)
class PluginConfigurationAdmin(admin.ModelAdmin):
    list_display = ["plugin_status", "key", "updated_at"]
    list_filter = ["plugin_status"]
    search_fields = ["key", "description"]


@admin.register(GPIOPinAllocation)
class GPIOPinAllocationAdmin(admin.ModelAdmin):
    list_display = [
        "pin_number",
        "plugin_status",
        "pin_name",
        "is_active",
        "allocated_at",
    ]
    list_filter = ["is_active", "allocated_at"]
    search_fields = ["pin_name", "purpose"]


@admin.register(PluginEventLog)
class PluginEventLogAdmin(admin.ModelAdmin):
    list_display = ["plugin_status", "event_name", "created_at"]
    list_filter = ["event_name", "created_at"]
    search_fields = ["message"]
    readonly_fields = ["plugin_status", "event_name", "message", "data", "created_at"]

    def has_add_permission(self, request):
        return False


@admin.register(PluginDependency)
class PluginDependencyAdmin(admin.ModelAdmin):
    list_display = ["plugin", "depends_on", "is_optional"]
    list_filter = ["is_optional"]
