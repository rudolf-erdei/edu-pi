#!/usr/bin/env python
"""Compile .po files to .mo files using polib."""

import polib
from pathlib import Path
from typing import Iterable, List, Optional


def find_locale_dirs(base_dir: Path) -> List[Path]:
    """Every locale directory this project keeps catalogues in.

    Args:
        base_dir: Project root.

    Returns:
        list[Path]: The main locale directory, plus one per plugin that has one.
    """
    locale_dirs = [base_dir / "locale"]

    plugins_dir = base_dir / "plugins"
    if plugins_dir.exists():
        locale_dirs += [
            plugin_locale
            for plugin_locale in plugins_dir.rglob("locale")
            if plugin_locale.is_dir()
        ]

    return locale_dirs


def compile_po_files(locale_dirs: Optional[Iterable[Path]] = None) -> None:
    """Compile every .po under the given locale directories.

    Args:
        locale_dirs: Directories to search. Defaults to the project's own.
    """
    if locale_dirs is None:
        locale_dirs = find_locale_dirs(Path(__file__).parent)

    for locale_dir in locale_dirs:
        locale_dir = Path(locale_dir)
        if not locale_dir.exists():
            print(f"Locale directory not found: {locale_dir}")
            continue

        for po_file in locale_dir.rglob("*.po"):
            # The .mo keeps the .po's own name, because Django loads the two
            # side by side: django.mo for Python and templates, djangojs.mo for
            # JavaScriptCatalog. Writing both to django.mo meant that whichever
            # was compiled last won — and since djangojs.po sorts after
            # django.po, one run of this script replaced the whole interface
            # catalogue with the twenty strings the browser needs, leaving
            # Romanian pages in English.
            mo_file = po_file.with_suffix(".mo")

            po = polib.pofile(po_file)
            po.save_as_mofile(mo_file)
            print(f"Compiled: {po_file} -> {mo_file}")


if __name__ == "__main__":
    compile_po_files()
