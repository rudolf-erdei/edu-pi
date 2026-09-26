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

import os
import subprocess
import sys
from pathlib import Path

import polib
import pytest

from compile_translations import compile_po_files, find_locale_dirs

REPO_ROOT = Path(__file__).resolve().parent.parent

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


def test_compiling_needs_no_system_gettext(tmp_path):
    """Prove it rather than assume it: the compiler runs with an empty PATH.

    GNU gettext (which provides ``msgfmt``) is not installed on a Tinko Pi and
    nothing installs it, so anything that shells out to it cannot be what the
    deploy compiles with. Compiling here with PATH emptied means msgfmt is not
    merely unused but unreachable.
    """
    locale_dir = tmp_path / "locale" / "ro" / "LC_MESSAGES"
    locale_dir.mkdir(parents=True)
    _write_po(locale_dir, "django.po", {"Dashboard": "Panou"})

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pathlib import Path;"
            "import compile_translations as compiler;"
            f"compiler.compile_po_files([Path(r'{locale_dir}')])",
        ],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PATH": ""},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (locale_dir / "django.mo").exists(), "no .mo was written"


@pytest.mark.parametrize("script", ["update.sh", "update-web.sh", "install-raspberry-pi.sh"])
def test_the_deploy_compiles_with_the_repositorys_own_compiler(script):
    """The deploy must not depend on a tool it does not install.

    It called ``django-admin compilemessages``, which needs ``msgfmt`` from the
    gettext package; gettext is installed on neither a Pi nor by the install
    script, so the interface catalogue stopped being compiled there and the
    update reported translations compiled while the pages kept the old text.
    """
    text = (REPO_ROOT / script).read_text(encoding="utf-8")
    code = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )

    assert "compile_translations.py" in code, (
        f"{script} does not run the project's own compiler, so no catalogue is "
        "compiled on the Pi"
    )
    assert "compilemessages" not in code and "msgfmt" not in code, (
        f"{script} compiles via django-admin compilemessages, which needs GNU "
        "msgfmt — nothing installs gettext, so this fails on every Pi"
    )
