"""Activity Timer Plugin for EDU-PI.

A classroom activity timer with visual progress on RGB LED.
"""

# Import the Plugin class so it's accessible from the package
try:
    from .plugin import Plugin
except ImportError:
    pass  # Plugin class not available during early Django startup

default_app_config = "plugins.edupi.activity_timer.apps.ActivityTimerConfig"
