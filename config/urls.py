"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path, include
from django.views.i18n import JavaScriptCatalog

from core.edupi_core.views import (
    home_view,
    serve_media,
    settings_view,
    power_shutdown,
)
from core.edupi_core.system.views import (
    system_backup,
    system_clean,
    system_clients,
    system_vacuum,
)
from core.plugin_system.views import (
    plugin_dashboard_view,
    enable_plugin_view,
    disable_plugin_view,
)

urlpatterns = [
    # Home page - main teacher dashboard
    path("", home_view, name="home"),
    # Language switcher
    path("i18n/", include("django.conf.urls.i18n")),
    # Translation catalog for JavaScript (gettext/ngettext in static JS)
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    # System updates
    path("updates/", include("core.update_system.urls")),
    # Safe shutdown (poweroff via sudoers; UI button on dashboard)
    path("power/shutdown/", power_shutdown, name="power_shutdown"),
    # Plugin URLs - plugins register under /plugins/<author>/<plugin>/
    path("plugins/", include("core.plugin_system.urls")),
    # Plugin dashboard URLs - must come before admin/ catch-all
    path("admin/plugins/", plugin_dashboard_view, name="plugin_dashboard"),
    path(
        "admin/plugins/<int:plugin_id>/enable/",
        enable_plugin_view,
        name="enable_plugin",
    ),
    path(
        "admin/plugins/<int:plugin_id>/disable/",
        disable_plugin_view,
        name="disable_plugin",
    ),
    # Settings page
    path("settings/", settings_view, name="settings"),
    # System tab on the settings page. `clean` and `vacuum` are POST-only;
    # `backup` is a download and so has to be a GET. None of the four asks for
    # a login, because nothing on this site does yet — see ISSUES.md.
    path("settings/system/clients/", system_clients, name="settings_system_clients"),
    path("settings/system/backup/", system_backup, name="settings_system_backup"),
    path("settings/system/clean/", system_clean, name="settings_system_clean"),
    path("settings/system/vacuum/", system_vacuum, name="settings_system_vacuum"),
    # Uploaded files (school logo, generated audio), under MEDIA_URL rather
    # than a hard-coded "media/" so the route and the URLs the templates build
    # cannot drift apart. Deliberately not gated on DEBUG: the logo is
    # uploaded through the settings page on a Pi running with DEBUG=False, and
    # until this route existed every logo upload looked like it did nothing —
    # the file was written and the setting saved, but the <img> pointing at it
    # got a 404. WhiteNoise cannot cover this either: it serves STATIC_ROOT and
    # indexes it at startup, so a file written at runtime would not be found
    # until the service restarted.
    re_path(
        r"^{}(?P<path>.*)$".format(settings.MEDIA_URL.lstrip("/")),
        serve_media,
        name="media",
    ),
    # Django admin - catch-all must be last
    path("admin/", admin.site.urls),
]
