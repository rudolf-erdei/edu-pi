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
