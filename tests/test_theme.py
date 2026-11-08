"""The app's default colour is Hunter Green, ``#2c5f34``.

daisyUI 4 reads its palette from CSS custom properties expressed as bare
oklch components, so the brand colour lives in ``base.html`` as ``--p`` in
that form rather than as a hex string. The numbers below are the oklch
equivalent of ``#2c5f34`` (L 43.82%, C 0.0888, H 147.24); changing the brand
colour means changing both and keeping the contrast against white text at or
above 4.5:1.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

HUNTER_GREEN = "#2c5f34"
HUNTER_GREEN_OKLCH = "43.82% 0.0888 147.24"


def test_the_dashboard_theme_uses_hunter_green_as_primary():
    base = (REPO_ROOT / "templates" / "base.html").read_text(encoding="utf-8")

    assert HUNTER_GREEN_OKLCH in base, (
        "base.html must override daisyUI's --p with Hunter Green, or every "
        "primary-coloured surface falls back to daisyUI's blue"
    )


def test_the_favicon_uses_the_brand_colour():
    favicon = (REPO_ROOT / "static" / "images" / "favicon.svg").read_text(
        encoding="utf-8"
    )

    assert HUNTER_GREEN in favicon
