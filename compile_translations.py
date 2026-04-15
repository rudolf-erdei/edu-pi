#!/usr/bin/env python
"""Compile .po files to .mo files using polib."""

import polib
from pathlib import Path


def compile_po_files():
    """Find and compile all .po files in locale directories."""
    base_dir = Path(__file__).parent

    # Compile main locale directory
    locale_dirs = [base_dir / "locale"]

    # Also compile plugin locale directories
    plugins_dir = base_dir / "plugins"
    if plugins_dir.exists():
        for plugin_locale in plugins_dir.rglob("locale"):
            if plugin_locale.is_dir():
                locale_dirs.append(plugin_locale)

    for locale_dir in locale_dirs:
        if not locale_dir.exists():
            print(f"Locale directory not found: {locale_dir}")
            continue

        for po_file in locale_dir.rglob("*.po"):
            # Determine the output .mo file path
            mo_file = po_file.parent / "django.mo"

            # Load the .po file
            po = polib.pofile(po_file)

            # Save as .mo file
            po.save_as_mofile(mo_file)
            print(f"Compiled: {po_file} -> {mo_file}")


if __name__ == "__main__":
    compile_po_files()