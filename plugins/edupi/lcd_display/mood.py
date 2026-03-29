"""Mood system for LCD Display robot face.

Defines different moods and their corresponding face expressions.
Each mood has 2 face variations that alternate (5s + 2s).
"""

from enum import Enum
from typing import Callable, List, Tuple


class Mood(Enum):
    """Robot mood states with their face expressions."""

    HAPPY = "happy"
    NEUTRAL = "neutral"  # Straight face
    SAD = "sad"
    ANGRY = "angry"
    LAUGHING = "laughing"
    CONCENTRATED = "concentrated"  # Learning mode

    @classmethod
    def get_default(cls) -> "Mood":
        """Get the default mood (HAPPY)."""
        return cls.HAPPY

    @classmethod
    def get_all_moods(cls) -> List[str]:
        """Get list of all mood names."""
        return [mood.value for mood in cls]

    def get_description(self) -> str:
        """Get human-readable description of the mood."""
        descriptions = {
            Mood.HAPPY: "Happy - Robot is cheerful and smiling",
            Mood.NEUTRAL: "Neutral - Robot has a straight face",
            Mood.SAD: "Sad - Robot is feeling down",
            Mood.ANGRY: "Angry - Robot is upset",
            Mood.LAUGHING: "Laughing - Robot is having fun",
            Mood.CONCENTRATED: "Concentrated - Robot is focused on learning",
        }
        return descriptions.get(self, "Unknown mood")

    def get_face_names(self) -> Tuple[str, str]:
        """Get the two face variation names for this mood."""
        face_names = {
            Mood.HAPPY: ("smile", "big_grin"),
            Mood.NEUTRAL: ("straight", "blink"),
            Mood.SAD: ("sad", "sadder"),
            Mood.ANGRY: ("angry", "furious"),
            Mood.LAUGHING: ("laugh", "big_laugh"),
            Mood.CONCENTRATED: ("focused", "thinking"),
        }
        return face_names.get(self, ("default", "default"))


class MoodManager:
    """Manages mood transitions and validation."""

    def __init__(self):
        self._current_mood = Mood.get_default()
        self._current_face_index = 0

    @property
    def current_mood(self) -> Mood:
        """Get current mood."""
        return self._current_mood

    @current_mood.setter
    def current_mood(self, mood: Mood):
        """Set current mood and reset face index."""
        self._current_mood = mood
        self._current_face_index = 0

    def set_mood_by_name(self, mood_name: str) -> bool:
        """Set mood by name string."""
        try:
            self.current_mood = Mood(mood_name)
            return True
        except ValueError:
            return False

    def toggle_face(self) -> str:
        """Toggle between the two faces of current mood."""
        face_names = self._current_mood.get_face_names()
        self._current_face_index = (self._current_face_index + 1) % 2
        return face_names[self._current_face_index]

    def get_current_face_name(self) -> str:
        """Get the name of current face."""
        face_names = self._current_mood.get_face_names()
        return face_names[self._current_face_index]

    def is_misbehaving_mood(self) -> bool:
        """Check if current mood indicates misbehaving."""
        return self._current_mood in [Mood.NEUTRAL, Mood.SAD, Mood.ANGRY]
