"""Tests for the journal surviving a reboot.

The field Pi, checked on 2026-09-27 after a power cycle, kept its journal on
tmpfs: `journalctl --list-boots` listed one boot, `/var/log/journal` was empty,
and the log written on the way down — the only record of why a Pi halted, or why
it did not come back — was gone by the time anyone could read it. That is
precisely the evidence the dashboard Power button produces.

`install_persistent_journal()` in `scripts/update_infra.sh` fixes that, and must
run on all three paths: install, CLI update (both via
`setup_update_infrastructure`) and the dashboard update (`update-web.sh`, which
deliberately does not call that function). These tests read the files rather
than restating them, so the three paths cannot drift apart.

Three parts have to hold together, and the first version of this function had
only the middle one:

1. The drop-in must out-sort the vendor's `40-rpi-volatile-storage.conf`, which
   sets `Storage=volatile` from /usr/lib (journald reads drop-ins in name order,
   last one wins).
2. `Storage=persistent` alone is inert on a running journald: the system journal
   is opened only once a flush has been requested, so `journalctl --flush` is
   the step that actually moves the log off tmpfs.
3. log2ram only backs the journal up to disk when its File path is under
   /var/log, so (1) is also what makes it survive the next boot.
"""

import re
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
    # /var/log is a 128M tmpfs (log2ram): a journal at its default share of it
    # would crowd out the dnsmasq and tinko_wifi logs the portal is read from,
    # and RuntimeMaxUse is what applies while the journal is still in /run.
    assert "SystemMaxUse=" in body
    assert "RuntimeMaxUse=" in body
    assert f'"{DROP_IN}"' in body


def test_the_drop_in_name_sorts_after_the_vendor_one_it_overrides():
    """journald reads drop-ins in name order and the last one wins.

    Raspberry Pi OS forces Storage=volatile from a file in /usr/lib; ours only
    wins because its basename sorts after that one. Renaming it to something
    starting with a digit, or with "r"/"t" inside the first few characters, would
    hand the vendor file the last word again -- silently: journald just stays
    volatile and says nothing. The vendor name is read from the comments rather
    than restated here, so a rename upstream shows up as a comment that no longer
    matches the sort.
    """
    body = body_of("install_persistent_journal", INFRA.read_text(encoding="utf-8"))

    vendor = re.search(r"(\d[\w.-]*volatile-storage\.conf)", body)
    assert vendor, "the vendor drop-in it overrides must be named in the comments"
    assert Path(DROP_IN).name > vendor.group(1)


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


def test_the_flush_is_what_moves_the_journal_off_tmpfs():
    """Storage=persistent alone changes nothing on a running journald.

    journald opens the system journal only once a flush has been requested
    (server_system_journal_open(): `flush_requested || server_flushed_flag_is_set`),
    so installing the drop-in and restarting journald is inert until the next
    boot. The field Pi is exactly that failure: drop-in installed with the right
    contents, journal still on tmpfs, no complaint from anyone. `journalctl
    --flush` is the step that makes the setting take effect now.
    """
    body = body_of("install_persistent_journal", INFRA.read_text(encoding="utf-8"))

    assert "journalctl --flush" in body
    restart = body.index("systemctl restart systemd-journald")
    flush = body.index("journalctl --flush")
    assert restart < flush, "the drop-in must be in place before it is flushed"
    assert flush < body.index("journalctl --header"), "flush before checking the result"


def test_it_checks_where_the_journal_actually_went():
    """Asking is not having: the fallback to tmpfs is silent."""
    body = body_of("install_persistent_journal", INFRA.read_text(encoding="utf-8"))

    assert "journalctl --header" in body
    assert "will not survive a reboot" in body


def test_it_reads_the_field_the_header_actually_prints():
    """`journalctl --header` prints "File path:", not "File:".

    The first version of the check grepped `^File:` and so matched nothing at
    all, which surfaced as "Could not read the journal header" on a Pi whose
    journal was in fact still volatile -- a warning that blamed the check instead
    of the journal. log2ram greps the same field for the same reason, so the
    spelling is pinned rather than assumed.
    """
    body = body_of("install_persistent_journal", INFRA.read_text(encoding="utf-8"))

    assert "^File path:" in body
    assert "^File:" not in body
    # One "File path:" line per open file (system journal, plus one per logged-in
    # user), so the system journal has to be picked out of the list.
    assert "/system" in body
    assert "user-" in body


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
