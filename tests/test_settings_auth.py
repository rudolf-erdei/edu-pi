"""The PIN gate: storage, brute-force counting, idle sessions, safe redirects."""

import time

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, RequestFactory

from core.edupi_core import settings_auth
from core.plugin_system.models import SiteSetting


@pytest.fixture(autouse=True)
def _empty_cache():
    """The PIN helpers cache values; DB rollback does not roll the cache back."""
    cache.clear()
    yield
    cache.clear()


def _request(path="/settings/", ip="10.0.0.5"):
    request = RequestFactory().get(path)
    request.META["REMOTE_ADDR"] = ip
    request.session = {}
    return request


@pytest.mark.django_db
def test_no_pin_means_not_configured():
    assert settings_auth.pin_is_configured() is False


@pytest.mark.django_db
def test_set_pin_stores_a_hash_not_the_pin():
    settings_auth.set_pin("1234")

    row = SiteSetting.objects.get(key=settings_auth.PIN_SETTING_KEY)
    assert row.value != "1234"
    assert "1234" not in row.value
    assert settings_auth.pin_is_configured() is True


@pytest.mark.django_db
def test_verify_pin_accepts_only_the_stored_pin():
    settings_auth.set_pin("1234")

    assert settings_auth.verify_pin("1234") is True
    assert settings_auth.verify_pin("4321") is False
    assert settings_auth.verify_pin("") is False


@pytest.mark.django_db
def test_clear_pin_returns_the_device_to_first_run():
    settings_auth.set_pin("1234")

    settings_auth.clear_pin()

    assert settings_auth.pin_is_configured() is False
    assert not SiteSetting.objects.filter(key=settings_auth.PIN_SETTING_KEY).exists()


@pytest.mark.django_db
def test_five_failures_lock_that_ip_out():
    request = _request()

    for _ in range(settings_auth.MAX_FAILURES):
        settings_auth.record_failure(request)

    assert settings_auth.is_locked_out(request) is True
    other_ip = _request(ip="10.0.0.6")
    assert settings_auth.is_locked_out(other_ip) is False


@pytest.mark.django_db
def test_a_successful_login_clears_the_counter():
    request = _request()
    settings_auth.record_failure(request)

    settings_auth.clear_failures(request)

    assert settings_auth.is_locked_out(request) is False


@pytest.mark.django_db
def test_a_session_within_the_idle_window_is_authenticated():
    request = _request()
    request.session[settings_auth.SESSION_KEY] = time.time()

    assert settings_auth.is_settings_authenticated(request) is True


@pytest.mark.django_db
def test_an_idle_session_expires():
    request = _request()
    request.session[settings_auth.SESSION_KEY] = (
        time.time() - settings_auth.IDLE_SECONDS - 1
    )

    assert settings_auth.is_settings_authenticated(request) is False
    assert settings_auth.SESSION_KEY not in request.session


@pytest.mark.django_db
def test_a_superuser_passes_the_gate_without_a_pin():
    request = _request()
    request.user = get_user_model().objects.create_superuser(
        "root", "root@example.com", "secret123"
    )

    assert settings_auth.is_settings_authenticated(request) is True


@pytest.mark.django_db
def test_safe_next_keeps_same_host_paths():
    request = RequestFactory().get("/settings/login/")

    assert settings_auth.safe_next(request, "/settings/?tab=system") == (
        "/settings/?tab=system"
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "hostile", ["https://evil.example/", "//evil.example/", "javascript:alert(1)"]
)
def test_safe_next_rejects_other_origins(hostile):
    request = RequestFactory().get("/settings/login/")

    assert settings_auth.safe_next(request, hostile) == "/settings/"


@pytest.mark.django_db
def test_safe_next_with_no_value_goes_to_settings():
    request = RequestFactory().get("/settings/login/")

    assert settings_auth.safe_next(request, None) == "/settings/"


from core.edupi_core.auth_views import SettingsPinSetupForm


@pytest.mark.django_db
def test_an_unset_pin_sends_the_login_page_to_setup():
    resp = Client().get("/settings/login/")

    assert resp.status_code == 302
    assert resp.url == "/settings/setup/"


@pytest.mark.django_db
def test_setup_sets_the_pin_signs_in_and_redirects_to_next():
    client = Client()

    resp = client.post(
        "/settings/setup/",
        {"pin": "1234", "confirm": "1234", "next": "/settings/?tab=system"},
    )

    assert resp.status_code == 302
    assert resp.url == "/settings/?tab=system"
    assert settings_auth.pin_is_configured() is True
    assert client.session[settings_auth.SESSION_KEY]


@pytest.mark.django_db
def test_setup_cannot_overwrite_an_existing_pin():
    settings_auth.set_pin("1234")

    resp = Client().post("/settings/setup/", {"pin": "9999", "confirm": "9999"})

    assert resp.status_code == 302
    assert resp.url == "/settings/login/"
    assert settings_auth.verify_pin("1234") is True


@pytest.mark.django_db
def test_setup_rejects_a_mismatched_confirmation():
    response = Client().post(
        "/settings/setup/", {"pin": "1234", "confirm": "5678"}
    )

    assert response.status_code == 200
    assert settings_auth.pin_is_configured() is False


@pytest.mark.django_db
def test_pin_must_be_digits_only():
    form = SettingsPinSetupForm({"pin": "12ab", "confirm": "12ab"})

    assert form.is_valid() is False
    assert "pin" in form.errors


@pytest.mark.django_db
def test_the_correct_pin_opens_settings():
    settings_auth.set_pin("1234")
    client = Client()

    resp = client.post("/settings/login/", {"pin": "1234"})

    assert resp.status_code == 302
    assert resp.url == "/settings/"
    assert client.session[settings_auth.SESSION_KEY]


@pytest.mark.django_db
def test_a_wrong_pin_stays_on_the_login_page():
    settings_auth.set_pin("1234")
    client = Client()

    resp = client.post("/settings/login/", {"pin": "0000"})

    assert resp.status_code == 200
    assert settings_auth.SESSION_KEY not in client.session


@pytest.mark.django_db
def test_the_login_page_is_locked_after_five_failures():
    settings_auth.set_pin("1234")
    client = Client()

    for _ in range(settings_auth.MAX_FAILURES):
        client.post(
            "/settings/login/", {"pin": "0000"}, REMOTE_ADDR="10.0.0.5"
        )

    resp = client.post("/settings/login/", {"pin": "1234"}, REMOTE_ADDR="10.0.0.5")

    assert resp.status_code == 200
    assert settings_auth.SESSION_KEY not in client.session


@pytest.mark.django_db
def test_logout_is_post_only_and_clears_the_session():
    settings_auth.set_pin("1234")
    client = Client()
    client.post("/settings/login/", {"pin": "1234"})

    assert client.get("/settings/logout/").status_code == 405
    resp = client.post("/settings/logout/")

    assert resp.status_code == 302
    assert settings_auth.SESSION_KEY not in client.session


@pytest.mark.django_db
def test_a_superuser_opens_settings_without_a_pin():
    settings_auth.set_pin("1234")
    client = Client()
    user = get_user_model().objects.create_superuser(
        "root", "root@example.com", "secret123"
    )
    client.force_login(user)

    assert client.get("/settings/").status_code == 200


PROTECTED_URLS = [
    "/settings/",
    "/settings/system/clients/",
    "/settings/system/backup/",
    "/settings/system/clean/",
    "/settings/system/vacuum/",
    "/updates/check/",
    "/updates/start/",
    "/updates/last-update/",
]


@pytest.mark.django_db
@pytest.mark.parametrize("url", PROTECTED_URLS)
def test_an_anonymous_client_is_sent_to_login(url):
    resp = Client().get(url)

    assert resp.status_code == 302
    assert resp.url.startswith("/settings/login/?next=")


@pytest.mark.django_db
def test_a_logged_in_session_reaches_the_settings_page():
    settings_auth.set_pin("1234")
    client = Client()
    client.post("/settings/login/", {"pin": "1234"})

    assert client.get("/settings/").status_code == 200


@pytest.mark.django_db
def test_the_update_status_poll_answers_json_after_login():
    settings_auth.set_pin("1234")
    client = Client()
    client.post("/settings/login/", {"pin": "1234"})

    resp = client.get("/updates/status/")

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/json")


from io import StringIO

from django.core.management import call_command


@pytest.mark.django_db
def test_reset_settings_pin_forgets_the_pin():
    settings_auth.set_pin("1234")
    out = StringIO()

    call_command("reset_settings_pin", stdout=out)

    assert settings_auth.pin_is_configured() is False
    assert "cleared" in out.getvalue().lower()


@pytest.mark.django_db
def test_reset_settings_pin_is_quiet_when_nothing_is_set():
    out = StringIO()

    call_command("reset_settings_pin", stdout=out)

    assert "no settings pin" in out.getvalue().lower()


# --- review fixes ---------------------------------------------------------


@pytest.mark.django_db
def test_a_refused_post_does_not_redirect_back_to_a_post_only_url():
    """A login redirect turns POST into GET; do not replay it at the action."""
    from urllib.parse import parse_qs, urlsplit

    resp = Client().post("/settings/system/clean/")

    assert resp.status_code == 302
    assert parse_qs(urlsplit(resp.url).query)["next"] == ["/settings/"]


@pytest.mark.django_db
def test_a_refused_get_still_remembers_where_it_was_going():
    from urllib.parse import parse_qs, urlsplit

    resp = Client().get("/settings/", {"tab": "system"})

    assert resp.status_code == 302
    assert parse_qs(urlsplit(resp.url).query)["next"] == [
        "/settings/?tab=system"
    ]


@pytest.mark.django_db
def test_the_pin_is_read_from_the_database_not_a_stale_cache():
    """`reset_settings_pin` runs in another process; its cache delete is local.

    The running server must notice the row is gone, not keep the cached hash.
    """
    settings_auth.set_pin("1234")
    assert settings_auth.pin_is_configured() is True  # warm the cache
    SiteSetting.objects.filter(key=settings_auth.PIN_SETTING_KEY).delete()

    assert settings_auth.pin_is_configured() is False
    assert settings_auth.verify_pin("1234") is False


@pytest.mark.django_db
def test_claim_pin_never_overwrites_an_existing_pin():
    assert settings_auth.claim_pin("1234") is True

    assert settings_auth.claim_pin("9999") is False
    assert settings_auth.verify_pin("1234") is True
    assert settings_auth.verify_pin("9999") is False


@pytest.mark.django_db
def test_setup_does_not_overwrite_a_row_written_by_another_process():
    """The row exists but this process never cached it (setup's TOCTOU case)."""
    from django.contrib.auth.hashers import make_password

    SiteSetting.objects.create(
        key=settings_auth.PIN_SETTING_KEY,
        value=make_password("1234"),
        setting_type="text",
        label="Settings PIN",
        is_system=True,
    )

    resp = Client().post("/settings/setup/", {"pin": "9999", "confirm": "9999"})

    assert resp.status_code == 302
    assert resp.url == "/settings/login/"
    assert settings_auth.verify_pin("1234") is True


@pytest.mark.django_db
def test_the_clients_poll_does_not_keep_the_session_alive():
    request = _request(path="/settings/system/clients/")
    stamp = time.time() - settings_auth.IDLE_SECONDS + 60
    request.session[settings_auth.SESSION_KEY] = stamp

    assert settings_auth.is_settings_authenticated(request) is True
    assert request.session[settings_auth.SESSION_KEY] == stamp


@pytest.mark.django_db
def test_an_ordinary_settings_request_refreshes_the_session():
    request = _request(path="/settings/")
    stamp = time.time() - settings_auth.IDLE_SECONDS + 60
    request.session[settings_auth.SESSION_KEY] = stamp

    assert settings_auth.is_settings_authenticated(request) is True
    assert request.session[settings_auth.SESSION_KEY] > stamp


@pytest.mark.django_db
def test_a_json_client_gets_401_instead_of_an_html_login_page():
    """The Updates tab polls with Accept: application/json; a 302 that fetch
    follows becomes 200 + HTML, which the JavaScript cannot tell from data."""
    resp = Client().get(
        "/settings/system/clients/", headers={"accept": "application/json"}
    )

    assert resp.status_code == 401
    assert resp.json()["error"] == "authentication_required"


@pytest.mark.django_db
def test_the_settings_page_offers_a_way_to_lock_it_again():
    settings_auth.set_pin("1234")
    client = Client()
    client.post("/settings/login/", {"pin": "1234"})

    body = client.get("/settings/").content.decode()

    assert 'action="/settings/logout/"' in body


@pytest.mark.django_db
def test_update_status_stays_readable_without_a_session():
    """The service restart wipes cache-backed sessions.

    The page that is waiting for the update must still be able to read the
    status afterwards, or it sits on "reconnecting" until someone refreshes.
    The status is read-only progress, not settings.
    """
    resp = Client().get(
        "/updates/status/", headers={"accept": "application/json"}
    )

    assert resp.status_code == 200
    assert "status" in resp.json()
