# Plugin API Reference

Complete API reference for the Tinko PluginBase class.

## PluginBase Class

All plugins must inherit from `PluginBase` and implement required methods.

### Class Definition

```python
from core.plugin_system.base import PluginBase

class Plugin(PluginBase):
    name = "Plugin Name"
    description = "Description"
    author = "Author"
    version = "1.0.0"
    icon = "star"
    
    def boot(self): ...
    def register(self): ...
    def uninstall(self): ...
```

### Metadata Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | str | Yes | Display name |
| `description` | str | Yes | Short description |
| `author` | str | Yes | Plugin author |
| `version` | str | Yes | Semantic version (x.y.z) |
| `icon` | str | No | Font Awesome icon name |
| `requires` | list | No | Plugin dependencies (see below) |

### Plugin Dependencies

Use the `requires` attribute to declare dependencies on other plugins. This ensures that dependent plugins are loaded first.

```python
class Plugin(PluginBase):
    name = "My Plugin"
    description = "A plugin that uses LCD display"
    author = "Developer"
    version = "1.0.0"
    icon = "star"
    requires = ["plugins.edupi.lcd_display"]
```

**Calling Other Plugins:**

Once a dependency is declared, you can import and use the other plugin's services:

```python
def some_method(self):
    from plugins.edupi.lcd_display.lcd_service import lcd_service
    from plugins.edupi.lcd_display.mood import Mood
    
    if lcd_service.is_initialized():
        lcd_service.set_mood(Mood.HAPPY)
        lcd_service.show_text("Hello from My Plugin!")
```

**Best Practices:**
- Always check `lcd_service.is_initialized()` before calling LCD methods
- Handle import errors gracefully in case the dependency is not available
- Document which plugins you depend on in your plugin's README

## Lifecycle Methods

### boot()

Called when plugin is loaded and enabled.

```python
def boot(self) -> None:
    """Initialize plugin."""
    # Register GPIO pins
    self.register_gpio_pins({
        'sensor': 4,
        'led': 17
    })
    
    # Schedule background tasks
    self.register_schedule(
        interval=60,
        callback=self.read_sensor
    )
```

**Use for:**
- GPIO pin registration
- Hardware initialization
- Background task scheduling
- Event listener registration

### register()

Called after boot() to register Django components.

```python
def register(self) -> None:
    """Register components."""
    from .models import MyModel
    from .views import MyView
    
    # Register models
    self.register_model(MyModel)
    
    # Register URLs
    self.register_url_pattern('', MyView.as_view())
    
    # Register settings
    self.register_setting('timeout', 'Timeout', default=30)
```

**Use for:**
- Model registration
- URL registration
- Admin menu items
- Settings registration

### uninstall()

Called when plugin is disabled or removed.

```python
def uninstall(self) -> None:
    """Cleanup resources."""
    self.cleanup_gpio_pins()
    # Additional cleanup...
```

**Use for:**
- GPIO cleanup
- Remove event listeners
- Save pending data
- Release resources

## GPIO Methods

### register_gpio_pins()

Request GPIO pins for exclusive use.

```python
def boot(self):
    self.register_gpio_pins({
        'led_red': 17,
        'led_green': 27,
        'sensor': 4
    })
```

**Parameters:**
- `pins`: dict[str, int] - Pin name to BCM number mapping

**Raises:**
- `GPIOPinConflictError`: If pins already allocated

### get_gpio_pin()

Get BCM pin number by name.

```python
def some_method(self):
    led_pin = self.get_gpio_pin('led_red')  # Returns 17
```

**Returns:** int - BCM pin number

### cleanup_gpio_pins()

Release all allocated GPIO pins.

```python
def uninstall(self):
    self.cleanup_gpio_pins()
```

## Configuration Methods

### register_setting()

Add a configurable setting.

```python
def register(self):
    # Text setting
    self.register_setting(
        'api_key',
        'API Key',
        default='',
        field_type='text'
    )
    
    # Number setting
    self.register_setting(
        'interval',
        'Update Interval',
        default=60,
        field_type='number',
        min=10,
        max=3600
    )
    
    # Select setting
    self.register_setting(
        'mode',
        'Mode',
        default='auto',
        field_type='select',
        choices=[
            ('auto', 'Automatic'),
            ('manual', 'Manual')
        ]
    )
```

**Parameters:**
- `key`: Setting identifier
- `label`: Display label
- `default`: Default value
- `field_type`: text, number, select, boolean
- `min/max`: For number type
- `choices`: For select type

### get_config()

Read setting value.

```python
def some_method(self):
    interval = self.get_config('interval', default=60)
```

### set_config()

Set setting value.

```python
def some_method(self):
    self.set_config('interval', 120)
```

## URL Methods

### register_url_pattern()

Add URL routes.

```python
def register(self):
    from django.urls import path
    from . import views
    
    self.register_url_pattern(
        'dashboard/',
        views.DashboardView.as_view(),
        name='dashboard'
    )
```

URLs are prefixed: `/plugins/{author}/{plugin_name}/`

### register_admin_menu()

Add admin sidebar menu item.

```python
def register(self):
    self.register_admin_menu(
        'My Plugin',
        '/plugins/acme/myplugin/',
        icon='star'
    )
```

## Model Methods

### register_model()

Register Django model.

```python
def register(self):
    from .models import Reading
    self.register_model(Reading)
```

**Important:** Set `app_label` in model Meta:

```python
class Reading(models.Model):
    class Meta:
        app_label = 'acme_myplugin'
```

## Scheduling Methods

### register_schedule()

Run function periodically.

```python
def boot(self):
    self.register_schedule(
        interval=300,      # seconds
        callback=self.update,
        name='updater'     # optional
    )

def update(self):
    # Called every 5 minutes
    pass
```

## Event System

### register_event()

Listen to events.

```python
def boot(self):
    self.register_event(
        'noise.level_changed',
        self.on_noise_change
    )

def on_noise_change(self, level, timestamp):
    print(f"Noise: {level}")
```

### emit_event()

Trigger events.

```python
def some_method(self):
    self.emit_event(
        'myplugin.sensor_read',
        value=42,
        timestamp=now()
    )
```

## Utility Methods

### get_identifier()

Get plugin import path.

```python
id = self.get_identifier()  # "plugins.acme.myplugin"
```

### get_namespace()

Get plugin namespace.

```python
ns = self.get_namespace()  # "acme.myplugin"
```

## Best Practices

1. **Always cleanup GPIO** in `uninstall()`
2. **Handle exceptions** gracefully
3. **Use type hints** for better code
4. **Log important events**
5. **Document your plugin**

## Example: Complete Plugin

```python
from core.plugin_system.base import PluginBase

class Plugin(PluginBase):
    name = "Example Plugin"
    description = "Demonstrates all API features"
    author = "Developer"
    version = "1.0.0"
    icon = "star"
    
    def boot(self):
        self.register_gpio_pins({'led': 17})
        self.register_schedule(60, self.update)
    
    def register(self):
        from .models import Data
        from .views import Dashboard
        
        self.register_model(Data)
        self.register_url_pattern('', Dashboard.as_view())
        self.register_setting('interval', 'Interval', default=60)
    
    def uninstall(self):
        self.cleanup_gpio_pins()
    
    def update(self):
        # Periodic update
        pass
```

## See Also

- [Plugin Tutorial](tutorial.md) - Step-by-step guide
- [Best Practices](best-practices.md) - Development guidelines
