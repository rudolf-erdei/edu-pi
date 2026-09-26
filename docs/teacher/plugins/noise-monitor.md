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

## Microphone

The monitor records from a USB sound card. No configuration is normally needed:
on startup it picks the first USB capture device it finds, and on a Tinko Pi that
is the classroom microphone.

### Choosing a Microphone

The **Microphone** picker on the configuration page lists every device that can
record, plus an **Automatic** entry. Automatic is right unless the room has more
than one microphone — the Pi's HDMI output cannot capture at all and is never
offered.

The choice is stored as a **name** as well as an index. ALSA renumbers the sound
cards when a USB microphone is replugged, so a saved index can end up pointing at
a device that cannot record; matching on the name instead means the choice
survives being unplugged and moved to another port.

### The 0-100 Scale, Shown in dB

The dashboard reads in **dB**, and the scale behind those numbers is the
plugin's own **0-100 relative scale**. It is not calibrated dB SPL: the
microphone has no absolute reference, so 21 dB on the graph means "the same
loudness as when 21 was useful to you", and it will not agree with a phone
sound-meter app in the same room. Use it to compare moments and lessons with
each other, which is what the thresholds and the LED bands are for.

Internally the microphone's RMS amplitude is converted to dBFS and mapped across
a 60 dB window (`-60 dBFS` → 0, `0 dBFS` → 100), so the scale is decibel-shaped
and evenly spaced, with the microphone's own gain setting as its zero point.
With the reference USB microphone that puts a quiet classroom around 15-25,
normal conversation in the yellow band, and a loud room in the red.

### If the Microphone Stops

The dashboard says so plainly rather than showing a plausible-looking number:

| Banner | Meaning |
|--------|---------|
| *(none)* | Levels on screen come from the microphone |
| **Microphone unavailable** | Monitoring is running but no device could be opened; the readings shown are the last ones measured |
| **No microphone support** | The audio library is missing on this device; the readings are simulated |

Readings are never invented when a real microphone is expected. If the
microphone is unplugged mid-session the display holds its last values and the
banner explains why.

## Noise Profiles

Choose from four preset noise profiles or create custom thresholds:

### Test Profile
- **Yellow Threshold**: Level 30
- **Red Threshold**: Level 50
- **Use Case**: Silent mode, testing

### Teaching Profile
- **Yellow Threshold**: Level 40
- **Red Threshold**: Level 70
- **Use Case**: Normal classroom teaching

### Group Work Profile
- **Yellow Threshold**: Level 50
- **Red Threshold**: Level 80
- **Use Case**: Collaborative activities, discussions

### Custom Profile
- **Yellow Threshold**: User-defined (0-100)
- **Red Threshold**: User-defined (0-100)
- **Use Case**: Specific classroom acoustics

### Renaming and Deleting Profiles

There is exactly one profile per type, so a profile name cannot be created
twice. On the configuration page, each profile card carries a **Rename** and a
**Delete** button:

- **Rename** opens a small form with the name and the description. Rename
  "Teaching" to "Citit în liniște" if that is what the class calls it. The new
  name is what the profile dropdown offers from then on. A name that is empty,
  longer than 100 characters, or already used by another profile is refused and
  the old name is kept.
- **Delete** removes a profile you never use. The card of the profile the
  dropdown currently points at is marked **In use**.

Deleting the profile in use is allowed: the configuration is left without a
profile and the monitor falls back to the default thresholds (Level 40 / 70)
until another profile is chosen. Deleting the *last* profile is refused,
because the configuration page cannot be submitted with an empty dropdown.

## Robot Face

If the LCD display is fitted, the robot's face shows the same verdict as LED 2
(the session average), on top of the LEDs:

| Session Colour | Face |
|----------------|------|
| Green | Happy |
| Yellow | Neutral |
| Red | Sad |

The face follows the *session* average rather than the instant one on purpose:
the face is the judgement on the lesson, and following the live reading would
have it change every time one child shouts. It changes only when the colour
changes, and goes back to Happy when monitoring stops.

No setup is needed — Noise Monitor already depends on the LCD Display plugin.
On a Pi without a display the monitor runs normally and no face is drawn.

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
- **Digital Readings**: Numeric level, 0-100
- **LED Indicators**: On-screen LEDs matching physical LEDs

### Historical Data

The **Noise Over Time** card draws the last **20 minutes** as a graph:

- **Session Average** — the solid line, the same figure shown on the card above
- **Instant Noise** — the fainter line, which is noisier by nature
- **Coloured bands** — the thresholds the LEDs use, so a line inside the green
  band means the LEDs were green at that moment
- **Clock times** at each end, so it is clear how much time the window covers
- **The value of each line, in dB**, printed at its right-hand end — the newest
  session average and the newest instant average. The axis on the left is
  labelled in dB too, so a height on the graph can be read as a number

The graph is drawn by the server as part of the page. It needs no internet
connection and no charting library, so it looks the same on a Pi with no network
as it does on a laptop.

**It keeps up on its own.** Leave the page open during a lesson and the graph
refreshes itself once a minute: readings taken since the page was opened appear,
the window slides forward, and the clock at each end moves with it. Nothing has
to be reloaded, and no button has to be pressed.

A minute is the pace at which the graph moves, so it advances in steps of about
a minute rather than smoothly. The two bars and the numbers above it are live, so
they can read up to a minute ahead of the line on the graph. A hidden tab (one
you have switched away from) is not refreshed, so that it does not make the Pi
work for nobody; switching back to the tab refreshes it straight away.

One reading is stored every 5 seconds while the meter runs, not one per
measurement — 240 of them across the window, about twelve per refresh. The
measurement itself is ten times a second; storing all of them would fill the
database and leave this window spanning a few seconds.

The exact numbers are still available to other software through
`/plugins/edupi/noise_monitor/api/history/`.

### Session Controls

| Button | Action |
|--------|--------|
| Start Monitoring | Begin noise measurement |
| Stop Monitoring | Pause noise measurement |
| Reset Session | Clear session average data |
| Profile Selector | Choose noise profile |

### Automatic Start

**The meter is already running when the Pi is switched on.** Nobody has to open
this page and press Start — the LEDs and the robot face come up on their own,
which is what a classroom Pi that is switched on and left alone needs.

To stop it happening, untick **Start Automatically** on the configuration page
and save. With it unticked the meter only runs when someone presses Start
Monitoring.

The switch is per configuration, so the Start and Stop buttons keep working
either way.

## Configuration Options

Access settings at `/plugins/edupi/noise_monitor/config/`:

### Time Windows

- **Instant Window**: Seconds for instant average (5-60s)
- **Session Window**: Minutes for session average (1-30min)

### Start

- **Start Automatically**: Start the meter as soon as the Pi is switched on
  (on by default)

### Microphone

- **Microphone**: Which capture device to record from (Automatic by default)

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

The dashboard banner says which of these applies, so read it first.

1. Check the USB microphone connection
2. List the capture devices: `arecord -l`
   — the classroom microphone appears as `card 1: Device [USB PnP Sound Device]`
3. Check the service log: `journalctl -u tinko -n 50 | grep -i micro`
4. Check the audio library is installed: `ldconfig -p | grep portaudio`
5. Confirm the selected device on the configuration page is still present; set it
   back to **Automatic** if the room has only one microphone

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

- **Audio Sampling**: 44.1 kHz mono, 50 ms blocks, read 10 times per second
- **Microphone Access**: `sounddevice` over ALSA (apt package `libportaudio2`)
- **Averaging**: Mean of the readings inside the configured time window
- **Level Scale**: RMS → dBFS, mapped over a 60 dB window to 0-100, shown in dB
  on the graph; relative to the microphone's gain, not calibrated to sound
  pressure (see [The 0-100 Scale, Shown in dB](#the-0-100-scale-shown-in-db))
- **Chart Readouts**: the newest value of each line, in dB, printed at the end of
  the line it belongs to
- **Chart Refresh**: the page re-fetches the card every 60 s and swaps it in by
  id (`history-chart`); the server draws it, so the geometry stays in one place
  and no charting library is needed
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
