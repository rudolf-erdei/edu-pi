"""The settings page's System tab: storage, retention, and the maintenance pair.

Three things here are worth more than the rest:

- **The scope of "clean history".** The timer page lists
  ``TimerSession.objects.all()[:10]``, so this button can shorten a list a
  teacher is looking at. The test pins exactly which rows may go.
- **The rows that are never deleted.** A running timer is held in memory by
  ``timer_service`` and saved again on every change, so deleting its row makes
  Django insert it back; an ``in_progress`` update row is what stops a second
  update starting. Both are covered.
- **The CSRF contract on the two destructive endpoints**, which Django's test
  client does not enforce by default — so without these tests a POST that would
  403 in a browser looks fine.
"""

from datetime import timedelta
from unittest import mock

import pytest
from django.apps import apps
from django.conf import settings as django_settings
from django.middleware.csrf import get_token
from django.test import Client, RequestFactory
from django.utils import timezone

from core.edupi_core.system import history, storage
from core.edupi_core.system.history import (
    CLEAN_TARGETS,
    CleanTarget,
    NOISE_RETENTION_HOURS,
    run_clean,
    survey_clean,
)

DESTRUCTIVE_URLS = ("/settings/system/clean/", "/settings/system/vacuum/")


# --- the tab itself --------------------------------------------------------


@pytest.mark.django_db
def test_the_system_tab_is_rendered_on_request():
    resp = Client().get("/settings/", {"tab": "system"})

    assert resp.status_code == 200
    assert resp.context["is_system"] is True
    # Not the plugin branch: that one renders nothing at all, because nothing
    # ever builds a PluginSettings instance.
    assert resp.context["is_plugin"] is False
    assert "Storage" in resp.content.decode()


@pytest.mark.django_db
def test_the_system_tab_is_offered_beside_the_others():
    resp = Client().get("/settings/")

    ids = [tab["id"] for tab in resp.context["tabs"]]

    assert ids == ["global", "updates", "system"]


@pytest.mark.django_db
def test_an_unknown_tab_falls_into_the_plugin_branch():
    """`?tab=nonsense` must not be mistaken for a real tab."""
    resp = Client().get("/settings/", {"tab": "nonsense"})

    assert resp.status_code == 200
    assert resp.context["is_plugin"] is True
    assert resp.context["is_system"] is False


@pytest.mark.django_db
@pytest.mark.parametrize("tab", ["global", "updates", "nonsense"])
def test_storage_is_only_measured_for_the_system_tab(tab):
    """Walking the media and log trees is work nobody asked for on other tabs."""
    with mock.patch(
        "core.edupi_core.views.measure_storage"
    ) as measure:
        Client().get("/settings/", {"tab": tab})

    assert measure.call_count == 0


@pytest.mark.django_db
def test_the_clients_endpoint_answers_json():
    resp = Client().get("/settings/system/clients/")

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == len(body["clients"]) >= 1
    assert set(body["clients"][0]) == {
        "ip",
        "user",
        "route",
        "idle_seconds",
        "seen_for_seconds",
    }


@pytest.mark.django_db
def test_the_clients_endpoint_refuses_a_post():
    assert Client().post("/settings/system/clients/").status_code == 405


# --- storage ---------------------------------------------------------------


def _usage(total: int, used: int):
    """A stand-in for ``shutil.disk_usage``'s named tuple."""
    return mock.Mock(total=total, used=used, free=total - used)


GIB = 1024**3


def test_a_full_root_filesystem_raises_a_warning():
    with mock.patch.object(
        storage.shutil, "disk_usage", return_value=_usage(GIB, int(GIB * 0.95))
    ):
        report = storage.measure_storage()

    free = GIB - int(GIB * 0.95)
    assert len(report.warnings) == 1
    assert "Only" in report.warnings[0]
    # The figures are in the sentence: a warning without them gets ignored.
    assert storage.human_size(free) in report.warnings[0]


def test_a_healthy_root_filesystem_says_nothing():
    with mock.patch.object(
        storage.shutil, "disk_usage", return_value=_usage(GIB, int(GIB * 0.4))
    ):
        report = storage.measure_storage()

    assert report.warnings == []


def test_a_ram_mount_is_only_shown_when_it_really_is_one():
    """`/var/log` and `/var/tmp` are separate mounts on the Pi, plain
    directories everywhere else — where a second row would repeat the first."""
    with mock.patch.object(
        storage.shutil, "disk_usage", return_value=_usage(GIB, GIB // 4)
    ), mock.patch.object(storage.os.path, "ismount", return_value=False):
        without = storage.measure_storage()
    with mock.patch.object(
        storage.shutil, "disk_usage", return_value=_usage(GIB, GIB // 4)
    ), mock.patch.object(storage.os.path, "ismount", return_value=True):
        with_mounts = storage.measure_storage()

    assert [mount.path for mount in without.mounts] == ["/"]
    assert [mount.path for mount in with_mounts.mounts] == [
        "/",
        "/var/log",
        "/var/tmp",
    ]


def test_an_unreadable_filesystem_is_survived_not_raised():
    with mock.patch.object(storage.shutil, "disk_usage", side_effect=OSError("nope")):
        report = storage.measure_storage()

    assert report.mounts == []
    assert report.warnings == []


@pytest.mark.parametrize(
    "path,total,used",
    (("/var/log", 128 * 1024**2, int(128 * 1024**2 * 0.9)),),
)
def test_the_log_area_warns_before_logging_stops(path, total, used):
    """log2ram's tmpfs is small and full is fatal to logging: say so."""

    def usage_for(target):
        if target == path:
            return _usage(total, used)
        return _usage(GIB, GIB // 4)

    with mock.patch.object(
        storage.shutil, "disk_usage", side_effect=usage_for
    ), mock.patch.object(storage.os.path, "ismount", return_value=True):
        report = storage.measure_storage()

    assert any("logging stops" in warning for warning in report.warnings)


def test_the_database_is_measured_with_its_write_ahead_log(tmp_path, monkeypatch):
    """WAL mode keeps committed rows beside the file, so both are the database."""
    database = tmp_path / "db.sqlite3"
    database.write_bytes(b"x" * 100)
    (tmp_path / "db.sqlite3-wal").write_bytes(b"y" * 50)
    monkeypatch.setattr(storage, "database_path", lambda: database)

    assert storage.database_size() == 150
    labels = {usage.label for usage in storage._app_paths()}
    assert "Database write-ahead log" in labels


def test_the_media_and_log_trees_are_measured(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.LOGS_DIR = tmp_path / "logs"
    (settings.MEDIA_ROOT / "site").mkdir(parents=True)
    (settings.MEDIA_ROOT / "site" / "logo.png").write_bytes(b"z" * 2048)
    settings.LOGS_DIR.mkdir(parents=True)
    (settings.LOGS_DIR / "django.log").write_bytes(b"l" * 512)

    sizes = {usage.label: usage.size for usage in storage._app_paths()}

    assert sizes["Uploaded files"] == 2048
    assert sizes["Logs"] == 512


def test_sizes_are_formatted_for_a_reader():
    assert storage.human_size(0) == "0 B"
    assert storage.human_size(2048) == "2.0 KB"
    assert storage.human_size(5 * 1024**2) == "5.0 MB"
    assert storage.human_size(None) == "—"


# --- what "clean history" may delete --------------------------------------


def test_every_clean_target_points_at_a_real_model_and_field():
    """A typo in an app label would silently clean nothing, forever."""
    for target in CLEAN_TARGETS:
        model = apps.get_model(target.app_label, target.model_name)
        assert model is not None
        assert model._meta.get_field(target.time_field) is not None


def test_the_noise_window_matches_the_service_that_prunes_it():
    """The same 24 hours, in two places, with nothing tying them together."""
    from plugins.edupi.noise_monitor import noise_service

    assert NOISE_RETENTION_HOURS == noise_service.READING_RETENTION_HOURS


@pytest.mark.django_db
def test_every_target_can_be_counted_without_a_fixture():
    previews = survey_clean()

    assert len(previews) == len(CLEAN_TARGETS)
    assert [preview.missing for preview in previews] == [False] * len(CLEAN_TARGETS)


@pytest.mark.django_db
def test_clean_deletes_history_past_its_window():
    TimerSession = apps.get_model("edupi_activity_timer", "TimerSession")
    stale = TimerSession.objects.create(
        duration_seconds=60, remaining_seconds=0, status="completed"
    )
    TimerSession.objects.filter(pk=stale.pk).update(
        created_at=timezone.now() - timedelta(days=40)
    )

    results = run_clean()

    assert not TimerSession.objects.filter(pk=stale.pk).exists()
    assert sum(result.deleted for result in results) == 1


@pytest.mark.django_db
def test_clean_reports_nothing_when_nothing_is_old_enough():
    """The usual answer, and the one that must not look like a broken button."""
    TimerSession = apps.get_model("edupi_activity_timer", "TimerSession")
    TimerSession.objects.create(duration_seconds=60, remaining_seconds=0)

    results = run_clean()

    assert sum(result.deleted for result in results) == 0


@pytest.mark.django_db
def test_clean_leaves_the_list_the_timer_page_shows_alone():
    """`activity_timer` renders `TimerSession.objects.all()[:10]`.

    Eleven recent sessions and one old one: the ten on screen must be the same
    ten afterwards, and only the old row may go.
    """
    TimerSession = apps.get_model("edupi_activity_timer", "TimerSession")
    for _ in range(11):
        TimerSession.objects.create(
            duration_seconds=60, remaining_seconds=0, status="completed"
        )
    stale = TimerSession.objects.create(
        duration_seconds=60, remaining_seconds=0, status="completed"
    )
    TimerSession.objects.filter(pk=stale.pk).update(
        created_at=timezone.now() - timedelta(days=40)
    )
    before = list(TimerSession.objects.all()[:10].values_list("pk", flat=True))

    run_clean()

    after = list(TimerSession.objects.all()[:10].values_list("pk", flat=True))
    assert after == before
    assert not TimerSession.objects.filter(pk=stale.pk).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["pending", "running", "paused"])
def test_clean_never_deletes_a_timer_that_is_still_going(status):
    """`timer_service` holds this row in memory and saves it again; deleting it
    underneath would make Django insert it back."""
    TimerSession = apps.get_model("edupi_activity_timer", "TimerSession")
    live = TimerSession.objects.create(
        duration_seconds=60, remaining_seconds=30, status=status
    )
    TimerSession.objects.filter(pk=live.pk).update(
        created_at=timezone.now() - timedelta(days=90)
    )

    run_clean()

    assert TimerSession.objects.filter(pk=live.pk).exists()


@pytest.mark.django_db
def test_clean_never_deletes_an_update_that_is_in_progress():
    """That row is what stops a second update starting."""
    UpdateStatus = apps.get_model("update_system", "UpdateStatus")
    running = UpdateStatus.objects.create(status="in_progress")
    UpdateStatus.objects.filter(pk=running.pk).update(
        started_at=timezone.now() - timedelta(days=90)
    )

    run_clean()

    assert UpdateStatus.objects.filter(pk=running.pk).exists()


@pytest.mark.django_db
def test_clean_still_removes_an_update_that_finished():
    UpdateStatus = apps.get_model("update_system", "UpdateStatus")
    finished = UpdateStatus.objects.create(status="completed")
    UpdateStatus.objects.filter(pk=finished.pk).update(
        started_at=timezone.now() - timedelta(days=90)
    )

    run_clean()

    assert not UpdateStatus.objects.filter(pk=finished.pk).exists()


@pytest.mark.django_db
def test_an_active_piano_session_is_kept_and_a_finished_one_is_not():
    PianoSession = apps.get_model("edupi_touch_piano", "PianoSession")
    old = timezone.now() - timedelta(days=90)
    active = PianoSession.objects.create(started_at=old, is_active=True)
    finished = PianoSession.objects.create(started_at=old, is_active=False)

    run_clean()

    assert PianoSession.objects.filter(pk=active.pk).exists()
    assert not PianoSession.objects.filter(pk=finished.pk).exists()


def test_a_target_whose_plugin_is_gone_is_skipped(monkeypatch):
    """`core` resolves plugin models lazily, so a plugin that is not installed
    has to be a reason rather than an exception."""
    missing = CleanTarget(
        app_label="not_installed_at_all",
        model_name="Nothing",
        time_field="created_at",
        retention_hours=24,
        label="Nothing",
        note="",
    )
    monkeypatch.setattr(history, "CLEAN_TARGETS", (missing,))

    assert survey_clean()[0].missing is True
    results = run_clean()

    assert results[0].missing is True
    assert results[0].deleted == 0


@pytest.mark.django_db
def test_a_failing_target_does_not_stop_the_others(monkeypatch):
    good = CleanTarget(
        app_label="edupi_activity_timer",
        model_name="TimerSession",
        time_field="created_at",
        retention_hours=24,
        label="Timer sessions",
        note="",
    )
    bad = CleanTarget(
        app_label="not_installed_at_all",
        model_name="Nothing",
        time_field="created_at",
        retention_hours=24,
        label="Nothing",
        note="",
    )
    TimerSession = apps.get_model("edupi_activity_timer", "TimerSession")
    stale = TimerSession.objects.create(
        duration_seconds=60, remaining_seconds=0, status="completed"
    )
    TimerSession.objects.filter(pk=stale.pk).update(
        created_at=timezone.now() - timedelta(days=40)
    )
    monkeypatch.setattr(history, "CLEAN_TARGETS", (bad, good))

    results = run_clean()

    assert [result.missing for result in results] == [True, False]
    assert not TimerSession.objects.filter(pk=stale.pk).exists()


# --- the two destructive endpoints ----------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("url", DESTRUCTIVE_URLS)
def test_a_get_cannot_delete_anything(url):
    """A GET is followed by browsers, link previews and crawlers."""
    assert Client().get(url).status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize("url", DESTRUCTIVE_URLS)
def test_a_post_without_a_csrf_token_is_refused(url):
    resp = Client(enforce_csrf_checks=True).post(url)

    assert resp.status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("url", DESTRUCTIVE_URLS)
def test_a_post_with_a_token_is_accepted(url):
    token = get_token(RequestFactory().get("/"))
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.cookies["csrftoken"] = token

    resp = csrf_client.post(url, headers={"x-csrftoken": token})

    assert resp.status_code == 302
    assert resp.url == "/settings/?tab=system"


@pytest.mark.django_db
def test_cleaning_reports_what_it_deleted():
    TimerSession = apps.get_model("edupi_activity_timer", "TimerSession")
    for _ in range(3):
        stale = TimerSession.objects.create(
            duration_seconds=60, remaining_seconds=0, status="completed"
        )
        TimerSession.objects.filter(pk=stale.pk).update(
            created_at=timezone.now() - timedelta(days=40)
        )
    token = get_token(RequestFactory().get("/"))
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.cookies["csrftoken"] = token

    resp = csrf_client.post(
        "/settings/system/clean/", headers={"x-csrftoken": token}, follow=True
    )

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "3 old records were deleted" in body
    assert "Timer sessions: 3" in body


@pytest.mark.django_db
def test_cleaning_says_so_when_there_was_nothing_to_do():
    token = get_token(RequestFactory().get("/"))
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.cookies["csrftoken"] = token

    resp = csrf_client.post(
        "/settings/system/clean/", headers={"x-csrftoken": token}, follow=True
    )

    assert "Nothing was old enough to delete." in resp.content.decode()


@pytest.mark.django_db(transaction=True)
def test_compacting_answers_with_the_size_of_the_database():
    """VACUUM cannot run inside a transaction, which is why this test asks for
    a real one. The answer is either "compacted" or "nothing to reclaim":
    pytest's SQLite test database is in memory, where VACUUM does nothing."""
    token = get_token(RequestFactory().get("/"))
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.cookies["csrftoken"] = token

    resp = csrf_client.post(
        "/settings/system/vacuum/", headers={"x-csrftoken": token}, follow=True
    )

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "compacted" in body.lower() or "reclaim" in body.lower()


@pytest.mark.django_db(transaction=True)
def test_compacting_never_reports_a_failure_it_did_not_have():
    """The database is fine, so nothing may be logged as an error."""
    token = get_token(RequestFactory().get("/"))
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.cookies["csrftoken"] = token

    resp = csrf_client.post(
        "/settings/system/vacuum/", headers={"x-csrftoken": token}, follow=True
    )

    assert "Could not compact" not in resp.content.decode()


def test_the_vacuum_gives_up_slowly_enough_for_the_noise_monitor():
    """Its commit every five seconds would fail against the default timeout."""
    from core.edupi_core.system import views

    assert views.VACUUM_BUSY_TIMEOUT_MS >= 5000


def test_the_poll_interval_is_the_one_the_project_uses():
    """One minute, like the noise chart's refresh."""
    assert django_settings.CLIENT_POLL_SECONDS == 60
