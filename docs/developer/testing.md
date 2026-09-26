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

## The Server Process Guard

The plugin system loads in **every** process that touches Django, not just the
server: `collectstatic` (the service's `ExecStartPre`), `migrate` from the
install and update scripts, any management command, and pytest itself. A plugin
that starts background work or claims hardware on load must tell those apart —
otherwise a two-second `collectstatic` grabs the microphone or paints the LCD
panel while the real service is starting, and pytest leaves a 10 Hz sampling
thread running through the whole session.

`core/server_process.py` is the single answer:

```python
from core.server_process import is_server_process

def boot(self):
    if not is_server_process():
        return
    self.start_background_service()
```

- `is_server_process()` is False for anything whose `sys.argv[1]` is a batch
  command in `BATCH_COMMANDS`, and False under pytest. Anything else counts as
  the server, so a service whose command line changes keeps working instead of
  quietly stopping.
- `running_under_pytest()` exists separately so a test can say *"pretend this is
  the server"* without pulling pytest out of `sys.modules`.

This was a real flakiness source, not a hypothetical: before the pytest check,
`sys.argv[1]` on a test run was a test path — not a management command — so the
run counted as the server and the Noise Monitor started a real thread at Django
setup, making whichever test next touched the display fail intermittently. There
was also a `runserver --noreload` session that wrote ~200 readings into the
tracked development DB before anyone noticed.

**Rule for plugin authors:** guard in `boot()` with `is_server_process()`, and
prefer a plugin `tests.py` that asserts the guard (see the Noise Monitor's
tests) over one that relies on the environment.

## Testing the Captive Portal Without Losing SSH

The captive portal's whole job is to take the network away, so **bringing the
hotspot up on `wlan0` drops the only link you have to the Pi.** Do not test it
that way on a device you cannot reach.

Three routes, in order of preference:

1. **Ethernet (best, zero risk).** Plug a cable into the Pi. `eth0` is normally
   free, so SSH rides the wire while `wlan0` runs the hotspot — the full branch
   becomes testable remotely.
2. **Dummy interface (what we use).** No wifi hardware involved, and the Pi's own
   link is untouched:

   ```bash
   sudo ip link add dummy0 type dummy
   sudo ip addr add 10.42.0.1/24 dev dummy0
   sudo ip link set dummy0 up
   sudo dnsmasq -C /dev/null --interface=dummy0 --bind-interfaces \
        --address=/#/10.42.0.1 --port=53
   PORTAL_PORT=8080 WIFI_WORKER_SCRIPT=/bin/true python3 wifi-connect/portal.py
   ```

   This proves the wildcard DNS answers, that all six captive-detection routes
   redirect to `http://10.42.0.1/`, that the form serves and the SSID/password
   validators reject bad input. It does **not** prove AP creation, NetworkManager
   shared-mode NAT, or the credential handoff/revert in `wifi_worker.sh` —
   `WIFI_WORKER_SCRIPT=/bin/true` stands in for the worker precisely so nothing
   reconfigures the network.
3. **A virtual radio (`mac80211_hwsim`)** would cover AP creation and a real
   client association with no risk, but it cannot run the shipped scripts
   verbatim: `wlan0` is hardcoded in `startup_check.sh`, `portal.py` and
   `/etc/dnsmasq.conf`, with no interface override. Declined so far for that
   reason.

Two findings from doing this that are worth keeping:

- **`dig`/`nslookup` must exist.** Without `dnsutils`, the dnsmasq check
  degraded to a bare socket-bind test that never proved dnsmasq *answers* — the
  install and update scripts now install it.
- **`StartLimit*` belong in `[Unit]`.** systemd logs *"Unknown key … ignoring"*
  for them in `[Service]` and silently drops the retry bound.

## Accessing the Field Pi Over SSH

For work on the real device (the one in the classroom):

- Host `tinko.local`, user `tinko`, password `tinko`. The **IP drifts** — always
  resolve the mDNS name, never cache an address.
- `sshpass` does not exist in Git Bash on Windows. Use `paramiko` from Python
  (`exec_command("bash -s")` to run a script over stdin), or a real
  `ssh`/`sshpass` from a Linux shell.
- A **non-interactive SSH PATH lacks `/usr/sbin`**, so `command -v nft` or
  `command -v shutdown` can "fail" on a machine where the tool is present. Probe
  absolute paths, or run the probe under `sudo`.
- `sudo` needs no password on the Pi (`/etc/sudoers.d/010_pi-nopasswd`), which is
  why install and update can run unattended — that file is deliberate, see
  [Update System](../reference/update-system.md#services-capabilities-and-root-access).
- A shell over SSH is **not** inside any service's sandbox, so it will happily
  report success for something the app itself cannot do. When the two disagree,
  read the service journal instead.

!!! warning "A halted Pi 4 cannot be woken remotely"
    No wake-on-LAN after `halt`. Recovering means physically cutting and
    restoring power. Never test shutdown from somewhere you cannot reach the
    plug.

## Best Practices

- Test one thing per test
- Use descriptive test names
- Mock external dependencies
- Clean up after tests
- Use fixtures for common setup

## See Also

- [pytest Documentation](https://docs.pytest.org/)
- [Django Testing](https://docs.djangoproject.com/en/4.2/topics/testing/)
- [Plugin Tutorial](plugins/tutorial.md)
