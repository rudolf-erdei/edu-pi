#!/bin/bash
#
# Tinko - Educational Raspberry Pi Platform - Update Script
# This script updates Tinko to the latest version from git
#
# Usage: ./update.sh
#

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
INSTALL_DIR="$(pwd)"
SERVICE_NAME="tinko"
STATUS_FILE="/run/tinko-update/status.json"

# Telemetry function for the daemon
update_status() {
    if [[ "$TINKO_UPDATE_DAEMON" == "1" ]]; then
        local stage=$1
        local status=$2
        # Use a temporary file and mv for atomic writes
        echo "{\"stage\": \"$stage\", \"status\": \"$status\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > "${STATUS_FILE}.tmp"
        mv "${STATUS_FILE}.tmp" "$STATUS_FILE"
    fi
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
$USER ALL=(All) NOPASSWD: /usr/bin/systemctl start tinko
$USER ALL=(All) NOPASSWD: /usr/bin/mkdir -p /run/tinko-update
$USER ALL=(All) NOPASSWD: /usr/bin/chmod 777 /run/tinko-update
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

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable tinko-update.service

    # Start the service if not running
    if ! sudo systemctl is-active --quiet tinko-update.service; then
        sudo systemctl start tinko-update.service
    fi

    log_success "Update infrastructure set up successfully"
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

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        # Allow root if run by the update daemon
        if [[ "$TINKO_UPDATE_DAEMON" == "1" ]]; then
            return 0
        fi
        log_error "This script should not be run as root/sudo"
        log_info "It will use sudo when necessary. Please run as normal user."
        exit 1
    fi
}

# Check if we're in a git repository
check_git_repo() {
    if [[ ! -d .git ]]; then
        log_error "Not a git repository. Please run this from the Tinko installation directory."
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
                log_error "Failed to stop service. Please stop it manually:"
                log_info "  sudo systemctl stop ${SERVICE_NAME}"
                update_status "stop_service" "failed"
                exit 1
            fi
            log_success "Service stopped"
        else
            log_info "Service is not running"
        fi
    else
        log_warning "Tinko service not found. Is it installed?"
    fi
    update_status "stop_service" "completed"
}

# Pull latest changes from git
pull_latest() {
    update_status "pull" "in_progress"
    log_info "Pulling latest changes from git..."

    cd "$INSTALL_DIR"

    # Prevent git from prompting for credentials (hangs in non-interactive scripts)
    export GIT_TERMINAL_PROMPT=0

    # Stash any local changes
    STASHED=0
    if [[ -n $(git status --porcelain) ]]; then
        log_warning "Local changes detected. Stashing them..."
        git stash
        STASHED=1
    fi

    # Pull latest changes (timeout prevents hanging on network issues)
    if timeout 60 git pull; then
        log_success "Latest changes pulled successfully"
        # Show what was updated
        log_info "Latest commits:"
        git log --oneline -5
        update_status "pull" "completed"
    else
        log_warning "Failed to pull (no internet or network error). Continuing with current version."
        # Restore stashed changes since we didn't pull anything new
        if [[ "$STASHED" -eq 1 ]]; then
            log_info "Restoring stashed local changes..."
            git stash pop 2>/dev/null || true
        fi
        update_status "pull" "skipped"
    fi
}

# Update Python dependencies
update_dependencies() {
    update_status "dependencies" "in_progress"
    log_info "Updating Python dependencies..."

    cd "$INSTALL_DIR"

    # Sync all dependencies including extras
    # Use --all-extras to ensure all optional dependencies are installed
    if [[ -f /proc/device-tree/model ]] && grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        log_info "Installing all dependencies including Pi-specific extras..."
        uv sync --all-extras
    else
        log_info "Installing dependencies..."
        uv sync
    fi

    log_success "Dependencies updated"
    update_status "dependencies" "completed"
}

# Run database migrations
run_migrations() {
    update_status "migrations" "in_progress"
    log_info "Running database migrations..."

    cd "$INSTALL_DIR"
    uv run python manage.py migrate --noinput

    log_success "Database migrations completed"
    update_status "migrations" "completed"
}

# Collect static files
collect_static() {
    log_info "Collecting static files..."

    cd "$INSTALL_DIR"
    uv run python manage.py collectstatic --noinput

    log_success "Static files collected"
}

# Ensure WiFi setup service is installed and enabled
ensure_wifi_service() {
    log_info "Ensuring WiFi setup service is present and enabled..."

    WIFI_DIR="$HOME"
    if [[ ! -f "$WIFI_DIR/startup_check.sh" ]]; then
        log_warning "startup_check.sh not found in $WIFI_DIR, skipping service creation"
        return
    fi

    # Grant Python permission to bind to privileged port 80
    # Since this is an update, the python binary might have changed
    PYTHON_BIN=$(uv run which python)
    if [[ -n "$PYTHON_BIN" ]]; then
        log_info "Updating capabilities for $PYTHON_BIN to allow port 80..."
        sudo setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"
    fi

    sudo tee /etc/systemd/system/tinko-wifi.service > /dev/null << EOF
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
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable tinko-wifi.service
    log_success "WiFi setup service ensured and enabled"
}

# Update wifi-connect files
update_wifi_connect() {
    log_info "Updating wifi-connect files..."

    WIFI_DIR="$HOME"

    # Check if wifi-connect directory exists in the repo
    if [[ ! -d "$INSTALL_DIR/wifi-connect" ]]; then
        log_warning "wifi-connect directory not found in repo, skipping"
        return
    fi

    # Copy wifi-connect files to home directory
    sudo cp "$INSTALL_DIR/wifi-connect/portal.py" "$WIFI_DIR/"
    sudo cp "$INSTALL_DIR/wifi-connect/startup_check.sh" "$WIFI_DIR/"
    sudo cp "$INSTALL_DIR/wifi-connect/wifi_worker.sh" "$WIFI_DIR/"

    # Make shell scripts executable
    sudo chmod +x "$WIFI_DIR/startup_check.sh"
    sudo chmod +x "$WIFI_DIR/wifi_worker.sh"

    # Set ownership to current user
    sudo chown $USER:$USER "$WIFI_DIR/portal.py"
    sudo chown $USER:$USER "$WIFI_DIR/startup_check.sh"
    sudo chown $USER:$USER "$WIFI_DIR/wifi_worker.sh"

    # Ensure dnsmasq is installed
    if ! command -v dnsmasq &> /dev/null; then
        log_info "dnsmasq not found, installing..."
        sudo apt-get install -y dnsmasq

        # Back up original config if no backup exists
        if [[ ! -f /etc/dnsmasq.conf.backup ]]; then
            sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup
        fi
    fi

    # Ensure captive portal DNS configuration is present (needed for older systems too)
    if ! grep -q "address=/#/10.42.0.1" /etc/dnsmasq.conf 2>/dev/null; then
        log_info "Configuring dnsmasq for captive portal..."
        cat << 'EOF' | sudo tee -a /etc/dnsmasq.conf > /dev/null

# Tinko Captive Portal Configuration
address=/#/10.42.0.1
interface=wlan0
bind-interfaces
EOF
    else
        # Config exists — make sure all three directives are present
        if ! grep -q "interface=wlan0" /etc/dnsmasq.conf 2>/dev/null; then
            echo "interface=wlan0" | sudo tee -a /etc/dnsmasq.conf > /dev/null
        fi
        if ! grep -q "bind-interfaces" /etc/dnsmasq.conf 2>/dev/null; then
            echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf > /dev/null
        fi
    fi

    # Ensure dnsmasq is running
    if command -v systemctl &> /dev/null; then
        if ! systemctl is-active --quiet dnsmasq 2>/dev/null; then
            log_warning "dnsmasq is not running, restarting..."
            sudo systemctl restart dnsmasq
        fi
    fi

    # Disable DNS on NetworkManager's internal dnsmasq to prevent port 53 conflict.
    # NM runs its own dnsmasq for shared connections which binds to port 53 on the hotspot IP.
    # Our standalone dnsmasq needs port 53 for captive portal DNS redirection (address=/#/).
    sudo mkdir -p /etc/NetworkManager/dnsmasq-shared.d/
    if [[ ! -f /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf ]]; then
        echo "port=0" | sudo tee /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf > /dev/null
        log_info "Disabled DNS on NetworkManager's internal dnsmasq (port 53 conflict prevention)"
    fi

    # Disable NetworkManager's periodic connectivity checks.
    # These checks can cause WiFi disconnects in hotspot mode by detecting
    # no internet and attempting to reconfigure the interface.
    sudo mkdir -p /etc/NetworkManager/conf.d/
    if [[ ! -f /etc/NetworkManager/conf.d/no-connectivity-check.conf ]]; then
        sudo tee /etc/NetworkManager/conf.d/no-connectivity-check.conf > /dev/null << 'EOF'
[connectivity]
interval=0
EOF
        log_info "Disabled NetworkManager connectivity checks (prevents hotspot disconnects)"
    fi

    # Check for dnsmasq version with known wildcard DNS bug
    DNSMASQ_VERSION=$(dnsmasq --version 2>/dev/null | head -1 | grep -oP '\d+\.\d+' | head -1)
    if [[ "$DNSMASQ_VERSION" == "2.86" ]]; then
        log_warning "dnsmasq 2.86 has a known bug with address=/#/ wildcard DNS redirection. Consider upgrading."
    fi

    # Ensure TLS certificate exists for HTTPS captive portal checks
    if [[ ! -f /etc/tinko-portal/cert.pem ]] || [[ ! -f /etc/tinko-portal/key.pem ]]; then
        log_info "Generating self-signed TLS certificate for captive portal..."
        sudo mkdir -p /etc/tinko-portal
        sudo openssl req -x509 -newkey rsa:2048 -keyout /etc/tinko-portal/key.pem \
            -out /etc/tinko-portal/cert.pem -days 3650 -nodes \
            -subj "/CN=Tinko-Setup" 2>/dev/null
        sudo chmod 644 /etc/tinko-portal/cert.pem
        sudo chmod 600 /etc/tinko-portal/key.pem
        log_success "TLS certificate generated"
    fi

    ensure_wifi_service

    log_success "wifi-connect files updated in $WIFI_DIR"
}

# Compile translations
compile_translations() {
    log_info "Compiling translations..."
    
    cd "$INSTALL_DIR"
    
    # Compile project translations
    uv run django-admin compilemessages 2>/dev/null || log_warning "No project translations to compile"
    
    # Compile plugin translations
    if [[ -f scripts/compile_translations.py ]]; then
        uv run python scripts/compile_translations.py
    fi
    
    log_success "Translations compiled"
}

# Update Python capabilities for port 80 binding
# After uv sync, the Python binary may change and setcap must be reapplied.
# This is separate from the wifi section's setcap because this is always needed.
update_python_capabilities() {
    log_info "Updating Python capabilities for port 80 binding..."

    PYTHON_BIN=$(uv run which python 2>/dev/null || true)
    if [[ -n "$PYTHON_BIN" && -f "$PYTHON_BIN" ]]; then
        sudo setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"
        log_success "Capabilities set for $PYTHON_BIN"
    else
        log_warning "Could not find Python binary to set capabilities"
        log_info "Daphne may not be able to bind to port 80"
    fi
}

# Restart the service
restart_service() {
    update_status "restart_service" "in_progress"
    log_info "Restarting Tinko service..."

    # Reload systemd in case service file changed
    sudo systemctl daemon-reload

    sudo systemctl start ${SERVICE_NAME}
    sleep 2

    if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
        SERVICE_RESTARTED=1
        log_success "Service restarted successfully!"
        update_status "restart_service" "completed"

        # Verify network binding
        log_info "Verifying network binding..."
        sleep 2

        if sudo netstat -tlnp 2>/dev/null | grep -q ":80.*0.0.0.0"; then
            log_success "Service is accessible from other devices on port 80"
        elif sudo ss -tlnp 2>/dev/null | grep -q ":80.*0.0.0.0"; then
            log_success "Service is accessible from other devices on port 80"
        elif sudo netstat -tlnp 2>/dev/null | grep -q "127.0.0.1:80"; then
            log_warning "Service is only listening on localhost (127.0.0.1:80)"
            log_info "This may mean the service file needs updating."
        fi
    else
        log_error "Service failed to start. Check logs with:"
        log_info "  sudo journalctl -u ${SERVICE_NAME} -f"
        update_status "restart_service" "failed"
        exit 1
    fi
}

# Print update summary
print_summary() {
    PI_IP=$(hostname -I | awk '{print $1}')
    
    echo
    echo "=========================================="
    echo -e "${GREEN}Tinko Update Complete!${NC}"
    echo "=========================================="
    echo
    echo "Tinko has been updated to the latest version."
    echo
    echo "Access Tinko at:"
    echo "  - Dashboard:       http://${PI_IP}:/"
    echo "  - Admin Panel:     http://${PI_IP}:/admin/"
    echo "  - Noise Monitor:   http://${PI_IP}:/plugins/edupi/noise_monitor/"
    echo "  - Routines:        http://${PI_IP}:/plugins/edupi/routines/"
    echo "  - Activity Timer:  http://${PI_IP}:/plugins/edupi/activity_timer/"
    echo "  - Touch Piano:     http://${PI_IP}:/plugins/edupi/touch_piano/"
    echo
    echo "Service commands:"
    echo "  sudo systemctl status ${SERVICE_NAME}"
    echo "  sudo systemctl restart ${SERVICE_NAME}"
    echo "  sudo journalctl -u ${SERVICE_NAME} -f"
    echo
}

# Main update function
main() {
    echo
    echo "=========================================="
    echo "Tinko - Update Script"
    echo "=========================================="
    echo
    
    check_root
    check_git_repo
    stop_service
    pull_latest
    update_dependencies
    update_python_capabilities
    run_migrations
    collect_static
    compile_translations
    update_wifi_connect
    restart_service
    print_summary
}

# Handle script interruption
trap 'log_error "Update interrupted"; exit 1' INT TERM

# Run main function
main "$@"
