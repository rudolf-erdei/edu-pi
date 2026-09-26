"""Tests for the dashboard view.

``home.html`` is the page every teacher lands on, and until now it could not
be rendered under pytest at all: production resolves ``{% static %}`` through
``whitenoise.storage.CompressedManifestStaticFilesStorage``, whose manifest
only exists after a ``collectstatic`` on a deployed install. Any render raised

    ValueError: Missing staticfiles manifest entry for 'images/favicon.svg'

before a single assertion ran, which is why the dashboard and its inline
JavaScript had no coverage. ``config.settings_test`` swaps in a manifest-free
backend; these tests pin that arrangement so the hole cannot reopen.
"""

import pytest


@pytest.mark.django_db
def test_home_page_renders(client):
    """GET / renders the dashboard instead of raising on a missing manifest."""
    resp = client.get("/")

    assert resp.status_code == 200, resp.content[:500]
    assert b"Tinko" in resp.content


@pytest.mark.django_db
def test_home_page_has_csrf_cookie_for_its_post_fetches(client):
    """The dashboard's inline JavaScript POSTs (shutdown) read the csrftoken
    cookie. Django only sets that cookie when the page renders a CSRF token,
    so a page that stopped doing it would silently break those requests the
    same way update.js did."""
    resp = client.get("/")

    assert "csrftoken" in resp.cookies


def test_test_settings_use_a_manifest_free_staticfiles_backend():
    """The suite depends on this: with the manifest backend, no template that
    uses {% static %} can render."""
    from django.conf import settings

    backend = settings.STORAGES["staticfiles"]["BACKEND"]

    assert "Manifest" not in backend, (
        "tests must run without the collectstatic manifest; a manifest "
        "backend makes home.html unrenderable under pytest"
    )
    assert backend == "django.contrib.staticfiles.storage.StaticFilesStorage"


def test_production_settings_still_use_manifest_storage():
    """Guard the other direction: settings_test must not be the only reason
    the manifest backend is intact — production still needs it for cache
    busting and compression. Someone 'fixing' tests by weakening production
    would otherwise go unnoticed."""
    import config.settings as production_settings

    backend = production_settings.STORAGES["staticfiles"]["BACKEND"]

    assert backend == "whitenoise.storage.CompressedManifestStaticFilesStorage"
