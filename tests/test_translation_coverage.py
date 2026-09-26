"""Every string a plugin shows a teacher must exist in its Romanian catalogue.

gettext is silent about a msgid it cannot find: the call falls through and the
English string is rendered, so a half-translated page looks like a working page
and no test fails. These tests are the thing that notices, at two levels —
the plugins that ship today, and the collector that decides what "used" means,
which is where the false results came from the first time it was written.
"""

from pathlib import Path
import shutil
import subprocess

import polib
import pytest

from compile_translations import compile_po_files
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
def test_the_catalogue_compiles_to_every_string_it_translates(plugin_dir, tmp_path):
    """The catalogue the deploy will load: this .po, through the real compiler.

    Compiled catalogues are build outputs and are no longer tracked — every
    install and update compiles them, so a stale ``.mo`` can no longer sit in
    the repository and ship. What can still be wrong is a ``.po`` the compiler
    cannot turn into a usable catalogue, so this compiles it and reads the
    result back.

    A ``.mo`` already built in the working tree (a developer's, or one left by
    a deploy) is checked too: Django reads the ``.mo``, so a stale build shows
    the old text while the repository has the new — which is how the graph
    strings would have shipped as English.
    """
    po_path = catalogue_path(plugin_dir)
    work = tmp_path / "LC_MESSAGES"
    work.mkdir()
    shutil.copy(po_path, work / po_path.name)

    compile_po_files([work])

    built_fresh = work / po_path.with_suffix(".mo").name
    assert built_fresh.exists(), f"{po_path.name} produced no {built_fresh.name}"
    compiled = {entry.msgid for entry in polib.mofile(str(built_fresh)) if entry.msgid}

    assert compiled == translated_msgids(plugin_dir)

    existing = po_path.with_suffix(".mo")
    if existing.exists():
        assert {entry.msgid for entry in polib.mofile(str(existing)) if entry.msgid} == (
            compiled
        ), f"{existing} is stale - run compile_translations.py"


def test_the_project_catalogue_compiles(tmp_path):
    """Same for the interface catalogue, which no plugin test covers."""
    po_path = PROJECT_ROOT / "locale" / "ro" / "LC_MESSAGES" / "django.po"
    work = tmp_path / "LC_MESSAGES"
    work.mkdir()
    shutil.copy(po_path, work / po_path.name)

    compile_po_files([work])

    compiled = {
        entry.msgid for entry in polib.mofile(str(work / "django.mo")) if entry.msgid
    }
    translated = {
        entry.msgid for entry in polib.pofile(str(po_path)) if entry.msgid and entry.msgstr
    }

    assert translated, "the interface catalogue translates nothing"
    assert compiled == translated


def test_compiled_catalogues_are_not_tracked():
    """They are build outputs, and tracking them costs a stash per translation.

    Every deploy rewrites them, so a tracked ``.mo`` leaves the working tree
    dirty after any translation change; the next update stashes that, and the
    stash is popped only when the pull failed. That is where the field Pi's 79
    stashes came from. ``db.sqlite3`` and ``media/`` were untracked for the same
    reason, and the compile that makes this safe is already running there.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "*.mo"],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    assert tracked.stdout.strip() == "", (
        "compiled catalogues are tracked again:\n"
        f"{tracked.stdout}"
        "Every deploy rewrites them, so this leaves the tree dirty and the next "
        "update stashes the result. Untrack them (`git rm --cached`) and let the "
        "deploy compile."
    )


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
