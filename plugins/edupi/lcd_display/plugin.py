"""LCD Display Plugin.

Provides support for SPI TFT LCD displays (ILI9341 driver).
Displays a smiling face on startup and can be controlled via the web interface.
"""

import logging

from core.plugin_system.base import PluginBase
from django.utils.translation import gettext_lazy as _

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
        from .lcd_service import lcd_service

        # Register models
        self.register_model(LCDConfig)
        self.register_model(DisplaySession)

        # Register URLs using include
        self.register_url_pattern(
            "", include("plugins.edupi.lcd_display.urls"), name="lcd_display"
        )

        # Register admin menu
        self.register_admin_menu(
            _("LCD Display"), "/plugins/edupi/lcd_display/", icon="tv"
        )

        # Auto-initialize LCD display on startup
        #
        # Only in the server. The service file loads the plugins for its
        # ExecStartPre too, so collectstatic would otherwise bring the panel up
        # in a process that exits seconds later: it clears the screen and draws
        # over whatever is there while the real process is starting, and for
        # that moment two processes are on the same SPI bus. The journal shows
        # both, one after the other, on every boot.
        from core.server_process import is_server_process

        if not is_server_process():
            logger.info("Not the server process, leaving the LCD alone")
        else:
            try:
                self._initialize_display(lcd_service, LCDConfig)
            except Exception as e:
                logger.warning(f"Could not auto-initialize LCD display: {e}")
                logger.info("LCD can still be initialized manually via web interface")

        # Register settings
        self.register_setting(
            "rotation",
            _("Display Rotation"),
            default=90,
            field_type="select",
            choices=[
                (0, _("0 degrees")),
                (90, _("90 degrees")),
                (180, _("180 degrees")),
                (270, _("270 degrees")),
            ],
        )
        self.register_setting(
            "backlight",
            _("Backlight Brightness (%)"),
            default=100,
            field_type="number",
            min=0,
            max=100,
        )
        self.register_setting(
            "contrast",
            _("Display Contrast"),
            default=1.0,
            field_type="number",
            min=0.5,
            max=2.0,
            step=0.1,
        )

        logger.info(f"{self.name} plugin registered")

    def _initialize_display(self, lcd_service, config_model) -> None:
        """Bring the panel up from the stored configuration, or its defaults.

        The rotation comes from the saved row when there is one and from the
        service default when there is not, which is why those two defaults have
        to agree: they are the same decision reached two ways, and a display
        that comes up on its side is what it looks like when they disagree.
        """
        if lcd_service.is_initialized():
            return

        config = config_model.objects.filter(name="Default").first()
        if config:
            logger.info("Auto-initializing LCD display from config...")
            lcd_service.initialize(
                rotation=config.rotation,
                backlight=config.backlight,
            )
        else:
            logger.info("Auto-initializing LCD display with defaults...")
            lcd_service.initialize()

        self._lcd_service = lcd_service
        logger.info(f"{self.name} LCD auto-initialized successfully")

        # Start smiley face after short delay (splash shows during boot)
        import threading

        def _delayed_smiley():
            import time

            time.sleep(3)
            try:
                lcd_service.show_smiley_face()
                lcd_service.start_face_animation()
                logger.info("Smiley face displayed after boot splash")
            except Exception as e:
                logger.warning(f"Failed to show smiley after splash: {e}")

        t = threading.Thread(target=_delayed_smiley, daemon=True)
        t.start()

    def uninstall(self) -> None:
        """Cleanup GPIO pins and resources."""
        if self._lcd_service:
            self._lcd_service.cleanup()
        self.cleanup_gpio_pins()
        logger.info(f"{self.name} plugin uninstalled")
