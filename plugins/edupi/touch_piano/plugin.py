"""Touch Piano Plugin.

Provides a capacitive touch piano using conductive materials
connected to GPIO pins with audio feedback.
"""

import logging

from core.plugin_system.base import PluginBase

logger = logging.getLogger(__name__)


class Plugin(PluginBase):
    """Touch Piano Plugin implementation."""

    name = "Touch Piano"
    description = (
        "Play musical notes by touching conductive materials connected to GPIO pins. "
        "Supports bananas, foil, copper tape, and other conductive items."
    )
    author = "Tinko Team"
    version = "1.0.0"
    icon = "music"
    requires = ["plugins.edupi.lcd_display"]

    def __init__(self, plugin_path: str, enabled: bool = True):
        super().__init__(plugin_path, enabled)
        self._piano_service = None

    def boot(self) -> None:
        """Initialize the plugin and register GPIO pins."""
        from django.utils.translation import gettext as _

        # Register GPIO pins for 6 piano keys
        # Using capacitive touch sensing with pull-up resistors
        # Pins updated to avoid SPI display conflicts (GPIO 8, 9, 10, 11 used by display)
        self.register_gpio_pins(
            {
                "key_1": 4,  # Pin 7 - Note C
                "key_2": 7,  # Pin 26 - Note D
                "key_3": 20,  # Pin 38 - Note E
                "key_4": 21,  # Pin 40 - Note F
                "key_5": 12,  # Pin 32 - Note G
                "key_6": 2,  # Pin 3 - Note A
            }
        )

        logger.info(
            _("%(name)s plugin booted - GPIO pins registered") % {"name": self.name}
        )

    def register(self) -> None:
        """Register models, URLs, and admin menus."""
        from django.urls import include, path
        from django.utils.translation import gettext as _

        from .models import PianoConfig, PianoSession, KeyPress

        # Register models
        self.register_model(PianoConfig)
        self.register_model(PianoSession)
        self.register_model(KeyPress)

        # Register URLs using include
        self.register_url_pattern(
            "", include("plugins.edupi.touch_piano.urls"), name="touch_piano"
        )

        # Register admin menu
        self.register_admin_menu(
            _("Touch Piano"), "/plugins/edupi/touch_piano/", icon="music"
        )

        # Register settings
        self.register_setting(
            "volume",
            _("Piano Volume (%)"),
            default=80,
            field_type="number",
            min=0,
            max=100,
        )
        self.register_setting(
            "audio_device",
            _("Audio Output Device"),
            default="default",
            field_type="text",
            help_text=_("ALSA audio device (e.g., default, hw:0,0, or plughw:1,0)"),
        )
        self.register_setting(
            "sensitivity",
            _("Touch Sensitivity"),
            default=5,
            field_type="number",
            min=1,
            max=10,
            help_text=_("Higher values = more sensitive touch detection"),
        )
        self.register_setting(
            "enable_visual_feedback",
            _("Enable Visual Feedback"),
            default=True,
            field_type="boolean",
            help_text=_("Show key presses on web interface in real-time"),
        )

        logger.info(_("%(name)s plugin registered") % {"name": self.name})

    def uninstall(self) -> None:
        """Cleanup GPIO pins and resources."""
        if self._piano_service:
            self._piano_service.cleanup()
        self.cleanup_gpio_pins()
        logger.info(f"{self.name} plugin uninstalled")
