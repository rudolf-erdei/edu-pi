"""LCD Display Plugin.

Provides support for SPI TFT LCD displays (ILI9341 driver).
Displays a smiling face on startup and can be controlled via the web interface.
"""

import logging

from core.plugin_system.base import PluginBase

logger = logging.getLogger(__name__)


class Plugin(PluginBase):
    """LCD Display Plugin implementation."""

    name = "LCD Display"
    description = (
        "SPI TFT LCD display support for ILI9341 driver. "
        "Shows a smiling face on startup with web-based controls."
    )
    author = "Tinko Team"
    version = "1.0.0"
    icon = "tv"

    def __init__(self, plugin_path: str, enabled: bool = True):
        super().__init__(plugin_path, enabled)
        self._lcd_service = None

    def boot(self) -> None:
        """Initialize the plugin and register GPIO pins."""
        # Register GPIO pins for SPI TFT LCD
        # ILI9341 display uses hardware SPI + control pins
        self.register_gpio_pins(
            {
                "cs": 8,  # Pin 24 - SPI Chip Select (CE0)
                "dc": 23,  # Pin 16 - Data/Command
                "rst": 25,  # Pin 22 - Reset
                "bl": 18,  # Pin 12 - Backlight (PWM capable)
            }
        )

        # Note: SPI pins are hardware-defined and cannot be changed:
        # GPIO 9 (Pin 21) - MISO
        # GPIO 10 (Pin 19) - MOSI
        # GPIO 11 (Pin 23) - SCLK

        logger.info(f"{self.name} plugin booted - GPIO pins registered")

    def register(self) -> None:
        """Register models, URLs, and admin menus."""
        from django.urls import include, path

        from .models import LCDConfig, DisplaySession

        # Register models
        self.register_model(LCDConfig)
        self.register_model(DisplaySession)

        # Register URLs using include
        self.register_url_pattern(
            "", include("plugins.edupi.lcd_display.urls"), name="lcd_display"
        )

        # Register admin menu
        self.register_admin_menu(
            "LCD Display", "/plugins/edupi/lcd_display/", icon="tv"
        )

        # Register settings
        self.register_setting(
            "rotation",
            "Display Rotation",
            default=0,
            field_type="select",
            choices=[
                (0, "0 degrees"),
                (90, "90 degrees"),
                (180, "180 degrees"),
                (270, "270 degrees"),
            ],
        )
        self.register_setting(
            "backlight",
            "Backlight Brightness (%)",
            default=100,
            field_type="number",
            min=0,
            max=100,
        )
        self.register_setting(
            "contrast",
            "Display Contrast",
            default=1.0,
            field_type="number",
            min=0.5,
            max=2.0,
            step=0.1,
        )

        logger.info(f"{self.name} plugin registered")

    def uninstall(self) -> None:
        """Cleanup GPIO pins and resources."""
        if self._lcd_service:
            self._lcd_service.cleanup()
        self.cleanup_gpio_pins()
        logger.info(f"{self.name} plugin uninstalled")
