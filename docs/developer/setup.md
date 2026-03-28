# Developer Setup

Set up your development environment for Tinko plugin development.

## Prerequisites

Before starting, ensure you have:

- Computer running Windows, macOS, or Linux
- Python 3.12 or higher installed
- Git installed
- Text editor or IDE (VS Code, PyCharm, etc.)
- Optional: Raspberry Pi for hardware testing

## Step 1: Install UV Package Manager

UV is the modern Python package manager used by Tinko.

### macOS / Linux

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Windows

```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Restart your terminal after installation.

## Step 2: Clone the Repository

```bash
git clone https://github.com/rudolf-erdei/edu-pi.git
cd edu-pi
```

## Step 3: Install Dependencies

Install base dependencies:

```bash
uv sync
```

This installs all required packages including Django, gpiozero, pygame, etc.

## Step 4: Set Up Development Environment

### Create .env File

Create a `.env` file in the project root:

```bash
# Development settings
DEBUG=True
SECRET_KEY=your-dev-secret-key-not-for-production
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
TIME_ZONE=Europe/Bucharest
```

Replace `your-dev-secret-key` with a random string.

### IDE Configuration

#### VS Code

Create `.vscode/settings.json`:

```json
{
    "python.defaultInterpreterPath": ".venv/bin/python",
    "python.analysis.extraPaths": ["."],
    "python.testing.pytestEnabled": true,
    "python.testing.pytestArgs": ["tests"],
    "python.linting.enabled": true,
    "python.formatting.provider": "black",
    "editor.formatOnSave": true,
}
```

#### PyCharm

1. Open the project in PyCharm
2. Go to File > Settings > Project > Python Interpreter
3. Point to the `.venv` directory created by UV
4. Mark `plugins/` as Sources Root

## Step 5: Run Migrations

Set up the database:

```bash
uv run python manage.py migrate
```

## Step 6: Create Superuser

Create an admin account:

```bash
uv run python manage.py createsuperuser
```

Follow the prompts.

## Step 7: Start Development Server

```bash
uv run python manage.py runserver
```

Access the application at:

- Dashboard: `http://localhost:8000/`
- Admin Panel: `http://localhost:8000/admin/`

## Development Workflow

### Making Changes

1. Edit code in your IDE
2. Run server: `uv run python manage.py runserver`
3. Test changes in browser
4. Run tests: `uv run pytest`

### Adding Dependencies

```bash
uv add package-name
```

This updates both `pyproject.toml` and `uv.lock`.

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_plugin.py

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=core
```

### Code Formatting

If you have Black installed:

```bash
uv run black .
```

## Mock Mode for Non-Pi Development

When developing on a non-Raspberry Pi system, GPIO operations are automatically mocked. This allows you to:

- Develop plugins without hardware
- Test logic without GPIO errors
- Debug code on any platform

The system detects when `gpiozero` is not available and uses mock implementations instead.

## Project Structure

Familiarize yourself with the project:

```
edu-pi/
├── config/              # Django configuration
├── core/                # Core functionality
│   └── plugin_system/  # Plugin framework
├── plugins/            # Plugin directory
│   └── edupi/         # Built-in plugins
├── templates/          # HTML templates
├── static/             # CSS/JS assets
├── tests/              # Test suite
└── docs/               # Documentation
```

## Debugging Tips

### Enable Debug Mode

Set `DEBUG=True` in your `.env` file for detailed error pages.

### Django Shell

Access the Django shell for debugging:

```bash
uv run python manage.py shell
```

Example:

```python
from core.plugin_system.base import plugin_manager
plugins = plugin_manager.get_all_plugins()
print(plugins)
```

### Logging

Set logging level in `config/settings.py`:

```python
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### Browser DevTools

Use browser Developer Tools (F12) to:

- View console logs
- Inspect WebSocket connections
- Debug JavaScript
- Monitor network requests

## Common Issues

### Import Errors

If you see import errors:

1. Ensure UV virtual environment is activated
2. Check `sys.path` includes project root
3. Verify imports use correct module paths

### Database Locked

SQLite may lock during development:

```bash
# Stop the server
# Wait a few seconds
# Restart
uv run python manage.py runserver
```

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000

# Kill process
kill -9 <PID>
```

## Raspberry Pi Testing

When testing on actual hardware:

1. Copy code to Pi
2. Install Pi dependencies: `uv sync --extra pi`
3. Run as user with GPIO access: `sudo usermod -a -G gpio pi`
4. Test with actual hardware connected

## Next Steps

- [Project Structure](structure.md) - Understand the codebase
- [Hardware Requirements](hardware/requirements.md) - Connect GPIO components
- [Plugin Tutorial](../plugins/tutorial.md) - Create your first plugin
- [Plugin API](../plugins/api.md) - Plugin development reference

## Useful Commands

```bash
# Start development server
uv run python manage.py runserver

# Run tests
uv run pytest

# Run migrations
uv run python manage.py migrate

# Create superuser
uv run python manage.py createsuperuser

# Django shell
uv run python manage.py shell

# Check plugin loading
uv run python -c "from core.plugin_system.base import plugin_manager; print(plugin_manager.get_all_plugins())"

# Compile translations
python scripts/compile_translations.py

# Collect static files
uv run python manage.py collectstatic
```
