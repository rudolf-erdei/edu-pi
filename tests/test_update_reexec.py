"""Tests for the update scripts' self-update guard.

bash reads a running script from its open file descriptor, and `git pull`
replaces files by atomic rename (new inode), so an in-flight run keeps executing
the PRE-pull function bodies. `reexec_if_self_changed()` exists for that: digests
recorded at startup, re-exec once after the pull if they moved.

The guard used to watch only the running script, which left the same staleness
one layer deeper. `scripts/update_infra.sh` is `source`d — parsed into functions
— before the pull, so a pull that changes a helper in it leaves the run calling
the OLD body. Observed on the field Pi 2026-09-26: the pull landed
`install_power_helper()` and the new power-button sudoers rule at 18:12:15, the
run then called the *old* `setup_update_infrastructure()` and rewrote
`/etc/sudoers.d/tinko-update` with the pre-fix contents at 18:12:31, and the
update reported success. `update.sh` itself had not changed (mtime 18:00), so the
one-file digest matched and nothing re-executed.

These tests run the shipped guard block itself, with the harness standing in for
the script: it is written to a file, `$0` is that file, and a simulated pull
edits the tree before the guard is called. A re-exec re-runs the harness, which
is how the second run is observed.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ["update.sh", "update-web.sh"]
INFRA_REL = "scripts/update_infra.sh"

# The guard block: from the digest bookkeeping through reexec_if_self_changed().
GUARD_START = 'SCRIPT_PATH="$(readlink -f'
GUARD_END_FN = "reexec_if_self_changed() {"


def msys_path(path: Path) -> str:
    """A path bash can use verbatim (Git Bash splits ``C:/...`` at the colon)."""
    posix = path.as_posix()
    if len(posix) > 1 and posix[1] == ":":
        return "/" + posix[0].lower() + posix[2:]
    return posix


def script_text(script: str) -> str:
    return (REPO_ROOT / script).read_text(encoding="utf-8")


def extract_guard(script: str) -> str:
    """The shipped guard block, exactly as the script has it."""
    text = script_text(script)
    start = text.index(GUARD_START)
    end = text.index(GUARD_END_FN, start)
    return text[start : text.index("\n}", end) + len("\n}")]


def run_guard(
    tmp_path: Path,
    script: str,
    change: str = "none",
    create_infra: bool = True,
    reexec_env: bool = False,
) -> str:
    """Run the real guard with a simulated pull, and return everything printed.

    *change* is what the simulated pull does: ``none``, ``infra`` (edit the
    sourced helper file), or ``script`` (edit the running script — appended only
    after bash has parsed it, which is what a rename-swap looks like).
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    infra = tmp_path / INFRA_REL
    if create_infra:
        infra.parent.mkdir(parents=True, exist_ok=True)
        infra.write_text("install_power_helper() { :; }\n", encoding="utf-8")

    # The `.pulled` marker keeps the simulated pull to the first run only, so a
    # re-executed run has nothing left to change and cannot loop.
    pull = {
        "none": ":",
        "infra": f'printf "# pulled change\\n" >> "{msys_path(infra)}"',
        "script": 'printf "\\n# pulled change\\n" >> "$0"',
    }[change]

    # Named after the shipped script it stands in for, so the guard's own log
    # line ("Replaced by the pull: <path>") is the real filename in the output.
    harness = tmp_path / script
    harness.write_text(
        "\n".join(
            [
                "#!/bin/bash",
                'log_warning(){ echo "WARNING: $*"; }',
                'log_info(){ echo "INFO: $*"; }',
                'log_error(){ echo "ERROR: $*"; }',
                f'INSTALL_DIR="{msys_path(tmp_path)}"',
                # A fresh PATH: the digest helpers must be the system ones.
                'export PATH="/usr/bin:/bin:$PATH"',
                'echo "RUN-START"',
                extract_guard(script),
                f'if [ ! -f "{msys_path(tmp_path)}/.pulled" ]; then',
                f'    touch "{msys_path(tmp_path)}/.pulled"',
                f"    {pull}",
                "fi",
                "reexec_if_self_changed",
                'echo "RUN-END"',
            ]
        ),
        encoding="utf-8",
    )

    env = {"PATH": "/usr/bin:/bin", "HOME": str(tmp_path)}
    env["TINKO_UPDATE_REEXEC"] = "1" if reexec_env else "0"
    result = subprocess.run(
        ["bash", harness.name],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )
    return result.stdout + result.stderr


@pytest.mark.parametrize("script", SCRIPTS)
def test_the_guard_watches_the_sourced_infra_file(script):
    """The gap that cost the field Pi an update: the sourced file was not
    watched, so a helper change waited for the next run."""
    guard = extract_guard(script)

    assert 'WATCHED_FILES=("$SCRIPT_PATH" "$INSTALL_DIR/scripts/update_infra.sh")' in guard
    # Its digest is recorded, not just its name.
    assert 'WATCHED_DIGESTS_AT_START+=("$(script_digest "$_watched" || true)")' in guard


@pytest.mark.parametrize("script", SCRIPTS)
def test_the_guard_still_re_execs_when_the_script_itself_moved(script):
    """The original behaviour, kept: the running script is watched too."""
    assert 'WATCHED_FILES=("$SCRIPT_PATH"' in extract_guard(script)


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_pull_that_changes_the_sourced_helper_re_execs(tmp_path, script):
    out = run_guard(tmp_path, script, change="infra")

    assert out.count("RUN-START") == 2, out
    assert "RUN-END" in out
    # The log names the file that moved instead of asserting it was the script.
    assert "update_infra.sh" in out
    assert "Replaced by the pull" in out


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_pull_that_changes_nothing_does_not_re_exec(tmp_path, script):
    out = run_guard(tmp_path, script, change="none")

    assert out.count("RUN-START") == 1, out
    assert "Replaced by the pull" not in out


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_pull_that_changes_the_script_itself_still_re_execs(tmp_path, script):
    out = run_guard(tmp_path, script, change="script")

    assert out.count("RUN-START") == 2, out
    assert script in out


@pytest.mark.parametrize("script", SCRIPTS)
def test_an_already_re_executed_run_never_re_execs_again(tmp_path, script):
    """A script that keeps changing must not loop."""
    out = run_guard(tmp_path, script, change="infra", reexec_env=True)

    assert out.count("RUN-START") == 1, out
    assert "Replaced by the pull" not in out


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_missing_infra_file_is_not_a_change(tmp_path, script):
    """An install without the file (or a pull that deleted it) must not
    re-exec on a digest that was never readable."""
    out = run_guard(tmp_path, script, change="none", create_infra=False)

    assert "RUN-END" in out
    assert "Replaced by the pull" not in out


@pytest.mark.parametrize("script", SCRIPTS)
def test_the_guard_is_called_after_the_pull_and_before_the_stages_it_protects(script):
    """Order is the whole point: a guard that runs before the pull, or after the
    stages it is meant to protect, protects nothing."""
    text = script_text(script)
    main = text.index("\nmain() {")

    pull = text.index("pull_latest\n", main)
    guard = text.index("reexec_if_self_changed\n", main)
    first_stage = text.index("update_dependencies\n", main)

    assert pull < guard < first_stage
