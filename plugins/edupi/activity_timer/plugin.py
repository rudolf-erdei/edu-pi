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
    requires = ["plugins.edupi.lcd_display"]

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
        # Moved from GPIO 24 to GPIO 3 to avoid conflict with LCD display
        self.register_gpio_pins(
            {
                "buzzer": 3,  # Pin 5
            }
        )

        logger.info(f"{self.name} plugin booted - GPIO pins registered")

    def register(self) -> None:
        """Register models, URLs, and admin menus."""
        from django.urls import include, path

        from .models import TimerPreset, TimerConfig, TimerSession

        # Register models
        self.register_model(TimerPreset)
        self.register_model(TimerConfig)
        self.register_model(TimerSession)

        # Create default presets if they don't exist
        self._create_default_presets()

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

    def _create_default_presets(self) -> None:
        """Create default timer presets if they don't exist."""
        from django.utils.translation import gettext as _
        from .models import TimerPreset

        presets = [
            {
                "preset_type": TimerPreset.PresetType.MINUTE_OF_SILENCE,
                "name": _("Minute of Silence"),
                "description": _(
                    "60 seconds of silence to calm down and prepare mentally"
                ),
                "duration_minutes": 1,
                "display_color": "#6366F1",  # Indigo
                "led_color_start": "#60A5FA",  # Light blue
                "led_color_warning": "#3B82F6",  # Blue
                "led_color_end": "#1E40AF",  # Dark blue
                "enable_breathing": True,
                "enable_ambient_sound": True,
                "ambient_sound_type": "nature",
                "announce_start": True,
                "announce_end": True,
                "start_message": _("Minute of silence begins now"),
                "end_message": _("Time's up"),
            },
            {
                "preset_type": TimerPreset.PresetType.BREAK_TIME,
                "name": _("Break Time"),
                "description": _("Standard break between activities"),
                "duration_minutes": 10,
                "display_color": "#10B981",  # Emerald
                "led_color_start": "#00FF00",
                "led_color_warning": "#FFFF00",
                "led_color_end": "#FF0000",
                "enable_breathing": False,
                "enable_ambient_sound": False,
                "announce_start": False,
                "announce_end": False,
            },
            {
                "preset_type": TimerPreset.PresetType.ACTIVITY,
                "name": _("Activity Timer"),
                "description": _("General classroom activity"),
                "duration_minutes": 30,
                "display_color": "#F59E0B",  # Amber
                "led_color_start": "#00FF00",
                "led_color_warning": "#FFFF00",
                "led_color_end": "#FF0000",
                "enable_breathing": False,
                "enable_ambient_sound": False,
                "announce_start": False,
                "announce_end": False,
            },
        ]

        for preset_data in presets:
            TimerPreset.objects.get_or_create(
                preset_type=preset_data["preset_type"], defaults=preset_data
            )

        logger.info("Default timer presets created")

    def uninstall(self) -> None:
        """Cleanup GPIO pins and resources."""
        self.cleanup_gpio_pins()
        logger.info(f"{self.name} plugin uninstalled")
