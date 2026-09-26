"""Starting the noise monitor from the saved configuration.

Two callers need exactly this: the plugin loading at boot, where the monitor
should come up on its own, and the control view, where a teacher asks for it.
The pin numbers and the fallback thresholds live here so the two cannot drift
apart.
"""

import logging

logger = logging.getLogger(__name__)


# BCM pin numbers for the two RGB LEDs.
#   instant: red 5 (pin 29), green 6 (pin 31), blue 13 (pin 33)
#   session: red 19 (pin 35), green 26 (pin 37), blue 16 (pin 36)
LED_PINS = {
    "instant_red": 5,
    "instant_green": 6,
    "instant_blue": 13,
    "session_red": 19,
    "session_green": 26,
    "session_blue": 16,
}

# Used when the configuration has no profile, which is the state left behind
# when the profile that was in use got deleted.
FALLBACK_YELLOW_THRESHOLD = 40
FALLBACK_RED_THRESHOLD = 70


def configure_service(config) -> None:
    """Point the service at the profile, windows, brightness and microphone.

    Does nothing when there is no configuration yet, so the service keeps its
    own defaults rather than being configured from nothing.

    Args:
        config: A NoiseMonitorConfig instance, or None.
    """
    if not config:
        return

    from .noise_service import noise_service

    profile = config.profile

    noise_service.configure(
        yellow_threshold=(
            profile.yellow_threshold if profile else FALLBACK_YELLOW_THRESHOLD
        ),
        red_threshold=profile.red_threshold if profile else FALLBACK_RED_THRESHOLD,
        instant_window_seconds=config.instant_window_seconds,
        session_window_minutes=config.session_window_minutes,
        brightness=config.led_brightness,
    )

    # Applied here as well as at plugin boot: the stream is opened lazily on
    # the first read, so this is what makes a saved choice take effect on a
    # service that has been restarted since it was saved.
    noise_service.set_device(
        config.audio_input_device_index, config.audio_input_device
    )


def start_monitoring(config) -> None:
    """Initialise the LED hardware, apply ``config``, and start monitoring.

    Args:
        config: A NoiseMonitorConfig instance, or None to use the defaults.
    """
    from .noise_service import noise_service

    noise_service.initialize_gpio(
        instant_red_pin=LED_PINS["instant_red"],
        instant_green_pin=LED_PINS["instant_green"],
        instant_blue_pin=LED_PINS["instant_blue"],
        session_red_pin=LED_PINS["session_red"],
        session_green_pin=LED_PINS["session_green"],
        session_blue_pin=LED_PINS["session_blue"],
    )

    configure_service(config)

    # History is written by the service itself, on its own slower interval.
    noise_service.start_monitoring(persist=True)
