"""USB Presenter Handler - Handles wireless presenter input events."""

import logging
import threading
import time
from typing import Callable, Dict, Optional, Any

try:
    import evdev
    from evdev import InputDevice, list_devices, ecodes

    EVDEV_AVAILABLE = True
    InputDeviceType = InputDevice
except ImportError:
    EVDEV_AVAILABLE = False
    InputDeviceType = Any
    logging.warning("evdev not available - USB presenter support disabled")

from django.dispatch import Signal

logger = logging.getLogger(__name__)

# Django signals for presenter events
presenter_next_pressed = Signal()
presenter_prev_pressed = Signal()
presenter_play_pause_pressed = Signal()
presenter_stop_pressed = Signal()
presenter_connected = Signal()
presenter_disconnected = Signal()


class PresenterHandler:
    """Handles USB wireless presenter input events.

    Automatically detects standard HID presenters and maps buttons to actions.
    """

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
        self._device: Optional[InputDeviceType] = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._is_running = False
        self._button_mappings: Dict[int, str] = {}  # code -> action
        self._on_button_callback: Optional[Callable[[str], None]] = None

        # Setup default button mappings
        self._setup_default_mappings()

        logger.info("Presenter handler initialized")

    def _setup_default_mappings(self):
        """Setup default button code mappings."""
        if not EVDEV_AVAILABLE:
            return

        # Common event codes for presenter buttons (Linux input event codes)
        DEFAULT_BUTTON_CODES = {
            "next": [115, 109, 106],  # KEY_VOLUMEUP, KEY_PAGEDOWN, KEY_RIGHT
            "prev": [114, 104, 105],  # KEY_VOLUMEDOWN, KEY_PAGEUP, KEY_LEFT
            "play_pause": [164, 28],  # KEY_PLAYPAUSE, KEY_ENTER
            "stop": [116, 1, 128],  # KEY_POWER, KEY_ESC, KEY_STOP
        }

        for action, codes in DEFAULT_BUTTON_CODES.items():
            for code in codes:
                self._button_mappings[code] = action

    def set_button_mappings(self, mappings: Dict[int, str]):
        """Set custom button mappings.

        Args:
            mappings: Dict of {event_code: action_name}
        """
        self._button_mappings = mappings
        logger.info(f"Updated button mappings: {mappings}")

    def is_available(self) -> bool:
        """Check if evdev is available."""
        return EVDEV_AVAILABLE

    def find_presenter(self) -> Optional[InputDeviceType]:
        """Find USB presenter device.

        Returns:
            InputDevice if found, None otherwise
        """
        if not EVDEV_AVAILABLE:
            return None

        try:
            devices = [InputDevice(path) for path in list_devices()]

            for device in devices:
                # Look for common presenter vendor/product IDs or names
                name = device.name.lower() if device.name else ""

                # Common presenter keywords
                presenter_keywords = [
                    "presenter",
                    "clicker",
                    "remote",
                    "logitech",
                    "kensington",
                    "wireless",
                    "usb receiver",
                    "hid",
                ]

                if any(keyword in name for keyword in presenter_keywords):
                    logger.info(
                        f"Found presenter device: {device.name} at {device.path}"
                    )
                    return device

                # Check for specific capabilities (should have KEY events)
                # evdev.EV_KEY = 1 (constant)
                capabilities = device.capabilities()
                if 1 in capabilities:  # EV_KEY
                    # Has key events, might be a presenter
                    keys = capabilities[1]  # EV_KEY
                    # Presenters typically have volume/page keys (115, 114, 109, 104)
                    presenter_keys = [115, 114, 109, 104]
                    if any(key in keys for key in presenter_keys):
                        logger.info(f"Found potential presenter: {device.name}")
                        return device

        except Exception as e:
            logger.error(f"Error finding presenter: {e}")

        return None

    def start_monitoring(self, callback: Optional[Callable[[str], None]] = None):
        """Start monitoring for presenter device.

        Args:
            callback: Function to call when button pressed (receives action name)
        """
        if not EVDEV_AVAILABLE:
            logger.warning("Cannot start presenter monitoring - evdev not available")
            return

        if self._is_running:
            logger.debug("Presenter monitoring already running")
            return

        self._on_button_callback = callback
        self._is_running = True

        # Find device
        self._device = self.find_presenter()

        if self._device:
            presenter_connected.send(sender=self.__class__, device=self._device.name)
            self._start_input_thread()
        else:
            logger.info("No presenter found, will retry...")
            self._start_discovery_thread()

    def _start_input_thread(self):
        """Start thread to read input events."""
        if not self._device:
            return

        self._monitor_thread = threading.Thread(target=self._input_loop, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Started presenter input monitoring on {self._device.name}")

    def _start_discovery_thread(self):
        """Start thread to periodically check for presenter."""
        self._monitor_thread = threading.Thread(
            target=self._discovery_loop, daemon=True
        )
        self._monitor_thread.start()
        logger.info("Started presenter discovery")

    def _input_loop(self):
        """Main loop to read presenter input events."""
        if not self._device:
            return

        try:
            # Grab the device (exclusive access)
            self._device.grab()

            for event in self._device.read_loop():
                if not self._is_running:
                    break

                # EV_KEY = 1, key pressed = 1
                if event.type == 1 and event.value == 1:  # Key pressed
                    self._handle_key_press(event.code)

        except Exception as e:
            logger.error(f"Presenter input error: {e}")
            presenter_disconnected.send(sender=self.__class__)
            # Try to reconnect
            self._start_discovery_thread()

        finally:
            try:
                self._device.ungrab()
            except:
                pass

    def _discovery_loop(self):
        """Loop to discover presenter device."""
        retry_count = 0
        max_retries = 100  # Retry for ~5 minutes

        while self._is_running and retry_count < max_retries:
            device = self.find_presenter()
            if device:
                self._device = device
                presenter_connected.send(sender=self.__class__, device=device.name)
                self._start_input_thread()
                return

            time.sleep(3)  # Check every 3 seconds
            retry_count += 1

        logger.warning("Presenter discovery timed out")

    def _handle_key_press(self, code: int):
        """Handle a key press event.

        Args:
            code: evdev key code
        """
        action = self._button_mappings.get(code)

        if action:
            logger.debug(f"Presenter button pressed: {action} (code {code})")

            # Emit Django signal
            if action == "next":
                presenter_next_pressed.send(sender=self.__class__)
            elif action == "prev":
                presenter_prev_pressed.send(sender=self.__class__)
            elif action == "play_pause":
                presenter_play_pause_pressed.send(sender=self.__class__)
            elif action == "stop":
                presenter_stop_pressed.send(sender=self.__class__)

            # Call custom callback if provided
            if self._on_button_callback:
                try:
                    self._on_button_callback(action)
                except Exception as e:
                    logger.error(f"Error in presenter callback: {e}")
        else:
            logger.debug(f"Unmapped presenter button: code {code}")

    def stop_monitoring(self):
        """Stop monitoring presenter input."""
        self._is_running = False

        if self._device:
            try:
                self._device.ungrab()
            except:
                pass

        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.0)

        self._device = None
        logger.info("Presenter monitoring stopped")

    def is_monitoring(self) -> bool:
        """Check if monitoring is active."""
        return self._is_running

    def is_connected(self) -> bool:
        """Check if presenter device is connected."""
        return self._device is not None

    def get_device_name(self) -> Optional[str]:
        """Get name of connected presenter device."""
        return self._device.name if self._device else None

    def get_detected_devices(self) -> list:
        """Get list of all detected input devices.

        Returns:
            List of device info dicts
        """
        if not EVDEV_AVAILABLE:
            return []

        devices = []
        try:
            for path in list_devices():
                device = InputDevice(path)
                devices.append(
                    {
                        "path": device.path,
                        "name": device.name,
                        "phys": device.phys,
                    }
                )
        except Exception as e:
            logger.error(f"Error listing devices: {e}")

        return devices


# Singleton instance
presenter_handler = PresenterHandler()


def connect_presenter_signals():
    """Connect presenter signals to routine player.

    This should be called when the plugin boots.
    """
    from .routine_player import routine_player

    def on_next(sender, **kwargs):
        if routine_player.is_playing():
            routine_player.next_line()

    def on_prev(sender, **kwargs):
        if routine_player.is_playing() or routine_player.is_paused():
            routine_player.prev_line()

    def on_play_pause(sender, **kwargs):
        if routine_player.is_playing():
            routine_player.pause()
        elif routine_player.is_paused():
            routine_player.resume()

    def on_stop(sender, **kwargs):
        if routine_player.get_session():
            routine_player.stop()

    presenter_next_pressed.connect(on_next)
    presenter_prev_pressed.connect(on_prev)
    presenter_play_pause_pressed.connect(on_play_pause)
    presenter_stop_pressed.connect(on_stop)

    logger.info("Presenter signals connected to routine player")
