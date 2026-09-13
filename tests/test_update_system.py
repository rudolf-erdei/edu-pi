"""Tests for core.update_system (web update flow).

The critical concern is that a previous update (successful, failed, or
abandoned) never blocks future updates from the UI, and that the DB record
is reconciled from the daemon's status file.
"""

import json
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from core.update_system.models import UpdateStatus


@pytest.mark.django_db
def test_start_update_not_blocked_by_stale_in_progress_record(client, tmp_path):
    """An in_progress record older than 24h is abandoned (failed), so a new
    update is not rejected with 409."""
    stale = UpdateStatus.objects.create(status="in_progress")
    # Backdate via update() -- auto_now_add would otherwise override.
    UpdateStatus.objects.filter(pk=stale.pk).update(
        started_at=timezone.now() - timedelta(hours=30)
    )

    with mock.patch("core.update_system.views.STATUS_FILE", tmp_path / "status.json"), mock.patch(
        "core.update_system.views.write_trigger_file"
    ) as trigger:
        resp = client.post("/updates/start/")

    assert resp.status_code == 200, resp.content
    assert trigger.call_count == 1
    # The abandoned row failed and exactly one new in_progress row exists.
    assert UpdateStatus.objects.filter(status="in_progress").count() == 1
    assert UpdateStatus.objects.filter(status="failed").count() == 1


@pytest.mark.django_db
def test_get_update_status_syncs_terminal_row(client, tmp_path):
    """When the daemon's status file shows a terminal state, the matching DB
    row is marked completed so future updates are not blocked."""
    record = UpdateStatus.objects.create(status="in_progress")
    status_file = tmp_path / "status.json"
    status_file.write_text(
        json.dumps({"update_id": record.id, "status": "completed", "stage": "finished"})
    )

    with mock.patch("core.update_system.views.STATUS_FILE", status_file):
        resp = client.get("/updates/status/")

    assert resp.status_code == 200
    record.refresh_from_db()
    assert record.status == "completed"
    assert record.completed_at is not None


@pytest.mark.django_db
def test_start_update_rate_limited_within_5_minutes(client, tmp_path):
    """A recently completed update still enforces the 5-minute rate limit."""
    UpdateStatus.objects.create(status="completed", started_at=timezone.now())

    with mock.patch("core.update_system.views.write_trigger_file") as trigger:
        resp = client.post("/updates/start/")

    assert resp.status_code == 429
    trigger.assert_not_called()


@pytest.mark.django_db
def test_failed_terminal_status_syncs_error(client, tmp_path):
    """Failed terminal state carries the error message into the DB row."""
    record = UpdateStatus.objects.create(status="in_progress")
    status_file = tmp_path / "status.json"
    status_file.write_text(
        json.dumps(
            {
                "update_id": record.id,
                "status": "failed",
                "stage": "dependencies",
                "error": "uv: command not found",
            }
        )
    )

    with mock.patch("core.update_system.views.STATUS_FILE", status_file):
        resp = client.get("/updates/status/")

    assert resp.status_code == 200
    record.refresh_from_db()
    assert record.status == "failed"
    assert record.error_message == "uv: command not found"


def test_javascript_catalog_serves_ro(client):
    """The JS translation catalog (djangojs domain) serves the Romanian
    translations used by update.js (stages, check result, confirmations)."""
    from django.test import override_settings
    from django.utils import translation

    with override_settings(LANGUAGE_CODE="ro"):
        with translation.override("ro"):
            resp = client.get("/jsi18n/")

    assert resp.status_code == 200, resp.content[:200]
    # The catalog JSON escapes non-ASCII (ensure_ascii=True), e.g. ș -> ș.
    # Browsers decode it; the test decodes it again to check readable output.
    body = resp.content.decode().encode("utf-8").decode("unicode_escape")
    for ro_string in (
        '"Stop service": "Oprește serviciul"',
        '"%s actualizare disponibilă"',
        '"Aceasta va reporni serviciul. Continuați?"',
    ):
        assert ro_string in body, ro_string


@pytest.mark.django_db
def test_last_update_info_returns_completed_db_row(client, tmp_path):
    """The last-update endpoint reports the most recent completed row and does
    not error when the git repo is absent (dev machines, non-Pi)."""
    done = UpdateStatus.objects.create(status="completed", completed_at=timezone.now())
    UpdateStatus.objects.create(status="in_progress")

    with mock.patch(
        "core.update_system.views.subprocess.run", side_effect=FileNotFoundError
    ):
        resp = client.get("/updates/last-update/")

    assert resp.status_code == 200
    data = resp.json()
    assert data["git_last_commit"] is None          # no git repo -> graceful None
    assert data["last_successful_update"] is not None
    assert (
        data["last_successful_update"] == done.completed_at.isoformat()
    )


@pytest.mark.django_db
def test_power_shutdown_spawns_detached_poweroff(client):
    """POST /power/shutdown/ fires sudo systemctl poweroff as a detached
    process (survives daphne going down) instead of blocking the request."""
    from unittest import mock

    with mock.patch("core.edupi_core.views.subprocess.Popen") as popen:
        resp = client.post("/power/shutdown/")

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    popen.assert_called_once()
    command = popen.call_args.args[0]
    assert command == ["sudo", "-n", "systemctl", "poweroff"]
    kwargs = popen.call_args.kwargs
    assert kwargs.get("start_new_session") is True

    resp_get = client.get("/power/shutdown/")
    assert resp_get.status_code == 405


@pytest.mark.django_db
def test_power_shutdown_returns_500_on_oserror(client, tmp_path):
    """If poweroff cannot be spawned (sudo missing, policy refused), the
    endpoint reports failure instead of pretending the Pi is shutting down."""
    from unittest import mock

    with mock.patch(
        "core.edupi_core.views.subprocess.Popen", side_effect=OSError("sudo missing")
    ):
        resp = client.post("/power/shutdown/")

    assert resp.status_code == 500
    assert resp.json()["ok"] is False
