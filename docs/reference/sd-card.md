# SD Card and Long-Term Wear

The Pi's only disk is its SD card. This page is what Tinko switches off to keep
the card out of the picture, what each of those costs, and how to check or undo
any of it.

For the app's own share of the writing — the log handlers and the database — see
[Logging Configuration](configuration.md#logging-configuration).

## What actually wears a card out

Not the total number of bytes. The field Pi had written about **23 GB** in its
lifetime, which is nothing for a card rated in tens of terabytes. What matters
is the *shape* of the writes:

- **many small writes**, spread over time, each one a separate erase-write cycle
  on the card's controller;
- **on a machine whose power is cut at the wall**, so every one of them is a
  chance to lose power mid-write, with no power-loss protection on the card
  itself.

That second point is the real one. Wear retires a card after years; a power cut
at the wrong moment corrupts it on the first afternoon.

So the target is not "write less" but "write less often, in bigger pieces, and
never have a half-finished write matter".

### The writers, measured on the field Pi

| Writer | Rate | Where it went |
|--------|------|---------------|
| LCD display log at `DEBUG` | every panel refresh | 8.7 MB of logs in a few weeks, no rotation |
| Noise monitor readings | one row every 5 seconds | 26,369 rows in a day and a half |
| `apt-daily.timer` / `apt-daily-upgrade.timer` | twice a day | package lists, and any upgrade unpacked |
| `rpi-zram-writeback.timer` | every 24 h, plus on boot | idle swap pages to `/dev/loop0` → `/var/swap` |
| ext4 journal commit | every 5 s | the journal, on a Pi doing nothing at all |
| kernel writeback flusher | every 5 s | dirty pages older than 30 s |
| Every log line from the app, dnsmasq and the captive portal | continuous | the card, unless `/var/log` is in RAM |

The first two are the app's own and are handled in code — see
`tests/test_sd_card_writes.py`. Everything else is the operating system's, and
is handled by `optimize_for_sd_card()` in `scripts/update_infra.sh`.

## What Tinko changes

Every step is idempotent (running the update again changes nothing) and
non-fatal (a step that fails is logged, and the update carries on). A Pi with
Bluetooth still on is a working Pi.

| Step | What it does | What it costs |
|------|--------------|---------------|
| Rolling log handlers | `logs/django.log` and `logs/lcd_display.log` rotate at 1 MB, keeping 2 backups | the oldest log lines are dropped — 3 MB per file is the ceiling, however long the Pi runs |
| LCD logger at `INFO` | stops logging every panel redraw | the per-refresh detail is gone from the log (the LCD page still shows the state) |
| SQLite `journal_mode=WAL` | commits append to a write-ahead log instead of rewriting the database page | none — this is the *safer* mode on a power cut, and it writes less |
| Noise reading retention | readings older than 24 h are deleted once an hour | the noise monitor's history does not go back further than a day; the chart's window is 20 minutes, so nothing visible changes |
| `apt-daily.timer`, `apt-daily-upgrade.timer` off | no automatic package-list fetch or upgrade | **OS packages only move when someone runs `apt` by hand.** Tinko's own update does not upgrade the OS |
| `rpi-zram-writeback.timer` off | zram swap no longer spills idle pages to `/var/swap` | swap stays in RAM, so memory pressure cannot be relieved by spilling. RAM is 3.7 GB here against ~400 MB in use |
| `commit=600` on the root mount | ext4's journal commits every 10 minutes instead of every 5 seconds | up to ten minutes of *unsynced* writes are lost in a power cut. Anything that calls `fsync` (SQLite does) is written on the spot and is unaffected |
| `vm.dirty_writeback_centisecs = 6000`, `vm.dirty_expire_centisecs = 6000` | the kernel's flusher wakes once a minute rather than every 5 seconds | the same ten-minute window for data nothing is waiting on |
| `/var/tmp` on tmpfs, 256 MB | throwaway files (package managers unpack there) stay in RAM | files under `/var/tmp` do not survive a reboot. They never were meant to |
| `dtoverlay=disable-bt` | the firmware stops loading the Bluetooth stack and frees its UART | no Bluetooth devices (keyboards, speakers) will pair. **Takes effect at the next reboot** |
| `bluetooth.service` disabled | stops the stack logging that it cannot find a controller | — |
| `log2ram` installed | `/var/log` is a tmpfs; a daily timer copies it to `/var/hdd.log` on the card | log lines are lost if the Pi is cut off before the daily sync. Also: the journal only reaches the card through log2ram, which is what [makes it survive a reboot](update-system.md) |

!!! warning "These trade durability for card life, deliberately"
    `commit=600`, the writeback interval and the log rotation all mean a power
    cut can lose recent writes. On this device that is the right trade — a
    classroom activity timer's last reading is not worth a card — but it is a
    trade, and it is why the database is the one thing that still syncs to disk
    on every commit.

    **That window only exists for an unplanned cut.** Switching the Pi off with
    the dashboard's Shutdown button — or any orderly halt — makes systemd stop
    the app, close the database and flush the filesystems before the power goes,
    so nothing is pending by the time it is safe to unplug. This is why the
    teachers' instructions are to always switch off from the dashboard: see
    [Shutting Down Tinko](../teacher/dashboard.md#shutting-down-tinko). What
    `commit=600` costs is the power failure nobody asked for.

`vm.dirty_expire_centisecs` is set alongside `vm.dirty_writeback_centisecs`
because a flusher interval longer than the expire time would just be rounded
back to the expire time: it is the *shorter* of the two that decides how long a
dirty page waits.

## Where each piece lives

| Path | Written by | Notes |
|------|-----------|-------|
| `/etc/systemd/system/var-tmp.mount` | `sd_mount_var_tmp_in_ram()` | A mount unit, not an fstab line — see below. `/etc/systemd/system/var-tmp.mount` must match `Where=/var/tmp`, or systemd refuses it. |
| `/etc/sysctl.d/99-tinko-sd.conf` | `sd_set_writeback_sysctl()` | `99-` sorts after the vendor's `98-rpi.conf`; sysctl.d is read in filename order and the last value wins. |
| `/etc/fstab` | `sd_add_root_commit_option()` | `commit=600` added to the root line only. |
| `/etc/fstab.tinko-bak` | `sd_add_root_commit_option()` | The pre-Tinko fstab, written once — uninstall restores from it. |
| `/boot/firmware/config.txt` | `sd_disable_bluetooth()` | A comment, a repeated `[all]` header and `dtoverlay=disable-bt`, appended. |
| `/boot/firmware/config.txt.tinko-bak` | `sd_disable_bluetooth()` | The pre-Tinko config.txt. |
| `/etc/rpi/swap.conf.d/tinko.conf` | `sd_disable_zram_writeback()` | `[Zram] WritebackTrigger=manual`. A drop-in, because `swap.conf(5)` names that directory as the recommended place for local configuration. |
| `log2ram` package | `install_log2ram()` | From Debian's own repository (`trixie/main`), so a fresh install gets it for real. |

### Why `/var/tmp` is a mount unit and not an fstab line

`systemd-fstab-generator` and `systemd-remount-fs.service` read `/etc/fstab`
during early boot, and a table they cannot parse drops the Pi into emergency
mode: no network, no keyboard, nobody near it. A mount unit that fails is just a
failed unit — boot carries on and `/var/tmp` stays on the card.

The same reasoning is why the fstab edit is guarded three times over: the line
count and the presence of a root entry are checked before the file is replaced,
`findmnt --verify` has to pass, and the file as installed is checked again — with
the backup restored if it does not. Note that `findmnt --verify` catches a
malformed table, **not** a bad option name: it accepted `defaults,bogusopt` on
the field Pi without a murmur.

### Why `disable` is not enough for the zram timer

`rpi-zram-writeback.timer` is *generated*: `rpi-swap-generator` recreates it at
every boot, and `systemctl disable` on it reports success while changing nothing
that survives a reboot. What works is the setting that stops it being created at
all — `WritebackTrigger=manual` — which is what the drop-in does. If an image's
generator ignores the drop-in, the step falls back to `systemctl mask`, and says
which of the two it used.

`WritebackTrigger` accepts only `auto`, `manual` or `timer`: there is no `none`,
and an unknown value is silently treated as `auto`.

## Checking what is in effect

```bash
# /var/log is RAM, and the journal is being copied to disk
systemctl is-active log2ram.service && findmnt -no FSTYPE,OPTIONS /var/log

# /var/tmp is RAM
findmnt /var/tmp

# the timers are off
systemctl is-enabled apt-daily.timer apt-daily-upgrade.timer
systemctl is-active rpi-zram-writeback.timer   # not-found is the good answer
ls /run/systemd/generator/rpi-zram-writeback.timer   # absent is the good answer

# the kernel and the filesystem agree with the files
findmnt -no OPTIONS /
sysctl vm.dirty_writeback_centisecs vm.dirty_expire_centisecs
```

Nothing in `/etc` reflects the mount options until the next reboot: the
committed fstab is read at boot, and `sd_add_root_commit_option()` remounts the
running root as well, which is why `findmnt` is the check rather than reading
the file.

## Reading it off the Settings page

Everything the commands above ask about has a read-out on
**Settings → System → Storage**: the card's used and free space, and — on the Pi
only — `/var/log` and `/var/tmp` as separate rows, with a warning above the
table once `/var/log` passes 80% full. Those two rows are the ones to look at,
because they are the tmpfs slices this page exists for; on a machine without
log2ram they are simply absent, which is the intended degradation rather than a
missing measurement.

The two buttons on that tab are worth knowing about here:

- **Download backup** builds the archive under the system temp directory, which
  is tmpfs — so taking a backup writes to RAM and adds **no SD-card writes at
  all**, at the cost of refusing a database too large to fit in memory. Copying
  `db.sqlite3` by hand would be a write, and a wrong one: see
  [Settings → Configuration Backup](../teacher/settings.md#configuration-backup).
- **Compact the database** is the opposite trade: `VACUUM` rewrites the entire
  database, so it is a real burst of writes to the card. It is worth it once
  after a large deletion; it is not a routine. Deleting history without
  compacting frees no space for the card but costs it nothing either — SQLite
  reuses the freed pages in place.

## Turning it off

`sudo bash uninstall.sh` reverses all of it — see
`remove_sd_optimizations()`. Three details there are worth knowing:

- `/etc/fstab` is restored from `/etc/fstab.tinko-bak`, but **only** if the
  `commit=` option is the one thing that has changed since. If the file has been
  edited by hand meanwhile, both are left alone and the summary says so.
- `config.txt` has Tinko's two lines removed by name, and the file is only
  rewritten when exactly those two lines are found. The bare `[all]` header
  stays — it clears config.txt's board filter, so it cannot change how anything
  else in the file is read.
- **`log2ram` is left installed.** It keeps `/var/log` in RAM, which anything on
  the machine benefits from, and removing it while its tmpfs is mounted over
  `/var/log` is more risk than the disk space it costs. To finish the job by
  hand: `sudo apt-get remove log2ram`.

To undo a single step without uninstalling, remove the file listed in
[Where each piece lives](#where-each-piece-lives) and reload the service that
reads it (`systemctl daemon-reload`, `sysctl --system`), or re-enable the timer
with `sudo systemctl enable --now apt-daily.timer`. Bluetooth and the `commit=`
interval take effect at the next reboot.

## What is deliberately not done

- **Swap is left on.** A list of SD-card tips circulating for the Pi says to run
  `swapoff` and delete the swap file. On this image swap is zram — compressed
  RAM, not the card — so turning it off removes the machine's protection against
  running out of memory and saves no writes at all. What *does* write to the
  card is the zram *writeback*, and that is off.
- **The desktop packages are left alone.** The field Pi boots to
  `multi-user.target` with no X server, no display manager and no desktop
  session, and none of the packages the usual tip purges — `cups`,
  `cups-browsed`, `modemmanager`, `triggerhappy`, `lightdm`, `wolfram-engine`,
  `scratch`, `geany`, `thonny`, `libreoffice-core` — are installed to begin
  with (checked on the field Pi, 2026-09-27). The one thing that *does* match
  is `x11-common` and `x11-utils`, and those are pulled in as dependencies of
  packages that are installed (`apt-cache rdepends --installed x11-utils` names
  `chromium-common` and `xdg-utils`): a `apt purge "x11-*"` there is a wildcard
  away from removing something else's dependency. Tinko does not remove OS
  packages on its own.
- **No SSD.** The card's limits are accepted rather than engineered around.
  Should one be fitted later, the writeback and the swap file are what would
  move to it.
