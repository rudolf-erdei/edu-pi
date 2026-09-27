# Future ideas for the project

## In the settings area

Analysed 2026-09-27 by probing the field Pi (Raspberry Pi 4 Model B Rev 1.2,
Debian 13, Django 4.2.29). Each entry says what the machine can actually answer.
Two of these are limited by the hardware rather than by the app, and one turned
up a gap that is not an idea at all — see [A login, first](#a-login-first).

Four were built the same day, as the Settings → System tab — see
[below](#built-2026-09-27--the-system-tab). What is left is the risky half of the
backup, two things the hardware cannot answer, and the login.

| Idea | Verdict | Size |
|------|---------|------|
| Used and free space | ✅ built — the Storage card | — |
| Clean the database | ✅ built — retention windows, not a space saver | — |
| Data backup (download) | ✅ built — `VACUUM INTO` snapshot in a zip | — |
| Clients connected | ✅ built — browsers seen in the last 2 minutes | — |
| Restore from a backup (upload) | doable; this is the risky half | medium — needs a root helper |
| SD card health | **proxies only** — there is no wear figure to read | medium |
| Energy consumption | **not measurable on a Pi 4** | estimate only |
| A login on the dashboard | **absent today** | medium |

### Built 2026-09-27 — the System tab

The four `small` ideas shipped as a **System** tab on `/settings/`:
`core/edupi_core/system/` (`storage.py`, `history.py`, `clients.py`,
`backup.py`, `views.py`), `templates/settings/system_tab.html`,
`static/js/system.js`, and three test files. What the analysis got right, and
what it changed once it met the code:

- **Free space is `shutil.disk_usage`, and the interesting rows are the RAM
  ones.** The field Pi reports 15 GB total, 7.9 GB used, 5.6 GB free; `/var/log`
  is log2ram's 128 MB tmpfs. **When that fills, logging stops** — which is why
  the warning above 80% names the consequence rather than the number. Both RAM
  rows are shown only when `os.path.ismount` says they are mounts, so the tab
  degrades to a single row off-Pi instead of lying.
- **"Clean the database" is a retention control, not a space saver**, and the
  measurement above still holds: the noise history is already pruned to 24 h, so
  the button frees kilobytes. Deleting does not shrink the file — the pages are
  reused — so **compact** is a separate, rare action with its own warning.
  `VACUUM` needs `PRAGMA busy_timeout=30000` here, because the noise monitor
  commits every five seconds and the default timeout would fail those commits
  mid-rewrite.
- **The scope was wider than "history tables".** A running `TimerSession` is
  held in memory by `timer_service` and saved again on every change, so deleting
  its row would have Django re-`INSERT` it; and an `in_progress` update row is
  what blocks a second concurrent update. Both are excluded, and both have
  tests. `PluginEventLog` is left alone entirely — never written, admin-only.
- **Clients = browsers seen in the last two minutes**, counted in process memory
  because sessions already live in `LocMemCache`: a count costs no database row
  and no SD-card write. `X-Forwarded-For` is not trusted (nothing proxies
  daphne), and what is stored is Django's *resolved route*, never the raw path —
  so no client-supplied string is ever stored or echoed. The original note said
  this needed the login to mean anything; it does not, but the honest label is
  "browsers", not "users", and the panel says so.
- **The download half of the backup is built**: `VACUUM INTO` a snapshot (never
  copy `db.sqlite3` — WAL), `PRAGMA integrity_check` it, zip it with `media/`
  and a `manifest.json` carrying per-table row counts and the site settings
  (minus credential-looking keys). Built under the temp directory, which is
  tmpfs, so a backup writes no card at all — at the price of refusing a database
  too large to fit in RAM.

### Restore from a backup — the other half, not built

The **upload** half is where the care goes, and the pattern already exists in
the repo: `update.sh` swaps the live database safely (`hide_live_db` /
`restore_live_db` / `db_files`, which carry the WAL and `-shm` with it), and
root helpers installed by `scripts/update_infra.sh` are an established shape
(`scripts/tinko-poweroff`, `tinko-update.service`). Restore is:

1. validate the upload is a SQLite file containing the expected tables —
   before anything touches the live database;
2. hand it to a root helper that stops `tinko.service`, replaces `db.sqlite3`
   **and deletes any `-wal`/`-shm`**, replaces `media/`, and starts the service.

Django cannot replace its own open database underneath itself, so step 2 is
never something the web process may do by itself. Two smaller notes: uploads
over 2.5 MB hit Django's `FILE_UPLOAD_MAX_MEMORY_SIZE`/`DATA_UPLOAD_MAX_MEMORY_SIZE`
defaults, which will need raising if `media/` ever holds much; and a restored
logo is exactly the kind of file the update merge has wiped before, so restore
should be verified the same way an update is.

Worth noting: **"Database backups" is already a requirement** (`REQUIREMENTS.md`
→ General). The download half now exists (see above); this is the half that does
not, and the System tab's button says so where a teacher will read it.

### SD card health — proxies only, and no percentage exists to show

What the machine exposes, all readable:

| Signal | Source | Field Pi |
|--------|--------|----------|
| Filesystem state, error behaviour | `dumpe2fs -h` | `clean` |
| Lifetime writes | `dumpe2fs -h` | 23 GB |
| Mount count, last checked | `dumpe2fs -h` | 34, Dec 2025 |
| Bus errors (CRC, timeouts) | `/sys/kernel/debug/mmc0/err_stats` | all 0 |
| Filesystem errors logged | `journalctl` (`EXT4-fs error`, remount-ro) | none |
| Free space | `df` | 5.6 GB |
| Who the card even is | `/sys/block/mmcblk0/device/` | see below |

Card identity is plain files: `name` = `SU16G`, `manfid` = `0x000003`
(SanDisk), `oemid` = `SD`, `date` = **10/2013**, plus `fwrev`, `serial`,
`type`.

**What does not exist:** wear percentage, TBW consumed, remaining life, spare
or bad-block counts. SD cards have no SMART (`smartctl` is not installed and
would have nothing to talk to); `life_time` is an **eMMC** register — checked on
the field Pi, the file is not there; and the SD Status Register (`ssr`) *is*
readable but carries speed class and erase geometry, not wear.

So: **flags, not a health bar.** Warn when free space is low, when the
filesystem state is not `clean`, when the mmc error counters are non-zero, when
the journal has logged a filesystem error. Do **not** derive a percentage from
`Lifetime writes` — 23 GB against a card rated in tens of terabytes would read
as a number that is wrong by orders of magnitude, and a teacher who wants a
number will act on the one you print.

The best predictor available is the one already in `/sys`: this card is a
16 GB SanDisk made in **10/2013**, thirteen years old and below the 32 GB the
hardware requirements ask for. Showing age and identity beside the flags is
more honest than inventing a score.

### Energy consumption — not measurable on this hardware

`vcgencmd` on the field Pi accepts exactly: `measure_clock`, `measure_temp`,
`measure_volts`, `get_throttled`, `display_power`. `pmic_read_adc` — the command
that reports the 5 V rail's voltage and current — answers *"Command not
registered"*: it is a **Pi 5** feature. There is no `/sys/class/power_supply`,
and no shunt to read: the only I2C buses exposed are `i2c-20`/`i2c-21`, which
are the HDMI DDC lines, with the header bus (`i2c-1`) not enabled.

What *is* readable answers the teacher's real question — *is the power all
right?* — better than a wattage would:

- `measure_temp`, `measure_volts core` (0.85 V here);
- `get_throttled` (`0x0` = fine; bit 0 = undervoltage **now**, bit 16 =
  undervoltage **since boot**, bits 2/3 = thermal). A sagging power supply is
  the thing that actually corrupts a card, and this flag detects it.

A consumption *estimate* is possible — a Pi 4 idles around 3 W and peaks near
6 W, so hours-on × a tariff the teacher enters gives a monthly figure — but it
is an estimate wearing a measurement's clothes. If it is shipped, it has to be
labelled as one. Real measurement means an INA219/INA260 shunt on the input plus
`i2c-1` enabled: hardware, not app work.

### A login, first

This started as a note under "clients connected" and is not an idea, it is a
gap. **Nothing asks for a login.** Django is 4.2.29 — `LoginRequiredMiddleware`
is 5.1+, so it is not available — there is no `@login_required` anywhere under
`core/` or `plugins/`, and `AuthenticationMiddleware` only attaches
`request.user`; it enforces nothing.

Consequences on the field Pi:

- the dashboard, every plugin page and `/settings/` are open to anyone who can
  reach port 8000;
- `settings_view` accepts a POST with **no auth check at all**, so an anonymous
  visitor on the classroom network can change the school name and upload a logo;
- only `/admin/` is gated, and that is Django's own admin, not Tinko's.

PIN-based authentication for teacher settings is already a requirement
(`REQUIREMENTS.md` → Security). Building the client counter before the login
means counting strangers, and building the restore button before it means anyone
on the network can replace the database.

## On the screen

* On boot, display the current status and eventual errors on the screen.
   - Maybe with a loading indicator and if everything is OK?
* Some issues need to be also displayed on the screen, to have a better view of what is happening.

## SD card / long-term usage

Audited 2026-09-27 against the field Pi (Debian 13, 15 GB card, zram swap,
log2ram) and applied. What shipped is `optimize_for_sd_card()` in
`scripts/update_infra.sh` plus the logging and SQLite changes in
`config/settings.py`; the manual is `docs/reference/sd-card.md`, which also
records why the rest of the usual SD-card advice turned out not to apply here.

* Still open:
  * **SSD.** The real fix for a card that keeps failing. Tinko does not assume
    one; if one is fitted, the zram writeback and the swap file are what should
    move to it.
  * **Read-only root.** A bigger change: the app would need a writable overlay
    for `db.sqlite3`, `media/` and `logs/`. Worth revisiting if a card ever fails
    again.
  * **What the boot screen shows** (the two items above) — still unbuilt.