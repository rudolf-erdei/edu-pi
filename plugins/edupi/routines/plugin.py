"""Routines Plugin - Text-to-Speech classroom routines.

Provides text-to-speech routines with USB presenter support for classroom activities.
"""

import logging
from typing import Optional

from core.plugin_system.base import PluginBase
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


class Plugin(PluginBase):
    """Routines Plugin implementation."""

    name = "Routines"
    description = (
        "Text-to-Speech classroom routines with USB presenter support for activities"
    )
    author = "Tinko Team"
    version = "1.0.0"
    icon = "microphone"
    requires = ["plugins.edupi.lcd_display"]

    def __init__(self, plugin_path: str, enabled: bool = True):
        super().__init__(plugin_path, enabled)
        self._presenter_started = False

    def boot(self) -> None:
        """Initialize the plugin."""
        from .services.presenter_handler import (
            presenter_handler,
            connect_presenter_signals,
        )

        # Start USB presenter monitoring
        if presenter_handler.is_available():
            connect_presenter_signals()
            presenter_handler.start_monitoring()
            self._presenter_started = True
            logger.info(f"{self.name} plugin booted - USB presenter monitoring started")
        else:
            logger.warning(f"{self.name} plugin booted - USB presenter unavailable")

    def register(self) -> None:
        """Register models, URLs, and admin menus."""
        from django.urls import include, path

        from .models import (
            RoutineCategory,
            Routine,
            RoutineSession,
            PresenterButtonMapping,
        )

        # Register models
        self.register_model(RoutineCategory)
        self.register_model(Routine)
        self.register_model(RoutineSession)
        self.register_model(PresenterButtonMapping)

        # Try to create default data, but don't fail if tables don't exist yet
        try:
            self._create_default_categories()
            self._create_default_button_mapping()
            self._create_prebuilt_routines()
        except Exception as e:
            logger.warning(
                f"Could not create default data (tables may not exist yet): {e}"
            )

        # Register URLs
        self.register_url_pattern(
            "", include("plugins.edupi.routines.urls"), name="routines"
        )

        # Register admin menu
        self.register_admin_menu(
            _("Routines"), "/plugins/edupi/routines/", icon="microphone"
        )

        # Register settings
        self.register_setting(
            "default_tts_engine",
            _("Default TTS Engine"),
            default="pyttsx3",
            field_type="select",
            choices=[
                ("pyttsx3", _("System TTS (Offline)")),
                ("edge_tts", _("Edge TTS (High Quality)")),
                ("gtts", _("Google TTS (Online)")),
            ],
            help_text=_("Default text-to-speech engine"),
        )
        self.register_setting(
            "default_tts_speed",
            _("Default TTS Speed"),
            default=1.0,
            field_type="number",
            min=0.5,
            max=2.0,
            step=0.1,
            help_text=_("Default speech speed (0.5 = slow, 1.0 = normal, 2.0 = fast)"),
        )
        self.register_setting(
            "default_language",
            _("Default Language"),
            default="en",
            field_type="text",
            help_text=_("Default language code (e.g., 'en', 'ro')"),
        )
        self.register_setting(
            "enable_presenter",
            _("Enable USB Presenter"),
            default=True,
            field_type="boolean",
            help_text=_("Allow USB presenter control"),
        )

        logger.info(f"{self.name} plugin registered")

    def _create_default_categories(self) -> None:
        """Create default routine categories."""
        from .models import RoutineCategory

        categories = [
            {
                "category_type": RoutineCategory.CategoryType.WARM_UP,
                "name": "Warm-up",
                "description": "Routines to warm up before activities",
                "display_color": "#F59E0B",  # Amber
                "order": 1,
            },
            {
                "category_type": RoutineCategory.CategoryType.TRANSITION,
                "name": "Transition",
                "description": "Routines for transitioning between activities",
                "display_color": "#3B82F6",  # Blue
                "order": 2,
            },
            {
                "category_type": RoutineCategory.CategoryType.COOLDOWN,
                "name": "Cooldown",
                "description": "Routines to cool down after activities",
                "display_color": "#10B981",  # Emerald
                "order": 3,
            },
        ]

        for cat_data in categories:
            RoutineCategory.objects.get_or_create(
                category_type=cat_data["category_type"],
                defaults=cat_data,
            )

        logger.info("Default routine categories created")

    def _create_default_button_mapping(self) -> None:
        """Create default presenter button mapping."""
        from .models import PresenterButtonMapping

        PresenterButtonMapping.objects.get_or_create(
            is_default=True,
            defaults={
                "name": "Default",
                "next_button_code": 115,  # KEY_VOLUMEUP
                "prev_button_code": 114,  # KEY_VOLUMEDOWN
                "play_pause_button_code": 164,  # KEY_PLAYPAUSE
                "stop_button_code": 116,  # KEY_POWER
                "is_active": True,
            },
        )

        logger.info("Default button mapping created")

    def _create_prebuilt_routines(self) -> None:
        """Create pre-built routines."""
        from django.utils.translation import gettext as _
        from .models import Routine, RoutineCategory

        # Hand Warming Routine
        warm_up_category = RoutineCategory.objects.filter(
            category_type=RoutineCategory.CategoryType.WARM_UP
        ).first()

        if warm_up_category:
            Routine.objects.get_or_create(
                title="Hand Warming Exercise",
                defaults={
                    "content": _(
                        "Let's warm up our hands for writing!\n"
                        "Rub your palms together, rub, rub, rub.\n"
                        "Now your fingers, wiggle them up high.\n"
                        "Shake them out, shake, shake, shake.\n"
                        "Ready to write, nice and warm!"
                    ),
                    "category": warm_up_category,
                    "tts_engine": Routine.TTSEngine.PYTTSX3,
                    "tts_speed": 0.9,
                    "tts_language": "en",
                    "is_pre_built": True,
                    "is_active": True,
                },
            )

            Routine.objects.get_or_create(
                title="Finger Stretch",
                defaults={
                    "content": _(
                        "Let's stretch our fingers!\n"
                        "Hold up your hands and spread your fingers wide.\n"
                        "Now make tight fists, squeeze, squeeze, squeeze.\n"
                        "Open your hands wide again.\n"
                        "Wiggle your fingers like they're dancing.\n"
                        "Your fingers are ready to write!"
                    ),
                    "category": warm_up_category,
                    "tts_engine": Routine.TTSEngine.PYTTSX3,
                    "tts_speed": 0.9,
                    "tts_language": "en",
                    "is_pre_built": True,
                    "is_active": True,
                },
            )

        # Deep Breathing Routine
        transition_category = RoutineCategory.objects.filter(
            category_type=RoutineCategory.CategoryType.TRANSITION
        ).first()

        if transition_category:
            Routine.objects.get_or_create(
                title="Deep Breathing",
                defaults={
                    "content": _(
                        "Let's take a moment to breathe.\n"
                        "Breathe in slowly through your nose...\n"
                        "Hold it...\n"
                        "Now breathe out through your mouth...\n"
                        "One more time.\n"
                        "Breathe in...\n"
                        "And out...\n"
                        "You're ready to focus."
                    ),
                    "category": transition_category,
                    "tts_engine": Routine.TTSEngine.PYTTSX3,
                    "tts_speed": 0.7,
                    "tts_language": "en",
                    "is_pre_built": True,
                    "is_active": True,
                },
            )

        logger.info("Pre-built routines created")

    def uninstall(self) -> None:
        """Cleanup resources."""
        from .services.presenter_handler import presenter_handler

        # Stop presenter monitoring
        if self._presenter_started:
            presenter_handler.stop_monitoring()

        logger.info(f"{self.name} plugin uninstalled")
