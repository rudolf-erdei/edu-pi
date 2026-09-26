"""No template tag may span more than one line.

Django lexes templates with ``re.compile(r"({%.*?%}|{{.*?}}|{#.*?#})")``, which
carries no DOTALL flag, so ``.`` never matches a newline. A tag left open at the
end of a line is therefore not a tag at all, and what happens next depends on
which tag it was:

- ``{% ... %}`` that spanned lines never opened, so a closing tag looking for it
  is orphaned and Django raises ``TemplateSyntaxError``. Loud: the page breaks
  and nobody ships it.
- ``{# ... #}`` and ``{{ ... }}`` that spanned lines are not matched either, so
  they are copied into the output as literal text. Silent: the reader gets the
  template source printed across the page, and every test still passes.

Both had happened in this repository. ``base.html`` printed its own three-line
comment above the message list, and ``home.html`` printed a ``{% trans %}`` tag
inside the "No Apps Installed" card.

This applies to Django templates only. The captive portal in
``wifi-connect/portal.py`` renders with Flask's ``render_template_string``, which
is Jinja2 and does allow a tag to span lines — its templates are deliberately
not covered here.
"""

from pathlib import Path

import pytest
from django.template.loader import render_to_string

PROJECT_ROOT = Path(__file__).resolve().parent.parent

#: Tags that open and close, and the pair that closes each.
DELIMITERS = (("{%", "%}"), ("{{", "}}"), ("{#", "#}"))

TEMPLATE_GLOBS = ("templates/**/*.html", "plugins/**/templates/**/*.html")


def template_files():
    """Every template in the project and its plugins."""
    found = set()
    for pattern in TEMPLATE_GLOBS:
        found.update(PROJECT_ROOT.glob(pattern))
    return sorted(found)


def open_tags(text):
    """Yield the tags a template leaves open at the end of a line.

    Args:
        text: The template source.

    Yields:
        tuple: ``(line number, opener, the line)`` for each unterminated tag.
    """
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # An HTML comment is not a template tag even when it quotes one.
        if stripped.startswith("<!--"):
            continue
        for opener, closer in DELIMITERS:
            # Only the last opener on the line can still be open at its end.
            start = stripped.rfind(opener)
            if start == -1 or stripped.find(closer, start) != -1:
                continue
            yield number, opener, stripped


TEMPLATES = template_files()


def test_the_templates_are_actually_found():
    """Guard the parametrised test below: it proves nothing at zero files."""
    names = {path.name for path in TEMPLATES}

    assert {"base.html", "home.html"} <= names
    assert len(TEMPLATES) > 10


@pytest.mark.parametrize(
    "path", TEMPLATES, ids=lambda path: str(path.relative_to(PROJECT_ROOT))
)
def test_no_template_tag_spans_more_than_one_line(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    offenders = list(open_tags(text))

    assert offenders == [], "tag left open at end of line: " + ", ".join(
        f"line {number} ({opener})" for number, opener, _line in offenders
    )


class TestOpenTags:
    """The detector itself, checked against the two cases that shipped."""

    def test_a_comment_spanning_lines_is_reported(self):
        """The exact shape base.html printed above the message list."""
        text = (
            "        {# Framework messages. The messages context processor was\n"
            "           enabled but nothing rendered the result. #}\n"
        )

        assert [number for number, _o, _l in open_tags(text)] == [1]

    def test_a_trans_tag_spanning_lines_is_reported(self):
        """The exact shape home.html printed inside the card."""
        text = (
            '          {% trans "There are currently no active apps available."\n'
            '          %}\n'
        )

        assert [number for number, _o, _l in open_tags(text)] == [1]

    def test_a_single_line_comment_is_not_reported(self):
        assert list(open_tags("{# fine #}\n")) == []

    def test_a_closed_tag_beside_an_open_one_is_not_reported(self):
        assert list(open_tags('{% trans "Save" %} and {{ name }}\n')) == []

    def test_the_last_tag_on_a_line_is_the_one_checked(self):
        """An earlier tag closing cannot hide a later one left open.

        This is the case that raises TemplateSyntaxError rather than printing:
        the ``if`` never opens, so its closing tag is orphaned.
        """
        assert [number for number, _o, _l in open_tags("{{ closed }} then {% if\n")] == [1]

    def test_a_line_whose_only_tag_closes_is_not_reported(self):
        assert list(open_tags("{% trans 'Save' %}\n")) == []

    def test_an_html_comment_quoting_a_tag_is_not_reported(self):
        assert list(open_tags("<!-- {% trans 'x' -->\n")) == []

    def test_a_comment_tag_body_is_read_normally(self):
        """{% comment %} bodies are prose, so an unbalanced quote in them shows.

        This is why the block in base.html keeps both braces on one line even
        while describing a comment that does not.
        """
        text = "{% comment %}\n  mentions {# ... #} safely\n{% endcomment %}\n"

        assert list(open_tags(text)) == []


def test_the_messages_comment_is_not_printed():
    """The reported symptom: base.html printed its own comment to the reader."""
    html = render_to_string("base.html", {})

    assert "Framework messages" not in html
    assert "{#" not in html


def test_the_empty_state_renders_its_sentence_not_its_tag():
    """home.html printed a {% trans %} tag inside the card."""
    # An empty plugin list is what shows the "No Apps Installed" card.
    html = render_to_string("home.html", {"plugins": []})

    assert "There are currently no active apps available." in html
    assert "{% trans" not in html
