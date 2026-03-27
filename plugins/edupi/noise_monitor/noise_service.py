"""Noise Monitor Service for EDU-PI.

Manages microphone input and dual RGB LED control for noise monitoring.
Provides instant and session rolling averages.
"""

import logging
import threading
import time
import math
from collections import deque
from typing import Optional, Callable, List, Tuple
from datetime import datetime, timedelta

try:
    from gpiozero import PWMLED

    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

    # Mock classes for development
    class PWMLED:
        def __init__(self, pin, active_high=True, initial_value=0):
            self.pin = pin
            self._value = initial_value
            self._is_on = False

        def on(self):
            self._is_on = True
            self._value = 1
            logging.getLogger(__name__).info(f"Mock LED {self.pin}: ON")

        def off(self):
            self._is_on = False
            self._value = 0
            logging.getLogger(__name__).info(f"Mock LED {self.pin}: OFF")

        @property
        def value(self):
            return self._value

        @value.setter
        def value(self, val):
            self._value = val
            self._is_on = val > 0
            logging.getLogger(__name__).info(f"Mock LED {self.pin}: value={val:.2f}")


# Try to import sounddevice for audio input
try:
    import sounddevice as sd
    import numpy as np

    MICROPHONE_AVAILABLE = True
except ImportError:
    MICROPHONE_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "sounddevice not available - using simulated noise data"
    )


logger = logging.getLogger(__name__)


class NoiseMonitorService:
    """
    Service for continuous noise monitoring with dual LED feedback.

    Features:
    - Continuous microphone monitoring
    - Instant average (rolling window, default 10 seconds)
    - Session average (rolling window, default 5 minutes)
    - Two independent RGB LEDs
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern for noise service."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the noise monitoring service."""
        if self._initialized:
            return

        self._initialized = True

        # GPIO pins for LEDs
        self._instant_red: Optional[PWMLED] = None
        self._instant_green: Optional[PWMLED] = None
        self._instant_blue: Optional[PWMLED] = None

        self._session_red: Optional[PWMLED] = None
        self._session_green: Optional[PWMLED] = None
        self._session_blue: Optional[PWMLED] = None

        # Settings
        self._brightness: float = 1.0
        self._instant_window_seconds: int = 10
        self._session_window_minutes: int = 5
        self._yellow_threshold: int = 40
        self._red_threshold: int = 70

        # State
        self._is_monitoring: bool = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._callback: Optional[Callable] = None

        # Rolling buffers for averages
        self._instant_readings: deque = deque(maxlen=100)  # Last 10 seconds at 10Hz
        self._session_readings: deque = deque(maxlen=3000)  # Last 5 minutes at 10Hz

        # Current state
        self._instant_average: int = 0
        self._session_average: int = 0
        self._instant_color: str = "green"
        self._session_color: str = "green"

    def initialize_gpio(
        self,
        instant_red_pin: int,
        instant_green_pin: int,
        instant_blue_pin: int,
        session_red_pin: int,
        session_green_pin: int,
        session_blue_pin: int,
        brightness: int = 100,
    ) -> None:
        """
        Initialize GPIO pins for two RGB LEDs.

        Args:
            instant_red_pin: BCM pin for instant LED red
            instant_green_pin: BCM pin for instant LED green
            instant_blue_pin: BCM pin for instant LED blue
            session_red_pin: BCM pin for session LED red
            session_green_pin: BCM pin for session LED green
            session_blue_pin: BCM pin for session LED blue
            brightness: LED brightness percentage (10-100)
        """
        try:
            self._brightness = brightness / 100.0

            # Initialize instant LED
            self._instant_red = PWMLED(instant_red_pin)
            self._instant_green = PWMLED(instant_green_pin)
            self._instant_blue = PWMLED(instant_blue_pin)

            # Initialize session LED
            self._session_red = PWMLED(session_red_pin)
            self._session_green = PWMLED(session_green_pin)
            self._session_blue = PWMLED(session_blue_pin)

            # Start with LEDs off
            self._set_instant_led_color(0, 0, 0)
            self._set_session_led_color(0, 0, 0)

            logger.info(
                f"GPIO initialized - Instant LED pins: {instant_red_pin}, "
                f"{instant_green_pin}, {instant_blue_pin} | "
                f"Session LED pins: {session_red_pin}, {session_green_pin}, {session_blue_pin}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")

    def cleanup_gpio(self) -> None:
        """Cleanup GPIO resources."""
        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)

        # Turn off LEDs
        self._set_instant_led_color(0, 0, 0)
        self._set_session_led_color(0, 0, 0)

        if self._instant_red:
            self._instant_red.off()
        if self._instant_green:
            self._instant_green.off()
        if self._instant_blue:
            self._instant_blue.off()

        if self._session_red:
            self._session_red.off()
        if self._session_green:
            self._session_green.off()
        if self._session_blue:
            self._session_blue.off()

        logger.info("GPIO cleanup completed")

    def configure(
        self,
        yellow_threshold: int = 40,
        red_threshold: int = 70,
        instant_window_seconds: int = 10,
        session_window_minutes: int = 5,
        brightness: int = 100,
    ) -> None:
        """
        Configure noise monitoring parameters.

        Args:
            yellow_threshold: Level at which LED turns yellow (0-100)
            red_threshold: Level at which LED turns red (0-100)
            instant_window_seconds: Window for instant average
            session_window_minutes: Window for session average
            brightness: LED brightness percentage
        """
        self._yellow_threshold = yellow_threshold
        self._red_threshold = red_threshold
        self._instant_window_seconds = instant_window_seconds
        self._session_window_minutes = session_window_minutes
        self._brightness = brightness / 100.0

        # Resize buffers based on new windows (10Hz sampling rate)
        instant_maxlen = instant_window_seconds * 10
        session_maxlen = session_window_minutes * 60 * 10

        # Create new deques with new sizes, preserving data if possible
        old_instant = list(self._instant_readings)
        old_session = list(self._session_readings)

        self._instant_readings = deque(
            old_instant[-instant_maxlen:], maxlen=instant_maxlen
        )
        self._session_readings = deque(
            old_session[-session_maxlen:], maxlen=session_maxlen
        )

        logger.info(
            f"Configured - Yellow: {yellow_threshold}, Red: {red_threshold}, "
            f"Instant window: {instant_window_seconds}s, Session window: {session_window_minutes}min"
        )

    def start_monitoring(self, callback: Callable = None) -> None:
        """
        Start noise monitoring.

        Args:
            callback: Optional callback function(levels_dict) called on each update
        """
        if self._is_monitoring:
            logger.warning("Noise monitoring already running")
            return

        self._stop_event.clear()
        self._callback = callback

        # Start monitoring thread
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self._is_monitoring = True

        logger.info("Noise monitoring started")

    def stop_monitoring(self) -> None:
        """Stop noise monitoring."""
        if not self._is_monitoring:
            return

        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)

        self._is_monitoring = False

        # Turn off LEDs
        self._set_instant_led_color(0, 0, 0)
        self._set_session_led_color(0, 0, 0)

        logger.info("Noise monitoring stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop - runs in separate thread."""
        sample_interval = 0.1  # 10Hz sampling rate
        last_update = time.time()

        while not self._stop_event.is_set():
            try:
                # Read noise level from microphone or simulate
                raw_level = self._read_microphone()

                # Add to buffers
                timestamp = datetime.now()
                reading = {"level": raw_level, "timestamp": timestamp}
                self._instant_readings.append(reading)
                self._session_readings.append(reading)

                # Calculate averages
                self._instant_average = self._calculate_average(
                    self._instant_readings,
                    timedelta(seconds=self._instant_window_seconds),
                )
                self._session_average = self._calculate_average(
                    self._session_readings,
                    timedelta(minutes=self._session_window_minutes),
                )

                # Determine LED colors
                self._instant_color = self._get_color_for_level(self._instant_average)
                self._session_color = self._get_color_for_level(self._session_average)

                # Update LEDs
                self._update_leds()

                # Call callback if provided
                if self._callback:
                    try:
                        self._callback(
                            {
                                "instant_average": self._instant_average,
                                "session_average": self._session_average,
                                "instant_color": self._instant_color,
                                "session_color": self._session_color,
                                "timestamp": timestamp.isoformat(),
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error in callback: {e}")

                # Sleep until next sample
                elapsed = time.time() - last_update
                sleep_time = max(0, sample_interval - elapsed)
                time.sleep(sleep_time)
                last_update = time.time()

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(sample_interval)

    def _read_microphone(self) -> int:
        """
        Read noise level from microphone.

        Returns:
            int: Noise level 0-100
        """
        if MICROPHONE_AVAILABLE:
            try:
                # Record a short sample
                duration = 0.05  # 50ms
                sample_rate = 44100
                samples = int(duration * sample_rate)

                recording = sd.rec(
                    samples, samplerate=sample_rate, channels=1, dtype="float32"
                )
                sd.wait()

                # Calculate RMS
                rms = np.sqrt(np.mean(recording**2))

                # Convert to 0-100 scale (assuming max RMS around 0.5)
                level = int(min(100, max(0, rms * 200)))

                return level

            except Exception as e:
                logger.error(f"Error reading microphone: {e}")
                return self._simulate_noise()
        else:
            return self._simulate_noise()

    def _simulate_noise(self) -> int:
        """
        Simulate noise data for development.

        Returns:
            int: Simulated noise level 0-100
        """
        import random

        # Base noise level with some variation
        base_level = 30
        variation = random.randint(-10, 20)

        # Occasional spikes
        if random.random() < 0.05:
            variation += random.randint(20, 40)

        level = base_level + variation
        return min(100, max(0, level))

    def _calculate_average(self, readings: deque, window: timedelta) -> int:
        """
        Calculate average from readings within time window.

        Args:
            readings: Deque of reading dicts with 'level' and 'timestamp'
            window: Time window for average

        Returns:
            int: Average noise level (0-100)
        """
        if not readings:
            return 0

        cutoff_time = datetime.now() - window
        recent_readings = [r["level"] for r in readings if r["timestamp"] > cutoff_time]

        if not recent_readings:
            return readings[-1]["level"] if readings else 0

        return int(sum(recent_readings) / len(recent_readings))

    def _get_color_for_level(self, level: int) -> str:
        """
        Get color for a given noise level.

        Args:
            level: Noise level 0-100

        Returns:
            str: 'green', 'yellow', or 'red'
        """
        if level >= self._red_threshold:
            return "red"
        elif level >= self._yellow_threshold:
            return "yellow"
        else:
            return "green"

    def _update_leds(self) -> None:
        """Update both LEDs based on current averages."""
        # Update instant LED
        instant_color_hex = self._color_to_hex(self._instant_color)
        r, g, b = self._hex_to_rgb(instant_color_hex)
        self._set_instant_led_color(r, g, b)

        # Update session LED
        session_color_hex = self._color_to_hex(self._session_color)
        r, g, b = self._hex_to_rgb(session_color_hex)
        self._set_session_led_color(r, g, b)

    def _set_instant_led_color(self, r: float, g: float, b: float) -> None:
        """Set instant LED color."""
        if self._instant_red:
            self._instant_red.value = r * self._brightness
        if self._instant_green:
            self._instant_green.value = g * self._brightness
        if self._instant_blue:
            self._instant_blue.value = b * self._brightness

    def _set_session_led_color(self, r: float, g: float, b: float) -> None:
        """Set session LED color."""
        if self._session_red:
            self._session_red.value = r * self._brightness
        if self._session_green:
            self._session_green.value = g * self._brightness
        if self._session_blue:
            self._session_blue.value = b * self._brightness

    @staticmethod
    def _color_to_hex(color: str) -> str:
        """
        Convert color name to hex.

        Args:
            color: 'green', 'yellow', or 'red'

        Returns:
            str: Hex color code
        """
        color_map = {
            "green": "#00FF00",
            "yellow": "#FFFF00",
            "red": "#FF0000",
        }
        return color_map.get(color, "#808080")

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
        """
        Convert hex color to RGB tuple.

        Args:
            hex_color: Hex color code (e.g., "#FF0000")

        Returns:
            Tuple of (r, g, b) values (0-1)
        """
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return (r, g, b)

    def get_current_levels(self) -> dict:
        """
        Get current noise levels.

        Returns:
            dict: Current noise monitoring state
        """
        return {
            "instant_average": self._instant_average,
            "session_average": self._session_average,
            "instant_color": self._instant_color,
            "session_color": self._session_color,
            "is_monitoring": self._is_monitoring,
            "yellow_threshold": self._yellow_threshold,
            "red_threshold": self._red_threshold,
        }

    def is_monitoring(self) -> bool:
        """Check if monitoring is active."""
        return self._is_monitoring


# Global noise service instance
noise_service = NoiseMonitorService()
