"""Activity Timer Plugin.

Provides a countdown timer for classroom activities with visual feedback
via RGB LED showing remaining time.
"""

import logging
from typing import Optional

from core.plugin_system.base import PluginBase

logger = logging.getLogger(__name__)


class Plugin(PluginBase):
    """Activity Timer Plugin implementation."""

    name = "Activity Timer"
    description = (
        "Visual countdown timer for classroom activities with RGB LED feedback"
    )
    author = "Tinko Team"
    version = "1.0.0"
    icon = "clock"

    def __init__(self, plugin_path: str, enabled: bool = True):
        super().__init__(plugin_path, enabled)
        self._timer = None

    def boot(self) -> None:
        """Initialize the plugin and register GPIO pins."""
        # Register GPIO pins for RGB LED
        self.register_gpio_pins(
            {
                "led_red": 17,  # Pin 11
                "led_green": 27,  # Pin 13
                "led_blue": 22,  # Pin 15
            }
        )

        # Register GPIO pin for buzzer (optional)
        self.register_gpio_pins(
            {
                "buzzer": 24,  # Pin 18
            }
        )

        logger.info(f"{self.name} plugin booted - GPIO pins registered")

    def register(self) -> None:
        """Register models, URLs, and admin menus."""
        from django.urls import include, path

        from .models import TimerConfig, TimerSession

        # Register models
        self.register_model(TimerConfig)
        self.register_model(TimerSession)

        # Register URLs using include
        self.register_url_pattern(
            "", include("plugins.edupi.activity_timer.urls"), name="activity_timer"
        )

        # Register admin menu
        self.register_admin_menu(
            "Activity Timer", "/plugins/edupi/activity_timer/", icon="clock"
        )

        # Register settings
        self.register_setting(
            "default_duration",
            "Default Duration (minutes)",
            default=10,
            field_type="number",
            min=1,
            max=120,
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
            "warning_threshold",
            "Warning Threshold (%)",
            default=20,
            field_type="number",
            min=5,
            max=50,
            help_text="Percentage of time remaining when LED turns yellow",
        )
        self.register_setting(
            "enable_buzzer",
            "Enable Buzzer",
            default=True,
            field_type="boolean",
        )

        logger.info(f"{self.name} plugin registered")

    def uninstall(self) -> None:
        """Cleanup GPIO pins and resources."""
        self.cleanup_gpio_pins()
        logger.info(f"{self.name} plugin uninstalled")
