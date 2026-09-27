"""Tests for the app's clock being the one on the wall.

The field Pi (2026-09-27) showed times three hours behind its own `date` and
`timedatectl` — no RTC, NTP synchronized, `Europe/Bucharest` — because
`config/settings.py` had `TIME_ZONE = "UTC"` hardcoded while `.env` carried
`TIME_ZONE=Europe/Bucharest`, written there by the installer from the machine's
own zone and then never read. So the app was *configured* correctly and ignored
it. Django also exports this setting as the process's `TZ`, which is why the
whole process — `datetime.now()`, template `|date`, and any `strftime` on a
stored value — was on UTC.

Two things are tested here: that the setting is derived rather than hardcoded
(machine's zone, then `.env`, then UTC), and that the places which format a
stored datetime for a human convert it first — `strftime` on an aware datetime
prints *its own* offset, so a UTC row reads as the UTC hour however the settings
are set. The noise chart's clock labels were exactly that, and they are the
times a teacher reads.
"""

import re
import zoneinfo
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from config import settings as app_settings

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = REPO_ROOT / "config" / "settings.py"
INSTALLER = REPO_ROOT / "install-raspberry-pi.sh"
REFERENCE = REPO_ROOT / "docs" / "reference" / "configuration.md"

# One zone with a DST rule and one without, so nothing here depends on the
# machine's own zone or on the current date.
WALL_CLOCK = "Europe/Bucharest"


def test_the_setting_is_derived_not_hardcoded():
    """The bug in one line: `TIME_ZONE = "UTC"` next to a `.env` that said
    otherwise."""
    text = SETTINGS_FILE.read_text(encoding="utf-8")

    # Anchored at column zero: the helper's own docstring names the old line
    # while explaining it, and an assignment is what matters.
    assert '\nTIME_ZONE = "UTC"' not in text
    assert "TIME_ZONE = time_zone()" in text


def test_the_installed_value_is_actually_read():
    """The installer has always written this; nothing has always read it."""
    assert "TIME_ZONE=" in INSTALLER.read_text(encoding="utf-8")
    assert 'os.environ.get("TIME_ZONE")' in SETTINGS_FILE.read_text(encoding="utf-8")


def test_the_machine_zone_wins(monkeypatch):
    """What `date` prints is what the dashboard shows.

    A Pi that is moved, or set with `timedatectl set-timezone`, follows on the
    next restart, without anyone editing `.env` on the device.
    """
    monkeypatch.setattr(app_settings, "system_time_zone", lambda: WALL_CLOCK)
    monkeypatch.setenv("TIME_ZONE", "Australia/Sydney")

    assert app_settings.time_zone() == WALL_CLOCK


def test_the_configured_zone_is_the_fallback(monkeypatch):
    """Windows and containers have no system zone to read."""
    monkeypatch.setattr(app_settings, "system_time_zone", lambda: None)
    monkeypatch.setenv("TIME_ZONE", WALL_CLOCK)

    assert app_settings.time_zone() == WALL_CLOCK


def test_an_unresolvable_zone_falls_back_instead_of_raising(monkeypatch):
    """A typo must cost the right hour, not the page.

    Django raises the moment it converts a time with a zone it cannot resolve,
    so `TIME_ZONE=Mars/Olympus` in `.env` would take every page down. The
    fallback keeps the app up, and `TIME_ZONE` is always a zone this system can
    actually resolve.
    """
    monkeypatch.setattr(app_settings, "system_time_zone", lambda: None)
    monkeypatch.setenv("TIME_ZONE", "Mars/Olympus")

    assert app_settings.time_zone() == "UTC"
    zoneinfo.ZoneInfo(app_settings.time_zone())  # resolves, so Django can use it


def test_the_zone_django_is_running_with_resolves():
    """Whatever the settings ended up with has to be usable."""
    zoneinfo.ZoneInfo(app_settings.TIME_ZONE)


@pytest.mark.parametrize(
    "name",
    ["", None, "  ", "/etc/passwd", "../../etc/passwd", "Europe/../UTC", "nonsense"],
)
def test_only_a_real_zone_is_accepted(name):
    assert app_settings.valid_time_zone(name) is None


@pytest.mark.parametrize("name", [WALL_CLOCK, "UTC", "Asia/Kolkata"])
def test_a_real_zone_is_kept(name):
    assert app_settings.valid_time_zone(name) == name


def test_the_name_is_read_from_the_timezone_file(tmp_path, monkeypatch):
    """Debian and Raspberry Pi OS: the name is in a file."""
    zone_file = tmp_path / "timezone"
    zone_file.write_text(f"{WALL_CLOCK}\n", encoding="utf-8")
    monkeypatch.setattr(app_settings, "TIME_ZONE_FILE", str(zone_file))
    monkeypatch.setattr(app_settings, "LOCALTIME_FILE", str(tmp_path / "absent"))

    assert app_settings.system_time_zone() == WALL_CLOCK


def test_the_name_is_read_from_the_localtime_symlink(tmp_path, monkeypatch):
    """Everywhere else, `/etc/localtime` points into the zoneinfo tree, and the
    path below that root *is* the zone name."""
    root = tmp_path / "zoneinfo"
    (root / "Europe").mkdir(parents=True)
    (root / "Europe" / "Bucharest").write_text("", encoding="utf-8")
    localtime = tmp_path / "localtime"
    try:
        localtime.symlink_to(root / "Europe" / "Bucharest")
    except OSError:
        pytest.skip("this platform does not allow symlinks")

    monkeypatch.setattr(app_settings, "TIME_ZONE_FILE", str(tmp_path / "absent"))
    monkeypatch.setattr(app_settings, "LOCALTIME_FILE", str(localtime))
    monkeypatch.setattr(app_settings, "ZONEINFO_ROOT", f"{root.as_posix()}/")

    assert app_settings.system_time_zone() == WALL_CLOCK


def test_a_machine_with_no_zone_at_all_says_so(tmp_path, monkeypatch):
    """Not an error: Windows and containers have neither file."""
    monkeypatch.setattr(app_settings, "TIME_ZONE_FILE", str(tmp_path / "absent"))
    monkeypatch.setattr(app_settings, "LOCALTIME_FILE", str(tmp_path / "absent"))

    assert app_settings.system_time_zone() is None


def test_the_chart_labels_the_local_clock(settings):
    """The chart's clock times are the ones a teacher reads.

    `strftime` on an aware datetime prints its own offset, not the reader's, so
    a row stored at 09:00 UTC was labelled 09:00 on a page whose clock said
    12:00. Three hours wrong, on the one card that is *about* time.
    """
    from plugins.edupi.noise_monitor.chart import _time_label

    settings.TIME_ZONE = WALL_CLOCK
    reading = SimpleNamespace(
        timestamp=datetime(2026, 9, 27, 9, 0, tzinfo=timezone.utc)
    )

    assert _time_label(reading) == "12:00"


def test_every_displayed_time_is_converted():
    """A static guard over the places that format a stored time for a human.

    Each of these prints what a person reads, and each must go through
    `localtime()` first — a new one that formats `self.started_at` directly
    reintroduces the bug in a corner nobody looks at twice.
    """
    for path in [
        REPO_ROOT / "plugins" / "edupi" / "noise_monitor" / "chart.py",
        REPO_ROOT / "plugins" / "edupi" / "noise_monitor" / "models.py",
        REPO_ROOT / "plugins" / "edupi" / "lcd_display" / "models.py",
        REPO_ROOT / "plugins" / "edupi" / "touch_piano" / "models.py",
    ]:
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if ".strftime(" in line and not line.lstrip().startswith("#"):
                assert "localtime(" in line, f"{path.name}:{number} formats a stored time"


def test_the_manual_explains_where_the_zone_comes_from():
    """The reference page listed `TIME_ZONE` as a plain setting; it has a
    precedence now, and the reason for it is a bug that was hard to see."""
    text = REFERENCE.read_text(encoding="utf-8")

    assert "/etc/timezone" in text
    assert re.search(r"machine'?s own zone", text)
    assert "TIME_ZONE" in text


def test_the_installed_zone_and_the_system_zone_agree_on_a_pi():
    """The installer reads the zone from systemd; settings read it from a file.

    Both are checked against the same command on the Pi, so pin the one thing
    that could silently differ: the installer asks `timedatectl`.
    """
    text = INSTALLER.read_text(encoding="utf-8")

    assert "timedatectl show --property=Timezone --value" in text
