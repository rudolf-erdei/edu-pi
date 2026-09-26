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

### Captive portal not appearing on phone

**Problem:** Phone connects to "Tinko-Setup" WiFi but no login page appears

**Solutions:**

1. **Check if dnsmasq is running:**
```bash
sudo systemctl status dnsmasq
```

2. **Check for port 53 conflicts** (NetworkManager's internal dnsmasq can conflict with standalone dnsmasq):
```bash
sudo ss -tlnp | grep :53
# There should be ONE dnsmasq process on port 53
# If two processes are on port 53, NM's internal dnsmasq is conflicting
```

3. **Verify NM's dnsmasq has DNS disabled:**
```bash
cat /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf
# Should contain: port=0
```

4. **Verify dnsmasq captive portal config:**
```bash
grep -E "address=/#|interface=wlan0|bind-interfaces|except-interface" /etc/dnsmasq.conf
# All four lines should be present
```

5. **Verify dnsmasq is NOT listening on loopback** (prevents Pi's DNS from being trapped):
```bash
grep "except-interface=lo" /etc/dnsmasq.conf
# If missing, add it:
echo "except-interface=lo" | sudo tee -a /etc/dnsmasq.conf
```

6. **Verify NetworkManager upstream DNS** (prevents resolv.conf from pointing to local dnsmasq):
```bash
cat /etc/NetworkManager/conf.d/dns-upstream.conf
# Should contain: [global-dns-domain-*]\nservers=8.8.8.8,8.8.4.4
```

5. **Verify captive portal detection URLs work** — From a device connected to Tinko-Setup, try:
```bash
curl -v http://10.42.0.1/generate_204
# Should return 302 redirect to http://10.42.0.1/
```

6. **Restart dnsmasq while hotspot is active:**
```bash
sudo systemctl restart dnsmasq
```

7. **Manual fallback:** If the captive portal popup doesn't appear, open a browser and navigate to `http://10.42.0.1`

### dnsmasq fails to start

**Problem:** dnsmasq won't start due to port 53 conflict

**Common cause:** NetworkManager's internal dnsmasq (used for `ipv4.method shared`) also binds to port 53 on the hotspot IP, conflicting with the standalone dnsmasq.

**Solutions:**

1. **Verify NM's dnsmasq has DNS disabled:**
```bash
cat /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf
# Must contain: port=0
# If missing, create it:
sudo mkdir -p /etc/NetworkManager/dnsmasq-shared.d/
echo "port=0" | sudo tee /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf
```

2. **Check if systemd-resolved is using port 53:**
```bash
sudo ss -tlnp | grep :53
```

3. **If systemd-resolved is the conflict**, disable its stub listener:
```bash
sudo mkdir -p /etc/systemd/resolved.conf.d/
echo -e "[Resolve]\nDNSStubListener=no" | sudo tee /etc/systemd/resolved.conf.d/no-stub.conf
sudo systemctl restart systemd-resolved
```

4. **Ensure bind-interfaces is set:**
```bash
grep "bind-interfaces" /etc/dnsmasq.conf
# If missing:
echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf
sudo systemctl restart dnsmasq
```

### WiFi hotspot not created on boot

**Problem:** "Tinko-Setup" hotspot doesn't appear

**Solutions:**

1. **Check the WiFi captive portal service:**
```bash
sudo systemctl status tinko-wifi
sudo journalctl -u tinko-wifi -f
```

2. **Verify service type is oneshot** (not simple):
```bash
grep "Type=" /etc/systemd/system/tinko-wifi.service
# Should be: Type=oneshot
# If it says Type=simple, update it
```

3. **Manually start the hotspot for testing:**
```bash
sudo /home/tinko/startup_check.sh
```

4. **Check if NetworkManager is managing wlan0:**
```bash
nmcli device status
# wlan0 should show as "wifi" and "managed"
```

### WiFi connection keeps cycling (connect/disconnect)

**Problem:** Pi connects to WiFi but keeps disconnecting and reconnecting

**Solutions:**

1. **Disable IPv6 on the hotspot connection** (IPv6 DHCP failures can cause cycling):
```bash
nmcli connection modify "Tinko-Setup" ipv6.method disabled
```

2. **Disable NetworkManager connectivity checks:**
```bash
cat /etc/NetworkManager/conf.d/no-connectivity-check.conf
# Should contain: [connectivity]\ninterval=0
# If missing:
sudo mkdir -p /etc/NetworkManager/conf.d/
echo -e "[connectivity]\ninterval=0" | sudo tee /etc/NetworkManager/conf.d/no-connectivity-check.conf
sudo systemctl reload NetworkManager
```

3. **Check for duplicate WiFi profiles:**
```bash
nmcli -f NAME,DEVICE connection show
# Two profiles that carry the same SSID both try to connect, and the radio
# bounces between them. See "Two profiles for one network" below.
```
Only delete one after checking which SSID each profile carries — the profile
name is often not the SSID (`nmcli -g 802-11-wireless.ssid connection show
"<name>"`). `wifi_worker.sh` no longer creates duplicates: it matches on the
SSID, not the name.

### Two profiles for one network

**Problem:** `nmcli -f NAME connection show` lists two profiles for the same
WiFi network, e.g. `netplan-wlan0-School-WiFi` and `School-WiFi`, and the Pi
behaves unpredictably over which one it uses.

**Explanation:** A Pi imaged with Raspberry Pi Imager or configured with netplan
names its profile `netplan-wlan0-<SSID>`. Older versions of `wifi_worker.sh`
compared that name against the SSID, failed to recognise the network the Pi
already knew, and created a second profile for it.

**Solutions:** Current versions match on the SSID and leave the existing profile
in place, so this only affects a Pi that was set up before. On such a Pi, keep
the one that is stored on disk and delete the other:

```bash
nmcli -f NAME,AUTOCONNECT,FILENAME connection show
# Keep the profile under /etc/NetworkManager/system-connections/ — it survives
# a reboot. Delete the duplicate:
sudo nmcli connection delete "<duplicate name>"
```

### Pi forgot the WiFi password after a reboot

**Problem:** WiFi was configured through the setup page and worked, but after
restarting the Pi the hotspot is up again and the school network's password has
to be typed again.

**Explanation:** A netplan-generated profile (the `netplan-wlan0-<SSID>` one,
stored in `/run`) is rebuilt from `/etc/netplan/*.yaml` at every boot. Writing a
new password to it with `nmcli` appears to succeed, but only in memory — the
next boot brings the yaml's password back. An `/etc` keyfile with the same UUID
cannot shadow it; `/run` wins.

**Solutions:**

1. **Check which the Pi is using and where the profile lives:**
```bash
nmcli -f NAME,AUTOCONNECT,FILENAME connection show
cat /var/log/tinko_wifi.log | tail -20
```
`wifi_worker.sh` logs whether the profile it used is on disk or is "rebuilt by
netplan at every boot".

2. **Current versions save the working password themselves.** When the password
of a netplan-managed profile is changed, the credential that worked is copied
into `Tinko-WiFi-<SSID>` in
`/etc/NetworkManager/system-connections/` with `autoconnect-priority 10`, which
survives reboots and wins over the netplan profile at the next boot. Nothing has
to be done by hand:

```bash
nmcli -f NAME,AUTOCONNECT,AUTOCONNECT-PRIORITY,FILENAME connection show
# Tinko-WiFi-<SSID>   yes   10   /etc/NetworkManager/system-connections/...
```

3. **If setup mode keeps coming back on a Pi that should be online**, see
"WiFi hotspot not created on boot" above and the boot gate in
`/var/log/tinko_wifi.log`.

To see what a handoff would do without changing anything:

```bash
sudo TINKO_DRY=1 /bin/bash /home/tinko/wifi_worker.sh "<SSID>" "<password>"
```

### No internet after connecting to WiFi (DNS broken)

**Problem:** Pi connects to WiFi but `curl` hangs/freezes or DNS resolution fails

**Common cause:** dnsmasq is running with wildcard DNS redirect (`address=/#/10.42.0.1`) even though the Pi is connected to a real WiFi network. This intercepts DNS queries and resolves everything to the old hotspot IP.

**Solutions:**

1. **Check if dnsmasq is running (it shouldn't be when connected to WiFi):**
```bash
sudo systemctl status dnsmasq
# If active, stop it:
sudo systemctl stop dnsmasq
```

2. **Verify dnsmasq is disabled at boot:**
```bash
sudo systemctl is-enabled dnsmasq
# Should show "disabled" or "masked"
# If enabled, disable it:
sudo systemctl disable dnsmasq
```

3. **Test DNS resolution:**
```bash
nslookup google.com
# Should resolve to a real IP, not 10.42.0.1
```

4. **Verify resolv.conf points to the correct DNS:**
```bash
cat /etc/resolv.conf
# Should show your router's DNS or 8.8.8.8, NOT 127.0.0.1 or 10.42.0.1
# If it points to 127.0.0.1, DNS queries may be trapped by local dnsmasq
```

5. **Check if dnsmasq is listening on loopback (DNS trap):**
```bash
grep "except-interface=lo" /etc/dnsmasq.conf
# If missing, dnsmasq answers queries on 127.0.0.1 too — add it:
echo "except-interface=lo" | sudo tee -a /etc/dnsmasq.conf
sudo systemctl restart dnsmasq  # only if in hotspot mode
```

6. **Verify NetworkManager upstream DNS configuration:**
```bash
cat /etc/NetworkManager/conf.d/dns-upstream.conf
# Should contain:
# [global-dns-domain-*]
# servers=8.8.8.8,8.8.4.4
# If missing, create it (see install script)
```

7. **Disable systemd-resolved stub listener** (if active, it hijacks DNS to 127.0.0.53):
```bash
systemctl is-active systemd-resolved
# If active:
sudo mkdir -p /etc/systemd/resolved.conf.d/
echo -e "[Resolve]\nDNSStubListener=no" | sudo tee /etc/systemd/resolved.conf.d/no-stub.conf
sudo systemctl restart systemd-resolved
```

### iptables command not found (nftables migration)

**Problem:** `iptables: command not found` errors, or NetworkManager hotspot NAT doesn't work

**Explanation:** Debian 12 Bookworm (newer Raspberry Pi OS) has phased out iptables in favor of nftables. NetworkManager's hotspot shared mode uses nftables for NAT masquerading on these systems. Without nftables, the hotspot NAT silently fails.

**Solutions:**

1. **Install nftables:**
```bash
sudo apt-get install -y nftables
```

2. **Install the iptables-nft compatibility wrapper** (for any legacy tools that still call iptables):
```bash
sudo apt-get install -y iptables
# This installs iptables-nft which translates iptables commands to nftables
```

3. **Verify nftables is working:**
```bash
sudo nft list ruleset
# Should show NetworkManager's NAT rules when hotspot is active
```

4. **Check NetworkManager's firewall backend:**
```bash
cat /etc/NetworkManager/NetworkManager.conf
# On Bookworm, NM should use nftables by default
# If firewall backend is explicitly set to iptables, change it:
# [main]
# firewall-backend=nftables  (or remove the line to use default)
```

### WiFi scan shows empty list in portal

**Problem:** The SSID dropdown is empty when connecting Tinko to WiFi

**Explanation:** The Pi's WiFi radio cannot scan for networks while in AP (hotspot) mode. This is a hardware limitation of most Raspberry Pi WiFi chips.

**Solution:** Type the WiFi network name manually in the SSID field.

### LCD screen is dark during WiFi setup

**Problem:** The Pi is in setup mode (the "Tinko-Setup" hotspot is up), but the LCD shows nothing.

**Explanation:** The screen is drawn by `portal.py`, which needs the adafruit/PIL LCD libraries. Those live in the project venv, while `startup_check.sh` starts the portal with the system `python3`. The portal re-runs itself under the venv interpreter to get them; if no interpreter on the Pi has the libraries, the portal says so and serves the setup page with the screen left dark.

**Solutions:**
```bash
# Check the portal is running and what it said about the screen
sudo journalctl -u tinko-wifi -n 50 | grep LCD

# "re-running the portal under ..." = the switch worked.
# "no interpreter with the LCD libraries found" = check the venv:
ls /home/tinko/edu-pi/.venv/bin/python
/home/tinko/edu-pi/.venv/bin/python -c "import board, adafruit_rgb_display"

# If those imports fail, reinstall the Pi dependencies
cd /home/tinko/edu-pi && uv sync --extra pi
```

The LCD is not required to finish setup — the hotspot name and password are fixed (`Tinko-Setup` / `tinko1234`) and the setup page still works.

### School logo uploads but never appears

**Problem:** On Settings → Global, a logo is chosen and **Save Settings** is
pressed. The page reloads, says the settings were saved, and the logo is still
not shown — in the settings page's preview box or in the header of any page.
It looks as if the upload does not work.

**Explanation:** The upload itself works. The file is written to
`media/site/logos/logo.png` and its path is saved in the
`tinko.global.logo_path` setting. What fails is *serving* it: the file is
requested from `/media/...`, and nothing answers that URL. `Static` files are
handled by WhiteNoise (which only serves `STATIC_ROOT`), while the media route
used to be added only when `DEBUG` was on — and a Pi runs with `DEBUG=False`.
The image URL therefore returned 404, and the browser showed an empty box.

**Solutions:**

1. **Confirm it is this** — the upload leaves evidence behind even when the
   image never appears:
```bash
ls -l /home/tinko/edu-pi/media/site/logos/
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1/media/site/logos/logo.png
```
A file with a recent timestamp (upload worked) and `404` (serving does not) is
the signature. A working install returns `200`.

2. **Update the software.** `config/urls.py` serves `MEDIA_URL` regardless of
   `DEBUG`; run `bash update.sh` on the Pi to pick it up.

3. **Check the stored path matches the file:**
```bash
sqlite3 /home/tinko/edu-pi/db.sqlite3 \
  "SELECT key, value FROM plugin_system_sitesetting WHERE key='tinko.global.logo_path'"
```
The value is relative to `MEDIA_ROOT` (`site/logos/logo.png`).

4. **If the file is missing altogether**, the upload did fail — check the size
   (5 MB maximum) and the format (PNG, JPG or GIF), and re-upload. A phone
   screenshot saved as HEIC or WebP is refused with an error on the page.

### Update from the web UI fails with "Permission denied"

**Problem:** Settings → Updates → **Update Now** shows

```
Failed to trigger update daemon: [Errno 13] Permission denied: '/run/tinko-update/trigger'
```

**Explanation:** Two processes share `/run/tinko-update`, and they run as
different users. The daemon (`tinko-update.service`) runs as **root** and owns
the directory; the web app (`tinko.service`) runs as the unprivileged service
user and is the one that writes the trigger file. `/run` is a tmpfs, so the
directory does not survive a reboot — the daemon recreates it at every boot, and
a directory created by root under root's umask is `drwxr-xr-x root root`, which
the web app cannot write to. The world-writable mode set at install time is lost
at the first reboot, so this surfaces on any Pi that has been restarted since it
was set up or last updated.

**Solutions:**

1. **Just try again.** The web app repairs the directory itself with the
   passwordless `mkdir`/`chmod` the installer granted it, and retries the write,
   so a current install recovers on its own.

2. **Check the state:**
```bash
ls -ld /run/tinko-update     # needs to be drwxrwxrwx, not drwxr-xr-x
systemctl is-active tinko-update
```

3. **Fix it by hand** (this is all the repair does):
```bash
sudo chmod 777 /run/tinko-update
```

4. **If it comes back after every reboot**, the daemon is older than the fix
   that makes it set the mode itself. Run the update from the command line
   once — it reinstalls and restarts the daemon:
```bash
cd ~/edu-pi && bash update.sh
```

### Update Now says an update is already running

**Problem:** Settings → Updates → **Update Now** is refused with *Update already
in progress*, and keeps being refused. Nothing is updating: the stage list is
empty and `systemctl status tinko-update` shows the daemon sitting idle.

**Explanation:** The dashboard tracks an update with a row in the database (it
must, so the page still knows what happened after a reboot), while the run
itself is tracked by two files under `/run/tinko-update/` — the `trigger` file
the dashboard writes and the `status.json` the daemon rewrites as it goes. `/run`
is a tmpfs: switching the Pi off while an update is running wipes both files,
while the database row survives and still says *in progress*. Nothing was left
to reconcile the two, so the row blocked every later attempt until it was a day
old.

A run that is really in progress leaves both files behind, so the dashboard can
tell an abandoned record from a live one: with no trigger file and no running
`status.json`, the record is marked failed and the update can be started again.
A two-minute grace period covers the moment between writing the record and the
daemon picking it up, and a second teacher clicking at the same time.

**Solutions:**

1. **Wait two minutes and reload the page.** The check runs on every status
   request, so the abandoned record is cleared on the next one and the button
   works again. This is what is supposed to happen — if it does, nothing is
   wrong.
2. **Check whether a run really is in progress:**
```bash
ls -l /run/tinko-update/
cat /run/tinko-update/status.json 2>/dev/null
journalctl -u tinko-update -n 30
```
A `trigger` file plus a `status.json` reading `"in_progress"` means an update
*is* running — leave it alone. If the directories are empty, the record is
stale.
3. **Clear the record by hand** (equivalent to waiting, for an install that
   predates the fix, or to do it immediately):
```bash
cd ~/edu-pi && uv run python manage.py shell -c "
from core.update_system.models import UpdateStatus
from django.utils import timezone
UpdateStatus.objects.filter(status='in_progress').update(
    status='failed', completed_at=timezone.now(),
    error_message='Cleared by hand')
"
```
4. **Update the software** to get the reconciliation, and so the daemon's log is
   readable — the unit now sets `PYTHONUNBUFFERED=1`, without which Python
   buffers the daemon's output and `journalctl -u tinko-update` shows nothing
   even while it works.

!!! note "Do not run `update.sh` by hand while a web update is running"
    A CLI update reinstalls and restarts `tinko-update.service`, which kills
    whatever the daemon was running and leaves exactly the abandoned record
    described above. Current installs skip that restart while a trigger file is
    present.

### The school logo disappears after an update

**Problem:** A logo is uploaded on Settings → Global and appears in the header.
After an update it is back to the previous one — or gone — although the settings
page still says the upload was saved. Uploading it again works until the next
update.

**Explanation:** `media/site/logos/logo.png` was tracked in git. An update
stashes local changes, pulls, and pops the stash, so a file the *app* writes was
being managed by git: the pull checked the committed copy out over the one the
school had uploaded, and the merge then saw the teacher's file as a change to
resolve. The logo does not vanish — it is replaced by whatever was last
committed, which is why it sometimes looks like an older logo rather than
nothing.

**Solutions:**

1. **Update the software.** `update.sh` and `update-web.sh` now move every file
   git still tracks under `media/` out of the way of the pull and back
   afterwards, on both the success and failure path, exactly as they already do
   for `db.sqlite3`. Upload the logo once more and it stays.
2. **Check what is tracked:**
```bash
cd ~/edu-pi && git ls-files media
```
Files listed there are the ones at risk. Once `media/` is untracked the list is
empty and the guard has nothing to do.
3. **Recover a logo left aside by an update that was interrupted** mid-pull —
   the file is still on the Pi, next to where it belongs:
```bash
ls -l ~/edu-pi/media/site/logos/
```
A `logo.png.update-tmp-<pid>` beside a missing `logo.png` is moved back by the
next update automatically; to do it now:
```bash
cd ~/edu-pi/media/site/logos && mv logo.png.update-tmp-* logo.png
```
4. **Re-upload** if it is genuinely gone (Settings → Global → School Logo). The
   upload itself was never the problem.

See also [School logo uploads but never appears](#school-logo-uploads-but-never-appears),
which is the other half of logo trouble: the file saved but not served.

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

If the path in the message is `/run/tinko-update/trigger`, the fix is different:
see [Update from the web UI fails with "Permission denied"](#update-from-the-web-ui-fails-with-permission-denied).

### "ImproperlyConfigured: The SECRET_KEY setting must not be empty"
**Fix:** Set SECRET_KEY in .env file

### "TemplateDoesNotExist"
**Fix:** Check template path and app_label

## See Also

- [Configuration](configuration.md) - Configuration options
- [Plugin Tutorial](../developer/plugins/tutorial.md) - Plugin development
- [Developer Setup](../developer/setup.md) - Development environment
