"""Tests for what the update scripts do and say around `git pull`.

Two defects lived in these few lines. The command itself was wrong — `timeout
60 GIT_TERMINAL_PROMPT=0 git pull` makes `timeout` exec a program named
`GIT_TERMINAL_PROMPT=0`, so the web pull never ran — and every failure, whatever
its cause, was reported as *"no internet or network error"*. The second is what
kept the first alive: a loud, diagnosable error read as a network problem and
the update carried on with the old code.

The functions below are extracted from the shipped scripts and run against real
git repositories, so a change that puts the guessing message back, or that lets
untracked files decide whether to stash, fails here.

The pull runs under `timeout`, which is an external program and so cannot see a
shell function — the stub has to be a `git` on `PATH` instead.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ["update.sh", "update-web.sh"]
REAL_GIT = shutil.which("git")

# What every failure used to be called, whatever actually happened.
GUESS = "(no internet or network error)"

# Stands in for what git prints when the credentials are wrong — the failure that
# the guessed message mislabelled as a network problem.
AUTH_FAILURE = "fatal: Authentication failed for 'https://example.invalid/x.git/'"

STUB = """#!/usr/bin/env bash
case "$1" in
    status|stash) exec "{real_git}" "$@" ;;
    log) exit 0 ;;
    *) echo "{message}" >&2; exit {code} ;;
esac
"""


def msys_path(path: Path) -> str:
    """A path bash can put on ``PATH``.

    Git Bash converts the PATH it is *started* with, but not one assigned inside
    a script — so a prefix of ``C:/Users/...`` is read as the path ``C`` followed
    by ``/Users/...``, and the stub directory is silently never searched.
    """
    posix = path.as_posix()
    if len(posix) > 1 and posix[1] == ":":
        return "/" + posix[0].lower() + posix[2:]
    return posix


def write_git_stub(tmp_path: Path, message: str = AUTH_FAILURE, code: int = 128) -> Path:
    """Put a `git` on PATH that fails the pull but is real for status/stash."""
    bin_dir = tmp_path / "stub-bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "git"
    stub.write_text(
        STUB.format(real_git=msys_path(Path(REAL_GIT)), message=message, code=code),
        encoding="utf-8",
    )
    stub.chmod(0o755)
    subprocess.run(
        ["bash", "-c", f'chmod 755 "{msys_path(stub)}"'], capture_output=True
    )
    return bin_dir


def extract_function(script: str, name: str) -> str:
    """Return *name*'s whole definition, closing brace included."""
    text = (REPO_ROOT / script).read_text(encoding="utf-8")
    marker = f"{name}() {{"
    assert marker in text, f"{script} has no {name}()"
    start = text.index(marker)
    return text[start : text.index("\n}", start) + len("\n}")]


def run_pull(tmp_path: Path, script: str, git_stub: Path) -> str:
    """Run the real ``pull_latest`` from *script* with helpers stubbed out."""
    lines = [
        # Logging echoes instead of writing a log file, so the output can be read.
        'log_info(){ echo "INFO: $*"; }',
        'log_warning(){ echo "WARNING: $*"; }',
        'log_error(){ echo "ERROR: $*" >&2; }',
        'log_success(){ echo "SUCCESS: $*"; }',
        "update_status(){ :; }",
        # The database and upload guards have their own test files.
        "recover_orphaned_db(){ :; }",
        "recover_orphaned_media(){ :; }",
        "hide_live_db(){ :; }",
        "restore_live_db(){ :; }",
        "hide_media(){ :; }",
        "restore_media(){ :; }",
        f'INSTALL_DIR="{tmp_path.as_posix()}"',
        f'export PATH="{msys_path(git_stub)}:$PATH"',
        "export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.invalid",
        "export GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.invalid",
    ]
    if script == "update-web.sh":
        # The web script reaches git through sudo; run the command directly so the
        # stub on PATH is the git it finds.
        lines.append('run_as_user(){ bash -c "$1"; }')
    lines.append(extract_function(script, "pull_latest"))
    lines.append("pull_latest")

    harness = tmp_path / "pull_harness.sh"
    harness.write_text("\n".join(lines), encoding="utf-8")
    result = subprocess.run(
        ["bash", str(harness)], capture_output=True, text=True, cwd=str(tmp_path)
    )
    return result.stdout + result.stderr


def init_repo(tmp_path: Path) -> None:
    """A real repository, so `git status` and `git stash` are the real thing."""
    subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_failed_pull_reports_what_git_actually_said(tmp_path, script):
    """The real reason reaches the log, not a guess about the network."""
    out = run_pull(tmp_path, script, write_git_stub(tmp_path))

    assert "Authentication failed" in out, (
        f"{script} swallowed git's own error. The log must carry the reason, "
        "because on a Pi nobody can log in to, that line is the whole diagnosis."
    )
    assert GUESS not in out, (
        f"{script} still reports a failed pull as '{GUESS}' regardless of cause"
    )


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_timed_out_pull_is_named_as_a_timeout(tmp_path, script):
    """Exit 124 has to read as a timeout — the output alone will not say so."""
    stub = write_git_stub(tmp_path, message="", code=124)
    out = run_pull(tmp_path, script, stub)

    assert "60 seconds" in out, f"{script} does not mention the 60 s timeout"
    assert GUESS not in out


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_successful_pull_is_still_reported_as_success(tmp_path, script):
    """Capturing the output must not turn a good pull into a silent one."""
    stub = write_git_stub(tmp_path, message="", code=0)
    out = run_pull(tmp_path, script, stub)

    assert "SUCCESS" in out
    assert "WARNING" not in out, f"{script} warns about a pull that worked"


@pytest.mark.parametrize("script", SCRIPTS)
def test_untracked_files_alone_do_not_announce_local_changes(tmp_path, script):
    """`git stash` ignores untracked files, so this must not depend on them.

    The field Pi always has some (`?? .env`, `?? staticfiles/`), so the old
    condition entered the stash branch on every run and logged "Local changes
    detected" over a tree with nothing to stash.
    """
    init_repo(tmp_path)
    (tmp_path / ".env").write_text("SECRET=1")

    out = run_pull(tmp_path, script, write_git_stub(tmp_path))

    assert "Local changes detected" not in out, (
        f"{script} treats untracked files as local changes worth stashing"
    )
    listed = subprocess.run(
        ["git", "stash", "list"], capture_output=True, text=True, cwd=str(tmp_path)
    )
    assert listed.stdout.strip() == "", "a stash was created with nothing to save"


@pytest.mark.parametrize("script", SCRIPTS)
def test_a_tracked_modification_still_stashes(tmp_path, script):
    """The guard that remains must still fire — a merge over real edits loses them."""
    init_repo(tmp_path)
    tracked = tmp_path / "settings.py"
    tracked.write_text("ORIGINAL")
    subprocess.run(["git", "add", "settings.py"], cwd=str(tmp_path), check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "-m",
            "init",
        ],
        cwd=str(tmp_path),
        check=True,
    )
    tracked.write_text("EDITED")

    out = run_pull(tmp_path, script, write_git_stub(tmp_path))

    assert "Local changes detected" in out, (
        f"{script} no longer stashes a modified tracked file"
    )


@pytest.mark.parametrize("script", SCRIPTS)
def test_the_scripts_carry_no_guessed_failure_message(script):
    """Guard the wording itself, comments excluded."""
    text = (REPO_ROOT / script).read_text(encoding="utf-8")
    code = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )

    assert GUESS not in code, f"{script} reports every failed pull as '{GUESS}'"
    assert "--untracked-files=no" in code, (
        f"{script} decides whether to stash from `git status --porcelain`, which "
        "counts untracked files that git stash will never touch"
    )
