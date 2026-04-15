## 1. Install dnsmasq, a lightweight DNS server:

```bash
sudo apt update
sudo apt install dnsmasq nftables iptables
```

**Important:** Install `nftables` and `iptables` too. On Debian 12 Bookworm (newer Raspberry Pi OS), iptables has been phased out in favor of nftables. NetworkManager's hotspot shared mode uses nftables for NAT masquerading. The `iptables` package installs the iptables-nft wrapper that translates legacy iptables calls to nftables.

**Critical:** Disable dnsmasq auto-start. It must only run during hotspot mode (managed by startup_check.sh and wifi_worker.sh). If dnsmasq starts on boot with its wildcard DNS redirect active, it will break internet DNS resolution for the Pi:

```bash
sudo systemctl stop dnsmasq
sudo systemctl disable dnsmasq
```

Edit the configuration file to redirect all web traffic to the Pi's hotspot IP address (NetworkManager defaults to 10.42.0.1 for hotspots):

```bash
sudo nano /etc/dnsmasq.conf
```

Add these lines to the bottom of the file:

```ini
# Tinko Captive Portal Configuration
address=/#/10.42.0.1
interface=wlan0
bind-interfaces
except-interface=lo
```

**Critical:** `except-interface=lo` prevents dnsmasq from listening on the loopback interface. Without it, if the Pi's `/etc/resolv.conf` points to `127.0.0.1`, all DNS queries from the Pi itself would be intercepted by dnsmasq's wildcard redirect, breaking internet access.

**Also critical:** Ensure NetworkManager uses real upstream DNS (not the local dnsmasq):

```bash
sudo mkdir -p /etc/NetworkManager/conf.d/
sudo tee /etc/NetworkManager/conf.d/dns-upstream.conf > /dev/null << 'EOF'
[global-dns-domain-*]
servers=8.8.8.8,8.8.4.4
EOF
```

**Important:** You must also disable DNS on NetworkManager's internal dnsmasq to prevent a port 53 conflict. NM runs its own dnsmasq for shared connections, which also binds to port 53 on the hotspot IP. Create this config file:

```bash
sudo mkdir -p /etc/NetworkManager/dnsmasq-shared.d/
echo "port=0" | sudo tee /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf
```

This tells NM's dnsmasq to only handle DHCP (not DNS), leaving port 53 free for the standalone dnsmasq with the wildcard redirect.

**Also important:** Disable NetworkManager's periodic connectivity checks to prevent hotspot disconnects:

```bash
sudo mkdir -p /etc/NetworkManager/conf.d/
sudo tee /etc/NetworkManager/conf.d/no-connectivity-check.conf > /dev/null << EOF
[connectivity]
interval=0
EOF
```

Restart the service (only needed when testing the hotspot; dnsmasq is normally managed by startup_check.sh):

```bash
sudo systemctl start dnsmasq
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

**Note:** The service type is `oneshot` (not `simple`). This is critical because it ensures systemd waits for `startup_check.sh` to finish before starting `tinko.service`. When there's internet, the script exits immediately and Django starts. When there's no internet, the script blocks (running the captive portal) until WiFi is configured, preventing a port 80 conflict between Flask and Django.

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
sudo nano /etc/systemd/system/tinko.service
```

Modify the [Unit] section:

```ini
[Unit]
Description=Tinko Educational Platform
Wants=network-online.target
After=network-online.target
```

Save and reload

```bash
sudo systemctl daemon-reload
sudo systemctl restart tinko.service
```

## Recap

what happens now when a teacher plugs it in:

- Power On: The Pi boots up.
- The Wait: The system waits for the network to initialize (up to 120 seconds for `network-online.target`).
- The Check (startup_check.sh): It pings the internet.
    - If online: It exits immediately, systemd starts `tinko.service`, and the Django app boots safely. The teacher goes to http://tinko.local.
    - If offline: It spins up the "Tinko-Setup" hotspot and the Flask portal. **Systemd waits for this service to finish** (Type=oneshot) before starting Django, preventing a port 80 conflict.
    - The Handoff (wifi_worker.sh): The teacher enters the credentials. The worker tears down the hotspot, connects to the school WiFi, and kills the Flask portal. The service exits, and Django starts via systemd ordering.

## Hotspot Credentials

- **SSID:** `Tinko-Setup`
- **Password:** `tinko1234`

These credentials are set in `startup_check.sh` when the hotspot is first created.

## Captive Portal Detection

The Flask portal handles OS-level captive portal detection URLs by redirecting them to the setup page:

- Android: `/generate_204` and `/gen_204` return 302 to `http://10.42.0.1/`
- Apple: `/hotspot-detect.html` returns 302 to `http://10.42.0.1/`
- Windows: `/connecttest.txt` returns 302 to `http://10.42.0.1/`

This ensures the "Sign in to Wi-Fi" notification appears on all major platforms.

## Key Configuration Files

- `/etc/dnsmasq.conf` — Standalone dnsmasq with wildcard DNS redirect (`address=/#/10.42.0.1`). **Must be disabled at boot** — only started by startup_check.sh in hotspot mode.
- `/etc/NetworkManager/dnsmasq-shared.d/no-dns.conf` — Disables DNS in NM's internal dnsmasq (`port=0`)
- `/etc/NetworkManager/conf.d/no-connectivity-check.conf` — Disables NM connectivity checks (`interval=0`)
- `/etc/tinko-portal/cert.pem` and `key.pem` — Self-signed TLS certificate for HTTPS captive portal detection

## dnsmasq Lifecycle

dnsmasq must **only** run when the hotspot is active. Its wildcard DNS (`address=/#/10.42.0.1`) resolves all domains to the hotspot IP, which breaks internet DNS if left running when the Pi is connected to real WiFi.

- **Disabled at boot** — `systemctl disable dnsmasq` prevents it from starting automatically
- **Started by startup_check.sh** — Only when no internet is detected (hotspot mode)
- **Stopped by wifi_worker.sh** — After successfully connecting to WiFi