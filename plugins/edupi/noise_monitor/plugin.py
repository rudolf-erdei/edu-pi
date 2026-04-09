"""Noise Monitor Plugin.

Provides continuous classroom noise monitoring with visual feedback via RGB LEDs
to help students self-regulate their volume levels.
"""

import logging
from typing import Optional

from core.plugin_system.base import PluginBase

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
        # Register GPIO pins for TWO RGB LEDs
        # LED 1: Instant noise (10-second average)
        self.register_gpio_pins(
            {
                "instant_red": 5,  # Pin 29
                "instant_green": 6,  # Pin 31
                "instant_blue": 13,  # Pin 33
            }
        )

        # LED 2: Session average (5-10 minute average)
        self.register_gpio_pins(
            {
                "session_red": 19,  # Pin 35
                "session_green": 26,  # Pin 37
                "session_blue": 16,  # Pin 36
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
            "Noise Monitor", "/plugins/edupi/noise_monitor/", icon="volume-2"
        )

        # Register settings
        self.register_setting(
            "instant_window_seconds",
            "Instant Average Window (seconds)",
            default=10,
            field_type="number",
            min=5,
            max=60,
            help_text="Time window for instant noise average calculation",
        )
        self.register_setting(
            "session_window_minutes",
            "Session Average Window (minutes)",
            default=5,
            field_type="number",
            min=1,
            max=30,
            help_text="Time window for session noise average calculation",
        )
        self.register_setting(
            "led_brightness",
            "LED Brightness (%)",
            default=100,
            field_type="number",
            min=10,
            max=100,
        )
        self.register_setting(
            "enable_monitoring",
            "Enable Noise Monitoring",
            default=True,
            field_type="boolean",
            help_text="Start monitoring when plugin is enabled",
        )

        # Load device config if available
        self._load_device_config()

        logger.info(f"{self.name} plugin registered")

    def _load_device_config(self) -> None:
        """Load saved device configuration into the service."""
        try:
            from .models import NoiseMonitorConfig
            from .noise_service import noise_service

            config = NoiseMonitorConfig.objects.filter(is_active=True).first()
            if config and config.audio_input_device_index is not None:
                noise_service.set_device(
                    config.audio_input_device_index,
                    config.audio_input_device
                )
                logger.info(f"Loaded device config: {config.audio_input_device}")
        except Exception as e:
            logger.warning(f"Could not load device config: {e}")

    def uninstall(self) -> None:
        """Cleanup GPIO pins and resources."""
        # Stop the noise monitoring service
        if self._service:
            from .noise_service import noise_service

            noise_service.stop_monitoring()

        self.cleanup_gpio_pins()
        logger.info(f"{self.name} plugin uninstalled")
