"""One activity at a time.

A classroom Pi has one speaker, one set of LEDs and one robot face. Starting
the touch piano is therefore not only starting the piano: whatever else is
running — the noise meter first of all, since it auto-starts at boot — has to
go quiet, and the face has to end up happy for the class to look at.

The mechanism is a per-plugin activity registry: each plugin declares in
``boot()`` how to stop what it runs, and the piano asks for the room. These
tests pin the registry, the exemption of the display, and the order of the two
steps in ``prepare_for_piano()`` — the noise monitor hands the face back to its
default when it stops, so the happy face only survives if it goes on last.
"""

import pytest

from core.plugin_system.base import PluginBase, PluginManager


class FakePlugin(PluginBase):
    """A plugin whose activity is a function the test can watch."""

    def __init__(self, path, name, enabled=True):
        super().__init__(path, enabled)
        self.name = name


def test_a_plugin_declares_how_to_stop_what_it_runs():
    plugin = FakePlugin("plugins.test.one", "One")
    stop = lambda: None

    plugin.register_activity("monitoring", stop, description="Noise monitoring")

    activities = plugin.get_activities()
    assert activities["monitoring"]["stop"] is stop
    assert activities["monitoring"]["description"] == "Noise monitoring"


def test_stopping_a_plugin_calls_every_activity_it_declared():
    plugin = FakePlugin("plugins.test.one", "One")
    called = []
    plugin.register_activity("timer", lambda: called.append("timer"))
    plugin.register_activity("audio", lambda: called.append("audio"))

    stopped = plugin.stop_activities()

    assert sorted(called) == ["audio", "timer"]
    assert sorted(stopped) == ["audio", "timer"]


def test_one_activity_failing_does_not_leave_the_rest_running():
    """A service that will not stop must not take the others down with it."""
    plugin = FakePlugin("plugins.test.one", "One")
    called = []

    def explode():
        raise RuntimeError("service is wedged")

    plugin.register_activity("broken", explode)
    plugin.register_activity("audio", lambda: called.append("audio"))

    stopped = plugin.stop_activities()

    assert called == ["audio"], "the second activity must still be stopped"
    assert stopped == ["audio"]


class _Manager(PluginManager):
    """A manager holding only the plugins a test hands it, no discovery."""

    def __init__(self, plugins):
        super().__init__()
        self._plugins = {path: plugin for path, plugin in plugins}


def test_the_running_plugins_are_stopped():
    noise = FakePlugin("plugins.test.noise", "Noise Monitor")
    timer = FakePlugin("plugins.test.timer", "Activity Timer")
    seen = []
    noise.register_activity("monitoring", lambda: seen.append("noise"))
    timer.register_activity("timer", lambda: seen.append("timer"))

    stopped = _Manager([("plugins.test.noise", noise), ("plugins.test.timer", timer)]).stop_other_activities(
        reason="Touch Piano"
    )

    assert sorted(seen) == ["noise", "timer"]
    assert sorted(stopped) == ["Activity Timer", "Noise Monitor"]


def test_the_exempt_plugins_are_left_running():
    """The display is shared output, and the caller is not a competitor."""
    display = FakePlugin("plugins.test.lcd", "LCD Display")
    piano = FakePlugin("plugins.test.piano", "Touch Piano")
    seen = []
    display.register_activity("animation", lambda: seen.append("display"))
    piano.register_activity("session", lambda: seen.append("piano"))

    stopped = _Manager(
        [("plugins.test.lcd", display), ("plugins.test.piano", piano)]
    ).stop_other_activities(
        except_plugins=("plugins.test.lcd", "plugins.test.piano")
    )

    assert seen == []
    assert stopped == []


def test_a_disabled_plugin_is_not_asked_to_stop():
    """It is not running: disabling it already called uninstall()."""
    disabled = FakePlugin("plugins.test.noise", "Noise Monitor", enabled=False)
    seen = []
    disabled.register_activity("monitoring", lambda: seen.append("noise"))

    stopped = _Manager([("plugins.test.noise", disabled)]).stop_other_activities()

    assert seen == []
    assert stopped == []


def test_a_plugin_with_nothing_to_stop_is_ignored():
    idle = FakePlugin("plugins.test.settings", "Settings Only")

    stopped = _Manager([("plugins.test.settings", idle)]).stop_other_activities()

    assert stopped == [], "only plugins that declared an activity are reported"


# The piano's side of it.


def test_prepare_for_piano_stops_the_others_before_showing_the_face(monkeypatch):
    """The order is the whole point: the noise monitor resets the face to its
    own default as it stops, so a face set first would be overwritten."""
    from plugins.edupi.touch_piano import startup

    order = []
    monkeypatch.setattr(startup, "stop_other_activities", lambda: order.append("stop"))
    monkeypatch.setattr(startup, "show_playing_face", lambda: order.append("face") or True)

    startup.prepare_for_piano()

    assert order == ["stop", "face"]


def test_prepare_for_piano_exempts_the_display_and_itself(monkeypatch):
    from core.plugin_system.base import plugin_manager
    from plugins.edupi.touch_piano import startup

    captured = {}

    def fake_stop(except_plugins=(), reason=""):
        captured["except_plugins"] = tuple(except_plugins)
        captured["reason"] = reason
        return []

    monkeypatch.setattr(plugin_manager, "stop_other_activities", fake_stop)
    monkeypatch.setattr(startup, "show_playing_face", lambda: True)

    startup.prepare_for_piano()

    assert "plugins.edupi.lcd_display" in captured["except_plugins"]
    assert "plugins.edupi.touch_piano" in captured["except_plugins"]


def test_the_noise_monitor_is_stopped_and_then_the_face_goes_happy(monkeypatch):
    """The feature end to end, minus HTTP: the real noise plugin, its real
    registered activity, and the real startup module talking to it."""
    from core.plugin_system.base import plugin_manager
    from plugins.edupi.noise_monitor import plugin as noise_plugin_module
    from plugins.edupi.noise_monitor.noise_service import noise_service
    from plugins.edupi.touch_piano import startup

    events = []
    monkeypatch.setattr(noise_service, "stop_monitoring", lambda: events.append("stopped"))

    noise_plugin = noise_plugin_module.Plugin("plugins.edupi.noise_monitor")
    noise_plugin.boot()

    monkeypatch.setattr(
        plugin_manager,
        "_plugins",
        {"plugins.edupi.noise_monitor": noise_plugin},
    )
    monkeypatch.setattr(
        startup,
        "show_playing_face",
        lambda: events.append("happy") or True,
    )

    startup.prepare_for_piano()

    assert events == ["stopped", "happy"]


def test_the_playing_face_is_happy():
    from plugins.edupi.touch_piano.startup import PLAYING_FACE_MOOD

    assert PLAYING_FACE_MOOD == "happy"


def test_a_missing_display_does_not_break_the_piano(monkeypatch):
    """A disabled LCD is not a reason for the class to hear nothing."""
    from plugins.edupi.lcd_display.lcd_service import lcd_service
    from plugins.edupi.touch_piano import startup

    monkeypatch.setattr(lcd_service, "is_initialized", lambda: False)

    assert startup.show_playing_face() is False


def test_prepare_for_piano_survives_a_service_that_will_not_stop(monkeypatch):
    """The session is already playing by this point: it must not be reported
    as failed because the noise monitor would not go quiet."""
    from plugins.edupi.touch_piano import startup

    def explode():
        raise RuntimeError("service is wedged")

    shown = []
    monkeypatch.setattr(startup, "stop_other_activities", explode)
    monkeypatch.setattr(startup, "show_playing_face", lambda: shown.append(True) or True)

    startup.prepare_for_piano()  # must not raise

    assert shown == [True], "the face is still owed after a failed stop"


@pytest.mark.django_db
def test_starting_a_session_claims_the_room(client, monkeypatch):
    """The wiring: pressing Start on the dashboard is what runs the above."""
    from plugins.edupi.touch_piano import views
    from plugins.edupi.touch_piano.models import PianoConfig, PianoKey
    from plugins.edupi.touch_piano.piano_service import piano_service

    config = PianoConfig.objects.create(
        name="Default", volume=80, sensitivity=5, is_active=True
    )
    PianoKey.objects.create(
        config=config,
        key_number=1,
        note="C4",
        frequency=261.63,
        gpio_pin=4,
        is_active=True,
    )

    # No real GPIO or audio in a test: the service is patched down to the
    # bookkeeping the view does around it.
    for method in (
        "set_volume",
        "set_sensitivity",
        "set_session_id",
        "initialize_audio",
        "initialize_gpio",
        "load_note_sounds",
        "start_monitoring",
    ):
        monkeypatch.setattr(piano_service, method, lambda *a, **k: None)

    called = []
    monkeypatch.setattr(views, "prepare_for_piano", lambda: called.append(True))

    response = client.post("/plugins/edupi/touch_piano/session/start/")

    assert response.status_code == 200, response.content[:500]
    assert response.json()["success"] is True
    assert called == [True], "the room must be claimed when a session starts"
