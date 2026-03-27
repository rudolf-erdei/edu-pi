"""
Tinko Plugin Development Documentation
=========================================

This document describes how to develop plugins for the Tinko platform.
The plugin system is inspired by OctoberCMS, adapted for Django and Raspberry Pi GPIO integration.

Quick Start
-----------
1. Create a plugin directory structure
2. Create a plugin.py file with a Plugin class
3. Register your plugin components
4. Test your plugin

Plugin Structure
----------------
A plugin follows this directory structure:

    plugins/
    └── authorname/
        └── pluginname/
            ├── __init__.py
            ├── plugin.py          # Main plugin file (REQUIRED)
            ├── models.py          # Django models (optional)
            ├── views.py           # Django views (optional)
            ├── urls.py            # URL routes (optional)
            ├── forms.py           # Forms (optional)
            ├── static/            # Static files (CSS/JS)
            ├── templates/         # HTML templates
            ├── migrations/          # Django migrations
            └── README.md          # Plugin documentation

The plugin.py File
------------------
Every plugin must have a `plugin.py` file with a `Plugin` class that inherits from `PluginBase`:

```python
# plugins/acme/weather/plugin.py
from core.plugin_system.base import PluginBase

class Plugin(PluginBase):
    name = "Weather Monitor"
    description = "Monitor temperature and humidity"
    author = "Acme Corp"
    version = "1.0.0"
    icon = "thermometer-half"
    
    def boot(self):
        # Initialize GPIO pins
        self.register_gpio_pins({
            'dht_sensor': 4,
            'status_led': 17
        })
        
        # Schedule readings every 5 minutes
        self.register_schedule(interval=300, callback=self.read_sensors)
    
    def register(self):
        # Import models and views here to avoid circular imports
        from .models import WeatherReading
        from .views import WeatherDashboardView
        
        # Register models
        self.register_model(WeatherReading)
        
        # Register URL
        self.register_url_pattern('weather/', WeatherDashboardView.as_view(), name='weather_dashboard')
        
        # Register admin menu
        self.register_admin_menu('Weather', '/admin/weather/', icon='cloud')
    
    def uninstall(self):
        # Cleanup GPIO pins
        self.cleanup_gpio_pins()
    
    def read_sensors(self):
        # Read sensor data
        pass
```

Plugin Metadata
---------------
Required attributes:
- `name`: Display name of the plugin
- `description`: Short description
- `author`: Plugin author/organization
- `version`: Semantic versioning (e.g., "1.0.0")

Optional attributes:
- `icon`: FontAwesome icon name (default: "puzzle-piece")
- `requires`: List of plugin dependencies (e.g., ["other.author.plugin"])

Lifecycle Methods
---------------

### boot()
Called when the plugin is loaded and enabled.
Use this for:
- Registering GPIO pins
- Setting up hardware
- Scheduling background tasks
- Initializing external connections

### register()
Called after boot() to register Django components.
Use this for:
- Registering models
- Setting up URL routes
- Configuring admin interfaces
- Adding settings forms

### uninstall()
Called when the plugin is disabled or removed.
Use this for:
- Cleaning up GPIO pins
- Removing event listeners
- Saving pending data
- Releasing resources

GPIO Pin Management
--------------------
Plugins request GPIO pins through the API:

```python
def boot(self):
    # Register pins - the system checks for conflicts
    self.register_gpio_pins({
        'red_led': 17,
        'green_led': 27,
        'blue_led': 22
    })
    
    # Access pins later
    red_pin = self.get_gpio_pin('red_led')  # Returns 17
```

The system automatically:
- Checks for pin conflicts between plugins
- Allocates pins exclusively to requesting plugins
- Tracks pin usage for cleanup

Settings and Configuration
--------------------------
Plugins can register settings that appear in the admin:

```python
def boot(self):
    # Register plugin settings
    self.register_setting('update_interval', 'Update Interval (seconds)', 
                         default=300, field_type='number', min=60, max=3600)
    self.register_setting('enabled_sensors', 'Enabled Sensors',
                         default=['temperature'], field_type='multiselect',
                         options=['temperature', 'humidity', 'pressure'])

def some_method(self):
    # Read setting value
    interval = self.get_config('update_interval')  # Returns 300
```

Event System
------------
Plugins can emit and listen to events:

```python
def boot(self):
    # Listen to events
    self.register_event('noise.level_changed', self.on_noise_changed)
    self.register_event('gpio.pin_triggered', self.on_gpio_trigger)

def on_noise_changed(self, level, timestamp):
    print(f"Noise level: {level}")

def some_method(self):
    # Emit events
    self.emit_event('custom.event', data={'key': 'value'})
```

Available Events:
- `plugin.enabled`: Plugin was enabled
- `plugin.disabled`: Plugin was disabled
- `gpio.pin_triggered`: GPIO pin state changed
- `noise.level_changed`: Noise level updated

Scheduling Tasks
----------------
Plugins can register periodic tasks:

```python
def boot(self):
    # Run callback every 60 seconds
    self.register_schedule(interval=60, callback=self.check_sensors)
    
    # Run callback every 5 minutes
    self.register_schedule(interval=300, callback=self.read_data, name='data_reader')

def check_sensors(self):
    # This runs every 60 seconds
    pass
```

URL Registration
----------------
Register custom URL patterns:

```python
def register(self):
    from django.urls import path
    from . import views
    
    # Register URL patterns
    self.register_url_pattern('sensors/', views.SensorListView.as_view(), name='sensor_list')
    self.register_url_pattern('sensors/<int:pk>/', views.SensorDetailView.as_view(), name='sensor_detail')
```

The URLs will be prefixed with the plugin namespace:
`/plugins/acme/weather/sensors/`

Admin Interface
---------------
Add items to the admin menu:

```python
def register(self):
    # Add to admin sidebar
    self.register_admin_menu('Weather Data', '/admin/weather/', icon='cloud-sun')
    self.register_admin_menu('Settings', '/admin/weather/settings/', icon='cog')
```

Django Models
-------------
Plugins can define their own models:

```python
# plugins/acme/weather/models.py
from django.db import models

class WeatherReading(models.Model):
    temperature = models.FloatField()
    humidity = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        # Important: use app_label matching plugin namespace
        app_label = 'acme_weather'

# In plugin.py
def register(self):
    from .models import WeatherReading
    self.register_model(WeatherReading)
```

Static Files
------------
Place static files in the plugin's static directory:

    plugins/acme/weather/static/weather/style.css
    plugins/acme/weather/static/weather/script.js

Access in templates:
```html
{% load static %}
<link rel="stylesheet" href="{% static 'weather/style.css' %}">
```

Templates
---------
Place templates in the plugin's templates directory:

    plugins/acme/weather/templates/weather/dashboard.html

Use in views:
```python
from django.shortcuts import render

def dashboard(request):
    return render(request, 'weather/dashboard.html', context)
```

Best Practices
--------------

1. **Always cleanup GPIO pins** in `uninstall()`

2. **Validate pin numbers** before using them

3. **Use mock mode** for development on non-Pi systems:
   ```python
   try:
       from gpiozero import LED
   except ImportError:
       from core.mock_gpio import LED  # Mock for development
   ```

4. **Handle exceptions** gracefully - don't crash the whole system

5. **Use type hints** for better code clarity

6. **Write tests** for your plugin logic

7. **Document your plugin** with a good README

8. **Version your plugin** using semantic versioning

9. **Check dependencies** before accessing other plugins

10. **Minimize GPIO usage** - share pins when possible

Complete Example
---------------

```python
# plugins/acme/ledcontroller/plugin.py
from core.plugin_system.base import PluginBase

class Plugin(PluginBase):
    name = "LED Controller"
    description = "Control RGB LEDs with web interface"
    author = "Acme Corp"
    version = "1.0.0"
    
    def boot(self):
        # Register GPIO pins
        self.register_gpio_pins({
            'red': 17,
            'green': 27,
            'blue': 22
        })
        
        # Initialize LED hardware
        self._init_leds()
    
    def register(self):
        from .models import LEDConfig
        from .views import LEDControlView
        
        self.register_model(LEDConfig)
        self.register_url_pattern('', LEDControlView.as_view(), name='led_control')
        self.register_admin_menu('LED Controller', '/plugins/acme/led/', icon='lightbulb')
        
        # Register settings
        self.register_setting('default_brightness', 'Default Brightness (%)',
                            default=50, field_type='number', min=0, max=100)
    
    def uninstall(self):
        self.cleanup_gpio_pins()
    
    def _init_leds(self):
        try:
            from gpiozero import PWMLED
            self.red_led = PWMLED(self.get_gpio_pin('red'))
            self.green_led = PWMLED(self.get_gpio_pin('green'))
            self.blue_led = PWMLED(self.get_gpio_pin('blue'))
        except ImportError:
            # Mock for development
            self.red_led = None
            self.green_led = None
            self.blue_led = None
```

Testing Plugins
---------------

Create tests in your plugin directory:

```python
# plugins/acme/weather/tests.py
from django.test import TestCase
from core.plugin_system.base import plugin_manager

class WeatherPluginTests(TestCase):
    def setUp(self):
        self.plugin = plugin_manager.get_plugin('acme.weather')
    
    def test_plugin_loaded(self):
        self.assertIsNotNone(self.plugin)
        self.assertEqual(self.plugin.name, "Weather Monitor")
    
    def test_gpio_pins_registered(self):
        pins = self.plugin.get_gpio_pin('dht_sensor')
        self.assertEqual(pins, 4)
```

Run tests:
```bash
uv run pytest plugins/acme/weather/tests.py
```

Plugin Distribution
-------------------
To share your plugin:

1. Create a git repository for your plugin
2. Include requirements.txt if needed
3. Add installation instructions
4. Tag releases with semantic versions
5. Document GPIO pin requirements
6. Include example configurations

Installation:
```bash
# Clone into plugins directory
git clone https://github.com/acme/weather-plugin plugins/acme/weather

# Run migrations
uv run python manage.py migrate

# Restart Django
```

Troubleshooting
---------------

**Plugin not loading:**
- Check that plugin.py exists
- Verify Plugin class inherits from PluginBase
- Check Django logs for import errors

**GPIO conflicts:**
- Check logs for pin allocation errors
- Ensure no other plugin uses same pins
- Verify pins are released in uninstall()

**Settings not saving:**
- Run migrations: `uv run python manage.py migrate`
- Check plugin has permission to write to database

**Template not found:**
- Ensure templates are in plugin/templates/
- Check template names match in views

API Reference
-------------

### PluginBase Class

#### Methods

- `boot()` - Initialize plugin
- `register()` - Register components
- `uninstall()` - Cleanup plugin
- `get_identifier()` - Get plugin import path
- `get_namespace()` - Get plugin namespace

#### Configuration

- `get_config(key, default)` - Get config value
- `set_config(key, value)` - Set config value
- `register_setting(key, label, ...)` - Register setting

#### GPIO

- `register_gpio_pins(pins)` - Request pins
- `get_gpio_pin(name)` - Get pin number
- `cleanup_gpio_pins()` - Release pins

#### URLs

- `register_url_pattern(route, view, name)` - Add URL
- `get_url_patterns()` - Get all URLs

#### Models

- `register_model(model_class)` - Register Django model
- `get_models()` - Get registered models

#### Admin

- `register_admin_menu(label, url, icon)` - Add menu item
- `get_admin_menus()` - Get menu items

#### Events

- `register_event(event_name, callback)` - Listen to event
- `emit_event(event_name, *args, **kwargs)` - Emit event

#### Scheduling

- `register_schedule(interval, callback, name)` - Schedule task
- `get_schedules()` - Get all schedules

Support
-------
For questions about plugin development:
- Check the example plugins in plugins/edupi/
- Review the core plugin system code in core/plugin_system/
- Open an issue on GitHub

---

Happy plugin development!
