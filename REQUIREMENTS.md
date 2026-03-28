# Tinko - Educational Raspberry Pi Platform

## Project Overview

Tinko is an educational platform running on Raspberry Pi, designed for interactive classroom activities. The system combines physical GPIO-based interactions with a web-based dashboard for teachers and students.

## Core Features

### Feature 1: Classroom Noise Monitor

**Priority**: High

**User Story**: As a teacher, I want the students to visualize classroom noise levels so that they can self-regulate their volume.

**Acceptance Criteria**:

- [x] Continuously monitor ambient sound using microphone
- [x] Calculate TWO rolling averages:
  - **Instant Noise**: Average over 10 seconds (teacher can modify)
  - **Session Average**: Average over 5-10 minutes (teacher can modify)
- [x] Display noise levels on TWO separate RGB LEDs:
  - **LED 1 (Instant Noise)**: Shows real-time 10-second average
    - Green: Low noise (quiet work)
    - Yellow: Medium noise (discussion allowed)
    - Red: High noise (too loud)
  - **LED 2 (Session Average)**: Shows 5-10 minute average
    - Green: Session has been quiet overall
    - Yellow: Session has been moderately noisy
    - Red: Session has been noisy overall
- [x] Teacher can set noise thresholds via web interface
- [x] Support multiple profiles:
  - `Test`: Minimal noise (silent mode)
  - `Teaching`: Moderate noise (teacher voice normal)
  - `Group Work`: Higher tolerance
  - `Custom`: User-defined thresholds
- [x] Real-time updates via WebSocket
- [x] Web interface displays both noise metrics separately
- [x] LED brightness control (10-100%)
- [x] Session reset functionality
- [x] Historical readings tracking

**Status**: ✅ **COMPLETED** (WebSocket support added)

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

- [x] Connect 6 GPIO input pins to conductive materials (bananas, foil, etc.)
- [x] Detect touch via capacitive sensing with pull-up resistors
- [x] Play corresponding piano note via pygame audio synthesis
- [x] Support conductive materials: bananas, aluminum foil, copper tape, etc.
- [x] Visual feedback on web interface showing which "key" is pressed
- [x] Real-time key press detection with web interface sync
- [x] Piano session tracking with key press history
- [x] Configurable piano configurations (volume, sensitivity, key mapping)
- [x] Web-based piano playing (click keys with mouse)
- [x] Keyboard shortcuts (A, S, D, F, G, H keys)
- [x] Instructions page with circuit diagram and learning objectives
- [x] Auto-cleanup of stuck notes (5-second timeout)
- [x] Translations support (English, Romanian)

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

**Status**: ✅ **COMPLETED** (Core features implemented)

- [x] Configurable countdown timer for classroom activities
- [x] Visual progress indicator on single RGB LED (LED strip support planned)
- [x] Optional buzzer for time-up notification
- [x] Web controls for start/pause/reset
- [x] **Configurable Preset Profiles** with custom display colors
- [x] **Minute of Silence preset** - Calming 60-second timer with:
  - [ ] Breathing circle animation (UI - planned)
  - [ ] Ambient sound support (nature, white noise, ocean, rain) - planned
  - [ ] TTS announcements ("Minute of silence begins now", "Time's up") - planned
  - [x] Calming blue LED colors
  - [x] Custom display color (indigo)
- [x] **Break Time preset** - Standard 10-minute break
- [x] **Activity preset** - General 30-minute activity timer
- [x] **Custom presets** with user-defined colors and durations
- [x] **Display colors** per preset for visual identification
- [x] Per-config ambient sound and breathing animation options (in database, not yet implemented)

**Note**: Breathing animation, ambient sounds, and TTS fields exist in models but actual playback/implementations are planned for future updates. The plugin uses HTTP polling for status updates; WebSocket support is planned for consistency with Noise Monitor plugin.

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

### Feature 11: Game Mode

**Priority**: High

**User Story**: As a teacher, I want to run interactive games that multiple teams can play simultaneously on their computers, with the Raspberry Pi as the central host, so that students can engage in educational competitions.

**Acceptance Criteria**:

- [ ] Teacher dashboard to select and launch games
- [ ] Multiple game types available (HTML + plain JavaScript)
- [ ] Games run in browser on student computers (not on Pi directly)
- [ ] WebSocket connection for real-time communication between Pi and all clients
- [ ] Teacher can control game state (start, pause, stop) from Pi
- [ ] Teacher sets time limit per team/session
- [ ] Automatic rotation between teams when time expires
- [ ] Score tracking per team with real-time display
- [ ] Optional automatic winner announcement via TTS when game ends
- [ ] Game results saved to database for later review
- [ ] Support for 2-8 teams simultaneously

**Game Types** (examples):

- **Quiz Race**: Multiple choice questions, first team to answer correctly
- **Memory Match**: Card matching game with educational content
- **Speed Challenge**: Complete tasks as fast as possible (e.g., solve simple math)
- **Category Quiz**: Teams guess words from categories
- **Custom Games**: Teacher-created games using simple JavaScript API

**Technical Notes**:

- WebSocket server on Pi (Django Channels)
- HTML5 games with vanilla JavaScript (no external dependencies)
- Game state synchronization across all clients
- Teacher controls via dedicated Pi interface
- Client computers connect via local network (WiFi)
- Timer management on server side
- Score validation to prevent cheating
- Game assets (HTML/JS/CSS) stored in `/games/` directory
- Simple game development API for teachers

**Game Session Flow**:

1. Teacher selects game from library
2. Teacher configures teams and time per team
3. Students open browser and navigate to Pi's IP address
4. Teams join by entering team name on their device
5. Teacher starts the game from Pi
6. Current team's turn displayed on all screens
7. Game automatically rotates teams when timer expires
8. Final scores displayed, winner announced (optional TTS)
9. Results saved to database

**Sample Game Structure**:

```
games/
├── quiz_race/
│   ├── index.html
│   ├── game.js
│   ├── styles.css
│   └── config.json
├── memory_match/
│   ├── index.html
│   └── ...
└── template/
    ├── index.html
    └── game.js
```

### Feature 8: Minute of Silence (Integrated into Activity Timer)

**Priority**: Medium

**Status**: ✅ **COMPLETED** - Integrated as a preset in Activity Timer plugin

**User Story**: As a teacher, I want to enforce a minute of silence before starting any activity so that students can calm down and prepare mentally.

**Acceptance Criteria**:

- [x] Display a visible 60-second countdown timer on the screen
- [ ] Optional calming visual (e.g., breathing circle animation) during countdown - planned
- [ ] Gentle audible signal when minute starts and ends (TTS announcements) - planned
- [x] Teacher can adjust duration (30-120 seconds) via configuration
- [x] Pause/resume functionality
- [x] Skip option for emergency situations (Stop button)
- [ ] Optional background ambient sound (nature sounds, white noise) - planned
- [x] Built-in preset with custom display color (indigo)

**Access**: http://localhost:8000/plugins/edupi/activity_timer/

**Note**: Minute of Silence is now available as a preset profile within the Activity Timer plugin, along with Break Time and Activity presets. Breathing animation, ambient sounds, and TTS are planned for future updates.

- Full-screen countdown overlay
- Calming blue LED colors
- Store statistics (usage count, average actual silence duration)

### Feature 9: Routines (Text-to-Speech)

**Priority**: Medium

**User Story**: As a teacher, I want to define classroom routines (like hand-warming poems or songs) that the system reads aloud so that students can follow along.

**Acceptance Criteria**:

- [ ] Teacher can create and edit routines in the web interface
- [ ] Each routine has a title and text content (poems, songs, instructions), and also a sound file (mp3/wav) which can be uploaded by the teacher or generated by the system using any TTS library installed
- [ ] Text-to-speech conversion with adjustable speed
- [ ] Support for multiple voices/languages
- [ ] Visual text display synchronized with speech
- [ ] Pause, resume, and replay controls
- [ ] Pre-built routines library (e.g., hand-warming exercise)
- [ ] Teacher can categorize routines (warm-up, transition, cooldown)

**Pre-built Routine Example - Hand Warming**:
```
"Let's warm up our hands for writing!
Rub your palms together, rub, rub, rub.
Now your fingers, wiggle them up high.
Shake them out, shake, shake, shake.
Ready to write, nice and warm!"
```

**Technical Notes**:

- TTS engine (eSpeak, pyttsx3, or edge-tts / gTTS) - multiple engines should exist, so that the teacher can select the prefered one
- Repeat/single-play modes
- **Wireless Presenter Support**:
  - Support for USB wireless presenters (PowerPoint clickers)
  - Presenter buttons mapped to controls (configurable):
    - **Next button**: Advance to next line/section
    - **Previous button**: Go back to previous line
    - **Play/Pause button**: Pause/resume speech
    - **Black screen button**: Stop/end routine
  - Compatible with standard USB HID presenters (Logitech, Kensington, etc.)
  - Automatic detection of presenter when plugged in
  - Uses `evdev` library to read USB input events
  - No drivers needed - works with any standard presenter

### Feature 10: Diction Exercises (this is an example routine from Feature 9)

**Priority**: Medium

**User Story**: As a teacher, I want to conduct diction exercises where students practice pronouncing random words so that they can improve their speech clarity.

**Acceptance Criteria**:

- [ ] Database of words categorized by difficulty (easy, medium, hard)
  - [ ] The words will have both the textual representation and the sound attached to them (mp3/wav files) 
- [ ] Physical button connected to GPIO, triggers next word selection
- [ ] System pronounces a random word when button is pressed
- [ ] Word displayed on screen
- [ ] Children attempt pronunciation
- [ ] Teacher presses button again for next random word
- [ ] Optional: Teacher can mark pronunciation success/failure for tracking
- [ ] Session statistics (words attempted, success rate)
- [ ] Various languages to choose from (not linked to the platform's language), aiding mother and foreign languages teaching

**Word Categories**:

- **Easy**: Short, common words (cat, book, sun)
- **Medium**: Multi-syllable words (butterfly, computer, elephant)
- **Hard**: Tongue twisters, complex sounds (squirrel, thorough, rhythm)
- **Custom**: Teacher-defined word lists

**Technical Notes**:

- GPIO button with debouncing
- Word database with audio pronunciation files
- TTS fallback for missing audio files
- Session-based progress tracking
- Exportable reports for student progress
- **Wireless Presenter Support**:
  - Alternative control method using USB wireless presenter
  - Presenter buttons mapped to controls (configurable):
    - **Next button**: Trigger new random word and pronounce it
    - **Play/Pause button**: Re-play current word
    - **Black screen button**: End session
  - Same presenter can be used for both Feature 9 and Feature 10
  - Automatic detection of presenter when plugged in
  - Fallback to GPIO button if presenter not connected

### Feature 7: Plugin System (OctoberCMS-style) ✅

**Priority**: High

**Status**: ✅ **COMPLETED**

**User Story**: As a developer, I want to extend the platform with custom plugins so that I can add new hardware integrations and features without modifying core code.

**Acceptance Criteria**:

- [x] Plugin registration system that auto-discovers plugins from `plugins/` directory
- [x] Each plugin has its own `plugin.py` with registration class
- [x] Plugins can define their own:
  - Django models and migrations
  - URL routes (auto-registered)
  - Admin interfaces
  - Settings/configuration forms
  - GPIO pin definitions and cleanup handlers
  - Frontend assets (JS/CSS)
  - WebSocket handlers
- [x] Plugin lifecycle hooks: `boot()`, `register()`, `uninstall()`
- [x] Dependency management (plugins can depend on other plugins)
- [x] Version compatibility checks with core platform
- [x] Enable/disable plugins via admin interface
- [x] Plugin configuration stored per-plugin in database
- [ ] Plugin marketplace structure (local plugins vs community plugins) ⏳ **PLANNED**

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
- `activity_timer`: Countdown for various activities

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

- **Backend**: Django 4.2+ with Django Channels ✅
- **Frontend**: Django Templates + Tailwind CSS + DaisyUI ✅
- **Real-time**: WebSocket (Django Channels) ✅ **IMPLEMENTED**
- **GPIO**: gpiozero library ✅
- **Database**: SQLite (default) or PostgreSQL (production) ✅
- **Audio**: pygame for audio playback ⏳ **PLANNED**
- **Deployment**: UV for package management ✅
- **Internationalization**: Django i18n ✅
- **Translations**: English (primary), Romanian (secondary) ✅

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
- `WS /ws/noise-monitor/` - WebSocket for real-time noise updates

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

**Audio:**
- ✅ pygame for audio playback (Touch Piano plugin)

#### Noise Monitor Plugin ✅

**User Story**: As a teacher, I want the students to visualize classroom noise levels so that they can self-regulate their volume.

**Features Implemented:**
- ✅ Continuous microphone monitoring with dual rolling averages
  - **Instant Average**: 10-second rolling window (configurable 5-60 seconds)
  - **Session Average**: 5-minute rolling window (configurable 1-30 minutes)
- ✅ Dual RGB LED visual feedback
  - LED 1: Shows instant noise level with color-coded thresholds
  - LED 2: Shows session average for overall session quality
- ✅ Multiple noise profiles with preset thresholds:
  - `Test`: Silent mode (yellow: 30, red: 50)
  - `Teaching`: Moderate noise (yellow: 40, red: 70)
  - `Group Work`: Higher tolerance (yellow: 50, red: 80)
  - `Custom`: User-defined thresholds via web interface
- ✅ Real-time WebSocket updates (no polling required)
  - Updates sent every 0.1 seconds during monitoring
  - Auto-reconnect on connection loss
  - WebSocket endpoint: `ws://host/ws/noise-monitor/`
- ✅ Web dashboard with dual metrics display
  - Visual LED indicators on screen matching physical LEDs
  - Progress bars for both instant and session averages
  - Status banner showing monitoring state
  - Historical readings table (last 50 readings)
- ✅ LED brightness control (10-100%)
- ✅ Session reset functionality
- ✅ Historical noise data tracking with database storage

**Technical Implementation:**
- Django Channels for WebSocket support
- Async WebSocket consumer at `plugins/edupi/noise_monitor/consumers.py`
- Singleton noise monitoring service with threading
- GPIO PWM control for dual RGB LEDs
- Mock mode for development on non-Pi systems

**Access URLs:**
- Dashboard: `/plugins/edupi/noise_monitor/`
- Configuration: `/plugins/edupi/noise_monitor/config/`
- API: `/plugins/edupi/noise_monitor/api/level/`

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

## Deployment

### Production Deployment on Raspberry Pi

For deploying Edu-Pi as the primary application that starts automatically on boot:

#### Systemd Service (Recommended)

Create a systemd service that manages the Django application:

1. **Service file location**: `/etc/systemd/system/edu-pi.service`

2. **Configuration**:
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

3. **Setup steps**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable edu-pi
   sudo systemctl start edu-pi
   ```

4. **Features**:
   - Auto-starts on boot
   - Auto-restarts on crash
   - Runs migrations and collectstatic before starting
   - Uses Daphne ASGI server for WebSocket support
   - Logs to systemd journal

5. **Management commands**:
   ```bash
   sudo systemctl status edu-pi      # Check status
   sudo systemctl restart edu-pi     # Restart
   sudo systemctl stop edu-pi        # Stop
   sudo journalctl -u edu-pi -f      # View logs
   ```

---

_Last updated: 2025-03-28_

### Documentation

- **Plugin Development Guide**: `docs/PLUGIN_DEVELOPMENT.md`
- **AGENTS.md**: Developer instructions and coding standards
- **Admin User**: admin / admin123
- **Access URLs:**
  - Dashboard: `http://localhost:8000/`
  - Admin Panel: `http://localhost:8000/admin/`
  - Plugin Management: `http://localhost:8000/admin/plugins/`
