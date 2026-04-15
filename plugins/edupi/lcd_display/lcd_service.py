"""LCD service for LCD Display plugin.

Manages SPI communication with ILI9341 TFT LCD display using Adafruit libraries.
and handles drawing operations including mood-based face animations.
"""

import logging
import threading
import time
from typing import Optional, Tuple
from PIL import Image, ImageDraw, ImageFont

from .mood import Mood, MoodManager

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

        # Animation loop attributes
        self._animation_thread = None
        self._animation_running = False
        self._animation_paused = False
        self._animation_lock = threading.Lock()

        # Mood management
        self._mood_manager = MoodManager()
        self._face_durations = (5.0, 2.0)  # 5s for main face, 2s for variation

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

            # Show splash text (replaces white flash during boot)
            logger.debug("Showing splash screen...")
            self.show_splash("Tinko")

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

        # Mouth - simple upward curve (happy smile!)
        mouth_y = center_y + (face_height // 8)
        mouth_width = face_width // 3
        mouth_height = face_height // 8

        # Draw smile as a filled arc/ellipse segment
        # Using a series of points to create an upward-curving smile
        mouth_points = []
        for i in range(11):
            t = i / 10.0  # 0 to 1
            # Inverted parabolic curve for smile (upward curve - happy!)
            # The smile curves UP at the corners and DOWN in the middle
            x = (center_x - mouth_width // 2) + (mouth_width * t)
            y = mouth_y + (mouth_height * (1 - ((t - 0.5) ** 2) * 4))
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

    def _draw_eyes(
        self, draw: ImageDraw.Draw, width: int, height: int, big_grin: bool = False
    ):
        """
        Draw eyes for the face.

        Args:
            draw: ImageDraw object
            width: Display width
            height: Display height
            big_grin: If True, draw squinted eyes for big grin (:D)
        """
        margin = 20
        face_width = width - (margin * 2)
        face_height = height - (margin * 2)

        center_x = width // 2
        center_y = height // 2

        # Eye dimensions
        eye_width = face_width // 10
        eye_height = face_height // 6
        eye_y = center_y - (face_height // 5)
        eye_y_offset = eye_height // 3  # Define here to avoid unbound error

        # Left eye
        left_eye_x = center_x - (face_width // 6)
        if big_grin:
            # Happy closed eyes - simple horizontal lines
            eye_line_width = 6
            left_start = (left_eye_x - eye_width // 2, eye_y)
            left_end = (left_eye_x + eye_width // 2, eye_y)
            draw.line([left_start, left_end], fill="white", width=eye_line_width)
        else:
            # Normal eyes - filled ellipses
            draw.ellipse(
                [
                    left_eye_x - eye_width // 2,
                    eye_y - eye_height // 2,
                    left_eye_x + eye_width // 2,
                    eye_y + eye_height // 2,
                ],
                fill="white",
            )

        # Right eye
        right_eye_x = center_x + (face_width // 6)
        if big_grin:
            # Happy closed eyes - simple horizontal lines
            eye_line_width = 6
            right_start = (right_eye_x - eye_width // 2, eye_y)
            right_end = (right_eye_x + eye_width // 2, eye_y)
            draw.line([right_start, right_end], fill="white", width=eye_line_width)
        else:
            # Normal eyes
            draw.ellipse(
                [
                    right_eye_x - eye_width // 2,
                    eye_y - eye_height // 2,
                    right_eye_x + eye_width // 2,
                    eye_y + eye_height // 2,
                ],
                fill="white",
            )

    def _draw_mouth(
        self, draw: ImageDraw.Draw, width: int, height: int, big_grin: bool = False
    ):
        """
        Draw mouth for the face.

        Args:
            draw: ImageDraw object
            width: Display width
            height: Display height
            big_grin: If True, draw bigger open mouth
        """
        margin = 20
        face_width = width - (margin * 2)
        face_height = height - (margin * 2)

        center_x = width // 2
        center_y = height // 2

        mouth_y = center_y + (face_height // 8)

        if big_grin:
            # Big happy grin (:D style) - wider, thicker smile
            mouth_width = face_width // 2
            mouth_height = face_height // 5

            # Draw smile as a wider, more pronounced curve
            mouth_points = []
            for i in range(11):
                t = i / 10.0
                x = (center_x - mouth_width // 2) + (mouth_width * t)
                # More pronounced upward curve
                y = mouth_y + (mouth_height * (1 - ((t - 0.5) ** 2) * 4.5))
                mouth_points.append((x, y))

            # Thicker line for big grin
            line_width = 12
            for i in range(len(mouth_points) - 1):
                draw.line(
                    [mouth_points[i], mouth_points[i + 1]],
                    fill="white",
                    width=line_width,
                )

            # Add rounded caps at ends (bigger for big grin)
            cap_radius = line_width // 2
            draw.ellipse(
                [
                    mouth_points[0][0] - cap_radius,
                    mouth_points[0][1] - cap_radius,
                    mouth_points[0][0] + cap_radius,
                    mouth_points[0][1] + cap_radius,
                ],
                fill="white",
            )
            draw.ellipse(
                [
                    mouth_points[-1][0] - cap_radius,
                    mouth_points[-1][1] - cap_radius,
                    mouth_points[-1][0] + cap_radius,
                    mouth_points[-1][1] + cap_radius,
                ],
                fill="white",
            )

            # Draw straight line at bottom to complete the "D" shape
            # Line from left corner to right corner at the bottom
            left_corner = mouth_points[0]
            right_corner = mouth_points[-1]
            bottom_y = max(left_corner[1], right_corner[1]) + line_width // 2
            draw.line(
                [(left_corner[0], bottom_y), (right_corner[0], bottom_y)],
                fill="white",
                width=line_width,
            )
            # Add rounded caps at the bottom corners
            draw.ellipse(
                [
                    left_corner[0] - cap_radius,
                    bottom_y - cap_radius,
                    left_corner[0] + cap_radius,
                    bottom_y + cap_radius,
                ],
                fill="white",
            )
            draw.ellipse(
                [
                    right_corner[0] - cap_radius,
                    bottom_y - cap_radius,
                    right_corner[0] + cap_radius,
                    bottom_y + cap_radius,
                ],
                fill="white",
            )
        else:
            # Normal smile (:) style) - upward curve
            mouth_width = face_width // 3
            mouth_height = face_height // 8

            # Draw smile as a curve
            mouth_points = []
            for i in range(11):
                t = i / 10.0
                x = (center_x - mouth_width // 2) + (mouth_width * t)
                y = mouth_y + (mouth_height * (1 - ((t - 0.5) ** 2) * 4))
                mouth_points.append((x, y))

            # Draw thick smile line
            line_width = 8
            for i in range(len(mouth_points) - 1):
                draw.line(
                    [mouth_points[i], mouth_points[i + 1]],
                    fill="white",
                    width=line_width,
                )

            # Add rounded caps at ends
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

    def show_face(self, big_grin: bool = False) -> None:
        """Display a face (:) or :D) on the LCD."""
        logger.debug(f"show_face called - big_grin={big_grin}, _device={self._device}")
        if not self._device:
            logger.warning("LCD not initialized, cannot show face")
            return

        try:
            # Create image with black background
            img = Image.new("RGB", (self._width, self._height), "black")
            draw = ImageDraw.Draw(img)

            # Draw eyes
            self._draw_eyes(draw, self._width, self._height, big_grin=big_grin)

            # Draw mouth
            self._draw_mouth(draw, self._width, self._height, big_grin=big_grin)

            # Display the image
            self._device.image(img)
            face_type = "big_grin (:D)" if big_grin else "smile (:))"
            logger.info(f"Face displayed: {face_type}")

        except Exception as e:
            logger.exception(f"Failed to display face: {e}")

    def show_face_for_mood(self, mood: Mood, face_variant: int = 0) -> None:
        """Display a face based on mood and variant.

        Args:
            mood: The current mood
            face_variant: 0 for main face, 1 for variation
        """
        logger.debug(
            f"show_face_for_mood called - mood={mood.value}, variant={face_variant}"
        )
        if not self._device:
            logger.warning("LCD not initialized, cannot show face")
            return

        try:
            # Create image with black background
            img = Image.new("RGB", (self._width, self._height), "black")
            draw = ImageDraw.Draw(img)

            # Draw face based on mood
            self._draw_mood_face(draw, self._width, self._height, mood, face_variant)

            # Display the image
            self._device.image(img)
            face_names = mood.get_face_names()
            face_name = face_names[face_variant]
            logger.info(f"Face displayed: {mood.value} - {face_name}")

        except Exception as e:
            logger.exception(f"Failed to display face: {e}")

    def _draw_mood_face(
        self,
        draw: ImageDraw.Draw,
        width: int,
        height: int,
        mood: Mood,
        variant: int = 0,
    ):
        """Draw a face based on mood and variant.

        Args:
            draw: ImageDraw object
            width: Display width
            height: Display height
            mood: The current mood
            variant: 0 for main face, 1 for variation
        """
        # Calculate dimensions
        margin = 20
        face_width = width - (margin * 2)
        face_height = height - (margin * 2)
        center_x = width // 2
        center_y = height // 2

        # Eye dimensions
        eye_width = face_width // 10
        eye_height = face_height // 6
        eye_y = center_y - (face_height // 5)
        left_eye_x = center_x - (face_width // 6)
        right_eye_x = center_x + (face_width // 6)

        if mood == Mood.HAPPY:
            self._draw_happy_face(
                draw,
                width,
                height,
                variant,
                left_eye_x,
                right_eye_x,
                eye_y,
                eye_width,
                eye_height,
                face_width,
                face_height,
                center_x,
                center_y,
            )
        elif mood == Mood.NEUTRAL:
            self._draw_neutral_face(
                draw,
                width,
                height,
                variant,
                left_eye_x,
                right_eye_x,
                eye_y,
                eye_width,
                eye_height,
                face_width,
                face_height,
                center_x,
                center_y,
            )
        elif mood == Mood.SAD:
            self._draw_sad_face(
                draw,
                width,
                height,
                variant,
                left_eye_x,
                right_eye_x,
                eye_y,
                eye_width,
                eye_height,
                face_width,
                face_height,
                center_x,
                center_y,
            )
        elif mood == Mood.ANGRY:
            self._draw_angry_face(
                draw,
                width,
                height,
                variant,
                left_eye_x,
                right_eye_x,
                eye_y,
                eye_width,
                eye_height,
                face_width,
                face_height,
                center_x,
                center_y,
            )
        elif mood == Mood.LAUGHING:
            self._draw_laughing_face(
                draw,
                width,
                height,
                variant,
                left_eye_x,
                right_eye_x,
                eye_y,
                eye_width,
                eye_height,
                face_width,
                face_height,
                center_x,
                center_y,
            )
        elif mood == Mood.CONCENTRATED:
            self._draw_concentrated_face(
                draw,
                width,
                height,
                variant,
                left_eye_x,
                right_eye_x,
                eye_y,
                eye_width,
                eye_height,
                face_width,
                face_height,
                center_x,
                center_y,
            )

    def _draw_happy_face(
        self,
        draw,
        width,
        height,
        variant,
        left_eye_x,
        right_eye_x,
        eye_y,
        eye_width,
        eye_height,
        face_width,
        face_height,
        center_x,
        center_y,
    ):
        """Draw happy mood faces."""
        if variant == 0:
            # Smile (:)) - open round eyes
            for eye_x in [left_eye_x, right_eye_x]:
                draw.ellipse(
                    [
                        eye_x - eye_width // 2,
                        eye_y - eye_height // 2,
                        eye_x + eye_width // 2,
                        eye_y + eye_height // 2,
                    ],
                    fill="white",
                )
            # Happy smile
            self._draw_smile(
                draw, center_x, center_y, face_width, face_height, big=False
            )
        else:
            # Big grin (:D) - closed happy eyes
            line_width = 6
            for eye_x in [left_eye_x, right_eye_x]:
                draw.line(
                    [(eye_x - eye_width // 2, eye_y), (eye_x + eye_width // 2, eye_y)],
                    fill="white",
                    width=line_width,
                )
            # Big smile
            self._draw_smile(
                draw, center_x, center_y, face_width, face_height, big=True
            )

    def _draw_neutral_face(
        self,
        draw,
        width,
        height,
        variant,
        left_eye_x,
        right_eye_x,
        eye_y,
        eye_width,
        eye_height,
        face_width,
        face_height,
        center_x,
        center_y,
    ):
        """Draw neutral/straight face mood."""
        if variant == 0:
            # Straight face (:|) - open neutral eyes
            for eye_x in [left_eye_x, right_eye_x]:
                draw.ellipse(
                    [
                        eye_x - eye_width // 2,
                        eye_y - eye_height // 2,
                        eye_x + eye_width // 2,
                        eye_y + eye_height // 2,
                    ],
                    fill="white",
                )
            # Straight line mouth
            mouth_y = center_y + (face_height // 8)
            mouth_width = face_width // 3
            draw.line(
                [
                    (center_x - mouth_width // 2, mouth_y),
                    (center_x + mouth_width // 2, mouth_y),
                ],
                fill="white",
                width=6,
            )
        else:
            # Blinking - closed eyes
            line_width = 4
            for eye_x in [left_eye_x, right_eye_x]:
                draw.line(
                    [(eye_x - eye_width // 2, eye_y), (eye_x + eye_width // 2, eye_y)],
                    fill="white",
                    width=line_width,
                )
            # Straight mouth
            mouth_y = center_y + (face_height // 8)
            mouth_width = face_width // 3
            draw.line(
                [
                    (center_x - mouth_width // 2, mouth_y),
                    (center_x + mouth_width // 2, mouth_y),
                ],
                fill="white",
                width=6,
            )

    def _draw_sad_face(
        self,
        draw,
        width,
        height,
        variant,
        left_eye_x,
        right_eye_x,
        eye_y,
        eye_width,
        eye_height,
        face_width,
        face_height,
        center_x,
        center_y,
    ):
        """Draw sad mood faces."""
        if variant == 0:
            # Sad face - droopy eyes
            for eye_x in [left_eye_x, right_eye_x]:
                # Draw droopy eye arcs (sad eyes)
                draw.arc(
                    [
                        eye_x - eye_width // 2,
                        eye_y - eye_height // 3,
                        eye_x + eye_width // 2,
                        eye_y + eye_height // 3,
                    ],
                    start=0,
                    end=180,
                    fill="white",
                    width=3,
                )
            # Sad downward curve mouth
            mouth_y = center_y + (face_height // 6)
            mouth_width = face_width // 3
            mouth_points = []
            for i in range(11):
                t = i / 10.0
                x = (center_x - mouth_width // 2) + (mouth_width * t)
                # Downward curve (sad)
                y = mouth_y + (20 * ((t - 0.5) ** 2) * 4)
                mouth_points.append((x, y))
            line_width = 6
            for i in range(len(mouth_points) - 1):
                draw.line(
                    [mouth_points[i], mouth_points[i + 1]],
                    fill="white",
                    width=line_width,
                )
        else:
            # Sadder - tears or more droopy
            for eye_x in [left_eye_x, right_eye_x]:
                draw.arc(
                    [
                        eye_x - eye_width // 2,
                        eye_y - eye_height // 3,
                        eye_x + eye_width // 2,
                        eye_y + eye_height // 3,
                    ],
                    start=0,
                    end=180,
                    fill="white",
                    width=3,
                )
            # More pronounced sad mouth
            mouth_y = center_y + (face_height // 6)
            mouth_width = face_width // 3
            mouth_points = []
            for i in range(11):
                t = i / 10.0
                x = (center_x - mouth_width // 2) + (mouth_width * t)
                # Deeper downward curve
                y = mouth_y + (30 * ((t - 0.5) ** 2) * 4)
                mouth_points.append((x, y))
            line_width = 6
            for i in range(len(mouth_points) - 1):
                draw.line(
                    [mouth_points[i], mouth_points[i + 1]],
                    fill="white",
                    width=line_width,
                )

    def _draw_angry_face(
        self,
        draw,
        width,
        height,
        variant,
        left_eye_x,
        right_eye_x,
        eye_y,
        eye_width,
        eye_height,
        face_width,
        face_height,
        center_x,
        center_y,
    ):
        """Draw angry mood faces."""
        if variant == 0:
            # Angry - slanted eyebrows, tight mouth
            for i, eye_x in enumerate([left_eye_x, right_eye_x]):
                # Angry slanted eyes
                slant = (
                    -8 if i == 0 else 8
                )  # Left eye slants down-right, right down-left
                draw.line(
                    [
                        (eye_x - eye_width // 2, eye_y - 5),
                        (eye_x + eye_width // 2, eye_y + slant),
                    ],
                    fill="white",
                    width=5,
                )
            # Tight angry mouth (small straight line)
            mouth_y = center_y + (face_height // 6)
            mouth_width = face_width // 4
            draw.line(
                [
                    (center_x - mouth_width // 2, mouth_y),
                    (center_x + mouth_width // 2, mouth_y),
                ],
                fill="white",
                width=8,
            )
        else:
            # Furious - more angry expression
            for i, eye_x in enumerate([left_eye_x, right_eye_x]):
                slant = -12 if i == 0 else 12
                draw.line(
                    [
                        (eye_x - eye_width // 2, eye_y - 8),
                        (eye_x + eye_width // 2, eye_y + slant),
                    ],
                    fill="white",
                    width=6,
                )
            # Very tight mouth
            mouth_y = center_y + (face_height // 6)
            mouth_width = face_width // 5
            draw.line(
                [
                    (center_x - mouth_width // 2, mouth_y),
                    (center_x + mouth_width // 2, mouth_y),
                ],
                fill="white",
                width=10,
            )

    def _draw_laughing_face(
        self,
        draw,
        width,
        height,
        variant,
        left_eye_x,
        right_eye_x,
        eye_y,
        eye_width,
        eye_height,
        face_width,
        face_height,
        center_x,
        center_y,
    ):
        """Draw laughing mood faces."""
        if variant == 0:
            # Laugh - happy closed eyes
            line_width = 6
            for eye_x in [left_eye_x, right_eye_x]:
                # Curved happy eyes
                draw.arc(
                    [
                        eye_x - eye_width // 2,
                        eye_y - 5,
                        eye_x + eye_width // 2,
                        eye_y + 5,
                    ],
                    start=0,
                    end=180,
                    fill="white",
                    width=4,
                )
            # Open laughing mouth (big D shape)
            mouth_y = center_y + (face_height // 8)
            mouth_width = face_width // 2
            mouth_height = face_height // 4
            draw.ellipse(
                [
                    center_x - mouth_width // 2,
                    mouth_y - mouth_height // 4,
                    center_x + mouth_width // 2,
                    mouth_y + mouth_height,
                ],
                fill="white",
            )
        else:
            # Big laugh
            line_width = 6
            for eye_x in [left_eye_x, right_eye_x]:
                draw.arc(
                    [
                        eye_x - eye_width // 2,
                        eye_y - 8,
                        eye_x + eye_width // 2,
                        eye_y + 8,
                    ],
                    start=0,
                    end=180,
                    fill="white",
                    width=5,
                )
            # Very open mouth
            mouth_y = center_y + (face_height // 8)
            mouth_width = face_width // 2
            mouth_height = face_height // 3
            draw.ellipse(
                [
                    center_x - mouth_width // 2,
                    mouth_y - mouth_height // 4,
                    center_x + mouth_width // 2,
                    mouth_y + mouth_height,
                ],
                fill="white",
            )

    def _draw_concentrated_face(
        self,
        draw,
        width,
        height,
        variant,
        left_eye_x,
        right_eye_x,
        eye_y,
        eye_width,
        eye_height,
        face_width,
        face_height,
        center_x,
        center_y,
    ):
        """Draw concentrated/learning mood faces."""
        if variant == 0:
            # Focused - narrowed eyes
            for eye_x in [left_eye_x, right_eye_x]:
                # Narrow focused eyes
                draw.ellipse(
                    [
                        eye_x - eye_width // 3,
                        eye_y - eye_height // 4,
                        eye_x + eye_width // 3,
                        eye_y + eye_height // 4,
                    ],
                    fill="white",
                )
            # Small concentrated mouth
            mouth_y = center_y + (face_height // 6)
            mouth_width = face_width // 4
            draw.ellipse(
                [
                    center_x - mouth_width // 2,
                    mouth_y - 5,
                    center_x + mouth_width // 2,
                    mouth_y + 5,
                ],
                fill="white",
            )
        else:
            # Thinking - one eye closed/raised eyebrow
            for eye_x in [left_eye_x, right_eye_x]:
                draw.ellipse(
                    [
                        eye_x - eye_width // 3,
                        eye_y - eye_height // 4,
                        eye_x + eye_width // 3,
                        eye_y + eye_height // 4,
                    ],
                    fill="white",
                )
            # Slight smile (thinking)
            mouth_y = center_y + (face_height // 6)
            mouth_width = face_width // 4
            mouth_points = []
            for i in range(11):
                t = i / 10.0
                x = (center_x - mouth_width // 2) + (mouth_width * t)
                y = mouth_y + (10 * (1 - ((t - 0.5) ** 2) * 4))
                mouth_points.append((x, y))
            line_width = 4
            for i in range(len(mouth_points) - 1):
                draw.line(
                    [mouth_points[i], mouth_points[i + 1]],
                    fill="white",
                    width=line_width,
                )

    def _draw_smile(self, draw, center_x, center_y, face_width, face_height, big=False):
        """Helper method to draw a smile (normal or big)."""
        mouth_y = center_y + (face_height // 8)
        mouth_width = face_width // 2 if big else face_width // 3
        mouth_height = face_height // 5 if big else face_height // 8

        mouth_points = []
        curve_factor = 4.5 if big else 4.0

        for i in range(11):
            t = i / 10.0
            x = (center_x - mouth_width // 2) + (mouth_width * t)
            y = mouth_y + (mouth_height * (1 - ((t - 0.5) ** 2) * curve_factor))
            mouth_points.append((x, y))

        line_width = 12 if big else 8
        for i in range(len(mouth_points) - 1):
            draw.line(
                [mouth_points[i], mouth_points[i + 1]], fill="white", width=line_width
            )

        # Add rounded caps
        cap_radius = line_width // 2
        draw.ellipse(
            [
                mouth_points[0][0] - cap_radius,
                mouth_points[0][1] - cap_radius,
                mouth_points[0][0] + cap_radius,
                mouth_points[0][1] + cap_radius,
            ],
            fill="white",
        )
        draw.ellipse(
            [
                mouth_points[-1][0] - cap_radius,
                mouth_points[-1][1] - cap_radius,
                mouth_points[-1][0] + cap_radius,
                mouth_points[-1][1] + cap_radius,
            ],
            fill="white",
        )

        if big:
            # Add straight bottom line for D shape
            left_corner = mouth_points[0]
            right_corner = mouth_points[-1]
            bottom_y = max(left_corner[1], right_corner[1]) + line_width // 2
            draw.line(
                [(left_corner[0], bottom_y), (right_corner[0], bottom_y)],
                fill="white",
                width=line_width,
            )
            draw.ellipse(
                [
                    left_corner[0] - cap_radius,
                    bottom_y - cap_radius,
                    left_corner[0] + cap_radius,
                    bottom_y + cap_radius,
                ],
                fill="white",
            )
            draw.ellipse(
                [
                    right_corner[0] - cap_radius,
                    bottom_y - cap_radius,
                    right_corner[0] + cap_radius,
                    bottom_y + cap_radius,
                ],
                fill="white",
            )

    def _animation_loop(self):
        """Animation loop that alternates between mood faces (5s main / 2s variation)."""
        logger.info(
            f"Mood animation loop started - current mood: {self._mood_manager.current_mood.value}"
        )

        while self._animation_running:
            with self._animation_lock:
                if self._animation_paused:
                    time.sleep(0.1)
                    continue

                if not self._is_initialized:
                    logger.warning("LCD not initialized, stopping animation")
                    break

                current_mood = self._mood_manager.current_mood

                # Show main face (5 seconds)
                self._mood_manager._current_face_index = 0
                self.show_face_for_mood(current_mood, face_variant=0)

            # Wait 5 seconds
            for _ in range(50):  # 5 seconds in 0.1s increments
                if not self._animation_running:
                    break
                time.sleep(0.1)

            with self._animation_lock:
                if self._animation_paused or not self._animation_running:
                    continue

                # Show variation face (2 seconds)
                self._mood_manager._current_face_index = 1
                self.show_face_for_mood(current_mood, face_variant=1)

            # Wait 2 seconds
            for _ in range(20):  # 2 seconds in 0.1s increments
                if not self._animation_running:
                    break
                time.sleep(0.1)

        logger.info("Face animation loop stopped")

    def start_face_animation(self) -> None:
        """Start the face animation loop."""
        if self._animation_running:
            logger.warning("Animation already running")
            return

        if not self._is_initialized:
            logger.warning("LCD not initialized, cannot start animation")
            return

        self._animation_running = True
        self._animation_thread = threading.Thread(
            target=self._animation_loop, daemon=True
        )
        self._animation_thread.start()
        logger.info("Face animation started (5s :) / 2s :D)")

    def stop_face_animation(self) -> None:
        """Stop the face animation loop."""
        if not self._animation_running:
            return

        self._animation_running = False
        if self._animation_thread:
            self._animation_thread.join(timeout=2.0)
        logger.info("Face animation stopped")

    def pause_face_animation(self) -> None:
        """Pause the face animation (for when displaying other content)."""
        with self._animation_lock:
            self._animation_paused = True
        logger.info("Face animation paused")

    def resume_face_animation(self) -> None:
        """Resume the face animation."""
        with self._animation_lock:
            self._animation_paused = False
        logger.info("Face animation resumed")

    def is_animation_running(self) -> bool:
        """Check if animation is running."""
        return self._animation_running

    def set_mood(self, mood: Mood) -> bool:
        """Set the current mood for the robot face.

        Args:
            mood: The new mood to set

        Returns:
            True if mood was set successfully
        """
        if not self._is_initialized:
            logger.warning("LCD not initialized, cannot set mood")
            return False

        old_mood = self._mood_manager.current_mood
        self._mood_manager.current_mood = mood

        # Immediately display the new mood face
        self.show_face_for_mood(mood, face_variant=0)

        logger.info(f"Mood changed from {old_mood.value} to {mood.value}")
        return True

    def set_mood_by_name(self, mood_name: str) -> bool:
        """Set mood by name string.

        Args:
            mood_name: Name of the mood (happy, neutral, sad, angry, laughing, concentrated)

        Returns:
            True if mood was set successfully
        """
        try:
            mood = Mood(mood_name)
            return self.set_mood(mood)
        except ValueError:
            logger.error(f"Invalid mood name: {mood_name}")
            return False

    def get_current_mood(self) -> Mood:
        """Get the current mood."""
        return self._mood_manager.current_mood

    def get_mood_description(self) -> str:
        """Get human-readable description of current mood."""
        return self._mood_manager.current_mood.get_description()

    def is_misbehaving(self) -> bool:
        """Check if current mood indicates classroom misbehavior."""
        return self._mood_manager.is_misbehaving_mood()

    def get_available_moods(self) -> list:
        """Get list of all available mood names."""
        return Mood.get_all_moods()

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
            # Pause animation while displaying text
            was_running = self._animation_running and not self._animation_paused
            if was_running:
                self.pause_face_animation()

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

            # Keep animation paused - user must click "Show Smiley" to resume
            # Don't automatically resume

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

    def show_splash(self, text: str = "Tinko") -> None:
        """Display large centered text as splash screen on boot."""
        if not self._device:
            logger.warning("LCD not initialized, cannot show splash")
            return

        try:
            img = Image.new("RGB", (self._width, self._height), "black")
            draw = ImageDraw.Draw(img)

            # Try system fonts, falling back to default
            font = None
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            ]
            for fp in font_paths:
                try:
                    font = ImageFont.truetype(fp, 72)
                    break
                except (OSError, IOError):
                    continue

            if font is None:
                try:
                    font = ImageFont.load_default(size=72)
                except TypeError:
                    font = ImageFont.load_default()

            # Center text
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x = (self._width - text_width) // 2
            y = (self._height - text_height) // 2

            draw.text((x, y), text, fill="white", font=font)
            self._device.image(img)
            logger.info(f"Splash screen displayed: '{text}'")

        except Exception as e:
            logger.error(f"Failed to display splash: {e}")

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
