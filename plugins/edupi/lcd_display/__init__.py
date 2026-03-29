# plugins/edupi/lcd_display/__init__.py

try:
    from .plugin import Plugin
except ImportError:
    pass  # Plugin class not available during early Django startup

default_app_config = "plugins.edupi.lcd_display.apps.LCDDisplayConfig"
