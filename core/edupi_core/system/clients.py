"""Who is using the dashboard right now, counted in the app's own memory.

Not in the database: the session backend is the cache (``LocMemCache``), so a
visit costs no row, and this registry costs none either. That matters on a
machine whose SD card is the part that wears out — a counter is not worth a
write per request.

The identity is a random id minted here and kept in the session, so two
browsers on one laptop count as two clients and one browser counts as one
however many pages it opens. What is recorded about a request is the route
*pattern* Django resolved (``settings/``), never the raw path, so the registry
holds no client-supplied string at all — nothing that could be echoed back
into a page.

Single process only. The deployment is one daphne process serving HTTP and
WebSocket together, so a module-level dict is the whole registry; a second
worker would each keep its own.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

from django.conf import settings
from django.urls import Resolver404, resolve

SESSION_KEY = "tinko.client_id"

# A browser that has not asked for a page in this long is no longer "connected".
# Long enough that reading a page and thinking about it does not drop it.
CLIENT_TTL_SECONDS = 120.0
# Hard ceiling, so a busy or hostile network cannot grow this without bound.
MAX_CLIENTS = 32

IGNORED_SUFFIXES = ("/favicon.ico", "/jsi18n/")

_lock = threading.Lock()
_clients: dict[str, "Client"] = {}


@dataclass(frozen=True)
class Client:
    """One browser."""

    id: str
    ip: str
    user: str
    route: str
    first_seen: float
    last_seen: float

    def as_dict(self, now: float | None = None) -> dict:
        """A JSON-safe view of this client, for the polling endpoint."""
        now = time.time() if now is None else now
        return {
            "ip": self.ip,
            "user": self.user,
            "route": self.route,
            "idle_seconds": int(max(0.0, now - self.last_seen)),
            "seen_for_seconds": int(max(0.0, now - self.first_seen)),
        }


def record(
    client_id: str,
    ip: str,
    user: str = "",
    route: str = "",
    now: float | None = None,
) -> Client:
    """Note that *client_id* is here, and return the entry it lives in.

    An empty *route* never overwrites a route already known: the request is
    recorded on the way in (when Django has not resolved the URL yet, so that a
    view which raises is still visible) and again on the way out, and the
    second call is the one that knows where the browser went.
    """
    now = time.time() if now is None else now
    with _lock:
        _prune_locked(now)
        client = _clients.get(client_id)
        if client is None:
            if len(_clients) >= MAX_CLIENTS:
                oldest = min(_clients.items(), key=lambda item: item[1].last_seen)
                del _clients[oldest[0]]
            client = Client(
                id=client_id,
                ip=ip,
                user=user,
                route=route,
                first_seen=now,
                last_seen=now,
            )
        else:
            client = Client(
                id=client.id,
                ip=ip or client.ip,
                user=user or client.user,
                route=route or client.route,
                first_seen=client.first_seen,
                last_seen=now,
            )
        _clients[client_id] = client
        return client


def _prune_locked(now: float) -> int:
    """Drop entries that have gone quiet. Caller holds the lock."""
    stale = [
        client_id
        for client_id, client in _clients.items()
        if now - client.last_seen > CLIENT_TTL_SECONDS
    ]
    for client_id in stale:
        del _clients[client_id]
    return len(stale)


def snapshot(now: float | None = None) -> list[Client]:
    """Everyone currently connected, most recently seen first."""
    now = time.time() if now is None else now
    with _lock:
        _prune_locked(now)
        return sorted(_clients.values(), key=lambda c: c.last_seen, reverse=True)


def reset() -> None:
    """Forget everyone. For tests, and for a process that is starting over."""
    with _lock:
        _clients.clear()


def _is_asset(path: str) -> bool:
    """True for requests that are not a page view.

    An asset request must not reach the session: minting a client id on a
    ``/static/`` request would hand out a cookie to a browser that has not
    opened a page yet.
    """
    for prefix in (settings.STATIC_URL, settings.MEDIA_URL):
        if prefix and path.startswith(prefix):
            return True
    return path.endswith(IGNORED_SUFFIXES)


def _route_of(request) -> str:
    """The resolved route pattern (``settings/``), or "" when there is none."""
    match = getattr(request, "resolver_match", None)
    if match is None:
        # Django has not matched the URL yet: this is the middleware's call
        # before the view runs. Resolving it here is what puts a page name in
        # the row of the browser that is *rendering the list right now* — the
        # second call knows the route, but by then the page is already built,
        # so a teacher opening the tab would see their own page as blank until
        # the first poll. The pattern that comes back is Django's, never the
        # path the client sent, which is the property the registry relies on.
        try:
            match = resolve(request.path_info)
        except Resolver404:
            return ""
    return getattr(match, "route", None) or getattr(match, "url_name", None) or ""


def _client_ip(request) -> str:
    """The address the request came from.

    ``REMOTE_ADDR`` only. There is no proxy in front of daphne, so an
    ``X-Forwarded-For`` header would be whatever the client felt like sending —
    a header anyone can forge is worse than no header.
    """
    return request.META.get("REMOTE_ADDR", "") or ""


class ClientRegistryMiddleware:
    """Records each page view in the in-process registry.

    Must be listed after ``SessionMiddleware`` (it stores the client id in the
    session) and after ``AuthenticationMiddleware`` (it records who is signed
    in, when anyone is).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self._touch(request)
        try:
            return self.get_response(request)
        finally:
            # Runs even when the view raises, so a client that hit a 500 is
            # still recorded, and this is the call that knows the route.
            self._touch(request)

    def _touch(self, request) -> None:
        path = getattr(request, "path", "") or ""
        if _is_asset(path):
            return
        session = getattr(request, "session", None)
        if session is None:
            return
        try:
            client_id = session.get(SESSION_KEY)
            if not client_id:
                client_id = uuid.uuid4().hex
                session[SESSION_KEY] = client_id
        except Exception:
            # A session backend that is unavailable must not take the page
            # down with it; the counter simply misses this request.
            return

        user = getattr(request, "user", None)
        record(
            client_id,
            ip=_client_ip(request),
            user=user.get_username() if getattr(user, "is_authenticated", False) else "",
            route=_route_of(request),
        )
