# AGENTS.md - Agentic Coding Instructions for edu-pi

This file provides instructions for AI agents working on the edu-pi Raspberry Pi education project.

Project requirements are in the REQUIREMENTS.md file.

Project readme is in the README.md file

After any modification, update the README and REQUIREMENTS files with what was done.

Admin user: admin

Admin pass: edupi2026

Serving the documentation is done via the command 

```bash
uv run mkdocs serve
````

Building the documentation for Github Pages is done via the command 

```bash
uv run mkdocs gh-deploy
```

## Project Overview

A Django-based educational platform for Raspberry Pi GPIO control and experimentation. Uses UV for Python package management.

## Build/Test/Lint Commands

```bash
# Install dependencies
uv sync

# Install Raspberry Pi specific dependencies (on actual Pi)
uv sync --extra pi

# Run Django server
uv run python manage.py runserver

# Run all tests
uv run pytest

# Run a single test
uv run pytest path/to/test_file.py::test_function_name -v

# Run tests for a specific module
uv run pytest tests/module/ -v

# Django management commands
uv run python manage.py makemigrations
uv run python manage.py migrate
uv run python manage.py shell
uv run python manage.py createsuperuser

# Check types (if mypy added)
uv run mypy .
```

## Code Style Guidelines

### Python Style

- **Follow PEP 8** - Use 4 spaces for indentation
- **Line length**: 88 characters (Black default)
- **Quotes**: Use double quotes for strings
- **Imports**: Group in order: stdlib, third-party, local (alphabetical within groups)
- **Type hints**: Use them for function parameters and return values
- **Docstrings**: Use Google style docstrings for all public functions/classes

### Naming Conventions

- **Modules**: `lowercase.py`
- **Packages**: `lowercase`
- **Classes**: `PascalCase`
- **Functions**: `snake_case`
- **Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **Private**: `_leading_underscore`

### Django Conventions

- **Views**: Use class-based views (CBV) for CRUD, function views for simple cases
- **Models**: Singular names (e.g., `Pin` not `Pins`)
- **Templates**: `app_name/template_name.html` structure
- **URLs**: Use `path()` not `url()`, kebab-case for URL patterns
- **Forms**: Separate forms in `forms.py`, use `ModelForm` when possible

### GPIO/Sensor Code

- **Pin references**: Always use BCM numbering (gpiozero default)
- **Cleanup**: Use context managers (`with` statement) for GPIO cleanup
- **Mocking**: Mock gpiozero for unit tests on non-Pi systems
- **Error handling**: Wrap GPIO calls in try/except with cleanup in finally

### Error Handling

- Use specific exceptions, not bare `except:`
- Log errors with context using `logging` module
- For user-facing errors, use Django's messages framework
- GPIO errors: Catch `gpiozero.exc` exceptions separately

### Testing Guidelines

- Use pytest for all tests
- Name test files `test_*.py`
- Name test functions `test_*`
- Use fixtures for setup/teardown
- Mock GPIO operations in tests
- Use `@pytest.mark.django_db` for database tests
- Aim for >80% coverage on critical paths

### Import Formatting

```python
# 1. Standard library
import os
import sys
from typing import Optional

# 2. Third-party
import django
from django.db import models
from gpiozero import LED

# 3. Local
from .models import Device
from utils.helpers import parse_pin
```

### File Organization

```
edu-pi/
├── config/              # Django settings
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/                # Django applications
│   ├── __init__.py
│   ├── gpio/            # GPIO control app
│   ├── lessons/         # Educational content
│   └── users/           # User management
├── tests/               # Test suite
│   ├── __init__.py
│   ├── conftest.py      # pytest fixtures
│   └── test_*.py
├── templates/           # HTML templates
├── static/              # CSS/JS assets
├── docs/                # Documentation
├── scripts/             # Utility scripts
├── manage.py
├── pyproject.toml
├── uv.lock
└── AGENTS.md           # This file
```

### Documentation

- Update README.md for major features
- Document GPIO pin mappings in comments
- Include docstrings with Args/Returns for complex functions
- Add type hints to public APIs

### Dependencies

- Pin versions in `pyproject.toml` (already done)
- GPIO libraries are optional extras - code must work without them
- Use `uv add <package>` to add new dependencies
- Update `uv.lock` after dependency changes

### Security

- Never commit secrets or API keys
- Use environment variables for sensitive config
- Validate all GPIO pin numbers before use
- Sanitize user inputs before GPIO operations
