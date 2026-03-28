# Plugin Best Practices

Guidelines for creating high-quality, maintainable Tinko plugins.

## Code Organization

### Directory Structure

```
plugins/author/pluginname/
├── __init__.py          # Required
├── plugin.py            # Required
├── models.py            # Optional
├── views.py             # Optional
├── urls.py              # Optional
├── forms.py             # Optional
├── consumers.py         # Optional (WebSocket)
├── services.py          # Optional (business logic)
├── utils.py             # Optional (helpers)
├── static/              # Optional
│   ├── css/
│   └── js/
├── templates/           # Optional
│   └── pluginname/
└── tests.py             # Recommended
```

### Separation of Concerns

Keep your code organized:

- **plugin.py**: Registration, lifecycle
- **models.py**: Data models
- **views.py**: HTTP request handling
- **services.py**: Business logic
- **utils.py**: Helper functions
- **tests.py**: Unit tests

## GPIO Safety

### Always Cleanup

```python
def uninstall(self):
    """Always cleanup GPIO pins."""
    self.cleanup_gpio_pins()
    # Additional cleanup...
```

### Validate Pins

```python
def boot(self):
    # Pin numbers are validated by register_gpio_pins
    self.register_gpio_pins({
        'led': 17,      # Valid: 0-27
        'sensor': 4,
    })
```

### Use Context Managers

```python
from gpiozero import LED

def blink_led(self):
    pin = self.get_gpio_pin('led')
    with LED(pin) as led:
        led.blink()
```

### Mock for Development

```python
try:
    from gpiozero import LED
except ImportError:
    from unittest.mock import MagicMock
    LED = MagicMock
```

## Error Handling

### Graceful Degradation

```python
def read_sensor(self):
    try:
        value = self._hardware.read()
        return value
    except HardwareError as e:
        logger.error(f"Sensor error: {e}")
        return None  # Graceful fallback
```

### Don't Crash the System

```python
def boot(self):
    try:
        self.initialize_hardware()
    except Exception as e:
        logger.error(f"Hardware init failed: {e}")
        # Plugin loads but without hardware
```

### Log with Context

```python
import logging

logger = logging.getLogger(__name__)

def process_data(self, data):
    logger.info(f"Processing {len(data)} records from {self.name}")
    # ...
```

## Database Models

### Proper App Labels

```python
class MyModel(models.Model):
    class Meta:
        app_label = 'author_pluginname'  # Required!
```

### Model Organization

```python
# models.py

class Reading(models.Model):
    """Single sensor reading."""
    value = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        app_label = 'acme_weather'
        ordering = ['-timestamp']

class Config(models.Model):
    """Plugin configuration."""
    key = models.CharField(max_length=50)
    value = models.TextField()
    
    class Meta:
        app_label = 'acme_weather'
```

## URL Patterns

### URL Namespacing

```python
# urls.py
app_name = 'weather_station'

urlpatterns = [
    path('', views.Dashboard.as_view(), name='dashboard'),
    path('api/', views.API.as_view(), name='api'),
]
```

### Reverse URLs

```python
from django.urls import reverse

url = reverse('plugins:acme.weather_station:dashboard')
```

## Templates

### Template Naming

```python
# Good: Namespaced templates
return render(request, 'weather/dashboard.html')

# Bad: Generic names
return render(request, 'dashboard.html')
```

### Template Structure

```html
<!-- templates/weather/dashboard.html -->
{% extends 'base.html' %}
{% load static %}

{% block title %}Weather - {{ block.super }}{% endblock %}

{% block content %}
<div class="container">
    <h1>Weather Station</h1>
    <!-- content -->
</div>
{% endblock %}
```

## Static Files

### Organization

```
static/
├── css/
│   └── weather/
│       └── style.css
└── js/
    └── weather/
        └── dashboard.js
```

### Referencing

```html
{% load static %}
<link rel="stylesheet" href="{% static 'weather/css/style.css' %}">
<script src="{% static 'weather/js/dashboard.js' %}"></script>
```

## Testing

### Test Structure

```python
# tests.py
from django.test import TestCase
from core.plugin_system.base import plugin_manager

class WeatherPluginTests(TestCase):
    def setUp(self):
        self.plugin = plugin_manager.get_plugin('acme.weather')
    
    def test_plugin_loaded(self):
        self.assertIsNotNone(self.plugin)
        self.assertEqual(self.plugin.name, "Weather Station")
    
    def test_gpio_pins_registered(self):
        pin = self.plugin.get_gpio_pin('sensor')
        self.assertEqual(pin, 4)
```

### Mock GPIO

```python
from unittest.mock import patch, MagicMock

@patch('plugins.acme.weather.plugin.LED')
def test_led_blink(self, mock_led):
    self.plugin.blink_status()
    mock_led.return_value.blink.assert_called_once()
```

## Type Hints

### Use Type Hints

```python
from typing import Optional, Dict, Any

def process_data(self, data: Dict[str, Any]) -> Optional[float]:
    """Process sensor data.
    
    Args:
        data: Raw sensor readings
        
    Returns:
        Processed value or None if invalid
    """
    if not data:
        return None
    return float(data.get('value', 0))
```

## Documentation

### Docstrings

```python
def read_sensor(self) -> float:
    """Read temperature from sensor.
    
    Reads the DHT22 sensor connected to GPIO pin 4.
    
    Returns:
        Temperature in Celsius
        
    Raises:
        SensorError: If sensor is not responding
    """
    # Implementation...
```

### README

Create a `README.md` in your plugin:

```markdown
# Weather Station Plugin

Monitor temperature and humidity.

## Features

- Temperature reading
- Humidity reading
- Web dashboard
- Historical data

## Hardware

- DHT22 sensor
- GPIO 4 (data)
- GPIO 17 (status LED)

## Installation

1. Copy to `plugins/acme/weather/`
2. Run migrations
3. Enable in admin

## Configuration

- Update interval: 60 seconds
- Temperature unit: Celsius
```

## Performance

### Database Queries

```python
# Bad: N+1 queries
for reading in Reading.objects.all():
    print(reading.plugin.name)  # Extra query each time

# Good: Use select_related
for reading in Reading.objects.select_related('plugin'):
    print(reading.plugin.name)
```

### Background Tasks

```python
# Don't block the main thread
def boot(self):
    self.register_schedule(
        interval=60,
        callback=self.update,
        name='background_update'
    )

def update(self):
    # Runs in background thread
    # Can be long-running
    pass
```

## Security

### Input Validation

```python
def handle_request(self, request):
    pin = request.POST.get('pin')
    
    # Validate pin number
    try:
        pin = int(pin)
        if not 0 <= pin <= 27:
            raise ValueError
    except ValueError:
        return HttpResponseBadRequest("Invalid pin")
```

### Don't Trust User Input

```python
def configure(self, settings):
    # Validate settings before applying
    if settings.get('interval', 0) < 10:
        raise ValueError("Interval too short")
```

## Version Management

### Semantic Versioning

- `1.0.0` - Initial release
- `1.1.0` - New feature (backward compatible)
- `1.1.1` - Bug fix
- `2.0.0` - Breaking change

### Changelog

```markdown
# Changelog

## 1.1.0 (2024-01-15)

### Added
- Support for DHT11 sensor
- Historical graph view

### Fixed
- GPIO cleanup on shutdown
```

## Debugging

### Logging Levels

```python
logger.debug("Detailed info for debugging")
logger.info("General information")
logger.warning("Warning, but not error")
logger.error("Error occurred")
logger.critical("Critical failure")
```

### Debug Mode

```python
def some_method(self):
    if self.get_config('debug', False):
        # Extra logging
        logger.debug(f"Debug: {detailed_info}")
```

## Summary

- ✅ Always cleanup GPIO
- ✅ Handle errors gracefully
- ✅ Use type hints
- ✅ Write tests
- ✅ Document your code
- ✅ Follow naming conventions
- ✅ Validate user input
- ✅ Log important events
