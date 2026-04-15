#!/bin/bash
#
# Tinko - Educational Raspberry Pi Platform - Uninstall Script
# Removes all services and configuration created by install-raspberry-pi.sh
#
# Usage: bash uninstall.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="tinko"
INSTALL_DIR="$(pwd)"

# Tracking what was removed
REMOVED_ITEMS=()
SKIPPED_ITEMS=()

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

# Ask user a yes/no question with a default
ask_yes_no() {
    local prompt="$1"
    local default="$2"  # "Y" or "N"

    if [[ "$default" == "Y" ]]; then
        prompt="$prompt (Y/n): "
    else
        prompt="$prompt (y/N): "
    fi

    read -p "$prompt" -n 1 -r
    echo

    if [[ -z "$REPLY" ]]; then
        REPLY="$default"
    fi

    if [[ "$REPLY" =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
}

# Remove a systemd service: stop, disable, remove file
remove_service() {
    local service_name="$1"
    local service_file="/etc/systemd/system/${service_name}.service"

    if systemctl list-unit-files | grep -q "${service_name}.service"; then
        log_info "Stopping ${service_name} service..."
        sudo systemctl stop "${service_name}" 2>/dev/null || true
        sudo systemctl disable "${service_name}" 2>/dev/null || true
        log_info "Removing ${service_file}..."
        sudo rm -f "$service_file"
        REMOVED_ITEMS+=("systemd service: ${service_name}")
    else
        log_info "${service_name}.service not found, skipping"
        SKIPPED_ITEMS+=("systemd service: ${service_name} (not found)")
    fi
}

# Remove a file if it exists, log result
remove_file() {
    local file_path="$1"
    local description="$2"

    if [[ -f "$file_path" ]]; then
        sudo rm -f "$file_path"
        REMOVED_ITEMS+=("$description")
    else
        SKIPPED_ITEMS+=("$description (not found)")
    fi
}

# Remove a directory if it exists, log result
remove_dir() {
    local dir_path="$1"
    local description="$2"

    if [[ -d "$dir_path" ]]; then
        sudo rm -rf "$dir_path"
        REMOVED_ITEMS+=("$description")
    else
        SKIPPED_ITEMS+=("$description (not found)")
    fi
}

# Step 1: Stop and remove systemd services
remove_systemd_services() {
    log_info "Removing systemd services..."

    remove_service "${SERVICE_NAME}"
    remove_service "tinko-wifi"
    remove_service "tinko-update"

    sudo systemctl daemon-reload
    log_success "Systemd services removed and daemon reloaded"
}

# Step 2: Remove WiFi scripts from home directory
remove_wifi_scripts() {
    log_info "Removing WiFi captive portal scripts..."

    WIFI_DIR="$HOME"

    remove_file "$WIFI_DIR/portal.py" "WiFi portal script"
    remove_file "$WIFI_DIR/startup_check.sh" "WiFi startup check script"
    remove_file "$WIFI_DIR/wifi_worker.sh" "WiFi worker script"
}

# Step 3: Remove TLS certificates
remove_tls_certs() {
    log_info "Removing TLS certificates..."

    remove_dir "/etc/tinko-portal" "TLS certificate directory"
}

# Step 4: Restore dnsmasq configuration
restore_dnsmasq() {
    log_info "Restoring dnsmasq configuration..."

    if [[ -f /etc/dnsmasq.conf.backup ]]; then
        log_info "Restoring from backup..."
        sudo cp /etc/dnsmasq.conf.backup /etc/dnsmasq.conf
        sudo rm -f /etc/dnsmasq.conf.backup
        REMOVED_ITEMS+=("dnsmasq config (restored from backup)")
    elif [[ -f /etc/dnsmasq.conf ]]; then
        # No backup exists — remove the appended Tinko lines manually
        log_info "No backup found. Removing Tinko captive portal lines from dnsmasq.conf..."
        sudo sed -i '/^# Tinko Captive Portal Configuration$/,+4d' /etc/dnsmasq.conf
        sudo sed -i '/^address=#\/#\/10\.42\.0\.1$/d' /etc/dnsmasq.conf
        sudo sed -i '/^interface=wlan0$/d' /etc/dnsmasq.conf
        sudo sed -i '/^bind-interfaces$/d' /etc/dnsmasq.conf
        sudo sed -i '/^except-interface=lo$/d' /etc/dnsmasq.conf
        REMOVED_ITEMS+=("dnsmasq config (Tinko lines removed)")
    else
        SKIPPED_ITEMS+=("dnsmasq config (not found)")
    fi

    # Re-enable dnsmasq auto-start if it was disabled by Tinko
    if command -v dnsmasq &>/dev/null; then
        log_info "Re-enabling dnsmasq system service..."
        sudo systemctl enable dnsmasq 2>/dev/null || true
        REMOVED_ITEMS+=("dnsmasq auto-start re-enabled")
    fi
}

# Step 5: Remove NetworkManager configuration drop-ins
remove_nm_config() {
    log_info "Removing NetworkManager configuration drop-ins..."

    remove_file "/etc/NetworkManager/dnsmasq-shared.d/no-dns.conf" "NM dnsmasq DNS disable"
    remove_file "/etc/NetworkManager/conf.d/dns-upstream.conf" "NM upstream DNS config"
    remove_file "/etc/NetworkManager/conf.d/no-connectivity-check.conf" "NM connectivity check disable"

    # Remove the directories if empty
    sudo rmdir /etc/NetworkManager/dnsmasq-shared.d/ 2>/dev/null || true

    # Restart NM to apply changes
    if systemctl is-active --quiet NetworkManager 2>/dev/null; then
        log_info "Restarting NetworkManager to apply config changes..."
        sudo systemctl restart NetworkManager
    fi
}

# Step 6: Remove systemd-resolved override
remove_resolved_config() {
    log_info "Removing systemd-resolved override..."

    remove_file "/etc/systemd/resolved.conf.d/no-stub.conf" "systemd-resolved stub listener override"
    sudo rmdir /etc/systemd/resolved.conf.d/ 2>/dev/null || true

    if systemctl is-active --quiet systemd-resolved 2>/dev/null; then
        log_info "Restarting systemd-resolved..."
        sudo systemctl restart systemd-resolved 2>/dev/null || true
    fi
}

# Step 7: Remove sudoers file
remove_sudoers() {
    log_info "Removing sudoers configuration..."

    remove_file "/etc/sudoers.d/tinko-update" "sudoers entry for tinko-update"
}

# Step 8: Remove update run directory
remove_run_dir() {
    log_info "Removing update run directory..."

    remove_dir "/run/tinko-update" "update status directory"
}

# Step 9: Remove GPIO group memberships
remove_gpio_groups() {
    if ask_yes_no "Remove user from gpio and spi groups?" "N"; then
        log_info "Removing group memberships..."

        sudo deluser "$USER" gpio 2>/dev/null || true
        sudo deluser "$USER" spi 2>/dev/null || true
        sudo deluser www-data gpio 2>/dev/null || true
        sudo deluser www-data spi 2>/dev/null || true

        REMOVED_ITEMS+=("gpio/spi group memberships")
        log_warning "Log out and back in for group changes to take effect"
    else
        SKIPPED_ITEMS+=("gpio/spi group memberships (user chose to keep)")
    fi
}

# Step 10: Optionally remove apt packages
remove_apt_packages() {
    # Tinko-specific packages that are unlikely to be used by other things
    local tinko_only_packages="dnsmasq nftables python3-flask"

    # Packages that may be shared with other applications
    local shared_packages="git python3 python3-pip python3-venv python3-dev libportaudio2 libsdl2-dev libsdl2-mixer-2.0-0 portaudio19-dev ffmpeg libespeak1 libasound2-dev curl build-essential pkg-config libjpeg-dev libpng-dev libfreetype6-dev liblcms2-dev libopenjp2-7-dev libtiff5-dev libwebp-dev libharfbuzz-dev libfribidi-dev wireless-tools alsa-utils libcap2-bin libatlas-base-dev"

    if ask_yes_no "Remove Tinko-specific apt packages (${tinko_only_packages})?" "Y"; then
        log_info "Removing Tinko-specific packages..."
        sudo apt-get remove -y $tinko_only_packages 2>/dev/null || true
        REMOVED_ITEMS+=("apt packages (Tinko-specific)")
    else
        SKIPPED_ITEMS+=("apt packages (user chose to keep)")
    fi

    if ask_yes_no "Remove shared apt packages (may affect other apps)?" "N"; then
        log_info "Removing shared packages..."
        sudo apt-get remove -y $shared_packages 2>/dev/null || true
        REMOVED_ITEMS+=("apt packages (shared)")
    else
        SKIPPED_ITEMS+=("apt packages (shared, user chose to keep)")
    fi

    sudo apt-get autoremove -y 2>/dev/null || true
}

# Step 11: Optionally remove .env and database
remove_app_data() {
    if [[ -f "$INSTALL_DIR/.env" ]]; then
        if ask_yes_no "Remove .env file?" "Y"; then
            rm -f "$INSTALL_DIR/.env"
            REMOVED_ITEMS+=(".env file")
        else
            SKIPPED_ITEMS+=(".env file (user chose to keep)")
        fi
    fi

    if [[ -f "$INSTALL_DIR/db.sqlite3" ]]; then
        if ask_yes_no "Delete database (db.sqlite3)? This is IRREVERSIBLE." "N"; then
            rm -f "$INSTALL_DIR/db.sqlite3"
            REMOVED_ITEMS+=("SQLite database")
        else
            SKIPPED_ITEMS+=("SQLite database (user chose to keep)")
        fi
    fi
}

# Step 12: Optionally remove project directory
remove_project_dir() {
    if ask_yes_no "Remove entire project directory (${INSTALL_DIR})?" "N"; then
        log_warning "This will delete ALL files in ${INSTALL_DIR}"
        read -p "Type 'yes' to confirm: " -r
        if [[ "$REPLY" == "yes" ]]; then
            cd /tmp
            rm -rf "$INSTALL_DIR"
            REMOVED_ITEMS+=("project directory")
        else
            SKIPPED_ITEMS+=("project directory (confirmation failed)")
        fi
    else
        SKIPPED_ITEMS+=("project directory (user chose to keep)")
    fi
}

# Print uninstall summary
print_summary() {
    echo
    echo "=========================================="
    echo -e "${GREEN}Tinko Uninstall Complete${NC}"
    echo "=========================================="
    echo

    if [[ ${#REMOVED_ITEMS[@]} -gt 0 ]]; then
        echo "Removed:"
        for item in "${REMOVED_ITEMS[@]}"; do
            echo -e "  ${RED}- $item${NC}"
        done
        echo
    fi

    if [[ ${#SKIPPED_ITEMS[@]} -gt 0 ]]; then
        echo "Skipped:"
        for item in "${SKIPPED_ITEMS[@]}"; do
            echo -e "  ${YELLOW}~ $item${NC}"
        done
        echo
    fi

    echo "Remaining manual steps (if applicable):"
    echo "  - Log out/in for group changes to take effect"
    echo "  - Verify WiFi works: ping google.com"
    echo "  - If dnsmasq was re-enabled and you don't need it:"
    echo "    sudo apt-get remove dnsmasq"
    echo
}

# Main uninstall function
main() {
    echo
    echo "=========================================="
    echo "Tinko - Uninstall Script"
    echo "=========================================="
    echo
    echo "This script will remove all Tinko services and configuration."
    echo "It will ask before removing potentially shared resources."
    echo
    echo "**WARNING**: This will stop the Tinko platform."
    echo "   The web interface will become inaccessible."
    echo

    if ! ask_yes_no "Continue with uninstall?" "N"; then
        log_info "Uninstall cancelled"
        exit 0
    fi

    check_root

    remove_systemd_services
    remove_wifi_scripts
    remove_tls_certs
    restore_dnsmasq
    remove_nm_config
    remove_resolved_config
    remove_sudoers
    remove_run_dir
    remove_gpio_groups
    remove_apt_packages
    remove_app_data
    remove_project_dir

    print_summary
}

# Handle script interruption
trap 'log_error "Uninstall interrupted"; exit 1' INT TERM

# Run main function
main "$@"