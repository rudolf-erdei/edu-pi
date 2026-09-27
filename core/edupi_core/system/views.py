"""Views behind the settings page's System tab.

Three rules hold for all four of them:

- **The destructive two are POST-only.** A GET that deletes rows is a GET that
  a browser, a link preview or a crawler will fire on its own. Django's CSRF
  middleware then does the rest: a page on another origin cannot read the token
  it would need.
- **Nothing here raises at the user.** A refusal or a failure becomes a
  message on the settings page, never a 500.
- **Nothing here needs a login** — the whole site is open, which is recorded in
  ``ISSUES.md``. These endpoints widen that exposure to deleting history and
  downloading the database, and the teacher documentation says so.
"""

from __future__ import annotations

import logging
import shutil

from django.contrib import messages
from django.db import DatabaseError, connection
from django.http import FileResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

from core.edupi_core.system.backup import BackupRefused, build_backup
from core.edupi_core.system.clients import snapshot
from core.edupi_core.system.history import run_clean
from core.edupi_core.system.storage import database_size, human_size

logger = logging.getLogger(__name__)

SYSTEM_TAB = "system"

# How long SQLite waits for the database before giving up on the VACUUM. The
# noise monitor commits a reading every five seconds, and the default five
# seconds of patience would let its commit fail in the middle of the rewrite.
VACUUM_BUSY_TIMEOUT_MS = 30000


def system_tab_url() -> str:
    """Where the System tab lives, for redirects back to it."""
    return f"{reverse('settings')}?tab={SYSTEM_TAB}"


class CleanupFileResponse(FileResponse):
    """A file response that also removes the directory it served from.

    Django has no "the download has finished" hook, so without this the
    snapshot directory would sit in RAM until the next sweep. ``close`` runs
    for a completed download and for a client that disconnected mid-way; the
    sweep is what covers the case where neither happens.
    """

    def __init__(self, *args, cleanup_directory=None, **kwargs):
        self._cleanup_directory = cleanup_directory
        super().__init__(*args, **kwargs)

    def close(self):
        super().close()
        directory = self._cleanup_directory
        self._cleanup_directory = None
        if directory:
            shutil.rmtree(directory, ignore_errors=True)


def system_clients(request):
    """The browsers connected right now, as JSON.

    The System tab renders the same list server-side; this is what the page
    polls to keep it current without a reload.
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    clients = snapshot()
    return JsonResponse(
        {
            "count": len(clients),
            "generated_at": timezone.localtime().isoformat(),
            "clients": [client.as_dict() for client in clients],
        }
    )


def system_backup(request):
    """Build a backup and send it as a download.

    A GET, because it is a download and the browser has to be able to follow a
    link to it. That also means anyone who can reach the dashboard can fetch
    the database without pressing anything — see ``ISSUES.md``.
    """
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    try:
        directory, archive = build_backup()
    except BackupRefused as e:
        messages.error(request, str(e))
        return redirect(system_tab_url())
    except Exception as e:  # Anything at all: report it, never a 500.
        logger.exception("Building the backup failed: %s", e)
        messages.error(
            request,
            _("The backup could not be built. See the log for the reason."),
        )
        return redirect(system_tab_url())

    filename = f"tinko-backup-{timezone.localdate().isoformat()}.zip"
    return CleanupFileResponse(
        open(archive, "rb"),
        as_attachment=True,
        filename=filename,
        cleanup_directory=directory,
    )


def system_clean(request):
    """Delete the history that is past its retention window."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    results = run_clean()
    deleted = sum(result.deleted for result in results)

    if deleted:
        messages.success(
            request,
            ngettext(
                "%(count)s old record was deleted.",
                "%(count)s old records were deleted.",
                deleted,
            )
            % {"count": deleted},
        )
        detail = ", ".join(
            f"{result.label}: {result.deleted}" for result in results if result.deleted
        )
        messages.info(request, detail)
    else:
        # Said plainly, because a button that appears to do nothing looks
        # broken — and "there is nothing old enough" is the usual answer.
        messages.info(request, _("Nothing was old enough to delete."))

    for result in results:
        if result.error:
            logger.error("Cleaning %s failed: %s", result.label, result.error)
            messages.error(
                request,
                _("Could not clean %(label)s: %(error)s")
                % {"label": result.label, "error": result.error},
            )

    return redirect(system_tab_url())


def system_vacuum(request):
    """Compact the database, returning the space of deleted rows to the file.

    Deleting rows in WAL mode frees pages for reuse but never shrinks the file;
    only ``VACUUM`` does, and it does it by rewriting the whole database.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    before = database_size()
    try:
        with connection.cursor() as cursor:
            # PRAGMA takes a literal, not a bound parameter; the value is a
            # constant defined above, not anything that arrived in a request.
            cursor.execute(f"PRAGMA busy_timeout = {VACUUM_BUSY_TIMEOUT_MS}")
            cursor.execute("VACUUM")
    except DatabaseError as e:
        logger.exception("Compacting the database failed: %s", e)
        messages.error(
            request,
            _("Could not compact the database: %(error)s") % {"error": e},
        )
        return redirect(system_tab_url())

    after = database_size()
    if after < before:
        messages.success(
            request,
            _("Database compacted: %(before)s down to %(after)s.")
            % {"before": human_size(before), "after": human_size(after)},
        )
    else:
        messages.info(
            request,
            _("Nothing to reclaim: the database is still %(size)s.")
            % {"size": human_size(after)},
        )
    return redirect(system_tab_url())
