"""The operating system's share of the SD card's writes.

``tests/test_sd_card_writes.py`` covers what the app itself writes -- the log
handlers and the database. This file covers ``scripts/update_infra.sh``'s
``optimize_for_sd_card()``: the timers, the mounts and the kernel settings that
keep the card out of the picture, installed from ``update_infra.sh`` and undone
by ``uninstall.sh``.

Two of those steps rewrite a file the machine needs in order to boot (fstab) or
to find its hardware (config.txt), so the functions that do the rewriting are
filters -- file in on stdin, file out on stdout -- and the tests below run the
real bodies against real files. A filter that adds an option to the wrong line,
or drops one, fails here instead of on a Pi that then does not come back on.

Everything else is checked by reading the scripts, because it needs systemd,
sudo and a Raspberry Pi to actually run: the ordering that matters there is the
order of the steps, and that is visible in the text.
"""

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
INFRA = REPO_ROOT / "scripts" / "update_infra.sh"
UNINSTALL = REPO_ROOT / "uninstall.sh"
DOCS = REPO_ROOT / "docs" / "reference" / "sd-card.md"

# The field Pi's own fstab, which is what this edit was written against.
SAMPLE_FSTAB = """\
proc            /proc           proc    defaults          0       0
PARTUUID=45361015-01  /boot/firmware  vfat    defaults          0       2
PARTUUID=45361015-02  /               ext4    defaults,noatime  0       1
# the root line above is the one that gets commit=, not the one below
PARTUUID=deadbeef-02  /mnt/other      ext4    defaults          0       2
"""

# And the tail of a stock config.txt.
SAMPLE_CONFIG = """\
# Enable audio (loads snd_bcm2835)
dtparam=audio=on

[cm5]
dtoverlay=dwc2,dr_mode=host

[all]
enable_uart=1
"""


def extract_function(name: str, path: Path = INFRA) -> str:
    """Return the source of ``name`` from *path*.

    From the declaration to the first line that is a closing brace on its own --
    which is how every function in these scripts ends. Raises rather than
    returning nothing, so a rename cannot turn these tests into no-ops.
    """
    text = path.read_text(encoding="utf-8")
    start = text.index(f"\n{name}() {{")
    end = text.index("\n}\n", start)
    return text[start : end + len("\n}")]


def extract_documented(name: str, path: Path = INFRA) -> str:
    """The function plus the comment block written directly above it.

    Some of what these steps decide is only written down above the declaration --
    the reason `systemctl disable` cannot work on the zram timer, the trade the
    apt timers make. A test that reads the body alone would not see it, and the
    point of the assertion is that the decision is explained where it is made.
    """
    text = path.read_text(encoding="utf-8")
    start = text.index(f"\n{name}() {{")
    head = text[:start].split("\n")
    first = len(head)
    while first > 0 and head[first - 1].startswith("#"):
        first -= 1
    body = text[start : text.index("\n}\n", start) + len("\n}")]
    return "\n".join(head[first:]) + "\n" + body


def run_filter(tmp_path, function: str, args: str, stdin: str) -> str:
    """Run a shipped filter function with *stdin*, return its stdout."""
    harness = tmp_path / "filter.sh"
    harness.write_text(
        "\n".join(
            [
                "set -u",
                extract_function(function),
                f"{function} {args}",
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(harness)],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, f"{function} failed:\n{result.stderr}"
    return result.stdout


def lines(text: str) -> list[str]:
    return text.splitlines()


def root_line(text: str) -> str:
    return next(line for line in lines(text) if line.split()[1] == "/")


# --- fstab: commit=600 on the root mount ----------------------------------


def test_the_root_line_gains_the_commit_option(tmp_path):
    out = run_filter(tmp_path, "sd_fstab_add_commit", "600", SAMPLE_FSTAB)

    assert "defaults,noatime,commit=600" in root_line(out), (
        "the root mount must commit less often; that is the whole change"
    )


def test_every_other_line_is_left_exactly_as_it_was(tmp_path):
    """A wrong mount here is a Pi that does not boot, so nothing else moves."""
    out = run_filter(tmp_path, "sd_fstab_add_commit", "600", SAMPLE_FSTAB)

    original = lines(SAMPLE_FSTAB)
    assert len(lines(out)) == len(original), "no line may be added or lost"
    for before, after in zip(original, lines(out)):
        if len(before.split()) > 1 and before.split()[1] == "/":
            continue  # the one line the change is for
        assert before == after, f"{before!r} was rewritten"


def test_the_comment_naming_commit_is_not_touched(tmp_path):
    """Comments mention options; only a real mount line may be edited."""
    out = run_filter(tmp_path, "sd_fstab_add_commit", "600", SAMPLE_FSTAB)

    comment = [line for line in lines(out) if line.startswith("#")]
    assert comment == ["# the root line above is the one that gets commit=, not the one below"]


def test_the_other_ext4_mount_is_not_touched(tmp_path):
    """Only the root line: /mnt/other is somebody else's decision."""
    out = run_filter(tmp_path, "sd_fstab_add_commit", "600", SAMPLE_FSTAB)

    assert "/mnt/other      ext4    defaults          0       2" in out


def test_running_it_twice_changes_nothing(tmp_path):
    """Every update runs this again; an update must not rewrite fstab."""
    once = run_filter(tmp_path, "sd_fstab_add_commit", "600", SAMPLE_FSTAB)
    twice = run_filter(tmp_path, "sd_fstab_add_commit", "600", once)

    assert once == twice
    assert root_line(twice).count("commit=") == 1, "the option must not be added twice"


def test_an_fstab_with_no_root_line_comes_back_unchanged(tmp_path):
    """Nothing to do is not an error, and not a reason to rewrite the file."""
    without_root = "proc  /proc  proc  defaults  0  0\n"

    assert run_filter(tmp_path, "sd_fstab_add_commit", "600", without_root) == without_root


def test_a_short_line_is_not_mistaken_for_a_mount(tmp_path):
    """Fewer than four fields is not a mount line, whatever its second field."""
    short = "tmpfs  /  tmpfs\n"

    assert run_filter(tmp_path, "sd_fstab_add_commit", "600", short) == short


# --- config.txt: Bluetooth off -------------------------------------------


def test_the_bluetooth_overlay_lands_under_an_all_section(tmp_path):
    out = run_filter(tmp_path, "sd_boot_config_with_bt_off", "'# Tinko: Bluetooth off'", SAMPLE_CONFIG)

    assert "dtoverlay=disable-bt" in out
    overlay = lines(out).index("dtoverlay=disable-bt")
    section = max(i for i, line in enumerate(lines(out)) if line.startswith("["))
    assert section == overlay - 1, "the overlay must sit in the section above it"
    assert lines(out)[section] == "[all]", (
        "anything the firmware reads must apply to every board: a stale section "
        "header would silently keep the overlay off the Pi it was meant for"
    )


def test_the_rest_of_config_txt_is_kept(tmp_path):
    out = run_filter(tmp_path, "sd_boot_config_with_bt_off", "'# Tinko: Bluetooth off'", SAMPLE_CONFIG)

    for line in lines(SAMPLE_CONFIG):
        if line:
            assert line in out, f"{line!r} was lost"
    assert lines(out)[: len(lines(SAMPLE_CONFIG))] == lines(SAMPLE_CONFIG), (
        "the block is appended; the existing file is not rewritten"
    )


def test_the_block_is_not_appended_twice(tmp_path):
    """The installer runs on every update, and every update appends nothing."""
    once = run_filter(tmp_path, "sd_boot_config_with_bt_off", "'# Tinko: Bluetooth off'", SAMPLE_CONFIG)
    twice = run_filter(tmp_path, "sd_boot_config_with_bt_off", "'# Tinko: Bluetooth off'", once)

    assert once == twice
    assert twice.count("dtoverlay=disable-bt") == 1


def test_a_file_with_no_trailing_newline_is_not_run_into(tmp_path):
    """config.txt is edited by hand, and a hand edit may not end in a newline."""
    out = run_filter(
        tmp_path, "sd_boot_config_with_bt_off", "'# Tinko: Bluetooth off'", SAMPLE_CONFIG.rstrip("\n")
    )

    assert "enable_uart=1\n\n# Tinko: Bluetooth off" in out


# --- the steps, and the order that matters --------------------------------


def test_optimize_for_sd_card_runs_every_step():
    body = extract_function("optimize_for_sd_card")

    for step in (
        "sd_disable_apt_timers",
        "sd_disable_zram_writeback",
        "sd_disable_bluetooth",
        "sd_mount_var_tmp_in_ram",
        "sd_set_writeback_sysctl",
        "sd_add_root_commit_option",
        "install_log2ram",
    ):
        assert f"{step} ||" in body, f"{step} is never called, or its failure is not caught"


def test_every_step_survives_failing():
    """One failed step must not abort the update: a Pi with Bluetooth on is
    still a working Pi, and half-updating one is not."""
    for step in (
        "sd_disable_apt_timers",
        "sd_disable_zram_writeback",
        "sd_disable_bluetooth",
        "sd_mount_var_tmp_in_ram",
        "sd_set_writeback_sysctl",
        "sd_add_root_commit_option",
        "install_log2ram",
    ):
        body = extract_function(step)
        assert "log_error" in body or "log_warning" in body, (
            f"{step} fails silently -- the failure has to reach the log"
        )


def test_all_three_entry_points_apply_it():
    """Installer, CLI update and web update. Missing one leaves a Pi that is
    updated one way writing to its card and a Pi updated the other way not."""
    installer = (REPO_ROOT / "install-raspberry-pi.sh").read_text(encoding="utf-8")
    web = (REPO_ROOT / "update-web.sh").read_text(encoding="utf-8")
    infra = INFRA.read_text(encoding="utf-8")
    setup = extract_function("setup_update_infrastructure")

    assert "optimize_for_sd_card" in setup, "the install/CLI path no longer calls it"
    assert "setup_update_infrastructure" in installer
    assert re.search(r"^\s*optimize_for_sd_card \|\|", web, re.M), (
        "update-web.sh calls the steps one by one; it must call this one too"
    )
    assert "optimize_for_sd_card()" in infra


def test_the_header_documents_the_new_step():
    header = INFRA.read_text(encoding="utf-8")[:3000]

    assert "optimize_for_sd_card" in header
    assert "install_log2ram" in header


# --- the individual steps -------------------------------------------------


def test_the_fstab_edit_is_backed_up_verified_and_reverted():
    """Three guards around the one change that can stop a Pi booting."""
    body = extract_function("sd_add_root_commit_option")

    backup = body.index('install -o root -g root -m 0644 "$FSTAB_FILE" "$backup"')
    verify = body.index("sd_fstab_verify")
    install = body.index('sudo install -o root -g root -m 0644 "$candidate" "$FSTAB_FILE"')
    assert verify < install, "verify the candidate before it becomes the real fstab"
    assert backup < install, "the backup must exist before the file is replaced"
    assert body.count("sd_fstab_verify") >= 2, (
        "the installed file must be verified too, not just the candidate"
    )
    assert 'install -o root -g root -m 0644 "$backup" "$FSTAB_FILE"' in body, (
        "a file that fails verification must be restored from the backup"
    )
    assert "root entry" in body, "a rewrite that loses the root line must be refused"


def test_the_fstab_edit_is_structural_before_it_is_semantic():
    """findmnt --verify does not check option names (it accepted a bogus option
    on the field Pi), so the line count and the root entry are checked directly."""
    body = extract_function("sd_add_root_commit_option")

    assert "grep -c ''" in body, "line count is the check that a rewrite did not eat a line"
    assert "found = 1" in body, "the rewritten table must still have a root entry"


def test_var_tmp_is_a_mount_unit_not_an_fstab_line():
    """A fstab systemd cannot parse drops the Pi into emergency mode with no
    network; a mount unit that fails just fails."""
    body = extract_function("sd_mount_var_tmp_in_ram")

    assert "Where=/var/tmp" in body
    assert "var-tmp.mount" in body, "the unit name must match Where=, or systemd refuses it"
    assert "systemd-analyze verify" in body, "verify before installing, not after"
    assert "daemon-reload" in body
    assert "systemctl enable var-tmp.mount" in body, "or it is not there at the next boot"


def test_the_writeback_sysctl_wins_over_the_vendors():
    body = extract_function("sd_set_writeback_sysctl")

    assert "99-tinko-sd.conf" in body, (
        "sysctl.d is read in filename order and the last value wins; 98-rpi.conf "
        "is the vendor's, so ours has to sort after it"
    )
    assert "vm.dirty_writeback_centisecs = 6000" in body
    assert "vm.dirty_expire_centisecs" in body, (
        "a flusher interval longer than the expire time would just be rounded back"
    )
    assert "sysctl -n vm.dirty_writeback_centisecs" in body, (
        "report the value in force, not the file's contents"
    )


def test_the_zram_writeback_goes_through_the_supported_configuration():
    """`disable` is not enough on this unit: rpi-swap-generator recreates it at
    every boot, so the setting that stops it being created is the fix."""
    body = extract_function("sd_disable_zram_writeback")

    assert "swap.conf.d" in extract_documented("sd_disable_zram_writeback"), (
        "swap.conf(5) names the drop-in directory, and the reason this is a "
        "drop-in rather than an edit of the vendor's file has to be written down"
    )
    assert "WritebackTrigger=manual" in body
    assert "daemon-reload" in body, "the generator only re-runs on a reload"
    assert "mask" in body, (
        "and if this image's generator ignores the drop-in, a mask is the "
        "fallback that works regardless"
    )
    assert "systemctl is-active" in body, (
        "report what the timer did, not what disable was asked to do"
    )


def test_the_bluetooth_step_says_the_overlay_needs_a_reboot():
    body = extract_function("sd_disable_bluetooth")

    assert "next reboot" in body, (
        "the overlay is read by the firmware at boot; claiming it is already off "
        "is the kind of success report this project keeps getting bitten by"
    )
    assert "grep -qE" in body, "checked before it is appended, so a second run is a no-op"
    assert "bluetooth.service" in body and "hciuart.service" in body, (
        "the overlay removes the controller; the services would log about it forever"
    )


def test_log2ram_is_installed_by_the_project_itself():
    """The journal work assumes /var/log is log2ram's tmpfs, and nothing here
    used to install it -- the field Pi had it because someone added it by hand."""
    body = extract_function("install_log2ram")

    assert "apt-get install -y log2ram" in body
    assert "install ok installed" in body, "already-installed is the normal case, not an error"
    assert "log2ram-daily.timer" in body
    assert "log_warning" in body, "no network is a normal answer on a classroom Pi"


def test_apt_timers_are_disabled_with_their_trade_off_written_down():
    body = extract_function("sd_disable_apt_timers")

    assert "apt-daily.timer" in body and "apt-daily-upgrade.timer" in body
    assert "disable --now" in body
    assert "runs apt by hand" in extract_documented("sd_disable_apt_timers"), (
        "with these off, OS packages only move by hand; that has to be said "
        "where the decision is made"
    )


# --- reversing it ---------------------------------------------------------


def test_uninstall_reverses_every_step():
    main = UNINSTALL.read_text(encoding="utf-8")
    body = extract_function("remove_sd_optimizations", UNINSTALL)

    assert "remove_sd_optimizations" in main.split("main() {")[1], "defined but never called"
    for artifact in (
        "/etc/systemd/system/var-tmp.mount",
        "/etc/sysctl.d/99-tinko-sd.conf",
        "/etc/rpi/swap.conf.d/tinko.conf",
    ):
        assert artifact in body, f"{artifact} is installed but never removed"
    for unit in ("bluetooth.service", "apt-daily.timer", "apt-daily-upgrade.timer"):
        assert unit in body, f"{unit} is disabled but never re-enabled"
    assert 'dtoverlay=disable-bt' in body
    assert "/etc/fstab.tinko-bak" in body


def test_uninstall_checks_before_it_rewrites_a_boot_file():
    """Both files are read at boot. Uninstall removes Tinko's own lines, and
    only when it can recognise them -- never by restoring a stale copy over an
    edit somebody else made since."""
    body = extract_function("remove_sd_optimizations", UNINSTALL)

    assert "removed_lines" in body and "-eq 2" in body, (
        "config.txt is rewritten only when exactly Tinko's two lines are found"
    )
    assert "grep -q 'commit='" in body, (
        "fstab is restored only when the commit= option is the thing that changed"
    )
    assert "findmnt --verify" in body, "and the restored table is checked"
    assert "leaving both files alone" in body, (
        "when it cannot tell, it must say so rather than guess"
    )


def test_uninstall_leaves_log2ram_installed_and_says_so():
    body = extract_function("remove_sd_optimizations", UNINSTALL)

    assert "log2ram is left installed" in body
    assert "apt-get remove log2ram" in body, "the admin is told how to finish the job"


# --- the manual -----------------------------------------------------------


def test_the_manual_has_a_page_for_this():
    assert DOCS.exists(), "docs/reference/sd-card.md is the manual for all of this"
    text = DOCS.read_text(encoding="utf-8")

    nav = yaml.safe_load((REPO_ROOT / "mkdocs.yml").read_text(encoding="utf-8"))
    reference = next(entry for entry in nav["nav"] if "Reference" in entry)
    entries = reference["Reference"]
    assert any("sd-card.md" in str(entry) for entry in entries), (
        "a page that is not in the nav ships unlisted"
    )

    for subject in ("commit=600", "/var/tmp", "Bluetooth", "log2ram", "zram"):
        assert subject in text, f"the manual does not mention {subject}"


def test_the_manual_says_what_it_costs():
    """Every one of these trades something. The page has to say what."""
    text = DOCS.read_text(encoding="utf-8")

    assert "power" in text.lower() and ("lose" in text or "lost" in text), (
        "the reader has to know these trade durability for card life"
    )
    assert "by hand" in text, "the apt timers are the one that changes how the OS is updated"


@pytest.mark.parametrize("script", ["scripts/update_infra.sh", "update.sh", "update-web.sh", "uninstall.sh"])
def test_the_scripts_still_parse(script):
    """Cheap, and it is the one check that catches a typo in a file that only
    ever runs on a Pi."""
    result = subprocess.run(
        ["bash", "-n", str(REPO_ROOT / script)], capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr
