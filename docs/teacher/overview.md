# Overview

Welcome to the Tinko Teacher Guide! This section will help you understand what Tinko is, how it can enhance your classroom, and how to get started.

## What is Tinko?

Tinko is an educational platform that runs on a Raspberry Pi computer, designed specifically for interactive classroom activities. It combines physical hardware (LEDs, sensors, touch pads) with a web-based dashboard that you control from any device on your network.

## Why Use Tinko?

### Engage Students with Physical Interaction

Traditional classroom management often relies on verbal instructions. Tinko adds a visual, interactive element that captures students' attention:

- **Noise Monitor**: Students see immediate visual feedback (colored LEDs) when the classroom gets too loud
- **Touch Piano**: Students learn about circuits by touching conductive materials (bananas, foil, copper tape)
- **Activity Timer**: Visual countdown with LED progress bar keeps students aware of time remaining
- **Routines**: Text-to-speech guidance for warm-ups and transitions

### Easy to Use

You don't need to be technical to use Tinko:

- Simple web interface accessible from any device
- One-click activation of activities
- Automatic background operation - activities continue even when you switch pages
- Clear visual indicators and status messages

### Customizable

Make Tinko your own:

- Set your school name and upload your logo
- Customize the robot's name
- Configure plugin settings to match your classroom needs
- Support for multiple languages (English and Romanian)

## Classroom Use Cases

### Transition Management

Use the **Activity Timer** to manage transitions between activities:

- Set a 2-minute timer for cleanup time
- LED shows green (plenty of time), then yellow (hurry up), then red (time's up)
- Students learn to manage their time visually

### Classroom Noise Control

Activate the **Noise Monitor** during group work:

- LED changes from green to yellow to red based on noise level
- Students self-regulate when they see the color change
- Dual LEDs show both instant noise and session average

### Sensory Breaks

Use the **Touch Piano** for sensory activities:

- Students touch bananas or foil connected to GPIO pins
- Each touch plays a musical note
- Combines music, electronics, and tactile learning

### Daily Routines

Automate your daily routines with the **Routines** plugin:

- Play hand-warming exercises before writing
- Guide breathing exercises for calming transitions
- USB presenter control allows you to advance from anywhere in the room

## Understanding the Interface

### Apps vs Plugins

Tinko uses two terms for the same thing:

- **Plugins** (technical term): Software modules that extend functionality
- **Apps** (teacher term): What you see on your dashboard

When you open the dashboard, you'll see cards for each "App" - these are the plugins you can activate.

### The Dashboard

The main dashboard at `http://localhost:8000/` shows:

- All installed apps with icons
- Click any app to open it
- Language selector in the top navigation
- Settings link for configuration

## Next Steps

Ready to get started?

1. **[Installation](installation.md)** - Install Tinko on your Raspberry Pi
2. **[First Steps](first-steps.md)** - Create your admin account and explore
3. **[Dashboard](dashboard.md)** - Learn to navigate the interface
4. **[Settings](settings.md)** - Personalize Tinko for your school

Or jump to specific plugin guides:

- [Activity Timer](plugins/activity-timer.md)
- [Noise Monitor](plugins/noise-monitor.md)
- [Routines](plugins/routines.md)
- [Touch Piano](plugins/touch-piano.md)
