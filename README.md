# Tinko - Educational Raspberry Pi Platform

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/django-4.2-green)](https://www.djangoproject.com/)
[![Tailwind CSS](https://img.shields.io/badge/tailwindcss-3.4%2B-38bdf8)](https://tailwindcss.com/)
[![DaisyUI](https://img.shields.io/badge/daisyui-4.10%2B-661ae6)](https://daisyui.com/)
[![License](https://img.shields.io/badge/license-MIT-brightgreen)](LICENSE)

An educational platform running on Raspberry Pi, designed for interactive classroom activities. The system combines physical GPIO-based interactions with a web-based dashboard for teachers and students.

## 🎯 Overview

Tinko enables teachers to create engaging, hands-on learning experiences by combining Raspberry Pi hardware with an intuitive web interface. Students can interact with physical sensors, LEDs, and conductive materials while teachers monitor and control activities through a modern dashboard.

### Key Highlights

- 🔌 **Plugin System**: OctoberCMS-inspired architecture for extending functionality
- 🌐 **Web Dashboard**: Responsive interface using Tailwind CSS + DaisyUI
- 🔊 **Noise Monitor**: Visual noise level feedback with RGB LEDs
- 🎹 **Touch Piano**: Learn circuits through musical interaction
- 🎤 **Routines**: Text-to-speech classroom routines with USB presenter support
- 🌍 **Multilingual**: English and Romanian support
- 🎨 **Modern UI**: Clean, accessible interface for teachers
- 🔍 **Auto-Discovery**: Plugins automatically discovered from `plugins/` directory

## ✨ Features

### Required hardware

- Raspberry PI - 1 pcs
- 3D printer - optional, for printing the case
- Screen - 1 pcs
  - <https://www.optimusdigital.ro/ro/optoelectronice-lcd-uri/12652-modul-ecran-2-ips-lcd-240x320.html?search_query=ecran&results=150>
  - <https://www.emag.ro/display-tactil-tft-lcd-2-8-inch-320x240-touchscreen-spi-driver-ili9341-arduino-rx961/pd/DSFJ88YBM/?ref=history-shopping_482672898_221614_1>
- RGB LEDs or 10 RGB LED strip - 2 pcs
- Speaker - 1 pcs

### Implemented ✅

#### Core Platform

- **Django 4.2+** backend with SQLite database
- **Plugin System** with auto-discovery from `plugins/` directory
- **GPIO Management** with pin allocation and conflict detection
- **Admin Dashboard** for plugin management
- **Teacher Dashboard** at `/` showing all installed apps
- **i18n Support** - English (primary) and Romanian (secondary)
- **Auto-Discovery** - Plugins automatically registered in Django without manual configuration

#### Hardware Integration

- [x] **Noise Monitor**: Dual RGB LED display with real-time WebSocket updates (10s and 5-10min averages)
- [x] **Touch Piano**: 6 touch-sensitive keys using conductive materials with pygame audio
- [ ] **GPIO Explorer**: Interactive pin testing interface (planned)
- [x] **Activity Timer**: Visual countdown with LED progress bar and configurable preset profiles
- [x] **Routines**: Text-to-speech classroom routines with USB presenter control

#### Activity Timer Plugin ⏱️

Visual countdown timer with configurable preset profiles for different classroom activities:

- **Preset Profiles**:
  - **Minute of Silence**: 60-second calming timer with:
    - [x] Calming blue LED colors and indigo display color
    - [ ] Breathing circle animation (planned)
    - [ ] Ambient sound support (nature, white noise, ocean, rain) (planned)
    - [ ] TTS announcements (planned)
  - **Break Time**: Standard 10-minute break with green theme
  - **Activity**: General 30-minute activity timer with amber theme
  - **Custom**: User-defined presets with custom colors and durations

- **Visual Features**:
  - Color-coded preset buttons (each preset has its own display color)
  - RGB LED showing remaining time (green→yellow→red)
  - Large digital countdown display
  - Status indicators for running/paused/stopped states

- **Controls**:
  - Start/Pause/Resume/Stop controls
  - Quick timer with custom duration
  - Preset selection with one-click start
  - Configuration management interface

- **Timer Features**:
  - Configurable duration (1-120 minutes)
  - Warning threshold (color changes at X% remaining)
  - Optional buzzer on completion
  - Session history tracking

- **Customization**:
  - Per-preset display colors for visual identification
  - LED color schemes (start/warning/end)

**Planned Features**:
- Breathing animation for calming timers
- Ambient sound support
- TTS announcement messages
- LED strip progress bar
- WebSocket real-time updates

**Access**: http://localhost:8000/plugins/edupi/activity_timer/

#### Routines Plugin 🎤

Text-to-speech classroom routines for warm-ups, transitions, and cooldowns:

- **Multi-Engine TTS Support**:
  - **pyttsx3**: System TTS (offline, works everywhere)
  - **edge-tts**: High-quality online voices (requires internet)
  - **gTTS**: Google TTS (requires internet)
  - Teacher can select preferred engine per routine
  - Configurable speed (0.5x - 2.0x)
  - Language support (en, ro, and others)

- **Audio File Upload**:
  - Upload MP3/WAV files to override TTS
  - Useful for music or custom recordings
  - Automatic fallback to TTS if no file uploaded

- **Line-by-Line Playback**:
  - Text split by lines
  - Current line highlighted
  - Progress tracking
  - Auto-advance to next line

- **USB Presenter Support**:
  - Compatible with standard USB wireless presenters (Logitech, Kensington, etc.)
  - Configurable button mappings:
    - **Next**: Advance to next line
    - **Previous**: Go back to previous line
    - **Play/Pause**: Pause/resume speech
    - **Stop**: End routine
  - Auto-detects presenter when plugged in
  - Graceful degradation on non-Linux systems (evdev library required on Pi)

- **Pre-built Routines**:
  - **Hand Warming Exercise**: Writing preparation routine
  - **Finger Stretch**: Hand stretching routine
  - **Deep Breathing**: Calming transition routine

- **Web Interface**:
  - Dashboard with categorized routines (Warm-up, Transition, Cooldown)
  - Full-screen player with synchronized text highlighting
  - TTS preview with live testing
  - Category management
  - Routine CRUD operations

- **Real-time Sync**:
  - WebSocket support for real-time updates
  - HTTP polling fallback
  - Keyboard shortcuts (Space, Arrow keys, Escape)

**Access**: http://localhost:8000/plugins/edupi/routines/

**WebSocket**: `ws://localhost:8000/ws/routines/`

#### Noise Monitor Plugin 🔊

Real-time classroom noise visualization with dual RGB LED feedback:

- **Dual Rolling Averages**: 
  - Instant: 10-second average (configurable 5-60s)
  - Session: 5-minute average (configurable 1-30min)
- **Dual RGB LEDs**: Independent color control for instant vs session noise
- **Noise Profiles**: Test, Teaching, Group Work, and Custom profiles
- **Real-time Updates**: WebSocket-based (no polling) at 10Hz
- **Web Dashboard**: Visual indicators, progress bars, and historical data
- **LED Brightness**: Adjustable 10-100%
- **Session Management**: Start/stop/reset controls

**Access**: http://localhost:8000/plugins/edupi/noise_monitor/

**WebSocket**: `ws://localhost:8000/ws/noise-monitor/`

#### Frontend

- Responsive design using Tailwind CSS and DaisyUI
- Language selector in navigation
- "App" terminology for teachers (backend uses "Plugin")
- Mobile-friendly interface

### Planned Features 📋

- [ ] **Sensor Data Logger** - Historical data visualization
- [ ] **Lesson Mode** - Step-by-step guided activities
- [ ] **Achievement System** - Progress tracking and badges
- [ ] **Multi-Pi Support** - Control multiple Raspberry Pis
- [x] **WebSocket Integration** - Real-time updates (Noise Monitor, Routines)
- [ ] **Activity Timer Enhancements** - Breathing animation, ambient sounds, TTS, LED strip support
- [ ] **Plugin Marketplace** - Community plugin sharing

### Important Behavior: Plugins Run Independently 🔄

**When a teacher starts an activity (like a timer or noise monitoring) and then navigates away to use another plugin, the activity continues running in the background.**

This design ensures classroom activities aren't interrupted when teachers switch between tools. Here's what happens:

**What Continues:**
- ✅ Timers keep counting down (LED shows remaining time)
- ✅ Noise monitoring keeps measuring (LEDs show current levels)
- ✅ GPIO pins remain active with their current state
- ✅ Database continues logging session data
- ✅ Hardware operations (buzzers, LEDs) continue working

**What Pauses:**
- ❌ Web browser updates (no page to display them)
- ❌ WebSocket real-time data streams
- ❌ Visual feedback on the web interface

**When You Return:**
The web interface automatically fetches the current state from the running background service and resumes displaying updates immediately. This allows teachers to:
1. Start a 30-minute activity timer
2. Switch to the Noise Monitor to check classroom levels
3. Return to the timer to see exactly how much time remains
4. All physical LED feedback continues throughout

**Technical Details:**
Plugins use singleton background services with daemon threads that persist independently of the web interface. This is why GPIO operations continue even when the browser is closed or the teacher navigates to another page.

## 🚀 Quick Start

### Prerequisites

- Python 3.12 or higher
- UV package manager
- Raspberry Pi 4 (2GB+) or Pi 3B+ (for deployment)
- Git

### Installation

1. **Clone the repository**

   ```bash
   git clone https://github.com/yourusername/edu-pi.git
   cd edu-pi
   ```

2. **Install dependencies**

   ```bash
   uv sync
   ```

3. **Install Raspberry Pi specific dependencies** (on actual Pi)

   ```bash
   uv sync --extra pi
   ```

4. **Run migrations**

   ```bash
   uv run python manage.py migrate
   ```

5. **Create admin user**

   ```bash
   uv run python manage.py createsuperuser
   ```

6. **Start the development server**

   ```bash
   uv run python manage.py runserver
   ```

7. **Access the application**
    - Dashboard: http://localhost:8000/
    - Admin Panel: http://localhost:8000/admin/
    - Plugin Management: http://localhost:8000/admin/plugins/
    - Noise Monitor: http://localhost:8000/plugins/edupi/noise_monitor/
    - Routines: http://localhost:8000/plugins/edupi/routines/

### WebSocket Support

The application uses Django Channels for real-time WebSocket communication. For development, `runserver` automatically supports WebSockets:

```bash
# Development with WebSocket support
uv run python manage.py runserver
```

For production or testing ASGI directly:

```bash
# Production with Daphne (ASGI server)
uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

**Note**: WebSocket connections use the same port as HTTP (8000 by default). Available WebSocket endpoints:
- Noise Monitor: `ws://localhost:8000/ws/noise-monitor/`
- Routines: `ws://localhost:8000/ws/routines/`

## 🚀 Production Deployment (Raspberry Pi)

For production deployment where the Raspberry Pi boots directly into the application, use systemd to manage the service.

### Systemd Service Setup

1. **Create the systemd service file**

   ```bash
   sudo nano /etc/systemd/system/edu-pi.service
   ```

2. **Add the following configuration**

   ```ini
   [Unit]
   Description=Edu-Pi Django Application
   After=network.target

   [Service]
   Type=simple
   User=pi
   WorkingDirectory=/home/pi/edu-pi
   Environment="PATH=/home/pi/.local/bin"
   Environment="PYTHONPATH=/home/pi/edu-pi"
   Environment="DJANGO_SETTINGS_MODULE=config.settings"
   Environment="EDUPI_DEBUG=False"
   ExecStartPre=/home/pi/.cargo/bin/uv run python manage.py migrate --noinput
   ExecStartPre=/home/pi/.cargo/bin/uv run python manage.py collectstatic --noinput
   ExecStart=/home/pi/.cargo/bin/uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application
   Restart=always
   RestartSec=3

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and start the service**

   ```bash
   # Reload systemd configuration
   sudo systemctl daemon-reload

   # Enable service to start on boot
   sudo systemctl enable edu-pi

   # Start the service
   sudo systemctl start edu-pi

   # Check service status
   sudo systemctl status edu-pi
   ```

4. **Service management commands**

   ```bash
   # View logs
   sudo journalctl -u edu-pi -f

   # Restart service
   sudo systemctl restart edu-pi

   # Stop service
   sudo systemctl stop edu-pi

   # Disable auto-start on boot
   sudo systemctl disable edu-pi
   ```

5. **Access the application**

   Once running, access via:
   - From the Pi itself: http://localhost:8000/
   - From other devices on the network: http://<raspberry-pi-ip>:8000/

### Default Credentials

- **Username**: admin
- **Password**: admin123

## 📁 Project Structure

```
edu-pi/
├── config/                  # Django project configuration
│   ├── settings.py         # Main settings (with plugin auto-discovery)
│   ├── urls.py             # URL routing
│   └── wsgi.py             # WSGI application
├── core/                    # Core functionality
│   ├── edupi_core/         # Main Django app
│   │   ├── views.py        # Dashboard views
│   │   └── urls.py         # App URLs
│   └── plugin_system/      # Plugin framework
│       ├── base.py         # PluginBase class
│       ├── models.py       # Plugin models
│       ├── admin.py        # Admin interface
│       └── views.py        # Plugin management views
├── plugins/                 # Plugin directory (auto-discovered)
│   └── edupi/              # Built-in plugins
│       ├── activity_timer/    # Countdown timer
│       ├── noise_monitor/     # Noise visualization
│       ├── routines/          # TTS classroom routines
│       └── touch_piano/       # Musical circuits
├── templates/               # HTML templates
│   ├── base.html           # Base template
│   ├── home.html           # Dashboard
│   └── admin/              # Admin templates
├── locale/                  # Translation files
│   ├── en/                 # English
│   └── ro/                 # Romanian
├── static/                  # Static assets
├── docs/                    # Documentation
│   └── PLUGIN_DEVELOPMENT.md
├── requirements.txt         # Dependencies
├── pyproject.toml          # Project configuration
└── AGENTS.md               # Developer guidelines
```

## 🔌 Plugin Development

Tinko uses an OctoberCMS-inspired plugin system with **automatic discovery**. Plugins are self-contained packages that can extend the platform's functionality.

### Creating a Plugin

1. **Create the directory structure**

   ```
   plugins/authorname/pluginname/
   ├── __init__.py          # Must import Plugin class
   ├── apps.py              # Django app configuration (optional but recommended)
   ├── plugin.py            # Required: Plugin registration class
   ├── models.py            # Django models (optional)
   ├── views.py             # Views (optional)
   ├── urls.py              # URL routes (optional)
   ├── forms.py             # Forms (optional)
   ├── consumers.py         # WebSocket consumers (optional)
   ├── routing.py           # WebSocket routing (optional)
   ├── migrations/          # Database migrations
   ├── static/              # CSS/JS assets
   └── templates/           # HTML templates
   ```

2. **Create the __init__.py file** (required for auto-discovery)

   ```python
   # plugins/authorname/pluginname/__init__.py
   try:
       from .plugin import Plugin
   except ImportError:
       pass  # Plugin class not available during early Django startup
   
   default_app_config = "plugins.authorname.pluginname.apps.PluginNameConfig"
   ```

3. **Create the plugin registration file**

   ```python
   # plugins/acme/myplugin/plugin.py
   from core.plugin_system.base import PluginBase
   from .models import MyModel

   class Plugin(PluginBase):
       name = "My Plugin"
       description = "A sample plugin"
       author = "Acme Corp"
       version = "1.0.0"
       icon = "star"  # Font Awesome icon name

       def boot(self):
           # Register GPIO pins
           self.register_gpio_pins({
               'led': 17,
               'sensor': 18
           })

           # Start background services
           self.start_background_service()

       def register(self):
           # Register models and URLs
           self.register_model(MyModel)
           self.register_url_pattern('myplugin/', include('plugins.acme.myplugin.urls'))
           self.register_admin_menu('My Plugin', '/plugins/acme/myplugin/')
           
           # Register settings
           self.register_setting(
               'my_setting',
               'My Setting',
               default='value',
               field_type='text'
           )

       def uninstall(self):
           # Cleanup
           self.cleanup_gpio_pins()
   ```

4. **Access the plugin**
   - Plugin is **auto-discovered** - no manual registration needed!
   - The `discover_plugin_apps()` function in `config/settings.py` automatically finds all plugins
   - Plugins are automatically added to Django's `INSTALLED_APPS`
   - Enable/disable via Admin Panel at `/admin/plugins/`

### Auto-Discovery

The system automatically discovers plugins from the `plugins/` directory:

1. At startup, `discover_plugin_apps()` scans `plugins/*/*/`
2. Any directory with an `__init__.py` file is registered as a Django app
3. Plugins are automatically added to `INSTALLED_APPS`
4. No manual configuration required!

This means:
- ✅ Just create a plugin directory with `__init__.py` and `plugin.py`
- ✅ Restart Django server
- ✅ Plugin is automatically available
- ✅ Migrations are created and applied automatically

### Plugin API Reference

See `docs/PLUGIN_DEVELOPMENT.md` for comprehensive documentation.

## 🌐 Translations

The platform supports multiple languages. Currently available:

- **English** (en) - Primary
- **Romanian** (ro) - Secondary

### Switching Languages

Use the globe icon in the navigation bar to switch between languages. Translations are automatically applied to all user-facing text.

### Adding a New Language

1. Create directory: `locale/xx/LC_MESSAGES/`
2. Create translation file: `django.po`
3. Compile translations: `uv run django-admin compilemessages`

### Plugin Translations

Plugins can include their own portable translation files. The Activity Timer plugin includes translations in its `locale/` directory.

#### Compiling Plugin Translations

We provide a script to compile plugin translations:

```bash
# Compile all plugin translations
python scripts/compile_translations.py

# Compile specific plugin
python scripts/compile_translations.py --plugin edupi/activity_timer

# List plugins with translations
python scripts/compile_translations.py --list

# Show detailed output
python scripts/compile_translations.py --verbose
```

#### Adding Translations to a Plugin

1. Create locale structure in your plugin:
   ```
   plugins/author/plugin/locale/
   ├── en/LC_MESSAGES/
   │   └── django.po
   └── ro/LC_MESSAGES/
       └── django.po
   ```

2. Mark strings for translation in your plugin:
   ```python
   from django.utils.translation import gettext as _

   class Plugin(PluginBase):
       name = _("My Plugin")
       description = _("Plugin description here")
   ```

3. Add translations to `.po` files:
   ```
   msgid "My Plugin"
   msgstr "Pluginul Meu"
   ```

4. Compile with: `python scripts/compile_translations.py --plugin author/plugin`

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
TIME_ZONE=Europe/Bucharest
```

### GPIO Pin Configuration

Pins are managed through the plugin system. Each plugin registers its required pins in `boot()`:

```python
def boot(self):
    self.register_gpio_pins({
        'red_led': 17,
        'green_led': 27,
        'blue_led': 22
    })
```

The system automatically:

- Checks for conflicts between plugins
- Allocates pins exclusively
- Handles cleanup on plugin disable

## 🧪 Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test
uv run pytest tests/test_plugin.py::test_name -v

# Run with coverage
uv run pytest --cov=core
```

### Code Style

The project follows PEP 8 with 88-character line length (Black default):

```bash
# Format code (if black installed)
uv run black .

# Check with ruff (if ruff installed)
uv run ruff check . --fix
```

### Mocking GPIO

For development on non-Pi systems, GPIO operations are automatically mocked:

```python
try:
    from gpiozero import LED
except ImportError:
    from core.mock_gpio import LED  # Mock implementation
```

## 📊 Hardware Requirements

### Required

- Raspberry Pi 4 (2GB+ RAM) or Pi 3B+
- MicroSD card (32GB+ recommended)
- USB microphone or microphone module
- RGB LED (common cathode)
- Resistors (220Ω, 1kΩ, 10kΩ)
- Breadboard and jumper wires
- Speaker or headphones (3.5mm jack)

### Optional

- Capacitive touch sensors (TTP223)
- LED strip (WS2812B)
- Buzzer module
- Temperature/humidity sensor (DHT22)
- Conductive materials (bananas, foil, copper tape)
- USB wireless presenter (for Routines plugin)

### GPIO Pin Assignments

```
Pin 1 (3.3V):     Power for sensors
Pin 2 (5V):       Power for LED strip
Pin 6 (GND):      Common ground
Pin 11 (GPIO 17): RGB LED - Red
Pin 13 (GPIO 27): RGB LED - Green
Pin 15 (GPIO 22): RGB LED - Blue
Pin 16 (GPIO 23): Touch sensor 1 / Piano key 1
Pin 18 (GPIO 24): Touch sensor 2 / Piano key 2
Pin 19 (GPIO 10): Touch sensor 3 / Piano key 3
Pin 21 (GPIO 9):  Touch sensor 4 / Piano key 4
Pin 22 (GPIO 25): Touch sensor 5 / Piano key 5
Pin 23 (GPIO 11): Touch sensor 6 / Piano key 6
Pin 24 (GPIO 8):  Buzzer / Additional output
```

## 📚 Documentation

- **Plugin Development**: `docs/PLUGIN_DEVELOPMENT.md`
- **Developer Guidelines**: `AGENTS.md`
- **Requirements**: `REQUIREMENTS.md`
- **Django Docs**: https://docs.djangoproject.com/en/4.2/
- **gpiozero Docs**: https://gpiozero.readthedocs.io/

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

Please read `AGENTS.md` for coding standards and guidelines.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- OctoberCMS for the plugin system inspiration
- Django team for the excellent framework
- gpiozero team for simplifying GPIO programming
- Tailwind CSS and DaisyUI for the beautiful UI

## 📧 Support

For questions or support:

- Open an issue on GitHub
- Check the documentation in `docs/`
- Review the plugin development guide

---

**Happy Teaching!** 🎓

_Made with ❤️ for education_
