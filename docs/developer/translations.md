# Translations

Internationalization (i18n) support for Tinko.

## Supported Languages

- **English** (en) - Primary
- **Romanian** (ro) - Secondary

## Marking Strings for Translation

### In Python

```python
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

# Immediate translation
name = _("Activity Timer")

# Lazy translation (for class attributes)
class Plugin(PluginBase):
    name = _lazy("My Plugin")
    description = _lazy("Plugin description")
```

### In Templates

```html
{% load i18n %}

<h1>{% trans "Welcome to Tinko" %}</h1>

<p>{% blocktrans %}Hello {{ user }}{% endblocktrans %}</p>
```

## Creating Translation Files

### 1. Make Messages

```bash
# Create .po files
uv run django-admin makemessages -l ro
uv run django-admin makemessages -l en
```

### 2. Edit Translations

**File:** `locale/ro/LC_MESSAGES/django.po`

```po
msgid "Activity Timer"
msgstr "Cronometru Activitate"

msgid "Start"
msgstr "Pornire"

msgid "Stop"
msgstr "Oprire"
```

### 3. Compile Messages

```bash
# Project and every plugin, in one run
uv run python compile_translations.py
```

This is the only compiler the project needs, and it is the one the install and
update scripts run. It uses `polib`, which is already a Python dependency, and
needs no system package.

`uv run django-admin compilemessages` also compiles the project catalogue, but
it shells out to GNU `msgfmt` from the **gettext** package. That is fine on a
development machine and impossible on a Pi, where nothing installs gettext — so
using it in the deploy meant the interface catalogue was never compiled there
and the update log said translations compiled while the pages kept the text
they were last built with. Both compilers write the same `.mo` files.

Each `.po` compiles to a `.mo` of its **own name**: `django.po` → `django.mo`,
`djangojs.po` → `djangojs.mo`. Django loads both side by side — `django.mo` for
Python and templates, `djangojs.mo` for `JavaScriptCatalog`. Writing every `.po`
in a directory to `django.mo` means the last one compiled wins, and since
`djangojs.po` sorts after `django.po`, one careless run replaces the whole
interface catalogue with the handful of strings the browser needs.

Django reads the `.mo`, so **editing a `.po` changes nothing until it is
compiled**. A catalogue that is ahead of its `.mo` shows the old text on the Pi
and the new text in the repository.

> **Note:** `compile_translations.py` finds each `locale/` directory itself —
> the project's and one per plugin — so a new plugin's catalogues are compiled
> without being listed anywhere. `makemessages` walks the tree the same way.

## Plugin Translations

### Plugin Structure

```
plugins/acme/myplugin/
├── locale/
│   ├── en/
│   │   └── LC_MESSAGES/
│   │       └── django.po
│   └── ro/
│       └── LC_MESSAGES/
│           └── django.po
```

### Compile Plugin Translations

```bash
# Every plugin, plus the project catalogue
uv run python compile_translations.py

# One plugin, with a summary of what it compiled
python scripts/compile_translations.py --plugin edupi/noise_monitor

# List plugins with translations
python scripts/compile_translations.py --list
```

Both scripts are run by the installer and by `update.sh` / `update-web.sh`.

## Language Selection

### Django Settings

```python
# config/settings.py

LANGUAGE_CODE = 'en-us'
LANGUAGES = [
    ('en', 'English'),
    ('ro', 'Romanian'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
    # Plugin locales discovered automatically
]
```

### URL Language Prefix

```python
# urls.py
from django.conf.urls.i18n import i18n_patterns

urlpatterns = i18n_patterns(
    path('', include('core.urls')),
    prefix_default_language=False,
)
```

## Testing Translations

### Test Setup

```python
# tests/test_translations.py
from django.test import TestCase
from django.utils import translation

class TranslationTests(TestCase):
    def test_romanian_translation(self):
        with translation.override('ro'):
            from django.utils.translation import gettext as _
            self.assertEqual(_("Start"), "Pornire")
```

### Check Coverage

```bash
# Report every plugin string with no Romanian translation
uv run python translation_audit.py

# Machine-readable, for a script
uv run python translation_audit.py --json
```

Exit code is 1 when anything is missing, so it can gate a build.

`makemessages` is not a coverage check. Run it from the project root and it does
walk the plugins — it collects every directory named `locale` it meets — but it
only *adds* msgids, and it says nothing about the entries still sitting there
with an empty `msgstr`. Nothing failed while the plugin catalogues fell 173
strings behind, because gettext treats a missing msgid as normal and renders the
English. The audit is what reports it, and it compares against what the code
actually calls rather than against what a previous run happened to pick up.

The audit reads Python with `ast` rather than a pattern, because Python joins
adjacent string literals: a msgid split over several lines reaches gettext as
one string, and a regular expression sees only the first line.

`tests/test_translation_coverage.py` runs the same audit over every plugin, and
additionally checks that no catalogue entry is empty, that no msgid is defined
twice, and that each `.mo` still matches its `.po`.

## Best Practices

- Use `_lazy()` for module-level strings
- Use `_()` for runtime strings
- Include context for ambiguous strings
- Keep translations updated

## See Also

- [Django i18n Documentation](https://docs.djangoproject.com/en/4.2/topics/i18n/)
- [Plugin Development](plugins/tutorial.md)
