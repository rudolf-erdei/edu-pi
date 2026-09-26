"""Tests for the LCD Display plugin.

The regression these guard is a display that comes up on its side: opening the
LCD page used to write a configuration with rotation 0, and the next start read
that row back and initialised the panel from it.
"""

import contextlib
import inspect
import sys
from unittest import mock

from django.test import TestCase

from plugins.edupi.lcd_display.lcd_service import lcd_service
from plugins.edupi.lcd_display.models import LCDConfig
from plugins.edupi.lcd_display.mood import Mood

PAGE = "/plugins/edupi/lcd_display/"

FORM = {
    "rotation": 90,
    "backlight": 100,
    "contrast": 1.0,
    "show_smile_on_startup": "on",
}


class LCDConfigPageTest(TestCase):
    """Opening the page must not write configuration."""

    def test_visiting_the_page_creates_no_configuration(self):
        assert LCDConfig.objects.count() == 0

        self.client.get(PAGE)

        assert LCDConfig.objects.count() == 0

    def test_visiting_the_page_twice_creates_no_configuration(self):
        self.client.get(PAGE)
        self.client.get(PAGE)

        assert LCDConfig.objects.count() == 0

    def test_a_saved_rotation_is_shown(self):
        LCDConfig.objects.create(name="Default", rotation=180, backlight=100)

        content = self.client.get(PAGE).content.decode("utf-8")

        assert '<option value="180" selected>' in content

    def test_the_page_still_renders_without_a_configuration(self):
        response = self.client.get(PAGE)

        assert response.status_code == 200


class LCDConfigSaveTest(TestCase):
    """The page posts to itself, so the post has to be handled."""

    def test_saving_stores_the_rotation(self):
        response = self.client.post(
            PAGE,
            {
                "rotation": 180,
                "backlight": 80,
                "contrast": 1.0,
                "show_smile_on_startup": "on",
            },
        )

        assert response.status_code == 302
        config = LCDConfig.objects.get(name="Default")
        assert config.rotation == 180
        assert config.backlight == 80

    def test_saving_creates_the_configuration_on_a_fresh_system(self):
        assert LCDConfig.objects.count() == 0

        self.client.post(
            PAGE,
            {
                "rotation": 90,
                "backlight": 100,
                "contrast": 1.0,
                "show_smile_on_startup": "on",
            },
        )

        assert LCDConfig.objects.count() == 1

    def test_saving_twice_updates_rather_than_duplicates(self):
        payload = {
            "rotation": 90,
            "backlight": 100,
            "contrast": 1.0,
            "show_smile_on_startup": "on",
        }
        self.client.post(PAGE, payload)
        self.client.post(PAGE, {**payload, "rotation": 270})

        assert LCDConfig.objects.count() == 1
        assert LCDConfig.objects.get(name="Default").rotation == 270

    def test_an_invalid_rotation_is_refused(self):
        response = self.client.post(
            PAGE,
            {
                "rotation": 45,
                "backlight": 100,
                "contrast": 1.0,
                "show_smile_on_startup": "on",
            },
        )

        assert response.status_code == 200
        assert LCDConfig.objects.count() == 0

    def test_the_backlight_is_clamped(self):
        self.client.post(
            PAGE,
            {
                "rotation": 90,
                "backlight": 500,
                "contrast": 1.0,
                "show_smile_on_startup": "on",
            },
        )

        assert LCDConfig.objects.get(name="Default").backlight == 100


class BootInitializationTest(TestCase):
    """The panel comes up in the server, and nowhere else.

    The service file runs collectstatic as an ExecStartPre, so the plugins load
    in that process too. It used to initialize the panel, clear the screen and
    start the smiley thread there, and then the real process did it all again —
    two processes on the same SPI bus for the overlap.
    """

    UNDER_PYTEST = "core.server_process.running_under_pytest"

    def _plugin(self):
        from plugins.edupi.lcd_display.plugin import Plugin

        return Plugin(plugin_path="plugins/edupi/lcd_display")

    @contextlib.contextmanager
    def _as_server(self, server):
        argv = ["daphne"] if server else ["manage.py", "collectstatic"]
        with mock.patch(self.UNDER_PYTEST, return_value=False), mock.patch.object(
            sys, "argv", argv
        ):
            yield

    def test_the_server_initialises_the_panel(self):
        LCDConfig.objects.create(name="Default", rotation=180, backlight=100)
        plugin = self._plugin()

        with self._as_server(True), mock.patch.object(
            lcd_service, "initialize"
        ) as init, mock.patch.object(plugin, "_initialize_display") as boot:
            plugin.register()

            boot.assert_called_once()

    def test_collectstatic_leaves_the_panel_alone(self):
        LCDConfig.objects.create(name="Default", rotation=180, backlight=100)
        plugin = self._plugin()

        with self._as_server(False), mock.patch.object(
            plugin, "_initialize_display"
        ) as boot:
            plugin.register()

            assert boot.call_count == 0

    def test_a_test_run_leaves_the_panel_alone(self):
        plugin = self._plugin()

        with mock.patch.object(plugin, "_initialize_display") as boot:
            plugin.register()

            assert boot.call_count == 0

    def test_the_saved_rotation_is_used(self):
        LCDConfig.objects.create(name="Default", rotation=180, backlight=100)

        with mock.patch.object(lcd_service, "initialize") as init:
            self._plugin()._initialize_display(lcd_service, LCDConfig)

            init.assert_called_once_with(rotation=180, backlight=100)

    def test_an_already_running_panel_is_not_initialised_twice(self):
        with mock.patch.object(
            lcd_service, "is_initialized", return_value=True
        ), mock.patch.object(lcd_service, "initialize") as init:
            self._plugin()._initialize_display(lcd_service, LCDConfig)

            assert init.call_count == 0

    def test_a_configuration_is_not_required(self):
        """A fresh install has no row; the service default has to be usable."""
        with mock.patch.object(
            lcd_service, "is_initialized", return_value=False
        ), mock.patch.object(lcd_service, "initialize") as init:
            self._plugin()._initialize_display(lcd_service, LCDConfig)

            init.assert_called_once_with()


class RotationDefaultTest(TestCase):
    """The two defaults have to agree, because the panel boots from either.

    With no saved row the service defaults; with one it uses the row. These
    differing is what put the display on its side.
    """

    def test_the_model_defaults_to_landscape(self):
        assert LCDConfig._meta.get_field("rotation").default == 90

    def test_a_new_configuration_is_landscape(self):
        assert LCDConfig().rotation == 90

    def test_the_service_default_matches_the_model(self):
        default = inspect.signature(lcd_service.initialize).parameters["rotation"].default

        assert default == LCDConfig._meta.get_field("rotation").default


class RotationApplyTest(TestCase):
    """Saving a rotation has to reach the panel, not just the database.

    A rotation that only lands in a row is not shown until the next restart,
    which reads as a setting that does nothing.
    """

    @contextlib.contextmanager
    def _service(self, **overrides):
        """Stub the singleton so the panel need not exist."""
        returns = {
            "is_initialized": True,
            "get_current_mood": Mood.HAPPY,
            "is_animation_running": False,
        }
        returns.update(overrides)

        with contextlib.ExitStack() as stack:
            for name, value in returns.items():
                stack.enter_context(
                    mock.patch.object(lcd_service, name, return_value=value)
                )
            for name in (
                "stop_face_animation",
                "start_face_animation",
                "cleanup",
                "initialize",
                "set_mood",
            ):
                stack.enter_context(mock.patch.object(lcd_service, name))
            yield

    def test_changing_the_rotation_reinitialises_the_panel(self):
        LCDConfig.objects.create(name="Default", rotation=0, backlight=100)

        with self._service():
            self.client.post(PAGE, {**FORM, "rotation": 90})

            lcd_service.stop_face_animation.assert_called_once()
            lcd_service.cleanup.assert_called_once()
            lcd_service.initialize.assert_called_once_with(rotation=90, backlight=100)

    def test_the_mood_survives_the_rotation(self):
        LCDConfig.objects.create(name="Default", rotation=0, backlight=100)

        with self._service():
            self.client.post(PAGE, {**FORM, "rotation": 90})

            lcd_service.set_mood.assert_called_once_with(Mood.HAPPY)

    def test_the_animation_is_restarted_when_it_was_running(self):
        LCDConfig.objects.create(name="Default", rotation=0, backlight=100)

        with self._service(is_animation_running=True):
            self.client.post(PAGE, {**FORM, "rotation": 90})

            lcd_service.start_face_animation.assert_called_once()

    def test_an_unchanged_rotation_leaves_the_panel_alone(self):
        LCDConfig.objects.create(name="Default", rotation=90, backlight=100)

        with self._service():
            self.client.post(PAGE, {**FORM, "rotation": 90})

            lcd_service.cleanup.assert_not_called()
            lcd_service.initialize.assert_not_called()

    def test_a_stopped_panel_is_not_started_by_a_save(self):
        with self._service(is_initialized=False):
            self.client.post(PAGE, FORM)

            lcd_service.initialize.assert_not_called()
