"""The backup download on the settings System tab.

The reason any of this exists is that ``db.sqlite3`` cannot simply be copied:
the app runs it in WAL mode, so the newest committed rows are in the ``-wal``
file beside it and a plain copy is a database missing its morning. Every test
that touches the build runs with ``transaction=True``, because ``VACUUM INTO``
refuses to run inside a transaction and the default ``django_db`` marker wraps
each test in one — which would make these tests pass for the wrong reason.

Three failure modes get their own tests, because each one has bitten a real
system: the snapshot left in RAM after the download, a cancelled download that
outlives the request, and a database too large to be built in the temp
directory (tmpfs on the Pi, so that is RAM).
"""

import io
import json
import os
import sqlite3
import time
import zipfile
from unittest import mock

import pytest
from django.apps import apps
from django.test import Client

from core.edupi_core.system import backup
from core.edupi_core.system.backup import (
    BACKUP_PREFIX,
    BackupRefused,
    build_backup,
    sweep_old_backups,
)

BACKUP_URL = "/settings/system/backup/"


@pytest.fixture
def backup_home(tmp_path, settings):
    """Build backups in the test's own directory, with media to carry."""
    settings.BACKUP_TMP_DIR = str(tmp_path / "tmp")
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.MEDIA_ROOT.mkdir()
    (settings.MEDIA_ROOT / "logo.png").write_bytes(b"png" * 10)
    (tmp_path / "tmp").mkdir()
    return tmp_path


def _download(client):
    """Fetch the backup over HTTP and return the archive's bytes."""
    resp = client.get(BACKUP_URL)
    assert resp.status_code == 200, resp.content
    payload = b"".join(resp.streaming_content)
    resp.close()
    return resp, payload


def _archive(payload):
    return zipfile.ZipFile(io.BytesIO(payload))


# --- what comes down ------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_the_download_contains_the_database_the_media_and_a_manifest(backup_home):
    resp, payload = _download(Client())

    names = set(_archive(payload).namelist())

    assert {"db.sqlite3", "manifest.json", "media/logo.png"} <= names
    assert "attachment" in resp["Content-Disposition"]
    assert resp["Content-Disposition"].endswith('.zip"')


@pytest.mark.django_db(transaction=True)
def test_the_snapshot_holds_a_row_committed_moments_before(backup_home):
    """The whole reason for `VACUUM INTO` rather than copying the file."""
    TimerSession = apps.get_model("edupi_activity_timer", "TimerSession")
    for _ in range(3):
        TimerSession.objects.create(duration_seconds=60, remaining_seconds=0)

    _resp, payload = _download(Client())

    with _archive(payload) as archive:
        snapshot = backup_home / "snapshot.sqlite3"
        snapshot.write_bytes(archive.read("db.sqlite3"))
    con = sqlite3.connect(snapshot)
    try:
        rows = con.execute(
            "SELECT COUNT(*) FROM edupi_activity_timer_timersession"
        ).fetchone()[0]
    finally:
        con.close()

    assert rows >= 3


@pytest.mark.django_db(transaction=True)
def test_the_snapshot_carries_no_write_ahead_log_beside_it(backup_home):
    """A snapshot with a -wal would be a database that still needs its other
    half."""
    _resp, payload = _download(Client())

    names = _archive(payload).namelist()

    assert not [name for name in names if name.endswith(("-wal", "-shm"))]


@pytest.mark.django_db(transaction=True)
def test_the_manifest_says_what_the_archive_is(backup_home):
    _resp, payload = _download(Client())

    with _archive(payload) as archive:
        manifest = json.loads(archive.read("manifest.json"))

    assert manifest["format"] == "tinko-backup"
    assert manifest["database"]["integrity"] == "ok"
    assert "edupi_activity_timer_timersession" in manifest["database"]["tables"]
    assert manifest["media"]["files"] == 1
    assert manifest["hostname"]


@pytest.mark.django_db(transaction=True)
def test_the_logs_are_left_out(backup_home, settings):
    """Not school data, and they would multiply the size of the download."""
    settings.LOGS_DIR = backup_home / "logs"
    settings.LOGS_DIR.mkdir()
    (settings.LOGS_DIR / "django.log").write_bytes(b"log" * 100)

    _resp, payload = _download(Client())

    assert not [
        name for name in _archive(payload).namelist() if name.startswith("logs/")
    ]


@pytest.mark.django_db(transaction=True)
def test_the_media_directory_is_optional(backup_home, settings):
    import shutil as _shutil

    _shutil.rmtree(settings.MEDIA_ROOT)

    _resp, payload = _download(Client())

    names = _archive(payload).namelist()
    assert "db.sqlite3" in names
    assert not [name for name in names if name.startswith("media/")]


@pytest.mark.django_db(transaction=True)
def test_a_setting_that_looks_like_a_credential_is_not_in_the_manifest(
    backup_home,
):
    from core.plugin_system.models import SiteSetting

    SiteSetting.objects.update_or_create(
        key="tinko.global.school_name",
        defaults={"label": "Name", "setting_type": "text", "value": "Tinko School"},
    )
    SiteSetting.objects.update_or_create(
        key="tinko.global.api_password",
        defaults={"label": "Password", "setting_type": "text", "value": "hunter2"},
    )

    _resp, payload = _download(Client())

    with _archive(payload) as archive:
        manifest = json.loads(archive.read("manifest.json"))

    assert manifest["settings"]["tinko.global.school_name"] == "Tinko School"
    assert "tinko.global.api_password" not in manifest["settings"]


# --- cleaning up after the download ---------------------------------------


@pytest.mark.django_db(transaction=True)
def test_the_temporary_directory_is_gone_once_the_download_is_sent(backup_home):
    """Django has no hook for "the file has been sent", so the response's
    close() is what has to do it — and the sweep is only the backstop."""
    _download(Client())

    assert list((backup_home / "tmp").glob(f"{BACKUP_PREFIX}*")) == []


@pytest.mark.django_db(transaction=True)
def test_a_cancelled_download_is_cleaned_up_by_the_sweep(backup_home):
    directory, _archive_path = build_backup()
    old = time.time() - backup.SWEEP_AFTER_SECONDS - 1
    os.utime(directory, (old, old))

    removed = sweep_old_backups()

    assert removed == 1
    assert not directory.exists()


@pytest.mark.django_db(transaction=True)
def test_a_fresh_backup_is_left_alone_by_the_sweep(backup_home):
    directory, _archive_path = build_backup()

    sweep_old_backups()

    assert directory.exists()


@pytest.mark.django_db(transaction=True)
def test_a_failed_build_leaves_nothing_behind(backup_home):
    """The snapshot is in RAM: a failure must not leave it there."""
    with mock.patch.object(
        backup, "snapshot_database", side_effect=sqlite3.OperationalError("nope")
    ):
        with pytest.raises(sqlite3.OperationalError):
            build_backup()

    assert list((backup_home / "tmp").glob(f"{BACKUP_PREFIX}*")) == []


# --- refusals -------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_a_database_too_large_for_the_limit_is_refused(backup_home, settings):
    """The limit is what keeps a large database out of RAM: the archive is
    built in the temp directory, which on the Pi is memory."""
    settings.BACKUP_MAX_BYTES = 1024 * 1024

    with mock.patch.object(backup, "database_size", return_value=4 * 1024 * 1024):
        resp = Client().get(BACKUP_URL, follow=True)

    assert "larger than" in resp.content.decode()
    assert list((backup_home / "tmp").glob(f"{BACKUP_PREFIX}*")) == []


@pytest.mark.django_db(transaction=True)
def test_a_full_temp_directory_is_refused_before_anything_is_written(
    backup_home,
):
    with mock.patch.object(backup, "free_space", return_value=0):
        resp = Client().get(BACKUP_URL, follow=True)

    assert "Not enough room" in resp.content.decode()
    assert list((backup_home / "tmp").glob(f"{BACKUP_PREFIX}*")) == []


@pytest.mark.django_db(transaction=True)
def test_a_file_backed_database_that_is_gone_is_refused(
    backup_home, monkeypatch, tmp_path
):
    monkeypatch.setattr(backup, "database_is_a_file", lambda: True)
    monkeypatch.setattr(backup, "database_path", lambda: tmp_path / "gone.sqlite3")

    with pytest.raises(BackupRefused):
        build_backup()


def test_an_in_memory_database_has_no_file_to_look_for():
    """The suite runs on `file:memorydb_default…`, where the existence check
    would refuse a database that is perfectly well there."""
    assert backup.database_is_a_file() is False


@pytest.mark.django_db(transaction=True)
def test_an_unusable_temp_directory_is_reported_not_raised(backup_home):
    with mock.patch.object(
        backup, "backup_root", return_value=backup_home / "file-not-dir"
    ):
        (backup_home / "file-not-dir").write_bytes(b"")
        resp = Client().get(BACKUP_URL, follow=True)

    assert resp.status_code == 200
    assert "Could not create a working directory" in resp.content.decode()


@pytest.mark.django_db
def test_the_backup_is_a_download_and_not_a_form(backup_home):
    assert Client().post(BACKUP_URL).status_code == 405


def test_the_refusal_limit_is_a_setting():
    from django.conf import settings

    assert settings.BACKUP_MAX_BYTES > 0
