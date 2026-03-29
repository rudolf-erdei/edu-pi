"""LCD service for LCD Display plugin.

Manages SPI communication with ILI9341 TFT LCD display using Adafruit libraries.
and handles drawing operations including the startup smiley face.
"""

import logging
import threading
import time
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Try to import Adafruit libraries for LCD control
try:
    import digitalio
    import board
    import adafruit_rgb_display.ili9341 as ili9341
    from gpiozero import PWMLED

    LCD_AVAILABLE = True
    logger.info("Adafruit LCD libraries loaded successfully")
except ImportError as e:
    logger.warning(f"LCD libraries not available: {e}")
    LCD_AVAILABLE = False

    # Mock classes for development
    class MockDigitalInOut:
        """Mock digital input/output for development."""

        def __init__(self, pin):
            self.pin = pin
            self.value = False
            logger.info(f"Mock DigitalInOut initialized on pin {pin}")

    class MockSPI:
        """Mock SPI bus for development."""

        def __init__(self):
            logger.info("Mock SPI bus initialized")

    class MockBoard:
        """Mock board pins."""

        D22 = 22
        D23 = 23
        D24 = 24
        SPI = MockSPI()

    class MockILI9341:
        """Mock ILI9341 device for development."""

        def __init__(self, spi, rotation, cs, dc, rst, baudrate):
            self.spi = spi
            self.rotation = rotation
            self.cs = cs
            self.dc = dc
            self.rst = rst
            self.baudrate = baudrate
            self.width = 240
            self.height = 320
            logger.info(
                f"Mock ILI9341 display initialized ({self.width}x{self.height})"
            )

        def image(self, img):
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

    digitalio = None
    board = MockBoard()
    ili9341 = MockILI9341
    PWMLED = MockPWMLED


class LCDService:
    """
    Service for managing SPI TFT LCD display.

    Handles initialization, drawing operations, and cleanup for
    ILI9341-based displays. Shows a smiling face on startup.
    """

    _instance = None
    _lock = threading.Lock()

    # Display dimensions (240x320 portrait by default for ILI9341)
    DEFAULT_WIDTH = 240
    DEFAULT_HEIGHT = 320

    # Pin assignments (using your working configuration)
    DEFAULT_PINS = {
        "cs": 22,  # GPIO 22 - Pin 15 (was Pin 24/GPIO 8)
        "dc": 24,  # GPIO 24 - Pin 18
        "rst": 23,  # GPIO 23 - Pin 16
        "bl": 18,  # GPIO 18 - Pin 12 - Backlight (PWM capable)
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
        self._cs_pin = None
        self._dc_pin = None
        self._rst_pin = None
        self._spi = None
        self._backlight = None
        self._width = self.DEFAULT_WIDTH
        self._height = self.DEFAULT_HEIGHT
        self._rotation = 90  # Default to landscape mode
        self._is_initialized = False
        self._pins = self.DEFAULT_PINS.copy()

        logger.info("LCDService initialized")

    def initialize(
        self,
        rotation: int = 90,
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
        logger.debug(
            f"LCD initialize called - rotation={rotation}, backlight={backlight}"
        )
        logger.debug(
            f"LCD_AVAILABLE={LCD_AVAILABLE}, _is_initialized={self._is_initialized}"
        )

        if self._is_initialized:
            logger.warning("LCD already initialized")
            return True

        if not LCD_AVAILABLE:
            logger.warning("LCD libraries not available, using mock mode")
            try:
                self._setup_mock_device(rotation, backlight)
                return True
            except Exception as e:
                logger.exception("Failed to setup mock device")
                return False

        # Update pin assignments if provided
        if pins:
            self._pins.update(pins)

        try:
            logger.info(f"Initializing LCD with pins: {self._pins}")

            # Setup GPIO pins using digitalio
            logger.debug("Setting up GPIO pins...")
            self._cs_pin = digitalio.DigitalInOut(
                getattr(board, f"D{self._pins['cs']}")
            )
            self._dc_pin = digitalio.DigitalInOut(
                getattr(board, f"D{self._pins['dc']}")
            )
            self._rst_pin = digitalio.DigitalInOut(
                getattr(board, f"D{self._pins['rst']}")
            )
            logger.debug("GPIO pins setup complete")

            # Initialize SPI bus
            logger.debug("Initializing SPI bus...")
            self._spi = board.SPI()
            logger.debug("SPI bus initialized")

            # Initialize ILI9341 device
            logger.debug("Creating ILI9341 device...")
            self._device = ili9341.ILI9341(
                self._spi,
                rotation=rotation,
                cs=self._cs_pin,
                dc=self._dc_pin,
                rst=self._rst_pin,
                baudrate=16000000,  # 16MHz baudrate
            )
            logger.debug("ILI9341 device created successfully")

            # Update dimensions based on rotation
            if rotation in [0, 180]:
                self._width = 240
                self._height = 320
            else:
                self._width = 320
                self._height = 240

            # Initialize backlight with PWM
            logger.debug(f"Initializing backlight on GPIO {self._pins['bl']}...")
            self._backlight = PWMLED(self._pins["bl"])
            self.set_backlight(backlight)
            logger.debug("Backlight initialized successfully")

            self._rotation = rotation
            self._is_initialized = True

            logger.info(f"LCD initialized: {self._width}x{self._height} @ {rotation}°")

            # Clear screen first to ensure display is ready
            logger.debug("Clearing screen...")
            self.clear_screen()
            time.sleep(0.2)

            # Show startup smiley face
            logger.debug("About to show smiley face...")
            self.show_smiley_face()

            return True

        except Exception as e:
            logger.exception(f"Failed to initialize LCD: {e}")
            return False

    def _setup_mock_device(self, rotation: int, backlight: int):
        """Setup mock device for development."""
        self._cs_pin = digitalio.DigitalInOut(board.D22)
        self._dc_pin = digitalio.DigitalInOut(board.D24)
        self._rst_pin = digitalio.DigitalInOut(board.D23)
        self._spi = board.SPI()
        self._device = ili9341.ILI9341(
            self._spi,
            rotation=rotation,
            cs=self._cs_pin,
            dc=self._dc_pin,
            rst=self._rst_pin,
            baudrate=16000000,
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
        logger.debug(
            f"set_backlight called with brightness={brightness}, _backlight={self._backlight}"
        )
        if self._backlight:
            value = max(0, min(100, brightness)) / 100.0
            self._backlight.value = value
            logger.debug(f"Backlight set to {brightness}%")
        else:
            logger.warning("Cannot set backlight - _backlight is None")

    def show_smiley_face(self) -> None:
        """Display a simple smiling face on the LCD."""
        logger.debug(
            f"show_smiley_face called - _device={self._device}, _is_initialized={self._is_initialized}"
        )
        if not self._device:
            logger.warning("LCD not initialized, cannot show smiley face")
            return

        try:
            logger.debug("Creating image for smiley face...")
            # Create image with black background
            img = Image.new("RGB", (self._width, self._height), "black")
            draw = ImageDraw.Draw(img)
            logger.debug(f"Image created: {self._width}x{self._height}")

            # Draw the smiley face
            logger.debug("Drawing smiley face...")
            self._draw_smiley_face(draw, self._width, self._height)
            logger.debug("Smiley face drawn")

            # Display the image
            logger.debug("Displaying image on LCD...")
            self._device.image(img)
            logger.info("Smiley face displayed on LCD")

        except Exception as e:
            logger.exception(f"Failed to display smiley face: {e}")

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
            self._device.image(img)
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
            self._device.image(img)
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
            self._device.image(img)
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
                # Cleanup digitalio pins
                if self._cs_pin:
                    self._cs_pin.deinit()
                if self._dc_pin:
                    self._dc_pin.deinit()
                if self._rst_pin:
                    self._rst_pin.deinit()
                logger.debug("LCD device cleaned up")
            except Exception as e:
                logger.error(f"Error cleaning up LCD device: {e}")

        self._device = None
        self._cs_pin = None
        self._dc_pin = None
        self._rst_pin = None
        self._spi = None
        self._backlight = None
        self._is_initialized = False

        logger.info("LCD service cleaned up")


# Global LCD service instance
lcd_service = LCDService()
