# Hardware Requirements

Complete list of hardware needed to build and run Tinko on a Raspberry Pi.

## Required Hardware

### Core Components

| Component | Quantity | Specifications |
|-----------|----------|---------------|
| Raspberry Pi | 1 | Pi 4 (2GB+ RAM) or Pi 3B+ |
| MicroSD Card | 1 | 32GB+ (Class 10 recommended) |
| Power Supply | 1 | 2.5A for Pi 4, 2A for Pi 3 |
| USB Microphone | 1 | Or microphone module with ADC |
| Speaker | 1 | 3.5mm jack or USB audio |
| Breadboard | 1 | Half-size or full-size |
| Jumper Wires | 1 pack | Male-to-male, various colors |

### Component Breakdown

#### Raspberry Pi

**Recommended: Raspberry Pi 4 (2GB or 4GB)**

- 2GB RAM: Minimum for running Tinko
- 4GB RAM: Better performance with multiple plugins
- USB-C power (5V/3A)

**Alternative: Raspberry Pi 3B+**

- Slower but functional
- 1GB RAM
- Micro-USB power (5V/2.5A)

#### MicroSD Card

Requirements:

- **Capacity**: 32GB minimum
- **Speed**: Class 10 or UHS-I
- **Type**: MicroSDHC or MicroSDXC
- **Reliability**: Use quality brands (SanDisk, Samsung, Kingston)

Tinko requires space for:

- Operating system (~5GB)
- Application code (~500MB)
- Database and media files (~5GB)
- Logs and temporary files

#### USB Microphone

Options:

1. **USB Desktop Microphone** (Recommended)
   - Plug and play
   - Good sensitivity
   - Examples: Fifine K669, Blue Snowball

2. **USB Microphone Module**
   - Smaller footprint
   - Lower quality but functional
   - Examples: Generic USB sound card + mic

3. **Microphone Module with ADC**
   - Requires GPIO connection
   - Better for custom installations
   - Requires additional components

#### Speaker / Audio Output

Options:

1. **3.5mm Jack Speaker**
   - Standard audio output
   - Powered speakers or headphones

2. **USB Speaker**
   - No additional power needed
   - Plug and play

3. **HDMI Audio**
   - If using monitor with speakers
   - Configure in system settings

### Electronic Components

| Component | Quantity | Notes |
|-----------|----------|-------|
| RGB LED | 3 | Common cathode, 5mm or 10mm |
| Resistors (220Ω) | 10 | For LED current limiting |
| Resistors (10kΩ) | 6 | For pull-up circuits |
| Resistors (1kΩ) | 2 | For general use |
| Breadboard | 1 | Half-size or full-size |
| Jumper Wires | 40+ | Various colors |

#### RGB LEDs

**Required: 3 RGB LEDs (Common Cathode)**

- **Activity Timer**: 1 RGB LED
- **Noise Monitor**: 2 RGB LEDs (1 instant, 1 session)

Specifications:

- Type: Common cathode (not common anode)
- Size: 5mm or 10mm diameter
- Colors: Red, Green, Blue combined
- Forward voltage: ~2V per color
- Current: 20mA typical

!!! warning "Important"
    Use common cathode LEDs, not common anode. Wiring differs between types.

#### Resistors

**220Ω Resistors (Pack of 10)**

Used for:
- RGB LED current limiting
- Protection circuits

Calculation for LEDs:
- GPIO voltage: 3.3V
- LED voltage drop: 2V
- Desired current: 15mA
- R = (3.3V - 2V) / 0.015A = 87Ω
- Standard value: 220Ω (safer, longer LED life)

**10kΩ Resistors (Pack of 6)**

Used for:
- Touch Piano pull-up circuits
- Input protection
- Signal conditioning

**1kΩ Resistors (Pack of 2)**

Used for:
- General purpose
- Additional circuits

## Optional Hardware

### Enhanced Components

| Component | Purpose | Benefit |
|-----------|---------|---------|
| Capacitive Touch Sensors (TTP223) | Touch Piano | More reliable touch detection |
| Buzzer Module | Activity Timer | Audio alerts |
| LED Strip (WS2812B) | Activity Timer | Better visual feedback |
| Temperature/Humidity Sensor (DHT22) | Future sensor | Environmental monitoring |
| USB Wireless Presenter | Routines plugin | Wireless control |
| Mini LCD Screen (2.8") | Display | Local display on Pi |
| 3D Printed Case | Housing | Professional look |

### Capacitive Touch Sensors

**TTP223 Modules (6 for Touch Piano)**

Advantages over bare wires:
- More reliable touch detection
- Built-in debouncing
- LED indicator
- Adjustable sensitivity

Wiring:
- VCC → 3.3V
- GND → Ground
- I/O → GPIO pin

### Buzzer Module

For Activity Timer completion alerts:

- **Active Buzzer**: Generates tone when powered
- **Passive Buzzer**: Requires PWM signal
- **Piezo Buzzer**: Recommended (5V, active)

Wiring:
- VCC → GPIO pin
- GND → Ground

### LED Strip (WS2812B)

For advanced Activity Timer:

- Individually addressable LEDs
- Rich visual effects
- Longer progress bars

Requires:
- 5V power supply
- Level shifter (3.3V to 5V)
- Additional power capacity

### USB Wireless Presenter

For Routines plugin control:

- Logitech R400/R800
- Kensington Wireless Presenter
- Any standard USB HID presenter

Features:
- Next/Previous buttons
- Play/Pause button
- Stop button
- Plug and play on Linux

### Mini LCD Screen

For local display on the Pi:

- 2.8" IPS LCD (240x320)
- Touch screen optional
- SPI interface
- Example: ILI9341-based screens

## GPIO Components Summary

### By Plugin

#### Activity Timer
- 1x RGB LED (pins 17, 27, 22)
- 1x Buzzer (pin 24) - Optional

#### Noise Monitor
- 2x RGB LED (pins 5, 6, 13 and 19, 26, 16)
- 1x USB Microphone

#### Routines
- 1x Speaker/Headphones (3.5mm jack)
- 1x USB Presenter - Optional

#### Touch Piano
- 6x Touch inputs (pins 23, 24, 10, 9, 25, 11)
- 1x Speaker/Headphones

## Shopping List

### Essential (~$50-80)

- Raspberry Pi 4 (2GB) × 1
- MicroSD Card (32GB) × 1
- Power Supply (USB-C) × 1
- USB Microphone × 1
- Basic Speaker × 1
- RGB LED (Common Cathode) × 3
- Resistor Kit (220Ω, 1kΩ, 10kΩ) × 1
- Breadboard + Jumper Wires × 1

### Recommended Additions (~$30-50)

- TTP223 Touch Sensors × 6
- Active Buzzer × 1
- Mini LCD Screen (2.8") × 1
- USB Wireless Presenter × 1
- Enclosure/Case × 1

### Total Estimated Cost

- **Basic Setup**: $50-80
- **Complete Setup**: $100-150
- **Premium Setup**: $150-200

## Power Requirements

### Raspberry Pi Power

**Pi 4 (2GB)**
- Input: 5V/3A USB-C
- Typical: 5V/1.5A
- Max: 5V/2.5A

**Pi 3B+**
- Input: 5V/2.5A Micro-USB
- Typical: 5V/1.2A
- Max: 5V/2A

### LED Power

Each RGB LED:
- Max: 60mA (all colors full brightness)
- Typical: 20mA (single color)
- PWM dimming reduces average current

Total LED power (3 LEDs at 60mA):
- 3 × 60mA × 3.3V = 0.6W
- Well within Pi GPIO capabilities

### External Power

For additional components:

- **LED Strips**: External 5V power supply
- **Sensors**: Usually powered from Pi
- **Motors**: Always use external power

## Safety Considerations

### Voltage Levels

- **GPIO Pins**: 3.3V only
- **Power Pins**: 5V (for sensors, LEDs)
- **Never exceed 3.3V on GPIO pins**

### Current Limits

- **Per GPIO pin**: 16mA max
- **All GPIO pins total**: 50mA max (3.3V rail)
- **5V pin**: 1A max from Pi

### Best Practices

1. **Power off Pi before wiring**
2. **Double-check connections**
3. **Use resistors with LEDs**
4. **Avoid short circuits**
5. **Keep away from water**
6. **Supervise students**

## Assembly Notes

### Breadboard Layout Tips

1. Leave space between components
2. Use color-coded wires
3. Group by function
4. Label connections
5. Keep high-frequency signals short

### Wire Management

- Use different colors for different signals
- Red: Power (3.3V or 5V)
- Black: Ground
- Yellow/Orange: Data/Signal
- Keep wires organized

## Next Steps

- [GPIO Pin Assignments](gpio-pins.md) - Detailed pin mapping
- [Wiring Diagrams](wiring.md) - Step-by-step wiring instructions
- [Developer Setup](../setup.md) - Set up development environment
