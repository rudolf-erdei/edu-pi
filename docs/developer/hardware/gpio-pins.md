# GPIO Pin Assignments

Complete reference for GPIO pin usage across all Tinko plugins.

## Pin Numbering

Tinko uses **BCM (Broadcom SOC channel)** pin numbering by default (gpiozero default).

### Physical Pinout Diagram

```
                    Raspberry Pi GPIO Header
                         (40-pin)

    3.3V  (1)  ●  ●  (2)  5V
    GPIO2 (3)  ●  ●  (4)  5V
    GPIO3 (5)  ●  ●  (6)  GND
    GPIO4 (7)  ●  ●  (8)  GPIO14
    GND   (9)  ●  ●  (10) GPIO15
    GPIO17(11) ●  ●  (12) GPIO18
    GPIO27(13) ●  ●  (14) GND
    GPIO22(15) ●  ●  (16) GPIO23
    3.3V  (17) ●  ●  (18) GPIO24
    GPIO10(19) ●  ●  (20) GND
    GPIO9 (21) ●  ●  (22) GPIO25
    GPIO11(23) ●  ●  (24) GPIO8
    GND   (25) ●  ●  (26) GPIO7
    GPIO0 (27) ●  ●  (28) GPIO1
    GPIO5 (29) ●  ●  (30) GND
    GPIO6 (31) ●  ●  (32) GPIO12
    GPIO13(33) ●  ●  (34) GND
    GPIO19(35) ●  ●  (36) GPIO16
    GPIO26(37) ●  ●  (38) GPIO20
    GND   (39) ●  ●  (40) GPIO21
```

## Plugin Pin Assignments

### Activity Timer

| Function | BCM Pin | Physical | Description |
|----------|---------|----------|-------------|
| LED Red | 17 | 11 | RGB LED - Red channel |
| LED Green | 27 | 13 | RGB LED - Green channel |
| LED Blue | 22 | 15 | RGB LED - Blue channel |
| Buzzer | 3 | 5 | Optional buzzer output (moved from GPIO 24) |

### Noise Monitor

**Instant Noise LED (10-second average):**

| Function | BCM Pin | Physical | Description |
|----------|---------|----------|-------------|
| Instant Red | 5 | 29 | Instant noise - Red |
| Instant Green | 6 | 31 | Instant noise - Green |
| Instant Blue | 13 | 33 | Instant noise - Blue |

**Session Average LED (5-10 minute average):**

| Function | BCM Pin | Physical | Description |
|----------|---------|----------|-------------|
| Session Red | 19 | 35 | Session noise - Red |
| Session Green | 26 | 37 | Session noise - Green |
| Session Blue | 16 | 36 | Session noise - Blue |

**Note**: USB Microphone is used for audio input (not GPIO).

### Touch Piano

| Key | Note | BCM Pin | Physical | Description |
|-----|------|---------|----------|-------------|
| Key 1 | C (Do) | 4 | 7 | Piano key 1 (moved from GPIO 23) |
| Key 2 | D (Re) | 7 | 26 | Piano key 2 (moved from GPIO 24) |
| Key 3 | E (Mi) | 20 | 38 | Piano key 3 (moved from GPIO 10) |
| Key 4 | F (Fa) | 21 | 40 | Piano key 4 (moved from GPIO 9) |
| Key 5 | G (Sol)| 12 | 32 | Piano key 5 (moved from GPIO 25) |
| Key 6 | A (La) | 2 | 3 | Piano key 6 (moved from GPIO 11) |

**Note**: Touch Piano pins were reassigned to avoid SPI conflicts with LCD Display.

### LCD Display

| Function | BCM Pin | Physical | Description |
|----------|---------|----------|-------------|
| CS | 22 | 15 | Chip Select (moved from GPIO 8) |
| DC | 24 | 18 | Data/Command |
| RST | 23 | 16 | Reset signal |
| LED/BL | 18 | 12 | Backlight (PWM control) |
| MOSI | 10 | 19 | SPI Data In (hardware SPI - fixed) |
| MISO | 9 | 21 | SPI Data Out (hardware SPI - fixed) |
| SCK | 11 | 23 | SPI Clock (hardware SPI - fixed) |

**Important**: LCD Display uses hardware SPI pins (9, 10, 11) which cannot be changed. CS was moved to GPIO 22 to avoid conflicts and work with Adafruit libraries.

### Routines

The Routines plugin does not use GPIO pins:

- **Audio Output**: 3.5mm jack or USB
- **USB Presenter**: USB port (not GPIO)

## Pin Conflict Matrix

This table shows which pins are used by each plugin:

| Pin | Activity Timer | Noise Monitor | Touch Piano | LCD Display | Status |
|-----|----------------|---------------|-------------|-------------|--------|
| 2 | | | Key 6 | | **In Use** |
| 3 | Buzzer | | | | **In Use** |
| 4 | | | Key 1 | | **In Use** |
| 5 | | Instant R | | | **In Use** |
| 6 | | Instant G | | | **In Use** |
| 7 | | | Key 2 | | **In Use** |
| 9 | | | | SPI MISO | **In Use** |
| 10 | | | | SPI MOSI | **In Use** |
| 11 | | | | SPI SCLK | **In Use** |
| 12 | | | Key 5 | Backlight | **Conflict!** |
| 13 | | Instant B | | | **In Use** |
| 16 | | Session B | | | **In Use** |
| 17 | LED R | | | | **In Use** |
| 18 | | | | Backlight | **In Use** |
| 19 | | Session R | | | **In Use** |
| 20 | | | Key 3 | | **In Use** |
| 21 | | | Key 4 | | **In Use** |
| 22 | LED B | | | CS | **Conflict!** |
| 23 | | | | RST | **In Use** |
| 24 | | | | DC | **In Use** |
| 25 | | | | | **Available** |
| 26 | | Session G | | | **In Use** |
| 27 | LED G | | | | **In Use** |

### Conflict Notes

**Pin 12 (GPIO 12)**: Used by:
- Touch Piano (key 5)
- LCD Display (backlight)

**Pin 15 (GPIO 22)**: Used by:
- Activity Timer (LED Blue)
- LCD Display (CS)

**Resolution**: These plugins should not be used simultaneously. Enable/disable as needed in the admin panel.

## Critical: LCD Display Pin Changes

The LCD Display plugin requires specific pin assignments to work with Adafruit libraries:

### Working Configuration

```
LCD Pin -> RPi Physical Pin -> RPi GPIO
----------------------------------------
VCC     -> Pin 1 or 17      -> 3.3V
GND     -> Pin 6 or 9      -> Ground
CS      -> Pin 15          -> GPIO 22 (was GPIO 8)
RST     -> Pin 16          -> GPIO 23
DC      -> Pin 18          -> GPIO 24
MOSI    -> Pin 19          -> GPIO 10 (hardware SPI - fixed)
SCK     -> Pin 23          -> GPIO 11 (hardware SPI - fixed)
LED/BL  -> Pin 12          -> GPIO 18 (PWM capable)
MISO    -> Pin 21          -> GPIO 9 (optional)
```

**Must Do:**
1. Move CS from Pin 24 (GPIO 8) to **Pin 15 (GPIO 22)**
2. Enable SPI: `sudo raspi-config` → Interface Options → SPI → Enable
3. Add permissions: `sudo usermod -a -G spi,gpio www-data`
4. Reboot after wiring changes

## Available Pins

These pins are **not used** by any built-in plugin:

| BCM | Physical | Notes |
|-----|----------|-------|
| 8 | 24 | Available |
| 14 | 8 | UART TX - Reserved |
| 15 | 10 | UART RX - Reserved |
| 25 | 22 | Available |

### Reserved Pins

These pins have special functions:

- **GPIO2/3**: I2C bus (SDA/SCL)
- **GPIO9/10/11**: Hardware SPI bus (used by LCD Display)
- **GPIO14/15**: UART serial (TX/RX)
- **GPIO18**: Hardware PWM channel 0 (used by LCD backlight)

## Custom Plugin Pin Selection

When developing custom plugins, choose from **available pins** above.

### Best Practices

1. **Check existing usage**: Consult this table before assigning pins
2. **Use available pins**: Prefer pins not used by built-in plugins
3. **Document your pins**: Include pin assignments in plugin documentation
4. **Avoid reserved pins**: Don't use I2C/UART/SPI pins unless necessary
5. **Test for conflicts**: Enable all plugins you'll use together

### Registering Pins in Plugins

```python
def boot(self):
    self.register_gpio_pins({
        'sensor_input': 4,    # Pin 7
        'status_led': 7,     # Pin 26
        'motor_pwm': 18,     # Pin 12 (hardware PWM)
    })
```

## Power Considerations

### Current Limits

- **Per GPIO pin**: Maximum 16mA
- **All GPIO pins total**: Maximum 50mA from 3.3V rail
- **5V pin**: Can supply up to 1A (if Pi power supply allows)

### LED Current Calculation

For an RGB LED with all colors on:

- Red: 20mA
- Green: 20mA
- Blue: 20mA
- **Total**: 60mA per LED

**With 220Ω resistors**:
- Actual current: ~6mA per color
- Total: ~18mA per LED (safe for GPIO)

## Safety Guidelines

### Voltage Levels

- **GPIO pins**: 3.3V maximum
- **5V pin**: Can power external devices
- **Never apply 5V to GPIO pins** - will damage the Pi

### Protection

- Always use resistors with LEDs
- Add pull-up/pull-down resistors for inputs
- Use level shifters for 5V devices
- Never short GPIO pins to power or ground

## Troubleshooting

### Pin Not Working

1. Check physical connection
2. Verify BCM vs BOARD numbering
3. Test with simple LED script
4. Check for permission errors (add user to gpio group)
5. For LCD: Verify CS is on Pin 15 (GPIO 22), not Pin 24

### Permission Denied

```bash
# Add user to gpio and spi groups
sudo usermod -a -G gpio,spi $USER
sudo usermod -a -G gpio,spi www-data

# Log out and back in for changes to take effect
```

### LCD Display Not Working

1. **Check SPI enabled**: `ls /dev/spi*` should show devices
2. **Verify CS pin**: Must be on Pin 15 (GPIO 22), not Pin 24
3. **Check permissions**: `groups $USER` should include gpio, spi
4. **Test wiring**: All connections secure, 3.3V power
5. **Install dependencies**: `uv sync` to get adafruit libraries

### Incorrect Pin Behavior

- Verify common cathode vs common anode for RGB LEDs
- Check pull-up/pull-down resistor configuration
- Test with multimeter for continuity
- For Touch Piano: Verify pins moved to avoid SPI conflicts

## Next Steps

- [Wiring Diagrams](wiring.md) - Step-by-step wiring instructions
- [Hardware Requirements](requirements.md) - Complete component list
- [Plugin Tutorial](../plugins/tutorial.md) - Create custom plugins
