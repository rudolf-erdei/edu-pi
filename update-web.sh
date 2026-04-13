#!/bin/bash
#
# Tinko - Educational Raspberry Pi Platform - Web Update Script
# This script is used by the tinko-update.service to update the system
#
# Usage: TINKO_UPDATE_DAEMON=1 ./update-web.sh

set -e

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

# Determine the service user from the service file
SERVICE_USER=$(grep '^User=' /etc/systemd/system/tinko.service 2>/dev/null | cut -d= -f2)
if [[ -z "$SERVICE_USER" || "$SERVICE_USER" == "root" ]]; then
    SERVICE_USER="tinko"
fi

# Telemetry function for the daemon
update_status() {
    if [[ "$TINKO_UPDATE_DAEMON" == "1" ]]; then
        local stage=$1
        local status=$2
        # Use a temporary file and mv for atomic writes
        # Note: The daemon typically manages the JSON structure,
        # but the script provides the current stage.
        echo "{\"stage\": \"$stage\", \"status\": \"$status\", \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" > "${STATUS_FILE}.tmp"
        mv "${STATUS_FILE}.tmp" "$STATUS_FILE"
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

    cd "$INSTALL_DIR"

    if [[ -n $(git status --porcelain) ]]; then
        log_warning "Local changes detected. Stashing them..."
        git stash
    fi

    if git pull; then
        log_success "Latest changes pulled successfully"
    else
        log_error "Failed to pull latest changes"
        update_status "pull" "failed"
        exit 1
    fi
    update_status "pull" "completed"
}

# Update Python dependencies
update_dependencies() {
    update_status "dependencies" "in_progress"
    log_info "Updating Python dependencies..."

    cd "$INSTALL_DIR"

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
    update_status "static" "in_progress"
    log_info "Collecting static files..."

    cd "$INSTALL_DIR"
    uv run python manage.py collectstatic --noinput

    log_success "Static files collected"
    update_status "static" "completed"
}

# Update wifi-connect files
update_wifi_connect() {
    update_status "wifi_connect" "in_progress"
    log_info "Updating wifi-connect files..."

    WIFI_DIR="$HOME"

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

    sudo chown $USER:$USER "$WIFI_DIR/portal.py"
    sudo chown $USER:$USER "$WIFI_DIR/startup_check.sh"
    sudo chown $USER:$USER "$WIFI_DIR/wifi_worker.sh"

    log_success "wifi-connect files updated in $WIFI_DIR"
    update_status "wifi_connect" "completed"
}

# Compile translations
compile_translations() {
    update_status "translations" "in_progress"
    log_info "Compiling translations..."

    cd "$INSTALL_DIR"

    uv run django-admin compilemessages 2>/dev/null || log_warning "No project translations to compile"

    if [[ -f scripts/compile_translations.py ]]; then
        uv run python scripts/compile_translations.py
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
# Must run AFTER fix_ownership because chown strips file capabilities.
# After uv sync, the Python binary may change, so setcap must be reapplied.
update_python_capabilities() {
    update_status "set_capabilities" "in_progress"
    log_info "Updating Python capabilities for port 80 binding..."

    PYTHON_BIN=$(cd "$INSTALL_DIR" && uv run which python 2>/dev/null || true)
    if [[ -n "$PYTHON_BIN" && -f "$PYTHON_BIN" ]]; then
        setcap 'cap_net_bind_service=+ep' "$PYTHON_BIN"
        log_success "Capabilities set for $PYTHON_BIN"
    else
        log_warning "Could not find Python binary to set capabilities"
        log_info "Daphne may not be able to bind to port 80"
    fi
    update_status "set_capabilities" "completed"
}

# Restart the service
restart_service() {
    update_status "restart_service" "in_progress"
    log_info "Restarting Tinko service..."

    sudo systemctl daemon-reload
    sudo systemctl start ${SERVICE_NAME}
    sleep 2

    if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
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
    restart_service

    echo
    echo "Update process finished successfully."
}

# Handle script interruption
trap 'log_error "Update interrupted"; exit 1' INT TERM

# Run main function
main "$@"
