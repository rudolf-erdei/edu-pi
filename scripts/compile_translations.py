#!/usr/bin/env python3
"""
Translation compiler for EDU-PI plugins.

This script compiles .po translation files to .mo binary format.
It can compile translations for all plugins or a specific plugin.

Usage:
    python scripts/compile_translations.py                    # Compile all plugins
    python scripts/compile_translations.py --plugin PLUGIN  # Compile specific plugin
    python scripts/compile_translations.py --list            # List available plugins
"""

import argparse
import os
import sys
from pathlib import Path


def get_available_plugins(plugins_dir: Path) -> list:
    """Discover all plugins with translation files."""
    plugins = []

    if not plugins_dir.exists():
        return plugins

    for author_dir in plugins_dir.iterdir():
        if not author_dir.is_dir():
            continue

        for plugin_dir in author_dir.iterdir():
            if not plugin_dir.is_dir():
                continue

            locale_dir = plugin_dir / "locale"
            if locale_dir.exists():
                plugins.append(
                    {
                        "path": plugin_dir,
                        "name": f"{author_dir.name}/{plugin_dir.name}",
                        "languages": [],
                    }
                )

                # Find languages
                for lang_dir in locale_dir.iterdir():
                    if (
                        lang_dir.is_dir()
                        and (lang_dir / "LC_MESSAGES" / "django.po").exists()
                    ):
                        plugins[-1]["languages"].append(lang_dir.name)

    return plugins


def compile_translations(plugin_path: Path) -> dict:
    """Compile translations for a single plugin."""
    try:
        import polib
    except ImportError:
        print("Error: polib is not installed. Install it with: uv add polib")
        return {"success": False, "error": "polib not installed"}

    results = {"success": True, "compiled": [], "errors": []}

    locale_dir = plugin_path / "locale"
    if not locale_dir.exists():
        return {"success": True, "compiled": [], "errors": ["No locale directory"]}

    for lang_dir in locale_dir.iterdir():
        if not lang_dir.is_dir():
            continue

        po_file = lang_dir / "LC_MESSAGES" / "django.po"
        mo_file = lang_dir / "LC_MESSAGES" / "django.mo"

        if not po_file.exists():
            continue

        try:
            # Load and compile PO file
            po = polib.pofile(str(po_file))

            # Save as MO file
            po.save_as_mofile(str(mo_file))

            # Get stats
            total = len(po)
            translated = len([e for e in po if e.translated()])

            results["compiled"].append(
                {
                    "language": lang_dir.name,
                    "total": total,
                    "translated": translated,
                    "percent": (translated / total * 100) if total > 0 else 0,
                    "size": os.path.getsize(mo_file),
                }
            )

        except Exception as e:
            results["errors"].append(f"{lang_dir.name}: {str(e)}")
            results["success"] = False

    return results


def print_results(plugin_name: str, results: dict):
    """Print compilation results for a plugin."""
    print(f"\n{'=' * 60}")
    print(f"Plugin: {plugin_name}")
    print("=" * 60)

    if not results["success"]:
        print(f"  Status: FAILED")
        for error in results.get("errors", []):
            print(f"  Error: {error}")
        return

    if not results["compiled"]:
        print("  No translation files found")
        return

    for lang in results["compiled"]:
        print(f"\n  Language: {lang['language']}")
        print(
            f"    Entries: {lang['translated']}/{lang['total']} ({lang['percent']:.1f}%)"
        )
        print(f"    Size: {lang['size']:,} bytes")

    if results["errors"]:
        print(f"\n  Errors:")
        for error in results["errors"]:
            print(f"    - {error}")


def main():
    parser = argparse.ArgumentParser(
        description="Compile translations for EDU-PI plugins"
    )
    parser.add_argument(
        "--plugin",
        help="Compile translations for a specific plugin (e.g., edupi/activity_timer)",
    )
    parser.add_argument(
        "--list", "-l", action="store_true", help="List all plugins with translations"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed output"
    )

    args = parser.parse_args()

    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    plugins_dir = project_root / "plugins"

    # Discover plugins
    plugins = get_available_plugins(plugins_dir)

    if args.list:
        print("\nAvailable plugins with translations:")
        print("-" * 60)
        for plugin in plugins:
            print(f"  {plugin['name']}")
            print(f"    Path: {plugin['path']}")
            print(f"    Languages: {', '.join(plugin['languages'])}")
        print()
        return

    if not plugins:
        print("No plugins with translation files found.")
        return

    # Filter specific plugin if requested
    if args.plugin:
        plugin_path = plugins_dir / args.plugin
        if not plugin_path.exists():
            print(f"Error: Plugin '{args.plugin}' not found")
            print(f"\nAvailable plugins:")
            for p in plugins:
                print(f"  - {p['name']}")
            sys.exit(1)

        results = compile_translations(plugin_path)
        print_results(args.plugin, results)
    else:
        # Compile all plugins
        print("Compiling translations for all plugins...")

        for plugin in plugins:
            results = compile_translations(plugin["path"])

            if args.verbose or not results["success"]:
                print_results(plugin["name"], results)
            else:
                # Quick summary
                total_lang = len(results["compiled"])
                if total_lang > 0:
                    print(f"  {plugin['name']}: {total_lang} language(s) compiled")

        print("\nDone!")


if __name__ == "__main__":
    main()
