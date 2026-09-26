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
    args = popen.call_args.args[0]
    assert args[0:3] == ["sudo", "-n", "bash"]
    assert args[3] == "-c"
    # Primary is `shutdown now` (field-verified); force-cut fallbacks follow.
    script = args[4]
    assert script.startswith("shutdown now;")
    assert "sleep 60;" in script
    assert "systemctl poweroff -f" in script
    assert "sysrq-trigger" in script  # hard power-off last resort
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


# --- CSRF contract for the Updates tab ------------------------------------
#
# The Updates tab POSTs to /updates/start/ from JavaScript. Django enforces
# CSRF on that route, so the request MUST carry an X-CSRFToken header. When it
# does not, Django answers 403 "CSRF token missing" — and because that body is
# HTML, update.js's `res.json().catch(() => ({}))` yields {} and the teacher
# sees the useless generic alert "Server error".
#
# The rest of the suite could not catch this: Django's test client defaults to
# enforce_csrf_checks=False, so every existing POST test passed regardless.


def test_update_js_sends_csrf_token_to_start_endpoint():
    """Pin the CSRF header on the startUpdate() fetch.

    This is a static check of the shipped JavaScript because the defect was
    purely client-side: the server was correct all along and answered 403 as
    designed. Reading the source is the only automated way to keep the header
    from being dropped again.
    """
    from pathlib import Path

    from django.conf import settings

    js = (Path(settings.BASE_DIR) / "static/js/update.js").read_text(encoding="utf-8")
    start_fn = js[js.index("async function startUpdate"):js.index("function connectWebSocket")]

    assert "/start/" in start_fn, "startUpdate should POST to the start endpoint"
    assert "X-CSRFToken" in start_fn, (
        "startUpdate() must send the X-CSRFToken header or Django answers 403 "
        "and the UI shows 'Server error'"
    )
    assert "credentials" in start_fn, (
        "the CSRF cookie is only sent on a same-origin credentialled request"
    )


@pytest.mark.django_db
def test_start_update_rejects_post_without_csrf_token():
    """Server side of the same contract: a tokenless POST is refused.

    Documents *why* the JavaScript must send the header, so the behavior is
    intentional and visible rather than surprising.
    """
    from django.test import Client

    csrf_client = Client(enforce_csrf_checks=True)
    resp = csrf_client.post("/updates/start/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_start_update_accepts_post_with_valid_csrf_token(tmp_path):
    """A POST carrying cookie + header passes CSRF and starts the update."""
    from django.middleware.csrf import get_token
    from django.test import Client, RequestFactory

    # get_token() is the public CSRF API and sets request.META['CSRF_COOKIE'].
    # Avoids rendering a page just to obtain the cookie (which would need the
    # collectstatic manifest that only exists on a deployed install).
    token = get_token(RequestFactory().get("/"))

    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.cookies["csrftoken"] = token

    with mock.patch("core.update_system.views.STATUS_FILE", tmp_path / "status.json"), mock.patch(
        "core.update_system.views.write_trigger_file"
    ) as trigger:
        resp = csrf_client.post("/updates/start/", headers={"x-csrftoken": token})

    assert resp.status_code == 200, resp.content
    assert trigger.call_count == 1


# --- the trigger file and the directory it lives in ------------------------
#
# /run is a tmpfs and is recreated by the root daemon after every boot, so the
# directory can end up root-only while the web app runs as the service user.
# That made every web update fail with "Permission denied: /run/tinko-update/
# trigger" on any Pi that had been rebooted since it was set up.


def test_trigger_write_repairs_directory_and_retries():
    """A refused first write repairs the directory and writes again."""
    from core.update_system import views

    calls = []

    def fake_write(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise PermissionError(13, "Permission denied")

    with mock.patch.object(views, "_write_trigger", side_effect=fake_write), mock.patch.object(
        views, "_repair_run_directory"
    ) as repair:
        views.write_trigger_file(7)

    assert len(calls) == 2, "the write must be retried after the repair"
    assert calls[0] == calls[1], "the retry must carry the same payload"
    assert repair.call_count == 1
    assert calls[0]["update_id"] == "7"


def test_trigger_write_raises_when_the_repair_does_not_help():
    """If the directory is still unwritable the error must reach the view,
    which reports it — silently swallowing it would leave the UI hanging."""
    from core.update_system import views

    with mock.patch.object(
        views, "_write_trigger", side_effect=PermissionError(13, "Permission denied")
    ), mock.patch.object(views, "_repair_run_directory"):
        with pytest.raises(PermissionError):
            views.write_trigger_file(7)


def test_run_directory_repair_uses_sudo_mkdir_and_chmod():
    """The repair must be exactly what the installer's sudoers file allows,
    non-interactively (a password prompt would hang the request)."""
    from pathlib import Path

    from core.update_system import views

    with mock.patch.object(views, "RUN_DIR", Path("/run/tinko-update")), mock.patch(
        "core.update_system.views.subprocess.run"
    ) as run:
        views._repair_run_directory()

    commands = [call.args[0] for call in run.call_args_list]
    # -n: never prompt for a password; a prompt would hang the request.
    assert [cmd[:3] for cmd in commands] == [
        ["sudo", "-n", "mkdir"],
        ["sudo", "-n", "chmod"],
    ]
    assert [cmd[3] for cmd in commands] == ["-p", "777"]
    assert all(cmd[4] == str(views.RUN_DIR) for cmd in commands)
    assert all(call.kwargs["check"] for call in run.call_args_list)


def test_run_directory_repair_never_raises():
    """No sudo (a dev machine), or a failing command, must not break the
    request — the original permission error is the one worth reporting."""
    from core.update_system import views

    with mock.patch("core.update_system.views.subprocess.run", side_effect=OSError("no sudo")):
        views._repair_run_directory()  # must not raise


@pytest.mark.django_db
def test_start_update_reports_an_unwritable_run_directory(client, tmp_path):
    """The message a teacher sees must name the directory, since the fix is a
    one-line command on the Pi."""
    with mock.patch("core.update_system.views.STATUS_FILE", tmp_path / "status.json"), mock.patch(
        "core.update_system.views.write_trigger_file",
        side_effect=PermissionError(13, "Permission denied: '/run/tinko-update/trigger'"),
    ):
        resp = client.post("/updates/start/")

    assert resp.status_code == 500
    error = resp.json()["error"]
    assert "Permission denied" in error
    assert "/run/tinko-update" in error
    assert "chmod 777" in error


def test_daemon_makes_the_run_directory_writable(tmp_path):
    """The daemon owns the directory across reboots, so it is the code that
    has to make it writable — not the installer, which only ran once."""
    from core.update_system import update_daemon

    trigger = tmp_path / "tinko-update" / "trigger"
    with mock.patch.object(update_daemon, "TRIGGER_FILE", trigger), mock.patch.object(
        update_daemon.os, "chmod"
    ) as chmod:
        update_daemon.ensure_directories()

    assert trigger.parent.is_dir()
    chmod.assert_called_once_with(trigger.parent, 0o777)


def test_daemon_survives_a_failed_chmod(tmp_path):
    """The daemon must not die (and take the web update path with it) if the
    directory cannot be chmodded."""
    from core.update_system import update_daemon

    trigger = tmp_path / "tinko-update" / "trigger"
    with mock.patch.object(update_daemon, "TRIGGER_FILE", trigger), mock.patch.object(
        update_daemon.os, "chmod", side_effect=OSError("read-only file system")
    ):
        update_daemon.ensure_directories()

    assert trigger.parent.is_dir()
