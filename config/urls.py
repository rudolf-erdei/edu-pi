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

from django.contrib import admin
from django.urls import path, include

from core.edupi_core.views import home_view, settings_view
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
    # Django admin - catch-all must be last
    path("admin/", admin.site.urls),
]
