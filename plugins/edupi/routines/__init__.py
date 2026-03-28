"""Routines Plugin for Tinko.

Text-to-speech classroom routines with USB presenter support.
"""

# Import the Plugin class so it's accessible from the package
try:
    from .plugin import Plugin
except ImportError:
    pass  # Plugin class not available during early Django startup

default_app_config = "plugins.edupi.routines.apps.RoutinesConfig"
