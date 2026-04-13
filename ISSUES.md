# Tinko Captive Portal — Known Issues

Issues discovered during logic analysis of the captive portal system (2026-04-13).

---

## CRITICAL — Will Cause Failure

### 1. dnsmasq likely fails to start (port 53 conflict with systemd-resolved) — FIXED

**File:** `install-raspberry-pi.sh` (line 321-328), `/etc/dnsmasq.conf`

The install script configures dnsmasq with:
```
address=/#/10.42.0.1
interface=wlan0
```

On Raspberry Pi OS Bookworm, `systemd-resolved` is enabled by default and listens on `127.0.0.53:53`. Without `bind-interfaces`, dnsmasq tries to bind to `0.0.0.0:53` first (before filtering by interface), which fails because port 53 is already occupied.

**Impact:** dnsmasq fails silently on startup. DNS queries from connected phones are not redirected to the Pi. The automatic captive portal popup never triggers. The teacher would have to manually type `http://10.42.0.1` in their browser.

**Fix:** Added `bind-interfaces` to the dnsmasq config so dnsmasq only binds to the IP of `wlan0` (`10.42.0.1:53`):
```
address=/#/10.42.0.1
interface=wlan0
bind-interfaces
```

**Verification on Pi:**
```bash
sudo systemctl status dnsmasq
sudo ss -tlnp | grep :53
```

---

### 2. No dnsmasq restart after hotspot creation — FIXED

**File:** `wifi-connect/startup_check.sh`

After `startup_check.sh` creates/activates the hotspot (which assigns `10.42.0.1` to `wlan0`), dnsmasq is not restarted. If dnsmasq started at boot before the hotspot existed (before `wlan0` had IP `10.42.0.1`), it may not be listening on that interface's IP address.

**Impact:** DNS redirection doesn't work even if dnsmasq is running, because it wasn't bound to the hotspot interface IP.

**Fix:** Added `sudo systemctl restart dnsmasq` in `startup_check.sh` after the hotspot is up and before Flask starts.

**Verification on Pi:**
```bash
# Start hotspot manually, then:
sudo systemctl restart dnsmasq
sudo systemctl status dnsmasq
# From a connected phone: nslookup google.com should return 10.42.0.1
```

---

### 3. WiFi scan returns empty during AP mode — FIXED

**File:** `wifi-connect/portal.py` (line 30)

`get_available_ssids()` runs `nmcli -t -f SSID dev wifi` while the Pi's WiFi radio is in AP (hotspot) mode. Most Raspberry Pi WiFi chips (brcmfmac) **cannot scan for networks while in AP mode** — scanning requires the radio to switch channels, which disrupts the hotspot.

**Impact:** The SSID dropdown in the portal form will be empty or show stale results. The teacher must type the network name manually.

**Fix:** Added a visible note to the HTML form: "Type your Wi-Fi name below. Scanning is unavailable in hotspot mode." The datalist is only rendered if scan results are available.

**Verification on Pi:**
```bash
# While hotspot is active:
nmcli -t -f SSID dev wifi
# Likely returns empty or very few results
```

---

## HIGH — Significant Usability Issues

### 4. Django startup delay after WiFi connect — FIXED

**File:** `wifi-connect/wifi_worker.sh` (line 28), `tinko.service`

When `tinko.service` had `ExecStartPre` commands that ran `migrate` and `collectstatic` **every time the service starts**. On a Pi, this can take 10-30+ seconds.

**Impact:** After the hotspot disappears and the Pi connects to the school WiFi, there's a gap where the Pi is on the network but nothing is serving on port 80. The teacher might think the setup failed.

**Fix:** Removed `ExecStartPre` from `tinko.service` and `edu-pi.service`. Migrations and collectstatic are now only run during install and update scripts.

---

### 5. update.sh doesn't ensure dnsmasq — FIXED

**File:** `update.sh`

The `update.sh` script copies wifi-connect files and recreates the `tinko-wifi.service`, but **never checks if dnsmasq is installed or running**. If dnsmasq was accidentally removed, stopped, or failed, an update won't fix it.

**Impact:** A system update could leave the captive portal broken if dnsmasq got into a bad state.

**Fix:** Added dnsmasq health check to `update_wifi_connect()`:
```bash
if ! systemctl is-active --quiet dnsmasq; then
    log_warning "dnsmasq is not running, restarting..."
    sudo systemctl restart dnsmasq
fi
```
Also checks and adds `bind-interfaces` to dnsmasq config if missing.

---

## MEDIUM — Edge Cases

### 6. Service ordering race condition — FIXED

**Files:** `wifi-connect/wifi_worker.sh` (line 28), `tinko-wifi.service`

`tinko-wifi.service` has `Before=tinko.service`, meaning systemd won't start `tinko.service` until `tinko-wifi.service` completes. But `wifi_worker.sh` explicitly called `systemctl start tinko`. When Flask is then killed, `tinko-wifi.service` exits, and systemd also tries to start `tinko.service`. Two concurrent start attempts occur.

**Impact:** systemd handles this gracefully (idempotent), but the double-start attempt is untidy and could cause confusing log messages.

**Fix:** In `wifi_worker.sh`, removed the explicit `systemctl start tinko` call. Django now starts via systemd's natural ordering dependency (`Before=tinko.service`).

---

### 7. `pkill -f portal.py` is broad — FIXED

**File:** `wifi-connect/wifi_worker.sh` (line 23)

`pkill -f portal.py` kills ANY process with "portal.py" in its command line, not just the specific Flask process.

**Impact:** On a dedicated Pi this is fine, but could kill unrelated processes if other "portal.py" scripts exist.

**Fix:** `startup_check.sh` now writes the Flask PID to `/run/tinko-portal.pid`. `wifi_worker.sh` reads and kills the specific PID, with pkill as a fallback if the PID file is missing.

---

### 8. HTTPS captive portal checks fail silently — FIXED

**File:** `wifi-connect/portal.py`

Some newer Android devices use HTTPS for connectivity checks (e.g., `https://connectivitycheck.gstatic.com/generate_204`). Flask has no TLS, so these requests fail with a connection error.

**Impact:** On some Android phones, the captive portal notification might not appear automatically.

**Fix:** Added a lightweight HTTPS redirect server on port 443 that uses a self-signed TLS certificate (generated during install). Android's connectivity check does not enforce certificate validation, so a self-signed cert is sufficient. The HTTPS server redirects all requests to `http://10.42.0.1`.

---

## LOW — Minor Issues

### 9. Hardcoded hotspot credentials

**Files:** `wifi-connect/startup_check.sh` (line 23)

SSID: `Tinko-Setup`, Password: `tinko1234` are hardcoded. Anyone who knows these can connect to the setup hotspot.

**Impact:** Low risk — the hotspot is only active when the Pi has no internet, and the portal only exposes a WiFi configuration form. No sensitive data is exposed.

**Status:** Accepted — risk is low for the use case.

---

### 10. Loose grep pattern for hotspot profile — FIXED

**File:** `wifi-connect/startup_check.sh` (line 21)

`nmcli connection show | grep -q "Tinko-Setup"` matches any line containing "Tinko-Setup", which could match connections with similar names.

**Fix:** Tightened the grep pattern to `grep -q "^\s*Tinko-Setup\b"` to match only at the start of a line with a word boundary.

---

## Pre-Deployment Checklist

Before testing on a real Pi, verify:

```bash
# 1. Is dnsmasq running?
sudo systemctl status dnsmasq

# 2. Is anything on port 53? (conflict check)
sudo ss -tlnp | grep :53

# 3. Is the dnsmasq config correct? (should include bind-interfaces)
cat /etc/dnsmasq.conf | grep -A3 "Tinko"

# 4. Is the wifi service enabled?
sudo systemctl is-enabled tinko-wifi.service

# 5. Does tinko.service NOT have ExecStartPre?
grep "ExecStartPre" /etc/systemd/system/tinko.service
# Should return nothing

# 6. Does the TLS cert exist?
ls -la /etc/tinko-portal/cert.pem /etc/tinko-portal/key.pem

# 7. Can dnsmasq restart while hotspot is active?
sudo nmcli dev wifi hotspot ifname wlan0 ssid "test" password "test1234" con-name "test"
sudo systemctl restart dnsmasq
sudo systemctl status dnsmasq
sudo nmcli connection delete "test"
```