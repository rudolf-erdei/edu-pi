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

# Step 7: Remove sudoers files and the power helper they grant
remove_sudoers() {
    log_info "Removing sudoers configuration..."

    remove_file "/etc/sudoers.d/tinko-update" "sudoers entry for tinko-update"
    remove_file "/etc/sudoers.d/tinko-poweroff" "sudoers entry for the power button"
    remove_file "/usr/local/sbin/tinko-poweroff" "dashboard power button helper"
}

# Step 7b: Remove the journald drop-in that made the journal persistent
remove_journal_config() {
    log_info "Removing journald configuration..."

    if [ -f /etc/systemd/journald.conf.d/tinko.conf ]; then
        remove_file "/etc/systemd/journald.conf.d/tinko.conf" "journald persistent-storage drop-in"
        sudo rmdir /etc/systemd/journald.conf.d/ 2>/dev/null || true
        sudo systemctl restart systemd-journald 2>/dev/null || true
    fi

    # /var/log/journal itself is left in place: it holds the log history, and it
    # is systemd's own directory rather than something Tinko owns.
}

# Step 7c: Remove the timesyncd drop-in that tightened the retry interval
remove_timesync_config() {
    log_info "Removing timesync configuration..."

    if [ -f /etc/systemd/timesyncd.conf.d/tinko.conf ]; then
        remove_file "/etc/systemd/timesyncd.conf.d/tinko.conf" "timesyncd retry drop-in"
        sudo rmdir /etc/systemd/timesyncd.conf.d/ 2>/dev/null || true
        sudo systemctl restart systemd-timesyncd 2>/dev/null || true
    fi

    # The clock itself is left alone: NTP is on by default on this image with or
    # without Tinko, and stopping it would leave the Pi with no time source.
}

# Step 7d: Undo the SD card write reductions (scripts/update_infra.sh)
#
# The counterpart of optimize_for_sd_card(). Every step here is the reverse of
# one there, and each one is checked before it acts rather than assuming Tinko's
# change is still the only thing in the file.
#
# fstab is restored from the copy taken before the first edit, because the edit
# is inside a line of a table that must stay parseable -- the file we know was
# good beats a rewritten one. It is only restored if the only thing that has
# changed since is our commit= option; otherwise the backup is kept beside it and
# the admin is told, since an unrelated edit made after install would be lost.
#
# config.txt is the opposite: the block was appended whole, so the lines are
# removed by name and the rewrite is only written if exactly those lines were
# found. The bare [all] header stays -- it clears config.txt's board filter, so
# it cannot change how anything else in the file is read.
#
# log2ram is deliberately left installed: it is a general-purpose package that
# keeps /var/log in RAM, and removing it while its tmpfs is mounted over
# /var/log is more risk than the disk space it costs. The summary says so.
remove_sd_optimizations() {
    log_info "Undoing the SD card write reductions..."

    local boot_config="/boot/firmware/config.txt"

    # 1. /var/tmp back onto the disk, if Tinko is what put it in RAM.
    if [ -f /etc/systemd/system/var-tmp.mount ]; then
        sudo systemctl disable --now var-tmp.mount 2>/dev/null || true
        remove_file "/etc/systemd/system/var-tmp.mount" "Tinko's /var/tmp RAM mount"
        sudo systemctl daemon-reload 2>/dev/null || true
    else
        SKIPPED_ITEMS+=("Tinko's /var/tmp RAM mount (not found)")
    fi

    # 2. The writeback sysctl drop-in.
    if [ -f /etc/sysctl.d/99-tinko-sd.conf ]; then
        remove_file "/etc/sysctl.d/99-tinko-sd.conf" "Tinko's writeback sysctl drop-in"
        sudo sysctl --system >/dev/null 2>&1 || true
    else
        SKIPPED_ITEMS+=("Tinko's writeback sysctl drop-in (not found)")
    fi

    # 3. The fstab commit= option, from the copy taken before the first edit.
    if [ -f /etc/fstab.tinko-bak ]; then
        if grep -q 'commit=' /etc/fstab && ! grep -q 'commit=' /etc/fstab.tinko-bak; then
            sudo install -o root -g root -m 0644 /etc/fstab.tinko-bak /etc/fstab
            REMOVED_ITEMS+=("commit= option in /etc/fstab")
            if command -v findmnt >/dev/null 2>&1 &&
                ! sudo findmnt --verify --tab-file /etc/fstab >/dev/null 2>&1; then
                log_error "/etc/fstab does not pass findmnt --verify; check it before rebooting"
            fi
            remove_file "/etc/fstab.tinko-bak" "fstab backup"
        else
            log_warning "/etc/fstab has changed since Tinko edited it; leaving both files alone"
            log_warning "  Tinko's option is in /etc/fstab, the pre-Tinko copy is /etc/fstab.tinko-bak"
            SKIPPED_ITEMS+=("commit= option in /etc/fstab (edited since; check by hand)")
        fi
    else
        SKIPPED_ITEMS+=("commit= option in /etc/fstab (no backup found)")
    fi

    # 4. The Bluetooth overlay, by removing the two lines this installed.
    if [ -f "$boot_config" ] && grep -qE '^[[:space:]]*dtoverlay=disable-bt([[:space:]]|$)' "$boot_config"; then
        local removed_lines
        removed_lines=$(grep -cE '^(# Tinko: Bluetooth off|[[:space:]]*dtoverlay=disable-bt([[:space:]]|$))' "$boot_config")
        if [ "$removed_lines" -eq 2 ]; then
            local stripped
            stripped="$(mktemp)"
            grep -vE '^(# Tinko: Bluetooth off|[[:space:]]*dtoverlay=disable-bt([[:space:]]|$))' \
                "$boot_config" > "$stripped"
            if [ -s "$stripped" ] && sudo install -o root -g root -m 0644 "$stripped" "$boot_config"; then
                REMOVED_ITEMS+=("Bluetooth overlay in $boot_config")
            else
                log_error "Could not rewrite $boot_config; leaving it alone"
                SKIPPED_ITEMS+=("Bluetooth overlay in $boot_config (rewrite failed)")
            fi
            rm -f "$stripped"
        else
            log_warning "$boot_config has $removed_lines of Tinko's Bluetooth lines, not 2; leaving it alone"
            SKIPPED_ITEMS+=("Bluetooth overlay in $boot_config ($removed_lines line(s); check by hand)")
        fi
        remove_file "${boot_config}.tinko-bak" "config.txt backup"
    else
        SKIPPED_ITEMS+=("Bluetooth overlay in $boot_config (not found)")
    fi

    # 5. The services and timers, back on.
    local unit
    for unit in bluetooth.service hciuart.service apt-daily.timer apt-daily-upgrade.timer; do
        if systemctl list-unit-files "$unit" >/dev/null 2>&1 &&
            ! systemctl is-enabled --quiet "$unit" 2>/dev/null; then
            if sudo systemctl enable --now "$unit" >/dev/null 2>&1; then
                REMOVED_ITEMS+=("disabled ${unit} (re-enabled)")
            else
                SKIPPED_ITEMS+=("could not re-enable ${unit}")
            fi
        fi
    done

    # 6. The zram writeback drop-in, and unmask in case that is what was used.
    if [ -f /etc/rpi/swap.conf.d/tinko.conf ]; then
        remove_file "/etc/rpi/swap.conf.d/tinko.conf" "Tinko's zram writeback drop-in"
        sudo rmdir /etc/rpi/swap.conf.d 2>/dev/null || true
    else
        SKIPPED_ITEMS+=("Tinko's zram writeback drop-in (not found)")
    fi
    if systemctl is-enabled rpi-zram-writeback.timer 2>/dev/null | grep -qx masked; then
        sudo systemctl unmask rpi-zram-writeback.timer 2>/dev/null || true
        REMOVED_ITEMS+=("mask on rpi-zram-writeback.timer")
    fi
    sudo systemctl daemon-reload 2>/dev/null || true

    log_warning "log2ram is left installed: it keeps /var/log in RAM and other things benefit too"
    log_warning "  remove it with: sudo apt-get remove log2ram"
    log_warning "Bluetooth and the commit= interval take effect at the next reboot"
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
    remove_journal_config
    remove_timesync_config
    remove_sd_optimizations
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