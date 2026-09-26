"""Tests for the dashboard Power button (`/power/shutdown/`).

The button used to spawn `sudo -n bash -c "shutdown now; ..."` and answer
`{"ok": true}` the moment the process was spawned, with stderr discarded. It
therefore worked only because Raspberry Pi OS ships `010_pi-nopasswd`
(`tinko ALL=(ALL) NOPASSWD: ALL`): the rules Tinko installs grant
`/usr/sbin/shutdown` and `/usr/bin/systemctl poweroff`, and the code called
neither. Had the OS rule ever been narrowed, the teacher would have seen
"Tinko is shutting down..." forever, the Pi would still be running, and nothing
would have been logged — while the old test, which mocked `Popen`, stayed green.

The halt now lives in a root-owned helper (`scripts/tinko-poweroff`) that the
endpoint runs `--check` against first. These tests hold three lines:

  * the command the view passes to sudo must be one the installer grants —
    read out of `scripts/update_infra.sh`, not restated here, because a
    duplicated list is what let the two drift apart;
  * readiness must be confirmed before anything is spawned, and a refusal must
    reach the teacher instead of looking like a slow shutdown;
  * the halt chain itself must still be the field-verified one.
"""

import os
import subprocess
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INFRA = REPO_ROOT / "scripts" / "update_infra.sh"
HELPER = REPO_ROOT / "scripts" / "tinko-poweroff"
UNINSTALL = REPO_ROOT / "uninstall.sh"

# The halt chain, in order. `shutdown now` is the field-verified primary:
# `systemctl poweroff` silently no-ops on some units, so it is only ever the
# bounded fallback for a halt that stalled.
CHAIN = ["shutdown now", "sleep 60", "systemctl poweroff -f", "sysrq-trigger"]


def granted_commands() -> list[str]:
    """Every command the installers grant with NOPASSWD, as written."""
    out = []
    for line in INFRA.read_text(encoding="utf-8").splitlines():
        if "NOPASSWD:" in line:
            out.append(line.split("NOPASSWD:", 1)[1].strip())
    return out


def fake_subprocess(order, check_returncode=0, check_stderr=""):
    """Stand-ins for `subprocess.run` / `Popen` that record call order."""

    def run(*args, **kwargs):
        order.append(("check", args[0], kwargs))
        return mock.Mock(returncode=check_returncode, stdout="ok", stderr=check_stderr)

    def popen(*args, **kwargs):
        order.append(("halt", args[0], kwargs))
        return mock.Mock()

    return run, popen


@pytest.mark.django_db
def test_readiness_is_confirmed_before_the_halt_is_spawned(client):
    order = []
    run, popen = fake_subprocess(order)

    with mock.patch("core.edupi_core.views.subprocess.run", run), mock.patch(
        "core.edupi_core.views.subprocess.Popen", popen
    ):
        resp = client.post("/power/shutdown/")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    from core.edupi_core.views import POWER_HELPER

    stages = [entry[0] for entry in order]
    assert stages == ["check", "halt"], "the check must run, and run first"

    # The check is the helper's own --check, run under the same grant the halt
    # uses, non-interactively (a password prompt would hang the request).
    assert order[0][1] == ["sudo", "-n", POWER_HELPER, "--check"]
    assert order[0][2]["timeout"] == 10

    # The halt is that same helper and nothing else -- no shell.
    assert order[1][1] == ["sudo", "-n", POWER_HELPER]
    assert order[1][2]["start_new_session"] is True


@pytest.mark.django_db
def test_a_refused_grant_is_reported_and_nothing_is_spawned(client):
    """The failure that used to be invisible: sudo says no, so no shutdown."""
    order = []
    run, popen = fake_subprocess(
        order,
        check_returncode=1,
        check_stderr="sudo: a password is required\n",
    )

    with mock.patch("core.edupi_core.views.subprocess.run", run), mock.patch(
        "core.edupi_core.views.subprocess.Popen", popen
    ), mock.patch("core.edupi_core.views.logger") as logger:
        resp = client.post("/power/shutdown/")

    assert resp.status_code == 500
    assert resp.json()["ok"] is False
    assert [entry[0] for entry in order] == ["check"], "must not spawn the halt"

    # And it must say why somewhere, or the Pi silently keeps running.
    logged = " ".join(str(call) for call in logger.error.call_args_list)
    assert "a password is required" in logged


@pytest.mark.django_db
def test_an_uninstalled_helper_is_reported_not_swallowed(client):
    """Helper missing entirely: `sudo` cannot even be executed."""
    order = []

    def run(*args, **kwargs):
        order.append(args[0])
        raise OSError("sudo not found")

    with mock.patch("core.edupi_core.views.subprocess.run", run), mock.patch(
        "core.edupi_core.views.subprocess.Popen"
    ) as popen, mock.patch("core.edupi_core.views.logger") as logger:
        resp = client.post("/power/shutdown/")

    assert resp.status_code == 500
    assert resp.json()["ok"] is False
    popen.assert_not_called()
    assert logger.error.called


@pytest.mark.django_db
def test_only_post_can_shut_the_pi_down(client):
    with mock.patch("core.edupi_core.views.subprocess.run") as run:
        resp = client.get("/power/shutdown/")

    assert resp.status_code == 405
    run.assert_not_called()


def test_the_halt_command_is_granted_by_the_sudoers_file_tinko_installs():
    """The cross-check the old test only claimed in its docstring.

    Every command the endpoint passes to sudo must appear in what
    `scripts/update_infra.sh` grants, read from the file rather than restated,
    so code and sudoers cannot drift apart again.
    """
    from core.edupi_core.views import POWER_HELPER

    granted = granted_commands()
    # "" is the sudoers idiom for "no arguments": the real halt cannot be
    # dressed up with any, and --check is the only argument allowed.
    assert f'{POWER_HELPER} ""' in granted
    assert f"{POWER_HELPER} --check" in granted

    # The granted path is written out literally (twice above), so it can be
    # read and audited; this pins it to where the helper is actually installed.
    text = INFRA.read_text(encoding="utf-8")
    assert f'helper_dst="{POWER_HELPER}"' in text, "grant and install path drifted"


def test_nothing_grants_the_app_a_shell_or_the_dead_shutdown_commands():
    """Granting `bash` is what the old code depended on; the two shutdown
    commands it listed were never called by anything."""
    granted = granted_commands()

    shells = [c for c in granted if c.split()[0].rsplit("/", 1)[-1] in {"bash", "sh"}]
    assert shells == [], f"these grants hand out a root shell: {shells}"

    assert not [c for c in granted if "systemctl poweroff" in c]
    assert not [c for c in granted if c.startswith("/usr/sbin/shutdown")]
    # `shutdown -r now` is a reboot the app has no business having.
    assert not [c for c in granted if "shutdown" in c and "tinko-poweroff" not in c]


def test_the_helper_keeps_the_field_verified_halt_chain():
    text = HELPER.read_text(encoding="utf-8")

    for step in CHAIN:
        assert step in text, f"{step!r} is missing from the helper"

    # Order matters: the fallbacks only make sense after `shutdown now`.
    # Matched on the whole line, because `sysrq-trigger` is also named in the
    # --check block and a bare substring would match that one first.
    steps = ["shutdown now", "sleep 60", "systemctl poweroff -f",
             "echo o > /proc/sysrq-trigger"]
    positions = [text.index(step) for step in steps]
    assert positions == sorted(positions), "the halt chain is out of order"


def test_the_helper_refuses_to_run_unprivileged_and_check_never_halts():
    text = HELPER.read_text(encoding="utf-8")

    # A non-root guard before the halt, and --check exits before reaching it.
    assert 'id -u' in text
    assert text.index("id -u") < text.index("shutdown now")
    check_block = text.index('"${1:-}" = "--check"')
    assert check_block < text.index("shutdown now")
    assert "exit 0" in text[check_block : text.index("shutdown now")]


def test_the_helper_is_installed_root_owned_and_validated_first():
    text = INFRA.read_text(encoding="utf-8")

    # Root-owned and mode 0755: the app user must not be able to rewrite the
    # file that a root rule executes.
    assert "install -o root -g root -m 0755" in text
    assert "install -o root -g root -m 0440" in text

    # A malformed sudoers.d file makes sudo refuse EVERY command for that user,
    # so it is parsed before it is installed.
    assert "visudo -cf" in text
    assert text.index("visudo -cf") < text.index('install -o root -g root -m 0440')


def test_uninstall_removes_the_helper_and_its_grant():
    text = UNINSTALL.read_text(encoding="utf-8")

    assert "/usr/local/sbin/tinko-poweroff" in text
    assert "/etc/sudoers.d/tinko-poweroff" in text


# --- the installer, run for real -------------------------------------------
#
# The tests above read text; these run install_power_helper() itself with `sudo`
# stubbed, so the grant that reaches the Pi is checked as produced rather than
# as written. The distinction matters twice over: the rule is built from a shell
# variable, and the service user has to survive a run under root (update-web.sh
# runs from the root daemon, where $USER is `root` — a grant written for root
# would leave the app unable to press its own button).

def msys_path(path: Path) -> str:
    """A path bash can put on ``PATH``.

    Git Bash converts the PATH it is *started* with, but not one assigned inside
    a script — a ``C:/Users/...`` entry is read as the path ``C`` followed by
    ``/Users/...``, and the directory is silently never searched.
    """
    posix = path.as_posix()
    if len(posix) > 1 and posix[1] == ":":
        return "/" + posix[0].lower() + posix[2:]
    return posix


def run_install_helper(tmp_path, svc_user="tinko", visudo_fails=False, user="root"):
    """Run the shipped install_power_helper() and return (output, sudo, log)."""
    text = INFRA.read_text(encoding="utf-8")
    marker = "install_power_helper() {"
    assert marker in text, "install_power_helper() has been renamed"
    start = text.index(marker)
    function = text[start : text.index("\n}", start) + len("\n}")]

    # The function skips validation when `visudo` is not on PATH (a warning, not
    # a failure), so a stub must exist for the guard to be exercised at all.
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    visudo = bin_dir / "visudo"
    visudo.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    visudo.chmod(0o755)
    subprocess.run(["bash", "-c", f'chmod 755 "{msys_path(visudo)}"'], capture_output=True)

    sudoers = tmp_path / "sudoers.txt"
    log = tmp_path / "sudo.log"
    harness = tmp_path / "harness.sh"
    harness.write_text(
        "\n".join(
            [
                "log_info(){ echo \"INFO: $*\"; }",
                "log_success(){ echo \"SUCCESS: $*\"; }",
                "log_warning(){ echo \"WARNING: $*\"; }",
                "log_error(){ echo \"ERROR: $*\"; }",
                f'export PATH="{msys_path(bin_dir)}:$PATH"',
                f'INSTALL_DIR="{REPO_ROOT.as_posix()}"',
                f'OUTDIR="{tmp_path.as_posix()}"',
                f'VISUDO_FAILS="{1 if visudo_fails else 0}"',
                # A `sudo` on PATH cannot stand in: the function calls `sudo`
                # by name, so a shell function is what it finds.
                "sudo(){",
                '    if [ "$1" = "install" ]; then',
                "        shift",
                '        echo "INSTALL $*" >> "' + log.name + '"',
                '        prev=""; last=""',
                '        for a in "$@"; do prev="$last"; last="$a"; done',
                '        if [ "$last" = "/etc/sudoers.d/tinko-poweroff" ]; then',
                '            cp "$prev" "' + sudoers.name + '"',
                "        fi",
                "        return 0",
                "    fi",
                '    if [ "$1" = "visudo" ]; then',
                '        if [ "$VISUDO_FAILS" = "1" ]; then',
                '            echo "syntax error" >&2; return 1',
                "        fi",
                '        echo "parsed OK"; return 0',
                "    fi",
                '    echo "UNEXPECTED sudo $*" >&2; return 1',
                "}",
                function,
                f'install_power_helper "{svc_user}"',
                'echo "rc=$?"',
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", harness.name],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env={**os.environ, "USER": user},
    )
    return result.stdout + result.stderr, sudoers, log


def test_the_installer_grants_the_service_user_and_installs_it_root_owned(tmp_path):
    out, sudoers, log = run_install_helper(tmp_path)

    assert "rc=0" in out, out
    assert "SUCCESS" in out

    # The helper lands root-owned and only root can rewrite it.
    assert "INSTALL -o root -g root -m 0755" in log.read_text(encoding="utf-8")
    assert "scripts/tinko-poweroff /usr/local/sbin/tinko-poweroff" in (
        log.read_text(encoding="utf-8")
    )

    written = sudoers.read_text(encoding="utf-8")
    assert 'tinko ALL=(ALL) NOPASSWD: /usr/local/sbin/tinko-poweroff ""' in written
    assert "tinko ALL=(ALL) NOPASSWD: /usr/local/sbin/tinko-poweroff --check" in written
    # No unexpanded shell variable survived into the installed file, and the
    # root daemon's own $USER did not leak into the grant.
    assert "$" not in written
    assert "root ALL" not in written


def test_an_invalid_rule_is_refused_before_it_is_installed(tmp_path):
    """sudo refuses every command for a user with a malformed sudoers file, so
    the update system's own rules would go down with it."""
    out, sudoers, log = run_install_helper(tmp_path, visudo_fails=True)

    assert "rc=1" in out, out
    assert "ERROR" in out
    assert "syntax error" in out, "visudo's own message must reach the log"
    assert not sudoers.exists(), "the rule was installed anyway"
    assert "0440" not in log.read_text(encoding="utf-8")
