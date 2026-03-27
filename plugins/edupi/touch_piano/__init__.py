"""Touch Piano Plugin for EDU-PI.

Allows students to play musical notes by touching conductive materials
like bananas, foil, or copper tape connected to GPIO pins.
"""

# Import the Plugin class so it's accessible from the package
try:
    from .plugin import Plugin
except ImportError:
    pass  # Plugin class not available during early Django startup

__version__ = "1.0.0"

default_app_config = "plugins.edupi.touch_piano.apps.TouchPianoConfig"
