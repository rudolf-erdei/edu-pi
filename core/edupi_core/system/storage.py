"""Read-only measurements shown on the settings page's System tab.

Everything here is a snapshot taken while the request is being served, and
every measurement is taken defensively: a value that cannot be read is reported
as missing rather than raised. A settings page that returns 500 because a mount
is not where it was expected is worse than a settings page missing that row —
the same rule ``power_helper_ready`` follows in ``core.edupi_core.views``.

Nothing in this module writes anything, needs root, or reads ``/proc``.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

# Warn when a mount has less than this fraction of its space free.
FREE_WARN_RATIO = 0.10
# Warn when one of the RAM-backed areas is this full. They are small by design
# (log2ram is 128 MB), so a percentage is the only useful way to say it.
RAM_MOUNT_FULL_WARN_RATIO = 0.80

# Mounts that are worth their own row only on the Pi. On a development machine
# they are ordinary directories on the root filesystem, and printing them would
# show the same numbers twice.
EXTRA_MOUNTS = ("/var/log", "/var/tmp")

# The write-ahead log and shared-memory files travel with the database: SQLite
# in WAL mode keeps committed rows in the -wal until a checkpoint, so the three
# files together are what "the database" weighs.
DATABASE_SIBLINGS = (
    ("-wal", _("Database write-ahead log")),
    ("-shm", _("Database shared memory")),
)


def human_size(size: int | None) -> str:
    """Format a byte count the way a teacher reads it (``2.0 MB``)."""
    if size is None:
        return "—"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


@dataclass(frozen=True)
class Mount:
    """A filesystem and how full it is."""

    path: str
    total: int
    used: int
    free: int

    @property
    def percent_used(self) -> float:
        return (self.used / self.total * 100) if self.total else 0.0

    @property
    def percent_used_display(self) -> str:
        return f"{self.percent_used:.0f}%"

    @property
    def total_h(self) -> str:
        return human_size(self.total)

    @property
    def used_h(self) -> str:
        return human_size(self.used)

    @property
    def free_h(self) -> str:
        return human_size(self.free)

    @property
    def is_full(self) -> bool:
        return bool(self.total) and self.percent_used >= RAM_MOUNT_FULL_WARN_RATIO * 100


@dataclass(frozen=True)
class PathUsage:
    """The size of one file or directory the app itself owns."""

    label: str
    path: str
    size: int
    exists: bool = True

    @property
    def size_h(self) -> str:
        return human_size(self.size)


@dataclass
class StorageReport:
    """What the storage card on the System tab renders."""

    mounts: list[Mount] = field(default_factory=list)
    paths: list[PathUsage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    measured_at: datetime | None = None


def database_path() -> Path:
    """The live SQLite database, as configured."""
    return Path(str(settings.DATABASES["default"]["NAME"]))


def file_size(path: Path) -> int:
    """Bytes in one file, or 0 when it is missing or unreadable."""
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def tree_size(path: Path) -> int:
    """Bytes in every file under *path*, skipping anything unreadable."""
    total = 0
    if not path.exists():
        return 0
    for dirpath, _dirnames, filenames in os.walk(path, onerror=lambda _e: None):
        for name in filenames:
            total += file_size(Path(dirpath) / name)
    return total


def database_size() -> int:
    """Bytes of the live database, including its WAL and shared-memory files."""
    path = database_path()
    return file_size(path) + sum(
        file_size(Path(str(path) + suffix)) for suffix, _label in DATABASE_SIBLINGS
    )


def free_space(path: Path | str) -> int | None:
    """Free bytes on the filesystem holding *path*, or None if unreadable."""
    try:
        return shutil.disk_usage(str(path)).free
    except OSError:
        return None


def _disk_usage(path: str) -> Mount | None:
    """A mount's figures, or None when the filesystem cannot be queried."""
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    return Mount(path=path, total=usage.total, used=usage.used, free=usage.free)


def _app_paths() -> list[PathUsage]:
    """The files the app itself grows, which is what fills the card."""
    paths: list[PathUsage] = []
    database = database_path()
    paths.append(
        PathUsage(
            label=_("Database"),
            path=str(database),
            size=file_size(database),
            exists=database.exists(),
        )
    )
    for suffix, label in DATABASE_SIBLINGS:
        sibling = Path(str(database) + suffix)
        if sibling.exists():
            paths.append(
                PathUsage(
                    label=label,
                    path=str(sibling),
                    size=file_size(sibling),
                )
            )

    media = Path(str(settings.MEDIA_ROOT))
    paths.append(
        PathUsage(
            label=_("Uploaded files"),
            path=str(media),
            size=tree_size(media),
            exists=media.exists(),
        )
    )
    logs = Path(str(settings.LOGS_DIR))
    paths.append(
        PathUsage(
            label=_("Logs"),
            path=str(logs),
            size=tree_size(logs),
            exists=logs.exists(),
        )
    )
    return paths


def _warnings(mounts: list[Mount]) -> list[str]:
    """The sentences that make the numbers mean something.

    Every one of them carries the figures it is about: a warning that says
    "disk space low" without saying how low is a warning that gets ignored.
    """
    warnings: list[str] = []
    for mount in mounts:
        if mount.total == 0:
            continue
        if mount.free / mount.total < FREE_WARN_RATIO:
            warnings.append(
                _("Only %(free)s left on %(path)s (%(percent)s used).")
                % {
                    "free": mount.free_h,
                    "path": mount.path,
                    "percent": mount.percent_used_display,
                }
            )
        if mount.path == "/var/log" and mount.is_full:
            warnings.append(
                _(
                    "The log area %(path)s is %(percent)s full "
                    "(%(used)s of %(total)s). When it fills, logging stops."
                )
                % {
                    "path": mount.path,
                    "percent": mount.percent_used_display,
                    "used": mount.used_h,
                    "total": mount.total_h,
                }
            )
        elif mount.path == "/var/tmp" and mount.is_full:
            warnings.append(
                _(
                    "%(path)s is %(percent)s full (%(used)s of %(total)s). "
                    "It is RAM, so nothing there survives a reboot."
                )
                % {
                    "path": mount.path,
                    "percent": mount.percent_used_display,
                    "used": mount.used_h,
                    "total": mount.total_h,
                }
            )
    return warnings


def measure_storage() -> StorageReport:
    """Measure what the System tab's storage card shows.

    The root filesystem always appears. ``/var/log`` and ``/var/tmp`` appear
    only when they really are separate mounts — on the Pi they are RAM
    (log2ram and a tmpfs), and on a development machine they are the root
    filesystem again, where a second row would be a copy of the first.
    """
    mounts: list[Mount] = []
    root = _disk_usage("/")
    if root is None:
        # No root to measure (an unusual platform): fall back to whichever
        # filesystem the project itself is on, which is the one that matters.
        root = _disk_usage(str(settings.BASE_DIR))
    if root is not None:
        mounts.append(root)

    for path in EXTRA_MOUNTS:
        if os.path.ismount(path):
            usage = _disk_usage(path)
            if usage is not None:
                mounts.append(usage)

    return StorageReport(
        mounts=mounts,
        paths=_app_paths(),
        warnings=_warnings(mounts),
        measured_at=timezone.localtime(),
    )
