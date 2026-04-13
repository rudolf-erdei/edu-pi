# Known Issues

## dnsmasq service not found during update

**Severity:** Medium  
**Location:** `update.sh:294-296`  
**Symptom:** `Failed to restart dnsmasq.service: Unit dnsmasq.service not found.`

**Root cause:** The update script assumes `dnsmasq` is installed as a standalone systemd service and tries to restart it if it's not running. However, on the Raspberry Pi, NetworkManager runs its own dnsmasq instance as a child process for the hotspot — not as `dnsmasq.service`. The standalone `dnsmasq` package may not even be installed.

The `is-active` check at line 294 redirects stderr to `/dev/null` (`2>/dev/null`), silencing the "unit not found" error from detection, so the script falls through to `sudo systemctl restart dnsmasq` — which then fails loudly with `Unit dnsmasq.service not found`.

**Code path:**
```bash
# update.sh:292-304
if command -v systemctl &> /dev/null; then
    if ! systemctl is-active --quiet dnsmasq 2>/dev/null; then
        log_warning "dnsmasq is not running, restarting..."
        sudo systemctl restart dnsmasq   # <-- fails: unit not found
    fi
    if ! grep -q "bind-interfaces" /etc/dnsmasq.conf 2>/dev/null; then
        log_warning "dnsmasq config missing bind-interfaces, adding it..."
        echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf > /dev/null
        sudo systemctl restart dnsmasq   # <-- also fails
    fi
fi
```

**Also affected:** `wifi-connect/startup_check.sh:33` and `wifi-connect/wifi_worker.sh:48` call `systemctl restart dnsmasq` with the same assumption.