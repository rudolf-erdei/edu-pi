"""Tests for the update scripts' live-database protection.

``db.sqlite3`` is written by the running app, so it is always dirty when an
update runs. ``pull_latest`` used to let ``git stash`` capture it and only
popped the stash when the pull *failed* — so a successful update silently
swapped the teacher's data for the committed copy. Both scripts now move the
database out of the working tree before the stash (``hide_live_db``) and move
it back on every path (``restore_live_db``).

This is the safety net that makes untracking the database possible at all: the
commit that removes it from the index also makes the merge delete it from the
working tree, and with no protection that deletes live data and leaves Django
with no database. The tests below run the real function bodies, extracted from
the shipped scripts, against real files — so a refactor that quietly drops the
restore call fails here instead of on a field Pi.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ["update.sh", "update-web.sh"]

# The block is delimited by this marker; if it moves, the extraction fails
# loudly rather than silently testing nothing.
BLOCK_START = "# --- Live database protection"
LAST_FN = "restore_live_db"


def extract_block(script: str) -> str:
    """Return the live-database-protection section of *script*.

    Runs from the section marker to the closing brace of the last helper.
    """
    text = (REPO_ROOT / script).read_text(encoding="utf-8")
    assert BLOCK_START in text, (
        f"{script} has no '{BLOCK_START}' block. The update scripts must hide the "
        "live database before the stash and restore it after the pull."
    )
    start = text.index(BLOCK_START)
    fn_start = text.index(f"{LAST_FN}() {{", start)
    block = text[start : text.index("\n}", fn_start) + len("\n}")]

    for fn in ("hide_live_db", "recover_orphaned_db", LAST_FN):
        assert f"{fn}()" in block, f"{script}: {fn} is missing from the block"
    return block


def run_scenario(tmp_path, body: str) -> str:
    """Run *body* in a shell with the real helpers loaded; return its output."""
    harness = tmp_path / "harness.sh"
    harness.write_text(
        "\n".join(
            [
                "log_info(){ :; }",
                "log_warning(){ :; }",
                "log_error(){ echo \"ERROR: $*\" >&2; }",
                "log_success(){ :; }",
                f'INSTALL_DIR="{tmp_path.as_posix()}"',
                extract_block("update.sh"),
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
    """Both entry points guard the database, not just the CLI one."""
    block = extract_block(script)

    assert "DB_SAVED_PATHS" in block
    assert "mv" in block, "the guard must move the file, not copy it"
    # The restore must be a call site in pull_latest, not only a definition.
    text = (REPO_ROOT / script).read_text(encoding="utf-8")
    assert text.count("restore_live_db") >= 2, (
        f"{script} defines restore_live_db but never calls it — the database "
        "would be moved aside and left there"
    )


def test_hide_moves_the_database_out_of_the_tree(tmp_path):
    """After hide_live_db, git can stash or merge without touching the DB."""
    (tmp_path / "db.sqlite3").write_text("LIVEDB")
    out = run_scenario(
        tmp_path,
        'hide_live_db\n'
        '[[ -f "$INSTALL_DIR/db.sqlite3" ]] && echo "STILL-PRESENT" || echo "ABSENT"\n'
        'ls "$INSTALL_DIR"\n',
    )

    assert "ABSENT" in out, "db.sqlite3 must leave the working tree"
    assert "db.sqlite3.update-tmp-" in out, "the saved copy must be findable"


def test_restore_wins_over_whatever_the_pull_left(tmp_path):
    """The live database beats the committed copy the merge checked out."""
    (tmp_path / "db.sqlite3").write_text("LIVEDB")
    out = run_scenario(
        tmp_path,
        'hide_live_db\n'
        # simulate the merge writing the committed copy back into the tree
        'echo "COMMITTED" > "$INSTALL_DIR/db.sqlite3"\n'
        'restore_live_db\n'
        'cat "$INSTALL_DIR/db.sqlite3"\n'
        'ls "$INSTALL_DIR"\n',
    )

    assert "LIVEDB" in out, "the live database must be restored"
    assert "COMMITTED" not in out, "the committed copy must not survive"
    assert "update-tmp-" not in out, "no leftovers after a restore"


def test_restore_also_wins_on_the_failed_pull_path(tmp_path):
    """A stash pop on the failure path must not resurrect the old database."""
    (tmp_path / "db.sqlite3").write_text("LIVEDB")
    out = run_scenario(
        tmp_path,
        'hide_live_db\n'
        # simulate `git stash pop` restoring the captured copy
        'echo "STASHCOPY" > "$INSTALL_DIR/db.sqlite3"\n'
        'restore_live_db\n'
        'cat "$INSTALL_DIR/db.sqlite3"\n',
    )

    assert "LIVEDB" in out, "the live database must win on both paths"
    assert "STASHCOPY" not in out


def test_hide_and_restore_are_no_ops_without_a_database(tmp_path):
    """A fresh install with no database yet must not be broken by the guard."""
    out = run_scenario(
        tmp_path,
        'hide_live_db\n'
        'restore_live_db\n'
        'echo "saved=[${DB_SAVED_PATHS[*]}]"\n',
    )

    assert "saved=[]" in out
    assert "ERROR" not in out, "a missing database is not an error"


def test_the_write_ahead_log_goes_with_the_database(tmp_path):
    """SQLite's WAL is the database, half-written.

    A db.sqlite3-wal left in the tree while its database is moved aside
    describes a state that no longer exists, and SQLite replays what it finds —
    so the log and the index have to travel with the file they belong to.
    """
    (tmp_path / "db.sqlite3").write_text("LIVEDB")
    (tmp_path / "db.sqlite3-wal").write_text("WAL")
    (tmp_path / "db.sqlite3-shm").write_text("SHM")
    out = run_scenario(
        tmp_path,
        'hide_live_db\n'
        'for f in db.sqlite3 db.sqlite3-wal db.sqlite3-shm; do\n'
        '    [[ -e "$INSTALL_DIR/$f" ]] && echo "PRESENT $f" || echo "HIDDEN $f"\n'
        'done\n'
        'restore_live_db\n'
        'for f in db.sqlite3 db.sqlite3-wal db.sqlite3-shm; do\n'
        '    [[ -e "$INSTALL_DIR/$f" ]] && echo "BACK $f" || echo "MISSING $f"\n'
        'done\n',
    )

    for name in ("db.sqlite3", "db.sqlite3-wal", "db.sqlite3-shm"):
        assert f"HIDDEN {name}" in out, f"{name} must leave the tree with the database"
        assert f"BACK {name}" in out, f"{name} must come back"

    # And they came back as themselves — not renamed onto one another.
    assert (tmp_path / "db.sqlite3").read_text() == "LIVEDB"
    assert (tmp_path / "db.sqlite3-wal").read_text() == "WAL"
    assert (tmp_path / "db.sqlite3-shm").read_text() == "SHM"
    assert not list(tmp_path.glob("*.update-tmp-*")), "no leftovers after a restore"


def test_an_orphaned_write_ahead_log_is_recovered_with_its_database(tmp_path):
    """Interrupted mid-pull, the log must not be lost — nor renamed onto the
    database, which is what a `"$DB_NAME".update-tmp-*` glob would do."""
    (tmp_path / "db.sqlite3.update-tmp-9999").write_text("ORPHANDB")
    (tmp_path / "db.sqlite3-wal.update-tmp-9999").write_text("ORPHANWAL")
    out = run_scenario(
        tmp_path,
        'recover_orphaned_db\n'
        'cat "$INSTALL_DIR/db.sqlite3"\n'
        'cat "$INSTALL_DIR/db.sqlite3-wal"\n',
    )

    assert "ORPHANDB" in out, "the database must come back"
    assert "ORPHANWAL" in out, "the log must come back as a log, not as the database"


def test_orphaned_database_is_recovered_not_lost(tmp_path):
    """An update that died mid-pull must not strand the database."""
    (tmp_path / "db.sqlite3.update-tmp-9999").write_text("ORPHAN")
    out = run_scenario(
        tmp_path,
        'recover_orphaned_db\n'
        'cat "$INSTALL_DIR/db.sqlite3"\n',
    )

    assert "ORPHAN" in out, "the database left aside must come back"


def test_orphan_recovery_never_deletes_a_live_database(tmp_path):
    """Both copies present: keep both rather than guess which is real."""
    (tmp_path / "db.sqlite3").write_text("LIVE")
    (tmp_path / "db.sqlite3.update-tmp-9999").write_text("ORPHAN")
    out = run_scenario(
        tmp_path,
        'recover_orphaned_db\n'
        'cat "$INSTALL_DIR/db.sqlite3"\n'
        'cat "$INSTALL_DIR/db.sqlite3.update-tmp-9999.recovered"\n',
    )

    assert "LIVE" in out, "the live database must be left alone"
    assert "ORPHAN" in out, "the leftover must be kept, not deleted"


def test_database_is_not_tracked_by_git():
    """The whole point: an update must not manage the database via git."""
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "db.sqlite3"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if tracked.returncode == 0:
        pytest.skip(
            "db.sqlite3 is still tracked. Untracking it is a deliberate two-step "
            "order: the protection above must be RUNNING on the Pi first, because "
            "the commit that untracks it makes the merge delete the live file."
        )
