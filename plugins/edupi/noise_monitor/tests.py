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
        from .noise_service import noise_service, DEVICE_STATUS_DEFAULT

        noise_service.set_device(None)
        assert noise_service._device_index is None
        assert noise_service._device_status == DEVICE_STATUS_DEFAULT

    def test_set_device_stores_name(self):
        """Test that device name is stored."""
        from .noise_service import noise_service, DEVICE_STATUS_CONNECTED

        noise_service.set_device(0, "Test Microphone")
        assert noise_service._device_index == 0
        assert noise_service._device_name == "Test Microphone"
        assert noise_service._device_status == DEVICE_STATUS_CONNECTED

    def test_get_device_status_returns_dict(self):
        """Test that get_device_status returns proper dict."""
        from .noise_service import noise_service

        noise_service.set_device(1, "USB Mic")
        status = noise_service.get_device_status()

        assert isinstance(status, dict)
        assert status["device_index"] == 1
        assert status["device_name"] == "USB Mic"
        assert "device_status" in status

    def test_get_current_levels_includes_device_status(self):
        """Test that get_current_levels includes device info."""
        from .noise_service import noise_service

        noise_service.set_device(2, "Another Mic")
        levels = noise_service.get_current_levels()

        assert "device_status" in levels
        assert "device_name" in levels
        assert levels["device_name"] == "Another Mic"
