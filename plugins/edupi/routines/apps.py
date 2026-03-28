"""Django app configuration for Routines plugin."""

from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class RoutinesConfig(AppConfig):
    """Routines plugin app configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "plugins.edupi.routines"
    label = "edupi_routines"
    verbose_name = _("Routines")

    def ready(self):
        """Called when the app is ready."""
        pass
