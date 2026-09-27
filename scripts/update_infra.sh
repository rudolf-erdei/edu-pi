#!/bin/bash
#
# Tinko - Update Infrastructure Setup
#
# Sourced by update.sh, install-raspberry-pi.sh and update-web.sh.
# Provides setup_update_infrastructure(), which installs, enables and starts
# the tinko-update.service daemon that powers web-driven updates
# (Settings -> Updates), install_power_helper(), which installs the
# dashboard power-button helper, install_persistent_journal(), which keeps the
# journal across reboots, install_timesync_config()/ensure_clock_is_set(),
# which sync the clock sooner after boot and make sure nothing trusts a stale
# one, and optimize_for_sd_card(), which turns off the writes to the SD card
# that this Pi does not need -- plus install_log2ram(), a step of it that has
# to run before the journal can be kept in RAM rather than on the card.
# Requires log_info/log_success/log_warning/log_error to be defined by the
# sourcing script BEFORE sourcing this file.
#
# This file only defines functions and the handful of path variables the SD
# section needs; sourcing it has no side effects.
#
# Usage: source "$INSTALL_DIR/scripts/update_infra.sh"

# Install the dashboard power-button helper and grant the service user exactly
# that command, and nothing else.
#
# $1 - the service user to grant it to. Defaults to $USER, which is right when a
#      human runs update.sh; update-web.sh runs as ROOT under the update daemon,
#      so it must pass the service user explicitly or the grant lands on root.
#
# Never fatal by itself: a caller that aborts the whole update because the power
# button could not be wired up would leave the Pi half-updated. It logs and
# returns 1, and the endpoint reports the missing helper to the teacher.
install_power_helper() {
    local svc_user="${1:-${USER}}"
    local helper_src="$INSTALL_DIR/scripts/tinko-poweroff"
    local helper_dst="/usr/local/sbin/tinko-poweroff"
    local drop_in="/etc/sudoers.d/tinko-poweroff"
    local sudoers_tmp

    if [ ! -f "$helper_src" ]; then
        log_error "Power helper source not found: $helper_src"
        return 1
    fi

    # Root-owned, mode 0755, in a directory the service user cannot write: the
    # rule below grants root, so the file it runs must not be rewritable by the
    # app that calls it.
    if ! sudo install -o root -g root -m 0755 "$helper_src" "$helper_dst"; then
        log_error "Could not install $helper_dst"
        return 1
    fi

    # Its own drop-in rather than an append to tinko-update's file: writing one
    # file per concern means a mistake here cannot clobber the update system's
    # own rules, and the validity check below covers only what changed.
    sudoers_tmp="$(mktemp)"
    cat > "$sudoers_tmp" << EOF
# Tinko dashboard Power button (templates/home.html -> /power/shutdown/).
# The halt itself lives in the helper below, root-owned and not writable by
# $svc_user, so this grants the power-off and nothing else. "" is the sudoers
# idiom for "no arguments": the real halt cannot be dressed up with any, and
# --check is the only argument allowed.
$svc_user ALL=(ALL) NOPASSWD: /usr/local/sbin/tinko-poweroff ""
$svc_user ALL=(ALL) NOPASSWD: /usr/local/sbin/tinko-poweroff --check
EOF

    # Validate BEFORE installing. sudo refuses every command for a user whose
    # sudoers.d entry is malformed, which would take the update system's own
    # rules, the run-directory repair and the service restarts down with it.
    # --check the file, so only what we are adding is on trial.
    if command -v visudo >/dev/null 2>&1; then
        local visudo_output
        if ! visudo_output=$(sudo visudo -cf "$sudoers_tmp" 2>&1); then
            log_error "Refusing to install an invalid sudoers file:"
            # visudo points at the offending column; log its own words rather
            # than a guess, since this is the only thing that can go wrong here.
            while IFS= read -r line; do
                [ -n "$line" ] && log_warning "  $line"
            done <<< "$visudo_output"
            log_warning "  ($drop_in not installed; the power button will report this when pressed)"
            rm -f "$sudoers_tmp"
            return 1
        fi
    else
        log_warning "visudo not found; installing the power rule without syntax validation"
    fi

    if ! sudo install -o root -g root -m 0440 "$sudoers_tmp" "$drop_in"; then
        log_error "Could not install $drop_in"
        rm -f "$sudoers_tmp"
        return 1
    fi
    rm -f "$sudoers_tmp"

    log_success "Power button helper installed ($helper_dst)"
}

# Make the journal survive a power cut.
#
# Three things have to line up, and on the field Pi none of them did. The log
# that would say why a Pi halted (or failed to come back) was on tmpfs every
# time, so `journalctl --list-boots` listed one boot and nothing else.
#
# 1. Raspberry Pi OS ships /usr/lib/systemd/journald.conf.d/40-rpi-volatile-
#    storage.conf setting Storage=volatile, to keep the journal off the SD card.
#    Overriding a vendor drop-in from /etc needs a filename that sorts AFTER it:
#    journald reads drop-ins sorted by name, last one wins. "tinko.conf" sorts
#    after "40-rpi-..."; a name sorting before it would be read first and lose.
# 2. With Storage=persistent, journald still writes to /run/log/journal until a
#    flush is requested. server_system_journal_open() in journald-server.c opens
#    the system journal only when `flush_requested ||
#    server_flushed_flag_is_set(s)`, and that flag is set by
#    systemd-journal-flush.service at boot or by `journalctl --flush` by hand.
#    So installing the drop-in and restarting journald changes nothing on a
#    running system, and journald says nothing about it. The flush below is what
#    makes the setting take effect now instead of at the next boot.
# 3. /var/log is log2ram's tmpfs, and log2ram only backs the journal up to disk
#    when `journalctl --header` reports a File path under /var/log -- that is
#    literally what its journald_logrotate() greps for. With the vendor's
#    volatile setting the path was /run/log/journal, so the journal was never
#    synced to /var/hdd.log and nothing survived a reboot.
#
# With all three, the journal goes to /var/log/journal (tmpfs), log2ram rotates
# and rsyncs it to its disk copy, and log2ram restores that into /var/log at the
# next boot, where journalctl reads it -- so older boots are listed again.
#
# `systemd-tmpfiles --create --prefix` is the supported way to create the
# directory with the ownership, mode and ACLs journald expects. The size limits
# are deliberately modest: /var/log is a 128M tmpfs here, and a journal allowed
# its default share of it would crowd out the dnsmasq and tinko_wifi logs the
# captive portal is diagnosed from.
#
# Never fatal by itself: a Pi whose journal is volatile still runs, and a caller
# that aborted the update over this would leave it half-updated.
install_persistent_journal() {
    local drop_in="/etc/systemd/journald.conf.d/tinko.conf"
    local journal_dir="/var/log/journal"
    local conf_tmp

    if ! sudo mkdir -p "$journal_dir" /etc/systemd/journald.conf.d; then
        log_error "Could not create $journal_dir"
        return 1
    fi

    if command -v systemd-tmpfiles >/dev/null 2>&1; then
        # Sets root:systemd-journal and the ACLs; without it journald cannot
        # create its machine-id directory here and quietly stays volatile.
        sudo systemd-tmpfiles --create --prefix "$journal_dir" ||
            log_warning "systemd-tmpfiles could not prepare $journal_dir"
    else
        log_warning "systemd-tmpfiles not found; $journal_dir may not be writable by journald"
    fi

    conf_tmp="$(mktemp)"
    cat > "$conf_tmp" << EOF
# Written by Tinko (scripts/update_infra.sh). Keep the journal across reboots so
# a halt or a failed boot can still be read afterwards.
#
# This overrides /usr/lib/systemd/journald.conf.d/40-rpi-volatile-storage.conf
# (Storage=volatile), which Raspberry Pi OS ships to keep the journal off the SD
# card. Overriding a vendor drop-in requires a filename sorting after it, since
# journald reads drop-ins in name order and the last one wins -- "tinko.conf"
# sorts after "40-rpi-...". Do not rename this to something starting with a
# digit or "t": it would be read before the vendor's file and silently lose.
#
# Without persistence here the journal also never reaches the SD card at all:
# log2ram backs the journal up only when its File path is under /var/log.
[Journal]
Storage=persistent
SystemMaxUse=32M
RuntimeMaxUse=32M
EOF

    if ! sudo install -o root -g root -m 0644 "$conf_tmp" "$drop_in"; then
        log_error "Could not install $drop_in"
        rm -f "$conf_tmp"
        return 1
    fi
    rm -f "$conf_tmp"

    sudo systemctl restart systemd-journald.service ||
        log_warning "Could not restart systemd-journald"

    # Restarting is not enough: this is what actually moves the journal off
    # tmpfs on a running system (see "2." above). Without it the drop-in only
    # takes effect at the next boot, which is how the first version of this
    # function reported success while the journal stayed volatile.
    if ! sudo journalctl --flush 2>/dev/null; then
        log_warning "Could not flush the journal now; it will move to $journal_dir at the next boot"
    fi

    # Report what journald actually chose, not what was asked of it: the
    # fallback to tmpfs is silent, and a silent failure here is the one that
    # costs the evidence. The header prints one "File path:" line per open file
    # (the system journal plus one per logged-in user), and the field is named
    # "File path" -- matching the shorter "File:" finds nothing at all, which is
    # how an earlier version of this check produced a false "could not read the
    # journal header" on a Pi whose journal was in fact still volatile.
    local journal_file
    journal_file=$(sudo journalctl --header 2>/dev/null |
        awk -F': ' '/^File path:/ && /\/system/ && !/user-/ {print $2; exit}')
    case "$journal_file" in
        "$journal_dir"/*)
            log_success "Persistent journal enabled ($journal_file)"
            ;;
        "")
            log_warning "Could not read the journal header; check 'journalctl --header'"
            ;;
        *)
            log_warning "journald is still logging to $journal_file -- the journal will not survive a reboot"
            ;;
    esac
}

# Make the first clock sync after a boot happen as soon as the network is up.
#
# A Pi 4 has no RTC. Until NTP answers, the clock is only the last time systemd
# saved: PID1 logs "System time advanced to timestamp on
# /var/lib/systemd/timesync/clock" in the boot journal and starts from that
# file's mtime, which on the field Pi was the moment it had shut down. So the
# clock is approximately right from the first second and exactly right once NTP
# replies -- the gap in between is what this narrows.
#
# systemd-timesyncd retries a failed server every ConnectionRetrySec, 30s by
# default. Wifi association and DHCP take ~35s on this hardware, so a first
# attempt that fails while the network is still coming up is followed by a wait
# that can be longer than the network took. Retrying every 5s costs a handful of
# UDP packets while the Pi is waiting and closes that gap.
#
# Server choice is deliberately left alone: timesyncd uses whatever DHCP hands
# out (option 42), and falls back to the Debian pool otherwise. A school's own
# server is usually the closest one, so overriding that would be a downgrade.
#
# Never fatal: an offline Pi has nothing to sync with, and the setup/captive-
# portal path must not depend on the internet.
install_timesync_config() {
    local drop_in="/etc/systemd/timesyncd.conf.d/tinko.conf"
    local conf_tmp
    local synced

    if ! sudo mkdir -p /etc/systemd/timesyncd.conf.d; then
        log_error "Could not create /etc/systemd/timesyncd.conf.d"
        return 1
    fi

    conf_tmp="$(mktemp)"
    cat > "$conf_tmp" << EOF
# Written by Tinko (scripts/update_infra.sh). See install_timesync_config().
# A Pi has no RTC, and the default 30s retry after a failed attempt can outlast
# the time wifi and DHCP take to come up.
[Time]
ConnectionRetrySec=5
EOF

    if ! sudo install -o root -g root -m 0644 "$conf_tmp" "$drop_in"; then
        log_error "Could not install $drop_in"
        rm -f "$conf_tmp"
        return 1
    fi
    rm -f "$conf_tmp"

    sudo systemctl restart systemd-timesyncd.service ||
        log_warning "Could not restart systemd-timesyncd"

    # Report the state, not the intent: no NTP answer is a normal answer on a Pi
    # with no network, and claiming a sync that did not happen is how the journal
    # check above went wrong.
    synced=$(timedatectl show -p NTPSynchronized --value 2>/dev/null)
    if [ "$synced" = "yes" ]; then
        log_success "Clock is NTP-synchronized ($(date -Is))"
    else
        log_info "Clock not synchronized yet (no NTP answer); it syncs when the network is up"
    fi
}

# Make sure the clock is trustworthy before anything that checks certificate
# dates.
#
# `git pull` over HTTPS is the case that matters: with a wrong clock the
# certificate check fails, and the failure reads like a network problem. That is
# the same shape as the bug that hid a broken web update for weeks (see
# docs/reference/update-system.md), so the clock is settled before the pull
# rather than guessed at afterwards.
#
# Cheapest first:
#   1. Already NTP-synchronized? Nothing to do.
#   2. Restart timesyncd and give it ~20s; it syncs within seconds of the network
#      being up.
#   3. Ask a web server for its Date header. That needs no certificate and so
#      works while the clock is wrong -- which is the point, since some school
#      networks drop UDP 123, leaving NTP unreachable while the web is fine.
#
# Returns 0 if the clock is now trustworthy, 1 if it is not. The caller decides
# what to do about it; an update that cannot pull is better reported than
# skipped, and the pull logs its own error.
ensure_clock_is_set() {
    local waited=0 http_date url

    if timedatectl show -p NTPSynchronized --value 2>/dev/null | grep -qx yes; then
        log_info "Clock is NTP-synchronized ($(date -Is))"
        return 0
    fi
    log_warning "Clock is not NTP-synchronized yet: $(date -Is)"

    sudo systemctl restart systemd-timesyncd.service 2>/dev/null || true
    while [ "$waited" -lt 20 ]; do
        sleep 2
        waited=$((waited + 2))
        if timedatectl show -p NTPSynchronized --value 2>/dev/null | grep -qx yes; then
            log_success "Clock synchronized after ${waited}s: $(date -Is)"
            return 0
        fi
    done

    if ! command -v curl >/dev/null 2>&1; then
        log_warning "No curl; cannot fall back to an HTTP Date header"
        return 1
    fi

    for url in http://github.com http://deb.debian.org; do
        # The header is RFC 1123 ("Sun, 27 Sep 2026 11:08:47 GMT"), which GNU
        # date parses. -u on both sides so the local timezone is not applied
        # twice: the header is UTC and the clock is set in UTC.
        http_date=$(curl -sI --max-time 8 "$url" 2>/dev/null |
            sed -n 's/^[Dd]ate:[[:space:]]*//p' | tr -d '\r' | head -1)
        [ -n "$http_date" ] || continue
        if sudo -n date -u -s "$(date -u -d "$http_date" '+%Y-%m-%d %H:%M:%S')" >/dev/null 2>&1; then
            log_success "Clock set from $url's Date header: $(date -Is)"
            return 0
        fi
        log_warning "Could not set the clock from $url ($http_date)"
    done

    log_warning "Clock is still unsynchronized: $(date -Is) -- a pull over HTTPS may fail with a certificate error"
    return 1
}

# --- SD card write reduction ----------------------------------------------
#
# The Pi's only disk is the SD card, and a card has a finite number of writes.
# What matters here is not the total (the field Pi had written ~23GB in its
# lifetime, nothing for a card rated in tens of TBW) but the *shape* of the
# writes: many small ones, spread over time, on a machine whose power is cut at
# the wall. Every one of them is a chance to lose power mid-write, and the card
# has no power-loss protection of its own.
#
# The two biggest writers the app owns are handled in code instead -- see
# tests/test_sd_card_writes.py for the rolling log handlers and SQLite's
# write-ahead log. Everything below is the operating system's share, measured on
# the field Pi rather than guessed at:
#
#   * apt-daily.timer and apt-daily-upgrade.timer fetch and install updates
#     twice a day, writing the package lists and any unpacked package to the
#     card. This Pi is updated by Tinko's own update system, and a classroom Pi
#     is switched off most of the day anyway.
#   * rpi-zram-writeback.timer copies idle pages out of compressed RAM swap to a
#     backing file on the card (/dev/loop0 -> /var/swap). Turning it off keeps
#     swap in RAM; it does not remove swap, and zram0 stays 2GB.
#   * ext4's commit interval is 5s by default, so a Pi that does almost nothing
#     still commits its journal twelve times a minute. commit=600 in fstab makes
#     that once every ten minutes; anything that fsyncs (SQLite does) is written
#     on the spot regardless.
#   * the kernel's writeback flusher runs every 5s and writes out anything older
#     than 30s. A minute of coalescing turns thousands of small writes into a
#     handful.
#   * /var/tmp is where throwaway files land (package managers unpack there) and
#     nothing expects them to survive a reboot.
#   * Bluetooth: the classroom Pi drives a touch display and has no Bluetooth
#     devices; the stack writes to the card and holds a serial port.
#
# Every step is idempotent, reports what it actually did rather than what it
# asked for, and is non-fatal. A Pi whose Bluetooth is still on is a working Pi,
# and a caller that aborted an update because one of these failed would leave it
# half-updated -- the rule this file already follows for the journal and the
# clock. Reversing all of it is uninstall.sh's remove_sd_optimizations().

# Overridable so the tests can point them at a throwaway tree instead of /etc.
# (The one exception to "this file only defines functions": a path variable the
# tests have to be able to move. Nothing is read or written at source time.)
FSTAB_FILE="${TINKO_FSTAB_FILE:-/etc/fstab}"
FSTAB_BACKUP="${FSTAB_FILE}.tinko-bak"
BOOT_CONFIG="${TINKO_BOOT_CONFIG:-/boot/firmware/config.txt}"
RPI_SWAP_DROP_IN_DIR="${TINKO_RPI_SWAP_DIR:-/etc/rpi/swap.conf.d}"
RPI_SWAP_DROP_IN="${RPI_SWAP_DROP_IN_DIR}/tinko.conf"
SD_SYSCTL_DIR="${TINKO_SYSCTL_DIR:-/etc/sysctl.d}"
VAR_TMP_MOUNT_UNIT="${TINKO_VAR_TMP_UNIT:-/etc/systemd/system/var-tmp.mount}"
SD_COMMIT_SECONDS=600

# Marks the block this installs in config.txt, and the line uninstall.sh removes
# again. Kept as a constant because three files agree on it: this one writes it,
# uninstall.sh matches it, and the tests read it.
SD_BT_COMMENT="# Tinko: Bluetooth off (no Bluetooth devices on this Pi; the stack writes to the SD card)."

# Print an fstab with commit=N added to the root mount's options.
#
# A filter -- fstab in on stdin, fstab out on stdout -- because that keeps the
# risky part in one place that can be run and read back: only the line whose
# second field is exactly "/" is touched, only when it does not already carry a
# commit= option, so a second run changes nothing and a separate /boot line is
# left as it was.
#
# (The root line is rewritten, which makes awk re-join it with tabs. fstab does
# not care about the whitespace; the alternative, patching the text in place
# with sed, is one bad pattern away from an unbootable fstab.)
sd_fstab_add_commit() {
    local commit="$1"
    awk -v commit="$commit" '
        /^[[:space:]]*#/ { print; next }
        /^[[:space:]]*$/ { print; next }
        NF >= 4 && $2 == "/" {
            if ($4 !~ /(^|,)commit=/) {
                $4 = $4 ",commit=" commit
            }
            line = $1 "\t" $2 "\t" $3 "\t" $4
            for (i = 5; i <= NF; i++) {
                line = line "\t" $i
            }
            print line
            next
        }
        { print }
    '
}

# Does this fstab pass the kernel's own reader?
#
# This catches a malformed table -- a parse error, a mountpoint that is not
# there, an unknown filesystem type -- and NOT a bad option name: `findmnt
# --verify` accepted `defaults,bogusopt` on the field Pi without a murmur. That
# is still worth running, because a table systemd cannot parse is what drops a
# Pi into emergency mode with no network and no keyboard.
sd_fstab_verify() {
    local candidate="$1" output parse_errors errors

    if ! command -v findmnt >/dev/null 2>&1; then
        log_warning "findmnt not found; $candidate checked structurally only"
        return 0
    fi

    output=$(sudo findmnt --verify --tab-file "$candidate" 2>&1) || true
    # "0 parse errors, 0 errors, 2 warnings" is the summary line, and the
    # warnings are usually just an unreadable superblock. Anything above zero in
    # either count means systemd will not read this table the way we mean it.
    parse_errors=$(printf '%s\n' "$output" |
        sed -n 's/^\([0-9][0-9]*\) parse errors.*/\1/p' | head -n 1)
    errors=$(printf '%s\n' "$output" |
        sed -n 's/^[0-9][0-9]* parse errors, \([0-9][0-9]*\) errors.*/\1/p' | head -n 1)

    if [ "$parse_errors" = "0" ] && [ "$errors" = "0" ]; then
        return 0
    fi

    log_error "findmnt rejected $candidate:"
    while IFS= read -r line; do
        [ -n "$line" ] && log_warning "  $line"
    done <<< "$output"
    return 1
}

# Give the root filesystem a longer commit interval.
sd_add_root_commit_option() {
    local candidate backup="${FSTAB_BACKUP}" installed_lines original_lines

    if [ ! -f "$FSTAB_FILE" ]; then
        log_warning "No $FSTAB_FILE; skipping the commit= option"
        return 1
    fi

    if awk '!/^[[:space:]]*#/ && $2 == "/" { print $4 }' "$FSTAB_FILE" | grep -q 'commit='; then
        log_info "Root mount already carries a commit= option; $FSTAB_FILE left alone"
        return 0
    fi

    candidate="$(mktemp)"
    sd_fstab_add_commit "$SD_COMMIT_SECONDS" < "$FSTAB_FILE" > "$candidate"

    # Structural checks, because these are the ones that decide whether the Pi
    # boots: the rewritten table must still have a root entry, and must not have
    # lost or gained a line. (`grep -c ''` counts lines the way a reader does,
    # including a last line with no trailing newline.)
    if [ ! -s "$candidate" ] ||
        ! awk '!/^[[:space:]]*#/ && $2 == "/" { found = 1 } END { exit !found }' "$candidate"; then
        log_error "Refusing to install a rewritten $FSTAB_FILE with no root entry"
        rm -f "$candidate"
        return 1
    fi
    installed_lines=$(grep -c '' "$candidate")
    original_lines=$(grep -c '' "$FSTAB_FILE")
    if [ "$installed_lines" != "$original_lines" ]; then
        log_error "Refusing to install a rewritten $FSTAB_FILE: ${original_lines} lines became ${installed_lines}"
        rm -f "$candidate"
        return 1
    fi

    if ! sd_fstab_verify "$candidate"; then
        log_error "Leaving $FSTAB_FILE as it is"
        rm -f "$candidate"
        return 1
    fi

    # Keep the file as it was before Tinko touched it. Written once: a second
    # update must not overwrite the pre-Tinko original with a Tinko-edited one.
    if [ ! -f "$backup" ]; then
        if ! sudo install -o root -g root -m 0644 "$FSTAB_FILE" "$backup"; then
            log_warning "Could not back up $FSTAB_FILE to $backup"
        fi
    fi

    if ! sudo install -o root -g root -m 0644 "$candidate" "$FSTAB_FILE"; then
        log_error "Could not install the rewritten $FSTAB_FILE"
        rm -f "$candidate"
        return 1
    fi
    rm -f "$candidate"

    # Verify what actually landed rather than what we meant to write, and put
    # the backup back if it does not pass. This is the one change in this file
    # that can stop the Pi coming back on, so a revert here costs nothing.
    if ! sd_fstab_verify "$FSTAB_FILE"; then
        log_error "The installed $FSTAB_FILE failed verification; restoring $backup"
        if [ -f "$backup" ] && sudo install -o root -g root -m 0644 "$backup" "$FSTAB_FILE"; then
            log_warning "$FSTAB_FILE restored; the commit= option is not in place"
        else
            log_error "COULD NOT RESTORE $FSTAB_FILE -- check it by hand before rebooting"
        fi
        return 1
    fi

    log_success "commit=$SD_COMMIT_SECONDS added to the root mount in $FSTAB_FILE"

    # Apply it to the running mount as well, so the saving starts now instead of
    # at the next reboot. Not fatal either way: the option is in fstab.
    if sudo mount -o "remount,commit=$SD_COMMIT_SECONDS" / 2>/dev/null; then
        log_success "Root remounted with commit=$SD_COMMIT_SECONDS"
    else
        log_info "Root mount keeps its old interval until the next reboot"
    fi
}

# Put /var/tmp in RAM.
#
# A systemd mount unit rather than an fstab line, deliberately: systemd-fstab-
# generator and systemd-remount-fs read fstab during early boot, and a table
# they cannot parse drops the Pi into emergency mode -- no network, no keyboard,
# and a teacher standing next to it. A mount unit that fails is just a failed
# unit: boot carries on and /var/tmp stays on the card.
sd_mount_var_tmp_in_ram() {
    local unit="$VAR_TMP_MOUNT_UNIT" staging unit_file

    if [ -f "$unit" ] && systemctl is-active --quiet var-tmp.mount; then
        log_info "/var/tmp is already in RAM"
        return 0
    fi

    # systemd-analyze verify refuses a unit whose filename does not match its
    # Where=, so the temporary copy has to carry the real unit name.
    staging="$(mktemp -d)"
    unit_file="$staging/var-tmp.mount"
    cat > "$unit_file" << 'EOF'
# Written by Tinko (scripts/update_infra.sh). See docs/reference/sd-card.md.
#
# /var/tmp is for files that are explicitly allowed not to survive a reboot
# (package managers unpack here), and on this Pi the only disk is the SD card.
# 256M is a ceiling, not a reservation: tmpfs holds only what is in it.
#
# A mount unit rather than an fstab line on purpose: a mistake in this file is
# a failed unit, and boot carries on with /var/tmp still on the card.
[Unit]
Description=/var/tmp in RAM (Tinko)

[Mount]
What=tmpfs
Where=/var/tmp
Type=tmpfs
Options=nosuid,nodev,noatime,mode=1777,size=256M

[Install]
WantedBy=local-fs.target
EOF

    if command -v systemd-analyze >/dev/null 2>&1 &&
        ! sudo systemd-analyze verify "$unit_file" 2>/dev/null; then
        log_error "systemd-analyze rejected the /var/tmp mount unit; not installing it"
        rm -rf "$staging"
        return 1
    fi

    sudo mkdir -p /var/tmp
    if ! sudo install -o root -g root -m 0644 "$unit_file" "$unit"; then
        log_error "Could not install $unit"
        rm -rf "$staging"
        return 1
    fi
    rm -rf "$staging"

    sudo systemctl daemon-reload
    sudo systemctl enable var-tmp.mount >/dev/null 2>&1 ||
        log_warning "Could not enable var-tmp.mount; it will not be mounted at boot"

    # Mount it now if it is not up. The old contents of /var/tmp are hidden
    # rather than deleted by the mount, and they reappear when the unit is
    # removed -- which is what uninstall.sh relies on.
    if systemctl is-active --quiet var-tmp.mount; then
        log_success "/var/tmp is in RAM"
    elif sudo systemctl start var-tmp.mount; then
        log_success "/var/tmp is in RAM ($(df -h /var/tmp 2>/dev/null | tail -1 | awk '{print $2}'))"
    else
        log_warning "Could not start var-tmp.mount; /var/tmp stays on the SD card for now"
        return 1
    fi
}

# Let the kernel batch its own writeback instead of waking every five seconds.
sd_set_writeback_sysctl() {
    local file="$SD_SYSCTL_DIR/99-tinko-sd.conf" candidate current

    candidate="$(mktemp)"
    cat > "$candidate" << 'EOF'
# Written by Tinko (scripts/update_infra.sh). See docs/reference/sd-card.md.
#
# The kernel wakes its writeback flusher every vm.dirty_writeback_centisecs and
# writes out anything older than vm.dirty_expire_centisecs. The defaults (500
# and 3000, i.e. 5s and 30s) mean a Pi that does nothing at all still touches
# the SD card thousands of times a day, and each touch is a chance to lose power
# mid-write. A minute of coalescing turns that into a handful.
#
# This is safe only because everything that must be durable fsyncs explicitly --
# SQLite does, and so does anything else that needs the write on the card. What
# is delayed here is the kernel's own periodic flush of data that nothing is
# waiting on.
#
# 99- sorts after the vendor's 98-rpi.conf: sysctl.d is read in filename order
# and the last value set for a key is the one that takes effect.
vm.dirty_writeback_centisecs = 6000
vm.dirty_expire_centisecs = 6000
EOF

    if ! sudo mkdir -p "$SD_SYSCTL_DIR" ||
        ! sudo install -o root -g root -m 0644 "$candidate" "$file"; then
        log_error "Could not install $file"
        rm -f "$candidate"
        return 1
    fi
    rm -f "$candidate"

    sudo sysctl --system >/dev/null 2>&1 ||
        sudo sysctl -p "$file" >/dev/null 2>&1 ||
        log_warning "Could not apply $file now; it applies from the next boot"

    # Report the value in force, not the file's contents.
    current=$(sysctl -n vm.dirty_writeback_centisecs 2>/dev/null) || current="?"
    log_success "Kernel writeback interval is ${current} centisecs (default is 500)"
}

# Stop the two apt timers.
#
# They fetch the package lists twice a day and install any upgrades: several MB
# written to the card per run, on a Pi that is switched off most of the day and
# is updated by Tinko's own update system. The trade is real and deliberate --
# with these off, OS packages only move when someone runs apt by hand.
sd_disable_apt_timers() {
    local unit

    for unit in apt-daily.timer apt-daily-upgrade.timer; do
        if ! systemctl list-unit-files "$unit" >/dev/null 2>&1; then
            continue
        fi
        if ! systemctl is-enabled --quiet "$unit" 2>/dev/null; then
            log_info "$unit is already disabled"
            continue
        fi
        if sudo systemctl disable --now "$unit"; then
            log_success "Disabled $unit"
        else
            log_warning "Could not disable $unit"
        fi
    done

    return 0
}

# Keep compressed swap in RAM instead of spilling it to the card.
#
# rpi-swap gives zram a backing device -- a loop device over /var/swap, on the
# SD card -- and a timer that periodically copies idle pages out to it, to free
# RAM. On this Pi the RAM is not the scarce resource (3.7GB, about 400MB in
# use); the card is. So the timer goes, via the documented configuration rather
# than by editing the vendor's file: `man 5 swap.conf` names
# /etc/rpi/swap.conf.d/*.conf as the recommended place for local overrides, and
# WritebackTrigger=manual is what makes the generator stop creating the timer at
# all. A drop-in is one file, removed to reverse.
#
# Swap itself is untouched: zram0 stays 2GB and stays in use.
sd_disable_zram_writeback() {
    local unit="rpi-zram-writeback.timer" candidate

    if ! systemctl list-unit-files "$unit" >/dev/null 2>&1 &&
        [ ! -e "$RPI_SWAP_DROP_IN" ]; then
        log_info "$unit is not present on this system; nothing to disable"
        return 0
    fi

    if [ ! -f "$RPI_SWAP_DROP_IN" ]; then
        candidate="$(mktemp)"
        cat > "$candidate" << 'EOF'
# Written by Tinko (scripts/update_infra.sh). See docs/reference/sd-card.md.
#
# rpi-swap gives zram a backing device on the SD card (a loop device over
# /var/swap) and a timer that copies idle pages out to it to free RAM. This Pi
# has RAM to spare and a card to spare nowhere, so the writeback is left to be
# triggered by hand instead: with `manual`, rpi-swap-generator does not create
# rpi-zram-writeback.timer at all. Swap itself is unchanged -- zram0 stays
# 2GB, and `echo idle > /sys/block/zram0/writeback` still writes back on
# request.
#
# A drop-in, not an edit of /etc/rpi/swap.conf: swap.conf(5) names this
# directory as the recommended place for local configuration, and removing this
# one file restores the default.
[Zram]
WritebackTrigger=manual
EOF
        if ! sudo mkdir -p "$RPI_SWAP_DROP_IN_DIR" ||
            ! sudo install -o root -g root -m 0644 "$candidate" "$RPI_SWAP_DROP_IN"; then
            log_error "Could not install $RPI_SWAP_DROP_IN"
            rm -f "$candidate"
            return 1
        fi
        rm -f "$candidate"
    fi

    # Stop it before the reload: on a running system the generator's unit
    # vanishes under the timer, and systemd logs that as a failed unit.
    sudo systemctl stop "$unit" 2>/dev/null || true
    sudo systemctl daemon-reload

    if ! systemctl is-active --quiet "$unit" 2>/dev/null &&
        [ ! -e "/run/systemd/generator/$unit" ]; then
        log_success "zram writeback timer removed ($RPI_SWAP_DROP_IN)"
        return 0
    fi

    # The drop-in is the documented way in; if this image's generator does not
    # honour it, a mask is the blunt way that works regardless.
    log_warning "$unit is still active; masking it instead"
    if sudo systemctl mask "$unit"; then
        log_success "Masked $unit"
        return 0
    fi
    log_warning "Could not turn off $unit; zram may still spill to the SD card"
    return 1
}

# Print config.txt with the Bluetooth overlay turned off.
#
# A filter, like the fstab one, so the appended block can be run and read back.
# Idempotent: if the overlay is already there, the file comes back unchanged.
#
# `[all]` because config.txt sections filter by board, and the header is
# repeated at the end of the file -- which config.txt allows: [all] clears the
# filter, so the lines after it apply whatever the firmware detected.
sd_boot_config_with_bt_off() {
    local comment="$1"
    awk -v comment="$comment" '
        { line[NR] = $0 }
        /^[[:space:]]*dtoverlay=disable-bt([[:space:]]|$)/ { found = 1 }
        END {
            for (i = 1; i <= NR; i++) {
                print line[i]
            }
            if (found) {
                exit
            }
            # Always a blank line first: awk cannot tell whether the last record
            # ended with a newline, and a file that did not would otherwise run
            # this comment into its last line. A blank line costs nothing here.
            print ""
            print comment
            print "[all]"
            print "dtoverlay=disable-bt"
        }
    '
}

# Turn Bluetooth off.
#
# Two halves, and both are needed. The overlay stops the firmware loading the
# Bluetooth stack and frees the UART it held; the service is what would
# otherwise sit there logging that it cannot find a controller. The overlay only
# takes effect at the next boot, and the function says so rather than implying
# it is already done.
sd_disable_bluetooth() {
    local candidate backup="${BOOT_CONFIG}.tinko-bak" overlay_present=0

    if [ ! -f "$BOOT_CONFIG" ]; then
        log_warning "No $BOOT_CONFIG; skipping Bluetooth"
        return 1
    fi

    if grep -qE '^[[:space:]]*dtoverlay=disable-bt([[:space:]]|$)' "$BOOT_CONFIG"; then
        overlay_present=1
        log_info "Bluetooth is already disabled in $BOOT_CONFIG"
    else
        candidate="$(mktemp)"
        sd_boot_config_with_bt_off "$SD_BT_COMMENT" < "$BOOT_CONFIG" > "$candidate"

        if [ ! -s "$candidate" ] ||
            ! grep -qE '^[[:space:]]*dtoverlay=disable-bt([[:space:]]|$)' "$candidate"; then
            log_error "Refusing to install a rewritten $BOOT_CONFIG with no Bluetooth overlay"
            rm -f "$candidate"
            return 1
        fi

        if [ ! -f "$backup" ]; then
            sudo install -o root -g root -m 0644 "$BOOT_CONFIG" "$backup" ||
                log_warning "Could not back up $BOOT_CONFIG to $backup"
        fi

        if ! sudo install -o root -g root -m 0644 "$candidate" "$BOOT_CONFIG"; then
            log_error "Could not install the rewritten $BOOT_CONFIG"
            rm -f "$candidate"
            return 1
        fi
        rm -f "$candidate"
        log_success "Bluetooth disabled in $BOOT_CONFIG (takes effect at the next reboot)"
    fi

    # The overlay only removes the controller; this is the stack that manages it,
    # and it would log a failure to find one for the rest of the Pi's life.
    # hciuart is not on every image, and is enabled by default only where the
    # Bluetooth UART exists, so both are checked rather than assumed.
    local unit
    for unit in bluetooth.service hciuart.service; do
        if ! systemctl list-unit-files "$unit" >/dev/null 2>&1; then
            continue
        fi
        if ! systemctl is-enabled --quiet "$unit" 2>/dev/null; then
            log_info "$unit is already disabled"
            continue
        fi
        if sudo systemctl disable --now "$unit"; then
            log_success "Disabled $unit"
        else
            log_warning "Could not disable $unit"
        fi
    done

    return 0
}

# Keep /var/log in RAM instead of on the card.
#
# This is what the journal work depends on: /var/log is a tmpfs, the journal
# goes to /var/log/journal on it, and log2ram's daily timer copies it to
# /var/hdd.log on the card. Without log2ram every log line from the app, dnsmasq
# and the captive portal is a card write.
#
# Nothing used to install it -- the docs assumed it and the field Pi had it
# because it was added by hand. It is in Debian's own repository (trixie/main),
# so a fresh install gets it for real now. Non-fatal when there is no network:
# the package is only reachable if apt can reach a mirror.
install_log2ram() {
    local version

    if dpkg-query -W -f='${Status}' log2ram 2>/dev/null | grep -q "install ok installed"; then
        version=$(dpkg-query -W -f='${Version}' log2ram 2>/dev/null)
        log_info "log2ram is already installed (${version:-unknown version})"
    elif ! command -v apt-get >/dev/null 2>&1; then
        log_warning "apt-get not found; log2ram not installed and /var/log stays on the SD card"
        return 1
    else
        log_info "Installing log2ram (keeps /var/log in RAM)..."
        if ! sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y log2ram; then
            log_warning "Could not install log2ram; /var/log stays on the SD card"
            return 1
        fi
        log_success "log2ram installed"
    fi

    sudo systemctl enable log2ram.service log2ram-daily.timer >/dev/null 2>&1 ||
        log_warning "Could not enable log2ram.service/log2ram-daily.timer"

    # The package starts it, but a Pi that has had it disabled would otherwise
    # only pick it up at the next boot.
    if systemctl is-active --quiet log2ram.service; then
        log_info "log2ram is active; /var/log is in RAM"
    elif sudo systemctl start log2ram.service; then
        log_success "log2ram started; /var/log is in RAM"
    else
        log_warning "log2ram installed but not started; /var/log moves to RAM at the next boot"
        return 1
    fi
}

# Turn off the SD card writes this Pi does not need.
#
# Called from setup_update_infrastructure() -- so the installer and the CLI
# update both get it -- and directly from update-web.sh, which deliberately does
# not call that function (it would restart the update daemon that is running it).
#
# Returns non-zero if any step could not be applied, so the caller can say so.
# Every step has already explained itself by then; this is the summary line.
optimize_for_sd_card() {
    local failures=0

    log_info "Reducing SD card writes..."

    sd_disable_apt_timers || failures=$((failures + 1))
    sd_disable_zram_writeback || failures=$((failures + 1))
    sd_disable_bluetooth || failures=$((failures + 1))
    sd_mount_var_tmp_in_ram || failures=$((failures + 1))
    sd_set_writeback_sysctl || failures=$((failures + 1))
    sd_add_root_commit_option || failures=$((failures + 1))
    install_log2ram || failures=$((failures + 1))

    if [ "$failures" -eq 0 ]; then
        log_success "SD card write reduction applied (see docs/reference/sd-card.md)"
        return 0
    fi

    log_warning "$failures SD card step(s) could not be applied; each one above says why"
    return 1
}

# Setup update infrastructure for web updates
setup_update_infrastructure() {
    log_info "Setting up update infrastructure for web updates..."

    # 1. Create run directory and set permissions
    sudo mkdir -p /run/tinko-update
    sudo chmod 777 /run/tinko-update

    # 2. Configure sudoers for the update process
    SUDOERS_FILE="/etc/sudoers.d/tinko-update"
    sudo tee $SUDOERS_FILE > /dev/null << EOF
# Permissions for Tinko update process
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl stop tinko
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl start tinko
$USER ALL=(ALL) NOPASSWD: /usr/bin/mkdir -p /run/tinko-update
$USER ALL=(ALL) NOPASSWD: /usr/bin/chmod 777 /run/tinko-update
EOF
    # The dashboard Power button is NOT granted here: it goes through
    # install_power_helper() into its own drop-in, so that the halt runs a
    # root-owned script instead of a shell. The old lines that granted
    # /usr/bin/systemctl poweroff and /usr/sbin/shutdown were removed
    # 2026-09-26 -- nothing in the code ever called either binary, and
    # `sudo shutdown -r now` is a reboot the app has no business having.

    # 3. Install the update daemon service
    log_info "Installing tinko-update.service..."

    # Determine absolute path to the daemon
    DAEMON_PATH="$INSTALL_DIR/core/update_system/update_daemon.py"

    sudo tee /etc/systemd/system/tinko-update.service > /dev/null << EOF
[Unit]
Description=Tinko Update Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $DAEMON_PATH
Restart=always
RestartSec=5
# The daemon streams the update script's output into the status file and, in
# passing, to its own stdout. Python block-buffers stdout when it is not a
# terminal, so without this the journal shows nothing until the buffer flushes
# -- and a daemon that dies mid-update leaves no trace at all in the log.
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable tinko-update.service

    # Start (or restart) the service. Restarting picks up new daemon code
    # after an update; recover_interrupted_update() in the daemon handles any
    # trigger left in-flight.
    #
    # Never restart while an update is in flight. This function also runs at the
    # start of a CLI update, so running update.sh by hand on a Pi that is
    # updating itself from the dashboard would kill the running update and leave
    # the dashboard saying "Update already in progress" with nothing behind it.
    if [ -f /run/tinko-update/trigger ]; then
        log_warning "An update is in flight; leaving tinko-update.service running"
    elif sudo systemctl is-active --quiet tinko-update.service; then
        sudo systemctl restart tinko-update.service
    else
        sudo systemctl start tinko-update.service
    fi

    # 4. Dashboard power button (helper + its own sudoers drop-in). Non-fatal:
    # see install_power_helper().
    install_power_helper "${TINKO_SERVICE_USER:-$USER}" ||
        log_warning "Power button helper not installed; the dashboard will report that when pressed"

    # 5. Keep the journal across reboots, so a halt or a failed boot can still
    # be read afterwards. Non-fatal: see install_persistent_journal().
    install_persistent_journal ||
        log_warning "Journal left volatile; logs will not survive a reboot"

    # 6. Sync the clock sooner after boot, so the log stops being stamped with
    # the last shutdown's time and a pull does not meet a wrong date. Non-fatal:
    # see install_timesync_config().
    install_timesync_config ||
        log_warning "Clock retry left at the default; the first sync may take longer"

    # 7. Cut the SD card writes this Pi does not need. It lives here because
    # this is the one function both the installer and the CLI update call --
    # update-web.sh calls the other steps individually, since it IS the update
    # daemon this function would otherwise restart, and calls this one directly.
    # Non-fatal: see optimize_for_sd_card().
    optimize_for_sd_card ||
        log_warning "Some SD card writes are still enabled; the steps above say which"

    log_success "Update infrastructure set up successfully"
}
