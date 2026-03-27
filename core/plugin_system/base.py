"""
Core plugin system inspired by OctoberCMS.

This module provides the base classes and managers for the plugin system,
allowing developers to extend the platform with custom features.
"""

import importlib
import inspect
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type
from django.apps import AppConfig
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)


class PluginBase:
    """
    Base class for all EDU-PI plugins.

    Inspired by OctoberCMS plugin architecture.
    Each plugin must have a Plugin class inheriting from PluginBase.

    Example:
        class Plugin(PluginBase):
            name = "My Plugin"
            description = "A sample plugin"
            author = "Developer Name"
            version = "1.0.0"

            def boot(self):
                # Initialize plugin
                pass

            def register(self):
                # Register models, URLs, etc.
                pass
    """

    # Plugin metadata
    name: str = ""
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    icon: str = "puzzle-piece"  # FontAwesome icon name

    # Plugin dependencies - list of plugin names this plugin depends on
    requires: List[str] = []

    def __init__(self, plugin_path: str, enabled: bool = True):
        """
        Initialize the plugin.

        Args:
            plugin_path: Python import path (e.g., 'plugins.acme.myplugin')
            enabled: Whether the plugin is currently enabled
        """
        self.plugin_path = plugin_path
        self.enabled = enabled
        self._config = {}
        self._gpio_pins: Dict[str, int] = {}
        self._url_patterns = []
        self._models: List[Type[models.Model]] = []
        self._admin_menus = []
        self._events: Dict[str, List[Callable]] = {}
        self._schedules: List[Dict] = []

        logger.info(f"Initialized plugin: {self.name} ({self.plugin_path})")

    def boot(self) -> None:
        """
        Called when the plugin is being initialized.

        Use this to:
        - Register GPIO pins
        - Set up event listeners
        - Initialize hardware
        - Schedule background tasks
        """
        pass

    def register(self) -> None:
        """
        Called after boot() to register plugin components.

        Use this to:
        - Register models with Django
        - Register URL patterns
        - Register admin interfaces
        - Register settings forms
        """
        pass

    def uninstall(self) -> None:
        """
        Called when the plugin is being disabled or uninstalled.

        Use this to:
        - Cleanup GPIO pins
        - Remove event listeners
        - Save any pending data
        - Release resources
        """
        pass

    def get_identifier(self) -> str:
        """Get the unique identifier for this plugin."""
        return self.plugin_path

    def get_namespace(self) -> str:
        """Get the namespace for this plugin (e.g., 'acme.myplugin')."""
        parts = self.plugin_path.split(".")
        if len(parts) >= 3:
            return ".".join(parts[1:])  # Remove 'plugins.' prefix
        return self.plugin_path

    # Configuration methods

    def get_config(self, key: str = None, default: Any = None) -> Any:
        """Get configuration value."""
        if key is None:
            return self._config
        return self._config.get(key, default)

    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self._config[key] = value

    def register_setting(
        self,
        key: str,
        label: str,
        default: Any = None,
        field_type: str = "text",
        **kwargs,
    ) -> None:
        """
        Register a setting for this plugin.

        Args:
            key: Setting key
            label: Display label
            default: Default value
            field_type: Form field type (text, number, boolean, select, etc.)
            **kwargs: Additional field options
        """
        if "settings" not in self._config:
            self._config["settings"] = {}

        self._config["settings"][key] = {
            "label": label,
            "default": default,
            "type": field_type,
            **kwargs,
        }

    # GPIO methods

    def register_gpio_pins(self, pins: Dict[str, int]) -> None:
        """
        Register GPIO pins this plugin uses.

        Args:
            pins: Dictionary mapping pin names to BCM pin numbers
                  e.g., {'led_red': 17, 'led_green': 27}
        """
        self._gpio_pins.update(pins)
        logger.info(f"Plugin {self.name} registered GPIO pins: {pins}")

    def get_gpio_pin(self, name: str) -> Optional[int]:
        """Get a registered GPIO pin number."""
        return self._gpio_pins.get(name)

    def cleanup_gpio_pins(self) -> None:
        """Cleanup all registered GPIO pins."""
        for name, pin in self._gpio_pins.items():
            try:
                logger.info(f"Cleaning up GPIO pin {pin} ({name})")
            except Exception as e:
                logger.error(f"Error cleaning up pin {pin}: {e}")
        self._gpio_pins.clear()

    # URL methods

    def register_url_pattern(
        self, route: str, view_or_include, name: str = None
    ) -> None:
        """
        Register a URL pattern for this plugin.

        Args:
            route: URL route (e.g., 'noise/')
            view_or_include: View function or include() result
            name: Optional URL name
        """
        self._url_patterns.append(
            {"route": route, "view": view_or_include, "name": name}
        )
        logger.info(f"Plugin {self.name} registered URL: {route}")

    def get_url_patterns(self) -> List[Dict]:
        """Get all registered URL patterns."""
        return self._url_patterns

    # Model methods

    def register_model(self, model_class: Type[models.Model]) -> None:
        """Register a Django model with this plugin."""
        self._models.append(model_class)
        logger.info(f"Plugin {self.name} registered model: {model_class.__name__}")

    def get_models(self) -> List[Type[models.Model]]:
        """Get all registered models."""
        return self._models

    # Admin methods

    def register_admin_menu(self, label: str, url: str, icon: str = "circle") -> None:
        """
        Register an admin menu item.

        Args:
            label: Menu label
            url: URL path
            icon: FontAwesome icon name
        """
        self._admin_menus.append({"label": label, "url": url, "icon": icon})

    def get_admin_menus(self) -> List[Dict]:
        """Get all registered admin menus."""
        return self._admin_menus

    # Event methods

    def register_event(self, event_name: str, callback: Callable) -> None:
        """Register an event listener."""
        if event_name not in self._events:
            self._events[event_name] = []
        self._events[event_name].append(callback)
        logger.info(f"Plugin {self.name} registered listener for event: {event_name}")

    def emit_event(self, event_name: str, *args, **kwargs) -> None:
        """Emit an event to all registered listeners."""
        if event_name in self._events:
            for callback in self._events[event_name]:
                try:
                    callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_name}: {e}")

    # Schedule methods

    def register_schedule(
        self, interval: int, callback: Callable, name: str = None
    ) -> None:
        """
        Register a scheduled task.

        Args:
            interval: Interval in seconds
            callback: Function to call
            name: Optional task name
        """
        self._schedules.append(
            {
                "interval": interval,
                "callback": callback,
                "name": name or callback.__name__,
                "last_run": 0,
            }
        )
        logger.info(
            f"Plugin {self.name} registered schedule: {name} (every {interval}s)"
        )

    def get_schedules(self) -> List[Dict]:
        """Get all registered schedules."""
        return self._schedules


class PluginManager:
    """
    Manager for all plugins in the system.

    Handles:
    - Plugin discovery and loading
    - Dependency resolution
    - Lifecycle management
    - GPIO pin allocation
    """

    def __init__(self):
        self._plugins: Dict[str, PluginBase] = {}
        self._plugin_instances: Dict[str, Any] = {}
        self._loaded = False
        self._gpio_allocations: Dict[int, str] = {}  # pin -> plugin

    def get_plugin_path(self) -> Path:
        """Get the path to the plugins directory."""
        return Path(settings.BASE_DIR) / "plugins"

    def discover_plugins(self) -> List[str]:
        """
        Discover all available plugins in the plugins directory.

        Returns:
            List of plugin import paths
        """
        plugins_path = self.get_plugin_path()
        if not plugins_path.exists():
            logger.warning(f"Plugins directory not found: {plugins_path}")
            return []

        plugins = []

        # Look for plugin.py files in plugins/*/
        for author_dir in plugins_path.iterdir():
            if not author_dir.is_dir():
                continue

            for plugin_dir in author_dir.iterdir():
                if not plugin_dir.is_dir():
                    continue

                plugin_file = plugin_dir / "plugin.py"
                if plugin_file.exists():
                    # Import path: plugins.author.plugin_name
                    import_path = f"plugins.{author_dir.name}.{plugin_dir.name}"
                    plugins.append(import_path)
                    logger.info(f"Discovered plugin: {import_path}")

        return plugins

    def load_plugin(
        self, import_path: str, enabled: bool = True
    ) -> Optional[PluginBase]:
        """
        Load a plugin from its import path.

        Args:
            import_path: Python import path (e.g., 'plugins.acme.myplugin')
            enabled: Whether to enable the plugin

        Returns:
            Plugin instance or None if loading failed
        """
        try:
            # Import the plugin module
            module = importlib.import_module(import_path)

            # Look for Plugin class
            if not hasattr(module, "Plugin"):
                logger.error(f"Plugin {import_path} does not have a Plugin class")
                return None

            plugin_class = module.Plugin

            # Verify it's a PluginBase subclass
            if not issubclass(plugin_class, PluginBase):
                logger.error(
                    f"Plugin {import_path} Plugin class must inherit from PluginBase"
                )
                return None

            # Create instance
            plugin = plugin_class(plugin_path=import_path, enabled=enabled)

            # Store the plugin
            self._plugins[import_path] = plugin

            logger.info(
                f"Loaded plugin: {plugin.name} ({import_path}) v{plugin.version}"
            )

            return plugin

        except Exception as e:
            logger.error(f"Failed to load plugin {import_path}: {e}")
            return None

    def check_dependencies(self, plugin: PluginBase) -> bool:
        """
        Check if all plugin dependencies are satisfied.

        Args:
            plugin: Plugin to check

        Returns:
            True if all dependencies are met
        """
        for dep in plugin.requires:
            if dep not in self._plugins:
                logger.error(
                    f"Plugin {plugin.name} requires {dep} which is not installed"
                )
                return False
        return True

    def allocate_gpio_pins(self, plugin: PluginBase) -> bool:
        """
        Allocate GPIO pins for a plugin, checking for conflicts.

        Args:
            plugin: Plugin requesting pins

        Returns:
            True if all pins were allocated successfully
        """
        for name, pin in plugin._gpio_pins.items():
            if pin in self._gpio_allocations:
                owner = self._gpio_allocations[pin]
                logger.error(
                    f"GPIO pin {pin} ({name}) requested by {plugin.name} "
                    f"but already allocated to {owner}"
                )
                return False

            self._gpio_allocations[pin] = plugin.name
            logger.info(f"Allocated GPIO pin {pin} to {plugin.name}")

        return True

    def boot_plugin(self, plugin: PluginBase) -> bool:
        """
        Boot a plugin by calling its boot() method.

        Args:
            plugin: Plugin to boot

        Returns:
            True if boot was successful
        """
        if not plugin.enabled:
            logger.info(f"Plugin {plugin.name} is disabled, skipping boot")
            return False

        try:
            # Check dependencies
            if not self.check_dependencies(plugin):
                return False

            # Allocate GPIO pins
            if not self.allocate_gpio_pins(plugin):
                return False

            # Call boot method
            plugin.boot()

            logger.info(f"Booted plugin: {plugin.name}")
            return True

        except Exception as e:
            logger.error(f"Error booting plugin {plugin.name}: {e}")
            return False

    def register_plugin(self, plugin: PluginBase) -> bool:
        """
        Register a plugin by calling its register() method.

        Args:
            plugin: Plugin to register

        Returns:
            True if registration was successful
        """
        if not plugin.enabled:
            return False

        try:
            plugin.register()
            logger.info(f"Registered plugin: {plugin.name}")
            return True

        except Exception as e:
            logger.error(f"Error registering plugin {plugin.name}: {e}")
            return False

    def load_all(self) -> None:
        """Load, boot, and register all discovered plugins."""
        if self._loaded:
            return

        logger.info("Loading plugins...")

        # Discover all plugins
        plugin_paths = self.discover_plugins()

        # Load all plugins first
        for path in plugin_paths:
            self.load_plugin(path)

        # Boot plugins (respecting dependencies)
        for path, plugin in self._plugins.items():
            self.boot_plugin(plugin)

        # Register plugins
        for path, plugin in self._plugins.items():
            self.register_plugin(plugin)

        self._loaded = True
        logger.info(f"Loaded {len(self._plugins)} plugins")

    def get_plugin(self, import_path: str) -> Optional[PluginBase]:
        """Get a loaded plugin by its import path."""
        return self._plugins.get(import_path)

    def get_all_plugins(self) -> Dict[str, PluginBase]:
        """Get all loaded plugins."""
        return self._plugins.copy()

    def get_enabled_plugins(self) -> Dict[str, PluginBase]:
        """Get all enabled plugins."""
        return {k: v for k, v in self._plugins.items() if v.enabled}

    def disable_plugin(self, import_path: str) -> bool:
        """Disable a plugin."""
        plugin = self._plugins.get(import_path)
        if plugin:
            plugin.enabled = False
            plugin.uninstall()
            logger.info(f"Disabled plugin: {plugin.name}")
            return True
        return False

    def enable_plugin(self, import_path: str) -> bool:
        """Enable a plugin."""
        plugin = self._plugins.get(import_path)
        if plugin:
            plugin.enabled = True
            self.boot_plugin(plugin)
            self.register_plugin(plugin)
            logger.info(f"Enabled plugin: {plugin.name}")
            return True
        return False


# Global plugin manager instance
plugin_manager = PluginManager()
