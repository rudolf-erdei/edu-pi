"""Noise Monitor Service for Tinko.

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

# Channel layer for WebSocket broadcasting
try:
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync

    CHANNELS_AVAILABLE = True
except ImportError:
    CHANNELS_AVAILABLE = False

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

# Device status constants
DEVICE_STATUS_CONNECTED = "connected"
DEVICE_STATUS_DISCONNECTED = "disconnected"
DEVICE_STATUS_RECONNECTING = "reconnecting"
DEVICE_STATUS_DEFAULT = "default"  # Using system default

# Microphone capture settings.
#
# A stream is held open rather than opened per reading: opening this USB sound
# card costs about 15 ms, which at ten readings a second dominated the monitor
# loop. Blocks are 50 ms, so the newest block the loop sees is at most that
# stale while the loop itself still runs at 10 Hz.
MIC_SAMPLE_RATE = 44100
MIC_BLOCK_SECONDS = 0.05

# Decibel floor of the 0-100 scale.
#
# The old mapping was `rms * 200` on a 0..1 float scale, which needed an RMS of
# 0.2 just to reach the yellow threshold. Room tone from the reference USB
# microphone (C-Media "USB PnP Sound Device") measures around 0.002 RMS, so that
# mapping reported 0 for a room with people in it and real audio was
# indistinguishable from a dead microphone. Mapping dBFS across a 60 dB window
# instead gives the thresholds something to bite on:
#
#     0.002 RMS -> -54 dBFS -> level 10   quiet classroom
#     0.02  RMS -> -34 dBFS -> level 43   normal talk, yellow
#     0.2   RMS -> -14 dBFS -> level 77   loud, red
MIC_FLOOR_DBFS = -60.0
MIC_CEILING_DBFS = 0.0

# How often a reading is written to the history table while monitoring.
READING_SAVE_INTERVAL_SECONDS = 5.0

# The face shown for each colour, keyed by the same colour names the LEDs use.
# Values are Mood values from the display plugin (lcd_display/mood.py), matched
# by name so this module does not have to import it.
FACE_MOODS = {"green": "happy", "yellow": "neutral", "red": "sad"}
# Mirrors Mood.get_default(). Shown when the monitor stops driving the face.
DEFAULT_FACE_MOOD = "happy"


logger = logging.getLogger(__name__)


def _query_devices() -> List[dict]:
    """
    List every audio device the sound library knows about.

    Kept as a module-level function so the device-selection logic can be
    exercised without a sound card present.

    Returns:
        List of device dicts, or an empty list when sounddevice is unavailable.
    """
    if not MICROPHONE_AVAILABLE:
        return []

    try:
        return list(sd.query_devices())
    except Exception as e:
        logger.error(f"Could not enumerate audio devices: {e}")
        return []


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

        # Last colour put on the LCD face. The face is redrawn only when the
        # colour changes, not on every 10 Hz sample: each redraw is a full
        # panel write over SPI.
        self._last_face_color: Optional[str] = None

        # History storage. Monitoring runs continuously once the plugin loads,
        # so readings are written on an interval rather than on every sample.
        self._persist: bool = False
        self._last_persist_at: Optional[datetime] = None

        # Audio device settings. _device_index/_device_name are what the
        # teacher configured; _resolved_index/_resolved_name are what the
        # service actually opened, which differ when the selection is automatic
        # or when ALSA has renumbered the cards since the choice was saved.
        self._device_index: Optional[int] = None
        self._device_name: str = ""
        self._resolved_index: Optional[int] = None
        self._resolved_name: str = ""
        self._device_status: str = DEVICE_STATUS_DEFAULT
        self._reconnect_interval: float = 2.0  # seconds
        self._next_stream_attempt: float = 0.0

        # Live audio stream (only when sounddevice is available)
        self._stream = None
        self._latest_block = None

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

        self._close_stream()

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

    def set_device(self, device_index: Optional[int], device_name: str = "") -> None:
        """
        Select the microphone to monitor.

        Args:
            device_index: Device index from sounddevice, or None to select
                automatically.
            device_name: Human-readable device name.
        """
        # A different device means the stream already open is pointed at the
        # old one, so drop it and let the next read open the right device.
        self._close_stream()

        if device_index is None and not device_name:
            self._device_index = None
            self._device_name = ""
            self._device_status = DEVICE_STATUS_DEFAULT
            logger.info("Microphone selection: automatic")
        else:
            self._device_index = device_index
            self._device_name = device_name
            self._device_status = DEVICE_STATUS_CONNECTED
            logger.info(
                f"Microphone selected: {device_name or 'index ' + str(device_index)}"
            )

    @staticmethod
    def _normalize_device_name(name: str) -> str:
        """
        Reduce a PortAudio device name to the part stable across renumbering.

        ALSA names look like ``'USB PnP Sound Device: Audio (hw:1,0)'``. The
        card number in the tail changes when the microphone is replugged or
        another card appears, so only the head is compared.

        Args:
            name: Device name as reported by sounddevice.

        Returns:
            str: Lower-cased name without the changing tail.
        """
        return (name or "").split("(")[0].strip().casefold()

    def list_input_devices(self) -> List[dict]:
        """
        List the devices that can capture audio.

        Returns:
            List of dicts with index, name, channels and default samplerate.
        """
        devices = []
        for idx, device in enumerate(_query_devices()):
            if device.get("max_input_channels", 0) > 0:
                devices.append(
                    {
                        "index": idx,
                        "name": device["name"],
                        "channels": device["max_input_channels"],
                        "default_samplerate": int(device["default_samplerate"]),
                    }
                )

        return devices

    def _resolve_device(self) -> Tuple[Optional[int], str]:
        """
        Work out which device to capture from.

        The saved *name* is matched before the saved index, because ALSA
        renumbers cards when a USB microphone is replugged: a saved index can
        silently end up pointing at the HDMI output, whose capture side does
        not exist. When nothing is configured, a USB microphone is preferred
        over the Pi's own audio, which cannot capture at all.

        Returns:
            Tuple of (device index, device name), or (None, "") when no device
            can capture.
        """
        devices = self.list_input_devices()
        if not devices:
            return None, ""

        wanted = self._normalize_device_name(self._device_name)
        if wanted:
            for device in devices:
                if self._normalize_device_name(device["name"]) == wanted:
                    return device["index"], device["name"]

        if self._device_index is not None:
            for device in devices:
                if device["index"] == self._device_index:
                    return device["index"], device["name"]

        for device in devices:
            if "usb" in device["name"].casefold():
                return device["index"], device["name"]

        return devices[0]["index"], devices[0]["name"]

    def get_device_status(self) -> dict:
        """
        Get current audio device status.

        Returns:
            dict: Device status information
        """
        return {
            "device_index": self._resolved_index,
            "device_name": self._resolved_name,
            "configured_device_index": self._device_index,
            "configured_device_name": self._device_name,
            "device_status": self._device_status,
            "microphone_available": MICROPHONE_AVAILABLE,
        }

    def _on_audio_block(self, indata, frames, time_info, status) -> None:
        """Keep the most recent block for the monitor loop to read."""
        if status:
            logger.debug(f"Audio stream status: {status}")
        try:
            self._latest_block = indata[:, 0].copy()
        except Exception as e:
            logger.debug(f"Could not copy audio block: {e}")

    def _close_stream(self) -> None:
        """Stop and release the microphone stream, if one is open."""
        stream, self._stream = self._stream, None
        self._latest_block = None
        if stream is None:
            return
        try:
            stream.stop()
            stream.close()
        except Exception as e:
            logger.debug(f"Could not close the audio stream cleanly: {e}")

    def _ensure_stream(self) -> bool:
        """
        Open the microphone stream if it is not already running.

        Returns:
            bool: True when a stream is available to read from.
        """
        if self._stream is not None:
            return True

        if time.time() < self._next_stream_attempt:
            return False

        index, name = self._resolve_device()
        if index is None:
            self._device_status = DEVICE_STATUS_DISCONNECTED
            self._next_stream_attempt = time.time() + self._reconnect_interval
            return False

        try:
            blocksize = int(MIC_SAMPLE_RATE * MIC_BLOCK_SECONDS)
            stream = sd.InputStream(
                device=index,
                samplerate=MIC_SAMPLE_RATE,
                channels=1,
                dtype="float32",
                blocksize=blocksize,
                callback=self._on_audio_block,
            )
            stream.start()
        except Exception as e:
            logger.error(f"Could not open microphone {name!r} (index {index}): {e}")
            self._close_stream()
            self._device_status = DEVICE_STATUS_RECONNECTING
            self._next_stream_attempt = time.time() + self._reconnect_interval
            return False

        self._stream = stream
        self._latest_block = None
        self._resolved_index = index
        self._resolved_name = name
        self._device_status = DEVICE_STATUS_CONNECTED
        logger.info(f"Microphone open: {name} (index {index})")
        return True

    @staticmethod
    def level_from_rms(rms: float) -> int:
        """
        Convert an RMS amplitude to a 0-100 noise level.

        The scale is decibel-based: RMS is converted to dBFS (0 dBFS being a
        full-scale signal) and mapped across ``MIC_FLOOR_DBFS`` (0) to
        ``MIC_CEILING_DBFS`` (100). A linear mapping over the same range would
        spend most of its resolution on levels no classroom reaches.

        Args:
            rms: Root-mean-square amplitude of the samples, on a 0..1 scale.

        Returns:
            int: Noise level 0-100.
        """
        if rms <= 0:
            return 0

        dbfs = 20.0 * math.log10(min(rms, 1.0))
        span = MIC_CEILING_DBFS - MIC_FLOOR_DBFS
        level = (dbfs - MIC_FLOOR_DBFS) / span * 100.0
        return int(min(100, max(0, level)))

    def start_monitoring(self, callback: Callable = None, persist: bool = False) -> None:
        """
        Start noise monitoring.

        Args:
            callback: Optional callback function(levels_dict) called on each update
            persist: Store readings for the history table while monitoring runs
        """
        if self._is_monitoring:
            logger.warning("Noise monitoring already running")
            return

        self._stop_event.clear()
        self._callback = callback
        self._persist = persist
        # Nothing stored yet this run, so the first reading is written at once
        # rather than after a full interval of an empty table.
        self._last_persist_at = None

        # Start monitoring thread
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        self._is_monitoring = True

        # Broadcast status change
        self._broadcast_status(True)

        logger.info("Noise monitoring started")

    def stop_monitoring(self) -> None:
        """Stop noise monitoring."""
        if not self._is_monitoring:
            return

        self._stop_event.set()

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)

        self._close_stream()

        self._is_monitoring = False

        # Turn off LEDs
        self._set_instant_led_color(0, 0, 0)
        self._set_session_led_color(0, 0, 0)

        # The face is part of this monitor's output too, so it goes back to the
        # display's own default rather than staying stuck on the last colour.
        self._reset_face()

        # Broadcast status change
        self._broadcast_status(False)

        logger.info("Noise monitoring stopped")

    def _monitor_loop(self) -> None:
        """Main monitoring loop - runs in separate thread."""
        sample_interval = 0.1  # 10Hz sampling rate
        last_update = time.time()

        while not self._stop_event.is_set():
            try:
                # Read noise level from microphone or simulate
                raw_level = self._read_microphone()

                if raw_level is None:
                    # No microphone reading available. Hold the previous
                    # averages and let device_status report the problem, rather
                    # than feeding the buffer invented numbers.
                    time.sleep(sample_interval)
                    last_update = time.time()
                    continue

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

                # Face follows LED 2
                self._update_face()

                # History, at its own slower interval
                self._persist_reading(timestamp)

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

                # Broadcast update to WebSocket clients
                self._broadcast_update(
                    {
                        "instant_average": self._instant_average,
                        "session_average": self._session_average,
                        "instant_color": self._instant_color,
                        "session_color": self._session_color,
                        "is_monitoring": True,
                        "timestamp": timestamp.isoformat(),
                    }
                )

                # Sleep until next sample
                elapsed = time.time() - last_update
                sleep_time = max(0, sample_interval - elapsed)
                time.sleep(sleep_time)
                last_update = time.time()

            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                time.sleep(sample_interval)

    def _read_microphone(self) -> Optional[int]:
        """
        Read the current noise level from the microphone.

        Returns:
            int: Noise level 0-100, or None when no reading could be taken.
                None is not zero: it means the loop should hold its last values
                rather than report a number nothing measured.
        """
        if not MICROPHONE_AVAILABLE:
            # Development machines without sounddevice still get a moving
            # display, but a real microphone that has failed does not: making
            # the two look alike is how a dead microphone went unnoticed.
            return self._simulate_noise()

        if not self._ensure_stream():
            return None

        block = self._latest_block
        if block is None or block.size == 0:
            # The stream has just opened and its first block has not arrived.
            return None

        rms = float(np.sqrt(np.mean(block**2)))
        return self.level_from_rms(rms)

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

    def _persist_reading(self, timestamp: datetime) -> None:
        """Store one reading for the history table, on an interval.

        The monitor samples at 10 Hz and now runs continuously, so writing on
        every sample would put 36,000 rows an hour into the database and leave
        the "recent readings" table spanning five seconds. One row per
        ``READING_SAVE_INTERVAL_SECONDS`` keeps that table readable and the
        database small.
        """
        if not self._persist:
            return

        if self._last_persist_at is not None:
            elapsed = (timestamp - self._last_persist_at).total_seconds()
            if elapsed < READING_SAVE_INTERVAL_SECONDS:
                return

        try:
            from .models import NoiseMonitorConfig, NoiseReading

            config = NoiseMonitorConfig.objects.filter(is_active=True).first()
            if not config:
                return

            NoiseReading.objects.create(
                config=config,
                raw_level=self._instant_average,
                instant_average=self._instant_average,
                session_average=self._session_average,
                instant_color=self._instant_color,
                session_color=self._session_color,
            )
            self._last_persist_at = timestamp
        except Exception as e:
            # The meter keeps working whether or not the row goes in; losing
            # history is not worth stopping the LEDs and the face for.
            logger.error(f"Error saving noise reading: {e}")
            self._last_persist_at = timestamp

    @staticmethod
    def _lcd():
        """The LCD service, or None when there is no usable display.

        Imported inside the call rather than at module scope: the display
        plugin is a declared dependency, but a missing or disabled display must
        not stop the microphone from working.
        """
        try:
            from plugins.edupi.lcd_display.lcd_service import lcd_service
        except ImportError:
            return None

        return lcd_service if lcd_service.is_initialized() else None

    def _update_face(self) -> None:
        """Show the session colour as the robot's face.

        Session, not instant: the face is the room's verdict over the lesson,
        and mirroring the live colour would have it flicker every time one
        child shouts. It is the same colour LED 2 shows, so the face and the
        LED never contradict each other.
        """
        if self._session_color == self._last_face_color:
            return

        mood_name = FACE_MOODS.get(self._session_color)
        if not mood_name:
            return

        lcd = self._lcd()
        if not lcd:
            # Deliberately not remembered: the display can initialize after
            # monitoring has already started, and the face is owed then.
            return

        if lcd.set_mood_by_name(mood_name):
            self._last_face_color = self._session_color

    def _reset_face(self) -> None:
        """Hand the face back to the display's own default mood."""
        self._last_face_color = None

        lcd = self._lcd()
        if lcd:
            lcd.set_mood_by_name(DEFAULT_FACE_MOOD)

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
            "device_status": self._device_status,
            "device_name": self._resolved_name or self._device_name,
            "microphone_available": MICROPHONE_AVAILABLE,
        }

    def is_monitoring(self) -> bool:
        """Check if monitoring is active."""
        return self._is_monitoring

    def _broadcast_update(self, data: dict) -> None:
        """Broadcast noise update to WebSocket clients.

        Args:
            data: Dictionary containing noise level data
        """
        if CHANNELS_AVAILABLE:
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    "noise_monitor",
                    {
                        "type": "noise_update",
                        "data": {
                            **data,
                            "device_status": self._device_status,
                            "device_name": self._resolved_name or self._device_name,
                            "microphone_available": MICROPHONE_AVAILABLE,
                        },
                    },
                )
            except Exception as e:
                logger.debug(f"Could not broadcast to WebSocket: {e}")

    def _broadcast_status(self, is_monitoring: bool) -> None:
        """Broadcast monitoring status change to WebSocket clients.

        Args:
            is_monitoring: Whether monitoring is active
        """
        if CHANNELS_AVAILABLE:
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    "noise_monitor",
                    {
                        "type": "monitoring_status",
                        "data": {
                            "is_monitoring": is_monitoring,
                            "instant_average": self._instant_average,
                            "session_average": self._session_average,
                            "instant_color": self._instant_color,
                            "session_color": self._session_color,
                        },
                    },
                )
            except Exception as e:
                logger.debug(f"Could not broadcast status to WebSocket: {e}")


# Global noise service instance
noise_service = NoiseMonitorService()
