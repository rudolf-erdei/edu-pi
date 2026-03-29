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

- **2.8" TFT LCD** (320x240 resolution)
- **Driver**: ILI9341 (very common and well-supported)
- **Interface**: SPI (4-wire: MOSI, SCLK, CS, DC)
- **Touch**: Optional (not used in Tinko)
- **Backlight**: Can be controlled via GPIO 18 (PWM) or always-on via 3.3V

**Wiring for ILI9341 Display:**

| LCD Pin | RPi Physical Pin | RPi GPIO | Function |
|---------|------------------|----------|----------|
| VCC | Pin 1 or 17 | - | 3.3V Power |
| GND | Pin 6 or 9 | - | Ground |
| CS | Pin 24 | GPIO 8 | SPI Chip Select (CE0) |
| RST | Pin 22 | GPIO 25 | Reset signal |
| DC | Pin 16 | GPIO 23 | Data/Command |
| MOSI | Pin 19 | GPIO 10 | SPI Data In (hardware) |
| SCK | Pin 23 | GPIO 11 | SPI Clock (hardware) |
| LED/BL | Pin 12 | GPIO 18 | Backlight (PWM capable) |
| MISO | Pin 21 | GPIO 9 | SPI Data Out (optional, read-only) |

**Important Notes:**

1. **Hardware SPI**: Pins 19 (MOSI), 21 (MISO), and 23 (SCLK) are hardware SPI pins and cannot be changed
2. **SPI CE0**: GPIO 8 (Pin 24) is Chip Select 0 - used by default
3. **Configurable pins**: DC (GPIO 23), RST (GPIO 25), and BL (GPIO 18) can be changed but must not conflict with other plugins
4. **Touch Piano conflict**: Cannot use Touch Piano and LCD Display simultaneously (both use hardware SPI)
5. **Display startup**: Shows a smiling face (simple eyes and mouth) on black background when app starts

**Pin Conflicts:**
- **Touch Piano**: Shares SPI pins - disable Touch Piano when using LCD
- **Activity Timer**: Buzzer moved to GPIO 3 (Pin 5) to avoid conflict with LCD
- **Noise Monitor**: No conflicts with LCD

**Required Libraries:**
- `luma.core>=2.4.0` - Core display framework
- `luma.lcd>=2.11.0` - ILI9341 driver support

**Installation:**
```bash
uv sync --extra pi  # Installs LCD libraries along with Pi-specific dependencies
```

**Where to Buy:**
- [Optimus Digital (RO)](https://www.optimusdigital.ro/ro/optoelectronice-lcd-uri/12652-modul-ecran-2-ips-lcd-240x320.html)
- [eMAG (RO)](https://www.emag.ro/display-tactil-tft-lcd-2-8-inch-320x240-touchscreen-spi-driver-ili9341-arduino-rx961/pd/DSFJ88YBM/)
- Any ILI9341-based 2.8" SPI display will work

## GPIO Components Summary

### By Plugin

#### Activity Timer
- 1x RGB LED (pins 17, 27, 22)
- 1x Buzzer (pin 5 / GPIO 3) - Optional

#### Noise Monitor
- 2x RGB LED (pins 5, 6, 13 and 19, 26, 16)
- 1x USB Microphone

#### Routines
- 1x Speaker/Headphones (3.5mm jack)
- 1x USB Presenter - Optional

#### Touch Piano
- 6x Touch inputs (pins 7, 26, 38, 40, 32, 3 / GPIO 4, 7, 20, 21, 12, 2)
- 1x Speaker/Headphones

#### LCD Display
- 1x 2.8" TFT LCD with ILI9341 driver (320x240, SPI interface)
- Pins: 16, 22, 24 (GPIO 23, 25, 8) + Hardware SPI (GPIO 9, 10, 11) + Backlight (GPIO 18)
- Shows smiling face on startup with simple eyes and mouth

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
