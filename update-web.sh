#!/bin/bash
#
# Tinko - Educational Raspberry Pi Platform - Web Update Script
# This script is used by the tinko-update.service to update the system
#
# Usage: TINKO_UPDATE_DAEMON=1 ./update-web.sh

set -e

# Safety: always restart the service even if the update fails.
# Without this, a failed pull/migrate leaves the service stopped = user locked out.
SERVICE_RESTARTED=0
emergency_restart() {
    if [[ "$SERVICE_RESTARTED" -eq 0 ]]; then
        echo "[EMERGENCY] Restarting Tinko service after failed update..."
        sudo systemctl start ${SERVICE_NAME} 2>/dev/null || true
    fi
}
trap emergency_restart EXIT

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
# Use absolute path for stability when run by systemd
INSTALL_DIR="/home/tinko/edu-pi"
SERVICE_NAME="tinko"
STATUS_FILE="/run/tinko-update/status.json"
# Stage telemetry goes to a SEPARATE file so the daemon remains the only
# writer of status.json (which carries update_id, logs, error, ...).
STAGE_FILE="/run/tinko-update/stage.json"

# Determine the service user from the service file
SERVICE_USER=$(grep '^User=' /etc/systemd/system/tinko.service 2>/dev/null | cut -d= -f2)
if [[ -z "$SERVICE_USER" || "$SERVICE_USER" == "root" ]]; then
    SERVICE_USER="tinko"
fi
SERVICE_HOME="/home/${SERVICE_USER}"

# Run a command as the service user (the owner of the repo and uv).
# The daemon runs as root; git/uv/django steps must run as $SERVICE_USER or
# git's "dubious ownership" check fatals and `uv` is not on root's PATH.
run_as_user() {
    sudo -u "$SERVICE_USER" env HOME="$SERVICE_HOME" \
        PATH="$SERVICE_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin" \
        bash -c "$1"
}

# Telemetry function for the daemon
update_status() {
    if [[ "$TINKO_UPDATE_DAEMON" == "1" ]]; then
        local stage=$1
        local status=$2
        # Use a temporary file and mv for atomic writes
        # The daemon owns status.json; this writes only the current stage.
        echo "{\"stage\": \"$stage\", \"status\": \"$status\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > "${STAGE_FILE}.tmp"
        mv "${STAGE_FILE}.tmp" "$STAGE_FILE"
    fi
}

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in a git repository
check_git_repo() {
    if [[ ! -d "$INSTALL_DIR/.git" ]]; then
        log_error "Not a git repository. Please ensure INSTALL_DIR is correct."
        exit 1
    fi
}

# Stop the service
stop_service() {
    update_status "stop_service" "in_progress"
    log_info "Checking if Tinko service is running..."

    if systemctl list-unit-files | grep -q "${SERVICE_NAME}.service"; then
        if sudo systemctl is-active --quiet ${SERVICE_NAME} 2>/dev/null; then
            log_info "Stopping Tinko service..."
            sudo systemctl stop ${SERVICE_NAME}
            sleep 2

            if sudo systemctl is-active --quiet ${SERVICE_NAME} 2>/dev/null; then
                log_error "Failed to stop service."
                update_status "stop_service" "failed"
                exit 1
            fi
            log_success "Service stopped"
        else
            log_info "Service is not running"
        fi
    else
        log_warning "Tinko service not found."
    fi
    update_status "stop_service" "completed"
}

# Pull latest changes from git
pull_latest() {
    update_status "pull" "in_progress"
    log_info "Pulling latest changes from git..."

    # Run as the service user so git sees a repo it owns (avoids the
    # "dubious ownership" fatal). Prevent credential prompting.
    STASHED=0
    if [[ -n $(run_as_user "cd '$INSTALL_DIR' && GIT_TERMINAL_PROMPT=0 git status --porcelain") ]]; then
        log_warning "Local changes detected. Stashing them..."
        run_as_user "cd '$INSTALL_DIR' && GIT_TERMINAL_PROMPT=0 git stash"
        STASHED=1
    fi

    if run_as_user "cd '$INSTALL_DIR' && timeout 60 GIT_TERMINAL_PROMPT=0 git pull"; then
        log_success "Latest changes pulled successfully"
        update_status "pull" "completed"
    else
        log_warning "Failed to pull (no internet or network error). Continuing with current version."
        # Restore stashed changes since we didn't pull anything new
        if [[ "$STASHED" -eq 1 ]]; then
            log_info "Restoring stashed local changes..."
            run_as_user "cd '$INSTALL_DIR' && git stash pop 2>/dev/null || true"
        fi
        update_status "pull" "skipped"
    fi
}

# Update Python dependencies
update_dependencies() {
    update_status "dependencies" "in_progress"
    log_info "Updating Python dependencies..."

    # uv lives under the service user's ~/.local/bin; run as that user.
    if [[ -f /proc/device-tree/model ]] && grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        log_info "Installing all dependencies including Pi-specific extras..."
        run_as_user "cd '$INSTALL_DIR' && uv sync --all-extras"
    else
        log_info "Installing dependencies..."
        run_as_user "cd '$INSTALL_DIR' && uv sync"
    fi

    log_success "Dependencies updated"
    update_status "dependencies" "completed"
}

# Run database migrations
run_migrations() {
    update_status "migrations" "in_progress"
    log_info "Running database migrations..."

    run_as_user "cd '$INSTALL_DIR' && uv run python manage.py migrate --noinput"

    log_success "Database migrations completed"
    update_status "migrations" "completed"
}

# Collect static files
collect_static() {
    update_status "static" "in_progress"
    log_info "Collecting static files..."

    run_as_user "cd '$INSTALL_DIR' && uv run python manage.py collectstatic --noinput"

    log_success "Static files collected"
    update_status "static" "completed"
}

# Ensure the NetworkManager / dnsmasq system configs the captive portal
# depends on are present and idempotent (port 53 for the wildcard dnsmasq,
# upstream DNS for the Pi, no connectivity checks that would cycle the hotspot).
ensure_nm_configs() {
    log_info "Ensuring NM/dnsmasq captive portal configs..."
    WIFI_DIR="/home/${SERVICE_USER}"

    if ! command -v dnsmasq &> /dev/null; then
        log_info "dnsmasq not found, installing..."
        apt-get install -y dnsmasq
        if [[ ! -f /etc/dnsmasq.conf.backup ]]; then
            cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup
        fi
    fi
    if ! command -v nft &> /dev/null; then
        log_info "nftables not found, installing..."
        apt-get install -y nftables
    fi
    if ! command -v iptables &> /dev/null; then
        log_info "iptables not found, installing iptables-nft wrapper..."
        apt-get install -y iptables
    fi

    # Wildcard DNS redirect config (idempotent)
    if ! grep -q "address=/#/10.42.0.1" /etc/dnsmasq.conf 2>/dev/null; then
        log_info "Configuring dnsmasq for captive portal..."
        cat << 'EOF' | tee -a /etc/dnsmasq.conf > /dev/null

# Tinko Captive Portal Configuration
address=/#/10.42.0.1
interface=wlan0
bind-interfaces
except-interface=lo
EOF
    fi
    grep -q "interface=wlan0" /etc/dnsmasq.conf 2>/dev/null || echo "interface=wlan0" | tee -a /etc/dnsmasq.conf > /dev/null
    grep -q "bind-interfaces" /etc/dnsmasq.conf 2>/dev/null || echo "bind-interfaces" | tee -a /etc/dnsmasq.conf > /dev/null
    grep -q "except-interface=lo" /etc/dnsmasq.conf 2>/dev/null || echo "except-interface=lo" | tee -a /etc/dnsmasq.conf > /dev/null

    # dnsmasq must only run in hotspot mode — never at boot.
    if systemctl is-enabled dnsmasq 2>/dev/null | grep -q "enabled"; then
        systemctl stop dnsmasq 2>/dev/null || true
        systemctl disable dnsmasq 2>/dev/null || true
        log_info "Disabled dnsmasq auto-start (will only run in hotspot mode)"
    fi

    # NM's internal dnsmasq must give up port 53 (DHCP only).
    mkdir -p /etc/NetworkManager/dnsmasq-shared.d
    if [[ ! -f /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf ]]; then
        echo "port=0" | tee /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf > /dev/null
        log_info "Disabled DNS on NetworkManager's internal dnsmasq (port 53 conflict prevention)"
    fi

    # Pi's own resolver must bypass any local dnsmasq.
    mkdir -p /etc/NetworkManager/conf.d
    if [[ ! -f /etc/NetworkManager/conf.d/dns-upstream.conf ]]; then
        tee /etc/NetworkManager/conf.d/dns-upstream.conf > /dev/null << 'EOF'
[global-dns-domain-*]
servers=8.8.8.8,8.8.4.4
EOF
        log_info "Configured NM to use upstream DNS (8.8.8.8) bypassing local dnsmasq"
    fi

    # systemd-resolved stub listener would hijack DNS to 127.0.0.53.
    if systemctl is-active --quiet systemd-resolved 2>/dev/null; then
        mkdir -p /etc/systemd/resolved.conf.d
        if [[ ! -f /etc/systemd/resolved.conf.d/no-stub.conf ]]; then
            tee /etc/systemd/resolved.conf.d/no-stub.conf > /dev/null << 'EOF'
[Resolve]
DNSStubListener=no
EOF
            systemctl restart systemd-resolved 2>/dev/null || true
            log_info "Disabled systemd-resolved stub listener (prevents 127.0.0.53 DNS hijack)"
        fi
    fi

    # No NM connectivity checks -> no hotspot cycling.
    mkdir -p /etc/NetworkManager/conf.d
    if [[ ! -f /etc/NetworkManager/conf.d/no-connectivity-check.conf ]]; then
        tee /etc/NetworkManager/conf.d/no-connectivity-check.conf > /dev/null << 'EOF'
[connectivity]
interval=0
EOF
        log_info "Disabled NetworkManager connectivity checks (prevents hotspot disconnects)"
    fi

    # TLS cert shared between portal HTTPS redirect and daphne HTTPS.
    if [[ ! -f /etc/tinko-portal/cert.pem ]] || [[ ! -f /etc/tinko-portal/key.pem ]]; then
        log_info "Generating self-signed TLS certificate for captive portal..."
        mkdir -p /etc/tinko-portal
        openssl req -x509 -newkey rsa:2048 -keyout /etc/tinko-portal/key.pem \
            -out /etc/tinko-portal/cert.pem -days 3650 -nodes \
            -subj "/CN=Tinko-Setup" 2>/dev/null
        chmod 644 /etc/tinko-portal/cert.pem
        chmod 600 /etc/tinko-portal/key.pem
        chown ${SERVICE_USER}:${SERVICE_USER} /etc/tinko-portal/key.pem
    fi

    # Cert must be readable by the service user (daphne runs as that user).
    chown ${SERVICE_USER}:${SERVICE_USER} /etc/tinko-portal/key.pem 2>/dev/null || true

    nmcli general reload 2>/dev/null || true
}

# Ensure tinko-wifi.service is installed and enabled, in sync with the
# version written by install-raspberry-pi.sh / update.sh.
ensure_wifi_service() {
    log_info "Ensuring WiFi setup service is present and enabled..."
    WIFI_DIR="/home/${SERVICE_USER}"

    if [[ ! -f "$WIFI_DIR/startup_check.sh" ]]; then
        log_warning "startup_check.sh not found in $WIFI_DIR, skipping service creation"
        return
    fi

    tee /etc/systemd/system/tinko-wifi.service > /dev/null << EOF
[Unit]
Description=Tinko Wi-Fi Captive Portal Check
After=NetworkManager.service
Before=tinko.service

[Service]
Type=oneshot
RemainAfterExit=no
ExecStart=/bin/bash $WIFI_DIR/startup_check.sh
User=root
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=120
StartLimitBurst=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable tinko-wifi.service
    log_success "WiFi setup service ensured and enabled"
}

# Update wifi-connect files
update_wifi_connect() {
    update_status "wifi_connect" "in_progress"
    log_info "Updating wifi-connect files..."

    # The daemon runs as root, so $HOME is /root — NOT the install user's
    # home. The tinko-wifi.service unit points at /home/<user>/startup_check.sh,
    # so wifi files MUST go to the service user's home or the boot-time portal
    # silently keeps running stale scripts.
    WIFI_DIR="/home/${SERVICE_USER}"

    if [[ ! -d "$INSTALL_DIR/wifi-connect" ]]; then
        log_warning "wifi-connect directory not found in repo, skipping"
        update_status "wifi_connect" "completed"
        return
    fi

    sudo cp "$INSTALL_DIR/wifi-connect/portal.py" "$WIFI_DIR/"
    sudo cp "$INSTALL_DIR/wifi-connect/startup_check.sh" "$WIFI_DIR/"
    sudo cp "$INSTALL_DIR/wifi-connect/wifi_worker.sh" "$WIFI_DIR/"

    sudo chmod +x "$WIFI_DIR/startup_check.sh"
    sudo chmod +x "$WIFI_DIR/wifi_worker.sh"

    # $USER is empty inside the root daemon — always use the service user.
    sudo chown ${SERVICE_USER}:${SERVICE_USER} "$WIFI_DIR/portal.py"
    sudo chown ${SERVICE_USER}:${SERVICE_USER} "$WIFI_DIR/startup_check.sh"
    sudo chown ${SERVICE_USER}:${SERVICE_USER} "$WIFI_DIR/wifi_worker.sh"

    ensure_nm_configs
    ensure_wifi_service

    log_success "wifi-connect files updated in $WIFI_DIR"
    update_status "wifi_connect" "completed"
}

# Compile translations
compile_translations() {
    update_status "translations" "in_progress"
    log_info "Compiling translations..."

    if ! run_as_user "cd '$INSTALL_DIR' && uv run django-admin compilemessages 2>/dev/null"; then
        log_warning "No project translations to compile"
    fi

    if [[ -f "$INSTALL_DIR/scripts/compile_translations.py" ]]; then
        run_as_user "cd '$INSTALL_DIR' && uv run python scripts/compile_translations.py" || log_warning "Plugin translations compile failed"
    fi

    log_success "Translations compiled"
    update_status "translations" "completed"
}

# Fix file ownership after root operations
# The daemon runs as root, so uv sync and git pull create files owned by root.
# The tinko service runs as a non-root user and can't access those files.
fix_ownership() {
    update_status "fix_ownership" "in_progress"
    log_info "Fixing file ownership for user $SERVICE_USER..."

    # Fix ownership of the project directory
    # .venv/ is critical (uv sync creates root-owned files)
    # .git/ needs fixing too (git pull as root creates root-owned objects)
    # staticfiles/ is created by collectstatic running as root
    chown -R "$SERVICE_USER:$SERVICE_USER" "$INSTALL_DIR"

    log_success "File ownership fixed"
    update_status "fix_ownership" "completed"
}

# Update Python capabilities for port 80 binding
# Redundant with AmbientCapabilities in tinko.service, kept as belt-and-suspenders.
update_python_capabilities() {
    update_status "set_capabilities" "in_progress"
    log_info "Updating Python capabilities for port 80 binding..."

    # Resolve the real interpreter path (uv/venv python is a symlink).
    PYTHON_BIN=$(run_as_user "cd '$INSTALL_DIR' && uv run python -c 'import sys; print(sys.executable)' 2>/dev/null")
    # setcap refuses symlinks, so resolve to the real binary underneath.
    PYTHON_BIN=$(realpath "$PYTHON_BIN" 2>/dev/null || echo "$PYTHON_BIN")
    if [[ -n "$PYTHON_BIN" && -f "$PYTHON_BIN" ]]; then
        if setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN" 2>/dev/null; then
            log_success "Capabilities set for $PYTHON_BIN"
        else
            # AmbientCapabilities in tinko.service already covers port 80;
            # setcap is belt-and-suspenders only, so it must never fail the update.
            log_warning "Could not set capabilities (non-fatal - AmbientCapabilities covers port 80)"
        fi
    else
        log_warning "Could not find Python binary to set capabilities"
        log_info "Daphne uses AmbientCapabilities, so this is non-fatal"
    fi
    update_status "set_capabilities" "completed"
}

# Ensure the tinko.service file is up to date.
# The update daemon runs as root but the tinko service must run as the
# service user. Mirrors update.sh's ensure_tinko_service, resolving
# user-specific paths from the service file.
ensure_tinko_service() {
    if [[ ! -f /etc/systemd/system/${SERVICE_NAME}.service ]]; then
        log_warning "tinko.service not found — skipping service file update"
        return
    fi

    # Ensure TLS key is readable by the service user (daphne reads it for HTTPS).
    sudo chown $SERVICE_USER /etc/tinko-portal/key.pem 2>/dev/null || true

    # Ensure TLS certificate exists (shared with captive portal)
    if [[ ! -f /etc/tinko-portal/cert.pem ]] || [[ ! -f /etc/tinko-portal/key.pem ]]; then
        log_info "Generating self-signed TLS certificate..."
        sudo mkdir -p /etc/tinko-portal
        sudo openssl req -x509 -newkey rsa:2048 -keyout /etc/tinko-portal/key.pem \
            -out /etc/tinko-portal/cert.pem -days 3650 -nodes \
            -subj "/CN=tinko.local" 2>/dev/null
        sudo chmod 644 /etc/tinko-portal/cert.pem
        sudo chmod 600 /etc/tinko-portal/key.pem
        sudo chown $SERVICE_USER /etc/tinko-portal/key.pem
    fi

    UV_PATH="$SERVICE_HOME/.local/bin/uv"

    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Tinko Educational Platform
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=$SERVICE_HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=${INSTALL_DIR}"
Environment="DJANGO_SETTINGS_MODULE=config.settings"
Environment="EDUPI_DEBUG=False"
ExecStartPre=${UV_PATH} run python manage.py collectstatic --noinput
ExecStart=${UV_PATH} run daphne -b 0.0.0.0 -p 80 -e ssl:443:privateKey=/etc/tinko-portal/key.pem:certKey=/etc/tinko-portal/cert.pem config.asgi:application
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=60

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    log_success "tinko.service updated (HTTP :80 + HTTPS :443)"
}

# Restart the service
restart_service() {
    update_status "restart_service" "in_progress"
    log_info "Restarting Tinko service..."

    # Reload systemd in case service file changed
    sudo systemctl daemon-reload

    # Wait for port 80 to be fully released (avoids crash-restart loop)
    log_info "Waiting for port 80 to be released..."
    for i in $(seq 1 15); do
        if ! sudo ss -tlnp 2>/dev/null | grep -q ":80\b"; then
            log_success "Port 80 is free"
            break
        fi
        if [[ "$i" -eq 15 ]]; then
            log_warning "Port 80 still in use after 15s, forcing start anyway"
        else
            sleep 1
        fi
    done

    sudo systemctl restart ${SERVICE_NAME}
    sleep 2

    if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
        SERVICE_RESTARTED=1
        log_success "Service restarted successfully!"
        update_status "restart_service" "completed"
    else
        log_error "Service failed to start."
        update_status "restart_service" "failed"
        exit 1
    fi
}

# Main update function
main() {
    echo
    echo "=========================================="
    echo "Tinko - Web Update Process"
    echo "=========================================="
    echo

    check_git_repo
    stop_service
    pull_latest
    update_dependencies
    fix_ownership
    update_python_capabilities
    run_migrations
    collect_static
    compile_translations
    update_wifi_connect
    ensure_tinko_service
    restart_service

    echo
    echo "Update process finished successfully."
}

# Handle script interruption
trap 'log_error "Update interrupted"; exit 1' INT TERM

# Run main function
main "$@"
