"""Django app configuration for LCD Display plugin."""

from django.apps import AppConfig


class LCDDisplayConfig(AppConfig):
    """LCD Display app configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "plugins.edupi.lcd_display"
    verbose_name = "LCD Display"
