from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ActivityTimerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plugins.edupi.activity_timer"
    label = "edupi_activity_timer"
    verbose_name = _("Activity Timer")
