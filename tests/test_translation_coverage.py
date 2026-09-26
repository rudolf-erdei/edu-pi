"""Every string a plugin shows a teacher must exist in its Romanian catalogue.

gettext is silent about a msgid it cannot find: the call falls through and the
English string is rendered, so a half-translated page looks like a working page
and no test fails. These tests are the thing that notices, at two levels —
the plugins that ship today, and the collector that decides what "used" means,
which is where the false results came from the first time it was written.
"""

from pathlib import Path

import polib
import pytest

from translation_audit import (
    DEFAULT_LOCALE,
    catalogue_path,
    discover_plugins,
    missing_msgids,
    python_msgids,
    template_msgids,
    translated_msgids,
    used_msgids,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = PROJECT_ROOT / "plugins"


def _plugin_id(plugin_dir: Path) -> str:
    """Name a plugin for the test report, as ``author/name``."""
    return "/".join(plugin_dir.relative_to(PLUGINS_DIR).parts)


PLUGINS = discover_plugins(PLUGINS_DIR)


def test_the_plugins_are_actually_discovered():
    """Guard the parametrised tests below: none of them proves much at zero."""
    assert {_plugin_id(plugin) for plugin in PLUGINS} == {
        "edupi/activity_timer",
        "edupi/lcd_display",
        "edupi/noise_monitor",
        "edupi/routines",
        "edupi/touch_piano",
    }


@pytest.mark.parametrize("plugin_dir", PLUGINS, ids=_plugin_id)
def test_no_plugin_string_is_left_untranslated(plugin_dir):
    assert missing_msgids(plugin_dir) == []


@pytest.mark.parametrize("plugin_dir", PLUGINS, ids=_plugin_id)
def test_no_catalogue_entry_is_left_empty(plugin_dir):
    """An entry with no msgstr is a msgid that renders in English too."""
    entries = polib.pofile(str(catalogue_path(plugin_dir)))

    assert [entry.msgid for entry in entries if entry.msgid and not entry.msgstr] == []


@pytest.mark.parametrize("plugin_dir", PLUGINS, ids=_plugin_id)
def test_no_catalogue_entry_is_defined_twice(plugin_dir):
    """Two definitions of one msgid leave the .mo free to pick either."""
    entries = polib.pofile(str(catalogue_path(plugin_dir)))
    msgids = [entry.msgid for entry in entries if entry.msgid]

    assert len(msgids) == len(set(msgids))


@pytest.mark.parametrize("plugin_dir", PLUGINS, ids=_plugin_id)
def test_the_compiled_catalogue_matches_its_source(plugin_dir):
    """A .po that was edited but never compiled changes nothing on screen.

    Django reads the .mo, so a stale one means the new translation is in the
    repository and not on the Pi. This is how the graph strings would have
    shipped as English.
    """
    po_path = catalogue_path(plugin_dir)
    mo_path = po_path.with_suffix(".mo")

    assert mo_path.exists(), f"{mo_path} is missing - run compile_translations.py"
    compiled = {entry.msgid for entry in polib.mofile(str(mo_path)) if entry.msgid}
    assert compiled == translated_msgids(plugin_dir)


class TestPythonMsgids:
    """The collector has to read Python the way gettext does."""

    def test_adjacent_literals_are_one_msgid(self):
        """A msgid split across lines reaches gettext as one string."""
        source = (
            "from django.utils.translation import gettext as _\n"
            "seed(\n"
            '    _(\n'
            '        "Let\'s stretch our fingers!\\n"\n'
            '        "Hold up your hands and spread your fingers wide."\n'
            "    )\n"
            ")\n"
        )

        assert python_msgids(source) == {
            "Let's stretch our fingers!\nHold up your hands and spread your fingers wide."
        }

    def test_a_pgettext_context_is_not_a_msgid(self):
        source = "pgettext('month name', 'May')\n"

        assert python_msgids(source) == {"May"}

    def test_both_forms_of_a_plural_are_collected(self):
        source = "ngettext('%d reading', '%d readings', count)\n"

        assert python_msgids(source) == {"%d reading", "%d readings"}

    def test_a_lazy_call_is_collected(self):
        source = 'gettext_lazy("Noise Monitor")\n'

        assert python_msgids(source) == {"Noise Monitor"}

    def test_an_unparseable_file_yields_nothing(self):
        assert python_msgids("def broken(:\n") == set()


class TestTemplateMsgids:
    """The collector has to read both template tags Django offers."""

    def test_an_apostrophe_does_not_truncate_a_double_quoted_msgid(self):
        text = """{% trans "If keys don't work, check the wiring." %}"""

        assert template_msgids(text) == {"If keys don't work, check the wiring."}

    def test_a_single_quoted_msgid_is_read(self):
        assert template_msgids("{% trans 'Save' %}") == {"Save"}

    def test_a_blocktrans_placeholder_becomes_a_gettext_one(self):
        """The template says {{ name }}; the catalogue says %(name)s."""
        text = (
            "{% blocktrans with minutes=chart_window_minutes %}"
            "The last {{ minutes }} minutes."
            "{% endblocktrans %}"
        )

        assert template_msgids(text) == {"The last %(minutes)s minutes."}

    def test_javascript_gettext_is_read(self):
        assert template_msgids('gettext("Updating...")') == {"Updating..."}


class TestSourceFiles:
    """Which files count as asking for a translation."""

    def test_a_catalogue_is_not_a_source_of_msgids(self, tmp_path):
        """The catalogue quotes every msgid, which is not a use of it."""
        plugin = tmp_path / "plugins" / "edupi" / "demo"
        locale = plugin / "locale" / DEFAULT_LOCALE / "LC_MESSAGES"
        locale.mkdir(parents=True)
        (locale / "django.po").write_text(
            'msgid "Dashboard"\nmsgstr "Panou"\n', encoding="utf-8"
        )

        assert used_msgids(plugin) == set()

    def test_a_msgid_quoted_in_a_test_is_not_a_use_of_it(self, tmp_path):
        """A test discussing a msgid would otherwise demand a translation."""
        plugin = tmp_path / "plugins" / "edupi" / "demo"
        plugin.mkdir(parents=True)
        (plugin / "tests.py").write_text(
            '"""Discusses {% trans "Save" %} without using it."""\n', encoding="utf-8"
        )

        assert used_msgids(plugin) == set()

    def test_a_template_in_the_plugin_is_a_use(self, tmp_path):
        plugin = tmp_path / "plugins" / "edupi" / "demo"
        templates = plugin / "templates"
        templates.mkdir(parents=True)
        (templates / "page.html").write_text(
            "{% trans 'Save' %}", encoding="utf-8"
        )

        assert used_msgids(plugin) == {"Save"}


class TestDiscovery:
    def test_a_plugin_without_a_catalogue_is_not_reported(self, tmp_path):
        """Plugins that ship no Romanian catalogue are left alone."""
        plugins = tmp_path / "plugins"
        (plugins / "edupi" / "untranslated").mkdir(parents=True)

        assert discover_plugins(plugins) == []

    def test_a_plugin_with_a_catalogue_is_found(self, tmp_path):
        plugins = tmp_path / "plugins"
        locale = plugins / "edupi" / "demo" / "locale" / DEFAULT_LOCALE / "LC_MESSAGES"
        locale.mkdir(parents=True)
        (locale / "django.po").write_text(
            'msgid "Dashboard"\nmsgstr "Panou"\n', encoding="utf-8"
        )

        assert [path.name for path in discover_plugins(plugins)] == ["demo"]

    def test_a_missing_plugins_directory_is_not_an_error(self, tmp_path):
        assert discover_plugins(tmp_path / "nothing") == []
