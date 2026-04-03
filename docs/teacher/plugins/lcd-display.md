# LCD Display Plugin

The LCD Display plugin provides a visual "face" for your Tinko robot using a 2.8" TFT LCD screen. The robot displays animated mood-based faces that respond to classroom conditions.

## Overview

The LCD Display turns your Raspberry Pi into an expressive robot with:
- **6 Different Moods**: Happy, Neutral, Sad, Angry, Laughing, and Concentrated
- **Animated Faces**: Each mood alternates between 2 face variations (5s + 2s cycle)
- **Web Control**: Change moods instantly via the web interface
- **Auto-Animation**: Faces animate continuously when not displaying content
- **SPI Interface**: Hardware-accelerated display updates

## Hardware Requirements

### Display Module

- **Size**: 2.8" TFT LCD
- **Resolution**: 320x240 pixels
- **Driver**: ILI9341
- **Interface**: SPI (4-wire)
- **Touch**: Not required (optional)

### Wiring Configuration

| LCD Pin | RPi Physical Pin | RPi GPIO | Function |
|---------|------------------|----------|----------|
| VCC | Pin 1 or 17 | - | 3.3V Power |
| GND | Pin 6 or 9 | - | Ground |
| **CS** | **Pin 24** | **GPIO 8** | Chip Select |
| RST | Pin 22 | GPIO 25 | Reset |
| DC | Pin 16 | GPIO 23 | Data/Command |
| MOSI | Pin 19 | GPIO 10 | SPI Data In |
| SCK | Pin 23 | GPIO 11 | SPI Clock |
| LED/BL | Pin 12 | GPIO 18 | Backlight (PWM) |
| MISO | Pin 21 | GPIO 9 | Data Out (optional) |

### Setup Steps

1. **Connect wires** according to the table above
2. **Enable SPI interface**:
   ```bash
   sudo raspi-config
   # Interface Options → SPI → Enable
   ```
3. **Add permissions**:
   ```bash
   sudo usermod -a -G spi,gpio $USER
   sudo usermod -a -G spi,gpio www-data
   ```
4. **Reboot** the Raspberry Pi

## Dependencies

Install required libraries:

```bash
uv add adafruit-circuitpython-rgb-display adafruit-blinka
```

Or during installation:
```bash
uv sync --extra pi
```

## Moods

### 1. Happy (Default)
**Faces**: :) and :D
- Default mood when system starts
- Cheerful expression with animated smile
- Use: General operation, welcoming students

### 2. Neutral
**Faces**: :| and blink
- Straight face for minor misbehavior
- Expressionless, professional look
- Use: First warning to students

### 3. Sad
**Faces**: :( and sadder
- Droopy eyes and downward mouth
- Indicates disappointment
- Use: Continued misbehavior

### 4. Angry
**Faces**: >:| and furious
- Slanted eyebrows, tight mouth
- Serious expression
- Use: Serious discipline issues

### 5. Laughing
**Faces**: :D and big laugh
- Curved eyes, open laughing mouth
- Joyful expression
- Use: Celebrations, fun activities

### 6. Concentrated
**Faces**: Focused and thinking
- Narrowed eyes, small thoughtful mouth
- Studious expression
- Use: Learning activities, focused work

## Usage

### Web Interface

Access the LCD Display control panel:
```
http://[raspberry-pi-ip]:8000/plugins/edupi/lcd_display/
```

**Controls**:
- **Mood Buttons**: Click any mood to change the robot's expression
- **Brightness Slider**: Adjust backlight (0-100%)
- **Show Smiley**: Resume animation after displaying text
- **Clear Screen**: Turn off display
- **Display Text**: Show custom message (pauses animation)

### API Endpoints

**Set Mood**:
```bash
curl -X POST http://localhost:8000/plugins/edupi/lcd_display/api/set-mood/ \
  -d "mood=sad"
```

**Get Current Mood**:
```bash
curl http://localhost:8000/plugins/edupi/lcd_display/api/get-mood/
```

**Available moods**: happy, neutral, sad, angry, laughing, concentrated

### Programmatic Usage

```python
from plugins.edupi.lcd_display.lcd_service import lcd_service
from plugins.edupi.lcd_display.mood import Mood

# Set mood
lcd_service.set_mood(Mood.SAD)

# Or by name
lcd_service.set_mood_by_name("angry")

# Check if misbehaving
if lcd_service.is_misbehaving():
    print("Classroom is misbehaving!")

# Display text (pauses animation)
lcd_service.show_text("Time to focus!")

# Resume animation
lcd_service.resume_face_animation()
```

## Animation System

### Face Cycle
Each mood displays 2 faces that alternate:
1. **Main Face** (5 seconds) - Primary expression
2. **Variation** (2 seconds) - Secondary expression (blink, bigger smile, etc.)

**Total cycle**: 7 seconds

### Automatic Behaviors
- **Startup**: Shows Happy mood with animation
- **Text Display**: Pauses animation, shows text
- **Countdown**: Pauses animation, shows countdown
- **Resume**: Click "Show Smiley" to restart animation

## Integration with Other Plugins

### Calling Plugins from Other Plugins

All plugins can call the LCD Display plugin to control the robot's mood and display. This is done by importing the LCD service singleton.

#### Basic Usage

```python
from plugins.edupi.lcd_display.lcd_service import lcd_service
from plugins.edupi.lcd_display.mood import Mood

# Always check if LCD is initialized before using
if lcd_service.is_initialized():
    # Set mood by enum
    lcd_service.set_mood(Mood.HAPPY)
    
    # Or by name
    lcd_service.set_mood_by_name("concentrated")
    
    # Display custom text
    lcd_service.show_text("Time's up!")
    
    # Adjust backlight
    lcd_service.set_backlight(50)  # 50% brightness
```

#### Complete Example: Noise-Based Mood Changes

Here's how to change the robot's mood based on classroom noise levels:

```python
from plugins.edupi.lcd_display.lcd_service import lcd_service
from plugins.edupi.lcd_display.mood import Mood

def update_robot_mood(noise_level):
    """Update LCD mood based on noise level.
    
    Args:
        noise_level: Current noise level (0-100)
    """
    if not lcd_service.is_initialized():
        return
    
    if noise_level > 80:
        # Very noisy - robot is angry
        lcd_service.set_mood(Mood.ANGRY)
    elif noise_level > 60:
        # Quite noisy - robot is sad
        lcd_service.set_mood(Mood.SAD)
    elif noise_level > 40:
        # Moderate noise - robot is neutral
        lcd_service.set_mood(Mood.NEUTRAL)
    elif noise_level > 20:
        # Quiet - robot is happy
        lcd_service.set_mood(Mood.HAPPY)
    else:
        # Very quiet - robot is concentrated
        lcd_service.set_mood(Mood.CONCENTRATED)
```

#### Available Methods

**Mood Control:**
- `lcd_service.set_mood(mood: Mood)` - Set mood using Mood enum
- `lcd_service.set_mood_by_name(name: str)` - Set mood by string name
- `lcd_service.get_current_mood()` - Get current mood
- `lcd_service.get_available_moods()` - List all available moods
- `lcd_service.is_misbehaving()` - Check if mood indicates misbehavior

**Display Control:**
- `lcd_service.show_text(text, position, font_size)` - Display text
- `lcd_service.clear_screen()` - Clear display
- `lcd_service.set_backlight(brightness)` - Set backlight (0-100)

**Animation:**
- `lcd_service.start_face_animation()` - Start mood animation
- `lcd_service.stop_face_animation()` - Stop animation
- `lcd_service.pause_face_animation()` - Pause animation
- `lcd_service.resume_face_animation()` - Resume animation

#### Important Considerations

1. **Check Initialization**: Always call `lcd_service.is_initialized()` before using
2. **SPI Conflict**: Touch Piano cannot be used simultaneously with LCD due to SPI conflicts
3. **Dependencies**: All plugins automatically declare LCD Display as a dependency
4. **Thread Safety**: LCD service is thread-safe for concurrent access

### Activity Timer
When countdown is running:
- LCD pauses mood animation
- Shows countdown timer
- Returns to mood animation after completion

### Noise Monitor
Can trigger mood changes based on noise levels - see example above.

### Touch Piano
Cannot use simultaneously with LCD Display (SPI conflict).
Disable Touch Piano plugin when using LCD.

## Troubleshooting

### Display Not Working

1. **Check SPI enabled**:
   ```bash
   ls /dev/spi*
   # Should show /dev/spidev0.0 and /dev/spidev0.1
   ```

2. **Verify CS pin location**:
   - Must be on Pin 15 (GPIO 22), NOT Pin 24

3. **Check permissions**:
   ```bash
   groups $USER
   # Should include: gpio, spi
   ```

4. **Test display**:
   ```bash
   uv run python -c "
   from plugins.edupi.lcd_display.lcd_service import lcd_service
   lcd_service.initialize()
   lcd_service.show_smiley_face()
   "
   ```

### Web Interface Shows "Disconnected"

- SPI interface not enabled
- Wrong CS pin wiring
- Missing permissions
- Hardware connection issue

### Animation Not Working

- Check `logs/lcd_display.log` for errors
- Ensure spidev library installed: `uv sync --extra pi`
- Verify all dependencies installed

### Face Looks Wrong

- Different LCD module may have different orientation
- Try changing rotation in settings (0, 90, 180, 270)
- Check backlight is connected

## Technical Details

### Libraries Used

- **adafruit-circuitpython-rgb-display**: ILI9341 driver
- **adafruit-blinka**: CircuitPython compatibility
- **Pillow**: Image drawing and manipulation
- **gpiozero**: PWM backlight control

### SPI Configuration

- **Port**: 0
- **Device**: 0
- **Baudrate**: 16MHz
- **Mode**: 0

### Display Specifications

- **Resolution**: 240x320 (portrait) or 320x240 (landscape)
- **Color Depth**: 16-bit (65k colors)
- **Refresh Rate**: ~60Hz
- **Interface**: 4-wire SPI

### Performance

- Face update: ~50ms
- Animation smooth: 7-second cycle
- Text display: Instant
- Backlight PWM: 0-100%

## Best Practices

1. **Wire carefully**: CS pin must be on Pin 15
2. **Test first**: Run initialization test before full setup
3. **Check conflicts**: Disable Touch Piano when using LCD
4. **Monitor logs**: Check `logs/lcd_display.log` for issues
5. **Use moods**: Set appropriate moods for classroom management

## Safety Notes

- **3.3V only**: Never apply 5V to display pins
- **Current**: Backlight draws ~100mA at full brightness
- **Heat**: Display may get warm during operation
- **Mounting**: Secure display to prevent student contact with pins

## Next Steps

- [Hardware Requirements](hardware-requirements.md) - Complete component list
- [GPIO Pin Assignments](gpio-pins.md) - Detailed pin mapping
- [Plugin API](../../developer/plugins/api.md) - Create custom integrations

## Support

For issues with the LCD Display:
1. Check troubleshooting section above
2. Review logs in `logs/lcd_display.log`
3. Verify wiring against pin table
4. Test with simple initialization script
