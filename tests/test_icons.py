"""Icon classes need their stylesheet, and that stylesheet must ship locally.

96 icons across the plugin pages use Font Awesome 6's ``fas fa-*`` classes. The
base template loaded Tailwind, daisyUI and Google Fonts, but no Font Awesome
stylesheet, so every ``<i class="fas fa-edit">`` was an empty inline element of
zero width: the button kept its colour and lost its icon (and, on the icon-only
buttons, its only visible content).

The assets are vendored under ``static/vendor/fontawesome/`` rather than
loaded from a CDN because Tinko runs on a classroom LAN that may have no
internet; a CDN link would leave the icons blank exactly when the school has no
connection.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSET_ROOT = REPO_ROOT / "static" / "vendor" / "fontawesome"


def test_base_template_loads_the_local_font_awesome_stylesheet():
    base = (REPO_ROOT / "templates" / "base.html").read_text(encoding="utf-8")

    assert "vendor/fontawesome/css/all.min.css" in base


def test_the_stylesheet_points_at_a_font_that_ships_with_it():
    stylesheet = ASSET_ROOT / "css" / "all.min.css"
    css = stylesheet.read_text(encoding="utf-8")

    assert "fa-solid-900.woff2" in css
    assert (ASSET_ROOT / "webfonts" / "fa-solid-900.woff2").is_file()
