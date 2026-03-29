"""LCD service for LCD Display plugin.

Manages SPI communication with ILI9341 TFT LCD display
and handles drawing operations including the startup smiley face.
"""

import logging
import threading
import time
from typing import Optional, Tuple
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# Try to import luma libraries for LCD control
try:
    from luma.core.interface.serial import spi
    from luma.core.render import canvas
    from luma.lcd.device import ili9341
    from gpiozero import PWMLED

    LCD_AVAILABLE = True
except ImportError:
    LCD_AVAILABLE = False

    # Mock classes for development
    class MockSPIDevice:
        """Mock SPI device for development on non-Pi systems."""

        def __init__(self, port, device, gpio_DC, gpio_RST):
            self.port = port
            self.device = device
            self.gpio_DC = gpio_DC
            self.gpio_RST = gpio_RST
            logger.info(f"Mock SPI device initialized (port={port}, device={device})")

    class MockILI9341:
        """Mock ILI9341 device for development."""

        def __init__(self, serial_interface, width=320, height=240, rotate=0):
            self.serial_interface = serial_interface
            self.width = width
            self.height = height
            self.rotate = rotate
            self.backlight = None
            logger.info(f"Mock ILI9341 display initialized ({width}x{height})")

        def display(self, image):
            logger.debug("Mock display updated")

        def cleanup(self):
            logger.info("Mock ILI9341 display cleaned up")

    class MockPWMLED:
        """Mock PWM LED for backlight control."""

        def __init__(self, pin):
            self.pin = pin
            self._value = 1.0
            logger.info(f"Mock backlight initialized on pin {pin}")

        @property
        def value(self):
            return self._value

        @value.setter
        def value(self, val):
            self._value = max(0.0, min(1.0, val))
            logger.debug(f"Mock backlight set to {self._value}")

        def close(self):
            logger.info(f"Mock backlight on pin {self.pin} closed")

    spi = MockSPIDevice
    ili9341 = MockILI9341
    canvas = None
    PWMLED = MockPWMLED


class LCDService:
    """
    Service for managing SPI TFT LCD display.

    Handles initialization, drawing operations, and cleanup for
    ILI9341-based displays. Shows a smiling face on startup.
    """

    _instance = None
    _lock = threading.Lock()

    # Display dimensions (320x240 landscape by default)
    DEFAULT_WIDTH = 320
    DEFAULT_HEIGHT = 240

    # Pin assignments
    DEFAULT_PINS = {
        "cs": 8,  # GPIO 8 - SPI Chip Select (CE0)
        "dc": 23,  # GPIO 23 - Data/Command
        "rst": 25,  # GPIO 25 - Reset
        "bl": 18,  # GPIO 18 - Backlight (PWM)
    }

    def __new__(cls):
        """Singleton pattern for LCD service."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the LCD service."""
        if self._initialized:
            return

        self._initialized = True
        self._device = None
        self._serial = None
        self._backlight = None
        self._width = self.DEFAULT_WIDTH
        self._height = self.DEFAULT_HEIGHT
        self._rotation = 0
        self._is_initialized = False
        self._pins = self.DEFAULT_PINS.copy()

        logger.info("LCDService initialized")

    def initialize(
        self,
        rotation: int = 0,
        backlight: int = 100,
        contrast: float = 1.0,
        pins: Optional[dict] = None,
    ) -> bool:
        """
        Initialize the LCD display.

        Args:
            rotation: Display rotation (0, 90, 180, 270)
            backlight: Backlight brightness (0-100)
            contrast: Display contrast (0.5-2.0)
            pins: Dictionary of pin assignments (cs, dc, rst, bl)

        Returns:
            True if initialization was successful
        """
        if self._is_initialized:
            logger.warning("LCD already initialized")
            return True

        if not LCD_AVAILABLE:
            logger.warning("LCD libraries not available, using mock mode")
            self._setup_mock_device(rotation, backlight)
            return True

        # Update pin assignments if provided
        if pins:
            self._pins.update(pins)

        try:
            # Initialize SPI interface
            self._serial = spi(
                port=0,
                device=0,
                gpio_DC=self._pins["dc"],
                gpio_RST=self._pins["rst"],
            )

            # Initialize ILI9341 device
            self._device = ili9341(
                self._serial,
                width=self._width,
                height=self._height,
                rotate=rotation,
            )

            # Initialize backlight with PWM
            self._backlight = PWMLED(self._pins["bl"])
            self.set_backlight(backlight)

            self._rotation = rotation
            self._is_initialized = True

            logger.info(f"LCD initialized: {self._width}x{self._height} @ {rotation}°")

            # Show startup smiley face
            self.show_smiley_face()

            return True

        except Exception as e:
            logger.error(f"Failed to initialize LCD: {e}")
            return False

    def _setup_mock_device(self, rotation: int, backlight: int):
        """Setup mock device for development."""
        self._serial = spi(0, 0, self._pins["dc"], self._pins["rst"])
        self._device = ili9341(
            self._serial,
            width=self._width,
            height=self._height,
            rotate=rotation,
        )
        self._backlight = PWMLED(self._pins["bl"])
        self.set_backlight(backlight)
        self._rotation = rotation
        self._is_initialized = True

        logger.info("Mock LCD device setup complete")
        self.show_smiley_face()

    def set_backlight(self, brightness: int) -> None:
        """
        Set the display backlight brightness.

        Args:
            brightness: Brightness level (0-100)
        """
        if self._backlight:
            value = max(0, min(100, brightness)) / 100.0
            self._backlight.value = value
            logger.debug(f"Backlight set to {brightness}%")

    def show_smiley_face(self) -> None:
        """Display a simple smiling face on the LCD."""
        if not self._device:
            logger.warning("LCD not initialized, cannot show smiley face")
            return

        try:
            # Create image with black background
            img = Image.new("RGB", (self._width, self._height), "black")
            draw = ImageDraw.Draw(img)

            # Draw smiling face
            self._draw_smiley_face(draw, self._width, self._height)

            # Display the image
            self._device.display(img)
            logger.info("Smiley face displayed on LCD")

        except Exception as e:
            logger.error(f"Failed to display smiley face: {e}")

    def _draw_smiley_face(self, draw: ImageDraw.Draw, width: int, height: int):
        """
        Draw a simple smiling face (eyes and mouth only).

        Args:
            draw: ImageDraw object
            width: Display width
            height: Display height
        """
        # Calculate dimensions for a face that fills most of the screen
        margin = 20
        face_width = width - (margin * 2)
        face_height = height - (margin * 2)

        # Face center
        center_x = width // 2
        center_y = height // 2

        # Eye dimensions - simple filled ellipses
        eye_width = face_width // 10
        eye_height = face_height // 6
        eye_y = center_y - (face_height // 5)

        # Left eye (from viewer's perspective, so on the right side of screen)
        left_eye_x = center_x - (face_width // 6)
        draw.ellipse(
            [
                left_eye_x - eye_width // 2,
                eye_y - eye_height // 2,
                left_eye_x + eye_width // 2,
                eye_y + eye_height // 2,
            ],
            fill="white",
        )

        # Right eye (on the left side of screen)
        right_eye_x = center_x + (face_width // 6)
        draw.ellipse(
            [
                right_eye_x - eye_width // 2,
                eye_y - eye_height // 2,
                right_eye_x + eye_width // 2,
                eye_y + eye_height // 2,
            ],
            fill="white",
        )

        # Mouth - simple upward curve (smile)
        mouth_y = center_y + (face_height // 8)
        mouth_width = face_width // 3
        mouth_height = face_height // 8

        # Draw smile as a filled arc/ellipse segment
        # Using a series of ellipses to create a thick line
        mouth_points = []
        for i in range(11):
            t = i / 10.0  # 0 to 1
            # Parabolic curve for smile (upward arc)
            x = (center_x - mouth_width // 2) + (mouth_width * t)
            y = mouth_y + (mouth_height * (t - 0.5) ** 2 * 4 * 0.3)
            mouth_points.append((x, y))

        # Draw thick smile line
        line_width = 8
        for i in range(len(mouth_points) - 1):
            draw.line(
                [mouth_points[i], mouth_points[i + 1]],
                fill="white",
                width=line_width,
            )

        # Add rounded caps at ends of smile
        draw.ellipse(
            [
                mouth_points[0][0] - line_width // 2,
                mouth_points[0][1] - line_width // 2,
                mouth_points[0][0] + line_width // 2,
                mouth_points[0][1] + line_width // 2,
            ],
            fill="white",
        )
        draw.ellipse(
            [
                mouth_points[-1][0] - line_width // 2,
                mouth_points[-1][1] - line_width // 2,
                mouth_points[-1][0] + line_width // 2,
                mouth_points[-1][1] + line_width // 2,
            ],
            fill="white",
        )

    def show_text(
        self, text: str, position: Optional[Tuple[int, int]] = None, font_size: int = 20
    ) -> None:
        """
        Display text on the LCD.

        Args:
            text: Text to display
            position: (x, y) position or None for center
            font_size: Font size in pixels
        """
        if not self._device:
            logger.warning("LCD not initialized")
            return

        try:
            img = Image.new("RGB", (self._width, self._height), "black")
            draw = ImageDraw.Draw(img)

            # Calculate text position
            if position is None:
                # Center text
                bbox = draw.textbbox((0, 0), text)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                x = (self._width - text_width) // 2
                y = (self._height - text_height) // 2
            else:
                x, y = position

            draw.text((x, y), text, fill="white")
            self._device.display(img)
            logger.debug(f"Text displayed: {text}")

        except Exception as e:
            logger.error(f"Failed to display text: {e}")

    def clear_screen(self) -> None:
        """Clear the LCD screen (fill with black)."""
        if not self._device:
            logger.warning("LCD not initialized")
            return

        try:
            img = Image.new("RGB", (self._width, self._height), "black")
            self._device.display(img)
            logger.info("LCD screen cleared")
        except Exception as e:
            logger.error(f"Failed to clear screen: {e}")

    def display_image(self, image_path: str) -> bool:
        """
        Display an image file on the LCD.

        Args:
            image_path: Path to the image file

        Returns:
            True if successful
        """
        if not self._device:
            logger.warning("LCD not initialized")
            return False

        try:
            img = Image.open(image_path)
            # Resize to fit display
            img = img.resize((self._width, self._height), Image.Resampling.LANCZOS)
            self._device.display(img)
            logger.info(f"Image displayed: {image_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to display image: {e}")
            return False

    def is_initialized(self) -> bool:
        """Check if the LCD is initialized."""
        return self._is_initialized

    def get_resolution(self) -> Tuple[int, int]:
        """Get the display resolution."""
        return (self._width, self._height)

    def cleanup(self) -> None:
        """Cleanup LCD resources."""
        if self._backlight:
            try:
                self._backlight.close()
                logger.debug("Backlight cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up backlight: {e}")

        if self._device:
            try:
                self._device.cleanup()
                logger.debug("LCD device cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up LCD device: {e}")

        self._device = None
        self._serial = None
        self._backlight = None
        self._is_initialized = False

        logger.info("LCD service cleaned up")


# Global LCD service instance
lcd_service = LCDService()
