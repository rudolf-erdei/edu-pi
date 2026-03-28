# Project Structure

Understanding the Tinko project organization is essential for effective development.

## Directory Overview

```
edu-pi/
├── config/                  # Django project configuration
│   ├── __init__.py
│   ├── settings.py         # Main settings with plugin discovery
│   ├── urls.py             # URL routing
│   ├── asgi.py             # ASGI application (WebSocket)
│   └── wsgi.py             # WSGI application
├── core/                    # Core functionality
│   ├── edupi_core/         # Main Django app
│   │   ├── views.py        # Dashboard views
│   │   ├── urls.py         # App URLs
│   │   └── templates/      # Core templates
│   └── plugin_system/      # Plugin framework (IMPORTANT!)
│       ├── __init__.py
│       ├── base.py         # PluginBase class
│       ├── manager.py      # PluginManager
│       ├── models.py       # Plugin models
│       ├── admin.py        # Admin interfaces
│       └── views.py        # Plugin management views
├── plugins/                 # Plugin directory (auto-discovered)
│   ├── __init__.py
│   └── edupi/              # Built-in plugins
│       ├── activity_timer/
│       ├── noise_monitor/
│       ├── routines/
│       └── touch_piano/
├── templates/               # Global HTML templates
│   ├── base.html           # Base template
│   ├── home.html           # Dashboard
│   └── ...
├── static/                  # Static assets (CSS/JS/images)
│   ├── css/
│   ├── js/
│   └── images/
├── locale/                  # Translation files
│   ├── en/
│   └── ro/
├── tests/                   # Test suite
│   ├── __init__.py
│   └── conftest.py         # pytest fixtures
├── docs/                    # Documentation
│   └── ...
├── scripts/                 # Utility scripts
│   └── compile_translations.py
├── manage.py               # Django management script
├── pyproject.toml          # Project configuration
├── uv.lock                 # Dependency lock file
└── .env                    # Environment variables
```

## Key Components

### config/ Directory

Contains Django project configuration:

- **settings.py**: Main configuration with plugin auto-discovery
- **urls.py**: Root URL routing
- **asgi.py**: ASGI application for WebSocket support
- **wsgi.py**: Traditional WSGI application

### core/ Directory

#### core/edupi_core/

The main Django application:

- **views.py**: Dashboard and home page views
- **urls.py**: URL routes for core functionality
- **templates/**: Global templates (base.html, home.html)

#### core/plugin_system/ (CRITICAL!)

The plugin framework - this is where plugin magic happens:

**base.py**

Contains the `PluginBase` class that all plugins must inherit:

```python
class PluginBase:
    def boot(self): ...
    def register(self): ...
    def uninstall(self): ...
    def register_gpio_pins(self, pins): ...
    def register_setting(self, key, label, **kwargs): ...
```

**manager.py**

`PluginManager` handles plugin loading and lifecycle:

```python
class PluginManager:
    def discover_plugins(self): ...
    def load_plugin(self, path): ...
    def enable_plugin(self, name): ...
    def disable_plugin(self, name): ...
```

**models.py**

Database models for plugin system:

- `Plugin`: Plugin metadata and status
- `PluginSetting`: Plugin configuration storage
- `GPIOPin`: GPIO pin allocation tracking

### plugins/ Directory

All plugins live here. The structure is:

```
plugins/
└── {author}/              # e.g., edupi, acme, etc.
    └── {plugin_name}/     # e.g., activity_timer
        ├── __init__.py    # Required: imports Plugin class
        ├── plugin.py      # Required: Plugin registration
        ├── models.py      # Optional: Django models
        ├── views.py       # Optional: Views
        ├── urls.py        # Optional: URL routes
        ├── forms.py       # Optional: Forms
        ├── consumers.py   # Optional: WebSocket consumers
        ├── routing.py     # Optional: WebSocket routing
        ├── static/        # Optional: CSS/JS
        ├── templates/     # Optional: HTML templates
        └── migrations/    # Auto-created: Database migrations
```

#### Built-in Plugins (plugins/edupi/)

- **activity_timer/**: Countdown timer with LED feedback
- **noise_monitor/**: Noise monitoring with dual RGB LEDs
- **routines/**: Text-to-speech routines with presenter support
- **touch_piano/**: Capacitive touch piano

### templates/ Directory

Django template files:

- **base.html**: Master template with navigation, footer
- **home.html**: Dashboard showing all plugins
- Admin templates in `admin/`

Templates use the Django template language with Tailwind CSS classes.

### static/ Directory

Static assets served directly:

- **css/**: Stylesheets (Tailwind + custom)
- **js/**: JavaScript files
- **images/**: Logo, icons, etc.

Static files are collected with:

```bash
uv run python manage.py collectstatic
```

### locale/ Directory

Translation files for internationalization:

```
locale/
├── en/
│   └── LC_MESSAGES/
│       └── django.po     # English translations
└── ro/
    └── LC_MESSAGES/
        └── django.po     # Romanian translations
```

### tests/ Directory

Test suite using pytest:

- **conftest.py**: pytest configuration and fixtures
- Test files named `test_*.py`

## Auto-Discovery Mechanism

The plugin system automatically discovers plugins from `plugins/`:

1. **Scanning**: `discover_plugin_apps()` scans `plugins/*/*/`
2. **Detection**: Directories with `__init__.py` are registered
3. **Loading**: Plugins added to Django's `INSTALLED_APPS`
4. **Boot**: Plugin `boot()` methods called
5. **Register**: Plugin `register()` methods called

This happens in `config/settings.py`:

```python
# Auto-discover plugins
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    # ...
] + discover_plugin_apps()  # Automatically adds plugins
```

## Plugin Namespace

Plugins are identified by namespace: `{author}.{plugin_name}`

Examples:
- `edupi.activity_timer`
- `edupi.noise_monitor`
- `acme.weather_station`

## Import Paths

When importing within plugins, use full Python paths:

```python
# From a plugin
from core.plugin_system.base import PluginBase
from plugins.edupi.activity_timer.models import TimerSession

# Django models
from django.db import models
```

## Configuration Files

### pyproject.toml

Project configuration including dependencies:

```toml
[project]
name = "edu-pi"
dependencies = [
    "Django>=4.2",
    "gpiozero>=2.0",
    # ...
]

[project.optional-dependencies]
pi = [
    "RPi.GPIO>=0.7.1",
    "lgpio>=0.2",
]
```

### uv.lock

Locked dependency versions - commit this file to ensure reproducible builds.

### .env

Environment-specific settings (don't commit this!):

```env
DEBUG=True
SECRET_KEY=...
ALLOWED_HOSTS=...
```

## Development Guidelines

### Adding a New File

1. Determine the appropriate directory
2. Follow naming conventions (snake_case)
3. Update imports if needed
4. Run tests to verify

### Modifying Core Files

Be careful when modifying:

- `core/plugin_system/base.py` - Affects all plugins
- `config/settings.py` - Affects entire application
- `config/urls.py` - Affects URL routing

Always test thoroughly after changes.

### Creating Plugins

See [Plugin Tutorial](plugins/tutorial.md) for detailed instructions.

## Next Steps

- [Hardware Requirements](hardware/requirements.md) - Connect GPIO components
- [Plugin Tutorial](plugins/tutorial.md) - Create your first plugin
- [Plugin API](plugins/api.md) - Complete API reference
- [GPIO Pins](hardware/gpio-pins.md) - Pin allocation reference
