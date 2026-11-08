"""PIN gate for the Settings surface.

The threat model is a student or another device on the school LAN, not an
attacker on the internet. The PIN is a single device-wide secret, stored only
as a hash in ``SiteSetting``. A forgotten PIN is recovered by signing in to
Django admin as a superuser or by running ``reset_settings_pin``; Settings
being locked never stops the dashboard or the plugins from working.

Sessions are in LocMemCache (see ``SESSION_ENGINE``), so a service restart
signs everyone out. That is acceptable here and needs no storage work.
"""

import time
from functools import wraps
from urllib.parse import quote

from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from core.plugin_system.models import SiteSetting
from core.plugin_system.settings import SiteSettings

PIN_SETTING_KEY = "tinko.security.settings_pin_hash"
SESSION_KEY = "settings_authenticated_at"
IDLE_SECONDS = 15 * 60
MAX_FAILURES = 5
FAILURE_WINDOW_SECONDS = 5 * 60

# Server-rendered polls that must not extend the idle window.
REFRESH_EXEMPT_PATHS = ("/settings/system/clients/",)


def _stored_pin_hash():
    """Read the hash straight from the row.

    Not ``SiteSettings.get``: that is a per-process LocMemCache, and
    ``reset_settings_pin`` runs in another process whose cache delete cannot
    reach the server. A cached hash would keep the old PIN usable, and keep
    the setup page hidden, for up to five minutes after a reset.
    """
    return (
        SiteSetting.objects.filter(key=PIN_SETTING_KEY)
        .values_list("value", flat=True)
        .first()
    )


def pin_is_configured() -> bool:
    """True once a PIN hash has been stored."""
    return bool(_stored_pin_hash())


def set_pin(pin: str) -> None:
    """Store *pin* as a hash."""
    SiteSettings.set(PIN_SETTING_KEY, make_password(pin))


def claim_pin(pin: str) -> bool:
    """Store *pin* only if no PIN exists; True when this call stored it.

    Setup is check-then-act: two clients can both see "no PIN" and then both
    write. The unique key turns the second write into an IntegrityError, and
    ``get_or_create`` handles the row appearing between the two statements.
    The caller treats False as "someone else chose the PIN" and goes to login.
    """
    try:
        _, created = SiteSetting.objects.get_or_create(
            key=PIN_SETTING_KEY,
            defaults={
                "value": make_password(pin),
                "setting_type": "text",
                "label": "Settings PIN",
                "is_system": True,
            },
        )
    except IntegrityError:
        return False

    cache.delete(f"site_setting:{PIN_SETTING_KEY}")
    return created


def verify_pin(pin: str) -> bool:
    """True when *pin* matches the stored hash."""
    stored = _stored_pin_hash()
    return bool(stored) and check_password(pin, stored)


def clear_pin() -> None:
    """Forget the PIN, returning the device to first-run setup."""
    SiteSetting.objects.filter(key=PIN_SETTING_KEY).delete()
    cache.delete(f"site_setting:{PIN_SETTING_KEY}")


def _failure_key(request) -> str:
    return f"settings_pin_failures:{request.META.get('REMOTE_ADDR', '')}"


def is_locked_out(request) -> bool:
    """True when this client has failed too often in the window."""
    return (cache.get(_failure_key(request)) or 0) >= MAX_FAILURES


def record_failure(request) -> int:
    """Count one failed attempt and return the running total."""
    key = _failure_key(request)
    failures = (cache.get(key) or 0) + 1
    cache.set(key, failures, FAILURE_WINDOW_SECONDS)
    return failures


def clear_failures(request) -> None:
    """Forget this client's failed attempts."""
    cache.delete(_failure_key(request))


def is_settings_authenticated(request) -> bool:
    """True for a live settings session or a signed-in superuser.

    A live session is refreshed on every allowed request, so the window is
    idle-based rather than absolute.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated and user.is_superuser:
        return True

    stamp = request.session.get(SESSION_KEY)
    if stamp is None:
        return False

    now = time.time()
    try:
        expired = now - float(stamp) > IDLE_SECONDS
    except (TypeError, ValueError):
        expired = True

    if expired:
        request.session.pop(SESSION_KEY, None)
        return False

    # A page that polls itself is not a teacher at the keyboard. The System
    # tab's client list refreshes every 60 s, and counting that as activity
    # would keep an unattended Settings page unlocked all day.
    if request.path not in REFRESH_EXEMPT_PATHS:
        request.session[SESSION_KEY] = now
    return True


def safe_next(request, url: str | None) -> str:
    """Return *url* when it is a same-host relative path, else Settings."""
    if url and url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return url
    return reverse("settings")


def settings_login_required(view):
    """Send an unauthenticated client to the login page, remembering where."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if is_settings_authenticated(request):
            return view(request, *args, **kwargs)

        # A fetch() follows a 302 and resolves with the login page at 200,
        # which the Updates tab's JavaScript cannot tell from data — it would
        # sit on "Updating…" forever. JSON clients get an answer they can act
        # on instead of a silent redirect.
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse(
                {"error": "authentication_required"}, status=401
            )

        # A redirect turns POST into GET. Replaying a refused POST as a GET on
        # a POST-only URL answers 405, and on /updates/start/ would start an
        # update from a link. Only safe requests remember their target.
        if request.method in ("GET", "HEAD"):
            target = request.get_full_path()
        else:
            target = reverse("settings")
        login_url = reverse("settings_login")
        return redirect(f"{login_url}?next={quote(target)}")

    return wrapped
