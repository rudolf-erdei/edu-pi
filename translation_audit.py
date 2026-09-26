"""Find msgids a plugin asks to translate but its catalogue does not define.

gettext never reports a missing msgid: the call falls through and the string
renders in English. A Romanian teacher therefore sees a stray English label on
an otherwise Romanian page, and nothing anywhere fails — which is how the
plugins ended up with 173 untranslated strings that no test noticed.

Usage:
    python translation_audit.py            # report every plugin
    python translation_audit.py --json     # machine-readable report
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple

import polib

DEFAULT_PLUGINS_DIR = Path(__file__).parent / "plugins"
DEFAULT_LOCALE = "ro"

#: Suffixes searched for translation calls.
SOURCE_SUFFIXES = {".py", ".html", ".js"}

#: Directories never searched, because nothing in them is a translation call.
SKIPPED_DIRECTORIES = {"locale", "migrations", "__pycache__"}

GETTEXT_FUNCTIONS = {"gettext", "gettext_lazy", "_", "ugettext", "ugettext_lazy"}
#: For these the msgid is not the first argument, so they cannot be read as if
#: it were.
CONTEXT_FUNCTIONS = {"pgettext", "pgettext_lazy"}
#: These carry a second string for the plural form, which is also an entry.
PLURAL_FUNCTIONS = {"ngettext", "ngettext_lazy"}

TRANSLATION_FUNCTIONS = GETTEXT_FUNCTIONS | CONTEXT_FUNCTIONS | PLURAL_FUNCTIONS

#: ``{% trans "x" %}`` / ``{% trans 'x' %}``. The delimiter decides where the
#: msgid ends, so an apostrophe inside double quotes cannot truncate it — a
#: single greedy pattern reading either quote type cut
#: ``"If keys don't work"`` down to ``"If keys don"`` and reported the real
#: string as untranslated.
TEMPLATE_TRANS = re.compile(r"""\{%\s*trans\s+(?:"([^"]*)"|'([^']*)')""")
TEMPLATE_BLOCKTRANS = re.compile(
    r"\{%\s*blocktrans[^%]*%\}(.*?)\{%\s*endblocktrans\s*%\}", re.S
)
#: A blocktrans placeholder is a gettext placeholder, spelled differently.
TEMPLATE_PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")
JS_GETTEXT = re.compile(r"""\bgettext\s*\(\s*(?:"([^"]*)"|'([^']*)')""")


def _literal(node: ast.AST) -> Optional[str]:
    """Return the string a node stands for, or None if it is not a constant."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def python_msgids(source: str, filename: str = "<unknown>") -> Set[str]:
    """Collect the msgids a Python source asks to have translated.

    The source is parsed rather than pattern-matched because Python joins
    adjacent string literals: a msgid split over several lines for readability
    reaches gettext as one string, and a regular expression sees only the first
    line and reports the remainder as untranslated.

    Args:
        source: The Python source to read.
        filename: Name used in error messages only.

    Returns:
        Set[str]: Every msgid found, plural forms included.
    """
    found: Set[str] = set()
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError:
        return found

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = getattr(function, "id", None) or getattr(function, "attr", None)
        if name not in TRANSLATION_FUNCTIONS or not node.args:
            continue

        # pgettext(context, msgid) — the context is not a msgid.
        index = 1 if name in CONTEXT_FUNCTIONS else 0
        if len(node.args) <= index:
            continue

        msgid = _literal(node.args[index])
        if msgid:
            found.add(msgid)

        if name in PLURAL_FUNCTIONS and len(node.args) > 1:
            plural = _literal(node.args[1])
            if plural:
                found.add(plural)

    return found


def template_msgids(text: str) -> Set[str]:
    """Collect the msgids a Django template asks to have translated.

    Args:
        text: The template source.

    Returns:
        Set[str]: Every msgid found, with blocktrans ``{{ name }}`` placeholders
        rewritten to the ``%(name)s`` form gettext stores.
    """
    found: Set[str] = set()

    for match in TEMPLATE_TRANS.finditer(text):
        found.add(match.group(1) if match.group(1) is not None else match.group(2))

    for body in TEMPLATE_BLOCKTRANS.findall(text):
        found.add(TEMPLATE_PLACEHOLDER.sub(r"%(\1)s", body).strip())

    for match in JS_GETTEXT.finditer(text):
        found.add(match.group(1) if match.group(1) is not None else match.group(2))

    return {msgid for msgid in found if msgid}


def source_files(plugin_dir: Path) -> Iterator[Path]:
    """Yield the files of a plugin that may contain translation calls.

    Args:
        plugin_dir: Root directory of the plugin.

    Yields:
        Path: Each searchable file.
    """
    for path in sorted(plugin_dir.rglob("*")):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        if SKIPPED_DIRECTORIES & set(path.parts):
            continue
        # A plugin's own tests quote msgids in docstrings while discussing
        # them, which is not a request to translate anything.
        if path.name == "tests.py":
            continue
        yield path


def used_msgids(plugin_dir: Path) -> Set[str]:
    """Collect every msgid a plugin asks to have translated.

    Args:
        plugin_dir: Root directory of the plugin.

    Returns:
        Set[str]: The msgids found in its Python, template and JavaScript files.
    """
    found: Set[str] = set()

    for path in source_files(plugin_dir):
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".py":
            found |= python_msgids(text, str(path))
        else:
            found |= template_msgids(text)

    return found


def catalogue_path(plugin_dir: Path, language: str = DEFAULT_LOCALE) -> Path:
    """Return the path of a plugin's compiled catalogue source.

    Args:
        plugin_dir: Root directory of the plugin.
        language: Language code of the catalogue.

    Returns:
        Path: The ``django.po`` file, whether or not it exists.
    """
    return plugin_dir / "locale" / language / "LC_MESSAGES" / "django.po"


def translated_msgids(plugin_dir: Path, language: str = DEFAULT_LOCALE) -> Set[str]:
    """Collect the msgids a plugin's catalogue defines.

    Args:
        plugin_dir: Root directory of the plugin.
        language: Language code of the catalogue.

    Returns:
        Set[str]: The catalogued msgids, or an empty set when there is no
        catalogue to read.
    """
    path = catalogue_path(plugin_dir, language)
    if not path.exists():
        return set()
    return {entry.msgid for entry in polib.pofile(str(path)) if entry.msgid}


def discover_plugins(plugins_dir: Path = DEFAULT_PLUGINS_DIR) -> List[Path]:
    """Find the plugins that ship a translated catalogue.

    Args:
        plugins_dir: The ``plugins`` directory to search.

    Returns:
        List[Path]: Plugin directories holding a ``django.po``, sorted by path.
    """
    if not plugins_dir.exists():
        return []
    return sorted(
        {
            po_file.parents[3]
            for po_file in plugins_dir.rglob(f"{DEFAULT_LOCALE}/LC_MESSAGES/django.po")
        }
    )


def missing_msgids(plugin_dir: Path, language: str = DEFAULT_LOCALE) -> List[str]:
    """Return the msgids a plugin uses but its catalogue does not define.

    Args:
        plugin_dir: Root directory of the plugin.
        language: Language code of the catalogue.

    Returns:
        List[str]: The untranslated msgids, sorted.
    """
    return sorted(used_msgids(plugin_dir) - translated_msgids(plugin_dir, language))


def audit(plugins_dir: Path = DEFAULT_PLUGINS_DIR) -> Dict[str, List[str]]:
    """Audit every plugin under a plugins directory.

    Args:
        plugins_dir: The ``plugins`` directory to search.

    Returns:
        Dict[str, List[str]]: Untranslated msgids, keyed by plugin name.
    """
    report: Dict[str, List[str]] = {}
    for plugin_dir in discover_plugins(plugins_dir):
        report[plugin_dir.name] = missing_msgids(plugin_dir)
    return report


def _plugin_label(plugin_dir: Path, plugins_dir: Path) -> str:
    """Name a plugin the way the audit reports it, as ``author/name``."""
    try:
        relative: Tuple[str, ...] = plugin_dir.relative_to(plugins_dir).parts
    except ValueError:
        return plugin_dir.name
    return "/".join(relative[-2:])


def main() -> int:
    """Report untranslated msgids for every plugin.

    Returns:
        int: 0 when everything is translated, 1 when something is missing.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--plugins-dir", type=Path, default=DEFAULT_PLUGINS_DIR, help="plugins root"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    report = audit(args.plugins_dir)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        plugins_dir = Path(args.plugins_dir)
        for plugin_dir in discover_plugins(plugins_dir):
            missing = report[plugin_dir.name]
            label = _plugin_label(plugin_dir, plugins_dir)
            print(f"{label:32} missing={len(missing)}")
            for msgid in missing:
                print(f"    {msgid!r}")

    return 1 if any(report.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
