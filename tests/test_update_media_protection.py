"""Tests for the update scripts' uploaded-files protection.

The school logo is uploaded from the settings page, so it is written by the
running app and is always dirty when an update runs. It used to be tracked in
git, which meant ``pull_latest`` stashed the teacher's upload and the merge
checked the committed copy back out over it — the logo the school had chosen
was replaced by whatever had last been committed. ``media/`` is being untracked
for the same reason ``db.sqlite3`` was, and the protection below is what makes
that safe: the commit that untracks the files makes the merge *delete* them from
the working tree, so ``hide_media`` moves them out of the tree before the pull
and ``restore_media`` moves them back on every path.

The tests run the real function bodies, extracted from the shipped scripts,
against a real git repository — so a refactor that drops the restore call, or
one that starts moving generated audio around, fails here instead of on a field
Pi.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ["update.sh", "update-web.sh"]

# The block is delimited by this marker; if it moves, the extraction fails
# loudly rather than silently testing nothing.
BLOCK_START = "# --- Uploaded files protection"
LAST_FN = "restore_media"

# A stand-in for the uploaded logo: the only kind of file that is tracked under
# media/ and therefore the only kind the guard has any business moving.
LOGO = "media/site/logos/logo.png"
# Generated audio: never tracked, so it must be left exactly where it is.
GENERATED = "media/routines/tts_cache/hello.mp3"


def extract_block(script: str) -> str:
    """Return the uploaded-files-protection section of *script*.

    Runs from the section marker to the closing brace of the last helper.
    """
    text = (REPO_ROOT / script).read_text(encoding="utf-8")
    assert BLOCK_START in text, (
        f"{script} has no '{BLOCK_START}' block. The update scripts must move the "
        "uploaded files out of the tree before the pull and back after it."
    )
    start = text.index(BLOCK_START)
    fn_start = text.index(f"{LAST_FN}() {{", start)
    block = text[start : text.index("\n}", fn_start) + len("\n}")]

    for fn in ("hide_media", "recover_orphaned_media", "media_tracked_files", LAST_FN):
        assert f"{fn}()" in block, f"{script}: {fn} is missing from the block"
    return block


def git(*args, cwd):
    result = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )
    assert result.returncode == 0, f"git {' '.join(args)} failed:\n{result.stderr}"
    return result.stdout


def make_repo(tmp_path, tracked=(LOGO,), generated=(GENERATED,)):
    """A real repository with *tracked* committed and *generated* ignored."""
    git("init", "-q", cwd=tmp_path)
    (tmp_path / ".gitignore").write_text("media/\n!media/site/logos/logo.png\n")
    for rel in tracked:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("UPLOADED")
    # -f: media/ is ignored, and a file cannot be re-included once its parent
    # directory is excluded — the whole point is that git still has this file.
    if tracked:
        git("add", "-f", *tracked, cwd=tmp_path)
    for rel in generated:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("GENERATED")


def run_scenario(tmp_path, body: str, script: str = "update.sh") -> str:
    """Run *body* in a shell with the real helpers loaded; return its output."""
    harness = tmp_path / "harness.sh"
    harness.write_text(
        "\n".join(
            [
                "log_info(){ :; }",
                "log_warning(){ :; }",
                "log_error(){ echo \"ERROR: $*\" >&2; }",
                "log_success(){ :; }",
                # update-web.sh routes git through this; running it directly is
                # the same thing the script does once sudo -u has done its part.
                'run_as_user(){ bash -c "$1"; }',
                f'INSTALL_DIR="{tmp_path.as_posix()}"',
                extract_block(script),
                body,
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["bash", str(harness)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert result.returncode == 0, f"scenario failed:\n{result.stderr}"
    return result.stdout


@pytest.mark.parametrize("script", SCRIPTS)
def test_both_update_scripts_hide_and_restore(script):
    """Both entry points guard the uploads, not just the CLI one."""
    block = extract_block(script)

    assert "MEDIA_SAVED_PATHS" in block
    assert "mv" in block, "the guard must move the file, not copy it"
    # The restore must be a call site in pull_latest, not only a definition.
    text = (REPO_ROOT / script).read_text(encoding="utf-8")
    assert text.count("restore_media") >= 2, (
        f"{script} defines restore_media but never calls it — the uploads would "
        "be moved aside and left there"
    )
    assert text.count("hide_media") >= 2, (
        f"{script} defines hide_media but never calls it — the merge would "
        "still overwrite the teacher's logo"
    )


@pytest.mark.parametrize("script", SCRIPTS)
def test_hide_takes_the_tracked_logo_out_of_the_tree(tmp_path, script):
    """After hide_media, git can stash or merge without touching the logo."""
    make_repo(tmp_path)
    out = run_scenario(
        tmp_path,
        f'hide_media\n'
        f'[[ -e "$INSTALL_DIR/{LOGO}" ]] && echo "STILL-PRESENT" || echo "ABSENT"\n'
        f'find "$INSTALL_DIR/media" -name "*.update-tmp-*" | sort\n',
        script=script,
    )

    assert "ABSENT" in out, "the tracked logo must leave the working tree"
    assert "logo.png.update-tmp-" in out, "the saved copy must be findable"


def test_generated_audio_is_left_alone(tmp_path):
    """Only what git tracks is moved: generated audio is not at risk, and
    copying a lesson's worth of it on every update would be waste."""
    make_repo(tmp_path)
    out = run_scenario(
        tmp_path,
        'hide_media\n'
        f'[[ -e "$INSTALL_DIR/{GENERATED}" ]] && echo "GENERATED-INTACT"\n'
        f'[[ -e "$INSTALL_DIR/{LOGO}" ]] && echo "TRACKED-STILL-THERE"\n'
        'echo "saved=${#MEDIA_SAVED_PATHS[@]}"\n',
    )

    assert "GENERATED-INTACT" in out, "untracked media must not be moved away"
    assert "TRACKED-STILL-THERE" not in out
    assert "saved=1" in out, "exactly the tracked file is guarded"


@pytest.mark.parametrize("script", SCRIPTS)
def test_restore_wins_over_whatever_the_pull_left(tmp_path, script):
    """The uploaded logo beats the committed copy the merge checked out."""
    make_repo(tmp_path)
    out = run_scenario(
        tmp_path,
        'hide_media\n'
        # simulate the merge writing the committed copy back into the tree
        f'echo "COMMITTED" > "$INSTALL_DIR/{LOGO}"\n'
        'restore_media\n'
        f'cat "$INSTALL_DIR/{LOGO}"\n'
        f'find "$INSTALL_DIR/media" -name "*.update-tmp-*" | sort\n',
        script=script,
    )

    assert "UPLOADED" in out, "the school's upload must be restored"
    assert "COMMITTED" not in out, "the committed copy must not survive"
    assert "update-tmp-" not in out, "no leftovers after a restore"


def test_restore_also_wins_on_the_failed_pull_path(tmp_path):
    """A stash pop on the failure path must not resurrect the committed logo."""
    make_repo(tmp_path)
    out = run_scenario(
        tmp_path,
        'hide_media\n'
        # simulate `git stash pop` restoring the captured copy
        f'echo "STASHCOPY" > "$INSTALL_DIR/{LOGO}"\n'
        'restore_media\n'
        f'cat "$INSTALL_DIR/{LOGO}"\n',
    )

    assert "UPLOADED" in out, "the upload must win on both paths"
    assert "STASHCOPY" not in out


def test_the_guard_is_a_no_op_once_nothing_is_tracked(tmp_path):
    """After the untracking commit there is nothing to do — every later
    update must run through this without touching anything."""
    make_repo(tmp_path, tracked=(), generated=(GENERATED,))
    out = run_scenario(
        tmp_path,
        'hide_media\n'
        'restore_media\n'
        'echo "saved=${#MEDIA_SAVED_PATHS[@]}"\n'
        f'cat "$INSTALL_DIR/{GENERATED}"\n',
    )

    assert "saved=0" in out
    assert "GENERATED" in out, "untracked media must survive an update untouched"
    assert "ERROR" not in out, "an untracked media/ is not an error"


def test_no_media_directory_at_all_is_not_an_error(tmp_path):
    """A fresh install has no media/ until the first upload."""
    make_repo(tmp_path, tracked=(), generated=())
    out = run_scenario(
        tmp_path,
        'hide_media\n'
        'recover_orphaned_media\n'
        'restore_media\n'
        'echo "saved=${#MEDIA_SAVED_PATHS[@]}"\n',
    )

    assert "saved=0" in out
    assert "ERROR" not in out


def test_orphaned_upload_is_recovered_not_lost(tmp_path):
    """An update that died mid-pull must not strand the logo."""
    make_repo(tmp_path)
    (tmp_path / f"{LOGO}.update-tmp-9999").write_text("ORPHAN")
    (tmp_path / LOGO).unlink()
    out = run_scenario(
        tmp_path,
        'recover_orphaned_media\n'
        f'cat "$INSTALL_DIR/{LOGO}"\n',
    )

    assert "ORPHAN" in out, "the upload left aside must come back"


def test_orphan_recovery_never_deletes_a_live_upload(tmp_path):
    """Both copies present: keep both rather than guess which is real."""
    make_repo(tmp_path)
    (tmp_path / f"{LOGO}.update-tmp-9999").write_text("ORPHAN")
    out = run_scenario(
        tmp_path,
        'recover_orphaned_media\n'
        f'cat "$INSTALL_DIR/{LOGO}"\n'
        f'cat "$INSTALL_DIR/{LOGO}.update-tmp-9999.recovered"\n',
    )

    assert "UPLOADED" in out, "the live upload must be left alone"
    assert "ORPHAN" in out, "the leftover must be kept, not deleted"


def test_media_is_not_tracked_by_git():
    """The whole point: an update must not manage the uploads via git."""
    tracked = git("ls-files", "media", cwd=REPO_ROOT).split()
    if tracked:
        pytest.skip(
            "media/ is still tracked. Untracking it is a deliberate two-step "
            "order: the protection above must be RUNNING on the Pi first, "
            "because the commit that untracks the files makes the merge delete "
            "them from the working tree. Files still tracked: " + ", ".join(tracked)
        )
