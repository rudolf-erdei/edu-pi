# Routines

Text-to-speech classroom routines with USB presenter support for warm-ups, transitions, and cooldowns.

## Overview

The Routines plugin provides guided classroom activities with synchronized text highlighting and multiple TTS engine support. Perfect for hand-warming exercises, calming transitions, and instructional sequences.

**URL**: `/plugins/edupi/routines/`

**WebSocket**: `ws://localhost:8000/ws/routines/`

## Hardware Requirements

- Speaker or headphones (3.5mm jack or USB)
- USB wireless presenter (optional but recommended)
- Internet connection (for online TTS engines)

## Features

### Multi-Engine TTS Support

Three text-to-speech engines available:

| Engine | Type | Quality | Requirements |
|--------|------|---------|--------------|
| pyttsx3 | Offline | Good | None |
| edge-tts | Online | Excellent | Internet |
| gTTS | Online | Good | Internet |

**Recommendation**: Use pyttsx3 for offline reliability, edge-tts when internet is available.

### Audio File Upload

Override TTS with custom audio files:

- **Supported Formats**: MP3, WAV
- **Use Cases**: Music, custom recordings, better pronunciations
- **Fallback**: Automatically uses TTS if no file uploaded

### USB Presenter Support

Control routines wirelessly with standard USB presenters (Logitech, Kensington, etc.):

**Button Mappings:**

| Presenter Button | Action | Default Mapping |
|------------------|--------|-----------------|
| Next | Advance line | Next button |
| Previous | Go back | Previous button |
| Play/Pause | Pause/resume | Play button |
| Stop | End routine | Black screen button |

!!! note "Presenter Detection"
    Plug in the USB presenter and it's automatically detected. No drivers needed on Linux systems.

## Pre-built Routines

### Hand Warming Exercise

Prepares students for writing activities:

```
"Let's warm up our hands for writing!
Rub your palms together, rub, rub, rub.
Now your fingers, wiggle them up high.
Shake them out, shake, shake, shake.
Ready to write, nice and warm!"
```

### Finger Stretch

Hand stretching routine:

```
"Let's stretch our fingers!
Open wide, close tight.
Wiggle left, wiggle right.
Roll your wrists around and around.
Stretch complete, hands ready!"
```

### Deep Breathing

Calming transition routine:

```
"Take a deep breath in... hold... and out.
Breathe in peace... hold... breathe out stress.
Your body is calm, your mind is clear.
Ready to learn!"
```

## Creating Routines

### Step 1: Create Category

Organize routines into categories:

1. Go to Routines dashboard
2. Click **Categories**
3. Click **Add Category**
4. Enter name (e.g., "Warm-up", "Transition", "Cooldown")

### Step 2: Create Routine

1. Click **New Routine**
2. Enter title
3. Select category
4. Add description (optional)
5. Add content (one instruction per line)

### Step 3: Configure Audio

**Option A: Use TTS**
- Select TTS engine (pyttsx3, edge-tts, gTTS)
- Set speed (0.5x - 2.0x)
- Select language

**Option B: Upload Audio**
- Click **Upload Audio**
- Select MP3 or WAV file
- Audio will play instead of TTS

### Step 4: Save and Test

1. Click **Save**
2. Click **Test TTS** to preview
3. Adjust settings if needed

## Playback Interface

### Full-Screen Player

When you start a routine, it opens in full-screen mode with:

- **Current Line**: Highlighted in large text
- **Previous/Next Lines**: Smaller, dimmed text
- **Progress Indicator**: Shows position in routine
- **Control Bar**: Play/pause, previous, next, stop

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Space | Play/Pause |
| → | Next line |
| ← | Previous line |
| Escape | Stop routine |

### Visual Highlighting

Text highlighting synchronizes with speech:

- **Current line**: Bold, bright color
- **Previous lines**: Dimmed
- **Next lines**: Grayed out
- **Auto-advance**: Moves to next line automatically

## Categories

Organize routines by purpose:

| Category | Purpose | Examples |
|----------|---------|----------|
| Warm-up | Prepare for activity | Hand warming, stretching |
| Transition | Between activities | Breathing, movement breaks |
| Cooldown | End of session | Calming, reflection |
| Custom | Any purpose | Teacher-defined |

## WebSocket Synchronization

Real-time synchronization across all connected clients:

- **Line Updates**: Current line synced instantly
- **Playback State**: Play/pause synchronized
- **Progress**: All see the same position
- **Control**: Any client can control playback

!!! tip "Multi-Device Setup"
    Open the routine player on your phone while presenting on the main screen. Controls sync between devices!

## Configuration Options

Access settings via **Settings** > **Routines**:

### Default TTS Engine

Choose your preferred default engine:
- pyttsx3 (offline, works everywhere)
- edge-tts (high quality, requires internet)
- gTTS (Google TTS, requires internet)

### Default TTS Speed

- **Slow**: 0.5x - 0.8x (for young learners)
- **Normal**: 1.0x (standard)
- **Fast**: 1.2x - 2.0x (for quick routines)

### Presenter Button Mappings

Customize which presenter buttons perform which actions:

1. Go to Settings > Routines > Presenter Mapping
2. Select button and assign action
3. Click Save

## Best Practices

### Routine Length

- **Warm-ups**: 30-60 seconds
- **Transitions**: 15-30 seconds
- **Cooldowns**: 30-120 seconds

Keep routines short for maximum engagement.

### Line Breaks

Place line breaks at natural pauses:

```
Good:
"Take a deep breath in...
hold...
and breathe out."

Less Good:
"Take a deep breath in... hold... and breathe out."
```

### TTS Speed Selection

- **Young students (K-2)**: 0.8x speed
- **Standard (3-5)**: 1.0x speed
- **Quick instructions**: 1.2x speed

### Presenter Usage

- Keep presenter in hand during routines
- Walk around the room while presenting
- Use visual cues along with audio
- Test presenter buttons before class

## Troubleshooting

### No Audio Output

1. Check speaker/headphone connection
2. Verify volume is up
3. Test with: `speaker-test -t wav`
4. Check audio device in settings

### TTS Not Working

**pyttsx3 issues:**
- Install espeak: `sudo apt-get install espeak`
- Check espeak installation: `espeak "test"`

**edge-tts/gTTS issues:**
- Verify internet connection
- Check firewall settings
- Try offline pyttsx3 as backup

### Presenter Not Detected

1. Unplug and re-plug USB receiver
2. Check system recognizes device: `lsusb`
3. Verify evdev library installed (Linux)
4. Check button mappings in settings

### WebSocket Disconnected

- Refresh page to reconnect
- Check network connection
- Verify WebSocket URL
- Look for firewall blocking

### Sync Issues

If text and audio get out of sync:

1. Pause playback
2. Click the correct line
3. Resume playback
4. Or stop and restart routine

## Technical Details

- **Audio**: pygame for playback
- **TTS**: pyttsx3 (offline), edge-tts, gTTS (online)
- **Presenter**: evdev library for USB input (Linux)
- **WebSocket**: Django Channels
- **File Storage**: Local filesystem in `media/routines/`

## Data Management

### Session Tracking

Each routine session is logged:

- Routine name
- Start/end time
- Completion percentage
- Audio engine used

### File Storage

- Audio files stored in `media/routines/`
- Automatic file naming with timestamps
- Can be backed up by copying directory

## Related Documentation

- [Background Activities](../background-activities.md) - Runs when you navigate away
- [Settings](../settings.md) - Configure TTS and presenter
- [Dashboard](../dashboard.md) - Access routines
- [WebSocket](../../developer/websocket.md) - Real-time sync technical details
