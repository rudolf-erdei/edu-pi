# Troubleshooting

Common issues and solutions for Tinko.

## Installation Issues

### uv: command not found

**Problem:** UV package manager not installed

**Solution:**
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Cannot install dependencies

**Problem:** Package installation fails

**Solutions:**
```bash
# Clear UV cache
uv cache clean

# Update UV
uv self update

# Install with verbose output
uv sync -v
```

### Import errors after installation

**Problem:** Cannot import modules

**Solutions:**
1. Ensure virtual environment is activated
2. Check Python path includes project root
3. Verify `__init__.py` files exist
4. Restart terminal/IDE

## Database Issues

### Migration errors

**Problem:** Migrations fail

**Solutions:**
```bash
# Run migrations with fresh database
rm db.sqlite3
uv run python manage.py migrate

# Create new migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Fake migration if stuck
uv run python manage.py migrate --fake
```

### Database is locked

**Problem:** SQLite database locked

**Solutions:**
```bash
# Check for other processes
lsof db.sqlite3

# Kill processes using database
kill -9 <PID>

# Wait and retry
sleep 5
uv run python manage.py migrate
```

## GPIO Issues

### Permission denied

**Problem:** Cannot access GPIO pins

**Solutions:**
```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Apply changes (log out and back in)
# Or use newgrp
newgrp gpio

# Check permissions
ls -la /dev/gpiomem
```

### GPIO pins not working

**Problem:** LEDs/sensors not responding

**Troubleshooting:**
1. Check pin numbers (BCM vs Physical)
2. Verify wiring connections
3. Test with simple script
4. Check LED orientation (cathode/anode)

**Test Script:**
```python
from gpiozero import LED
from time import sleep

led = LED(17)  # GPIO 17
led.on()
sleep(2)
led.off()
```

### Pin conflicts

**Problem:** Multiple plugins use same pins

**Solutions:**
- Check [GPIO Pin Assignments](../developer/hardware/gpio-pins.md)
- Remap pins in plugin configuration
- Disable conflicting plugins
- Use different pins for custom plugins

## WebSocket Issues

### WebSocket connection failed

**Problem:** Cannot connect to WebSocket

**Solutions:**
1. Verify using ASGI server (daphne/runserver)
2. Check firewall settings
3. Ensure WebSocket URL is correct
4. Check browser console for errors

### Real-time updates not working

**Problem:** WebSocket connected but no updates

**Troubleshooting:**
1. Check consumer is running
2. Verify routing configuration
3. Look for channel layer errors
4. Test with browser DevTools

## Audio Issues

### No sound output

**Problem:** No audio from plugins

**Solutions:**
```bash
# Test speaker
speaker-test -t wav

# Check audio devices
aplay -l

# Set default device
sudo raspi-config
# Navigate to: System Options > Audio

# Check volume
alsamixer
```

### Microphone not working

**Problem:** Noise Monitor not detecting audio

**Solutions:**
```bash
# List audio devices
arecord -l

# Test microphone
arecord -D plughw:1,0 -d 5 test.wav
aplay test.wav

# Check USB microphone
lsusb
```

## Web Interface Issues

### CSS/JS not loading

**Problem:** Static files not served

**Solutions:**
```bash
# Collect static files
uv run python manage.py collectstatic --noinput

# Check static files exist
ls static/

# Debug mode
# Set DEBUG=True in .env
```

### 404 errors for plugins

**Problem:** Plugin URLs not found

**Solutions:**
1. Verify plugin is enabled in admin
2. Check URL registration in `register()`
3. Ensure `__init__.py` imports Plugin
4. Restart server

### Admin interface not accessible

**Problem:** Cannot access /admin/

**Solutions:**
```bash
# Create superuser
uv run python manage.py createsuperuser

# Check admin URLs
# config/urls.py should include:
# path('admin/', admin.site.urls)
```

## Performance Issues

### Slow page loading

**Problem:** Web interface is slow

**Solutions:**
- Check Raspberry Pi resources: `htop`
- Disable unused plugins
- Optimize database queries
- Use caching
- Ensure adequate power supply

### High CPU usage

**Problem:** Pi runs hot or slow

**Solutions:**
```bash
# Check processes
htop

# Kill stuck processes
kill -9 <PID>

# Restart Tinko
sudo systemctl restart tinko
```

### Memory issues

**Problem:** Out of memory

**Solutions:**
- Stop unused plugins
- Clear cache: `uv cache clean`
- Restart service: `sudo systemctl restart tinko`
- Check for memory leaks in custom plugins

## Plugin Issues

### Plugin not loading

**Problem:** Plugin doesn't appear in dashboard

**Troubleshooting:**
1. Check `__init__.py` exists and imports Plugin
2. Verify `plugin.py` has Plugin class
3. Ensure Plugin inherits from PluginBase
4. Check Django logs for errors
5. Verify plugin is enabled in admin

### Plugin errors

**Problem:** Plugin crashes

**Solutions:**
```python
# Enable debug logging
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        '': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### Settings not saving

**Problem:** Plugin settings don't persist

**Solutions:**
1. Run migrations
2. Check database permissions
3. Verify settings key is unique
4. Check for validation errors

## System Issues

### Service won't start

**Problem:** systemd service fails

**Solutions:**
```bash
# Check status
sudo systemctl status tinko

# View logs
sudo journalctl -u tinko -f

# Check permissions
ls -la /home/pi/edu-pi/

# Fix permissions
sudo chown -R pi:pi /home/pi/edu-pi
```

### Port already in use

**Problem:** Port 8000 occupied

**Solutions:**
```bash
# Find process
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>

# Or use different port
uv run python manage.py runserver 0.0.0.0:8080
```

### Disk space full

**Problem:** No disk space

**Solutions:**
```bash
# Check space
df -h

# Clean UV cache
uv cache clean

# Remove old logs
sudo journalctl --vacuum-time=7d

# Clear temporary files
sudo apt-get clean
```

## Debug Mode

### Enable Debug Mode

```bash
# .env file
DEBUG=True
```

**Benefits:**
- Detailed error pages
- Django debug toolbar
- SQL query logging
- Stack traces

### View Logs

```bash
# Django logs
uv run python manage.py runserver

# System logs (production)
sudo journalctl -u tinko -f

# Custom log location
# Check settings.py for LOGGING config
```

## Getting Help

If you can't solve the issue:

1. **Check documentation:**
   - Plugin guides
   - API reference
   - Hardware guides

2. **Search issues:**
   - GitHub Issues
   - Django documentation
   - gpiozero documentation

3. **Collect information:**
   - Error messages
   - Log files
   - System info (`uname -a`)
   - Python version (`python --version`)

4. **Create minimal reproduction:**
   - Simplify the problem
   - Isolate the component
   - Test with fresh install

## Quick Fixes

### Nuclear Option: Fresh Start

```bash
# Backup database
cp db.sqlite3 db.sqlite3.backup

# Clean everything
rm -rf .venv
rm -rf __pycache__
rm db.sqlite3

# Reinstall
uv sync
uv run python manage.py migrate
uv run python manage.py createsuperuser
```

### Emergency Restart

```bash
# Kill all Python processes
sudo pkill -f python

# Restart Tinko
sudo systemctl restart tinko
```

## Common Error Messages

### "No module named 'gpiozero'"
**Fix:** `uv sync --extra pi`

### "OperationalError: database is locked"
**Fix:** Wait and retry, or restart service

### "PermissionError: [Errno 13] Permission denied"
**Fix:** `sudo usermod -a -G gpio $USER`

### "ImproperlyConfigured: The SECRET_KEY setting must not be empty"
**Fix:** Set SECRET_KEY in .env file

### "TemplateDoesNotExist"
**Fix:** Check template path and app_label

## See Also

- [Configuration](configuration.md) - Configuration options
- [Plugin Tutorial](../developer/plugins/tutorial.md) - Plugin development
- [Developer Setup](../developer/setup.md) - Development environment
