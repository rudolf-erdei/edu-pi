# Activity Timer Plugin

A classroom activity timer with visual feedback via RGB LED and optional buzzer for Tinko platform.

## Features

- **Countdown Timer**: Configurable countdown timer for classroom activities
- **Visual Feedback**: RGB LED shows remaining time with color changes
  - Green: Normal time remaining
  - Yellow: Warning threshold reached
  - Red: Timer ended
- **Audio Alert**: Optional buzzer sounds when timer ends
- **Web Interface**: Control and monitor timer from any device
- **Configurable Presets**: Create and save timer configurations
- **Pause/Resume**: Pause timer and resume later
- **Session History**: Track completed timer sessions

## Hardware Requirements

- Raspberry Pi (3B+ or 4)
- RGB LED (common cathode)
- Resistors (220Ω for each LED color)
- Optional: Buzzer module

## GPIO Pin Mapping

Default GPIO pin assignments (BCM numbering):

- **GPIO 17 (Pin 11)**: Red LED
- **GPIO 27 (Pin 13)**: Green LED
- **GPIO 22 (Pin 15)**: Blue LED
- **GPIO 24 (Pin 18)**: Buzzer (optional)

## Installation

The plugin is automatically discovered by the Tinko plugin system. Simply ensure the plugin directory exists at:

```
plugins/edupi/activity_timer/
```

## Configuration

### Default Settings

Plugin settings can be configured via the admin interface:

- **Default Duration**: Default timer duration in minutes (1-120)
- **LED Brightness**: LED brightness percentage (10-100)
- **Warning Threshold**: Percentage remaining when LED turns yellow (5-50)
- **Enable Buzzer**: Toggle buzzer on/off

### Timer Configurations

Create custom timer configurations:

- Set duration (1-120 minutes)
- Configure custom colors for start/warning/end states
- Set warning threshold percentage
- Enable/disable buzzer per configuration
- Mark configurations as default

## Usage

### Web Interface

Access the timer dashboard at:

```
http://localhost:8000/plugins/edupi/activity_timer/
```

### Controls

- **Start**: Begin countdown with selected configuration
- **Pause**: Temporarily stop the timer
- **Resume**: Continue from paused state
- **Stop**: Cancel the timer

### Quick Start Options

1. **Preset Timers**: Use predefined configurations (Test, Teaching, Quiz, Group Work, Exam)
2. **Quick Timer**: Enter duration and start immediately
3. **Custom Configuration**: Create and save your own timer settings

## API Endpoints

### Timer Control

- `POST /plugins/edupi/activity_timer/control/` - Control timer (start/pause/resume/stop)
- `GET /plugins/edupi/activity_timer/status/` - Get current timer status

### Configuration Management

- `GET /plugins/edupi/activity_timer/configs/` - List configurations
- `POST /plugins/edupi/activity_timer/configs/create/` - Create configuration
- `POST /plugins/edupi/activity_timer/configs/<id>/edit/` - Update configuration
- `POST /plugins/edupi/activity_timer/configs/<id>/delete/` - Delete configuration

## Development

### Mock GPIO Mode

For development on non-Pi systems, the plugin automatically uses mock GPIO classes that log actions instead of controlling hardware.

### Testing

Run plugin-specific tests:

```bash
uv run pytest plugins/edupi/activity_timer/
```

## File Structure

```
plugins/edupi/activity_timer/
├── __init__.py              # Plugin initialization
├── apps.py                  # Django app configuration
├── plugin.py               # Plugin registration and lifecycle
├── models.py               # TimerConfig and TimerSession models
├── views.py                # Django views
├── urls.py                 # URL configuration
├── forms.py                # Django forms
├── timer_service.py        # Timer logic and GPIO control
├── locale/                 # Translations (portable with plugin)
│   ├── en/LC_MESSAGES/     # English translations
│   │   ├── django.po
│   │   └── django.mo
│   └── ro/LC_MESSAGES/     # Romanian translations
│       ├── django.po
│       └── django.mo
├── templates/
│   └── activity_timer/
│       ├── dashboard.html   # Main timer interface
│       ├── config_list.html   # Configuration list
│       └── config_form.html   # Configuration form
├── static/
│   └── activity_timer/    # Static assets (CSS/JS)
└── migrations/
    └── 0001_initial.py    # Database migrations
```

## Translations

The Activity Timer plugin includes portable translations that are distributed with the plugin code:

### Supported Languages

- **English** (en) - Primary language
- **Romanian** (ro) - Secondary language

### Translation Files Location

Translations are stored in the plugin's `locale/` directory:

```
locale/
├── en/LC_MESSAGES/
│   ├── django.po    # Source translation file
│   └── django.mo    # Compiled translation file
└── ro/LC_MESSAGES/
    ├── django.po
    └── django.mo
```

### How Translations Work

Django automatically discovers translations from each app's `locale/` directory. When the plugin is installed:

1. The `.po` files contain the source translations
2. The `.mo` files are compiled binary versions
3. Django loads translations based on the user's language preference
4. All plugin strings are marked with `{% trans %}` or `gettext()` for translation

### Adding New Translations

To add a new language:

1. Create the directory structure: `locale/<language_code>/LC_MESSAGES/`
2. Copy `django.po` from another language as a template
3. Translate all `msgstr` entries
4. Compile to `.mo` using: `django-admin compilemessages`

### Updating Translations

After modifying strings in the plugin:

```bash
# Extract new strings
uv run django-admin makemessages -l en -l ro --ignore=.venv

# Edit .po files with new translations
# ... translate strings ...

# Compile translations
uv run django-admin compilemessages
```

## License

Part of Tinko Educational Platform
