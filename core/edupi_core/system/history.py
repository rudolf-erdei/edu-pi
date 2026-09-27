"""The retention rules behind the System tab's "clean history" button.

The button is a retention control, not a space saver: deleting rows does not
shrink the file in WAL mode, only ``VACUUM`` does. What it is for is dropping
history nobody will look at again, on demand, without waiting for a timer.

Two rules matter more than the windows themselves:

- **Some rows are never deleted.** A session the app is still using is held in
  memory by a service that will save it later, so deleting the row underneath
  it makes Django write the row back. The ``keep`` filter on each target is
  what stops that.
- **``core`` never imports a plugin.** Models are resolved by
  ``apps.get_model``, so a plugin that is not installed is skipped with a
  reason rather than raising at import time.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from django.apps import apps
from django.db import DatabaseError
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

# Matches noise_service.READING_RETENTION_HOURS, and a test asserts that the
# two have not drifted apart. It is not imported from the plugin: core does not
# depend on a plugin's module layout, and the plugin's value is about its own
# hourly timer, not about this button.
NOISE_RETENTION_HOURS = 24
SESSION_RETENTION_DAYS = 30


@dataclass(frozen=True)
class CleanTarget:
    """One table's retention rule."""

    app_label: str
    model_name: str
    time_field: str
    retention_hours: int
    label: str
    note: str
    # Rows matching this are never deleted, however old they are.
    keep: dict = field(default_factory=dict)

    @property
    def retention_days(self) -> int:
        return max(1, round(self.retention_hours / 24))

    @property
    def retention_days_display(self) -> str:
        if self.retention_hours < 24:
            return _("%(hours)s hours") % {"hours": self.retention_hours}
        return _("%(days)s days") % {"days": self.retention_days}


CLEAN_TARGETS: tuple[CleanTarget, ...] = (
    CleanTarget(
        app_label="edupi_noise_monitor",
        model_name="NoiseReading",
        time_field="timestamp",
        retention_hours=NOISE_RETENTION_HOURS,
        label=gettext_lazy("Noise readings"),
        note=gettext_lazy(
            "One row every few seconds while the monitor runs. The chart shows "
            "the last 20 minutes."
        ),
    ),
    CleanTarget(
        app_label="edupi_activity_timer",
        model_name="TimerSession",
        time_field="created_at",
        retention_hours=SESSION_RETENTION_DAYS * 24,
        label=gettext_lazy("Timer sessions"),
        note=gettext_lazy(
            "The timer page lists the ten most recent sessions, so clearing "
            "old ones can shorten or empty that list."
        ),
        # A running timer lives in memory and is saved again on every change;
        # deleting its row would make Django insert it back.
        keep={"status__in": ("pending", "running", "paused")},
    ),
    CleanTarget(
        app_label="edupi_routines",
        model_name="RoutineSession",
        time_field="created_at",
        retention_hours=SESSION_RETENTION_DAYS * 24,
        label=gettext_lazy("Routine sessions"),
        note=gettext_lazy(
            "A record of routines that were played; nothing on screen reads "
            "them yet."
        ),
        keep={"status__in": ("pending", "playing", "paused")},
    ),
    CleanTarget(
        app_label="edupi_touch_piano",
        model_name="PianoSession",
        time_field="started_at",
        retention_hours=SESSION_RETENTION_DAYS * 24,
        label=gettext_lazy("Piano sessions"),
        note=gettext_lazy(
            "The piano page shows the current session only."
        ),
        keep={"is_active": True},
    ),
    CleanTarget(
        app_label="lcd_display",
        model_name="DisplaySession",
        time_field="started_at",
        retention_hours=SESSION_RETENTION_DAYS * 24,
        label=gettext_lazy("Display sessions"),
        note=gettext_lazy("The display page shows the current session only."),
        keep={"is_active": True},
    ),
    CleanTarget(
        app_label="update_system",
        model_name="UpdateStatus",
        time_field="started_at",
        retention_hours=SESSION_RETENTION_DAYS * 24,
        label=gettext_lazy("Update history"),
        note=gettext_lazy(
            "The Updates tab lists the recent ones. An update that is running "
            "is never deleted, so the five-minute rate limit still holds."
        ),
        keep={"status__in": ("pending", "in_progress")},
    ),
)

# PluginEventLog is deliberately not on this list: nothing writes it, it holds
# no teacher data, and it is the only audit trail the project has. Deleting an
# audit log to reclaim nothing sets a bad precedent.


@dataclass(frozen=True)
class CleanPreview:
    """What one target would delete, without deleting it."""

    label: str
    retention_days_display: str
    note: str
    count: int
    missing: bool = False


@dataclass(frozen=True)
class CleanResult:
    """What one target did delete."""

    label: str
    deleted: int
    missing: bool = False
    error: str = ""


def _queryset(target: CleanTarget, now: datetime):
    """The rows *target* would delete, or None when its model is not installed."""
    try:
        model = apps.get_model(target.app_label, target.model_name)
    except LookupError:
        return None
    cutoff = now - timedelta(hours=target.retention_hours)
    queryset = model.objects.filter(**{f"{target.time_field}__lt": cutoff})
    if target.keep:
        queryset = queryset.exclude(**target.keep)
    return queryset


def survey_clean(now: datetime | None = None) -> list[CleanPreview]:
    """Count what "Clean history" would remove, so the button can say the number.

    Never raises: a table that cannot be counted is reported as absent.
    """
    now = now or timezone.now()
    previews: list[CleanPreview] = []
    for target in CLEAN_TARGETS:
        queryset = _queryset(target, now)
        if queryset is None:
            previews.append(
                CleanPreview(
                    label=str(target.label),
                    retention_days_display=target.retention_days_display,
                    note=str(target.note),
                    count=0,
                    missing=True,
                )
            )
            continue
        try:
            count = queryset.count()
        except DatabaseError:
            count = 0
        previews.append(
            CleanPreview(
                label=str(target.label),
                retention_days_display=target.retention_days_display,
                note=str(target.note),
                count=count,
            )
        )
    return previews


def run_clean(now: datetime | None = None) -> list[CleanResult]:
    """Delete every row past its retention window.

    A failing target does not stop the others and does not raise: the caller
    reports what happened, and history that outlives its window is a smaller
    problem than a settings page that breaks.
    """
    now = now or timezone.now()
    results: list[CleanResult] = []
    for target in CLEAN_TARGETS:
        queryset = _queryset(target, now)
        if queryset is None:
            results.append(
                CleanResult(label=str(target.label), deleted=0, missing=True)
            )
            continue
        try:
            deleted, _per_model = queryset.delete()
        except DatabaseError as e:
            results.append(
                CleanResult(label=str(target.label), deleted=0, error=str(e))
            )
            continue
        results.append(CleanResult(label=str(target.label), deleted=deleted))
    return results
