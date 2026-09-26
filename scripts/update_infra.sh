#!/bin/bash
#
# Tinko - Update Infrastructure Setup
#
# Sourced by update.sh and install-raspberry-pi.sh.
# Provides setup_update_infrastructure(), which installs, enables and starts
# the tinko-update.service daemon that powers web-driven updates
# (Settings -> Updates). Requires log_info/log_success/log_warning/log_error
# to be defined by the sourcing script BEFORE sourcing this file.
#
# Usage: source "$INSTALL_DIR/scripts/update_infra.sh"

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
# Safe shutdown from the dashboard (Power button)
$USER ALL=(ALL) NOPASSWD: /usr/bin/systemctl poweroff
$USER ALL=(ALL) NOPASSWD: /usr/sbin/shutdown
EOF

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

    log_success "Update infrastructure set up successfully"
}
