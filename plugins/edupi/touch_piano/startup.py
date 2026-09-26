"""Making the room ready for a piano session.

Starting the piano is not just starting the piano. The Pi has one speaker, one
set of LEDs and one robot face, and a class that presses Start on the piano
expects the notes it touches — not the noise meter's LEDs, not a countdown
buzzer, not a routine talking over the music. So a session begins by quieting
whatever else is running.

What is left alone is the display: it is shared output rather than a competing
activity, and the piano wants it — a happy face is what the class looks at
while they play. That is why the face is set *after* the others are stopped:
stopping the noise monitor hands the face back to the display's own default.

The plugin keeps no state here. Everything below reads the live services, so a
session started twice, or started with nothing else running, lands in the same
place.
"""

import logging

logger = logging.getLogger(__name__)

# Plugins that must survive a piano session starting.
#   lcd_display: shared output, not an activity. It is listed explicitly rather
#       than left implicit so that a future activity on the display (an
#       animation, say) cannot be stopped by accident.
#   touch_piano: the caller. It is exempt because it is the one claiming the
#       room, not a competitor for it.
EXEMPT_PLUGINS = (
    "plugins.edupi.lcd_display",
    "plugins.edupi.touch_piano",
)

# The face the class sees while playing. Happy is also the display's own
# default, so this is a deliberate return to it rather than a new state.
PLAYING_FACE_MOOD = "happy"


def stop_other_activities() -> list:
    """Stop what the other plugins are running (timer, routine, noise meter).

    Returns:
        The display names of the plugins that were asked to stop. Empty when
        nothing else was running, which is the normal case on a fresh boot.
    """
    from core.plugin_system.base import plugin_manager

    return plugin_manager.stop_other_activities(
        except_plugins=EXEMPT_PLUGINS,
        reason="Touch Piano",
    )


def show_playing_face() -> bool:
    """Put the happy face on the display.

    Imported inside the call rather than at module scope: the display plugin is
    a declared dependency, but a missing or disabled display must not stop the
    piano from playing — the class hears the notes either way.

    Returns:
        True if the face was set, False when there is no usable display.
    """
    try:
        from plugins.edupi.lcd_display.lcd_service import lcd_service
    except ImportError:
        return False

    if not lcd_service.is_initialized():
        return False

    return lcd_service.set_mood_by_name(PLAYING_FACE_MOOD)


def prepare_for_piano() -> None:
    """Claim the room for a piano session.

    Order is the point: the noise monitor resets the face to the display's
    default when it stops, so the happy face has to go on last or it would be
    overwritten by the plugin being stopped. Nothing here raises — a session
    that has already started its hardware must not be reported as failed
    because another plugin would not go quietly.
    """
    try:
        stop_other_activities()
    except Exception as e:
        logger.error(f"Could not stop other activities for the piano: {e}")

    try:
        if not show_playing_face():
            logger.info("No display available, piano face not set")
    except Exception as e:
        logger.error(f"Could not set the piano face: {e}")
