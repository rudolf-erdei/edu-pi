# Known Issues

Open items only. Closed work is compressed to one line each at the bottom —
the reasoning lives in the commit that fixed it, not here.

## Open — the web update could never pull (FIXED in repo, not yet on the Pi)

Found 2026-09-26 by reading a real web-update log on the field Pi. The
**root cause of "the update button does nothing"**, and it was not the CSRF
header — that was a separate, real bug hiding this one.

`update-web.sh` ran:

```bash
run_as_user "cd '$INSTALL_DIR' && timeout 60 GIT_TERMINAL_PROMPT=0 git pull"
```

`timeout` does not accept a `VAR=value` prefix the way a shell does. It tries
to exec a program literally named `GIT_TERMINAL_PROMPT=0`:

```
timeout: failed to run command 'GIT_TERMINAL_PROMPT=0': No such file or directory
```

The `if` failed, and the else branch reported it as *"Failed to pull (no
internet or network error)"* — so the update continued cheerfully on the old
version and marked itself complete. Every web update ever run has been a no-op
on the git side. `git fetch` reaches GitHub fine (`exit=0`), so the network was
never the problem.

**Fixed** by moving the assignment in front of `timeout`:

```bash
run_as_user "cd '$INSTALL_DIR' && GIT_TERMINAL_PROMPT=0 timeout 60 git pull"
```

Verified both halves: the broken ordering reproduces the exact error on a
dev machine, and the corrected ordering returns `exit=0` on the Pi. `update.sh`
was already correct (`export GIT_TERMINAL_PROMPT=0`, then a plain
`timeout 60 git pull`) — which is why CLI updates always worked and the web
path never did.

The misleading "no internet" message is itself part of the bug: it turned a
loud, diagnosable failure into a silent one. Worth separating the exit-reason
in the message when this is next touched.

## Open — the live database is replaced on every successful update

`db.sqlite3` is tracked in git *and* written at runtime, so it is always
"modified" when an update runs. `pull_latest` in both `update.sh` and
`update-web.sh` stashes local changes, and **pops the stash only when the pull
failed**. On success the stash is left behind and never restored — so the
working tree keeps the *committed* database, and any data written since the
last commit is reachable only from a stash the app knows nothing about.

Verified on the field Pi:

- `db.sqlite3` is tracked (`git ls-files` matches).
- The mechanism is confirmed in the log: this run stashed, failed to pull, and
  popped — the stash contained `db.sqlite3` and the `.mo` files.
- **Impact right now is nil**: a table-by-table row count comparison of the live
  database against `HEAD:db.sqlite3` differs in exactly two places —
  `sqlite_sequence` (autoincrement counters) and
  `update_system_updatestatus` (the record this run created, 1 vs 0). Every
  content table matches.

So the risk is **latent, not active**: it bites once a teacher accumulates real
data (noise readings, new routines, changed settings) and an update then runs.
Options, none chosen yet:

- Stop tracking `db.sqlite3` and ship initial data as a fixture/migration.
- Back the database up before stashing, and restore it after the pull.
- Pop the stash on success too (careful: after a pull the stash may conflict).

## Open — 67 accumulated stashes on the field Pi

Every successful update leaves one stash behind (same root cause as above).
The Pi currently holds **67**, each a snapshot of `.mo` files and sometimes the
database, all still reachable from `HEAD` and never pruned. This is dead weight
in `.git` that grows without bound on an SD card, and it makes the stash list
useless as signal. Needs a cleanup pass plus a decision on the behaviour above.

## Open — the Pi is 2 commits behind `master`

The field Pi tracks `master`; work is committed to `development` and reaches
`master` only through a pull request. Today's commit `bc2fd47` is already on
`origin/master` (via PR #20), but the Pi has not taken it — the pull failed
for the reason above.

One CLI `bash update.sh` run is enough to close this: the pull works on that
path, and `bc2fd47` contains the guard, `settings_test.py`, `test_home_view.py`
and the docs. Nothing in it needs a second run to "apply" — the guard only
takes effect the next time a pull changes `update.sh` itself.

## Open — captive portal offline/setup branch has never run on hardware

The hotspot itself, NetworkManager shared-mode NAT, and the credential
handoff/revert in `wifi_worker.sh` have never been exercised on the Pi.
Bringing the hotspot up drops the only SSH link, so the branch must be tested
where a failure cannot strand the device.

**Decision 2026-09-26: on-site only, for now.** No Ethernet cable is
available. Two remote alternatives were considered and declined:

- **Ethernet shortcut.** Plug a cable into the Pi. `eth0` is free
  (`NO-CARRIER` on the field Pi 4), so SSH rides the wire while wlan0 runs the
  hotspot — the whole branch becomes testable remotely with no risk. Still the
  best option the moment a cable is at hand.
- **Virtual radio (`mac80211_hwsim`).** The module is present on the field Pi
  (`/lib/modules/6.18.39+rpt-rpi-v8/.../mac80211_hwsim.ko.xz`, not loaded), so
  two fake wifi radios could be created — build the AP on one, associate the
  other as a real client — without touching wlan0. It would genuinely cover AP
  creation, NM assigning 10.42.0.1, shared-mode nftables NAT, and a real client
  association. Declined for now because it cannot run the shipped scripts
  verbatim: `wlan0` is hardcoded throughout `startup_check.sh`, `portal.py` and
  `/etc/dnsmasq.conf`, with no interface override.

Run it on-site:

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

## Known-inherent — single-radio wildcard DNS

`address=/#/10.42.0.1` breaks the Pi's own DNS while dnsmasq runs. Inherent to
a one-radio design; it cannot be removed, only contained. Contained by the
boot gate (the wildcard dnsmasq only starts when the Pi is genuinely offline)
and by stopping dnsmasq on handoff and on watchdog teardown. No action.

## Resolved — history, do not re-investigate

- **Web update "Eroare de server"** (2026-09-26) — `update.js` POSTed without
  an `X-CSRFToken` header, so Django answered 403 with an HTML body; the
  `res.json().catch(() => ({}))` fallback produced the generic "Server error"
  alert and hid the real cause. The server was correct throughout. Fixed, with
  a static check of the shipped JS plus 403/200 CSRF contract tests.
  **Confirmed working on the field Pi 2026-09-26**: the button ran a full
  update end-to-end, reached "Update completed successfully", and the service
  restarted cleanly.
- **Field Pi ran pre-fix systemd units and lacked `dnsutils`** (2026-09-26) —
  `StartLimitIntervalSec`/`StartLimitBurst` sat in `[Service]`, where systemd
  logs `Unknown key ... ignoring` and silently falls back to the 10 s default.
  Fixed by moving them into `[Unit]` across all three unit writers.
  **Deployed and verified on the field Pi 2026-09-26**:
  `tinko-wifi` → `StartLimitIntervalUSec=2min`, burst 3; `tinko` → `1min`,
  burst 5; both `dig` and `nslookup` present.
- **`update.sh` could not ship its own changes in one run** (2026-09-26) — bash
  reads a running script from its open file descriptor, and `git pull` replaces
  the file by atomic rename, so the in-flight run kept executing the pre-pull
  function bodies. Diagnosed from the split: `update.js` (data, read later by
  `collectstatic`) deployed while the unit blocks and `dnsutils` guard (code,
  already parsed) did not. Fixed by `reexec_if_self_changed()` in both
  `update.sh` and `update-web.sh` — records its own digest at startup and
  re-execs once after the pull if it moved, guarded by `TINKO_UPDATE_REEXEC=1`.
  `exec` skips the `EXIT` trap (no bogus emergency restart) and keeps the PID
  the daemon waits on. Mechanism verified in isolation: new code loads, the
  loop stops, arguments survive, and the `EXIT` trap fires exactly once.
  Cannot bootstrap itself — the run that installs it is still the old script —
  so the installing commit needs two runs unless the pull is done by hand
  first.
- **Captive portal root-cause chain, 12 issues** (2026-09-13) — boot gate was
  a single `ping` after a fixed sleep; the setup path had no verification or
  retry; dnsmasq started before the hotspot IP existed; the watchdog left
  dnsmasq running; web update shipped wifi files to `/root`; `chown $USER:$USER`
  aborted the update; `update-web.sh` never rewrote `tinko-wifi.service`; port
  53 conflict mitigated only at install; the wifi worker deleted genuine saved
  profiles; the SSID scan in AP mode was a doomed blocking call; boot ordering
  had no retry bound. All fixed.
- **SD-card swap optimization** (2026-09-13) — obsolete on the field Pi.
  `dphys-swapfile` is not installed (`dpkg -l` → `un`), swap runs entirely on
  `/dev/zram0`, and `/etc/rpi/swap.conf` has writeback commented out, so there
  are already zero SD-card writes from swap. Revisit only if swap is later
  reconfigured to `Mechanism=file`.
- **`home.html` unrenderable under pytest** (2026-09-26) — production resolves
  `{% static %}` through the `collectstatic` manifest, which does not exist in
  a test run, so `GET /` raised `Missing staticfiles manifest entry for
  'images/favicon.svg'` before any assertion. The dashboard and its inline
  JavaScript therefore had no coverage. Fixed by `config/settings_test.py`
  (manifest-free `StaticFilesStorage`, production otherwise unchanged), with
  tests both pinning that and guarding production's manifest backend.
