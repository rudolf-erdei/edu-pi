"""Tests for the journal surviving a reboot.

The field Pi, checked on 2026-09-27 after a power cycle, kept its journal on
tmpfs: `journalctl --list-boots` listed one boot, `/var/log/journal` was empty,
and `journald.conf` had no `Storage` line. So the log written on the way down —
the only record of why a Pi halted, or why it did not come back — was gone by
the time anyone could read it, which is precisely the evidence the dashboard
Power button produces.

`install_persistent_journal()` in `scripts/update_infra.sh` fixes that, and must
run on all three paths: install, CLI update (both via
`setup_update_infrastructure`) and the dashboard update (`update-web.sh`, which
deliberately does not call that function). These tests read the files rather
than restating them, so the three paths cannot drift apart.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INFRA = REPO_ROOT / "scripts" / "update_infra.sh"
UPDATE_WEB = REPO_ROOT / "update-web.sh"
UNINSTALL = REPO_ROOT / "uninstall.sh"
REFERENCE = REPO_ROOT / "docs" / "reference" / "update-system.md"

DROP_IN = "/etc/systemd/journald.conf.d/tinko.conf"
JOURNAL_DIR = "/var/log/journal"


def body_of(function: str, text: str) -> str:
    """The text of one shell function, so assertions cannot match a neighbour."""
    start = text.index(f"{function}() {{")
    end = text.index("\n}\n", start)
    return text[start:end]


def test_the_function_exists_and_asks_journald_for_persistent_storage():
    body = body_of("install_persistent_journal", INFRA.read_text(encoding="utf-8"))

    assert "Storage=persistent" in body
    # The log lives on the SD card; unbounded growth is its own failure.
    assert "SystemMaxUse=" in body
    assert f'"/etc/systemd/journald.conf.d/tinko.conf"' in body


def test_the_directory_is_prepared_the_supported_way():
    """`mkdir` alone is not enough.

    journald runs as systemd-journal and needs the machine-id subdirectory; the
    mode and ACLs that allow it come from systemd-tmpfiles, not from a plain
    mkdir. Skipping this is how a Pi ends up with the config in place and the
    journal still on tmpfs.
    """
    body = body_of("install_persistent_journal", INFRA.read_text(encoding="utf-8"))

    assert "systemd-tmpfiles --create --prefix" in body
    assert body.index("systemd-tmpfiles --create") < body.index("Storage=persistent")


def test_it_checks_where_the_journal_actually_went():
    """Asking is not having: the fallback to tmpfs is silent."""
    body = body_of("install_persistent_journal", INFRA.read_text(encoding="utf-8"))

    assert "journalctl --header" in body
    assert "will not survive a reboot" in body


def test_a_failure_does_not_take_the_update_down_with_it():
    body = body_of("install_persistent_journal", INFRA.read_text(encoding="utf-8"))

    assert "exit 1" not in body, "must return, not exit: the caller decides"
    assert "return 1" in body


def test_all_three_update_paths_install_it():
    infra = INFRA.read_text(encoding="utf-8")

    # install-raspberry-pi.sh and update.sh both call setup_update_infrastructure,
    # so one call there covers both.
    setup = body_of("setup_update_infrastructure", infra)
    assert "install_persistent_journal" in setup, "install + CLI update path"

    # update-web.sh deliberately skips setup_update_infrastructure (it would
    # restart tinko-update.service, which is the service running it), so it
    # needs its own call -- the same reason it calls install_power_helper.
    # Compared inside main(), because the function names also appear where they
    # are defined.
    stage = body_of("main", UPDATE_WEB.read_text(encoding="utf-8"))
    assert "install_persistent_journal" in stage, "dashboard update path"
    assert stage.index("install_persistent_journal") < stage.index("restart_service")


def test_the_header_documents_the_new_helper():
    """The file names its own exports; a sourcing caller reads this to know
    what it may call."""
    header = INFRA.read_text(encoding="utf-8")[:2000]

    assert "install_persistent_journal" in header


def test_uninstall_removes_the_drop_in():
    text = UNINSTALL.read_text(encoding="utf-8")

    assert DROP_IN in text
    assert "remove_journal_config" in text


def test_the_manual_lists_the_file_it_writes():
    """`docs/reference/update-system.md` is the manual for what an update writes
    outside the repository; no test reads docs, so this pins the one thing that
    would otherwise go stale silently."""
    text = REFERENCE.read_text(encoding="utf-8")

    assert DROP_IN in text
    assert JOURNAL_DIR in text
