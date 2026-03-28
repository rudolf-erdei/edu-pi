"""
Views for the Tinko core application.
"""

from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from core.plugin_system.models import PluginStatus
from core.plugin_system.settings import SiteSettings
from core.plugin_system.settings_forms import GlobalSettingsForm, LogoUploadForm
from django.shortcuts import redirect
from django import forms
import logging

logger = logging.getLogger(__name__)


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


class GlobalSettingsFormImpl(GlobalSettingsForm):
    """Global settings form with all required fields."""

    school_name = forms.CharField(
        label=_("School Name"),
        max_length=200,
        required=False,
        help_text=_("The name of your school or institution"),
    )

    robot_name = forms.CharField(
        label=_("Robot Name"),
        max_length=100,
        required=False,
        initial="Tinko",
        help_text=_("Customize the robot's name for your classroom"),
    )

    default_language = forms.ChoiceField(
        label=_("Default Language"),
        choices=[
            ("en", _("English")),
            ("ro", _("Romanian")),
        ],
        required=False,
        help_text=_("Default language for the interface"),
    )

    timezone = forms.CharField(
        label=_("Timezone"),
        max_length=50,
        required=False,
        initial="UTC",
        help_text=_("Timezone (e.g., Europe/Bucharest, America/New_York)"),
    )


@login_required
def settings_view(request: HttpRequest) -> HttpResponse:
    """
    Main settings page with tabs for global and plugin settings.
    """
    if request.method == "POST":
        form = GlobalSettingsFormImpl(request.POST, request.FILES)
        logo_form = LogoUploadForm(request.POST, request.FILES)

        if form.is_valid() and logo_form.is_valid():
            # Save form data
            form.save()

            # Handle logo upload
            if request.FILES.get("logo"):
                logo_path = logo_form.save()
                if logo_path:
                    from core.plugin_system.models import SiteSetting

                    SiteSetting.objects.update_or_create(
                        key="tinko.global.logo_path",
                        defaults={
                            "label": "Logo Path",
                            "setting_type": "text",
                            "value": logo_path,
                            "section": "General",
                            "is_system": True,
                        },
                    )

            messages.success(request, _("Global settings saved successfully."))
            return redirect("settings")
        else:
            messages.error(request, _("Please correct the errors below."))
    else:
        form = GlobalSettingsFormImpl()
        logo_form = LogoUploadForm()

    # Get current logo
    from core.plugin_system.models import SiteSetting

    try:
        logo_setting = SiteSetting.objects.get(key="tinko.global.logo_path")
        logo_path = logo_setting.value
    except SiteSetting.DoesNotExist:
        logo_path = None

    # Build tabs
    tabs = [
        {
            "id": "global",
            "label": _("Global Settings"),
            "icon": "globe",
            "active": True,
        }
    ]

    # Add plugin setting tabs
    from core.plugin_system.settings import SettingsRegistry

    for plugin_name, settings in SettingsRegistry.get_all_settings().items():
        if settings._settings_fields:
            tabs.append(
                {
                    "id": plugin_name.replace(".", "_"),
                    "label": plugin_name.replace("edupi.", "")
                    .replace("_", " ")
                    .title(),
                    "icon": "cog",
                    "active": False,
                }
            )

    context = {
        "title": _("Settings"),
        "form": form,
        "logo_form": logo_form,
        "logo_path": logo_path,
        "is_global": True,
        "tabs": tabs,
    }

    return render(request, "settings/settings_page.html", context)
