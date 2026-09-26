"""Compiled catalogues must land in the .mo file their .po names.

Django loads ``django.mo`` for Python and templates and ``djangojs.mo`` for
JavaScriptCatalog, so the two living side by side in one directory is the
point. ``compile_translations.py`` used to write every ``.po`` it found to
``django.mo``, so the last one compiled in a directory won — and since
``djangojs.po`` sorts after ``django.po``, one run replaced the whole interface
catalogue with the twenty strings the browser needs. Romanian pages then
rendered in English and nothing failed, because a missing msgid is not an error
in gettext.
"""

from pathlib import Path

import polib
import pytest

from compile_translations import compile_po_files, find_locale_dirs

ENTRY = """
msgid "%(id)s"
msgstr "%(text)s"
"""


def _write_po(directory: Path, name: str, entries: dict) -> Path:
    body = "".join(
        ENTRY % {"id": msgid, "text": msgstr} for msgid, msgstr in entries.items()
    )
    path = directory / name
    path.write_text(
        'msgid ""\n'
        'msgstr ""\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        "\n" + body,
        encoding="utf-8",
    )
    return path


@pytest.fixture
def locale_dir(tmp_path):
    """A locale directory with the two catalogues Django expects together."""
    directory = tmp_path / "locale" / "ro" / "LC_MESSAGES"
    directory.mkdir(parents=True)
    _write_po(directory, "django.po", {"Dashboard": "Panou", "Settings": "Setări"})
    _write_po(directory, "djangojs.po", {"Save": "Salvează"})
    return directory


def test_each_catalogue_gets_its_own_mo(locale_dir):
    compile_po_files([locale_dir])

    interface = polib.mofile(str(locale_dir / "django.mo"))
    browser = polib.mofile(str(locale_dir / "djangojs.mo"))

    assert sorted(entry.msgid for entry in interface) == ["Dashboard", "Settings"]
    assert [entry.msgid for entry in browser] == ["Save"]


def test_the_javascript_catalogue_cannot_replace_the_interface_one(locale_dir):
    """The failure that made Romanian pages render in English."""
    compile_po_files([locale_dir])

    interface = polib.mofile(str(locale_dir / "django.mo"))

    assert "Save" not in [entry.msgid for entry in interface]
    assert "Dashboard" in [entry.msgid for entry in interface]


def test_the_project_locale_directories_are_discovered():
    dirs = find_locale_dirs(Path(__file__).resolve().parent.parent)

    assert dirs[0].name == "locale"
    # The plugins each keep their own catalogues.
    assert any(path.parts[-3:-1] == ("edupi", "noise_monitor") for path in dirs)
