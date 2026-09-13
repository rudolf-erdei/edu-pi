# CLAUDE.md

The system should be self-sufficient. When executing the `/install-raspberry-pi.sh` or `/update.sh`, the app and all supporting components (setup for unknown wifi and update) should be working.

Make sure the system is always in working condition, so that the user won't be locked out of it.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

You can find the requirements in the `/REQUIREMENTS.md` file. Keep the file updated with what you do.

Also, maintain the `/docs` folder updated with the developments, as in that folder is the official documentation for the project.

Do not perform any commits. The user will commit manually.

Backend user and pass:

user: admin
pass: edupi2026

SSH user and pass:

user: tinko
pass: tinko

Temporary WiFi pass:

SSID: Tinko-Setup
pass: tinko1234

## Project Overview

Tinko (edu-pi) is a Django-based educational platform for Raspberry Pi that combines GPIO hardware control with a web dashboard. 

It features an OctoberCMS-inspired plugin system where plugins are auto-discovered from the `plugins/` directory.

## Key Commands

```bash
# Install dependencies
uv sync

# Install Raspberry Pi specific dependencies (on actual Pi)
uv sync --extra pi

# Run development server (includes WebSocket support)
uv run python manage.py runserver

# Run production ASGI server
uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application

# Database migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Run tests
uv run pytest
uv run pytest tests/test_file.py::test_name -v

# Compile translations
python compile_translations.py

# Serve documentation locally
uv run mkdocs serve

# Deploy documentation to GitHub Pages
uv run mkdocs gh-deploy
```

## Architecture

### Plugin System (Critical)

Plugins are auto-discovered from `plugins/{author}/{plugin_name}/`. Each plugin must have:
- `__init__.py` - imports the Plugin class
- `plugin.py` - contains `Plugin(PluginBase)` class

**Plugin Lifecycle:**
1. `boot()` - Initialize hardware, register GPIO pins, schedule tasks
2. `register()` - Register models, URLs, admin menus, settings
3. `uninstall()` - Cleanup GPIO pins and resources

**Key imports:**
```python
from core.plugin_system.base import PluginBase
```

**GPIO Pin Registration:**
```python
def boot(self):
    self.register_gpio_pins({'led': 17, 'sensor': 4})
```

**Plugin Dependencies:**
```python
class Plugin(PluginBase):
    requires = ["plugins.edupi.lcd_display"]  # Declare dependencies
```

### URL Namespacing

Plugin URLs are automatically prefixed: `/plugins/{author}/{plugin_name}/`

### Background Services

Plugins run independently - when a teacher navigates away, activities continue in background via singleton services with daemon threads. Hardware operations persist independently of web interface.

### WebSocket Support

Uses Django Channels for real-time updates. Consumers live in plugin `consumers.py`, routing in `routing.py`.

## GPIO Development

BCM pin numbering is used throughout. On non-Pi systems, GPIO operations are automatically mocked via fallback imports:

```python
try:
    from gpiozero import LED
except ImportError:
    from core.mock_gpio import LED  # Mock implementation
```

## File Structure

```
edu-pi/
├── config/           # Django settings, URLs, ASGI/WSGI
├── core/
│   ├── edupi_core/   # Main Django app (dashboard, home)
│   └── plugin_system/ # PluginBase, PluginManager
├── plugins/edupi/    # Built-in plugins
│   ├── activity_timer/
│   ├── noise_monitor/
│   ├── routines/
│   ├── touch_piano/
│   └── lcd_display/
├── templates/        # Global HTML templates
├── locale/          # Translation files (en, ro)
└── docs/            # MkDocs documentation
```

## Testing

Uses pytest with Django test tools. GPIO operations should be mocked in tests using `unittest.mock.patch`. Database tests require `@pytest.mark.django_db`.

## Plugin Development Reference

When creating a new plugin:
1. Create directory: `plugins/{author}/{plugin_name}/`
2. Create `__init__.py` that imports Plugin class
3. Create `plugin.py` with `Plugin(PluginBase)` class
4. Implement `boot()`, `register()`, and `uninstall()` methods
5. Django will auto-discover and register the plugin

## Admin Credentials

- Username: admin
- Password: edupi2026

## Code Style

- PEP 8 with 88-character line length (Black default)
- Double quotes for strings
- Google-style docstrings for public APIs
- Type hints for function parameters and return values

## Session Memory

**Proactively save session summaries to MemPalace before the session ends.** 

Save important discoveries, decisions, and context proactively rather than waiting for session end.