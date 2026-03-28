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
# Compile .po to .mo
uv run django-admin compilemessages
```

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
# Compile all plugin translations
python scripts/compile_translations.py

# Compile specific plugin
python scripts/compile_translations.py --plugin acme/myplugin

# List plugins with translations
python scripts/compile_translations.py --list
```

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
# Check for untranslated strings
uv run django-admin makemessages -l ro --no-obsolete
```

## Best Practices

- Use `_lazy()` for module-level strings
- Use `_()` for runtime strings
- Include context for ambiguous strings
- Keep translations updated

## See Also

- [Django i18n Documentation](https://docs.djangoproject.com/en/4.2/topics/i18n/)
- [Plugin Development](../plugins/tutorial.md)
