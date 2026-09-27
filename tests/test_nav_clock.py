"""Tests for the clock in the navbar.

A teacher should not have to open the LCD's neighbour — or a phone — to know
what time it is. The reading has to be the *Pi's* time, though, not the
browser's: it sits next to the activity timers and the routines, and a clock
that disagrees with them by a time zone is worse than no clock at all. So the
server renders the baseline and `static/js/clock.js` only counts forward from
it, which is what most of these tests pin down.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BASE_TEMPLATE = REPO_ROOT / "templates" / "base.html"
CLOCK_JS = REPO_ROOT / "static" / "js" / "clock.js"
DASHBOARD_DOC = REPO_ROOT / "docs" / "teacher" / "dashboard.md"

WALL_CLOCK = "Europe/Bucharest"

CLOCK_ELEMENT = re.compile(
    r'<time id="nav-clock"[^>]*datetime="(?P<datetime>[^"]+)"'
    r'[^>]*data-epoch="(?P<epoch>-?\d+)"'
    r'[^>]*data-offset="(?P<offset>-?\d+)"[^>]*>(?P<text>[^<]*)</time>'
)


def render_dashboard(client):
    """The dashboard's HTML, which is every page's layout too."""
    resp = client.get("/")

    assert resp.status_code == 200, resp.content[:500]
    return resp.content.decode("utf-8")


@pytest.mark.django_db
def test_the_dashboard_shows_a_clock(client):
    html = render_dashboard(client)

    match = CLOCK_ELEMENT.search(html)

    assert match, "no <time id='nav-clock'> in the dashboard"
    assert re.fullmatch(r"\d\d:\d\d:\d\d", match.group("text").strip())


@pytest.mark.django_db
def test_the_clock_reads_the_pi_clock(client, settings):
    """The reading is the Pi's local time, in the zone it is configured with.

    Overriding the zone moves the rendered reading and the offset it is ticked
    from, which is the whole point: the navbar clock, the LCD and the activity
    timers are then on one clock.
    """
    settings.TIME_ZONE = WALL_CLOCK
    html = render_dashboard(client)

    match = CLOCK_ELEMENT.search(html)
    assert match

    from django.utils import timezone

    local = timezone.localtime()
    expected = local.strftime("%H:%M:%S")

    def day_seconds(stamp: str) -> int:
        hours, minutes, seconds = (int(part) for part in stamp.split(":"))
        return hours * 3600 + minutes * 60 + seconds

    # A second may tick between the render and this line, so allow the two
    # readings to differ by a tick; the wrap at midnight is what the modulo is
    # for.
    rendered = day_seconds(match.group("text").strip())
    difference = abs(rendered - day_seconds(expected)) % 86400
    assert min(difference, 86400 - difference) <= 2, (match.group("text"), expected)

    # And the offset the script will tick from is this zone's, not UTC's.
    offset = int(match.group("offset"))
    actual = local.utcoffset().total_seconds()
    assert offset == actual, "the clock is ticked from the wrong offset"


@pytest.mark.django_db
def test_the_baseline_is_an_instant_not_a_string(client):
    """`data-epoch` is a Unix timestamp, so nothing has to parse a date string.

    Browsers disagree about which date strings they accept — the obvious
    `datetime` attribute, rendered with `c`, carries microseconds, which is
    exactly the kind of value one of them rejects.
    """
    html = render_dashboard(client)

    match = CLOCK_ELEMENT.search(html)
    assert match

    from django.utils import timezone

    epoch = int(match.group("epoch"))
    now = timezone.now().timestamp()

    assert abs(epoch - now) < 60

    # The attribute for a reader is still there, and still ISO 8601.
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d.*", match.group("datetime"))


def test_the_script_never_reads_the_browser_clock():
    """Every way of asking the browser for the time is banned here.

    `new Date()` with no argument, `getHours()`, `getMinutes()`,
    `getSeconds()`, `toLocaleTimeString()` — each reads the *viewer's* clock,
    which on a laptop set to another zone is not the room's. Only the UTC
    getters are allowed, against the server's own baseline.
    """
    source = CLOCK_JS.read_text(encoding="utf-8")

    for banned in [
        "toLocaleTimeString",
        "toLocaleDateString",
        "getHours(",
        "getMinutes(",
        "getSeconds(",
    ]:
        assert banned not in source, f"clock.js reads the browser clock via {banned}"

    assert "getUTCHours()" in source
    assert "getUTCMinutes()" in source
    assert "getUTCSeconds()" in source
    assert "Math.round(" not in source, "the reading must not be rounded"


def test_the_script_ticks_from_what_the_server_rendered():
    source = CLOCK_JS.read_text(encoding="utf-8")

    assert "getElementById('nav-clock')" in source
    assert "'data-epoch'" in source
    assert "'data-offset'" in source
    # Faster than the second it shows, so the reading is never a whole second
    # late, and written only when it changes, so that costs no DOM churn.
    assert re.search(r"setInterval\(tick, (\d+)\)", source)
    interval = int(re.search(r"setInterval\(tick, (\d+)\)", source).group(1))
    assert 0 < interval < 1000
    assert "if (text !== shown)" in source


def test_the_element_carries_all_three_values():
    """Guarded in the template as well, so the render is complete even before
    the script runs."""
    text = BASE_TEMPLATE.read_text(encoding="utf-8")

    assert 'id="nav-clock"' in text
    assert "{% now 'c' %}" in text
    assert "{% now 'U' %}" in text
    assert "{% now 'Z' %}" in text
    assert '{% now "H:i:s" %}' in text


def test_the_clock_ships_on_every_page():
    """It is in the shared layout, loaded outside any block — a page that
    extends base.html gets the clock without asking for it."""
    text = BASE_TEMPLATE.read_text(encoding="utf-8")

    assert "{% static 'js/clock.js' %}" in text
    assert text.index("js/clock.js") < text.index("{% block extra_js %}")


def test_the_clock_gives_up_the_navbar_on_a_phone():
    """The navbar wraps on a phone, and the clock is the piece worth dropping
    first — the rest of the row is navigation."""
    text = BASE_TEMPLATE.read_text(encoding="utf-8")

    assert "hidden sm:inline-block" in text
    assert "tabular-nums" in text, "a ticking clock must not jitter the layout"


def test_the_manual_documents_the_clock():
    text = DASHBOARD_DOC.read_text(encoding="utf-8")

    assert re.search(r"[Cc]lock", text)
    assert "navbar" in text.lower()
