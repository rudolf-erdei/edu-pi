# Installation

This guide will walk you through installing Tinko on your Raspberry Pi.

## Prerequisites

Before installing Tinko, ensure you have:

- Raspberry Pi 4 (2GB+ RAM) or Raspberry Pi 3B+
- MicroSD card (32GB+ recommended) with Raspberry Pi OS
- Internet connection (for initial setup)
- USB microphone or microphone module (for Noise Monitor)
- Basic GPIO components (LEDs, resistors, breadboard) - see Hardware Requirements

## Step 1: Install UV Package Manager

Tinko uses UV for Python package management. Install it with:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your terminal or run:

```bash
source $HOME/.local/bin/env
```

## Step 2: Clone the Repository

```bash
git clone https://github.com/rudolf-erdei/edu-pi.git
cd edu-pi
```

## Step 3: Install Dependencies

Install the base dependencies:

```bash
uv sync
```

If you're installing on an actual Raspberry Pi (not for development), also install GPIO-specific dependencies:

```bash
uv sync --extra pi
```

This installs `RPi.GPIO` and `lgpio` which are required for hardware control.

## Step 4: Configure Environment

Create a `.env` file in the project root:

```bash
nano .env
```

Add the following configuration:

```env
DEBUG=False
SECRET_KEY=your-secret-key-here-change-this-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,your-pi-ip-address
TIME_ZONE=Europe/Bucharest
```

Replace `your-secret-key-here` with a random string and update `TIME_ZONE` to your location.

## Step 5: Run Migrations

Set up the database:

```bash
uv run python manage.py migrate
```

## Step 6: Create Admin User

Create a superuser account:

```bash
uv run python manage.py createsuperuser
```

Follow the prompts to set username, email, and password.

**Default credentials:**
- Username: `admin`
- Password: `admin123` (change this!)

## Step 7: Collect Static Files

```bash
uv run python manage.py collectstatic --noinput
```

## Step 8: Start the Server

For development:

```bash
uv run python manage.py runserver 0.0.0.0:8000
```

For production (see [Production Deployment](#production-deployment)):

```bash
uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

## Step 9: Verify Installation

Open a browser and navigate to:

- Dashboard: `http://your-pi-ip:8000/`
- Admin Panel: `http://your-pi-ip:8000/admin/`

You should see the Tinko dashboard!

## Production Deployment

For a production environment where Tinko runs automatically on boot, use the provided install script:

```bash
bash install-raspberry-pi.sh
```

The script handles everything: system dependencies, Python packages, database setup, GPIO permissions, captive portal, and systemd services.

### Manual Service Setup

If you prefer to set up services manually, the key service files are:

**Tinko WiFi Captive Portal** (`/etc/systemd/system/tinko-wifi.service`):
```ini
[Unit]
Description=Tinko Wi-Fi Captive Portal Check
After=NetworkManager.service
Before=tinko.service

[Service]
Type=oneshot
RemainAfterExit=no
ExecStart=/bin/bash /home/YOURUSER/startup_check.sh
User=root
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Tinko Django App** (`/etc/systemd/system/tinko.service`):
```ini
[Unit]
Description=Tinko Educational Platform
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/edu-pi
Environment="PATH=/home/pi/.local/bin"
Environment="PYTHONPATH=/home/pi/edu-pi"
Environment="DJANGO_SETTINGS_MODULE=config.settings"
Environment="EDUPI_DEBUG=False"
ExecStart=/home/pi/.local/bin/uv run daphne -b 0.0.0.0 -p 80 config.asgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

!!! note
    The `tinko-wifi.service` uses `Type=oneshot` (not `simple`). This is critical — it ensures systemd waits for the captive portal script to finish before starting Django, preventing a port 80 conflict. When there's internet, the script exits immediately. When there's no internet, it blocks until WiFi is configured.

!!! note
    Migrations and static file collection are handled by the install and update scripts.
    They are not run at service start time to avoid a 10-30 second delay.

### Captive Portal (WiFi Setup)

When the Pi boots without a configured WiFi network, it automatically creates a hotspot named **"Tinko-Setup"** with password **"tinko1234"**. Teachers can connect to this hotspot from their phone and configure the school WiFi through a simple web form.

**Key configuration files** (set up automatically by the install script):

| File | Purpose |
|------|---------|
| `/etc/dnsmasq.conf` | Wildcard DNS redirect (`address=/#/10.42.0.1`) |
| `/etc/NetworkManager/dnsmasq-shared.d/no-dns.conf` | Disables DNS in NM's internal dnsmasq (`port=0`) to prevent port 53 conflict |
| `/etc/NetworkManager/conf.d/no-connectivity-check.conf` | Disables NM connectivity checks (`interval=0`) to prevent hotspot disconnects |
| `/etc/tinko-portal/cert.pem` | Self-signed TLS cert for HTTPS captive portal detection |

### Enable and Start Services

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable tinko-wifi
sudo systemctl enable tinko

# Start the services
sudo systemctl start tinko-wifi
sudo systemctl start tinko

# Check status
sudo systemctl status tinko-wifi
sudo systemctl status tinko
```

### View Logs

```bash
# Django app logs
sudo journalctl -u tinko -f

# Captive portal logs
sudo journalctl -u tinko-wifi -f

# WiFi connection logs
cat /var/log/tinko_wifi.log
```

## Troubleshooting

### Port Already in Use

If you get "Address already in use":

```bash
# Find process using port 8000
sudo lsof -i :8000

# Kill the process
sudo kill -9 <PID>
```

### Permission Denied (GPIO)

If you get GPIO permission errors:

```bash
# Add user to gpio group
sudo usermod -a -G gpio pi

# Log out and back in for changes to take effect
```

### WebSocket Not Working

Ensure you're using `daphne` or `runserver` (not WSGI). WebSocket requires ASGI server.

## Next Steps

Now that Tinko is installed:

1. [First Steps](first-steps.md) - Create your admin account
2. [Hardware Setup](../developer/hardware/requirements.md) - Connect LEDs and sensors
3. [Dashboard](dashboard.md) - Learn the interface

## Hardware Configuration

Before using plugins that require hardware (all built-in plugins), connect the necessary components:

- **Activity Timer**: RGB LED (pins 17, 27, 22), Buzzer (pin 24)
- **Noise Monitor**: 2x RGB LEDs (pins 5, 6, 13 and 19, 26, 16), USB microphone
- **Routines**: Speaker or headphones (3.5mm jack), USB presenter (optional)
- **Touch Piano**: 6 touch sensors (pins 23, 24, 10, 9, 25, 11), speaker

See [Hardware Requirements](../developer/hardware/requirements.md) for detailed wiring instructions.
