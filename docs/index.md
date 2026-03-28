# Welcome to Tinko

Tinko is an open-source educational platform for Raspberry Pi that brings interactive classroom activities to life. Combining physical GPIO-based hardware with a modern web interface, Tinko helps teachers create engaging, hands-on learning experiences.

## What is Tinko?

Tinko enables teachers to transform their Raspberry Pi into an interactive classroom assistant. Students can touch conductive materials to play music, visualize noise levels with colorful LEDs, follow guided routines with text-to-speech, and more - all while teachers control everything through an intuitive web dashboard.

## Key Features

- **Plugin System**: OctoberCMS-inspired architecture for easy extensibility
- **Web Dashboard**: Responsive interface using Tailwind CSS + DaisyUI
- **Hardware Integration**: RGB LEDs, touch sensors, speakers, and more
- **Multilingual**: English and Romanian support
- **Auto-Discovery**: Plugins automatically registered from `plugins/` directory
- **Settings Area**: Centralized configuration for global and plugin-specific settings
- **Personalization**: Customizable school name, logo, and robot name

## Built-in Plugins

Tinko comes with four powerful plugins ready to use:

### Activity Timer
Visual countdown timer with configurable preset profiles for different classroom activities. Features RGB LED feedback showing remaining time (green to yellow to red).

[Learn more](teacher/plugins/activity-timer.md){ .md-button }

### Noise Monitor
Dual RGB LED classroom noise visualization with real-time WebSocket updates. Helps students self-regulate their volume levels.

[Learn more](teacher/plugins/noise-monitor.md){ .md-button }

### Routines
Text-to-speech classroom routines with USB presenter support. Includes hand-warming exercises, finger stretches, and calming transitions.

[Learn more](teacher/plugins/routines.md){ .md-button }

### Touch Piano
Learn circuits through musical interaction. Connect bananas, foil, or copper tape to GPIO pins and play piano notes.

[Learn more](teacher/plugins/touch-piano.md){ .md-button }

## Quick Start

<div class="grid cards" markdown>

-   :material-school:{ .lg .middle } __Teacher Guide__

    ---

    Get started using Tinko in your classroom. Installation, dashboard overview, and plugin usage.

    [:octicons-arrow-right-24: Getting Started](teacher/overview.md)

-   :material-code-braces:{ .lg .middle } __Developer Guide__

    ---

    Set up your development environment, understand the architecture, and create custom plugins.

    [:octicons-arrow-right-24: Developer Setup](developer/setup.md)

-   :material-memory:{ .lg .middle } __Hardware Setup__

    ---

    Connect LEDs, sensors, and other components to your Raspberry Pi GPIO pins.

    [:octicons-arrow-right-24: Requirements](developer/hardware/requirements.md)

</div>

## Access URLs

Once Tinko is running, access these endpoints:

| Endpoint | URL |
|----------|-----|
| Dashboard | `http://localhost:8000/` |
| Admin Panel | `http://localhost:8000/admin/` |
| Plugin Management | `http://localhost:8000/admin/plugins/` |
| Activity Timer | `http://localhost:8000/plugins/edupi/activity_timer/` |
| Noise Monitor | `http://localhost:8000/plugins/edupi/noise_monitor/` |
| Routines | `http://localhost:8000/plugins/edupi/routines/` |
| Touch Piano | `http://localhost:8000/plugins/edupi/touch_piano/` |

## System Requirements

- Raspberry Pi 4 (2GB+ RAM) or Pi 3B+
- Python 3.12 or higher
- UV package manager
- USB microphone or microphone module
- RGB LEDs and resistors
- Speaker or headphones

## Support

- GitHub: [github.com/rudolf-erdei/edu-pi](https://github.com/rudolf-erdei/edu-pi)
- Documentation: You're reading it!

---

**Happy Teaching!** 🎓

_Made with love for education_
