"""Audio Player Service - Handles audio playback using pygame."""

import logging
import threading
from pathlib import Path
from typing import Callable, Optional

import pygame

logger = logging.getLogger(__name__)


class AudioPlayer:
    """Audio player using pygame for playback control."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return

        self._initialized = True
        self._current_sound = None
        self._current_channel = None
        self._is_playing = False
        self._on_complete_callback: Optional[Callable] = None
        self._volume = 1.0

        # Initialize pygame mixer
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            logger.info("Audio player initialized")
        except pygame.error as e:
            logger.error(f"Failed to initialize audio player: {e}")

    def play(
        self,
        audio_path: str,
        on_complete: Optional[Callable] = None,
        volume: float = 1.0,
    ) -> bool:
        """Play an audio file.

        Args:
            audio_path: Path to audio file (MP3/WAV)
            on_complete: Callback function when playback completes
            volume: Playback volume (0.0 to 1.0)

        Returns:
            True if playback started successfully
        """
        try:
            # Stop any currently playing audio
            self.stop()

            # Load and play new audio
            if not Path(audio_path).exists():
                logger.error(f"Audio file not found: {audio_path}")
                return False

            self._current_sound = pygame.mixer.Sound(audio_path)
            self._volume = volume
            self._current_sound.set_volume(volume)

            self._current_channel = self._current_sound.play()
            self._is_playing = True
            self._on_complete_callback = on_complete

            # Start monitoring thread for completion
            monitor_thread = threading.Thread(
                target=self._monitor_playback,
                daemon=True,
            )
            monitor_thread.start()

            logger.info(f"Started playing: {audio_path}")
            return True

        except pygame.error as e:
            logger.error(f"Error playing audio: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error playing audio: {e}")
            return False

    def _monitor_playback(self):
        """Monitor playback and call callback when complete."""
        if not self._current_channel:
            return

        clock = pygame.time.Clock()
        while self._is_playing and self._current_channel.get_busy():
            clock.tick(10)  # Check every 100ms

        if self._is_playing:  # Playback finished naturally
            self._is_playing = False
            if self._on_complete_callback:
                try:
                    self._on_complete_callback()
                except Exception as e:
                    logger.error(f"Error in completion callback: {e}")

    def stop(self) -> None:
        """Stop current playback."""
        if self._current_channel:
            try:
                self._current_channel.stop()
            except Exception:
                pass

        self._is_playing = False
        self._current_sound = None
        self._current_channel = None

    def pause(self) -> None:
        """Pause current playback."""
        if self._current_channel:
            try:
                self._current_channel.pause()
                self._is_playing = False
                logger.debug("Audio paused")
            except Exception as e:
                logger.error(f"Error pausing audio: {e}")

    def resume(self) -> None:
        """Resume paused playback."""
        if self._current_channel:
            try:
                self._current_channel.unpause()
                self._is_playing = True
                logger.debug("Audio resumed")
            except Exception as e:
                logger.error(f"Error resuming audio: {e}")

    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        if not self._current_channel:
            return False
        return self._current_channel.get_busy()

    def set_volume(self, volume: float) -> None:
        """Set playback volume (0.0 to 1.0)."""
        self._volume = max(0.0, min(1.0, volume))
        if self._current_sound:
            self._current_sound.set_volume(self._volume)

    def get_volume(self) -> float:
        """Get current volume."""
        return self._volume


# Singleton instance
audio_player = AudioPlayer()
