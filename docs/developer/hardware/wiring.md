# Step-by-Step Wiring Guide

Complete wiring instructions for connecting all Tinko hardware components.

## Before You Start

### Safety First

1. **Power off Raspberry Pi** before wiring
2. **Double-check connections** before powering on
3. **Use proper resistor values** to protect components
4. **Keep away from water** and conductive surfaces

### Tools Needed

- Breadboard (half-size or full-size)
- Jumper wires (various colors)
- Wire strippers (if using custom wires)
- Multimeter (optional, for testing)
- Small screwdriver (for some connectors)

## Activity Timer Wiring

### Components

- 1x RGB LED (common cathode)
- 3x 220Ω resistors
- Optional: 1x buzzer module
- Jumper wires

### Wiring Steps

**Step 1: RGB LED Setup**

Place the RGB LED on the breadboard. Common cathode LEDs have one longer leg (cathode/negative) and three shorter legs (RGB anodes).

```
RGB LED (Common Cathode):
      __
   __|  |__
  | |    | |
  | |____| |
  |__    __|
     |__|
    
   Pins (from left to right):
   [1] Red anode (longer leg)
   [2] Common cathode (longest leg, negative)
   [3] Green anode
   [4] Blue anode
```

**Step 2: Connect Cathode to Ground**

1. Identify the longest leg (cathode/negative)
2. Connect it to Raspberry Pi ground:
   - Breadboard rail → Jumper wire → Physical Pin 6 (GND)

**Step 3: Connect Color Channels**

Connect each color through a 220Ω resistor to GPIO pins:

| Color | LED Pin | Resistor | GPIO Pin | Physical Pin |
|-------|---------|----------|----------|--------------|
| Red | Pin 1 | 220Ω | GPIO 17 | Pin 11 |
| Green | Pin 3 | 220Ω | GPIO 27 | Pin 13 |
| Blue | Pin 4 | 220Ω | GPIO 22 | Pin 15 |

**Step 4: Optional Buzzer**

If using a buzzer:
- Buzzer VCC → GPIO 24 (Pin 18)
- Buzzer GND → Ground rail

### Testing

1. Power on Raspberry Pi
2. Run Tinko
3. Start Activity Timer
4. LED should light up based on timer state

## Noise Monitor Wiring

### Components

- 2x RGB LEDs (common cathode)
- 6x 220Ω resistors
- USB microphone
- Jumper wires

### Wiring Steps

**LED 1 (Instant Noise - 10-second average):**

Same as Activity Timer RGB LED wiring, but using different pins:

| Color | LED Pin | Resistor | GPIO Pin | Physical Pin |
|-------|---------|----------|----------|--------------|
| Red | Pin 1 | 220Ω | GPIO 5 | Pin 29 |
| Green | Pin 3 | 220Ω | GPIO 6 | Pin 31 |
| Blue | Pin 4 | 220Ω | GPIO 13 | Pin 33 |

**LED 2 (Session Average - 5-10 minute average):**

| Color | LED Pin | Resistor | GPIO Pin | Physical Pin |
|-------|---------|----------|----------|--------------|
| Red | Pin 1 | 220Ω | GPIO 19 | Pin 35 |
| Green | Pin 3 | 220Ω | GPIO 26 | Pin 37 |
| Blue | Pin 4 | 220Ω | GPIO 16 | Pin 36 |

**USB Microphone:**

Simply plug the USB microphone into any available USB port on the Raspberry Pi.

### Testing

1. Connect microphone to USB port
2. Power on Raspberry Pi
3. Run Tinko and start Noise Monitor
4. Make noise - LEDs should change color

## Touch Piano Wiring

### Components

- 6x touch inputs (can use TTP223 modules or bare wire)
- 6x 10kΩ pull-up resistors (if using bare wire)
- Conductive materials (bananas, foil, etc.)
- Jumper wires

### Option 1: Using TTP223 Touch Sensors (Recommended)

**TTP223 Module Pinout:**

```
    ┌──────────┐
    │  VCC  ●  │  → Connect to 3.3V (Pin 1)
    │  GND  ●  │  → Connect to GND (Pin 6)
    │  I/O  ●  │  → Connect to GPIO pin
    └──────────┘
```

**Wiring 6 TTP223 Modules:**

| Key | GPIO Pin | Physical Pin | TTP223 I/O |
|-----|----------|--------------|------------|
| Key 1 (C) | GPIO 23 | Pin 16 | Module 1 |
| Key 2 (D) | GPIO 24 | Pin 18 | Module 2 |
| Key 3 (E) | GPIO 10 | Pin 19 | Module 3 |
| Key 4 (F) | GPIO 9 | Pin 21 | Module 4 |
| Key 5 (G) | GPIO 25 | Pin 22 | Module 5 |
| Key 6 (A) | GPIO 11 | Pin 23 | Module 6 |

**Common Connections:**
- All TTP223 VCC → 3.3V (Pin 1)
- All TTP223 GND → Ground rail → Pin 6

**Attach Conductive Materials:**
- Connect wire from each TTP223 I/O pad to conductive material
- Banana, foil, copper tape, etc.

### Option 2: Using Bare Wire with Pull-up Resistors

**Circuit for Each Key:**

```
3.3V (Pin 1) ──┬──[10kΩ]──┬── GPIO Pin
               │          │
               │          └── Touch wire to conductive material
               │
               └───[220Ω]──┬── Common Ground (if needed)
```

**Wiring 6 Keys:**

| Key | GPIO | Physical | Pull-up Resistor | Touch Wire |
|-----|------|----------|------------------|------------|
| Key 1 | 23 | 16 | 10kΩ to 3.3V | To banana |
| Key 2 | 24 | 18 | 10kΩ to 3.3V | To banana |
| Key 3 | 10 | 19 | 10kΩ to 3.3V | To banana |
| Key 4 | 9 | 21 | 10kΩ to 3.3V | To banana |
| Key 5 | 25 | 22 | 10kΩ to 3.3V | To banana |
| Key 6 | 11 | 23 | 10kΩ to 3.3V | To banana |

**Common Ground:**
- All pull-up resistor other ends → Common ground
- Common ground → Physical Pin 6

### Testing

1. Connect speaker to 3.5mm jack
2. Run Tinko and open Touch Piano
3. Touch conductive materials
4. Each should play a different note

## Complete System Wiring

### Breadboard Layout Suggestion

**Left Side - Power Rails:**
- Blue rail: Ground (GND)
- Red rail: 3.3V

**Component Placement:**

```
Breadboard Layout (top view):

[Power Rails]
Red (3.3V) ────────────────────────────────────
Blue (GND) ─────────────────────────────────────

[Section 1: Activity Timer LED]
         R1    R2    R3
         ├─────┼─────┤
    LED1 [R]   [G]   [B]
         │     │     │
         17    27    22

[Section 2: Noise Monitor LED 1]
         R4    R5    R6
         ├─────┼─────┤
    LED2 [R]   [G]   [B]
         │     │     │
         5     6     13

[Section 3: Noise Monitor LED 2]
         R7    R8    R9
         ├─────┼─────┤
    LED3 [R]   [G]   [B]
         │     │     │
         19    26    16

[Section 4: Touch Piano Inputs]
    TTP1  TTP2  TTP3  TTP4  TTP5  TTP6
    (23)  (24)  (10)  (9)   (25)  (11)
```

### Wire Color Coding

Use consistent colors for easier troubleshooting:

- **Red**: Power (3.3V or 5V)
- **Black**: Ground
- **Yellow**: GPIO signals
- **White**: Touch inputs
- **Blue, Green, Orange**: LED connections

## Wiring Checklist

### Activity Timer

- [ ] RGB LED cathode connected to GND
- [ ] Red channel → 220Ω → GPIO 17
- [ ] Green channel → 220Ω → GPIO 27
- [ ] Blue channel → 220Ω → GPIO 22
- [ ] Optional: Buzzer → GPIO 24

### Noise Monitor

- [ ] LED 1 cathode connected to GND
- [ ] LED 1 Red → 220Ω → GPIO 5
- [ ] LED 1 Green → 220Ω → GPIO 6
- [ ] LED 1 Blue → 220Ω → GPIO 13
- [ ] LED 2 cathode connected to GND
- [ ] LED 2 Red → 220Ω → GPIO 19
- [ ] LED 2 Green → 220Ω → GPIO 26
- [ ] LED 2 Blue → 220Ω → GPIO 16
- [ ] USB microphone plugged in

### Touch Piano

- [ ] 6 touch sensors or pull-up circuits wired
- [ ] All VCC connections to 3.3V
- [ ] All GND connections to ground
- [ ] Each I/O connected to correct GPIO
- [ ] Conductive materials attached
- [ ] Speaker connected to 3.5mm jack

## Troubleshooting

### LED Not Lighting

1. Check cathode/anode orientation
2. Verify resistor connections
3. Test with known-good LED
4. Check GPIO pin number (BCM vs Physical)

### Touch Not Registering

1. Check TTP223 module power
2. Verify conductive material connection
3. Test with multimeter for continuity
4. Check GPIO pin numbers

### No Sound

1. Verify speaker connection
2. Check system volume
3. Test with: `speaker-test -t wav`
4. Check audio device settings

### Intermittent Connections

1. Check breadboard contacts
2. Verify wire seating
3. Look for loose jumper wires
4. Replace worn components

## Next Steps

- [GPIO Pin Assignments](gpio-pins.md) - Pin reference
- [Hardware Requirements](requirements.md) - Component list
- [Developer Setup](../setup.md) - Set up development environment
