# Known Issues

## ~~dnsmasq service not found during update~~ [FIXED]

**Severity:** Medium (was)  
**Location:** `update.sh:292-304`  
**Symptom:** `Failed to restart dnsmasq.service: Unit dnsmasq.service not found.`

**Root cause:** The update script assumed `dnsmasq` was already installed as a standalone systemd service. When the unit didn't exist, it tried to restart it anyway, causing the error.

**Fix:** `update.sh` now checks whether the `dnsmasq.service` unit exists. If not, it installs dnsmasq via `apt-get`, backs up the original config, and writes the captive portal configuration — matching the install script's behavior. If the service already exists, it verifies it's running and that the config includes `bind-interfaces`.

**Still affected:** `wifi-connect/startup_check.sh:33` and `wifi-connect/wifi_worker.sh:48` call `systemctl restart dnsmasq` with the same assumption — these should also guard against a missing service unit.