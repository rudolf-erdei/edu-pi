#!/bin/bash
#
# Tinko - Update Infrastructure Setup
#
# Sourced by update.sh, install-raspberry-pi.sh and update-web.sh.
# Provides setup_update_infrastructure(), which installs, enables and starts
# the tinko-update.service daemon that powers web-driven updates
# (Settings -> Updates), install_power_helper(), which installs the
# dashboard power-button helper, and install_persistent_journal(), which keeps
# the journal across reboots. Requires log_info/log_success/log_warning/
# log_error to be defined by the sourcing script BEFORE sourcing this file.
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
# The image ships /var/log/journal empty and no Storage setting, so journald
# keeps its log on tmpfs (/run/log/journal) and every boot starts with an empty
# history: `journalctl --list-boots` lists one boot and nothing else. That is
# exactly the evidence the dashboard Power button leaves behind -- the log that
# would say why a Pi halted, or failed to come back -- so it is worth the two
# lines of configuration.
#
# `systemd-tmpfiles --create --prefix` is the supported way to create the
# directory with the ownership, mode and ACLs journald expects; SystemMaxUse
# caps it so a long-lived Pi cannot fill its SD card with log.
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
# a halt or a failed boot can still be read afterwards. SystemMaxUse bounds it:
# the log lives on the SD card.
[Journal]
Storage=persistent
SystemMaxUse=200M
EOF

    if ! sudo install -o root -g root -m 0644 "$conf_tmp" "$drop_in"; then
        log_error "Could not install $drop_in"
        rm -f "$conf_tmp"
        return 1
    fi
    rm -f "$conf_tmp"

    sudo systemctl restart systemd-journald.service ||
        log_warning "Could not restart systemd-journald"

    # Report what journald actually chose, not what was asked of it: the
    # fallback to tmpfs is silent, and a silent failure here is the one that
    # costs the evidence.
    local journal_file
    journal_file=$(sudo journalctl --header 2>/dev/null | awk '/^File:/ {print $2; exit}')
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

    log_success "Update infrastructure set up successfully"
}
