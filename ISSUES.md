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

12. **Boot ordering relied on `Before=` alone; no retry bound.** — MITIGATED,
    but the bound was inert until 2026-09-26 (see the verification pass below).
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

## Captive Portal — verification pass (2026-09-26, field Pi)

### Defect found and fixed: `StartLimitIntervalSec` was in the wrong section

Every boot logged:

```
tinko-wifi.service:13: Unknown key 'StartLimitIntervalSec' in section [Service], ignoring.
```

`StartLimitIntervalSec` is a `[Unit]` directive. systemd ignored it, so the
interval fell back to the 10 s default while `RestartSec=10` spaces restarts
10 s apart — the 3-restart burst could effectively never trip. The retry
bound credited to issue #12 above was therefore **not actually in force**.

Fixed by moving `StartLimitIntervalSec`/`StartLimitBurst` into `[Unit]`, for
both units, in all three unit writers (6 blocks):

| File | Units |
|------|-------|
| `install-raspberry-pi.sh` | `tinko-wifi.service`, `tinko.service` |
| `update.sh` | `tinko-wifi.service`, `tinko.service` |
| `update-web.sh` | `tinko-wifi.service`, `tinko.service` |

Docs brought in line: `docs/teacher/installation.md`, `wifi-connect/docs.md`,
`REQUIREMENTS.md`, and the captive-portal architecture memory.

### Defect found and fixed: `dig` absent, so dnsmasq verification was hollow

`dnsutils` was not installed, so `start_dnsmasq`'s `dig`/`nslookup` branch
never ran and the function fell through to the socket-bound-only branch —
dnsmasq was confirmed *listening* but never confirmed *answering*. Both `dig`
and `nslookup` ship in `dnsutils`; neither was present on the Pi.

Fixed: an `apt-get install -y dnsutils` guard added to
`install-raspberry-pi.sh`, `update.sh` and `update-web.sh`.

### Zero-risk verification (run remotely, wlan0 untouched)

Method: create a `dummy0` interface with `10.42.0.1/24`, run dnsmasq against
that interface only, run `portal.py` with `PORTAL_PORT=8080` and
`WIFI_WORKER_SCRIPT=/bin/true`. wlan0 was never touched, so the SSH session
survived the whole test.

Results:

- dnsmasq bound `10.42.0.1:53` and the wildcard answered `anything.example.com`,
  `clients3.google.com` and `captive.apple.com` → `10.42.0.1`. The real DNS
  redirect path is proven, not just the socket bind.
- All six captive-detection routes returned `302 -> http://10.42.0.1/`:
  `/generate_204`, `/gen_204`, `/hotspot-detect.html`, `/connecttest.txt`,
  `/ncsi.txt`, `/library/test/success.html`.
- `GET /` → 200 serving the "Connect Tinko to Wi-Fi" form.
- `POST /connect` → 400 for empty input, 400 for a 33-char SSID (length and
  control-character guards hold), 200 + wait page for valid credentials.
- Cleanup verified: `dummy0` deleted, wlan0 still connected, `dnsmasq`
  service still inactive/disabled, `tinko` service still active.

Side note, not a defect: `portal.py`'s HTTPS redirect server logged
`could not bind port 443: [Errno 13] Permission denied`. Expected — the test
ran the portal as `tinko`, not root. In real setup mode it runs as root and
daphne is held back by `Before=tinko.service`, so :443 is free.

### Not covered by the above (needs the radio)

The `Tinko-Setup` access point itself, NetworkManager shared-mode NAT, and the
credential handoff/revert in `wifi_worker.sh`. Those remain for the field test
below.

## Still needs a field test (do on-site, not over SSH)

**The offline/setup branch** (hotspot + dnsmasq + portal, handoff, failure
revert) was NOT exercised on the live Pi — bringing the hotspot up would have
dropped the SSH link. To test:

**Shortcut that avoids the blind window:** plug an Ethernet cable into the Pi.
`eth0` is free (`NO-CARRIER` on the field Pi 4), so SSH can ride the wire while
wlan0 runs the hotspot — the entire branch becomes testable remotely with no
risk of locking yourself out. Without a cable, do the run on-site.

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

### RESOLVED 2026-09-13 — check before running the above

Investigation on the field Pi showed this section is largely obsolete there:

- **dphys-swapfile is not installed** (`dpkg -l` → `un`) — the three commands
  above fail on this system. Raspberry Pi OS now uses `rpi-swap` / `zram`.
- **Swap runs entirely on `/dev/zram0`** (compressed, in-RAM) — `/proc/swaps`
  shows no disk-backed swap, and `/etc/rpi/swap.conf` has writeback fully
  commented out → **zero SD-card writes from swap already**. The intended
  longevity gain is already in effect.
- Cleanup done: deleted the orphan `/var/swap` (2 GiB sparse leftover from the
  2026-09-13 aborted `apt upgrade`, not in fstab, not active, ~0 allocated
  blocks). Nothing references it; zram swap untouched.

No action needed on the field Pi. Only if swap is later reconfigured to a
file-based mechanism (`Mechanism=file` in `/etc/rpi/swap.conf`) do the
SD-wear concerns return.

## Web Update — "Eroare de server" on Update Now (found and FIXED 2026-09-26)

### Symptom

Settings → Updates detected the available updates correctly, but clicking
**Update Now** showed the alert `Eroare de server` and nothing happened. No
update ran, no stage progressed.

### Root cause

`static/js/update.js` posted to the start endpoint **without a CSRF token**:

```js
const res = await fetch(`${API_BASE}/start/`, { method: 'POST' });
```

Django's `CsrfViewMiddleware` refused it, and daphne logged exactly that:

```
WARNING Forbidden (CSRF token missing.): /updates/start/
```

So the response was **403, not 500** — the server was behaving correctly the
whole time. Two things then conspired to hide it:

1. `update.js` did `await res.json().catch(() => ({}))`. A Django 403 body is
   HTML, so `json()` threw, the catch produced `{}`, `resJson.error` was
   `undefined`, and the alert fell through to the generic
   `gettext('Server error')` → "Eroare de server".
2. The test suite could not catch it: Django's test client defaults to
   `enforce_csrf_checks=False`, so the existing `POST /updates/start/` tests
   passed whether or not a real browser would be allowed through.

### Fix

- `static/js/update.js`: `startUpdate()` now sends
  `headers: { 'X-CSRFToken': csrfToken() }` with `credentials: 'same-origin'`,
  using the same `csrfToken()` cookie helper already used by
  `templates/home.html` for the shutdown button.
- The non-JSON fallback now shows `` `HTTP ${res.status}` `` instead of the
  misleading "Server error", so a future refusal is diagnosable on sight.

Only two `POST` fetches exist in the shipped UI (`update.js`, `home.html`) and
both now carry the header.

### Tests added (`tests/test_update_system.py`)

- `test_update_js_sends_csrf_token_to_start_endpoint` — static check of the
  shipped JavaScript. The defect was client-side, so pinning the header in the
  source is the only automated guard. This test fails on the pre-fix file.
- `test_start_update_rejects_post_without_csrf_token` — documents the 403.
- `test_start_update_accepts_post_with_valid_csrf_token` — cookie + header
  passes and the trigger file is written.

### Deployment note

`static/js/update.js` ships through `CompressedManifestStaticFilesStorage`, so
`collectstatic` must run for the browser to pick the new file up — the service's
`ExecStartPre` already does this on restart, and `update-web.sh` runs it as a
stage.

### Unrelated test-environment finding

`GET /` raises `ValueError: Missing staticfiles manifest entry for
'images/favicon.svg'` under pytest, because the manifest only exists after a
`collectstatic` on a deployed install. This means no test currently renders
`home.html` through the home view. Worth addressing separately — it is why the
dashboard's own JavaScript is untested.
