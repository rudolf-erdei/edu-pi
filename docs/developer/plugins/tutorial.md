# Plugin Development Tutorial

Step-by-step guide to creating your first Tinko plugin.

## What is a Plugin?

A Tinko plugin is a self-contained module that extends the platform's functionality. Each plugin has:

- A `plugin.py` file with a `Plugin` class
- Its own models, views, templates, and static files
- Lifecycle methods for initialization and cleanup
- Automatic discovery and registration

## Tutorial: Creating a Weather Station Plugin

Let's create a simple weather station plugin that reads temperature and displays it on the web interface.

## Step 1: Create Directory Structure

```bash
mkdir -p plugins/acme/weather_station
```

Directory structure:

```
plugins/acme/weather_station/
├── __init__.py          # Required
├── plugin.py            # Required
├── models.py            # Optional: Database models
├── views.py             # Optional: Web views
├── urls.py              # Optional: URL routes
├── forms.py             # Optional: Forms
├── consumers.py         # Optional: WebSocket consumers
├── static/              # Optional: CSS/JS
├── templates/           # Optional: HTML templates
└── migrations/          # Auto-created
```

## Step 2: Create __init__.py

**File:** `plugins/acme/weather_station/__init__.py`

```python
"""Weather Station Plugin for Tinko."""

try:
    from .plugin import Plugin
except ImportError:
    pass  # Plugin class not available during early Django startup

default_app_config = "plugins.acme.weather_station.apps.WeatherStationConfig"
```

## Step 3: Create Plugin Registration

**File:** `plugins/acme/weather_station/plugin.py`

```python
"""Weather Station Plugin registration."""

import logging
from typing import Optional

from core.plugin_system.base import PluginBase

logger = logging.getLogger(__name__)


class Plugin(PluginBase):
    """Weather Station Plugin for monitoring temperature and humidity."""
    
    # Plugin metadata
    name = "Weather Station"
    description = "Monitor temperature and humidity with web dashboard"
    author = "Acme Corp"
    version = "1.0.0"
    icon = "cloud-sun"
    
    def __init__(self, plugin_path: str, enabled: bool = True):
        """Initialize the plugin."""
        super().__init__(plugin_path, enabled)
        self._sensor = None
        self._last_reading = None
    
    def boot(self) -> None:
        """Initialize the plugin when loaded."""
        # Register GPIO pins for temperature sensor
        self.register_gpio_pins({
            'sensor_data': 4,    # DHT22 data pin
            'status_led': 17,  # LED to show activity
        })
        
        # Schedule readings every 60 seconds
        self.register_schedule(
            interval=60,
            callback=self.read_sensors,
            name='weather_reader'
        )
        
        logger.info(f"{self.name} plugin booted successfully")
    
    def register(self) -> None:
        """Register plugin components."""
        from django.urls import path, include
        
        # Import models and views here to avoid circular imports
        from .models import WeatherReading
        from .views import WeatherDashboardView, WeatherAPIView
        
        # Register models
        self.register_model(WeatherReading)
        
        # Register URL patterns
        self.register_url_pattern(
            '',
            include('plugins.acme.weather_station.urls'),
            name='weather_station'
        )
        
        # Register admin menu
        self.register_admin_menu(
            'Weather Station',
            '/plugins/acme/weather_station/',
            icon='thermometer-half'
        )
        
        # Register settings
        self.register_setting(
            'update_interval',
            'Update Interval (seconds)',
            default=60,
            field_type='number',
            min=30,
            max=3600
        )
        
        self.register_setting(
            'temperature_unit',
            'Temperature Unit',
            default='celsius',
            field_type='select',
            choices=[
                ('celsius', 'Celsius'),
                ('fahrenheit', 'Fahrenheit'),
            ]
        )
        
        logger.info(f"{self.name} plugin registered")
    
    def uninstall(self) -> None:
        """Clean up when plugin is disabled."""
        # Release GPIO pins
        self.cleanup_gpio_pins()
        
        logger.info(f"{self.name} plugin uninstalled")
    
    def read_sensors(self) -> None:
        """Read temperature and humidity from sensor."""
        try:
            # In real implementation, read from DHT22 sensor
            # For this tutorial, we'll simulate readings
            import random
            
            temperature = 20 + random.uniform(-5, 5)  # Simulated: 15-25°C
            humidity = 50 + random.uniform(-20, 20)     # Simulated: 30-70%
            
            # Store reading in database
            from .models import WeatherReading
            WeatherReading.objects.create(
                temperature=temperature,
                humidity=humidity
            )
            
            # Update status LED
            self._update_status_led()
            
            logger.debug(f"Weather reading: {temperature:.1f}°C, {humidity:.1f}%")
            
        except Exception as e:
            logger.error(f"Failed to read sensors: {e}")
    
    def _update_status_led(self) -> None:
        """Blink status LED to show activity."""
        try:
            from gpiozero import LED
            
            led_pin = self.get_gpio_pin('status_led')
            led = LED(led_pin)
            
            led.on()
            import time
            time.sleep(0.1)
            led.off()
            
        except ImportError:
            # gpiozero not available (development mode)
            pass
```

## Step 4: Create Models

**File:** `plugins/acme/weather_station/models.py`

```python
"""Models for Weather Station plugin."""

from django.db import models


class WeatherReading(models.Model):
    """Stores temperature and humidity readings."""
    
    temperature = models.FloatField(
        help_text="Temperature in Celsius"
    )
    humidity = models.FloatField(
        help_text="Humidity percentage (0-100)"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="When the reading was taken"
    )
    
    class Meta:
        # Important: use app_label matching plugin namespace
        app_label = 'acme_weather'
        ordering = ['-timestamp']
    
    def __str__(self) -> str:
        return f"{self.temperature:.1f}°C, {self.humidity:.1f}% at {self.timestamp}"
    
    @property
    def temperature_fahrenheit(self) -> float:
        """Convert Celsius to Fahrenheit."""
        return (self.temperature * 9/5) + 32
```

## Step 5: Create Views

**File:** `plugins/acme/weather_station/views.py`

```python
"""Views for Weather Station plugin."""

from django.views.generic import TemplateView, View
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta

from .models import WeatherReading


class WeatherDashboardView(TemplateView):
    """Main dashboard showing current weather."""
    
    template_name = 'weather/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get latest reading
        latest = WeatherReading.objects.first()
        context['latest'] = latest
        
        # Get readings from last 24 hours
        day_ago = timezone.now() - timedelta(hours=24)
        context['readings'] = WeatherReading.objects.filter(
            timestamp__gte=day_ago
        )[:50]
        
        # Calculate statistics
        if context['readings']:
            temps = [r.temperature for r in context['readings']]
            context['stats'] = {
                'temp_min': min(temps),
                'temp_max': max(temps),
                'temp_avg': sum(temps) / len(temps),
            }
        
        return context


class WeatherAPIView(View):
    """API endpoint for current weather data."""
    
    def get(self, request):
        """Return current weather as JSON."""
        latest = WeatherReading.objects.first()
        
        if latest:
            data = {
                'temperature': round(latest.temperature, 1),
                'humidity': round(latest.humidity, 1),
                'timestamp': latest.timestamp.isoformat(),
                'unit': 'celsius'
            }
        else:
            data = {'error': 'No readings available'}
        
        return JsonResponse(data)
```

## Step 6: Create URLs

**File:** `plugins/acme/weather_station/urls.py`

```python
"""URL configuration for Weather Station plugin."""

from django.urls import path
from . import views

app_name = 'weather_station'

urlpatterns = [
    path('', views.WeatherDashboardView.as_view(), name='dashboard'),
    path('api/current/', views.WeatherAPIView.as_view(), name='api_current'),
]
```

## Step 7: Create Templates

**File:** `plugins/acme/weather_station/templates/weather/dashboard.html`

```html
{% extends 'base.html' %}
{% load static %}

{% block title %}Weather Station - Tinko{% endblock %}

{% block content %}
<div class="container mx-auto px-4 py-8">
    <h1 class="text-3xl font-bold mb-6">Weather Station</h1>
    
    <!-- Current Conditions -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div class="card bg-base-200 shadow-xl">
            <div class="card-body">
                <h2 class="card-title">Temperature</h2>
                {% if latest %}
                <p class="text-4xl font-bold">{{ latest.temperature|floatformat:1 }}°C</p>
                <p class="text-xl">{{ latest.temperature_fahrenheit|floatformat:1 }}°F</p>
                {% else %}
                <p class="text-gray-500">No data available</p>
                {% endif %}
            </div>
        </div>
        
        <div class="card bg-base-200 shadow-xl">
            <div class="card-body">
                <h2 class="card-title">Humidity</h2>
                {% if latest %}
                <p class="text-4xl font-bold">{{ latest.humidity|floatformat:1 }}%</p>
                {% else %}
                <p class="text-gray-500">No data available</p>
                {% endif %}
            </div>
        </div>
    </div>
    
    <!-- Statistics -->
    {% if stats %}
    <div class="card bg-base-200 shadow-xl mb-8">
        <div class="card-body">
            <h2 class="card-title">24-Hour Statistics</h2>
            <div class="stats shadow">
                <div class="stat">
                    <div class="stat-title">Min Temp</div>
                    <div class="stat-value">{{ stats.temp_min|floatformat:1 }}°C</div>
                </div>
                <div class="stat">
                    <div class="stat-title">Max Temp</div>
                    <div class="stat-value">{{ stats.temp_max|floatformat:1 }}°C</div>
                </div>
                <div class="stat">
                    <div class="stat-title">Avg Temp</div>
                    <div class="stat-value">{{ stats.temp_avg|floatformat:1 }}°C</div>
                </div>
            </div>
        </div>
    </div>
    {% endif %}
    
    <!-- Historical Data -->
    <div class="card bg-base-200 shadow-xl">
        <div class="card-body">
            <h2 class="card-title">Recent Readings</h2>
            <div class="overflow-x-auto">
                <table class="table table-zebra">
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Temperature</th>
                            <th>Humidity</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for reading in readings %}
                        <tr>
                            <td>{{ reading.timestamp|date:"H:i" }}</td>
                            <td>{{ reading.temperature|floatformat:1 }}°C</td>
                            <td>{{ reading.humidity|floatformat:1 }}%</td>
                        </tr>
                        {% empty %}
                        <tr>
                            <td colspan="3" class="text-center text-gray-500">
                                No readings available
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

## Step 8: Run Migrations

After creating the plugin, run migrations to create database tables:

```bash
uv run python manage.py makemigrations
uv run python manage.py migrate
```

## Step 9: Test the Plugin

1. Restart the Django development server
2. The plugin should be automatically discovered
3. Visit: `http://localhost:8000/plugins/acme/weather_station/`
4. You should see the weather dashboard

## How It Works

### Auto-Discovery

Tinko automatically discovers plugins from the `plugins/` directory:

1. Scans `plugins/*/*/`
2. Finds directories with `__init__.py` and `plugin.py`
3. Registers the plugin class
4. Adds to Django's `INSTALLED_APPS`

### Lifecycle

1. **boot()**: Called when plugin loads - register GPIO, schedule tasks
2. **register()**: Called after boot - register models, URLs, settings
3. **uninstall()**: Called when disabled - cleanup GPIO, resources

### Namespace

Plugin is identified as: `acme.weather_station`

- URL: `/plugins/acme/weather_station/`
- Admin: Shows in plugin list
- Settings: Stored as `acme.weather_station.*`

## Next Steps

Now you have a working plugin! You can:

- Add more sensors (pressure, light)
- Create charts with JavaScript
- Add WebSocket for real-time updates
- Implement user authentication
- Add data export features

See [Plugin API Reference](api.md) for complete API documentation.

## Common Issues

### "Plugin not found"

- Check `__init__.py` exists
- Verify `Plugin` class inherits from `PluginBase`
- Restart Django server

### "Models not created"

- Run `makemigrations`
- Check `app_label` matches namespace
- Verify model registration in `register()`

### "GPIO not working"

- Check pin numbers (BCM numbering)
- Verify user in `gpio` group
- Use mock mode for development

## Best Practices

- Always cleanup GPIO in `uninstall()`
- Use type hints for better code
- Log errors with context
- Handle exceptions gracefully
- Document your plugin

**Congratulations on creating your first Tinko plugin!** 🎉
