# Activity Timer

Visual countdown timer for classroom activities with configurable preset profiles and RGB LED feedback.

## Overview

The Activity Timer helps manage classroom time with visual countdown displays and LED indicators. Perfect for activity transitions, breaks, and timed exercises.

**URL**: `/plugins/edupi/activity_timer/`

## Hardware Requirements

- RGB LED (common cathode)
- 3x 220Ω resistors
- Optional: Buzzer module
- Breadboard and jumper wires

### GPIO Pin Connections

| Component | GPIO Pin | Physical Pin | Color |
|-----------|----------|--------------|-------|
| LED Red | 17 | 11 | Red wire |
| LED Green | 27 | 13 | Green wire |
| LED Blue | 22 | 15 | Blue wire |
| Buzzer (optional) | 24 | 18 | Any wire |

## Preset Profiles

Four built-in presets for common classroom scenarios:

### Minute of Silence
- **Duration**: 60 seconds
- **Display Color**: Indigo (calming)
- **LED Colors**: Blue tones
- **Use Case**: Calming students before activities

### Break Time
- **Duration**: 10 minutes
- **Display Color**: Green
- **LED Colors**: Green to yellow to red
- **Use Case**: Standard break periods

### Activity
- **Duration**: 30 minutes
- **Display Color**: Amber
- **LED Colors**: Amber to orange to red
- **Use Case**: Regular class activities

### Custom
- **Duration**: User-defined (1-120 minutes)
- **Display Color**: User-selected
- **LED Colors**: Configurable
- **Use Case**: Any custom timing need

## Interface Controls

### Main Timer Display

Large digital countdown showing:
- **Remaining Time**: Minutes and seconds
- **Status**: Running, Paused, or Stopped
- **Progress**: Visual indicator

### Preset Buttons

Click any preset to load its configuration:

1. **Minute of Silence** - Blue button
2. **Break Time** - Green button
3. **Activity** - Amber button
4. **Custom** - Opens duration selector

### Playback Controls

| Button | Action | Keyboard Shortcut |
|--------|--------|-------------------|
| Start | Begin countdown | Space |
| Pause | Pause timer | Space |
| Resume | Continue countdown | Space |
| Stop | End timer, reset to 0 | Escape |

## LED Visual Feedback

The RGB LED shows remaining time visually:

| Time Remaining | LED Color | Meaning |
|----------------|-----------|---------|
| > 50% | Green | Plenty of time |
| 20-50% | Yellow | Time passing |
| < 20% | Red | Time running out |
| Finished | Flashing Red | Time's up! |

!!! note "LED Brightness"
    Adjust LED brightness in Settings to match your classroom lighting.

## Custom Timer

Create timers with custom durations:

1. Click **Custom** preset button
2. Enter duration (1-120 minutes)
3. Select display color
4. Click **Start**

## Configuration Options

Access settings at `/plugins/edupi/activity_timer/config/` or via the main Settings page:

- **Default Duration**: Default timer length (1-120 min)
- **LED Brightness**: LED intensity percentage (10-100%)
- **Warning Threshold**: When LED changes color (5-50% remaining)
- **Enable Buzzer**: Play sound when timer completes

## Session Tracking

Each timer session is recorded in the database:

- Start time
- Duration
- Preset used
- Completion status

View history in the plugin interface.

## Use Cases

### Transition Management

Set a 2-minute timer for cleanup:
1. Select **Custom** preset
2. Set duration to 2 minutes
3. Choose calming blue color
4. Click Start

Students see the LED change from green → yellow → red, helping them manage time.

### Focus Sessions

Use **Minute of Silence** before writing activities:
- Calming blue display
- 60-second countdown
- Students prepare mentally while watching the timer

### Activity Timing

Standard 30-minute activity:
1. Select **Activity** preset
2. Click Start
3. LED shows progress throughout
4. Optional buzzer alerts at end

## Best Practices

### LED Brightness

- **Classroom with natural light**: 80-100%
- **Dim classroom**: 50-70%
- **Dark room**: 30-50%

### Warning Threshold

- **Younger students**: 30% (earlier warning)
- **Older students**: 20% (standard)
- **Urgent activities**: 10% (minimal warning)

### Combining with Other Plugins

The Activity Timer runs independently:

1. Start Activity Timer
2. Navigate to Noise Monitor
3. Check classroom noise while timer runs
4. Return to see remaining time

See [Background Activities](../background-activities.md) for details.

## Troubleshooting

### LED Not Lighting

1. Check wiring connections
2. Verify GPIO pins in plugin settings
3. Check LED brightness setting (> 0%)
4. Ensure LED is common cathode

### Buzzer Not Working

1. Verify buzzer polarity (+/-)
2. Check buzzer enabled in settings
3. Test with multimeter

### Timer Not Starting

1. Check browser console for JavaScript errors
2. Verify WebSocket connection (if applicable)
3. Refresh page and try again

### Wrong Colors

- Check RGB LED wiring matches pin assignments
- Common cathode LEDs have different wiring than common anode

## Technical Details

- Updates every second during countdown
- Uses threading for background operation
- Stores session data in SQLite database
- HTTP polling for web interface updates
- WebSocket support planned for future versions

## Related Documentation

- [Dashboard](../dashboard.md) - Navigate between plugins
- [Settings](../settings.md) - Configure plugin options
- [Background Activities](../background-activities.md) - Independent operation
- [GPIO Wiring](../../developer/hardware/wiring.md) - Hardware setup guide
