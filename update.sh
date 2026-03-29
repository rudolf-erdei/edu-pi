#!/bin/bash
#
# Tinko - Educational Raspberry Pi Platform - Update Script
# This script updates Tinko to the latest version from git
#
# Usage: ./update.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$(pwd)"
SERVICE_NAME="tinko"

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
    log_info "Checking if Tinko service is running..."
    
    if systemctl list-unit-files | grep -q "${SERVICE_NAME}.service"; then
        if sudo systemctl is-active --quiet ${SERVICE_NAME} 2>/dev/null; then
            log_info "Stopping Tinko service..."
            sudo systemctl stop ${SERVICE_NAME}
            sleep 2
            
            if sudo systemctl is-active --quiet ${SERVICE_NAME} 2>/dev/null; then
                log_error "Failed to stop service. Please stop it manually:"
                log_info "  sudo systemctl stop ${SERVICE_NAME}"
                exit 1
            fi
            log_success "Service stopped"
        else
            log_info "Service is not running"
        fi
    else
        log_warning "Tinko service not found. Is it installed?"
    fi
}

# Pull latest changes from git
pull_latest() {
    log_info "Pulling latest changes from git..."
    
    cd "$INSTALL_DIR"
    
    # Stash any local changes
    if [[ -n $(git status --porcelain) ]]; then
        log_warning "Local changes detected. Stashing them..."
        git stash
    fi
    
    # Pull latest changes
    if git pull; then
        log_success "Latest changes pulled successfully"
    else
        log_error "Failed to pull latest changes"
        exit 1
    fi
    
    # Show what was updated
    log_info "Latest commits:"
    git log --oneline -5
}

# Update Python dependencies
update_dependencies() {
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
}

# Run database migrations
run_migrations() {
    log_info "Running database migrations..."
    
    cd "$INSTALL_DIR"
    uv run python manage.py migrate --noinput
    
    log_success "Database migrations completed"
}

# Collect static files
collect_static() {
    log_info "Collecting static files..."
    
    cd "$INSTALL_DIR"
    uv run python manage.py collectstatic --noinput
    
    log_success "Static files collected"
}

# Compile translations
compile_translations() {
    log_info "Compiling translations..."
    
    cd "$INSTALL_DIR"
    
    # Compile project translations
    uv run django-admin compilemessages 2>/dev/null || log_warning "No project translations to compile"
    
    # Compile plugin translations
    if [[ -f scripts/compile_translations.py ]]; then
        python3 scripts/compile_translations.py
    fi
    
    log_success "Translations compiled"
}

# Restart the service
restart_service() {
    log_info "Restarting Tinko service..."
    
    # Reload systemd in case service file changed
    sudo systemctl daemon-reload
    
    sudo systemctl start ${SERVICE_NAME}
    sleep 2
    
    if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
        log_success "Service restarted successfully!"
        
        # Verify network binding
        log_info "Verifying network binding..."
        sleep 2
        
        if sudo netstat -tlnp 2>/dev/null | grep -q ":8000.*0.0.0.0"; then
            log_success "Service is accessible from other devices on port 8000"
        elif sudo ss -tlnp 2>/dev/null | grep -q ":8000.*0.0.0.0"; then
            log_success "Service is accessible from other devices on port 8000"
        elif sudo netstat -tlnp 2>/dev/null | grep -q "127.0.0.1:8000"; then
            log_warning "Service is only listening on localhost (127.0.0.1:8000)"
            log_info "This may mean the service file needs updating."
        fi
    else
        log_error "Service failed to start. Check logs with:"
        log_info "  sudo journalctl -u ${SERVICE_NAME} -f"
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
    echo "  - Dashboard:       http://${PI_IP}:8000/"
    echo "  - Admin Panel:     http://${PI_IP}:8000/admin/"
    echo "  - Noise Monitor:   http://${PI_IP}:8000/plugins/edupi/noise_monitor/"
    echo "  - Routines:        http://${PI_IP}:8000/plugins/edupi/routines/"
    echo "  - Activity Timer:  http://${PI_IP}:8000/plugins/edupi/activity_timer/"
    echo "  - Touch Piano:     http://${PI_IP}:8000/plugins/edupi/touch_piano/"
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
    run_migrations
    collect_static
    compile_translations
    restart_service
    print_summary
}

# Handle script interruption
trap 'log_error "Update interrupted"; exit 1' INT TERM

# Run main function
main "$@"
