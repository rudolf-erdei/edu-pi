# Known Issues

## Captive Portal — Root Cause Chain (analyzed 2026-09-13, FIXED 2026-09-13)

The captive portal was a daisy-chain of fragile steps with no failure
detection. Breakages looked like "setup mode runs on a fully-connected Pi"
or "captive page never shows". All items below are addressed in the current
code; verification status is listed on each.

### CRITICAL

1. **Boot gate was a single `ping 8.8.8.8` after a fixed `sleep 15`.**
   (`wifi-connect/startup_check.sh`) — FIXED.
   Now: `nm-online` warm-up + retried HTTPS probe (curl, max 6 tries), and a
   hard rule — **never tear down a live wlan0 connection** if the probe fails.
   A Pi already connected to a real network now always boots normally, even on
   networks that block ICMP or CDNs.
   Verified: dry-run + real boot check on the field Pi (online path → exit 0).

2. **Setup path had zero verification / zero retry.** — FIXED.
   `start_hotspot`, `start_dnsmasq`, `start_portal` each poll and verify their
   result; failures are logged loudly and returned as errors instead of
   silently continuing. Hotspot is confirmed via `nmcli` state + IP
   (10.42.0.1/24), dnsmasq confirmed via `ss` bind + DNS answer, portal
   confirmed via HTTP 200 on :80. Port 80 ownership is checked before launch.

3. **dnsmasq started before wlan0 had the hotspot IP.** — FIXED.
   The hotspot (and its address) are confirmed BEFORE dnsmasq starts; dnsmasq
   start is then verified bound to 10.42.0.1:53 and answering. Startup retries
   for up to 12s.

4. **Wildcard dnsmasq broke the Pi's own DNS once it ran** — MITIGATED
   (inherent to a single-radio design, now contained).
   The new boot gate (#1) means the wildcard dnsmasq only runs when the Pi is
   genuinely offline, and it is stopped again on handoff and on watchdog
   teardown. During genuine offline setup the Pi is offline anyway; its DNS
   recovers automatically when the hotspot is dropped. NM/systemd-resolved
   configs (`dns-upstream.conf`, `no-dns.conf`, `no-stub.conf`) are re-ensured
   at setup time, not only at install.

### HIGH

5. **Watchdog left dnsmasq running + Django took over a redirecting :80.** — FIXED.
   On timeout the teardown now kills the portal, stops dnsmasq, and drops the
   hotspot so NM can reconnect any saved network. Django then binds a clean :80.

6. **Web-initiated updates shipped wifi files to `/root/`, not the service
   user's home.** (`update-web.sh`) — FIXED.
   `WIFI_DIR` now resolves to `/home/${SERVICE_USER}` (daemon runs as root, so
   `$HOME` was `/root`).

7. **Web update could abort on `chown $USER:$USER`** (`$USER` empty under the
   root daemon, `set -e` kills the update) — FIXED.
   All ownership ops now use `${SERVICE_USER}`.

8. **`update-web.sh` never rewrote `tinko-wifi.service`** (drift vs `update.sh`)
   — FIXED. Added `ensure_wifi_service` + `ensure_nm_configs` to the web update
   path; all three unit writers now match (incl. `StartLimitBurst=3`).

### MEDIUM

9. **Port 53 conflict only mitigated at install, never at runtime.** — FIXED.
   `ensure_system_configs()` (startup) and `ensure_nm_configs()` (web update)
   re-check the NM dnsmasq / systemd-resolved overrides before the hotspot
   starts, and the dnsmasq bind itself is verified.

10. **WiFi worker deleted possibly-genuine saved profiles and restored blindly.**
    (`wifi_connect/wifi_worker.sh`) — FIXED.
    Pre-existing saved networks are kept; only auto-created/stale profiles are
    removed. Restore + dnsmasq-rebind steps check their results.

### LOW

11. **SSID scan in AP mode was a doomed blocking call.** (`wifi-connect/portal.py`)
    — FIXED. Scan is skipped (`_in_hotspot_mode()` guard); scan has a timeout.

12. **Boot ordering relied on `Before=` alone; no retry bound.** — MITIGATED.
    `StartLimitBurst=3` bounds retry spinning; a failed `tinko-wifi` does not
    block `tinko` (ordering only, not an After/Requires dependency) so the Pi
    can never be locked out of the dashboard. Residual reliance on `Before=`
    is documented in `wifi-connect/docs.md`.

### Additional hardening in this pass

- Portal HTTPS :443 redirect server wrapped in try/except (no crash if daphne
  holds the port); test port override `PORTAL_PORT`; extra captive-detection
  routes (`/ncsi.txt`, `/library/test/success.html`).
- `TINKO_DRY=1` mode on `startup_check.sh` for safe decision testing on a live
  system (changes nothing).

## Verification done (2026-09-13, field Pi)

- `bash -n` clean on all scripts.
- `startup_check.sh` real online-path run → "Internet verified", exit 0.
- `TINKO_DRY=1` → correct branch decision on a live Pi.
- `portal.py` on `PORTAL_PORT=8080` → `/` 200, `/generate_204` +
  `/hotspot-detect.html` 302 (captive detection works).
- Service unit + scripts deployed to `/home/tinko/` on the Pi.

## Still needs a field test (do on-site, not over SSH)

**The offline/setup branch** (hotspot + dnsmasq + portal, handoff, failure
revert) was NOT exercised on the live Pi — bringing the hotspot up would have
dropped the SSH link. To test:

1. Put the Pi where its configured WiFi is unavailable (or disable the saved
   network), reboot, then on another device:
2. Join `Tinko-Setup` (pass `tinko1234`) → expect captive popup / page at
   `http://10.42.0.1`.
3. Enter real WiFi credentials → expect wait page, hotspot vanishes, Django
   appears on `http://tinko.local`.
4. Wrong password → expect hotspot + portal to come back in ~20s.
5. Watch `sudo journalctl -u tinko-wifi -f` and `/var/log/tinko_wifi.log`.

## System Optimization (kept from earlier notes)

Optimize the system for longer SD card life:

```bash
sudo dphys-swapfile swapoff
sudo dphys-swapfile uninstall
sudo systemctl disable dphys-swapfile
```
