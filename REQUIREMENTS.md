# EDU-PI - Educational Raspberry Pi Platform

## Project Overview

EDU-PI is an educational platform running on Raspberry Pi, designed for interactive classroom activities. The system combines physical GPIO-based interactions with a web-based dashboard for teachers and students.

## Core Features

### Feature 1: Classroom Noise Monitor

**Priority**: High

**User Story**: As a teacher, I want the students to visualize classroom noise levels so that they can self-regulate their volume.

**Acceptance Criteria**:

- [ ] Continuously monitor ambient sound using microphone
- [ ] Calculate TWO rolling averages:
  - **Instant Noise**: Average over 10 seconds (teacher can modify)
  - **Session Average**: Average over 5-10 minutes (teacher can modify)
- [ ] Display noise levels on TWO separate RGB LEDs:
  - **LED 1 (Instant Noise)**: Shows real-time 10-second average
    - Green: Low noise (quiet work)
    - Yellow: Medium noise (discussion allowed)
    - Red: High noise (too loud)
  - **LED 2 (Session Average)**: Shows 5-10 minute average
    - Green: Session has been quiet overall
    - Yellow: Session has been moderately noisy
    - Red: Session has been noisy overall
- [ ] Teacher can set noise thresholds via web interface
- [ ] Support multiple profiles:
  - `Test`: Minimal noise (silent mode)
  - `Teaching`: Moderate noise (teacher voice normal)
  - `Group Work`: Higher tolerance
  - `Custom`: User-defined thresholds

**Technical Notes**:

- Use microphone module or USB microphone
- GPIO pins for TWO RGB LEDs (PWM support needed):
  - LED 1: Instant noise (10-second average)
  - LED 2: Session average (5-10 minute average)
- Independent color control for both LEDs
- Store profiles and time windows in database
- Real-time updates via WebSocket
- Web interface displays both noise metrics separately

### Feature 2: Touch Piano Circuit

**Priority**: High

**User Story**: As a student, I want to play musical notes by touching conductive materials so that I can learn about circuits and conductivity.

**Acceptance Criteria**:

- [ ] Connect 5-6 GPIO input pins to conductive materials (bananas, foil, etc.)
- [ ] Detect touch via capacitive sensing or resistive method
- [ ] Play corresponding piano note on speaker/headphones
- [ ] Support conductive materials: bananas, aluminum foil, copper tape, etc.
- [ ] Visual feedback on web interface showing which "key" is pressed

**Technical Notes**:

- Capacitive touch sensing (can use resistors or dedicated sensors)
- Audio output via 3.5mm jack or USB audio
- Synthesize piano notes with pygame/midi
- Pull-up resistors required on input pins

## Additional Feature Ideas

### Feature 3: GPIO Pin Explorer

**Priority**: Medium\*\*

- Interactive web interface to test individual GPIO pins
- Toggle digital outputs, read digital inputs
- PWM control visualization
- Pin state dashboard

### Feature 4: Activity Timer

**Priority**: HIGH

- Configurable countdown timer for classroom activities
- Visual progress bar on LED strip or single RGB LED
- Optional buzzer for time-up notification
- Web controls for start/pause/reset

### Feature 5: Sensor Data Logger

**Priority**: Low\*\*

- Log GPIO activity and sensor readings
- Historical charts (last hour, day, week)
- Export data as CSV
- Temperature/humidity sensor support (optional)

### Feature 6: Lesson Mode

**Priority**: Medium\*\*

- Step-by-step guided activities
- Progress tracking for students
- Achievement badges for completed circuits
- Teacher can create custom lessons

### Feature 7: Plugin System (OctoberCMS-style)

**Priority**: High

**User Story**: As a developer, I want to extend the platform with custom plugins so that I can add new hardware integrations and features without modifying core code.

**Acceptance Criteria**:

- [ ] Plugin registration system that auto-discovers plugins from `plugins/` directory
- [ ] Each plugin has its own `plugin.py` with registration class
- [ ] Plugins can define their own:
  - Django models and migrations
  - URL routes (auto-registered)
  - Admin interfaces
  - Settings/configuration forms
  - GPIO pin definitions and cleanup handlers
  - Frontend assets (JS/CSS)
  - WebSocket handlers
- [ ] Plugin lifecycle hooks: `boot()`, `register()`, `uninstall()`
- [ ] Dependency management (plugins can depend on other plugins)
- [ ] Version compatibility checks with core platform
- [ ] Enable/disable plugins via admin interface
- [ ] Plugin configuration stored per-plugin in database
- [ ] Plugin marketplace structure (local plugins vs community plugins)

**Technical Implementation** (OctoberCMS-inspired):

```
edu-pi/
├── plugins/                    # All plugins live here
│   └── authorname/
│       └── pluginname/        # e.g., acme/weatherstation
│           ├── __init__.py
│           ├── plugin.py      # Plugin registration class
│           ├── models.py      # Plugin models
│           ├── views.py       # Plugin views
│           ├── urls.py        # Plugin URLs
│           ├── forms.py       # Plugin forms
│           ├── static/        # CSS/JS assets
│           ├── templates/     # HTML templates
│           ├── config.py      # Default settings
│           └── migrations/    # Database migrations
```

**Plugin Registration Example**:

```python
# plugins/acme/weatherstation/plugin.py
from core.plugin import PluginBase
from .models import WeatherReading

class Plugin(PluginBase):
    name = "WeatherStation"
    description = "Logs temperature and humidity data"
    author = "Acme Corp"
    version = "1.0.0"

    def boot(self):
        # Runs when plugin is enabled
        self.register_gpio_pins({
            'dht_pin': 4,
            'led_pin': 17
        })
        self.register_schedule(interval=300, callback=self.read_sensors)

    def register(self):
        # Register models, URLs, admin panels
        self.register_model(WeatherReading)
        self.register_url_pattern('weather/', include('plugins.acme.weatherstation.urls'))
        self.register_admin_menu('Weather', '/admin/weather/')

    def uninstall(self):
        # Cleanup when plugin is disabled/removed
        self.cleanup_gpio_pins()
```

**Core Plugin Features**:

- **GPIO Access**: Plugins request pins via API, system handles conflicts
- **Settings API**: Per-plugin configuration with automatic forms
- **Events**: Plugins can emit and listen to events
  - `noise.level_changed`
  - `gpio.pin_triggered`
  - `plugin.enabled`
  - `plugin.disabled`
- **Components**: Reusable UI components plugins can use
- **Assets**: Automatic asset compilation and serving
- **Permissions**: Role-based access control per plugin

**Built-in Plugins** (as examples):

- `noise_monitor`: The noise monitoring feature as a plugin
- `touch_piano`: The piano feature as a plugin
- `gpio_explorer`: GPIO testing utility as a plugin

## Non-Functional Requirements

### Performance

- Web interface loads in < 2 seconds
- GPIO response latency < 100ms
- Support for 5 concurrent WebSocket connections

### Reliability

- Graceful handling of missing hardware (mock mode)
- Auto-restart on crash
- Database backups

### Security

- PIN-based authentication for teacher settings
- No external network exposure by default
- Input validation on all GPIO operations
- Safe pin numbering validation

### Usability

- Mobile-responsive interface
- Works without internet (local network)
- Intuitive dashboard for non-technical users
- Clear error messages

## Hardware Requirements

### Required

- Raspberry Pi 4 (2GB+ RAM) or Raspberry Pi 3B+
- MicroSD card (32GB+ recommended)
- USB microphone or microphone module
- RGB LED (common cathode)
- Resistors (220Ω, 1kΩ, 10kΩ)
- Breadboard and jumper wires
- Speaker or headphones (3.5mm jack)

### Optional

- Capacitive touch sensors (TTP223 modules)
- LED strip (WS2812B) for timer
- Buzzer module
- Temperature/humidity sensor (DHT22)
- Conductive materials (bananas, foil, copper tape)

### GPIO Pin Assignments

```
Pin 1 (3.3V): Power for sensors
Pin 2 (5V): Power for LED strip
Pin 6 (GND): Common ground
Pin 11 (GPIO 17): RGB LED - Red
Pin 13 (GPIO 27): RGB LED - Green
Pin 15 (GPIO 22): RGB LED - Blue
Pin 16 (GPIO 23): Touch sensor 1 / Piano key 1
Pin 18 (GPIO 24): Touch sensor 2 / Piano key 2
Pin 19 (GPIO 10): Touch sensor 3 / Piano key 3
Pin 21 (GPIO 9): Touch sensor 4 / Piano key 4
Pin 22 (GPIO 25): Touch sensor 5 / Piano key 5
Pin 23 (GPIO 11): Touch sensor 6 / Piano key 6
Pin 24 (GPIO 8): Buzzer / Additional output
```

## User Stories

### Teacher Persona

1. "I want to set noise thresholds appropriate for my classroom acoustics"
2. "I want to switch between activity modes quickly"
3. "I want to monitor if students are using the interactive features"

### Student Persona

1. "I want to learn about circuits by building the piano project"
2. "I want to see if I'm being too loud during group work"
3. "I want to complete challenges and earn badges"

## Architecture

### Technology Stack

- **Backend**: Django 4.2+ with Django Channels
- **Frontend**: ReactJS + Tailwind CSS + DaisyUI
- **Real-time**: WebSocket (Django Channels)
- **GPIO**: gpiozero library
- **Database**: SQLite (default) or PostgreSQL (production)
- **Audio**: pygame for audio playback
- **Deployment**: UV for package management

### Project Structure

```
edu-pi/
├── config/                 # Django project settings
├── apps/
│   ├── dashboard/         # Main web interface
│   ├── gpio_control/      # GPIO management
│   ├── noise_monitor/     # Sound detection logic
│   ├── piano/             # Touch piano feature
│   └── lessons/           # Educational content
├── static/                # Frontend assets
├── templates/             # Django templates
├── tests/                 # Test suite
└── docs/                  # Documentation
```

### API Endpoints

- `GET /api/noise-level` - Current noise reading
- `POST /api/noise-profile` - Update noise thresholds
- `GET /api/gpio-status` - Current GPIO pin states
- `POST /api/gpio-control` - Control GPIO outputs
- `WS /ws/dashboard` - WebSocket for real-time updates

## Implementation Phases

### Phase 1: MVP

- Basic noise monitor with RGB LED
- Web dashboard to view current status
- Simple threshold configuration

### Phase 2: Enhanced Features

- Touch piano implementation
- Noise profiles (Test, Teaching, Group Work)
- Mobile-responsive interface

### Phase 3: Advanced

- GPIO pin explorer
- Activity timer
- Lesson mode with progress tracking
- Historical data logging

## Development Notes

### GPIO Safety

- Always validate pin numbers before operations
- Use BCM pin numbering (gpiozero default)
- Implement cleanup on program exit
- Mock GPIO for development on non-Pi systems

### Testing Strategy

- Unit tests for GPIO logic (mocked)
- Integration tests for WebSocket connections
- Hardware-in-the-loop tests for actual Pi

### Completed Features

The following features have been implemented:

#### Core Platform ✅

**Django Project Setup:**
- ✅ Django 4.2+ project with SQLite database
- ✅ Plugin system with OctoberCMS-style architecture
- ✅ Auto-discovery from `plugins/` directory
- ✅ GPIO pin allocation and conflict management
- ✅ Plugin lifecycle: `boot()`, `register()`, `uninstall()`
- ✅ Admin dashboard with plugin management interface

**Frontend:**
- ✅ Tailwind CSS + DaisyUI for styling
- ✅ Responsive design (mobile-friendly)
- ✅ Teacher dashboard at `/` showing all installed apps
- ✅ Translatable interface (English + Romanian)
- ✅ Language selector in navbar
- ✅ "App" terminology for teachers (backend still uses "Plugin")

**Plugin System Features:**
- ✅ `PluginBase` class with lifecycle hooks
- ✅ Plugin registration via `plugin.py`
- ✅ GPIO pin management with conflict detection
- ✅ Settings/configuration per plugin
- ✅ Event system for inter-plugin communication
- ✅ URL route registration
- ✅ Django models support
- ✅ Scheduled tasks support

**Admin Interface:**
- ✅ Plugin status management (enable/disable)
- ✅ Plugin configuration storage
- ✅ GPIO pin allocation tracking
- ✅ Event logging for debugging
- ✅ Dependency management
- ✅ Custom plugin dashboard at `/admin/plugins/`

#### Translations ✅

**Languages Supported:**
- ✅ English (primary)
- ✅ Romanian (secondary)

**UI Elements Translated:**
- ✅ All user-facing text
- ✅ Navigation menu
- ✅ Dashboard elements
- ✅ Status messages
- ✅ Error messages

### Configuration

- Environment variables for sensitive settings
- JSON/YAML config files for profiles
- Database migrations for schema changes

---

_Last updated: 2025-03-27_

### Documentation

- **Plugin Development Guide**: `docs/PLUGIN_DEVELOPMENT.md`
- **AGENTS.md**: Developer instructions and coding standards
- **Admin User**: admin / admin123
- **Access URLs:**
  - Dashboard: `http://localhost:8000/`
  - Admin Panel: `http://localhost:8000/admin/`
  - Plugin Management: `http://localhost:8000/admin/plugins/`
