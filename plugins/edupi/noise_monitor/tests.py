"""Tests for Noise Monitor plugin."""

import sys
from unittest import mock

import pytest
from django.test import TestCase
from django.utils import timezone

from plugins.edupi.noise_monitor.models import (
    NoiseProfile,
    NoiseMonitorConfig,
    NoiseReading,
)


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
            "Măsurători recente",
            "Luminozitate LED",
            "Ghid de culori LED",
        ):
            assert text in content, f"untranslated on the dashboard: {text!r}"

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

    def test_every_string_the_templates_ask_for_is_translated(self):
        """The guard that would have caught the gap: a catalogue missing an
        entry is silent at runtime."""
        import re
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
            text = path.read_text(encoding="utf-8")
            used |= set(re.findall(r'\{%\s*trans\s+"([^"]+)"', text))

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
