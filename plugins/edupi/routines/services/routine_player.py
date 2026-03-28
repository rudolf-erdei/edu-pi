"""Routine Player Service - Manages line-by-line routine playback."""

import logging
import threading
from typing import Callable, Optional

from .tts_manager import tts_manager
from .audio_player import audio_player

logger = logging.getLogger(__name__)


class RoutinePlayer:
    """Manages playback state for routines with line-by-line control."""

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
        self._current_session = None
        self._lines = []
        self._on_line_change: Optional[Callable] = None
        self._on_status_change: Optional[Callable] = None
        self._is_ready = False
        self._audio_cache = {}  # line_index -> audio_path

    def load_routine(self, session, on_line_change=None, on_status_change=None):
        """Load a routine session for playback.

        Args:
            session: RoutineSession model instance
            on_line_change: Callback(current_line_index, line_text)
            on_status_change: Callback(status)
        """
        self._current_session = session
        self._lines = session.routine.get_lines()
        self._on_line_change = on_line_change
        self._on_status_change = on_status_change
        self._audio_cache = {}
        self._is_ready = True

        logger.info(
            f"Loaded routine: {session.routine.title} with {len(self._lines)} lines"
        )

    async def preload_audio(self):
        """Pre-generate TTS audio for all lines."""
        if not self._current_session or not self._lines:
            return

        routine = self._current_session.routine

        for i, line in enumerate(self._lines):
            # Check if uploaded audio exists
            if routine.has_custom_audio():
                # TODO: Split uploaded audio into segments
                # For now, use full audio file
                self._audio_cache[i] = routine.audio_file.path
                continue

            # Generate TTS audio
            audio_path = await tts_manager.generate_audio(
                text=line,
                engine_name=routine.tts_engine,
                language=routine.tts_language,
                voice=routine.tts_voice or None,
                speed=routine.tts_speed,
            )

            if audio_path:
                self._audio_cache[i] = audio_path

        logger.info(f"Preloaded audio for {len(self._audio_cache)} lines")

    def play_line(self, line_index: int) -> bool:
        """Play a specific line.

        Args:
            line_index: Index of line to play

        Returns:
            True if line exists and playback started
        """
        if not self._is_ready or not self._lines:
            return False

        if line_index < 0 or line_index >= len(self._lines):
            return False

        # Update session
        self._current_session.current_line_index = line_index
        self._current_session.save()

        # Get audio for this line
        audio_path = self._audio_cache.get(line_index)

        if not audio_path:
            logger.warning(f"No audio for line {line_index}")
            return False

        # Play audio with callback for next line
        def on_complete():
            if self._current_session and self._current_session.is_playing():
                # Auto-advance to next line if playing
                self.next_line()

        success = audio_player.play(audio_path, on_complete=on_complete)

        if success and self._on_line_change:
            self._on_line_change(line_index, self._lines[line_index])

        return success

    def play(self) -> bool:
        """Start or resume playback.

        Returns:
            True if playback started
        """
        if not self._is_ready:
            return False

        if self._current_session.is_paused():
            # Resume from pause
            audio_player.resume()
            self._current_session.resume()
        else:
            # Start fresh
            self._current_session.start()
            # Play current line
            return self.play_line(self._current_session.current_line_index)

        if self._on_status_change:
            self._on_status_change(self._current_session.status)

        return True

    def pause(self) -> bool:
        """Pause playback.

        Returns:
            True if paused successfully
        """
        if not self._is_ready:
            return False

        audio_player.pause()
        self._current_session.pause()

        if self._on_status_change:
            self._on_status_change(self._current_session.status)

        logger.info("Routine paused")
        return True

    def resume(self) -> bool:
        """Resume playback.

        Returns:
            True if resumed successfully
        """
        if not self._is_ready:
            return False

        audio_player.resume()
        self._current_session.resume()

        if self._on_status_change:
            self._on_status_change(self._current_session.status)

        logger.info("Routine resumed")
        return True

    def stop(self) -> bool:
        """Stop playback.

        Returns:
            True if stopped successfully
        """
        if not self._is_ready:
            return False

        audio_player.stop()
        self._current_session.stop()

        if self._on_status_change:
            self._on_status_change(self._current_session.status)

        logger.info("Routine stopped")
        return True

    def next_line(self) -> bool:
        """Advance to next line.

        Returns:
            True if advanced, False if at end
        """
        if not self._is_ready:
            return False

        current = self._current_session.current_line_index
        if current < len(self._lines) - 1:
            return self.play_line(current + 1)
        else:
            # End of routine
            self.complete()
            return False

    def prev_line(self) -> bool:
        """Go back to previous line.

        Returns:
            True if went back, False if at beginning
        """
        if not self._is_ready:
            return False

        current = self._current_session.current_line_index
        if current > 0:
            return self.play_line(current - 1)
        return False

    def complete(self) -> bool:
        """Mark routine as completed.

        Returns:
            True if completed
        """
        if not self._is_ready:
            return False

        audio_player.stop()
        self._current_session.complete()

        if self._on_status_change:
            self._on_status_change(self._current_session.status)

        logger.info("Routine completed")
        return True

    def get_current_line(self) -> Optional[str]:
        """Get the current line text."""
        if not self._is_ready or not self._lines:
            return None

        idx = self._current_session.current_line_index
        if 0 <= idx < len(self._lines):
            return self._lines[idx]
        return None

    def get_line_count(self) -> int:
        """Get total number of lines."""
        return len(self._lines) if self._lines else 0

    def get_progress(self) -> tuple:
        """Get playback progress.

        Returns:
            Tuple of (current_line_index, total_lines, progress_percent)
        """
        if not self._is_ready:
            return (0, 0, 0)

        current = self._current_session.current_line_index
        total = len(self._lines)
        percent = int((current / total) * 100) if total > 0 else 0
        return (current, total, percent)

    def is_playing(self) -> bool:
        """Check if routine is currently playing."""
        return (
            self._is_ready
            and self._current_session
            and self._current_session.is_playing()
        )

    def is_paused(self) -> bool:
        """Check if routine is paused."""
        return (
            self._is_ready
            and self._current_session
            and self._current_session.is_paused()
        )

    def get_status(self) -> Optional[str]:
        """Get current playback status."""
        if not self._is_ready or not self._current_session:
            return None
        return self._current_session.status

    def get_session(self):
        """Get current session."""
        return self._current_session


# Singleton instance
routine_player = RoutinePlayer()
