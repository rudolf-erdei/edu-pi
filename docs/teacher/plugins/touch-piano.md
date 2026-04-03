# Touch Piano

Interactive musical experience using conductive materials connected to GPIO pins. Learn about circuits while making music!

## Overview

The Touch Piano transforms everyday conductive materials into musical keys. Students learn about circuits, conductivity, and music while having fun.

**URL**: `/plugins/edupi/touch_piano/`

## Hardware Requirements

- 6 touch sensors or capacitive touch inputs
- Conductive materials (bananas, foil, copper tape, etc.)
- Speaker or headphones (3.5mm jack)
- 6x 10kΩ pull-up resistors (if using bare wire)
- Breadboard and jumper wires

### GPIO Pin Connections

**6 Piano Keys:**

| Key | Note | GPIO Pin | Physical Pin | Wire Color |
|-----|------|----------|--------------|------------|
| Key 1 | C (Do) | 4 | 7 | Red |
| Key 2 | D (Re) | 7 | 26 | Orange |
| Key 3 | E (Mi) | 20 | 38 | Yellow |
| Key 4 | F (Fa) | 21 | 40 | Green |
| Key 5 | G (Sol) | 12 | 32 | Blue |
| Key 6 | A (La) | 2 | 3 | Purple |

## How It Works

### Capacitive Touch Sensing

The Touch Piano uses capacitive touch sensing to detect when conductive materials are touched:

1. **Circuit Setup**: Conductive material connected to GPIO pin
2. **Pull-up Resistor**: Maintains HIGH state when not touched
3. **Touch Detection**: When touched, capacitance changes
4. **Signal Processing**: GPIO detects the change and triggers note
5. **Audio Output**: pygame synthesizes and plays the note

### Conductive Materials

Many everyday items work as piano keys:

| Material | Conductivity | Best For |
|----------|--------------|----------|
| Bananas | Excellent | Fun demonstrations |
| Aluminum Foil | Excellent | Custom shapes |
| Copper Tape | Excellent | Permanent installations |
| Play-Doh | Good | Child-safe |
| Water | Moderate | Science experiments |
| Plants | Moderate | Living piano |

!!! tip "Best Results"
    Moist materials (like fresh fruit) work better than dry materials.

## Interface

### Piano Display

The web interface shows a 6-key piano:

- **Visual Keys**: Click to play
- **Key Labels**: Shows note names (C, D, E, F, G, A)
- **Status**: Shows which key is currently pressed
- **Volume Control**: Adjust output level

### Keyboard Shortcuts

Play using your computer keyboard:

| Computer Key | Piano Key | Note |
|--------------|-----------|------|
| A | Key 1 | C |
| S | Key 2 | D |
| D | Key 3 | E |
| F | Key 4 | F |
| G | Key 5 | G |
| H | Key 6 | A |

## Building the Circuit

### Option 1: Simple Wire Connection

1. Connect GPIO pins to conductive materials with wire
2. Add 10kΩ pull-up resistors between each pin and 3.3V
3. Connect common ground
4. Touch material to play

### Option 2: Using Capacitive Touch Sensors (TTP223)

1. Connect TTP223 modules to GPIO pins
2. Connect sensor outputs to materials
3. No pull-up resistors needed
4. More reliable touch detection

### Wiring Diagram

```
GPIO 4 (Pin 7) ----[10kΩ]---- 3.3V (Pin 1)
     |
     +---- Wire to banana/foil

Repeat for all 6 keys:
- GPIO 4 (Pin 7) for Key 1 (C)
- GPIO 7 (Pin 26) for Key 2 (D)
- GPIO 20 (Pin 38) for Key 3 (E)
- GPIO 21 (Pin 40) for Key 4 (F)
- GPIO 12 (Pin 32) for Key 5 (G)
- GPIO 2 (Pin 3) for Key 6 (A)
```

!!! warning "Safety"
    Always use 3.3V power, not 5V. High voltage can damage GPIO pins.

## Learning Objectives

### Science Concepts

- **Conductivity**: What materials conduct electricity?
- **Circuits**: How do circuits work?
- **Resistance**: Why do some materials work better?
- **Capacitance**: How does touch sensing work?

### Music Concepts

- **Pitch**: Higher/lower notes
- **Octaves**: Scale relationships
- **Melody**: Creating simple tunes
- **Rhythm**: Timing and beats

### Technology Concepts

- **GPIO**: General Purpose Input/Output
- **Digital Input**: Reading on/off states
- **Audio Synthesis**: Creating sounds programmatically
- **Human-Computer Interaction**: Physical computing

## Configuration Options

Access settings via **Settings** > **Touch Piano**:

### Volume

- Range: 0-100%
- Default: 80%
- Adjust based on classroom noise level

### Audio Device

- **default**: System default audio
- **hw:0,0**: Hardware device 0
- **plughw:1,0**: USB audio device

To list available devices:

```bash
aplay -l
```

### Sensitivity

- Range: 1-10
- Default: 5
- Higher = more sensitive touch detection
- Increase if touches aren't registering
- Decrease if getting false triggers

### Visual Feedback

- Enable/disable web interface highlighting
- Shows which key is pressed
- Helpful for debugging

## Session Tracking

The Touch Piano tracks playing sessions:

- Session start/end times
- Key press counts per key
- Total play duration
- Most frequently used keys

View statistics in the plugin interface.

## Classroom Activities

### Activity 1: Circuit Discovery

**Objective**: Identify conductive materials

1. Gather various objects (pencil, eraser, coin, foil, etc.)
2. Test each with the piano
3. Sort into "conductive" and "non-conductive" piles
4. Discuss why some work and others don't

### Activity 2: Build a Banana Piano

**Objective**: Create a working musical instrument

1. Connect 6 bananas to GPIO pins
2. Test each banana-key
3. Play simple songs (Twinkle Twinkle, etc.)
4. Experiment with different fruits

### Activity 3: Copper Tape Art

**Objective**: Create permanent touch pads

1. Design piano key shapes on cardboard
2. Apply copper tape to create touch areas
3. Connect to GPIO pins
4. Play and decorate your custom piano

### Activity 4: Science of Sound

**Objective**: Understand pitch and frequency

1. Play each key, note the pitch
2. Compare high vs low notes
3. Discuss why C is lower than A
4. Create simple melodies

## Troubleshooting

### No Sound

1. Check speaker connection
2. Verify volume > 0%
3. Test audio device: `speaker-test`
4. Check pygame audio initialization

### Keys Not Responding

1. Check wire connections
2. Verify GPIO pin numbers
3. Test with multimeter
4. Increase sensitivity in settings

### Intermittent Touch Detection

1. Check for loose connections
2. Ensure good contact with material
3. Increase sensitivity
4. Use more conductive materials (fruit vs foil)

### False Triggers

1. Decrease sensitivity
2. Check for electrical interference
3. Ensure proper grounding
4. Add capacitors for filtering (advanced)

### One Key Not Working

1. Test that specific GPIO pin
2. Check wire continuity
3. Verify resistor connection
4. Swap with working key to isolate issue

## Best Practices

### Material Selection

- **Fresh fruit works best** (higher moisture content)
- **Avoid very dry materials**
- **Test materials before class**
- **Have backups ready**

### Setup Tips

1. **Label connections**: Mark which wire goes to which key
2. **Secure wires**: Prevent accidental disconnections
3. **Stable surface**: Place materials on flat surface
4. **Common ground**: Ensure all users touch ground reference

### Safety

- Use only 3.3V GPIO pins
- Keep water away from electronics
- Supervise younger students
- Don't touch bare wires with wet hands

### Maintenance

- Check connections before each use
- Replace worn wires
- Clean contacts if using metal materials
- Update materials (fruit gets old!)

## Advanced Topics

### Custom Key Mappings

Edit `plugin.py` to change notes:

```python
notes = {
    'key_1': 'C4',
    'key_2': 'D4',
    'key_3': 'E4',
    'key_4': 'F4',
    'key_5': 'G4',
    'key_6': 'A4',
}
```

### Adding More Keys

Requires hardware modification and code changes. See plugin development guide.

### MIDI Output

Can be configured to output MIDI signals for external synthesizers.

## Technical Details

- **Audio**: pygame.midi for synthesis
- **GPIO**: gpiozero for input detection
- **Sampling**: 60Hz touch detection
- **Debounce**: 50ms to prevent multiple triggers
- **Auto-cleanup**: Stuck notes timeout after 5 seconds

## Related Documentation

- [GPIO Wiring](../../developer/hardware/wiring.md) - Detailed hardware setup
- [Dashboard](../dashboard.md) - Access the piano
- [Settings](../settings.md) - Configure piano options
- [Plugin Development](../../developer/plugins/tutorial.md) - Customize the piano
