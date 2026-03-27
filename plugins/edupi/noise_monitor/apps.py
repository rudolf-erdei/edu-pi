from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NoiseMonitorConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plugins.edupi.noise_monitor"
    label = "edupi_noise_monitor"
    verbose_name = _("Noise Monitor")
