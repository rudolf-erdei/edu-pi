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


@pytest.mark.django_db
def test_hero_leads_with_a_statement_not_the_mascot_greeting(client):
    """The hero is the first thing a teacher reads; it says what the product
    is for, in the app's own words, rather than introducing the character."""
    content = client.get("/").content.decode()

    assert "Welcome to Tinko" in content
    assert "Bring your everyday lessons to life." in content
    assert "Timers, sound levels, routines and music" in content
    assert "Hello, I'm Tinko!" not in content


@pytest.mark.django_db
def test_hero_eyebrow_names_the_school_when_one_is_configured(client):
    """A teacher should recognise their own school in the first line. The
    school name is a setting, so it cannot be hardcoded in the template."""
    from core.plugin_system.settings import SiteSettings

    SiteSettings.set("tinko.global.school_name", "Greenfield School")
    try:
        content = client.get("/").content.decode()
    finally:
        SiteSettings.set("tinko.global.school_name", "")

    assert "Welcome to Tinko · Greenfield School" in content


@pytest.mark.django_db
def test_hero_is_translated_into_romanian(client):
    """gettext falls through silently, so an untranslated hero would render
    English on a Romanian page and nothing else would notice."""
    content = client.get("/", HTTP_ACCEPT_LANGUAGE="ro").content.decode()

    assert "Bine ați venit la Tinko" in content
    assert "Timere, nivelul zgomotului, rutine și muzică" in content


@pytest.mark.django_db
def test_blank_robot_name_falls_back_to_the_product_name(client):
    """A saved empty string is the settings form's idea of "unset". Taken
    literally it blanks the brand in the navbar and the hero eyebrow, so the
    fallback the settings system advertises has to survive an empty row."""
    from core.plugin_system.settings import SiteSettings

    SiteSettings.set("tinko.global.robot_name", "")
    try:
        content = client.get("/").content.decode()
    finally:
        SiteSettings.set("tinko.global.robot_name", "Tinko")

    assert "Welcome to Tinko" in content


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
