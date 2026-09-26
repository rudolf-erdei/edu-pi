"""Uploaded files must be served by the app itself, not only in DEBUG.

The school logo is uploaded through the settings page on a Pi that runs with
DEBUG=False. The upload always worked — the file was written to MEDIA_ROOT and
the setting was saved — but the `<img>` pointing at it got a 404, so the logo
appeared simply not to upload. These tests pin the route that fixes that, and
tie it to the URLs the templates actually emit so the two cannot drift apart.
"""

import re

import pytest
from django.conf import settings
from django.test import override_settings

from core.plugin_system.models import SiteSetting


@pytest.fixture
def media_root(tmp_path):
    """A media directory holding one uploaded logo."""
    logos = tmp_path / "site" / "logos"
    logos.mkdir(parents=True)
    # 1x1 PNG.
    (logos / "logo.png").write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
            "890000000a49444154789c6360000002000100ffff03000006000557bfabd400"
            "00000049454e44ae426082"
        )
    )
    return tmp_path


def test_media_is_served_with_debug_off(client, media_root):
    """The exact case on the Pi: DEBUG=False, a logo on disk."""
    with override_settings(DEBUG=False, MEDIA_ROOT=media_root):
        response = client.get("/media/site/logos/logo.png")

    assert response.status_code == 200, "the uploaded logo must be served"
    assert response["Content-Type"] == "image/png"


@pytest.mark.django_db
def test_the_url_the_setting_stores_is_the_url_that_resolves(client, media_root):
    """The stored value is a path under MEDIA_ROOT; MEDIA_URL + that path is
    what the templates render, so it is what must resolve."""
    setting = SiteSetting.objects.create(
        key="tinko.global.logo_path",
        label="Logo Path",
        setting_type="text",
        value="site/logos/logo.png",
        section="General",
    )

    with override_settings(DEBUG=False, MEDIA_ROOT=media_root):
        response = client.get(f"{settings.MEDIA_URL}{setting.value}")

    assert response.status_code == 200


def test_media_route_is_derived_from_media_url():
    """A hard-coded `media/` in the URLconf would keep working today and
    silently stop matching the moment MEDIA_URL changed, taking the logo with
    it. The pattern is built from the setting, and this pins that."""
    from django.urls import get_resolver

    patterns = [
        pattern.pattern.regex.pattern
        for pattern in get_resolver().url_patterns
        if getattr(pattern, "name", None) == "media"
    ]

    assert len(patterns) == 1, "exactly one media route"
    assert patterns[0].startswith("^" + settings.MEDIA_URL.lstrip("/"))


def test_missing_media_is_404_not_500(client, media_root):
    with override_settings(DEBUG=False, MEDIA_ROOT=media_root):
        response = client.get("/media/site/logos/does-not-exist.png")

    assert response.status_code == 404


def test_media_path_cannot_escape_media_root(client, media_root):
    """`serve` runs safe_join, so a traversal attempt must not reach a file
    outside MEDIA_ROOT — the database lives beside it."""
    (media_root.parent / "secret.txt").write_text("not yours")

    with override_settings(DEBUG=False, MEDIA_ROOT=media_root):
        for attempt in (
            "/media/../secret.txt",
            "/media/..%2fsecret.txt",
            "/media/%2e%2e/secret.txt",
        ):
            response = client.get(attempt)
            assert response.status_code in (400, 404), attempt
            assert b"not yours" not in response.content, attempt


@pytest.mark.django_db
def test_settings_page_points_at_a_served_logo(client, media_root):
    """End to end: save the logo setting, load the settings page, pull the
    image URL out of the HTML and fetch it. This is the loop the teacher
    performs, and the one that appeared to do nothing."""
    SiteSetting.objects.create(
        key="tinko.global.logo_path",
        label="Logo Path",
        setting_type="text",
        value="site/logos/logo.png",
        section="General",
    )

    with override_settings(DEBUG=False, MEDIA_ROOT=media_root):
        page = client.get("/settings/")
        assert page.status_code == 200
        # Only the uploaded logo: the site also ships a static logo.svg, which
        # is served by WhiteNoise and is none of this route's business.
        urls = set(
            re.findall(
                r'src="({}[^"]*)"'.format(re.escape(settings.MEDIA_URL)),
                page.content.decode(),
            )
        )

        assert urls, "the settings page must reference the uploaded logo"
        for url in urls:
            assert client.get(url).status_code == 200, url
