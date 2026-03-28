"""TTS Service Manager - Multi-engine text-to-speech support."""

import asyncio
import hashlib
import logging
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)


class BaseTTSEngine(ABC):
    """Abstract base class for TTS engines."""

    def __init__(self, name: str):
        self.name = name
        self._available = None

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this TTS engine is available."""
        pass

    @abstractmethod
    async def generate_audio(
        self,
        text: str,
        output_path: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> bool:
        """Generate audio file from text.

        Args:
            text: Text to convert to speech
            output_path: Path to save audio file
            language: Language code (e.g., 'en', 'ro')
            voice: Specific voice to use (engine-specific)
            speed: Speed multiplier (0.5 = slow, 2.0 = fast)

        Returns:
            True if audio was generated successfully
        """
        pass

    def get_voices(self) -> list:
        """Get list of available voices for this engine."""
        return []


class Pyttsx3Engine(BaseTTSEngine):
    """pyttsx3 TTS engine (offline, system voices)."""

    def __init__(self):
        super().__init__("pyttsx3")
        self._engine = None

    def is_available(self) -> bool:
        """Check if pyttsx3 is available."""
        if self._available is not None:
            return self._available

        try:
            import pyttsx3

            self._available = True
        except ImportError:
            self._available = False
            logger.warning("pyttsx3 not installed")

        return self._available

    async def generate_audio(
        self,
        text: str,
        output_path: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> bool:
        """Generate audio using pyttsx3."""
        if not self.is_available():
            return False

        try:
            import pyttsx3

            # Run in thread to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._generate_sync,
                text,
                output_path,
                voice,
                speed,
            )
        except Exception as e:
            logger.error(f"pyttsx3 generation error: {e}")
            return False

    def _generate_sync(
        self, text: str, output_path: str, voice: Optional[str], speed: float
    ) -> bool:
        """Synchronous audio generation."""
        try:
            import pyttsx3

            engine = pyttsx3.init()

            # Set voice if specified
            if voice:
                voices = engine.getProperty("voices")
                for v in voices:
                    if voice.lower() in v.name.lower():
                        engine.setProperty("voice", v.id)
                        break

            # Set rate (default is usually 200)
            rate = engine.getProperty("rate")
            engine.setProperty("rate", int(rate * speed))

            # Save to file
            engine.save_to_file(text, output_path)
            engine.runAndWait()

            return os.path.exists(output_path)
        except Exception as e:
            logger.error(f"pyttsx3 sync generation error: {e}")
            return False

    def get_voices(self) -> list:
        """Get available voices."""
        if not self.is_available():
            return []

        try:
            import pyttsx3

            engine = pyttsx3.init()
            voices = engine.getProperty("voices")
            return [
                {"id": v.id, "name": v.name, "languages": v.languages} for v in voices
            ]
        except Exception as e:
            logger.error(f"Error getting pyttsx3 voices: {e}")
            return []


class EdgeTTSEngine(BaseTTSEngine):
    """Edge TTS engine (online, high quality)."""

    # Common Edge TTS voices by language
    DEFAULT_VOICES = {
        "en": "en-US-AriaNeural",
        "ro": "ro-RO-AlinaNeural",
        "es": "es-ES-ElviraNeural",
        "fr": "fr-FR-DeniseNeural",
        "de": "de-DE-KatjaNeural",
        "it": "it-IT-ElsaNeural",
        "pt": "pt-BR-FranciscaNeural",
        "ru": "ru-RU-SvetlanaNeural",
        "zh": "zh-CN-XiaoxiaoNeural",
        "ja": "ja-JP-NanamiNeural",
        "ko": "ko-KR-SunHiNeural",
    }

    def __init__(self):
        super().__init__("edge_tts")

    def is_available(self) -> bool:
        """Check if edge-tts is available."""
        if self._available is not None:
            return self._available

        try:
            import edge_tts

            self._available = True
        except ImportError:
            self._available = False
            logger.warning("edge-tts not installed")

        return self._available

    async def generate_audio(
        self,
        text: str,
        output_path: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> bool:
        """Generate audio using Edge TTS."""
        if not self.is_available():
            return False

        try:
            import edge_tts

            # Select voice
            if not voice:
                voice = self.DEFAULT_VOICES.get(language, "en-US-AriaNeural")

            # Create communicate instance
            communicate = edge_tts.Communicate(text, voice)

            # Adjust speed (Edge TTS uses prosody rate)
            # +50% = 1.5, -50% = 0.5
            rate = f"{int((speed - 1) * 100):+d}%"

            # Save audio
            await communicate.save(output_path)

            return os.path.exists(output_path)
        except Exception as e:
            logger.error(f"Edge TTS generation error: {e}")
            return False

    def get_voices(self) -> list:
        """Get available voices (limited selection)."""
        voices = []
        for lang, voice_id in self.DEFAULT_VOICES.items():
            voices.append(
                {
                    "id": voice_id,
                    "name": voice_id.split("-")[-1].replace("Neural", ""),
                    "language": lang,
                }
            )
        return voices


class GTTSengine(BaseTTSEngine):
    """Google TTS engine (online)."""

    def __init__(self):
        super().__init__("gtts")

    def is_available(self) -> bool:
        """Check if gTTS is available."""
        if self._available is not None:
            return self._available

        try:
            from gtts import gTTS

            self._available = True
        except ImportError:
            self._available = False
            logger.warning("gTTS not installed")

        return self._available

    async def generate_audio(
        self,
        text: str,
        output_path: str,
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
    ) -> bool:
        """Generate audio using gTTS."""
        if not self.is_available():
            return False

        try:
            from gtts import gTTS

            # gTTS doesn't support speed directly, we'll handle it post-generation
            tts = gTTS(text=text, lang=language, slow=(speed < 0.8))
            tts.save(output_path)

            # TODO: Use ffmpeg or pydub to adjust speed if needed
            # For now, gTTS 'slow' parameter handles basic speed adjustment

            return os.path.exists(output_path)
        except Exception as e:
            logger.error(f"gTTS generation error: {e}")
            return False

    def get_voices(self) -> list:
        """gTTS uses language codes, not voices."""
        return [
            {"id": "en", "name": "English", "language": "en"},
            {"id": "ro", "name": "Romanian", "language": "ro"},
            {"id": "es", "name": "Spanish", "language": "es"},
            {"id": "fr", "name": "French", "language": "fr"},
            {"id": "de", "name": "German", "language": "de"},
            {"id": "it", "name": "Italian", "language": "it"},
            {"id": "pt", "name": "Portuguese", "language": "pt"},
        ]


class TTSManager:
    """Manager for multiple TTS engines with caching."""

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.engines = {
            "pyttsx3": Pyttsx3Engine(),
            "edge_tts": EdgeTTSEngine(),
            "gtts": GTTSengine(),
        }

        # Cache directory for generated audio
        self.cache_dir = Path(settings.MEDIA_ROOT) / "routines" / "tts_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._initialized = True
        logger.info("TTS Manager initialized")

    def get_available_engines(self) -> dict:
        """Get all available TTS engines."""
        return {
            name: engine
            for name, engine in self.engines.items()
            if engine.is_available()
        }

    def get_default_engine(self) -> Optional[BaseTTSEngine]:
        """Get the first available engine as default."""
        available = self.get_available_engines()
        if available:
            # Prefer offline engines first
            for name in ["pyttsx3", "edge_tts", "gtts"]:
                if name in available:
                    return available[name]
        return None

    def get_engine(self, name: str) -> Optional[BaseTTSEngine]:
        """Get a specific TTS engine by name."""
        engine = self.engines.get(name)
        if engine and engine.is_available():
            return engine
        return None

    def _get_cache_key(
        self,
        text: str,
        engine_name: str,
        language: str,
        voice: Optional[str],
        speed: float,
    ) -> str:
        """Generate cache key for audio file."""
        key_data = f"{text}:{engine_name}:{language}:{voice}:{speed}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _get_cache_path(self, cache_key: str) -> str:
        """Get path for cached audio file."""
        return str(self.cache_dir / f"{cache_key}.mp3")

    async def generate_audio(
        self,
        text: str,
        engine_name: str = "pyttsx3",
        language: str = "en",
        voice: Optional[str] = None,
        speed: float = 1.0,
        use_cache: bool = True,
    ) -> Optional[str]:
        """Generate audio for text using specified engine.

        Args:
            text: Text to convert to speech
            engine_name: TTS engine to use
            language: Language code
            voice: Voice name (engine-specific)
            speed: Speed multiplier
            use_cache: Whether to use cached audio

        Returns:
            Path to audio file, or None if generation failed
        """
        if not text or not text.strip():
            return None

        # Check cache first
        cache_key = self._get_cache_key(text, engine_name, language, voice, speed)
        cache_path = self._get_cache_path(cache_key)

        if use_cache and os.path.exists(cache_path):
            logger.debug(f"Using cached TTS audio: {cache_path}")
            return cache_path

        # Get engine
        engine = self.get_engine(engine_name)
        if not engine:
            # Fallback to default engine
            engine = self.get_default_engine()
            if not engine:
                logger.error("No TTS engine available")
                return None

        # Generate audio
        success = await engine.generate_audio(text, cache_path, language, voice, speed)

        if success:
            return cache_path
        else:
            logger.error(f"TTS generation failed for engine: {engine.name}")
            return None

    def clear_cache(self):
        """Clear all cached TTS audio files."""
        try:
            for file in self.cache_dir.glob("*.mp3"):
                file.unlink()
            logger.info("TTS cache cleared")
        except Exception as e:
            logger.error(f"Error clearing TTS cache: {e}")

    def get_cache_size(self) -> int:
        """Get cache size in bytes."""
        total_size = 0
        for file in self.cache_dir.glob("*.mp3"):
            total_size += file.stat().st_size
        return total_size


# Singleton instance
tts_manager = TTSManager()
