# Future ideas for the project

* In the settings area:
  * Show the used and free space on the device, so the teacher knows the state of the system.
  * Provide a button to clean the database (whatever is not needed, like old history).
  * Provide a backup button for the data (download). Also provide upload possibilities for backed-up data.
  * Show the health of the SD card, if possible. Tell the teacher to change it when health is at a dangerous level.
  * Show the energy consumption of the entire system (is this possible?).
  * Show how many clients are connected to the django service. Prevents unwanted connection.
* On boot, display the current status and eventual errors on the screen.
   - Maybe with a loading indicator and if everything is OK?
* Some issues need to be also displayed on the screen, to have a better view of what is happening.

## SD card / long-term usage

Audited 2026-09-27 against the field Pi (Debian 13, 15 GB card, zram swap,
log2ram). What shipped is `optimize_for_sd_card()` in `scripts/update_infra.sh`
plus the logging and SQLite changes in `config/settings.py`; the manual is
`docs/reference/sd-card.md`. Marked below: what was applied, what was checked and
found unnecessary, and what is still open.

* Optimize the PI for long term usage:
  * ~~Remove GUI~~ — not applicable: the field Pi boots to `multi-user.target`,
    with no X server, display manager or desktop session running. Nothing to
    remove, and the `purge` wildcards for it are a way to delete something the
    system needs.
  * ~~Disable Swap~~ — **deliberately not done.** Swap here is zram (compressed
    RAM), so it writes nothing to the card and turning it off only removes the
    protection against running out of memory. What *did* write to the card is the
    zram **writeback**, and that is now off — `WritebackTrigger=manual` in
    `/etc/rpi/swap.conf.d/tinko.conf`, because `systemctl disable` cannot stick
    on a unit the generator recreates at every boot.
  * ~~`sudo apt install log2ram`~~ — now installed by the project itself
    (`install_log2ram()`), not assumed. The journal work depended on it and the
    field Pi only had it because someone added it by hand.
  * ~~`sudo apt purge libreoffice* wolfram-engine scratch* geany thonny`~~ — not
    applicable: checked on the field Pi, none of them are installed.
  * ~~`sudo apt autoremove --purge`~~ / ~~`sudo apt clean`~~ — one-off disk
    housekeeping, no ongoing writes. Worth running by hand on a Pi that has seen
    upgrades; not something an update should decide.
  * ~~`sudo systemctl disable cups`~~ / ~~`cups-browsed`~~ — not applicable: not
    installed (checking beats disabling a unit that is not there).
  * ~~`sudo apt purge modemmanager`~~ — not applicable: not installed. It is the
    thing behind the long boot delays people notice on desktop images.
  * ~~`sudo systemctl disable triggerhappy.service`~~ — not applicable: not
    installed.
  * ~~purge x11/wayfire/lxde/pixel/lightdm~~ / ~~autoremove~~ — not applicable,
    same as "Remove GUI". One caveat found while checking: `x11-common` and
    `x11-utils` *are* installed, as dependencies of packages that are present
    (`apt-cache rdepends --installed x11-utils` names `chromium-common` and
    `xdg-utils`), so a wildcard purge there removes something else's dependency
    rather than a desktop.
  * ~~remove swap from /etc/fstab~~ / ~~`sudo rm /swapfile`~~ — no swap file and
    no swap entry exist on this image; swap is zram.
* Not in the original list but applied because the same audit turned them up:
  * Log rotation for both app log files, LCD logger moved off `DEBUG` (it was
    8.7 MB in a few weeks), SQLite in WAL mode, noise readings kept 24 h
    (26,369 rows in a day and a half).
  * `apt-daily` / `apt-daily-upgrade` timers off — twicedaily package-list
    fetches nobody asked for. Cost: OS packages now move **only** when someone
    runs `apt` by hand.
  * `commit=600` on the root mount and a 60 s kernel writeback interval — the
    two that decide how often anything the app does not `fsync` reaches the card.
  * `/var/tmp` on tmpfs (256 MB) — package managers unpack there.
  * Bluetooth off (`dtoverlay=disable-bt`) — no Bluetooth devices on these Pis.
* Still open:
  * **SSD.** The real fix for a card that keeps failing. Tinko does not assume
    one; if one is fitted, the zram writeback and the swap file are what should
    move to it.
  * **Read-only root.** A bigger change: the app would need a writable overlay
    for `db.sqlite3`, `media/` and `logs/`. Worth revisiting if a card ever fails
    again.
  * **What the boot screen shows** (the two items above) — still unbuilt.