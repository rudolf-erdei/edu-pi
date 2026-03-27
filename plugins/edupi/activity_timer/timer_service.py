"""Timer service for Activity Timer plugin.

Manages timer logic and GPIO LED control.
"""

import logging
import threading
import time
from typing import Optional, Callable

try:
    from gpiozero import PWMLED, Buzzer

    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

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

    class Buzzer:
        def __init__(self, pin):
            self.pin = pin

        def on(self):
            logging.getLogger(__name__).info(f"Mock Buzzer {self.pin}: BEEP")

        def off(self):
            logging.getLogger(__name__).info(f"Mock Buzzer {self.pin}: OFF")

        def beep(self, on_time=0.1, off_time=0.1, n=1):
            logging.getLogger(__name__).info(f"Mock Buzzer {self.pin}: BEEP x{n}")


from django.utils import timezone

from .models import TimerSession

logger = logging.getLogger(__name__)


class TimerService:
    """
    Service for managing timer sessions and controlling LED visual feedback.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern for timer service."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the timer service."""
        if self._initialized:
            return

        self._initialized = True
        self._red_led: Optional[PWMLED] = None
        self._green_led: Optional[PWMLED] = None
        self._blue_led: Optional[PWMLED] = None
        self._buzzer: Optional[Buzzer] = None
        self._brightness: float = 1.0
        self._active_session: Optional[TimerSession] = None
        self._update_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._callback: Optional[Callable] = None

    def initialize_gpio(
        self,
        red_pin: int,
        green_pin: int,
        blue_pin: int,
        buzzer_pin: int,
        brightness: int = 100,
    ) -> None:
        """
        Initialize GPIO pins for RGB LED and buzzer.

        Args:
            red_pin: BCM pin number for red LED
            green_pin: BCM pin number for green LED
            blue_pin: BCM pin number for blue LED
            buzzer_pin: BCM pin number for buzzer
            brightness: LED brightness percentage (10-100)
        """
        try:
            self._brightness = brightness / 100.0

            self._red_led = PWMLED(red_pin)
            self._green_led = PWMLED(green_pin)
            self._blue_led = PWMLED(blue_pin)
            self._buzzer = Buzzer(buzzer_pin)

            logger.info(
                f"GPIO initialized - RGB pins: {red_pin}, {green_pin}, {blue_pin}, Buzzer: {buzzer_pin}"
            )
            self._set_led_color(0, 0, 0)  # Start with LED off

        except Exception as e:
            logger.error(f"Failed to initialize GPIO: {e}")

    def cleanup_gpio(self) -> None:
        """Cleanup GPIO resources."""
        self._stop_event.set()

        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=2)

        self._set_led_color(0, 0, 0)

        if self._red_led:
            self._red_led.off()
        if self._green_led:
            self._green_led.off()
        if self._blue_led:
            self._blue_led.off()
        if self._buzzer:
            self._buzzer.off()

        logger.info("GPIO cleanup completed")

    def start_timer(self, session: TimerSession, callback: Callable = None) -> None:
        """
        Start a timer session.

        Args:
            session: TimerSession model instance
            callback: Optional callback function to call on updates
        """
        if self._active_session and self._active_session.is_running():
            logger.warning("Timer already running, stopping previous session")
            self.stop_timer()

        self._active_session = session
        self._callback = callback
        self._stop_event.clear()

        session.start()

        # Start the update thread
        self._update_thread = threading.Thread(target=self._timer_loop, daemon=True)
        self._update_thread.start()

        logger.info(f"Timer started - Duration: {session.duration_seconds}s")
        self._update_led_display()

    def pause_timer(self) -> None:
        """Pause the current timer."""
        if self._active_session and self._active_session.is_running():
            self._active_session.pause()
            self._update_led_display()
            logger.info("Timer paused")

    def resume_timer(self) -> None:
        """Resume the paused timer."""
        if self._active_session and self._active_session.is_paused():
            self._active_session.resume()
            logger.info("Timer resumed")

    def stop_timer(self) -> None:
        """Stop the current timer."""
        self._stop_event.set()

        if self._active_session:
            self._active_session.cancel()
            self._active_session = None

        self._set_led_color(0, 0, 0)
        logger.info("Timer stopped")

    def _timer_loop(self) -> None:
        """Main timer loop that runs in a separate thread."""
        last_update = time.time()

        while not self._stop_event.is_set():
            if not self._active_session:
                break

            if self._active_session.is_paused():
                time.sleep(0.1)
                continue

            if not self._active_session.is_running():
                break

            current_time = time.time()
            elapsed = current_time - last_update

            if elapsed >= 1.0:  # Update every second
                self._active_session.remaining_seconds = max(
                    0, self._active_session.remaining_seconds - int(elapsed)
                )
                self._active_session.save()

                last_update = current_time

                self._update_led_display()

                if self._callback:
                    try:
                        self._callback(self._active_session)
                    except Exception as e:
                        logger.error(f"Error in timer callback: {e}")

                # Check if timer completed
                if self._active_session.remaining_seconds <= 0:
                    self._complete_timer()
                    break

            time.sleep(0.1)

    def _update_led_display(self) -> None:
        """Update LED color based on timer progress."""
        if not self._active_session or not self._red_led:
            return

        color_hex = self._active_session.get_current_color()
        r, g, b = self._hex_to_rgb(color_hex)
        self._set_led_color(r, g, b)

    def _set_led_color(self, r: float, g: float, b: float) -> None:
        """
        Set RGB LED color with brightness adjustment.

        Args:
            r: Red intensity (0-1)
            g: Green intensity (0-1)
            b: Blue intensity (0-1)
        """
        if self._red_led:
            self._red_led.value = r * self._brightness
        if self._green_led:
            self._green_led.value = g * self._brightness
        if self._blue_led:
            self._blue_led.value = b * self._brightness

    def _complete_timer(self) -> None:
        """Handle timer completion."""
        if self._active_session:
            self._active_session.complete()

            # Flash LED red
            self._flash_led("#FF0000", 5)

            # Play buzzer if enabled
            if (
                self._active_session.config
                and self._active_session.config.enable_buzzer
            ):
                self._play_buzzer()

            logger.info("Timer completed")

            if self._callback:
                try:
                    self._callback(self._active_session)
                except Exception as e:
                    logger.error(f"Error in completion callback: {e}")

            self._active_session = None

    def _flash_led(self, color_hex: str, count: int) -> None:
        """
        Flash LED a specific color.

        Args:
            color_hex: Hex color code
            count: Number of flashes
        """
        r, g, b = self._hex_to_rgb(color_hex)

        for _ in range(count):
            self._set_led_color(r, g, b)
            time.sleep(0.3)
            self._set_led_color(0, 0, 0)
            time.sleep(0.3)

    def _play_buzzer(self) -> None:
        """Play buzzer sound when timer ends."""
        if self._buzzer:
            try:
                self._buzzer.beep(on_time=0.2, off_time=0.2, n=3)
            except Exception as e:
                logger.error(f"Error playing buzzer: {e}")

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple:
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

    def get_active_session(self) -> Optional[TimerSession]:
        """Get the currently active timer session."""
        return self._active_session

    def is_timer_running(self) -> bool:
        """Check if a timer is currently running."""
        return self._active_session is not None and self._active_session.is_running()


# Global timer service instance
timer_service = TimerService()
