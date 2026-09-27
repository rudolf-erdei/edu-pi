# Update System

How Tinko updates itself: what each path does, what it writes outside the
repository, which files are protected across a pull, and why an update
occasionally needs a second run.

For symptoms and fixes, see
[Troubleshooting](troubleshooting.md#an-update-reported-success-but-a-change-did-not-take-effect).

## The three update paths

| Path | Entry point | Runs as | Notes |
|------|-------------|---------|-------|
| Install | `install-raspberry-pi.sh` | root | First install. Also sets up the update infrastructure, so a fresh Pi can update itself from the dashboard immediately. |
| CLI | `sudo bash update.sh` | root | Progress goes to the terminal. |
| Web | Settings → Updates → **Update Now** | root, via `tinko-update.service` | Trigger file → daemon → `update-web.sh`; progress streams into the dashboard. |

All three end the same way: new code on disk, `uv sync`, migrations, static
files, translations compiled, tinko.service restarted.

**The shared piece is `scripts/update_infra.sh`.** It defines
`setup_update_infrastructure()`, `install_power_helper()`,
`install_persistent_journal()` and `install_timesync_config()` /
`ensure_clock_is_set()`, and all three paths `source` it. It is sourced for its
functions only — sourcing has no side effects, and the caller must have defined
the `log_*` helpers first.

`update-web.sh` deliberately does **not** call `setup_update_infrastructure()`: it
restarts `tinko-update.service`, and that service is what is running the script.
Each helper therefore needs its own call there, which is why the helper list above
appears twice in the web path's `main()`.

## What install and update write outside the repository

| Path | Written by | Purpose |
|------|-----------|---------|
| `/etc/systemd/system/tinko.service` | all three | The Django/daphne service, including its capability settings (below). |
| `/etc/systemd/system/tinko-update.service` | `setup_update_infrastructure()` | The root update daemon that the dashboard talks to. |
| `/etc/sudoers.d/tinko-update` | `setup_update_infrastructure()` | Lets the app stop and start *its own* service, and repair `/run/tinko-update`. |
| `/usr/local/sbin/tinko-poweroff` | `install_power_helper()` | The dashboard Power button's halt chain — root-owned, mode 0755. |
| `/etc/sudoers.d/tinko-poweroff` | `install_power_helper()` | Grants the service user that helper, and nothing else. |
| `/etc/systemd/journald.conf.d/tinko.conf` | `install_persistent_journal()` | Keeps the journal across reboots (`Storage=persistent`, `SystemMaxUse=32M`, `RuntimeMaxUse=32M`). Overrides the vendor's `Storage=volatile` — the name must sort after `40-rpi-volatile-storage.conf`. |
| `/var/log/journal/` | `install_persistent_journal()` | Where the journal then lives — systemd's own directory, prepared with `systemd-tmpfiles`. |
| `/etc/systemd/timesyncd.conf.d/tinko.conf` | `install_timesync_config()` | `ConnectionRetrySec=5`, so a first NTP attempt that fails while wifi is still coming up is retried sooner than the default 30 s. |
| `/run/tinko-update/` | runtime | Trigger, status and stage files. tmpfs — recreated at every boot. |

!!! warning "Three copies of the same unit file"
    The `tinko.service` heredoc exists in `install-raspberry-pi.sh`, `update.sh`
    and `update-web.sh`, and a Pi ends up with whichever script last wrote the
    unit. They must agree — `tests/test_power_shutdown.py` fails if they drift.

The sudoers rule for the power helper is validated with `visudo -cf` before it
is installed. A malformed file in `sudoers.d` makes sudo refuse **every**
command for that user, which would take the update system's own rules down with
it.

Two things deliberately do **not** go through Tinko's sudoers files:

- The dashboard Power button runs a root-owned script rather than `sudo bash -c`,
  so the app is granted the halt and nothing else.
- `setcap` on the venv's Python (web path only) is belt-and-suspenders;
  `AmbientCapabilities` in the unit is what actually lets daphne bind port 80.

## The journal across reboots

`install_persistent_journal()` runs on all three paths — it is called from
`setup_update_infrastructure()` for install and CLI updates, and directly from
`update-web.sh`, which deliberately does not call that function because it would
restart `tinko-update.service` while that service is running the update. A Pi
updated only from the dashboard would otherwise never get it.

Without it the journal is **volatile**: journald keeps its log on tmpfs
(`/run/log/journal`), each boot starts with an empty history, and
`journalctl --list-boots` lists one boot and nothing else. On the field Pi
(checked 2026-09-27) that meant the log written on the way down was gone by the
time anyone could read it, which is exactly the record the Power button leaves
behind.

Three separate things have to line up, and the first version of this function
had only the middle one — it reported success while the journal stayed volatile:

1. **The vendor drop-in must be out-sorted.** Raspberry Pi OS ships
   `/usr/lib/systemd/journald.conf.d/40-rpi-volatile-storage.conf` setting
   `Storage=volatile`, to keep the journal off the SD card. journald reads
   drop-ins sorted by name with the last one winning, so an override in `/etc`
   only wins if its basename sorts after `40-rpi-volatile-storage.conf` —
   `tinko.conf` does, a name starting with a digit would not. Renaming that file
   is how the setting silently stops applying.
2. **A flush is required.** With `Storage=persistent` in place, journald still
   writes to `/run/log/journal` until a flush has been requested:
   `server_system_journal_open()` opens the system journal only when
   `flush_requested || server_flushed_flag_is_set`, and that flag is set by
   `systemd-journal-flush.service` at boot or by `journalctl --flush` by hand.
   So installing the drop-in and restarting journald changes nothing on a
   *running* system, and journald says nothing about it. The function runs
   `journalctl --flush` for exactly this reason, and it is what made the fix work
   on the field Pi without a reboot.
3. **log2ram syncs the journal only from under `/var/log`.** `/var/log` is
   log2ram's tmpfs, and `journald_logrotate()` backs the journal up to disk only
   when `journalctl --header` reports a `File path` under `/var/log` — it greps
   that field. With the vendor's volatile setting the path was `/run/log/journal`,
   so nothing was ever copied to log2ram's disk copy (`/var/hdd.log`) and nothing
   survived the reboot. (1) is what fixes this too.

Preparation and honesty:

- **`systemd-tmpfiles --create --prefix /var/log/journal`** is what prepares the
  directory with the ownership, mode and ACLs journald expects. A plain `mkdir`
  leaves a directory journald cannot create its machine-id subdirectory in, and
  it falls back to tmpfs *silently*.
- The function reports **what journald actually chose**, not what it asked for,
  by reading the path out of `journalctl --header` and warning if it is still
  under `/run`. The field to read is `File path:` — one line per open journal
  (the system journal, plus one per logged-in user), so the check matches only
  the line containing `/system`. An earlier version grepped `^File:`, matched
  nothing, and warned "Could not read the journal header" on a Pi whose journal
  was in fact still volatile — a false alarm pointing at the check rather than
  the journal.

`SystemMaxUse=32M` and `RuntimeMaxUse=32M` bound it. The log now lives on the SD
card, and `/var/log` is a 128M tmpfs here: a journal allowed its default share of
it would crowd out the dnsmasq and `tinko_wifi` logs the captive portal is
diagnosed from.

## The clock after a boot

A Raspberry Pi 4 has no battery-backed clock, and this image has no
`fake-hwclock`. Until NTP answers, the clock is the last time systemd saved: PID1
logs `System time advanced to timestamp on /var/lib/systemd/timesync/clock` and
starts from that file's **mtime** — the moment the Pi last shut down. So the
clock is approximately right from the first second and exactly right once
`systemd-timesyncd` gets an answer, and the gap in between is the whole problem:
log lines are stamped with yesterday's date, and `git pull` over HTTPS can fail
on a certificate that is not yet valid, which reads like a network fault.

On the field Pi the first sync landed 42 seconds after boot — the time wifi
association and DHCP take — with four `Network configuration changed, trying to
establish connection` retries first. Two changes narrow that:

- **`install_timesync_config()`** writes
  `/etc/systemd/timesyncd.conf.d/tinko.conf` with `ConnectionRetrySec=5`. The
  default is 30 s, so a first attempt that fails while the network is still
  coming up can be followed by a wait longer than the network took. Retrying
  every 5 s costs a handful of UDP packets. The *server* is deliberately left
  alone: timesyncd uses what DHCP hands out (option 42) and falls back to the
  Debian pool, and a school's own server is usually the nearest one.
- **`ensure_clock_is_set()`** runs before every update pull
  (`update.sh:pull_latest`, `update-web.sh:pull_latest`), because that is the
  step where a wrong clock turns into a confusing failure rather than a wrong
  timestamp. It returns immediately if the clock is already NTP-synchronized;
  otherwise it restarts timesyncd and polls for 20 s; otherwise it falls back to
  reading the `Date:` header of `http://github.com` or
  `http://deb.debian.org` and setting the clock from it — a plain HTTP request
  needs no certificate and so works while the clock is wrong, which matters on
  networks that drop UDP 123.

Both are non-fatal and both are honest about the outcome: with no network there
is nothing to sync with, and the setup/captive-portal path must not depend on the
internet. The app's own start is deliberately **not** gated on
`systemd-time-wait-sync` — Django does not need the wall clock, and blocking boot
on the internet is how a Pi in a school with no uplink stops working.

`uninstall.sh` removes both drop-ins and leaves `/var/log/journal` (systemd's own
directory, and it holds the history) and NTP itself in place.

## Sourced-file staleness and the re-exec guard

bash reads a running script from its open file descriptor, and `git pull`
replaces files by atomic rename. So the run that *performs* the pull keeps
executing the code it already parsed — which is fine for data it writes, but
means its own code changes silently wait for the next run.

`source` makes this one layer worse: `scripts/update_infra.sh` is parsed into
functions **before** the pull, so a pull that changes a helper leaves that run
calling the old body. Observed 2026-09-26: an update rewrote
`/etc/sudoers.d/tinko-update` with pre-fix contents and never installed the
power helper, then reported success.

Both update scripts now record a digest of the running script **and**
`scripts/update_infra.sh` at startup, and re-execute themselves once after the
pull if either moved, naming the file in the log:

```
[WARNING] Replaced by the pull: /home/tinko/edu-pi/scripts/update_infra.sh
[INFO] This run is still on the old copy; re-executing so the changes take effect now...
```

The re-exec is guarded by `TINKO_UPDATE_REEXEC=1` so it cannot loop, and uses
`exec` — which skips the EXIT trap (no bogus emergency restart) and keeps the
PID the daemon is waiting on. On a Pi still running the older guard, run the
update once more: the new file is already on disk, so the second run parses it
at startup.

## Files that must survive a pull

`git pull` on a Pi whose working tree is dirty needs a stash, and the stash is
popped only when the pull *fails*. Three kinds of file are both tracked in git
and written at runtime, so each update used to lose the live version (or leave
a stash behind):

| File | Why it is at risk | Protection |
|------|-------------------|-----------|
| `db.sqlite3` | Tracked, but the app writes to it constantly. | `hide_live_db()` / `restore_live_db()` move it out of the tree around the pull, on both paths; `recover_orphaned_db()` handles an interrupted run. |
| Files git still tracks under `media/` (the school logo) | An upload is stashed, then the committed copy is checked back out over it. | `hide_media()` / `restore_media()` / `recover_orphaned_media()`, driven by `git ls-files media`, so the guard retires itself once `media/` is untracked. |
| Compiled catalogues (`*.mo`) | Rewrites of `compile_translations.py`, so any translation change left the tree dirty and produced one stash per update. | Untracked, `*.mo` in `.gitignore`, and the stash check now uses `--untracked-files=no`. The `.mo` files are rebuilt by the update itself. |

!!! danger "Untracking a live file is a two-step order"
    `git rm --cached db.sqlite3` (or a logo, or a `.mo`) makes the *merge*
    delete the working-tree file. The protection above must therefore be
    **running on the Pi first**, and only then may the untrack be committed —
    otherwise the update deletes the live database or the teacher's upload.

## The web update, end to end

1. The dashboard POSTs to `/updates/start/`; Django writes
   `/run/tinko-update/trigger` and creates an `UpdateStatus` row.
2. `tinko-update.service` (root, stdlib-only, no Django) sees the trigger and
   runs `update-web.sh`.
3. The script writes only `stage.json`; the daemon is the **sole writer** of
   `status.json`, streaming the script's output into it.
4. The WebSocket consumer polls the status file and pushes progress to the
   browser.
5. `reconcile_update_records()` runs on later requests: it syncs a terminal
   status file back into the DB row, and abandons rows that are older than two
   minutes with neither a trigger file nor an `in_progress` status — the state
   a reboot leaves behind, which otherwise blocks the next update with
   *"Update already in progress"*.

The daemon recreates its own runtime state after every reboot, so any
permission the installer set once on `/run/tinko-update/` is gone at boot. The
daemon re-applies it, and the app repairs it with the two granted `mkdir`/
`chmod` sudoers lines as a fallback.

**A CLI update leaves no trace in these files.** `bash update.sh` writes to the
terminal, so `/run/tinko-update/status.json` and
`journalctl -u tinko-update` stay empty. When someone updates by hand, judge
the result by outcomes — service active, ports serving, helper installed — not
by the log.

## Services, capabilities and root access

`tinko.service` carries:

```ini
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE CAP_SETUID CAP_SETGID CAP_AUDIT_WRITE
```

`AmbientCapabilities` is what lets daphne bind ports 80 and 443 without
`setcap`. The **bounding set** is the part worth understanding: it also clamps
what a *setuid* binary gains, and `sudo` is setuid root. With only
`CAP_NET_BIND_SERVICE` in the set, sudo cannot `setgid(0)` and refuses every
command the app asks for — `unable to change to root gid: Operation not
permitted` — which killed the Power button and the run-directory repair
(found 2026-09-26). `CAP_SETUID`/`CAP_SETGID` let sudo reach root;
`CAP_AUDIT_WRITE` only stops sudo's audit plugin from reporting *"unable to send
audit message"* on every call.

**Nothing here bounds escalation.** Raspberry Pi OS ships
`/etc/sudoers.d/010_pi-nopasswd` (`tinko ALL=(ALL) NOPASSWD: ALL`), so the app
user could already run any command as root; the clamp was the only thing
blocking that, and widening it hands that back. The narrow grant is what keeps
the Power button honest; a real boundary would start at that OS file, which
needs install and update to stop calling `sudo` non-interactively first. Tinko
leaves the file alone deliberately — see
[Power button does nothing](troubleshooting.md#power-button-does-nothing).

## Verifying an update

```bash
# Web updates: what the daemon recorded
cat /run/tinko-update/status.json
sudo journalctl -u tinko-update --since "30 min ago"

# The unit the Pi is actually running
systemctl show tinko -p CapabilityBoundingSet -p AmbientCapabilities

# The pieces install and update are responsible for
ls -l /usr/local/sbin/tinko-poweroff
sudo -n /usr/local/sbin/tinko-poweroff --check     # safe: never halts
cat /etc/sudoers.d/tinko-poweroff

# Nothing was left behind by the last pull
cd ~/edu-pi && git stash list

# The journal survives a reboot, and holds more than this boot
journalctl --list-boots
journalctl --header | grep '^File path:'     # /var/log/journal/... means persistent
systemd-analyze cat-config systemd/journald.conf | grep -E 'Storage|MaxUse'

# The clock: synchronized, and by which server
timedatectl show -p NTPSynchronized --value  # yes
timedatectl timesync-status
```

A CLI update prints its own summary to the terminal; the files above stay empty
for that path, which is expected.

## See also

- [Troubleshooting](troubleshooting.md) — the failure modes of everything above
- [Configuration](configuration.md) — service unit and settings reference
- [Translations](../developer/translations.md) — the catalogues the update compiles
