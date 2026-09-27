#!/bin/bash
#
# Tinko - Update Infrastructure Setup
#
# Sourced by update.sh, install-raspberry-pi.sh and update-web.sh.
# Provides setup_update_infrastructure(), which installs, enables and starts
# the tinko-update.service daemon that powers web-driven updates
# (Settings -> Updates), install_power_helper(), which installs the
# dashboard power-button helper, install_persistent_journal(), which keeps the
# journal across reboots, and install_timesync_config()/ensure_clock_is_set(),
# which sync the clock sooner after boot and make sure nothing trusts a stale
# one. Requires log_info/log_success/log_warning/log_error to be defined by the
# sourcing script BEFORE sourcing this file.
#
# This file only defines functions; sourcing it has no side effects.
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

    log_success "Update infrastructure set up successfully"
}
