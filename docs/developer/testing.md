# Testing

Testing guidelines for Tinko plugins.

## Test Setup

### Configuration

**File:** `pyproject.toml`

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
DJANGO_SETTINGS_MODULE = "config.settings"
django_find_project = false
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test
uv run pytest tests/test_plugin.py::test_name -v

# Run with coverage
uv run pytest --cov=core --cov=plugins
```

## Writing Tests

### Basic Test Structure

```python
# plugins/acme/myplugin/tests.py
import pytest
from django.test import TestCase
from core.plugin_system.base import plugin_manager

class MyPluginTests(TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.plugin = plugin_manager.get_plugin('acme.myplugin')
    
    def test_plugin_loaded(self):
        """Test plugin is loaded."""
        self.assertIsNotNone(self.plugin)
        self.assertEqual(self.plugin.name, "My Plugin")
```

### Testing GPIO

```python
from unittest.mock import patch, MagicMock

class GPIOTests(TestCase):
    @patch('plugins.acme.myplugin.plugin.LED')
    def test_led_control(self, mock_led):
        """Test LED control."""
        # Set up mock
        mock_led_instance = MagicMock()
        mock_led.return_value = mock_led_instance
        
        # Call method
        self.plugin.blink_led()
        
        # Assert
        mock_led.assert_called_once_with(17)
        mock_led_instance.blink.assert_called_once()
```

### Database Tests

```python
import pytest
from django.test import TestCase
from plugins.acme.myplugin.models import Reading

@pytest.mark.django_db
class ModelTests(TestCase):
    def test_create_reading(self):
        """Test model creation."""
        reading = Reading.objects.create(
            value=42.0,
            timestamp=timezone.now()
        )
        self.assertEqual(reading.value, 42.0)
```

### API Tests

```python
from django.test import TestCase, Client

class APITests(TestCase):
    def setUp(self):
        self.client = Client()
    
    def test_get_status(self):
        """Test API endpoint."""
        response = self.client.get(
            '/plugins/acme/myplugin/api/status/'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('status', data)
```

### WebSocket Tests

```python
import pytest
from channels.testing import WebsocketCommunicator
from config.asgi import application

@pytest.mark.asyncio
async def test_websocket():
    """Test WebSocket consumer."""
    communicator = WebsocketCommunicator(
        application,
        '/ws/myplugin/'
    )
    connected, _ = await communicator.connect()
    assert connected
    
    # Send message
    await communicator.send_json_to({'message': 'test'})
    
    # Receive response
    response = await communicator.receive_json_from()
    assert response['type'] == 'response'
    
    await communicator.disconnect()
```

## Fixtures

### Conftest.py

```python
# tests/conftest.py
import pytest

@pytest.fixture
def plugin():
    """Provide plugin instance."""
    from core.plugin_system.base import plugin_manager
    return plugin_manager.get_plugin('acme.myplugin')

@pytest.fixture
def mock_gpio():
    """Mock GPIO for testing."""
    from unittest.mock import patch
    with patch('gpiozero.LED') as mock:
        yield mock
```

## Test Coverage

### Coverage Configuration

```toml
# pyproject.toml
[tool.pytest.ini_options]
addopts = "--cov=core --cov=plugins --cov-report=html"
```

### Generate Report

```bash
uv run pytest --cov-report=html
# Open htmlcov/index.html
```

## Mocking

### Mock External Services

```python
from unittest.mock import patch

def test_with_mock(self):
    with patch('requests.get') as mock_get:
        mock_get.return_value.json.return_value = {'temp': 20}
        
        result = self.plugin.get_weather()
        
        self.assertEqual(result['temp'], 20)
```

## Best Practices

- Test one thing per test
- Use descriptive test names
- Mock external dependencies
- Clean up after tests
- Use fixtures for common setup

## See Also

- [pytest Documentation](https://docs.pytest.org/)
- [Django Testing](https://docs.djangoproject.com/en/4.2/topics/testing/)
- [Plugin Tutorial](../plugins/tutorial.md)
