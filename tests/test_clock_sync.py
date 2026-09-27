"""Tests for the clock being right soon after a boot.

The field Pi (2026-09-27) has no RTC and no `fake-hwclock`. Until NTP answers,
the clock is the mtime of `/var/lib/systemd/timesync/clock`, which PID1 restores
with `System time advanced to timestamp on /var/lib/systemd/timesync/clock` --
the moment the Pi last shut down. `systemd-timesyncd` does correct it (42s after
boot on that Pi: the time wifi association and DHCP take), so this is not a
broken clock, it is a window: during it, log lines carry yesterday's date and a
`git pull` over HTTPS can fail a certificate check in a way that reads like a
network fault -- the same shape as the bug that hid a broken web update for
weeks.

Two helpers narrow the window, and both are in `scripts/update_infra.sh`:

- `install_timesync_config()` -- retry NTP every 5s instead of 30s.
- `ensure_clock_is_set()`  -- settle the clock before every update pull.

Both are deliberately non-fatal: an offline Pi has nothing to sync with, and the
captive-portal path must never depend on the internet. These tests read the
scripts rather than restating them, so the three paths cannot drift apart.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INFRA = REPO_ROOT / "scripts" / "update_infra.sh"
UPDATE = REPO_ROOT / "update.sh"
UPDATE_WEB = REPO_ROOT / "update-web.sh"
UNINSTALL = REPO_ROOT / "uninstall.sh"
REFERENCE = REPO_ROOT / "docs" / "reference" / "update-system.md"
TROUBLESHOOTING = REPO_ROOT / "docs" / "reference" / "troubleshooting.md"

DROP_IN = "/etc/systemd/timesyncd.conf.d/tinko.conf"
CLOCK_FILE = "/var/lib/systemd/timesync/clock"


def body_of(function: str, text: str) -> str:
    """The text of one shell function, so assertions cannot match a neighbour."""
    start = text.index(f"{function}() {{")
    end = text.index("\n}\n", start)
    return text[start:end]


def test_it_retries_ntp_sooner_than_the_default():
    """The default 30s retry can outlast the network it is waiting for.

    Wifi association and DHCP take ~35s on this hardware. The first NTP attempt
    happens before that and fails, so the clock waits a full retry interval after
    the network is already up.
    """
    body = body_of("install_timesync_config", INFRA.read_text(encoding="utf-8"))

    assert "[Time]" in body
    retry = re.search(r"^ConnectionRetrySec=(\d+)$", body, re.MULTILINE)
    assert retry, "the drop-in must set ConnectionRetrySec"
    assert 0 < int(retry.group(1)) < 30, "anything above the default is pointless"
    assert f'"{DROP_IN}"' in body


def test_it_reports_the_state_not_the_intent():
    """A Pi with no network is a normal Pi.

    Claiming a sync that did not happen is the same mistake the journal check
    shipped with ("Could not read the journal header" on a journal that was
    plainly volatile), so the drop-in is written and the state is asked for
    afterwards.
    """
    body = body_of("install_timesync_config", INFRA.read_text(encoding="utf-8"))

    assert "NTPSynchronized" in body
    assert 'log_success' in body and "log_info" in body
    # The un-synchronized branch is reported, not celebrated: log_success must
    # live in the `then` half of the test, log_info in the `else` half.
    assert body.index("log_success") < body.index("else")
    assert body.index("log_info") > body.index("else")


def test_both_helpers_are_non_fatal():
    """An update must not abort because the clock could not be settled.

    `update.sh` and `update-web.sh` both run under `set -e`, so the callers use
    `|| true`; inside the helpers, returning is what lets them.
    """
    text = INFRA.read_text(encoding="utf-8")

    for function in ("install_timesync_config", "ensure_clock_is_set"):
        body = body_of(function, text)
        assert "exit 1" not in body, f"{function} must return, not exit"
        assert "return 1" in body
        assert "systemctl restart systemd-timesyncd" in body


def test_the_wait_is_bounded():
    """An update that hangs on a dead network is worse than a wrong clock.

    The poll is a fixed number of 2s steps, and the limit is read from the script
    so raising it is a deliberate edit rather than a silent one.
    """
    body = body_of("ensure_clock_is_set", INFRA.read_text(encoding="utf-8"))

    limit = re.search(r'"\$waited" -lt (\d+)', body)
    assert limit, "the poll loop needs an explicit bound"
    assert int(limit.group(1)) <= 60, "an update may not wait minutes for NTP"
    assert "sleep 2" in body


def test_it_falls_back_to_a_web_server_when_ntp_is_blocked():
    """UDP 123 is dropped on some school networks; HTTPS is not.

    A plain HTTP request needs no certificate, so it is the one clock source that
    works *while* the clock is wrong -- which is the only time this code runs.
    """
    body = body_of("ensure_clock_is_set", INFRA.read_text(encoding="utf-8"))

    assert "curl" in body
    assert "http://" in body, "must be plain HTTP: a TLS request would fail too"
    assert "[Dd]ate:" in body, "the Date header is the source (either spelling)"
    assert "date -u -s" in body, "set in UTC; the header is UTC"


def test_the_clock_is_settled_before_the_pull_on_both_update_paths():
    """The pull is where a wrong clock becomes a misleading failure.

    It runs before anything is moved aside, so a failure here leaves the tree
    exactly as it was -- and it is non-fatal, so the pull still reports its own
    error rather than the update stopping silently.
    """
    for script in (UPDATE, UPDATE_WEB):
        stage = body_of("pull_latest", script.read_text(encoding="utf-8"))
        assert "ensure_clock_is_set" in stage, f"{script.name} must settle the clock"
        assert "ensure_clock_is_set || true" in stage, "set -e is on in both scripts"
        assert stage.index("ensure_clock_is_set") < stage.index("hide_live_db"), (
            f"{script.name}: the clock is checked before files are moved aside"
        )


def test_all_three_update_paths_install_the_retry_config():
    infra = INFRA.read_text(encoding="utf-8")

    # install-raspberry-pi.sh and update.sh both call setup_update_infrastructure.
    setup = body_of("setup_update_infrastructure", infra)
    assert "install_timesync_config" in setup, "install + CLI update path"

    # update-web.sh deliberately skips that function (it would restart
    # tinko-update.service, which is running it), so it needs its own call.
    stage = body_of("main", UPDATE_WEB.read_text(encoding="utf-8"))
    assert "install_timesync_config" in stage, "dashboard update path"
    assert stage.index("install_timesync_config") < stage.index("restart_service")


def test_the_header_documents_the_new_helpers():
    """The file names its own exports; a sourcing caller reads this to know
    what it may call."""
    header = INFRA.read_text(encoding="utf-8")[:2400]

    assert "install_timesync_config" in header
    assert "ensure_clock_is_set" in header


def test_uninstall_removes_the_drop_in_and_leaves_the_clock_alone():
    text = UNINSTALL.read_text(encoding="utf-8")

    assert DROP_IN in text
    assert "remove_timesync_config" in text
    # NTP itself is on by default on this image with or without Tinko; turning it
    # off would leave the Pi with no time source at all.
    assert "systemctl disable systemd-timesyncd" not in text


def test_the_manual_explains_where_the_clock_comes_from():
    """No test reads docs, so the one claim that was wrong earlier is pinned."""
    text = REFERENCE.read_text(encoding="utf-8")

    assert DROP_IN in text
    assert CLOCK_FILE in text

    # The original explanation credited `fake-hwclock`, which is not installed on
    # this image; PID1 restoring the clock file's mtime is what actually happens.
    troubleshooting = TROUBLESHOOTING.read_text(encoding="utf-8")
    if "fake-hwclock" in troubleshooting:
        assert "not installed" in troubleshooting, (
            "fake-hwclock must not be described as the time source"
        )
    assert CLOCK_FILE in troubleshooting
