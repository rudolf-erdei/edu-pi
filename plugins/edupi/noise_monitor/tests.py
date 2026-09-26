"""Tests for Noise Monitor plugin."""

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
