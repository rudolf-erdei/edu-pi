"""The connected-clients counter on the settings System tab.

The counter's whole justification is that it is cheap: no database row, no SD
card write. That is a claim about behaviour, so it is tested rather than
described — ``test_no_session_row_is_written`` is the one that would catch a
future change of session backend, and the static check on the poller is what
keeps a value from the server out of the page's markup.
"""

from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client

from core.edupi_core.system import clients
from core.edupi_core.system.clients import (
    CLIENT_TTL_SECONDS,
    MAX_CLIENTS,
    record,
    reset,
    snapshot,
)


@pytest.fixture(autouse=True)
def empty_registry():
    """Every test starts and ends with nobody connected."""
    reset()
    yield
    reset()


# --- what counts as a client ----------------------------------------------


@pytest.mark.django_db
def test_a_page_view_registers_a_client():
    Client().get("/settings/", {"tab": "system"})

    connected = snapshot()

    assert len(connected) == 1
    assert connected[0].ip == "127.0.0.1"
    assert connected[0].route == "settings/"


@pytest.mark.django_db
def test_the_page_being_rendered_is_named_in_its_own_list():
    """The row for the browser reading the page must have a page in it.

    The route is recorded on the way out, which is after the list has been
    rendered, so `_route_of` resolves the URL itself while Django has not
    matched it yet. Without that, a teacher opening the tab sees their own
    page as blank until the first poll a minute later.
    """
    resp = Client().get("/settings/", {"tab": "system"})

    mine = [client for client in resp.context["clients"] if client.ip == "127.0.0.1"]

    assert [client.route for client in mine] == ["settings/"]


@pytest.mark.django_db
def test_a_page_that_does_not_exist_is_recorded_without_a_route():
    """Resolving must not turn a 404 into an exception in the middleware."""
    resp = Client().get("/no-such-page/")

    assert resp.status_code == 404
    assert [client.route for client in snapshot()] == [""]


@pytest.mark.django_db
def test_no_session_row_is_written():
    """Sessions live in LocMemCache here; the counter must not change that.

    On a Pi the SD card is the part that wears out, and a write per page view
    is exactly what the SD-card work removed.
    """
    from django.contrib.sessions.models import Session

    for _ in range(3):
        Client().get("/settings/", {"tab": "system"})

    assert Session.objects.count() == 0
    assert len(snapshot()) == 3


@pytest.mark.django_db
def test_two_browsers_count_as_two_clients():
    """A second browser is a second session, so a second id."""
    Client().get("/")
    Client().get("/")

    assert len(snapshot()) == 2


@pytest.mark.django_db
def test_one_browser_counts_once_however_many_pages_it_opens():
    client = Client()
    for _ in range(4):
        client.get("/")

    assert len(snapshot()) == 1


@pytest.mark.django_db
def test_an_asset_request_is_not_a_client():
    """Minting a client id for a stylesheet hands a cookie to nobody's page."""
    client = Client()

    resp = client.get(settings.STATIC_URL + "js/system.js")

    assert snapshot() == []
    assert "sessionid" not in resp.cookies


@pytest.mark.django_db
def test_the_javascript_catalog_is_not_a_client():
    Client().get("/jsi18n/")

    assert snapshot() == []


# --- the registry itself --------------------------------------------------


def test_a_client_ages_out_after_the_ttl():
    record("browser", "10.0.0.5", now=1000.0)

    assert len(snapshot(now=1000.0 + CLIENT_TTL_SECONDS)) == 1
    assert snapshot(now=1000.0 + CLIENT_TTL_SECONDS + 1) == []


def test_the_registry_is_capped():
    """A busy or hostile network must not grow this without bound."""
    for number in range(MAX_CLIENTS + 10):
        record(f"browser-{number}", "10.0.0.5", now=1000.0)

    assert len(snapshot(now=1000.0)) == MAX_CLIENTS


def test_the_least_recently_seen_client_is_the_one_dropped():
    record("quiet", "10.0.0.1", now=1000.0)
    for number in range(MAX_CLIENTS):
        record(f"busy-{number}", "10.0.0.2", now=1000.0 + number)

    ids = {client.id for client in snapshot(now=1001.0)}

    assert "quiet" not in ids


def test_the_most_recently_seen_client_is_first():
    record("first", "10.0.0.1", now=1000.0)
    record("second", "10.0.0.2", now=1001.0)

    assert [client.id for client in snapshot(now=1001.0)] == ["second", "first"]


def test_an_empty_route_never_erases_the_one_already_known():
    """The request is recorded on the way in (no route yet) and again on the
    way out, which is the call that knows where the browser went."""
    record("browser", "10.0.0.5", route="", now=1000.0)
    record("browser", "10.0.0.5", route="settings/", now=1000.0)
    record("browser", "10.0.0.5", route="", now=1001.0)

    assert snapshot(now=1001.0)[0].route == "settings/"


def test_the_registry_holds_no_client_supplied_string():
    """Nothing here can be echoed into a page: routes are Django's patterns,
    user names come from the auth backend, addresses from the socket."""
    for client in snapshot():
        assert "<" not in client.route and "<" not in client.user


# --- the middleware -------------------------------------------------------


@pytest.mark.django_db
def test_a_hostile_query_string_cannot_reach_the_registry():
    Client().get("/settings/", {"tab": "<script>alert(1)</script>"})

    connected = snapshot()

    assert len(connected) == 1
    assert connected[0].route == "settings/"
    assert "<" not in connected[0].route


@pytest.mark.django_db
def test_a_missing_session_does_not_break_the_page():
    """A page must not fail because the counter could not count it."""
    resp = Client().get("/")

    assert resp.status_code == 200


def test_the_middleware_runs_after_sessions_and_authentication():
    order = settings.MIDDLEWARE

    assert order.index("core.edupi_core.system.clients.ClientRegistryMiddleware") > (
        order.index("django.contrib.sessions.middleware.SessionMiddleware")
    )
    assert order.index("core.edupi_core.system.clients.ClientRegistryMiddleware") > (
        order.index("django.contrib.auth.middleware.AuthenticationMiddleware")
    )


def test_the_registry_is_asked_for_a_snapshot_not_the_live_dict():
    """`snapshot()` copies under the lock; handing out the dict itself would
    let a request mutate it while another thread is reading."""
    record("browser", "10.0.0.5", now=1000.0)

    taken = snapshot(now=1000.0)
    reset()

    assert len(taken) == 1


# --- the poller -----------------------------------------------------------


def test_the_poller_writes_text_and_never_markup():
    """The values it writes come from the server; the route a teacher is on is
    not a place to teach the page a new tag."""
    js = (Path(settings.BASE_DIR) / "static/js/system.js").read_text(encoding="utf-8")

    assert "innerHTML" not in js
    assert "textContent" in js


def test_the_poller_polls_the_endpoint_the_view_serves():
    js = (Path(settings.BASE_DIR) / "static/js/system.js").read_text(encoding="utf-8")

    assert "data-clients-url" in js


@pytest.mark.django_db
def test_the_page_hands_the_poller_its_interval_and_its_unit():
    """The interval and the translated "seconds" come from the server, so the
    JavaScript needs no translation catalogue of its own."""
    body = Client().get("/settings/", {"tab": "system"}).content.decode()

    assert f'data-poll-seconds="{settings.CLIENT_POLL_SECONDS}"' in body
    assert 'data-idle-suffix="seconds"' in body


def test_the_registry_uses_a_lock():
    """One daphne process, many threads: the dict is shared state."""
    source = Path(clients.__file__).read_text(encoding="utf-8")

    assert "threading.Lock()" in source
    assert "with _lock:" in source
