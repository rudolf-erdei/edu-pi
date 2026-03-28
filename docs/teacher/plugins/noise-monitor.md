# Noise Monitor

Real-time classroom noise visualization with dual RGB LED feedback and WebSocket-based updates.

## Overview

The Noise Monitor helps students self-regulate their volume levels by providing continuous visual feedback through RGB LEDs. Perfect for group work and maintaining appropriate classroom noise levels.

**URL**: `/plugins/edupi/noise_monitor/`

**WebSocket**: `ws://localhost:8000/ws/noise-monitor/`

## Hardware Requirements

- 2x RGB LEDs (common cathode)
- 6x 220Ω resistors
- USB microphone or microphone module
- Breadboard and jumper wires

### GPIO Pin Connections

**LED 1 (Instant Noise - 10-second average):**

| Component | GPIO Pin | Physical Pin | Color |
|-----------|----------|--------------|-------|
| LED 1 Red | 5 | 29 | Red wire |
| LED 1 Green | 6 | 31 | Green wire |
| LED 1 Blue | 13 | 33 | Blue wire |

**LED 2 (Session Average - 5-10 minute average):**

| Component | GPIO Pin | Physical Pin | Color |
|-----------|----------|--------------|-------|
| LED 2 Red | 19 | 35 | Red wire |
| LED 2 Green | 26 | 37 | Green wire |
| LED 2 Blue | 16 | 36 | Blue wire |

## Dual LED System

The Noise Monitor uses two separate RGB LEDs with different purposes:

### LED 1: Instant Noise

Shows the **current** noise level over a short time window:

- **Time Window**: Configurable (default: 10 seconds, range: 5-60s)
- **Purpose**: Immediate feedback on current noise
- **Use Case**: Students get instant feedback when they get too loud

### LED 2: Session Average

Shows the **overall** noise level for the session:

- **Time Window**: Configurable (default: 5 minutes, range: 1-30min)
- **Purpose**: Track overall session noise quality
- **Use Case**: Reward quiet sessions, identify problematic periods

## Noise Profiles

Choose from four preset noise profiles or create custom thresholds:

### Test Profile
- **Yellow Threshold**: 30 dB
- **Red Threshold**: 50 dB
- **Use Case**: Silent mode, testing

### Teaching Profile
- **Yellow Threshold**: 40 dB
- **Red Threshold**: 70 dB
- **Use Case**: Normal classroom teaching

### Group Work Profile
- **Yellow Threshold**: 50 dB
- **Red Threshold**: 80 dB
- **Use Case**: Collaborative activities, discussions

### Custom Profile
- **Yellow Threshold**: User-defined
- **Red Threshold**: User-defined
- **Use Case**: Specific classroom acoustics

## LED Color Coding

Both LEDs use the same color scheme:

| Noise Level | LED Color | Meaning |
|-------------|-----------|---------|
| Below Yellow | Green | Quiet/Silent |
| Yellow Threshold | Yellow | Moderate noise |
| Red Threshold | Red | Too loud |

!!! tip "Visual Feedback"
    Green = Good, Yellow = Caution, Red = Too Loud

## Web Interface

### Main Display

- **Instant Noise Bar**: Visual representation of current noise (0-100%)
- **Session Average Bar**: Visual representation of session average
- **Digital Readings**: Numeric dB values
- **LED Indicators**: On-screen LEDs matching physical LEDs

### Historical Data

View recent noise readings:

- Last 50 readings displayed
- Timestamp for each reading
- Color-coded noise levels
- Helps identify patterns

### Session Controls

| Button | Action |
|--------|--------|
| Start Monitoring | Begin noise measurement |
| Stop Monitoring | Pause noise measurement |
| Reset Session | Clear session average data |
| Profile Selector | Choose noise profile |

## Configuration Options

Access settings at `/plugins/edupi/noise_monitor/config/`:

### Time Windows

- **Instant Window**: Seconds for instant average (5-60s)
- **Session Window**: Minutes for session average (1-30min)

### LED Settings

- **LED Brightness**: Intensity percentage (10-100%)
- **Enable Monitoring**: Turn monitoring on/off

### Thresholds

Configure custom profile thresholds:

- **Yellow Threshold**: Moderate noise level
- **Red Threshold**: High noise level

## Real-Time Updates

The Noise Monitor uses WebSocket for real-time updates:

- **Update Frequency**: 10 times per second
- **Latency**: < 100ms
- **Auto-reconnect**: Reconnects if connection drops
- **Fallback**: HTTP polling if WebSocket unavailable

!!! note "WebSocket Connection"
    The browser automatically connects to WebSocket when the page loads. Look for the connection status indicator.

## Use Cases

### Group Work Monitoring

1. Select **Group Work** profile
2. Click **Start Monitoring**
3. Place LED where students can see it
4. Students self-regulate when LED turns yellow/red

### Silent Reading Time

1. Select **Test** profile (lowest thresholds)
2. Start monitoring
3. LED provides instant feedback
4. Session average shows overall compliance

### Transition Management

1. Monitor noise during transitions
2. Session average shows if transitions are getting quieter over time
3. Use data to encourage quieter transitions

### Classroom Acoustics Testing

1. Use **Custom** profile
2. Set thresholds based on your room
3. Test different times of day
4. Find optimal thresholds for your space

## Best Practices

### LED Placement

- Place LEDs where students can easily see them
- Consider using diffusers or covers for softer light
- Avoid direct eye contact with bright LEDs
- Position at student eye level when possible

### Profile Selection

- **Start of class**: Teaching profile
- **Group work**: Group Work profile
- **Tests/Silent work**: Test profile
- **Experiment**: Custom profile for your room

### Session Management

- **Reset session** at the start of each class period
- Keep session window consistent for fair comparison
- Review historical data to identify patterns

### Calibration

1. Set all thresholds in a quiet room
2. Note the baseline reading
3. Set yellow threshold 10-20% above baseline
4. Set red threshold at unacceptable level

## Troubleshooting

### LEDs Not Responding

1. Check all 6 wire connections
2. Verify RGB LED common cathode configuration
3. Check LED brightness setting (> 0%)
4. Ensure monitoring is enabled

### No Noise Readings

1. Check USB microphone connection
2. Verify microphone is not muted
3. Check system audio settings
4. Test microphone with: `arecord -l`

### WebSocket Disconnected

1. Check browser console for errors
2. Verify WebSocket URL is correct
3. Refresh page to reconnect
4. Check if firewall blocks port 8000

### LEDs Show Wrong Colors

- Common cathode vs common anode confusion
- Check wiring matches pin assignments
- Verify profile thresholds are reasonable

### Noisy Baseline

- Adjust thresholds upward
- Check for environmental noise sources
- Consider acoustic treatment
- Use custom profile with higher thresholds

## Technical Details

- **Audio Sampling**: 10 times per second
- **Averaging**: Exponential moving average
- **WebSocket Protocol**: Django Channels
- **Database**: Stores last 1000 readings
- **GPIO Control**: PWM for smooth color transitions

## Data Privacy

- Noise data stays local on Raspberry Pi
- No cloud storage
- Historical data auto-deletes after 1000 readings
- Can be configured to store less data

## Related Documentation

- [Background Activities](../background-activities.md) - Runs when you navigate away
- [Settings](../settings.md) - Configure plugin options
- [GPIO Wiring](../../developer/hardware/wiring.md) - Hardware setup guide
- [WebSocket](../../developer/websocket.md) - Technical implementation
