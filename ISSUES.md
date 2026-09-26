# Known Issues

Open items only. Closed work is compressed to one line each at the bottom —
the reasoning lives in the commit that fixed it, not here.

## Open — field Pi is behind the repo

Three fixes are in the repo but not in force on the hardware. All were found
2026-09-26; none has been deployed yet.

1. **`StartLimitIntervalSec` / `StartLimitBurst` still sit in `[Service]`.**
   systemd logs `Unknown key ... ignoring` on every boot, so the interval
   falls back to the 10 s default while `RestartSec=10` spaces restarts 10 s
   apart — the burst bound can never trip. Confirmed on the Pi:
   `systemctl show tinko-wifi -p StartLimitIntervalUSec` → `10s`, not `120s`.
2. **`dnsutils` is not installed.** No `dig`/`nslookup`, so
   `start_dnsmasq`'s verification falls through to the socket-bind branch:
   dnsmasq is confirmed *listening* but never confirmed *answering*.
3. **The self-exec guard has never run.** Added to `update.sh` and
   `update-web.sh` 2026-09-26 (see below); the next Pi update is its first
   real exercise.

**Deploying item 1 and 2 was itself the bug** — see the next section.

## Open — `update.sh` could not ship its own changes in one run

Found 2026-09-26 while investigating why the update above appeared to succeed
but changed nothing.

bash reads a running script from its open file descriptor. `git pull` replaces
`update.sh` by atomic rename (new inode), so the in-flight run keeps executing
the **pre-pull** function bodies. Everything the script does *to files*
deployed normally; nothing it does *as its own code* did.

That is exactly the observed split:

| Change | Kind | Deployed? |
|--------|------|-----------|
| `static/js/update.js` CSRF header | data, read later by `collectstatic` | yes |
| systemd unit blocks (6) | code, already parsed | no |
| `dnsutils` apt guard | code, already parsed | no |

**Fixed in repo** (not yet verified on hardware): `reexec_if_self_changed()` in
both `update.sh` and `update-web.sh`. The script records its own digest at
startup and, after the pull, re-execs once if the digest moved.
`TINKO_UPDATE_REEXEC=1` stops the second run from looping. `exec` replaces the
process image, so the `EXIT` trap (the emergency service restart) does not
fire and the daemon still waits on the same PID.

Verify on the next Pi run: the units on disk must move `StartLimit*` into
`[Unit]`, `dig` must appear, and the log must show
`Re-executing with the new version`.

## Open — captive portal offline/setup branch has never run on hardware

The hotspot itself, NetworkManager shared-mode NAT, and the credential
handoff/revert in `wifi_worker.sh` have never been exercised on the Pi.
Bringing the hotspot up drops the only SSH link, so the branch must be tested
where a failure cannot strand the device.

**Shortcut that removes the risk:** plug an Ethernet cable into the Pi. `eth0`
is free (`NO-CARRIER` on the field Pi 4), so SSH rides the wire while wlan0
runs the hotspot — the whole branch becomes testable remotely.

Without a cable, run it on-site:

1. Put the Pi where its configured WiFi is unavailable (or disable the saved
   network), reboot, then on another device:
2. Join `Tinko-Setup` (pass `tinko1234`) → expect captive popup / page at
   `http://10.42.0.1`.
3. Enter real WiFi credentials → expect wait page, hotspot vanishes, Django
   appears on `http://tinko.local`.
4. Wrong password → expect hotspot + portal to come back in ~20s.
5. Watch `sudo journalctl -u tinko-wifi -f` and `/var/log/tinko_wifi.log`.

Already proven by the zero-risk `dummy0` test (method: see the
`captive-portal-test-method` memory): wildcard DNS answers, all six
captive-detection routes return `302 -> http://10.42.0.1/`, the form serves,
and the SSID/password validators reject bad input.

## Open — Update Now has not been clicked since the CSRF fix

`static/js/update.js` is confirmed deployed and served on the Pi. Two updates
were pending at the time. Nobody has run the button end-to-end since.

## Known-inherent — single-radio wildcard DNS

`address=/#/10.42.0.1` breaks the Pi's own DNS while dnsmasq runs. Inherent to
a one-radio design; it cannot be removed, only contained. Contained by the
boot gate (the wildcard dnsmasq only starts when the Pi is genuinely offline)
and by stopping dnsmasq on handoff and on watchdog teardown. No action.

## Resolved — history, do not re-investigate

- **Captive portal root-cause chain, 12 issues** (2026-09-13) — boot gate was
  a single `ping` after a fixed sleep; the setup path had no verification or
  retry; dnsmasq started before the hotspot IP existed; the watchdog left
  dnsmasq running; web update shipped wifi files to `/root`; `chown $USER:$USER`
  aborted the update; `update-web.sh` never rewrote `tinko-wifi.service`; port
  53 conflict mitigated only at install; the wifi worker deleted genuine saved
  profiles; the SSID scan in AP mode was a doomed blocking call; boot ordering
  had no retry bound. All fixed.
- **`StartLimitIntervalSec` in the wrong section**, 6 unit blocks across 3
  writers (2026-09-26). Fixed in repo; deployment still open above.
- **`dig` absent** (2026-09-26). Fixed in repo; deployment still open above.
- **SD-card swap optimization** (2026-09-13) — obsolete on the field Pi.
  `dphys-swapfile` is not installed (`dpkg -l` → `un`), swap runs entirely on
  `/dev/zram0`, and `/etc/rpi/swap.conf` has writeback commented out, so there
  are already zero SD-card writes from swap. Revisit only if swap is later
  reconfigured to `Mechanism=file`.
- **Web update "Eroare de server"** (2026-09-26) — `update.js` POSTed without
  an `X-CSRFToken` header, so Django answered 403 with an HTML body; the
  `res.json().catch(() => ({}))` fallback then produced the generic "Server
  error" alert and hid the real cause. The server was correct throughout. The
  suite could not catch it because Django's test client defaults to
  `enforce_csrf_checks=False`. Fixed, with a static check of the shipped JS
  plus 403/200 CSRF contract tests.
- **`home.html` unrenderable under pytest** (2026-09-26) — production resolves
  `{% static %}` through the `collectstatic` manifest, which does not exist in
  a test run, so `GET /` raised `Missing staticfiles manifest entry for
  'images/favicon.svg'` before any assertion. The dashboard and its inline
  JavaScript therefore had no coverage. Fixed by `config/settings_test.py`
  (manifest-free `StaticFilesStorage`, production otherwise unchanged), with
  tests both pinning that and guarding production's manifest backend.
