"""Noise Monitor Plugin.

Provides continuous classroom noise monitoring with visual feedback via RGB LEDs
to help students self-regulate their volume levels.
"""

import logging
from typing import Optional

from core.plugin_system.base import PluginBase
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class Plugin(PluginBase):
    """Noise Monitor Plugin implementation."""

    name = "Noise Monitor"
    description = "Visual noise level monitor for classroom with dual RGB LED feedback"
    author = "Tinko Team"
    version = "1.0.0"
    icon = "volume-2"
    requires = ["plugins.edupi.lcd_display"]

    def __init__(self, plugin_path: str, enabled: bool = True):
        super().__init__(plugin_path, enabled)
        self._service = None

    def boot(self) -> None:
        """Initialize the plugin and register GPIO pins."""
        from .startup import LED_PINS

        # Register GPIO pins for TWO RGB LEDs. The numbers live in startup.py
        # because the auto-start below initialises the same pins.
        # LED 1: Instant noise (10-second average)
        self.register_gpio_pins(
            {
                name: LED_PINS[name]
                for name in ("instant_red", "instant_green", "instant_blue")
            }
        )

        # LED 2: Session average (5-10 minute average)
        self.register_gpio_pins(
            {
                name: LED_PINS[name]
                for name in ("session_red", "session_green", "session_blue")
            }
        )

        logger.info(f"{self.name} plugin booted - GPIO pins registered")

    def register(self) -> None:
        """Register models, URLs, and admin menus."""
        from django.urls import include, path

        from .models import NoiseProfile, NoiseMonitorConfig, NoiseReading

        # Register models
        self.register_model(NoiseProfile)
        self.register_model(NoiseMonitorConfig)
        self.register_model(NoiseReading)

        # Register URLs using include
        self.register_url_pattern(
            "", include("plugins.edupi.noise_monitor.urls"), name="noise_monitor"
        )

        # Register admin menu
        self.register_admin_menu(
            _("Noise Monitor"), "/plugins/edupi/noise_monitor/", icon="volume-2"
        )

        # Register settings
        self.register_setting(
            "instant_window_seconds",
            _("Instant Average Window (seconds)"),
            default=10,
            field_type="number",
            min=5,
            max=60,
            help_text=_("Time window for instant noise average calculation"),
        )
        self.register_setting(
            "session_window_minutes",
            _("Session Average Window (minutes)"),
            default=5,
            field_type="number",
            min=1,
            max=30,
            help_text=_("Time window for session noise average calculation"),
        )
        self.register_setting(
            "led_brightness",
            _("LED Brightness (%)"),
            default=100,
            field_type="number",
            min=10,
            max=100,
        )
        self.register_setting(
            "enable_monitoring",
            _("Enable Noise Monitoring"),
            default=True,
            field_type="boolean",
            help_text=_("Start monitoring when plugin is enabled"),
        )

        # Load device config if available
        self._load_device_config()

        # Last, so a failure here cannot leave the plugin half-registered.
        self._autostart_monitoring()

        logger.info(f"{self.name} plugin registered")

    def _load_device_config(self) -> None:
        """Load saved device configuration into the service."""
        try:
            from .models import NoiseMonitorConfig
            from .noise_service import noise_service

            config = NoiseMonitorConfig.objects.filter(is_active=True).first()
            if config:
                # Called even when nothing is configured, so that an empty
                # selection means "choose automatically" rather than "keep
                # whatever the last process left behind".
                noise_service.set_device(
                    config.audio_input_device_index,
                    config.audio_input_device,
                )
                logger.info(
                    f"Microphone config: {config.audio_input_device or 'automatic'}"
                )
        except Exception as e:
            logger.warning(f"Could not load device config: {e}")

    def _autostart_monitoring(self) -> None:
        """Bring the monitor up on its own, when the configuration asks for it.

        A classroom Pi is switched on and left alone. The LEDs and the face are
        the whole point of the plugin, and waiting for someone to open the
        dashboard and press Start leaves them dark for the whole lesson.

        Nothing happens before the configuration exists, which is the state on
        a fresh install until the dashboard has been opened once — that first
        visit seeds the configuration and leaves the decision to the default.
        """
        try:
            from .models import NoiseMonitorConfig
            from core.server_process import is_server_process

            from .startup import start_monitoring

            if not is_server_process():
                # Only the server should hold the microphone. The service file
                # loads the plugins for its ExecStartPre too, and a meter that
                # comes up there dies with the command.
                return

            config = NoiseMonitorConfig.objects.filter(is_active=True).first()
            if not config:
                logger.info("No noise configuration yet, not auto-starting")
                return

            if not config.auto_start:
                logger.info("Auto-start is off, leaving the monitor stopped")
                return

            start_monitoring(config)
            logger.info("Noise monitoring auto-started")
        except Exception as e:
            # Never fatal: the plugin's URLs and models are already registered,
            # and the teacher can always press Start.
            logger.warning(f"Could not auto-start noise monitoring: {e}")

    def uninstall(self) -> None:
        """Cleanup GPIO pins and resources."""
        # Stop the noise monitoring service
        if self._service:
            from .noise_service import noise_service

            noise_service.stop_monitoring()

        self.cleanup_gpio_pins()
        logger.info(f"{self.name} plugin uninstalled")
