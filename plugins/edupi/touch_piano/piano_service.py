"""Piano service for Touch Piano plugin.

Manages GPIO touch detection and audio synthesis for piano notes.
"""

import logging
import threading
import time
import wave
import math
import struct
import os
import tempfile
import atexit
import warnings
from typing import Optional, Callable, Dict, List
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger(__name__)

# Suppress gpiozero pin factory fallback warnings on non-Pi systems
warnings.filterwarnings("ignore", category=UserWarning, message=".*Falling back.*")

# Try to import GPIO libraries
try:
    from gpiozero import DigitalInputDevice, Button

    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

    class DigitalInputDevice:
        """Mock DigitalInputDevice for development."""

        def __init__(self, pin, pull_up=True):
            self.pin = pin
            self._is_pressed = False
            self._when_pressed = None
            self._when_released = None
            self._name = f"MockPin{pin}"
            logger.info(f"Mock GPIO pin {pin} initialized")

        @property
        def is_pressed(self):
            return self._is_pressed

        @property
        def when_pressed(self):
            return self._when_pressed

        @when_pressed.setter
        def when_pressed(self, callback):
            self._when_pressed = callback

        @property
        def when_released(self):
            return self._when_released

        @when_released.setter
        def when_released(self, callback):
            self._when_released = callback

        def close(self):
            logger.info(f"Mock GPIO pin {self.pin} closed")


# Try to import audio libraries
try:
    import pygame
    import pygame.mixer

    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

# Note frequencies (equal temperament, A4 = 440Hz)
NOTE_FREQUENCIES = {
    "C4": 261.63,
    "C#4": 277.18,
    "D4": 293.66,
    "D#4": 311.13,
    "E4": 329.63,
    "F4": 349.23,
    "F#4": 369.99,
    "G4": 392.00,
    "G#4": 415.30,
    "A4": 440.00,
    "A#4": 466.16,
    "B4": 493.88,
    "C5": 523.25,
    "D5": 587.33,
    "E5": 659.25,
}

# Default piano key mapping
# Pins updated to avoid SPI display conflicts (GPIO 8, 9, 10, 11 used by display)
DEFAULT_KEY_MAPPING = {
    1: {
        "note": "C4",
        "frequency": 261.63,
        "gpio_pin": 4,
        "label": "Do",
        "color": "#FF6B6B",
    },
    2: {
        "note": "D4",
        "frequency": 293.66,
        "gpio_pin": 7,
        "label": "Re",
        "color": "#4ECDC4",
    },
    3: {
        "note": "E4",
        "frequency": 329.63,
        "gpio_pin": 20,
        "label": "Mi",
        "color": "#45B7D1",
    },
    4: {
        "note": "F4",
        "frequency": 349.23,
        "gpio_pin": 21,
        "label": "Fa",
        "color": "#96CEB4",
    },
    5: {
        "note": "G4",
        "frequency": 392.00,
        "gpio_pin": 12,
        "label": "Sol",
        "color": "#FFEAA7",
    },
    6: {
        "note": "A4",
        "frequency": 440.00,
        "gpio_pin": 2,
        "label": "La",
        "color": "#DDA0DD",
    },
}


class PianoService:
    """
    Service for managing touch piano functionality.

    Handles GPIO touch detection, audio synthesis, and real-time
    communication with the web interface.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern for piano service."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the piano service."""
        if self._initialized:
            return

        self._initialized = True
        self._gpio_devices: Dict[int, DigitalInputDevice] = {}
        self._key_states: Dict[int, bool] = {}
        self._key_timestamps: Dict[int, float] = {}
        self._sounds: Dict[int, any] = {}
        self._audio_initialized = False
        self._volume = 0.8
        self._sensitivity = 5
        self._key_press_callback: Optional[Callable] = None
        self._key_release_callback: Optional[Callable] = None
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._current_session_id: Optional[int] = None
        self._temp_dir = tempfile.mkdtemp(prefix="piano_sounds_")
        self._active_notes: Dict[int, float] = {}  # Track active notes with timestamps
        self._max_note_duration = 5.0  # Maximum note duration in seconds

        logger.info("PianoService initialized")

        # Register cleanup on exit
        atexit.register(self.cleanup)

    def initialize_audio(self, volume: int = 80, audio_device: str = "default") -> bool:
        """
        Initialize audio playback system.

        Args:
            volume: Volume level (0-100)
            audio_device: ALSA audio device name

        Returns:
            True if audio was initialized successfully
        """
        if not PYGAME_AVAILABLE:
            logger.warning("Pygame not available, audio will not work")
            return False

        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            self._volume = volume / 100.0
            pygame.mixer.music.set_volume(self._volume)
            self._audio_initialized = True
            logger.info(
                f"Audio initialized - volume: {volume}%, device: {audio_device}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to initialize audio: {e}")
            return False

    def initialize_gpio(self, key_mapping: Optional[Dict] = None) -> bool:
        """
        Initialize GPIO pins for touch detection.

        Args:
            key_mapping: Dictionary mapping key numbers to GPIO pins

        Returns:
            True if GPIO was initialized successfully
        """
        self.cleanup_gpio()

        mapping = key_mapping or DEFAULT_KEY_MAPPING

        try:
            for key_num, config in mapping.items():
                gpio_pin = config.get("gpio_pin")
                if gpio_pin is None:
                    continue

                # Create digital input with pull-up resistor
                device = DigitalInputDevice(gpio_pin, pull_up=True)
                device._name = f"Key{key_num}"

                # Set up callbacks
                device.when_pressed = lambda k=key_num: self._on_key_pressed(k)
                device.when_released = lambda k=key_num: self._on_key_released(k)

                self._gpio_devices[key_num] = device
                self._key_states[key_num] = False
                self._key_timestamps[key_num] = 0

                logger.info(f"GPIO initialized for key {key_num} on pin {gpio_pin}")

            return True
        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")
            return False

    def _generate_note_sound(
        self, frequency: float, duration: float = 1.0, volume: float = 0.5
    ) -> str:
        """
        Generate a WAV file for a musical note.

        Args:
            frequency: Note frequency in Hz
            duration: Note duration in seconds
            volume: Volume level (0.0 to 1.0)

        Returns:
            Path to the generated WAV file
        """
        sample_rate = 44100
        num_samples = int(sample_rate * duration)

        # Generate sine wave with envelope
        wav_file = os.path.join(self._temp_dir, f"note_{frequency:.2f}.wav")

        if os.path.exists(wav_file):
            return wav_file

        try:
            with wave.open(wav_file, "w") as wav:
                wav.setnchannels(1)  # Mono
                wav.setsampwidth(2)  # 16-bit
                wav.setframerate(sample_rate)

                # Generate samples
                for i in range(num_samples):
                    t = i / sample_rate
                    # Attack-decay envelope
                    if t < 0.01:  # Attack
                        env = t / 0.01
                    elif t < 0.3:  # Decay
                        env = 1.0 - (t - 0.01) / 0.29 * 0.3
                    else:  # Sustain
                        env = 0.7 * math.exp(-(t - 0.3) * 3)

                    # Sine wave with slight harmonics for piano-like sound
                    sample = (
                        volume
                        * env
                        * (
                            0.6 * math.sin(2 * math.pi * frequency * t)
                            + 0.3 * math.sin(2 * math.pi * frequency * 2 * t)
                            + 0.1 * math.sin(2 * math.pi * frequency * 3 * t)
                        )
                    )

                    # Convert to 16-bit signed integer
                    sample_int = int(sample * 32767)
                    sample_int = max(-32768, min(32767, sample_int))
                    wav.writeframes(struct.pack("<h", sample_int))

            return wav_file
        except Exception as e:
            logger.error(f"Failed to generate note sound: {e}")
            return None

    def load_note_sounds(self, key_mapping: Optional[Dict] = None) -> None:
        """
        Pre-generate sound files for all piano notes.

        Args:
            key_mapping: Dictionary mapping key numbers to note configurations
        """
        if not PYGAME_AVAILABLE:
            logger.warning("Pygame not available, cannot load sounds")
            return

        mapping = key_mapping or DEFAULT_KEY_MAPPING

        for key_num, config in mapping.items():
            frequency = config.get("frequency", 440.0)
            wav_file = self._generate_note_sound(frequency, duration=2.0, volume=0.5)
            if wav_file:
                try:
                    sound = pygame.mixer.Sound(wav_file)
                    self._sounds[key_num] = sound
                    logger.debug(f"Loaded sound for key {key_num} ({frequency}Hz)")
                except Exception as e:
                    logger.error(f"Failed to load sound for key {key_num}: {e}")

    def _on_key_pressed(self, key_num: int) -> None:
        """
        Handle key press event.

        Args:
            key_num: The key number (1-6)
        """
        if key_num in self._key_states and self._key_states[key_num]:
            return  # Already pressed

        self._key_states[key_num] = True
        self._key_timestamps[key_num] = time.time()

        logger.debug(f"Key {key_num} pressed")

        # Play sound
        self._play_note(key_num)

        # Notify callback
        if self._key_press_callback:
            try:
                self._key_press_callback(key_num)
            except Exception as e:
                logger.error(f"Error in key press callback: {e}")

    def _on_key_released(self, key_num: int) -> None:
        """
        Handle key release event.

        Args:
            key_num: The key number (1-6)
        """
        if key_num not in self._key_states or not self._key_states[key_num]:
            return  # Not pressed

        press_duration = time.time() - self._key_timestamps.get(key_num, time.time())
        self._key_states[key_num] = False

        logger.debug(f"Key {key_num} released (duration: {press_duration:.3f}s)")

        # Stop sound
        self._stop_note(key_num)

        # Notify callback
        if self._key_release_callback:
            try:
                self._key_release_callback(key_num, press_duration)
            except Exception as e:
                logger.error(f"Error in key release callback: {e}")

    def _play_note(self, key_num: int) -> None:
        """
        Play a piano note.

        Args:
            key_num: The key number (1-6)
        """
        if not PYGAME_AVAILABLE or not self._audio_initialized:
            logger.debug(f"Would play note for key {key_num} (audio not available)")
            return

        try:
            if key_num in self._sounds:
                # Stop any existing note first
                self._sounds[key_num].stop()
                sound = self._sounds[key_num]
                sound.set_volume(self._volume)
                # Play once (loops=0), not indefinitely
                sound.play(loops=0)
                self._active_notes[key_num] = time.time()
                logger.debug(f"Playing note for key {key_num}")
        except Exception as e:
            logger.error(f"Failed to play note for key {key_num}: {e}")

    def _stop_note(self, key_num: int) -> None:
        """
        Stop playing a piano note.

        Args:
            key_num: The key number (1-6)
        """
        if not PYGAME_AVAILABLE or not self._audio_initialized:
            return

        try:
            if key_num in self._sounds:
                self._sounds[key_num].stop()
                # Remove from active notes tracking
                self._active_notes.pop(key_num, None)
                logger.debug(f"Stopped note for key {key_num}")
        except Exception as e:
            logger.error(f"Failed to stop note for key {key_num}: {e}")

    def _check_stuck_notes(self) -> None:
        """Check for and stop any notes that have been playing too long."""
        if not PYGAME_AVAILABLE or not self._audio_initialized:
            return

        current_time = time.time()
        stuck_keys = [
            key_num
            for key_num, start_time in self._active_notes.items()
            if (current_time - start_time) > self._max_note_duration
        ]

        for key_num in stuck_keys:
            logger.warning(f"Auto-stopping stuck note for key {key_num}")
            self._stop_note(key_num)
            # Also reset key state if it was stuck
            if key_num in self._key_states:
                self._key_states[key_num] = False

    def start_monitoring(self) -> None:
        """Start the GPIO monitoring thread."""
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            return

        self._stop_event.clear()
        self._monitoring_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self._monitoring_thread.start()
        logger.info("GPIO monitoring started")

    def _monitoring_loop(self) -> None:
        """Main monitoring loop for GPIO state."""
        while not self._stop_event.is_set():
            # Check for stuck notes (auto-stop after max duration)
            self._check_stuck_notes()

            if GPIO_AVAILABLE:
                # gpiozero handles events automatically
                time.sleep(0.1)
            else:
                # Mock mode - simulate reading
                time.sleep(0.1)

    def stop_monitoring(self) -> None:
        """Stop the GPIO monitoring thread."""
        self._stop_event.set()
        if self._monitoring_thread and self._monitoring_thread.is_alive():
            self._monitoring_thread.join(timeout=2)
        logger.info("GPIO monitoring stopped")

    def set_key_press_callback(self, callback: Callable) -> None:
        """
        Set callback for key press events.

        Args:
            callback: Function to call when a key is pressed
        """
        self._key_press_callback = callback

    def set_key_release_callback(self, callback: Callable) -> None:
        """
        Set callback for key release events.

        Args:
            callback: Function to call when a key is released
        """
        self._key_release_callback = callback

    def get_key_states(self) -> Dict[int, bool]:
        """
        Get current state of all keys.

        Returns:
            Dictionary mapping key numbers to pressed state
        """
        return self._key_states.copy()

    def is_key_pressed(self, key_num: int) -> bool:
        """
        Check if a specific key is pressed.

        Args:
            key_num: The key number (1-6)

        Returns:
            True if the key is pressed
        """
        return self._key_states.get(key_num, False)

    def set_volume(self, volume: int) -> None:
        """
        Set the piano volume.

        Args:
            volume: Volume level (0-100)
        """
        self._volume = max(0, min(100, volume)) / 100.0
        if self._audio_initialized and PYGAME_AVAILABLE:
            pygame.mixer.music.set_volume(self._volume)
        logger.info(f"Volume set to {volume}%")

    def set_sensitivity(self, sensitivity: int) -> None:
        """
        Set touch sensitivity.

        Args:
            sensitivity: Sensitivity level (1-10)
        """
        self._sensitivity = max(1, min(10, sensitivity))
        logger.info(f"Sensitivity set to {self._sensitivity}")

    def set_session_id(self, session_id: Optional[int]) -> None:
        """
        Set the current piano session ID.

        Args:
            session_id: Session ID or None
        """
        self._current_session_id = session_id
        logger.info(f"Session ID set to {session_id}")

    def get_session_id(self) -> Optional[int]:
        """Get the current piano session ID."""
        return self._current_session_id

    def cleanup_gpio(self) -> None:
        """Cleanup GPIO resources."""
        for key_num, device in self._gpio_devices.items():
            try:
                device.close()
                logger.debug(f"Closed GPIO device for key {key_num}")
            except Exception as e:
                logger.error(f"Error closing GPIO device {key_num}: {e}")

        self._gpio_devices.clear()
        self._key_states.clear()
        self._key_timestamps.clear()
        logger.info("GPIO cleanup completed")

    def cleanup_audio(self) -> None:
        """Cleanup audio resources."""
        if PYGAME_AVAILABLE and self._audio_initialized:
            try:
                # Stop all sounds
                for sound in self._sounds.values():
                    sound.stop()

                pygame.mixer.quit()
                self._audio_initialized = False
                logger.info("Audio cleanup completed")
            except Exception as e:
                logger.error(f"Error cleaning up audio: {e}")

    def cleanup(self) -> None:
        """Cleanup all resources."""
        self.stop_monitoring()
        self.cleanup_gpio()
        self.cleanup_audio()

        # Clean up temp directory
        try:
            import shutil

            shutil.rmtree(self._temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp directory: {self._temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}")

    def simulate_key_press(self, key_num: int) -> None:
        """
        Simulate a key press (for testing and web interface).

        Args:
            key_num: The key number (1-6)
        """
        self._on_key_pressed(key_num)

    def simulate_key_release(self, key_num: int) -> None:
        """
        Simulate a key release (for testing and web interface).

        Args:
            key_num: The key number (1-6)
        """
        self._on_key_released(key_num)


# Global piano service instance
piano_service = PianoService()
