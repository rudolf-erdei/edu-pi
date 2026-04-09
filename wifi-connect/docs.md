## 1. Install dnsmasq, a lightweight DNS server:

```bash
sudo apt update
sudo apt install dnsmasq
```

Edit the configuration file to redirect all web traffic to the Pi's hotspot IP address (NetworkManager defaults to 10.42.0.1 for hotspots):
Bash

```bash
sudo nano /etc/dnsmasq.conf
```
Add these lines to the bottom of the file:
Plaintext

```ini
address=/#/10.42.0.1
interface=wlan0
```

Restart the service: 

```bash
sudo systemctl restart dnsmasq
```

Install Flask

```bash
pip install Flask
```

## Make the tinko-wifi.service

Create the following file using SUDO, on the Pi:

```bash
sudo nano /etc/systemd/system/tinko-wifi.service
```

With the following content (replace `/home/YOURUSER` with your actual home directory):

```ini
[Unit]
Description=Tinko Wi-Fi Captive Portal Check
After=NetworkManager.service

[Service]
Type=simple
ExecStart=/bin/bash /home/YOURUSER/startup_check.sh
User=root
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

After that run the following commands sequentially:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tinko-wifi.service
sudo systemctl start tinko-wifi.service
```

Whenever you want to see what is happening, or if the hotspot doesn't appear, run this command:

```bash
sudo journalctl -u tinko-wifi.service -f
```

## Modify Django Service:

```bash
sudo nano /etc/systemd/system/django.service
```

Modify the [Unit] section:

```ini
[Unit]
Description=My Django Web Application
Wants=network-online.target
After=network-online.target
```

Save and reload

```bash
sudo systemctl daemon-reload
sudo systemctl restart django.service
```

## Recap

what happens now when a teacher plugs it in:

- Power On: The Pi boots up.
- The Wait: The system waits for the network to initialize.
- The Check (startup_check.sh): It pings the internet.
    - If online: It skips the portal, your Django app boots safely, and the teacher goes to http://tinko.local.
    - If offline: It spins up the "Tinko-Setup" hotspot and the lightweight Flask portal.
    - The Handoff (wifi_worker.sh): The teacher enters the credentials. The worker tests them in the background. If they fail, it reverts to the hotspot so the teacher isn't locked out. If they succeed, it kills the Flask portal, connects to the school router, starts Django, and your app takes over.

## Hotspot Credentials

- **SSID:** `Tinko-Setup`
- **Password:** `tinko1234`

These credentials are set in `startup_check.sh` when the hotspot is first created.