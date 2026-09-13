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
