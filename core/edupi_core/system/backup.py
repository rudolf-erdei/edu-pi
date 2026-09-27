"""The downloadable backup: a consistent snapshot, built in the temp directory.

**Never copy ``db.sqlite3``.** The database is live and in WAL mode, so the
file on its own is not the database — the newest committed rows are in the
``-wal`` beside it. ``VACUUM INTO`` writes a single self-contained file that is
consistent as of the moment it runs, and that file is what goes in the zip.

Everything is built under the system temp directory, which on the Pi is tmpfs:
taking a backup writes to RAM and touches the SD card not at all. The price is
that a database too big to fit in RAM must be refused rather than attempted,
which is what the pre-flight check is for.
"""

from __future__ import annotations

import json
import platform
import shutil
import socket
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path

import django
from django.conf import settings
from django.db import connection
from django.utils import timezone
from django.utils.translation import gettext as _

from core.edupi_core.system.storage import (
    database_path,
    database_size,
    file_size,
    free_space,
    human_size,
    tree_size,
)

BACKUP_PREFIX = "tinko-backup-"
BACKUP_FORMAT = "tinko-backup"
BACKUP_FORMAT_VERSION = 1

# A directory left behind by a download that was cancelled or interrupted. The
# response cleans up after itself on a completed send; nothing cleans up after
# one that never finished, except this.
SWEEP_AFTER_SECONDS = 900

# Headroom over the snapshot itself: the zip plus the media files.
SPACE_HEADROOM_BYTES = 16 * 1024 * 1024

# Settings whose name suggests a credential are left out of the manifest. The
# project stores none today; the guard is here so that it stays true.
SECRET_HINTS = ("password", "secret", "token", "pin", "api_key", "apikey", "credential")


class BackupRefused(Exception):
    """The backup was not started. The message is safe to show the user."""


def database_is_a_file() -> bool:
    """True when the configured database is a file that ought to be there.

    A ``file:`` URI or ``:memory:`` names a database SQLite keeps itself, with
    no file on disk to find — which is how the test suite runs. The checks that
    ask about a file on disk only make sense for the other case.
    """
    name = str(settings.DATABASES["default"]["NAME"])
    return bool(name) and not name.startswith("file:") and name != ":memory:"


def backup_root() -> Path:
    """Where snapshots are built. tmpfs on the Pi, so this writes no card."""
    configured = getattr(settings, "BACKUP_TMP_DIR", None)
    root = Path(str(configured)) if configured else Path(tempfile.gettempdir())
    return root


def max_backup_bytes() -> int:
    return int(getattr(settings, "BACKUP_MAX_BYTES", 64 * 1024 * 1024))


def sweep_old_backups(now: float | None = None) -> int:
    """Delete snapshot directories older than the sweep window.

    Returns how many were removed. Never raises: failing to tidy up is not a
    reason to fail a download.
    """
    now = time.time() if now is None else now
    root = backup_root()
    removed = 0
    try:
        entries = list(root.glob(f"{BACKUP_PREFIX}*"))
    except OSError:
        return 0
    for entry in entries:
        try:
            if now - entry.stat().st_mtime < SWEEP_AFTER_SECONDS:
                continue
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink()
        except OSError:
            continue
        removed += 1
    return removed


def snapshot_database(destination: Path) -> None:
    """Write a consistent copy of the live database to *destination*.

    ``VACUUM INTO`` is the only correct way to do this while the app is
    running: it reads the database through SQLite itself, so it sees the rows
    the WAL has not checkpointed yet, and it produces one file with no
    ``-wal`` or ``-shm`` sibling.

    It cannot run inside a transaction, so it must not be called from a view
    wrapped in ``ATOMIC_REQUESTS`` (this project does not wrap) or from a test
    that has not marked itself ``transaction=True``.
    """
    if destination.exists():
        # VACUUM INTO refuses an existing file, and a half-written one from an
        # earlier attempt is not something to append to.
        destination.unlink()
    with connection.cursor() as cursor:
        # Bound parameter, not an f-string: the path is built from settings and
        # the temp directory, and this keeps it that way.
        cursor.execute("VACUUM INTO %s", [str(destination)])


def inspect_snapshot(path: Path) -> dict:
    """Read the snapshot back and describe it.

    Opening it proves the file is a database at all; ``integrity_check`` proves
    it is a sound one; the row counts are what makes a manifest worth having.
    """
    connection_uri = f"file:{path}?mode=ro"
    con = sqlite3.connect(connection_uri, uri=True)
    try:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        names = [
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        tables = {}
        for name in names:
            quoted = name.replace('"', '""')
            tables[name] = con.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
    finally:
        con.close()
    return {
        "bytes": file_size(path),
        "bytes_display": human_size(file_size(path)),
        "integrity": integrity,
        "tables": tables,
        "total_rows": sum(tables.values()),
    }


def _media_stats() -> dict:
    """How much uploaded material the snapshot is carrying."""
    media_root = Path(str(settings.MEDIA_ROOT))
    files = 0
    total = 0
    if media_root.exists():
        for path in media_root.rglob("*"):
            if path.is_file():
                files += 1
                total += file_size(path)
    return {
        "files": files,
        "bytes": total,
        "bytes_display": human_size(total),
    }


def _site_settings() -> dict:
    """The site's own settings, minus anything that looks like a credential."""
    from core.plugin_system.models import SiteSetting

    values: dict[str, str] = {}
    try:
        rows = SiteSetting.objects.all()
    except Exception:
        return values
    for row in rows:
        key = row.key or ""
        if any(hint in key.lower() for hint in SECRET_HINTS):
            continue
        values[key] = row.value
    return values


def build_manifest(snapshot: Path, report: dict) -> dict:
    """The file that tells a future restore what it is looking at."""
    return {
        "format": BACKUP_FORMAT,
        "format_version": BACKUP_FORMAT_VERSION,
        "created_at": timezone.localtime().isoformat(),
        "hostname": socket.gethostname(),
        "django": django.get_version(),
        "python": platform.python_version(),
        "sqlite": sqlite3.sqlite_version,
        "database": report,
        "media": _media_stats(),
        "settings": _site_settings(),
    }


def _write_zip(destination: Path, snapshot: Path, manifest: dict) -> None:
    """Collect the snapshot, the media and the manifest into one download."""
    media_root = Path(str(settings.MEDIA_ROOT))
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(snapshot, "db.sqlite3")
        if media_root.exists():
            for path in sorted(media_root.rglob("*")):
                if path.is_file():
                    archive.write(path, f"media/{path.relative_to(media_root).as_posix()}")
        archive.writestr(
            "manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False)
        )


def build_backup() -> tuple[Path, Path]:
    """Build the download and return ``(directory, zip_path)``.

    The caller owns *directory*: it must be removed once the download has been
    sent, or the sweep will eventually get it. Raises :class:`BackupRefused`
    with a message worth showing when the backup must not be attempted.
    """
    sweep_old_backups()

    database = database_path()
    if database_is_a_file() and not database.exists():
        raise BackupRefused(
            _("The database file was not found, so there is nothing to back up.")
        )

    size = database_size()
    if size > max_backup_bytes():
        raise BackupRefused(
            _(
                "The database is %(size)s, larger than the %(limit)s this backup "
                "will build in memory."
            )
            % {"size": human_size(size), "limit": human_size(max_backup_bytes())}
        )

    root = backup_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise BackupRefused(
            _("Could not create a working directory for the backup: %(error)s")
            % {"error": e}
        ) from e

    # The snapshot is built in RAM (tmpfs on the Pi), so the room has to be
    # there before it is: a Pi that runs out of memory does not recover neatly.
    needed = size + SPACE_HEADROOM_BYTES
    available = free_space(root)
    if available is not None and available < needed:
        raise BackupRefused(
            _(
                "Not enough room to build the backup: it needs about %(needed)s "
                "and %(free)s is free in %(root)s."
            )
            % {
                "needed": human_size(needed),
                "free": human_size(available),
                "root": str(root),
            }
        )

    try:
        directory = Path(tempfile.mkdtemp(prefix=BACKUP_PREFIX, dir=root))
    except OSError as e:
        raise BackupRefused(
            _("Could not create a working directory for the backup: %(error)s")
            % {"error": e}
        ) from e

    try:
        snapshot = directory / "db.sqlite3"
        snapshot_database(snapshot)
        manifest = build_manifest(snapshot, inspect_snapshot(snapshot))
        zip_path = directory / "tinko-backup.zip"
        _write_zip(zip_path, snapshot, manifest)
    except Exception:
        # Whatever went wrong, do not leave a half-built snapshot in RAM.
        shutil.rmtree(directory, ignore_errors=True)
        raise
    return directory, zip_path
