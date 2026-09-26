"""Tests for Noise Monitor plugin."""

import contextlib
import sys
from datetime import timedelta
from unittest import mock

import pytest
from django.test import TestCase
from django.utils import timezone

from plugins.edupi.noise_monitor.models import (
    NoiseProfile,
    NoiseMonitorConfig,
    NoiseReading,
)
from plugins.edupi.noise_monitor.noise_service import READING_SAVE_INTERVAL_SECONDS
from plugins.edupi.noise_monitor.views import CHART_WINDOW_MINUTES, chart_reading_count


class NoiseProfileTests(TestCase):
    """Tests for NoiseProfile model."""

    def test_profile_creation(self):
        """Test creating a noise profile."""
        profile = NoiseProfile.objects.create(
            profile_type=NoiseProfile.ProfileType.TEACHING,
            name="Test Profile",
            description="Test description",
            yellow_threshold=40,
            red_threshold=70,
        )

        assert profile.name == "Test Profile"
        assert profile.yellow_threshold == 40
        assert profile.red_threshold == 70
        assert str(profile) == "Test Profile (Teaching - Moderate Noise)"

    def test_get_color_for_level(self):
        """Test color determination for noise levels."""
        profile = NoiseProfile.objects.create(
            profile_type=NoiseProfile.ProfileType.TEACHING,
            name="Test",
            yellow_threshold=40,
            red_threshold=70,
        )

        assert profile.get_color_for_level(30) == "green"
        assert profile.get_color_for_level(40) == "yellow"
        assert profile.get_color_for_level(50) == "yellow"
        assert profile.get_color_for_level(70) == "red"
        assert profile.get_color_for_level(80) == "red"


class NoiseMonitorConfigTests(TestCase):
    """Tests for NoiseMonitorConfig model."""

    def test_config_creation(self):
        """Test creating a config."""
        profile = NoiseProfile.objects.create(
            profile_type=NoiseProfile.ProfileType.TEACHING,
            name="Test",
            yellow_threshold=40,
            red_threshold=70,
        )

        config = NoiseMonitorConfig.objects.create(
            name="Test Config",
            profile=profile,
            instant_window_seconds=10,
            session_window_minutes=5,
            led_brightness=100,
        )

        assert config.name == "Test Config"
        assert config.instant_window_seconds == 10
        assert config.get_session_window_seconds() == 300

    def test_default_config_uniqueness(self):
        """Test that only one config can be default."""
        profile = NoiseProfile.objects.create(
            profile_type=NoiseProfile.ProfileType.TEACHING,
            name="Test",
            yellow_threshold=40,
            red_threshold=70,
        )

        config1 = NoiseMonitorConfig.objects.create(
            name="Config 1",
            profile=profile,
            is_default=True,
        )

        config2 = NoiseMonitorConfig.objects.create(
            name="Config 2",
            profile=profile,
            is_default=True,
        )

        config1.refresh_from_db()
        assert not config1.is_default
        assert config2.is_default


class NoiseReadingTests(TestCase):
    """Tests for NoiseReading model."""

    def test_reading_creation(self):
        """Test creating a noise reading."""
        profile = NoiseProfile.objects.create(
            profile_type=NoiseProfile.ProfileType.TEACHING,
            name="Test",
            yellow_threshold=40,
            red_threshold=70,
        )

        config = NoiseMonitorConfig.objects.create(
            name="Test Config",
            profile=profile,
        )

        reading = NoiseReading.objects.create(
            config=config,
            raw_level=50,
            instant_average=45,
            session_average=40,
            instant_color="yellow",
            session_color="green",
        )

        assert reading.instant_average == 45
        assert reading.session_average == 40
        assert reading.get_instant_color_display() == "#FFFF00"
        assert reading.get_session_color_display() == "#00FF00"


class AudioDevicesAPITest(TestCase):
    """Tests for the audio devices API endpoint."""

    def test_audio_devices_api_returns_json(self):
        """Test that the API returns valid JSON."""
        from django.test import Client

        client = Client()
        response = client.get("/plugins/edupi/noise_monitor/api/audio-devices/")

        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "devices" in data

    def test_audio_devices_api_structure(self):
        """Test that device list has correct structure."""
        from django.test import Client

        client = Client()
        response = client.get("/plugins/edupi/noise_monitor/api/audio-devices/")

        data = response.json()
        if data["success"] and data["devices"]:
            device = data["devices"][0]
            assert "index" in device
            assert "name" in device
            assert "channels" in device


class NoiseServiceDeviceTest(TestCase):
    """Tests for noise service device selection."""

    def test_set_device_to_none_uses_default(self):
        """Test that setting device to None uses system default."""
        from plugins.edupi.noise_monitor.noise_service import noise_service, DEVICE_STATUS_DEFAULT

        noise_service.set_device(None)
        assert noise_service._device_index is None
        assert noise_service._device_status == DEVICE_STATUS_DEFAULT

    def test_set_device_stores_name(self):
        """Test that device name is stored."""
        from plugins.edupi.noise_monitor.noise_service import noise_service, DEVICE_STATUS_CONNECTED

        noise_service.set_device(0, "Test Microphone")
        assert noise_service._device_index == 0
        assert noise_service._device_name == "Test Microphone"
        assert noise_service._device_status == DEVICE_STATUS_CONNECTED

    def test_get_device_status_returns_dict(self):
        """Test that get_device_status returns proper dict."""
        from plugins.edupi.noise_monitor.noise_service import noise_service

        noise_service.set_device(1, "USB Mic")
        status = noise_service.get_device_status()

        assert isinstance(status, dict)
        # The configured selection is reported, plus what is actually open.
        # They differ while the selection is automatic, or once ALSA has
        # renumbered the cards under a saved index.
        assert status["configured_device_index"] == 1
        assert status["configured_device_name"] == "USB Mic"
        assert "device_index" in status
        assert "device_name" in status
        assert "device_status" in status

    def test_get_current_levels_includes_device_status(self):
        """Test that get_current_levels includes device info."""
        from plugins.edupi.noise_monitor.noise_service import noise_service

        noise_service.set_device(2, "Another Mic")
        levels = noise_service.get_current_levels()

        assert "device_status" in levels
        assert "device_name" in levels
        assert levels["device_name"] == "Another Mic"


class AutoStartTest(TestCase):
    """The monitor comes up on its own when the Pi is switched on."""

    START = "plugins.edupi.noise_monitor.startup.start_monitoring"
    UNDER_PYTEST = "core.server_process.running_under_pytest"

    def _plugin(self):
        from plugins.edupi.noise_monitor.plugin import Plugin

        return Plugin(plugin_path="plugins/edupi/noise_monitor")

    def _config(self, **kwargs):
        return NoiseMonitorConfig.objects.create(
            name="Default", is_default=True, **kwargs
        )

    @contextlib.contextmanager
    def _as_server(self):
        """Pretend this process is the service rather than a test run."""
        with mock.patch(self.UNDER_PYTEST, return_value=False):
            yield

    @mock.patch(START)
    def test_a_configured_pi_starts_monitoring_on_its_own(self, start):
        self._config()

        with self._as_server():
            self._plugin()._autostart_monitoring()

        assert start.call_count == 1

    @mock.patch(START)
    def test_switching_auto_start_off_keeps_the_meter_dark(self, start):
        self._config(auto_start=False)

        with self._as_server():
            self._plugin()._autostart_monitoring()

        assert start.call_count == 0

    @mock.patch(START)
    def test_nothing_happens_before_anything_is_configured(self, start):
        """A fresh install has no settings row until the dashboard is opened."""
        with self._as_server():
            self._plugin()._autostart_monitoring()

        assert start.call_count == 0

    @mock.patch(START)
    def test_a_failure_to_start_does_not_escape(self, start):
        """The plugin's URLs and models are already registered by then."""
        start.side_effect = RuntimeError("no sound card")
        self._config()

        with self._as_server():
            self._plugin()._autostart_monitoring()

    @mock.patch("plugins.edupi.noise_monitor.views.start_configured_monitoring")
    def test_the_start_button_starts_the_same_way(self, start):
        self._config()

        self.client.post("/plugins/edupi/noise_monitor/control/", {"action": "start"})

        assert start.call_count == 1

    @mock.patch(START)
    def test_a_batch_command_does_not_take_the_microphone(self, start):
        """collectstatic runs as an ExecStartPre, in a process that exits."""
        self._config()

        with mock.patch.object(sys, "argv", ["manage.py", "collectstatic"]):
            with self._as_server():
                self._plugin()._autostart_monitoring()

        assert start.call_count == 0

    @mock.patch(START)
    def test_the_server_itself_does_start(self, start):
        """daphne is not a management command at all."""
        self._config()

        with mock.patch.object(
            sys,
            "argv",
            ["daphne", "-b", "0.0.0.0", "-p", "80", "config.asgi:application"],
        ):
            with self._as_server():
                self._plugin()._autostart_monitoring()

        assert start.call_count == 1

    def test_a_test_run_does_not_take_the_microphone(self):
        """A test run is not the server, though its command line looks like one.

        ``pytest plugins/.../tests.py`` has a test path where the server has a
        management command, so the batch list never matched it and every test
        session started a real monitor thread at Django setup — against the
        real database, still sampling while the suite ran.
        """
        from core.server_process import is_server_process

        assert is_server_process() is False


class ReadingHistoryTest(TestCase):
    """Readings are written on an interval, not on every sample."""

    def _service(self, persist):
        from plugins.edupi.noise_monitor.noise_service import noise_service

        noise_service._persist = persist
        noise_service._last_persist_at = None
        noise_service._instant_average = 42
        noise_service._session_average = 38
        noise_service._instant_color = "yellow"
        noise_service._session_color = "green"
        return noise_service

    def setUp(self):
        self.config = NoiseMonitorConfig.objects.create(
            name="Default", is_default=True
        )

    def _stamp(self, seconds):
        return timezone.now() + timedelta(seconds=seconds)

    def test_the_first_reading_is_stored_at_once(self):
        service = self._service(persist=True)

        service._persist_reading(self._stamp(0))

        assert NoiseReading.objects.count() == 1
        reading = NoiseReading.objects.get()
        assert reading.instant_average == 42
        assert reading.session_color == "green"

    def test_a_reading_inside_the_interval_is_skipped(self):
        """10 Hz sampling would otherwise be 36,000 rows an hour."""
        service = self._service(persist=True)

        service._persist_reading(self._stamp(0))
        service._persist_reading(self._stamp(1))
        service._persist_reading(self._stamp(4))

        assert NoiseReading.objects.count() == 1

    def test_a_reading_after_the_interval_is_stored(self):
        service = self._service(persist=True)

        service._persist_reading(self._stamp(0))
        service._persist_reading(self._stamp(6))

        assert NoiseReading.objects.count() == 2

    def test_nothing_is_stored_when_history_is_not_wanted(self):
        service = self._service(persist=False)

        service._persist_reading(self._stamp(0))
        service._persist_reading(self._stamp(60))

        assert NoiseReading.objects.count() == 0

    def test_no_configuration_means_no_history(self):
        NoiseMonitorConfig.objects.all().delete()
        service = self._service(persist=True)

        service._persist_reading(self._stamp(0))

        assert NoiseReading.objects.count() == 0


class AutoStartSettingTest(TestCase):
    """The auto-start switch on the configuration page."""

    CONFIG = "/plugins/edupi/noise_monitor/config/"

    def setUp(self):
        self.profile = NoiseProfile.objects.create(
            profile_type=NoiseProfile.ProfileType.TEACHING,
            name="Teaching",
            yellow_threshold=40,
            red_threshold=70,
        )
        self.config = NoiseMonitorConfig.objects.create(
            name="Default", profile=self.profile, is_default=True
        )

    def _form(self):
        content = self.client.get(self.CONFIG).content.decode("utf-8")
        marker = 'action="/plugins/edupi/noise_monitor/config/"'
        start = content.index(marker)
        return content[start : content.index("</form>", start)]

    def test_the_switch_is_on_by_default(self):
        assert self.config.auto_start is True

    def test_the_switch_shows_what_is_saved(self):
        self.config.auto_start = False
        self.config.save()

        assert 'name="auto_start"' in self._form()
        assert "checked" not in self._form()

    def test_switching_it_off_is_saved(self):
        payload = {
            "profile": self.profile.pk,
            "instant_window_seconds": 10,
            "session_window_minutes": 5,
            "led_brightness": 100,
        }

        self.client.post(self.CONFIG, payload)

        self.config.refresh_from_db()
        assert self.config.auto_start is False

    def test_resubmitting_the_rendered_page_keeps_it_off(self):
        """An unticked checkbox posts nothing, so the form must not default it back on."""
        self.config.auto_start = False
        self.config.save()

        content = self.client.get(self.CONFIG).content.decode("utf-8")
        assert 'name="auto_start"' in content

        payload = {
            "profile": self.profile.pk,
            "instant_window_seconds": 10,
            "session_window_minutes": 5,
            "led_brightness": 100,
            "audio_input_device": "",
            "audio_input_device_index": "",
        }
        self.client.post(self.CONFIG, payload)

        self.config.refresh_from_db()
        assert self.config.auto_start is False


class NoiseFaceTest(TestCase):
    """The robot face shows what the session LED shows.

    Patched on the display module's own attribute, because the service imports
    it inside the call so the monitor still runs without a display.
    """

    LCD = "plugins.edupi.lcd_display.lcd_service.lcd_service"

    def _service(self, session_color):
        from plugins.edupi.noise_monitor.noise_service import noise_service

        # The service is a singleton shared with the other tests, so the face
        # state is reset rather than assumed.
        noise_service._session_color = session_color
        noise_service._last_face_color = None
        return noise_service

    @mock.patch(LCD)
    def test_a_quiet_session_is_a_happy_face(self, lcd):
        lcd.is_initialized.return_value = True
        lcd.set_mood_by_name.return_value = True

        self._service("green")._update_face()

        lcd.set_mood_by_name.assert_called_once_with("happy")

    @mock.patch(LCD)
    def test_a_moderately_noisy_session_is_a_neutral_face(self, lcd):
        lcd.is_initialized.return_value = True
        lcd.set_mood_by_name.return_value = True

        self._service("yellow")._update_face()

        lcd.set_mood_by_name.assert_called_once_with("neutral")

    @mock.patch(LCD)
    def test_a_noisy_session_is_a_sad_face(self, lcd):
        lcd.is_initialized.return_value = True
        lcd.set_mood_by_name.return_value = True

        self._service("red")._update_face()

        lcd.set_mood_by_name.assert_called_once_with("sad")

    @mock.patch(LCD)
    def test_the_face_is_not_redrawn_while_the_colour_holds(self, lcd):
        """Each redraw is a full panel write, and the loop runs at 10 Hz."""
        lcd.is_initialized.return_value = True
        lcd.set_mood_by_name.return_value = True
        service = self._service("yellow")

        service._update_face()
        service._update_face()
        service._update_face()

        assert lcd.set_mood_by_name.call_count == 1

    @mock.patch(LCD)
    def test_a_colour_change_redraws_the_face(self, lcd):
        lcd.is_initialized.return_value = True
        lcd.set_mood_by_name.return_value = True
        service = self._service("green")

        service._update_face()
        service._session_color = "red"
        service._update_face()

        assert lcd.set_mood_by_name.call_args_list == [
            mock.call("happy"),
            mock.call("sad"),
        ]

    @mock.patch(LCD)
    def test_an_uninitialized_display_is_retried_not_remembered(self, lcd):
        """The panel can come up after monitoring has started."""
        lcd.is_initialized.return_value = False
        service = self._service("red")

        service._update_face()
        assert lcd.set_mood_by_name.call_count == 0

        lcd.is_initialized.return_value = True
        lcd.set_mood_by_name.return_value = True
        service._update_face()

        lcd.set_mood_by_name.assert_called_once_with("sad")

    @mock.patch(LCD)
    def test_stopping_the_monitor_gives_the_face_back(self, lcd):
        """Otherwise the robot is left looking sad with nothing running."""
        lcd.is_initialized.return_value = True
        lcd.set_mood_by_name.return_value = True
        service = self._service("red")
        service._is_monitoring = True
        service._monitor_thread = None

        service.stop_monitoring()

        assert lcd.set_mood_by_name.call_args_list[-1] == mock.call("happy")

    def test_no_display_at_all_is_not_an_error(self):
        """The monitor must run with the display plugin absent.

        A None in ``sys.modules`` is how an import is made to fail, which is
        what the plugin being disabled would look like here.
        """
        service = self._service("red")

        with mock.patch.dict(
            sys.modules, {"plugins.edupi.lcd_display.lcd_service": None}
        ):
            service._update_face()

        assert service._last_face_color is None


class MicrophoneConfigViewTest(TestCase):
    """Tests for how the configuration pages carry the microphone choice."""

    DASHBOARD = "/plugins/edupi/noise_monitor/"
    CONFIG = "/plugins/edupi/noise_monitor/config/"

    def test_custom_threshold_form_has_no_microphone_fields(self):
        """The microphone belongs to the profile form.

        Both forms are on the same page. While the custom form carried the
        fields too, submitting it posted an empty device and reset the
        microphone to automatic.
        """
        from plugins.edupi.noise_monitor.forms import CustomThresholdForm

        form = CustomThresholdForm()

        assert "audio_input_device" not in form.fields
        assert "audio_input_device_index" not in form.fields

    def test_profile_form_shows_the_saved_microphone(self):
        from plugins.edupi.noise_monitor.models import NoiseMonitorConfig

        NoiseMonitorConfig.objects.create(
            name="Default",
            is_default=True,
            audio_input_device="USB PnP Sound Device: Audio (hw:1,0)",
            audio_input_device_index=1,
        )

        response = self.client.get(self.CONFIG)

        assert response.status_code == 200
        assert b'value="1"' in response.content, "saved index must be pre-filled"
        assert b"USB PnP Sound Device" in response.content

    def test_dashboard_renders_a_microphone_state(self):
        response = self.client.get(self.DASHBOARD)

        assert response.status_code == 200
        assert b"mic-banner" in response.content


class CustomThresholdConfigTest(TestCase):
    """Saving a custom configuration has to survive the next page load.

    The form was rendered from the field defaults rather than from the stored
    configuration, so the saved name never appeared again — and pressing the
    button without changing anything wrote "Custom Configuration" and 40/70
    back over whatever the teacher had set.
    """

    CONFIG = "/plugins/edupi/noise_monitor/config/"
    CUSTOM = "/plugins/edupi/noise_monitor/config/custom/"
    STANDALONE = "/plugins/edupi/noise_monitor/config/custom/"

    SAVED = {
        "name": "My Quiet Room",
        "yellow_threshold": 35,
        "red_threshold": 65,
        "instant_window_seconds": 15,
        "session_window_minutes": 8,
        "led_brightness": 60,
    }

    def _custom_form(self, content):
        """The custom form's own markup.

        Both forms sit on the configuration page and share three field names
        (instant window, session window, brightness), so a search over the whole
        page finds the profile form's copy first.
        """
        marker = 'action="/plugins/edupi/noise_monitor/config/custom/"'
        start = content.index(marker)
        return content[start : content.index("</form>", start)]

    def _field(self, content, name):
        import re

        match = re.search(
            r'<input[^>]*name="%s"[^>]*value="([^"]*)"' % name,
            self._custom_form(content),
        )
        return match.group(1) if match else None

    def test_the_saved_name_and_thresholds_come_back(self):
        self.client.post(self.CUSTOM, self.SAVED)

        content = self.client.get(self.CONFIG).content.decode("utf-8")

        assert self._field(content, "name") == "My Quiet Room"
        assert self._field(content, "yellow_threshold") == "35"
        assert self._field(content, "red_threshold") == "65"
        assert self._field(content, "instant_window_seconds") == "15"
        assert self._field(content, "session_window_minutes") == "8"
        assert self._field(content, "led_brightness") == "60"

    def test_resubmitting_the_rendered_form_keeps_the_saved_values(self):
        """The no-op visit that used to erase the configuration."""
        from plugins.edupi.noise_monitor.models import NoiseMonitorConfig

        self.client.post(self.CUSTOM, self.SAVED)
        content = self.client.get(self.CONFIG).content.decode("utf-8")

        resubmitted = {
            key: self._field(content, key)
            for key in self.SAVED
        }
        self.client.post(self.CUSTOM, resubmitted)

        config = NoiseMonitorConfig.objects.get(is_default=True)
        assert config.name == "My Quiet Room"
        assert config.profile.yellow_threshold == 35
        assert config.profile.red_threshold == 65
        assert config.instant_window_seconds == 15
        assert config.session_window_minutes == 8
        assert config.led_brightness == 60

    def test_the_standalone_page_is_prefilled_too(self):
        self.client.post(self.CUSTOM, self.SAVED)

        content = self.client.get(self.STANDALONE).content.decode("utf-8")

        assert self._field(content, "name") == "My Quiet Room"
        assert self._field(content, "yellow_threshold") == "35"


class ProfileFormRoundTripTest(TestCase):
    """Applying the profile form must not reset what is already configured.

    It rendered the field defaults (10/5/100 and the first profile) whatever
    was stored, so pressing "Apply Profile" without changing anything rewrote
    the windows, the brightness and the profile.
    """

    CONFIG = "/plugins/edupi/noise_monitor/config/"
    CUSTOM = "/plugins/edupi/noise_monitor/config/custom/"

    SAVED = {
        "name": "My Quiet Room",
        "yellow_threshold": 35,
        "red_threshold": 65,
        "instant_window_seconds": 15,
        "session_window_minutes": 8,
        "led_brightness": 60,
    }

    def _profile_form_html(self, content):
        marker = 'action="/plugins/edupi/noise_monitor/config/"'
        start = content.index(marker)
        return content[start : content.index("</form>", start)]

    def _value(self, content, name):
        import re

        match = re.search(
            r'name="%s"[^>]*value="([^"]*)"' % name,
            self._profile_form_html(content),
        )
        return match.group(1) if match else None

    def test_the_form_shows_the_saved_windows_and_brightness(self):
        self.client.post(self.CUSTOM, self.SAVED)

        content = self.client.get(self.CONFIG).content.decode("utf-8")

        assert self._value(content, "instant_window_seconds") == "15"
        assert self._value(content, "session_window_minutes") == "8"
        assert self._value(content, "led_brightness") == "60"

    def test_the_saved_profile_is_the_selected_option(self):
        self.client.post(self.CUSTOM, self.SAVED)

        content = self.client.get(self.CONFIG).content.decode("utf-8")

        assert "selected" in self._profile_form_html(content)

    def test_resubmitting_the_profile_form_keeps_the_saved_settings(self):
        from plugins.edupi.noise_monitor.models import NoiseMonitorConfig

        self.client.post(self.CUSTOM, self.SAVED)
        content = self.client.get(self.CONFIG).content.decode("utf-8")
        config = NoiseMonitorConfig.objects.get(is_default=True)

        self.client.post(
            self.CONFIG,
            {
                "profile": str(config.profile_id),
                "instant_window_seconds": self._value(content, "instant_window_seconds"),
                "session_window_minutes": self._value(
                    content, "session_window_minutes"
                ),
                "led_brightness": self._value(content, "led_brightness"),
            },
        )

        config.refresh_from_db()
        assert config.instant_window_seconds == 15
        assert config.session_window_minutes == 8
        assert config.led_brightness == 60
        assert config.profile.yellow_threshold == 35


class ProfileManagementTest(TestCase):
    """Renaming and deleting profiles from the configuration page.

    ``profile_type`` is unique, so there is one profile per type and the seeded
    name is what the teacher is stuck with until it can be renamed.
    """

    CONFIG = "/plugins/edupi/noise_monitor/config/"
    DASHBOARD = "/plugins/edupi/noise_monitor/"

    def _profile(self, profile_type=NoiseProfile.ProfileType.TEACHING, **kwargs):
        return NoiseProfile.objects.create(
            profile_type=profile_type,
            name=kwargs.pop("name", "Teaching"),
            yellow_threshold=kwargs.pop("yellow_threshold", 40),
            red_threshold=kwargs.pop("red_threshold", 70),
            **kwargs,
        )

    def _rename_url(self, profile):
        return f"/plugins/edupi/noise_monitor/profiles/{profile.pk}/rename/"

    def _delete_url(self, profile):
        return f"/plugins/edupi/noise_monitor/profiles/{profile.pk}/delete/"

    def test_renaming_changes_the_name_and_description(self):
        profile = self._profile()

        response = self.client.post(
            self._rename_url(profile),
            {"name": "Bibliotecă", "description": "Lucru liniștit"},
            follow=True,
        )

        profile.refresh_from_db()
        assert profile.name == "Bibliotecă"
        assert profile.description == "Lucru liniștit"
        assert response.status_code == 200

    def test_the_new_name_is_what_the_dropdown_offers(self):
        profile = self._profile()

        self.client.post(
            self._rename_url(profile), {"name": "Bibliotecă", "description": ""}
        )
        content = self.client.get(self.CONFIG).content.decode("utf-8")

        assert "Bibliotecă" in content

    def test_an_empty_name_is_refused(self):
        profile = self._profile()

        self.client.post(self._rename_url(profile), {"name": "   "})

        profile.refresh_from_db()
        assert profile.name == "Teaching"

    def test_a_duplicate_name_is_refused(self):
        first = self._profile(name="Teaching")
        second = self._profile(
            profile_type=NoiseProfile.ProfileType.GROUP_WORK, name="Group Work"
        )

        self.client.post(self._rename_url(second), {"name": "teaching"})

        second.refresh_from_db()
        assert second.name == "Group Work"
        assert first.name == "Teaching"

    def test_an_overlong_name_is_refused(self):
        profile = self._profile()

        self.client.post(self._rename_url(profile), {"name": "x" * 101})

        profile.refresh_from_db()
        assert profile.name == "Teaching"

    def test_a_profile_that_does_not_exist_is_a_404(self):
        response = self.client.post(
            "/plugins/edupi/noise_monitor/profiles/9999/rename/", {"name": "x"}
        )

        assert response.status_code == 404

    def test_deleting_removes_the_profile(self):
        self._profile(name="Teaching")
        doomed = self._profile(
            profile_type=NoiseProfile.ProfileType.TEST, name="Test"
        )

        self.client.post(self._delete_url(doomed))

        assert not NoiseProfile.objects.filter(pk=doomed.pk).exists()
        assert NoiseProfile.objects.count() == 1

    def test_the_last_profile_is_not_deletable(self):
        """Deleting it would leave the dropdown empty and the form unusable."""
        only = self._profile()

        self.client.post(self._delete_url(only))

        assert NoiseProfile.objects.filter(pk=only.pk).exists()

    def test_deleting_the_profile_in_use_leaves_the_monitor_working(self):
        profile = self._profile(name="Teaching")
        # A second profile, so the delete is not refused as the last one.
        self._profile(profile_type=NoiseProfile.ProfileType.TEST, name="Test")
        NoiseMonitorConfig.objects.create(
            name="Default", profile=profile, is_default=True
        )

        self.client.post(self._delete_url(profile))

        config = NoiseMonitorConfig.objects.get(is_default=True)
        assert config.profile is None
        # No profile means the default thresholds, not a broken page.
        assert self.client.get(self.DASHBOARD).status_code == 200

    def test_the_configuration_page_offers_both_actions(self):
        profile = self._profile()
        NoiseMonitorConfig.objects.create(
            name="Default", profile=profile, is_default=True
        )

        content = self.client.get(self.CONFIG).content.decode("utf-8")

        assert self._rename_url(profile) in content
        assert self._delete_url(profile) in content

    def test_the_profile_in_use_is_marked(self):
        """The teacher has to see which card the dropdown is pointing at."""
        profile = self._profile()
        NoiseMonitorConfig.objects.create(
            name="Default", profile=profile, is_default=True
        )

        content = self.client.get(self.CONFIG).content.decode("utf-8")

        assert 'badge badge-primary badge-sm mt-2 self-start' in content


class RomanianTranslationTest(TestCase):
    """The plugin's Romanian catalogue must cover the plugin's own pages.

    It did not: 50 of the 124 strings the templates ask for had no entry, so
    most of the dashboard rendered in English inside an otherwise translated
    interface. Nothing failed — a missing msgid is not an error in gettext, it
    just falls through to the source string. These render the real pages and
    assert the Romanian text is on them.
    """

    DASHBOARD = "/plugins/edupi/noise_monitor/"
    CONFIG = "/plugins/edupi/noise_monitor/config/"

    def _get(self, url):
        return self.client.get(url, headers={"accept-language": "ro"})

    def test_dashboard_is_romanian(self):
        content = self._get(self.DASHBOARD).content.decode("utf-8")

        for text in (
            "Monitorizarea este activă",
            "Zgomot instantaneu",
            "Media sesiunii",
            "Zgomot în timp",
            "Luminozitate LED",
            "Ghid de culori LED",
            # The chart card. The window sentence carries a placeholder, so
            # this is also what proves the blocktrans variables reach the
            # Romanian text rather than being dropped. The chart's own aria
            # label is not asserted here: with no readings there is no chart.
            f"Ultimele {CHART_WINDOW_MINUTES} minute",
            "Nu există încă măsurători",
        ):
            assert text in content, f"untranslated on the dashboard: {text!r}"

    def test_the_chart_is_labelled_in_romanian(self):
        """The chart's accessible name, which only exists once it draws."""
        self._get(self.DASHBOARD)

        from plugins.edupi.noise_monitor.models import (
            NoiseMonitorConfig,
            NoiseReading,
        )

        config = NoiseMonitorConfig.objects.filter(is_active=True).first()
        NoiseReading.objects.create(
            config=config,
            raw_level=30,
            timestamp=timezone.now(),
            instant_average=30,
            session_average=30,
            instant_color="green",
            session_color="green",
        )

        content = self._get(self.DASHBOARD).content.decode("utf-8")

        assert "noise-history-chart" in content
        assert "Nivelul de zgomot în timp" in content

    def test_config_page_is_romanian(self):
        content = self._get(self.CONFIG).content.decode("utf-8")

        for text in (
            "Aplică profilul",
            "Profiluri disponibile",
            "Praguri personalizate",
            "Microfon",
        ):
            assert text in content, f"untranslated on the config page: {text!r}"

    def test_the_seeded_profile_is_named_in_the_active_language(self):
        """The default profile is written to the database, so it is named when
        it is first created rather than translated on every render."""
        self._get(self.DASHBOARD)

        from plugins.edupi.noise_monitor.models import NoiseProfile

        profile = NoiseProfile.objects.get(profile_type=NoiseProfile.ProfileType.TEACHING)

        assert profile.name == "Predare"
        assert profile.description == "Niveluri moderate de zgomot pentru predare obișnuită"

    @staticmethod
    def _python_msgids(path):
        """The strings passed to ``_()``, read from the syntax tree.

        Not a regex over the source: that would pick up the string inside a
        comment and would take only the first half of a string split across
        lines, both of which report a missing entry that is not missing.
        """
        import ast

        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = set()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.add(node.args[0].value)
        return found

    @staticmethod
    def _template_msgids(text):
        """Every string a template asks gettext for.

        Both forms, because they are not interchangeable: a string with a
        placeholder in it has to use ``blocktrans``, and a scan that only read
        ``trans`` would call the catalogue complete while that string fell
        through to English.

        The quoting has to be matched per delimiter. A pattern for either quote
        stops at the first apostrophe inside a double-quoted string, so
        ``{% trans "If keys don't work" %}`` came through as "If keys don" and
        the real string was reported missing while a string that is nowhere in
        the templates was demanded instead.
        """
        import re

        found = set()
        for match in re.finditer(r"""\{%\s*trans\s+(?:"([^"]*)"|'([^']*)')""", text):
            found.add(match.group(1) if match.group(1) is not None else match.group(2))

        for body in re.findall(
            r"\{%\s*blocktrans[^%]*%\}(.*?)\{%\s*endblocktrans\s*%\}", text, re.S
        ):
            # gettext sees the placeholders, not the Django variable names.
            found.add(re.sub(r"\{\{\s*(\w+)\s*\}\}", r"%(\1)s", body).strip())

        return found

    def test_every_string_the_templates_ask_for_is_translated(self):
        """The guard that would have caught the gap: a catalogue missing an
        entry is silent at runtime."""
        from pathlib import Path

        import polib

        plugin_dir = Path(__file__).resolve().parent
        catalogue = polib.pofile(str(plugin_dir / "locale/ro/LC_MESSAGES/django.po"))
        known = {entry.msgid for entry in catalogue}
        assert not catalogue.untranslated_entries(), "catalogue has empty translations"

        used = set()
        for path in plugin_dir.glob("*.py"):
            used |= self._python_msgids(path)
        for path in plugin_dir.rglob("*.html"):
            used |= self._template_msgids(path.read_text(encoding="utf-8"))

        missing = sorted(used - known)
        assert not missing, f"not in the Romanian catalogue: {missing}"


class NoiseLevelCalibrationTest(TestCase):
    """Tests for the microphone RMS to 0-100 conversion.

    The microphone used to be scaled linearly (``rms * 200``), which put a
    room with people in it at 0 and needed an RMS of 0.2 just to reach the
    yellow threshold. These pin the decibel mapping that replaced it.
    """

    def test_silence_is_zero(self):
        from plugins.edupi.noise_monitor.noise_service import NoiseMonitorService

        assert NoiseMonitorService.level_from_rms(0.0) == 0
        assert NoiseMonitorService.level_from_rms(-1.0) == 0

    def test_measured_room_tone_is_audible_but_green(self):
        """Room tone on the reference USB microphone measures ~0.002 RMS."""
        from plugins.edupi.noise_monitor.noise_service import NoiseMonitorService

        level = NoiseMonitorService.level_from_rms(0.002)

        assert 5 <= level < 40, f"room tone should sit in the green band, got {level}"

    def test_normal_speech_reaches_yellow(self):
        """Talking in the room has to be able to trip the yellow threshold."""
        from plugins.edupi.noise_monitor.noise_service import NoiseMonitorService

        assert NoiseMonitorService.level_from_rms(0.02) >= 40

    def test_loud_reaches_red(self):
        from plugins.edupi.noise_monitor.noise_service import NoiseMonitorService

        assert NoiseMonitorService.level_from_rms(0.2) >= 70

    def test_scale_is_monotonic_and_bounded(self):
        from plugins.edupi.noise_monitor.noise_service import NoiseMonitorService

        levels = [
            NoiseMonitorService.level_from_rms(rms)
            for rms in [0.0001, 0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
        ]

        assert levels == sorted(levels), f"scale must not go backwards: {levels}"
        assert all(0 <= level <= 100 for level in levels), levels


class MicrophoneSelectionTest(TestCase):
    """Tests for choosing a capture device.

    A saved device *index* is not stable: ALSA renumbers cards when a USB
    microphone is replugged, and the saved index then points at a playback-only
    device. Selection therefore matches the saved name first.
    """

    USB_MIC = {
        "name": "USB PnP Sound Device: Audio (hw:1,0)",
        "max_input_channels": 1,
        "default_samplerate": 44100.0,
    }
    HDMI_OUT = {
        "name": "vc4-hdmi: - (hw:0,0)",
        "max_input_channels": 0,
        "default_samplerate": 44100.0,
    }

    def setUp(self):
        import sys

        from plugins.edupi.noise_monitor.noise_service import NoiseMonitorService, noise_service

        self.service = noise_service
        # Patch through the module the class actually lives in rather than a
        # path string: the plugin is importable both as ``noise_monitor`` and
        # as ``plugins.edupi.noise_monitor``, and a string naming the wrong one
        # patches a second copy of the module that nothing calls.
        self.module = sys.modules[NoiseMonitorService.__module__]

        # The service is a process-wide singleton, so every field these tests
        # touch is reset here rather than assumed to be fresh.
        self.service.set_device(None)
        self.service._resolved_index = None
        self.service._resolved_name = ""
        self.service._next_stream_attempt = 0.0
        self.addCleanup(self.service.set_device, None)

    def _patch_devices(self, *devices):
        from unittest.mock import patch

        patcher = patch.object(self.module, "_query_devices", return_value=list(devices))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _patch_microphone_available(self, available):
        from unittest.mock import patch

        patcher = patch.object(self.module, "MICROPHONE_AVAILABLE", available)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_playback_only_devices_are_not_offered(self):
        self._patch_devices(self.USB_MIC, self.HDMI_OUT)

        devices = self.service.list_input_devices()

        assert [d["name"] for d in devices] == [self.USB_MIC["name"]]
        assert devices[0]["index"] == 0  # index is the position in the full list

    def test_usb_microphone_is_chosen_automatically(self):
        """With nothing configured, an external microphone wins."""
        self._patch_devices(self.HDMI_OUT, self.USB_MIC)

        index, name = self.service._resolve_device()

        assert name == self.USB_MIC["name"]
        assert index == 1

    def test_saved_name_wins_over_a_stale_index(self):
        """Replugging the microphone moves it; the name still finds it."""
        self._patch_devices(self.HDMI_OUT, self.USB_MIC)
        # Saved before the microphone moved from card 1 to card 2.
        self.service.set_device(9, "USB PnP Sound Device: Audio (hw:1,0)")

        index, name = self.service._resolve_device()

        assert name == self.USB_MIC["name"]
        assert index == 1

    def test_saved_index_is_used_when_the_name_does_not_match(self):
        self._patch_devices(self.USB_MIC)

        self.service.set_device(0, "Some Other Microphone")
        index, name = self.service._resolve_device()

        assert index == 0
        assert name == self.USB_MIC["name"]

    def test_no_input_device_resolves_to_nothing(self):
        self._patch_devices(self.HDMI_OUT)

        assert self.service._resolve_device() == (None, "")

    def test_reading_returns_none_when_no_microphone_can_be_opened(self):
        """No reading is not the same as a reading of zero."""
        self._patch_devices(self.HDMI_OUT)
        self._patch_microphone_available(True)

        assert self.service._read_microphone() is None

    def test_name_matching_ignores_the_card_number(self):
        from plugins.edupi.noise_monitor.noise_service import NoiseMonitorService

        normalize = NoiseMonitorService._normalize_device_name

        assert normalize("USB PnP Sound Device: Audio (hw:1,0)") == normalize(
            "USB PnP Sound Device: Audio (hw:3,0)"
        )
        assert normalize(None) == ""
        assert normalize("") == ""


class HistoryChartTest(TestCase):
    """The chart's geometry, which the template draws without any arithmetic.

    Readings are plain stand-ins rather than saved rows: the chart only ever
    reads three attributes off them, and the tests are about coordinates.
    """

    START = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)

    def _readings(self, *values):
        """Readings one minute apart, from (instant, session) pairs."""
        import types

        return [
            types.SimpleNamespace(
                timestamp=self.START + timedelta(minutes=i),
                instant_average=instant,
                session_average=session,
            )
            for i, (instant, session) in enumerate(values)
        ]

    def _chart(self, *values, yellow=40, red=70):
        from plugins.edupi.noise_monitor.chart import history_chart

        return history_chart(
            self._readings(*values), yellow_threshold=yellow, red_threshold=red
        )

    def test_no_readings_means_nothing_to_draw(self):
        from plugins.edupi.noise_monitor.chart import history_chart

        chart = history_chart([], yellow_threshold=40, red_threshold=70)

        assert chart["has_data"] is False
        assert chart["session_points"] == ""
        assert chart["gridlines"], "the empty state still needs its axis"

    def test_one_reading_is_centred_rather_than_left_aligned(self):
        chart = self._chart((30, 30))

        assert chart["single_reading"] is True
        assert chart["session_dot"]["x"] == (chart["plot_left"] + chart["plot_right"]) / 2
        assert chart["instant_dot"]["x"] == chart["session_dot"]["x"]

    def test_several_readings_span_the_full_width_oldest_first(self):
        chart = self._chart((10, 10), (20, 20), (30, 30))

        points = [p.split(",") for p in chart["session_points"].split(" ")]

        assert float(points[0][0]) == chart["plot_left"]
        assert float(points[-1][0]) == chart["plot_right"]
        # Louder is higher, so the y falls as the value climbs.
        assert float(points[0][1]) > float(points[-1][1])

    def test_the_quietest_reading_sits_on_the_floor_and_the_loudest_at_the_top(self):
        chart = self._chart((0, 0), (100, 100))

        ys = [float(p.split(",")[1]) for p in chart["session_points"].split(" ")]

        assert ys[0] == chart["plot_bottom"]
        assert ys[1] == chart["plot_top"]

    def test_a_reading_above_full_scale_is_clamped_not_drawn_off_the_chart(self):
        chart = self._chart((100, 100), (140, 140))

        ys = [float(p.split(",")[1]) for p in chart["session_points"].split(" ")]

        assert min(ys) == chart["plot_top"]

    def test_a_missing_session_average_leaves_a_gap_without_moving_the_others(self):
        """One dropped session average must not shift the rest of the line.

        The x of each point comes from its position in the window, so skipped
        readings still take up their own slice of it.
        """
        with_gap = self._chart((10, None), (20, 20), (30, 30))
        without_gap = self._chart((10, 10), (20, 20), (30, 30))

        assert len(with_gap["session_points"].split(" ")) == 2
        # The two surviving points keep the x they would have had.
        assert with_gap["session_points"].split(" ")[0] == (
            without_gap["session_points"].split(" ")[1]
        )
        assert with_gap["session_points"].split(" ")[1] == (
            without_gap["session_points"].split(" ")[2]
        )

    def test_missing_instant_averages_are_skipped_too(self):
        chart = self._chart((None, 10), (20, 20))

        assert len(chart["instant_points"].split(" ")) == 1
        assert chart["session_points"]

    def test_the_bands_follow_the_thresholds(self):
        chart = self._chart((50, 50), yellow=40, red=70)

        fills = [band["fill"] for band in chart["bands"]]

        assert fills == ["#22c55e", "#eab308", "#ef4444"]
        # Bottom band reaches from the floor up to the yellow line.
        assert chart["bands"][0]["y"] + chart["bands"][0]["height"] == chart["plot_bottom"]
        # The three stack without a gap or an overlap.
        for lower, upper in zip(chart["bands"], chart["bands"][1:]):
            assert lower["y"] == upper["y"] + upper["height"]

    def test_a_threshold_at_the_floor_leaves_no_empty_band(self):
        chart = self._chart((50, 50), yellow=0, red=70)

        assert len(chart["bands"]) == 2

    def test_a_threshold_above_the_scale_grows_the_chart_instead_of_clipping(self):
        """A mis-set threshold must not push the lines off the top.

        The scale follows the highest threshold, so a red level of 150 leaves
        no red band at all — rather than a chart whose top band is a thin sliver
        and whose readings are all squashed into the green one.
        """
        chart = self._chart((50, 50), yellow=40, red=150)

        assert [band["fill"] for band in chart["bands"]] == ["#22c55e", "#eab308"]
        assert chart["bands"][-1]["y"] == chart["plot_top"]

        level = float(chart["session_points"].split(" ")[0].split(",")[1])
        assert chart["plot_top"] < level < chart["plot_bottom"]

    def test_the_area_is_closed_along_the_floor(self):
        chart = self._chart((10, 10), (20, 20))

        area = chart["session_area"]

        assert area.startswith(f"M {chart['plot_left']:.1f},{chart['plot_bottom']:.1f} ")
        assert area.endswith(f" L {chart['plot_right']:.1f},{chart['plot_bottom']:.1f} Z")

    def test_no_session_averages_means_no_area(self):
        chart = self._chart((10, None), (20, None))

        assert chart["session_area"] == ""
        assert chart["session_dot"] is None

    def test_the_clock_runs_from_the_oldest_reading_to_the_newest(self):
        chart = self._chart((10, 10), (20, 20), (30, 30))

        assert chart["first_label"] == "09:00"
        assert chart["last_label"] == "09:02"


class ChartDecibelLabelsTest(TestCase):
    """The chart is read in decibels, the unit the levels are named in.

    The scale itself is the plugin's own 0-100 one; these tests are about the
    labels and the end-of-line readouts that put a number on it.
    """

    START = timezone.now().replace(hour=14, minute=5, second=0, microsecond=0)

    def _chart(self, *values, yellow=40, red=70):
        import types

        from plugins.edupi.noise_monitor.chart import history_chart

        readings = [
            types.SimpleNamespace(
                timestamp=self.START + timedelta(minutes=i),
                instant_average=instant,
                session_average=session,
            )
            for i, (instant, session) in enumerate(values)
        ]
        return history_chart(
            readings, yellow_threshold=yellow, red_threshold=red
        )

    def _readout(self, chart, key):
        return next(entry for entry in chart["readouts"] if entry["key"] == key)

    def test_the_axis_is_labelled_in_decibels(self):
        chart = self._chart((30, 30))

        assert [line["label"] for line in chart["gridlines"]] == [
            "100 dB",
            "75 dB",
            "50 dB",
            "25 dB",
            "0 dB",
        ]

    def test_a_grown_scale_is_still_labelled_in_decibels(self):
        """A mis-set threshold grows the scale; the unit does not change."""
        chart = self._chart((30, 30), red=150)

        assert [line["label"] for line in chart["gridlines"]] == [
            "100 dB",
            "75 dB",
            "50 dB",
            "25 dB",
            "0 dB",
        ]

    def test_each_line_shows_its_newest_value(self):
        """The point of the change: read the number, not just the shape."""
        chart = self._chart((34, 21), (30, 25))

        assert self._readout(chart, "session")["label"] == "25 dB"
        assert self._readout(chart, "instant")["label"] == "30 dB"

    def test_the_readout_sits_at_the_height_of_its_line(self):
        chart = self._chart((30, 30))

        readout = self._readout(chart, "session")
        point = chart["session_points"].split(" ")[-1]

        assert readout["y"] == float(point.split(",")[1])
        assert readout["x"] < chart["plot_right"], "printed outside the plot"

    def test_a_newest_reading_with_no_average_keeps_the_last_value_shown(self):
        """A gap at the end must not blank the number the line still means."""
        chart = self._chart((30, 30), (None, None))

        assert self._readout(chart, "session")["label"] == "30 dB"

    def test_a_line_that_never_had_a_value_gets_no_readout(self):
        chart = self._chart((30, None), (40, None))

        assert [entry["key"] for entry in chart["readouts"]] == ["instant"]

    def test_no_readings_means_no_readouts(self):
        from plugins.edupi.noise_monitor.chart import history_chart

        chart = history_chart([], yellow_threshold=40, red_threshold=70)

        assert chart["readouts"] == []

    def test_readouts_that_would_overlap_are_pushed_apart(self):
        """Both averages are usually close, and must stay readable."""
        chart = self._chart((30, 30))

        session = self._readout(chart, "session")
        instant = self._readout(chart, "instant")

        assert abs(session["y"] - instant["y"]) >= 13

    def test_pushed_apart_readouts_stay_inside_the_plot(self):
        """Neither nudge may print a value over the clock labels or off the top."""
        for value in range(0, 101):
            chart = self._chart((value, value))
            for entry in chart["readouts"]:
                assert chart["plot_top"] <= entry["y"] <= chart["plot_bottom"]

    def test_the_instant_readout_is_fainter_than_the_session_one(self):
        chart = self._chart((30, 20))

        assert (
            self._readout(chart, "instant")["opacity"]
            < self._readout(chart, "session")["opacity"]
        )

    def test_the_dashboard_prints_the_values_on_the_chart(self):
        """End to end: the numbers reach the page."""
        from plugins.edupi.noise_monitor.models import NoiseMonitorConfig, NoiseProfile, NoiseReading

        profile = NoiseProfile.objects.create(
            profile_type=NoiseProfile.ProfileType.TEACHING,
            name="Teaching",
            yellow_threshold=40,
            red_threshold=70,
        )
        config = NoiseMonitorConfig.objects.create(
            name="Default", profile=profile, is_default=True
        )
        NoiseReading.objects.create(
            config=config,
            instant_average=34,
            session_average=21,
            raw_level=21,
            timestamp=timezone.now(),
            instant_color="green",
            session_color="green",
        )

        content = self.client.get("/plugins/edupi/noise_monitor/").content.decode("utf-8")

        assert ">21 dB<" in content, "the session value is not printed on the chart"
        assert ">34 dB<" in content, "the instant value is not printed on the chart"
        assert "100 dB" in content, "the axis is not labelled in decibels"


class DashboardChartTest(TestCase):
    """The dashboard draws the chart, and says so when there is nothing to draw."""

    DASHBOARD = "/plugins/edupi/noise_monitor/"

    def _config(self):
        profile = NoiseProfile.objects.create(
            profile_type=NoiseProfile.ProfileType.TEACHING,
            name="Teaching",
            yellow_threshold=40,
            red_threshold=70,
        )
        return NoiseMonitorConfig.objects.create(
            name="Default", profile=profile, is_default=True
        )

    def _reading(self, config, minutes_ago, instant, session):
        return NoiseReading.objects.create(
            config=config,
            raw_level=session,
            timestamp=timezone.now() - timedelta(minutes=minutes_ago),
            instant_average=instant,
            session_average=session,
            instant_color="green",
            session_color="green",
        )

    def test_a_quiet_dashboard_says_there_is_nothing_yet(self):
        self._config()

        response = self.client.get(self.DASHBOARD)

        assert response.status_code == 200
        # The page carries other inline icons, so this looks for the chart's
        # own marker rather than any <svg> at all.
        assert b"noise-history-chart" not in response.content
        assert b"No readings yet" in response.content

    def test_readings_are_drawn_as_a_line(self):
        config = self._config()
        readings = [
            self._reading(config, minutes, level, level)
            for minutes, level in ((4, 10), (3, 40), (2, 80), (1, 90))
        ]

        content = self.client.get(self.DASHBOARD).content.decode("utf-8")

        assert "noise-history-chart" in content
        assert "<polyline" in content
        # Oldest on the left. The query hands the window over newest first, so
        # without the reverse in the view these two labels would swap.
        oldest, newest = readings[0], readings[-1]
        assert content.index(oldest.timestamp.strftime("%H:%M")) < content.index(
            newest.timestamp.strftime("%H:%M")
        )

    def test_the_table_is_gone(self):
        """The chart replaced it, not joined it."""
        config = self._config()
        self._reading(config, 1, 30, 30)

        content = self.client.get(self.DASHBOARD).content.decode("utf-8")

        assert "readings-table" not in content

    def test_the_page_announces_the_window_it_draws(self):
        """The caption is the only thing telling a teacher how far back it goes."""
        config = self._config()
        self._reading(config, 1, 30, 30)

        content = self.client.get(self.DASHBOARD).content.decode("utf-8")

        assert f"The last {CHART_WINDOW_MINUTES} minutes." in content

    def test_readings_older_than_the_window_are_dropped(self):
        """The window is a limit, so the graph cannot grow without bound."""
        config = self._config()
        window = chart_reading_count()
        # More than fits, so the excess is what the view has to leave out.
        extra = 5
        start = timezone.now() - timedelta(minutes=window + extra)
        NoiseReading.objects.bulk_create(
            [
                NoiseReading(
                    config=config,
                    raw_level=30,
                    timestamp=start + timedelta(minutes=offset),
                    instant_average=30,
                    session_average=30,
                    instant_color="green",
                    session_color="green",
                )
                for offset in range(window + extra)
            ]
        )

        chart = self.client.get(self.DASHBOARD).context["chart"]

        # Asserted through the chart rather than by looking for a clock reading
        # in the page, which the rest of the dashboard also prints.
        # session_points is the SVG points attribute: one "x,y" per reading.
        assert len(chart["session_points"].split()) == window
        assert chart["first_label"] == (start + timedelta(minutes=extra)).strftime(
            "%H:%M"
        )


class ChartWindowTest(TestCase):
    """How much history the dashboard asks for.

    The window is a length of lesson, not an implementation detail, so it is
    pinned here: widening or narrowing it is a decision about what a teacher
    sees, and the reading count it turns into is what bounds the query.
    """

    def test_the_window_lasts_twenty_minutes(self):
        assert CHART_WINDOW_MINUTES == 20

    def test_the_reading_count_covers_the_whole_window(self):
        """One reading every interval, for the whole window — no shortfall."""
        covered = chart_reading_count() * READING_SAVE_INTERVAL_SECONDS

        assert covered == CHART_WINDOW_MINUTES * 60


class ChartRefreshTest(TestCase):
    """The graph keeps up with the lesson instead of freezing at page load.

    It is drawn by the server, so re-fetching the card is what refreshes it.
    These tests are the contract between the two halves: the view has to hand
    back the card, and the page has to carry the code that asks for it.
    """

    DASHBOARD = "/plugins/edupi/noise_monitor/"
    FRAGMENT = "/plugins/edupi/noise_monitor/chart/"

    def _config(self):
        profile = NoiseProfile.objects.create(
            profile_type=NoiseProfile.ProfileType.TEACHING,
            name="Teaching",
            yellow_threshold=40,
            red_threshold=70,
        )
        return NoiseMonitorConfig.objects.create(
            name="Default", profile=profile, is_default=True
        )

    def _reading(self, config, minutes_ago, level):
        return NoiseReading.objects.create(
            config=config,
            raw_level=level,
            timestamp=timezone.now() - timedelta(minutes=minutes_ago),
            instant_average=level,
            session_average=level,
            instant_color="green",
            session_color="green",
        )

    def test_the_fragment_returns_the_card_and_nothing_else(self):
        """It is swapped into the page, so a whole document would nest."""
        config = self._config()
        self._reading(config, 1, 30)

        content = self.client.get(self.FRAGMENT).content.decode("utf-8")

        assert content.count('id="history-chart"') == 1
        assert "<!DOCTYPE" not in content.upper()
        assert "<html" not in content.lower()
        # The card is what the page swaps in by id, so it has to be the root.
        assert content.lstrip().startswith("<div")

    def test_the_fragment_draws_the_same_chart_as_the_dashboard(self):
        config = self._config()
        for minutes, level in ((4, 10), (3, 40), (2, 80), (1, 90)):
            self._reading(config, minutes, level)

        page = self.client.get(self.DASHBOARD)
        fragment = self.client.get(self.FRAGMENT)

        assert fragment.context["chart"] == page.context["chart"]

    def test_the_fragment_picks_up_readings_stored_since_the_page_loaded(self):
        """The whole point: a new reading reaches a page that is already open."""
        config = self._config()
        self._reading(config, 2, 30)

        self.assertNotIn(
            ">77 dB<", self.client.get(self.FRAGMENT).content.decode("utf-8")
        )

        self._reading(config, 0, 77)

        assert ">77 dB<" in self.client.get(self.FRAGMENT).content.decode("utf-8")

    def test_the_fragment_says_there_is_nothing_yet_when_there_is_nothing(self):
        self._config()

        content = self.client.get(self.FRAGMENT).content.decode("utf-8")

        assert 'id="history-chart"' in content
        assert "No readings yet" in content

    def test_the_fragment_leaves_the_page_layout_out(self):
        """No nav, no cards above it: only the card comes back."""
        self._config()

        content = self.client.get(self.FRAGMENT).content.decode("utf-8")

        assert "LED Color Guide" not in content
        assert "instant-level" not in content

    def test_the_dashboard_asks_for_the_fragment_once_a_minute(self):
        self._config()

        content = self.client.get(self.DASHBOARD).content.decode("utf-8")

        assert f'const chartUrl = "{self.FRAGMENT}"' in content
        assert "const chartRefreshMs = 60000;" in content
        assert "setInterval(refreshChart, chartRefreshMs);" in content

    def test_the_refresh_replaces_the_card_by_the_id_it_carries(self):
        """A rename on either side would leave the graph frozen and silent."""
        self._config()

        content = self.client.get(self.DASHBOARD).content.decode("utf-8")

        assert "getElementById('history-chart')" in content
        assert 'id="history-chart"' in content

    def test_a_failed_refresh_keeps_the_graph_on_screen(self):
        """A stale graph beats an empty card, and the next tick tries again."""
        self._config()

        content = self.client.get(self.DASHBOARD).content.decode("utf-8")

        assert "Could not refresh the noise graph" in content
        # The swap only happens once the response came back usable, so a
        # failure leaves the graph that is already on screen untouched.
        refresh = content[content.index("function refreshChart") :]
        refresh = refresh[: refresh.index("chartRefreshInterval = setInterval")]
        assert "outerHTML = html" in refresh
        assert "throw new Error(response.status)" in refresh

    def test_a_hidden_tab_does_not_keep_asking(self):
        """Nobody is reading it, and the Pi has other work."""
        self._config()

        content = self.client.get(self.DASHBOARD).content.decode("utf-8")

        refresh = content[content.index("function refreshChart") :]
        assert "if (document.hidden)" in refresh
        assert "visibilitychange" in content

    def test_the_refresh_interval_is_cleared_when_the_page_goes_away(self):
        self._config()

        content = self.client.get(self.DASHBOARD).content.decode("utf-8")

        unload = content[content.index("beforeunload") :]
        assert "clearInterval(chartRefreshInterval)" in unload

    def test_the_interval_matches_how_often_a_reading_is_stored(self):
        """Slower than the readings, so a refresh never misses one entirely.

        One minute against a reading every
        ``READING_SAVE_INTERVAL_SECONDS`` seconds means the graph moves in
        steps of a dozen-odd readings; that is the trade the interval makes.
        """
        assert 60000 / 1000 >= READING_SAVE_INTERVAL_SECONDS
        assert 60000 / 1000 < CHART_WINDOW_MINUTES * 60
