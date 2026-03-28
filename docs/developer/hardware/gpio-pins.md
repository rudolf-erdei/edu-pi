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
| Buzzer | 24 | 18 | Optional buzzer output |

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
| Key 1 | C (Do) | 23 | 16 | Piano key 1 |
| Key 2 | D (Re) | 24 | 18 | Piano key 2 |
| Key 3 | E (Mi) | 10 | 19 | Piano key 3 |
| Key 4 | F (Fa) | 9 | 21 | Piano key 4 |
| Key 5 | G (Sol)| 25 | 22 | Piano key 5 |
| Key 6 | A (La) | 11 | 23 | Piano key 6 |

### Routines

The Routines plugin does not use GPIO pins:

- **Audio Output**: 3.5mm jack or USB
- **USB Presenter**: USB port (not GPIO)

## Pin Conflict Matrix

This table shows which pins are used by each plugin:

| Pin | Activity Timer | Noise Monitor | Touch Piano | Status |
|-----|----------------|---------------|-------------|--------|
| 5 | | Instant R | | **In Use** |
| 6 | | Instant G | | **In Use** |
| 9 | | | Key 4 | **In Use** |
| 10 | | | Key 3 | **In Use** |
| 11 | | | Key 6 | **In Use** |
| 13 | | Instant B | | **In Use** |
| 16 | | Session B | | **In Use** |
| 17 | LED R | | | **In Use** |
| 19 | | Session R | | **In Use** |
| 22 | LED B | | | **In Use** |
| 23 | | | Key 1 | **In Use** |
| 24 | Buzzer | | Key 2 | **Conflict!** |
| 25 | | | Key 5 | **In Use** |
| 26 | | Session G | | **In Use** |
| 27 | LED G | | | **In Use** |

### Conflict Warning

**Pin 24** is used by:
- Activity Timer (buzzer)
- Touch Piano (key 2)

**Do not use both plugins simultaneously** or remap pins in plugin configuration.

## Available Pins

These pins are **not used** by any built-in plugin:

| BCM | Physical | Notes |
|-----|----------|-------|
| 2 | 3 | I2C SDA - Reserved |
| 3 | 5 | I2C SCL - Reserved |
| 4 | 7 | Available |
| 7 | 26 | Available |
| 8 | 24 | Available |
| 12 | 32 | Available |
| 14 | 8 | UART TX - Reserved |
| 15 | 10 | UART RX - Reserved |
| 18 | 12 | PWM0 - Available |
| 20 | 38 | Available |
| 21 | 40 | Available |

### Reserved Pins

These pins have special functions:

- **GPIO2/3**: I2C bus (SDA/SCL)
- **GPIO14/15**: UART serial (TX/RX)
- **GPIO18**: Hardware PWM channel 0

## Custom Plugin Pin Selection

When developing custom plugins, choose from **available pins** above.

### Best Practices

1. **Check existing usage**: Consult this table before assigning pins
2. **Use available pins**: Prefer pins not used by built-in plugins
3. **Document your pins**: Include pin assignments in plugin documentation
4. **Avoid reserved pins**: Don't use I2C/UART pins unless necessary
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

### Permission Denied

```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Log out and back in for changes to take effect
```

### Incorrect Pin Behavior

- Verify common cathode vs common anode for RGB LEDs
- Check pull-up/pull-down resistor configuration
- Test with multimeter for continuity

## Next Steps

- [Wiring Diagrams](wiring.md) - Step-by-step wiring instructions
- [Hardware Requirements](requirements.md) - Complete component list
- [Plugin Tutorial](../plugins/tutorial.md) - Create custom plugins
