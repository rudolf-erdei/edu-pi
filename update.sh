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
# The daemon owns status.json; scripts only report the current stage.
STAGE_FILE="/run/tinko-update/stage.json"

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

# --- Self-update guard ----------------------------------------------------
#
# bash reads a running script from its open file descriptor. `git pull`
# replaces update.sh via an atomic rename (new inode), so without this the
# in-flight run keeps executing the PRE-pull function bodies: any change this
# script makes to its own logic silently waits for the NEXT run. Observed
# 2026-09-26 — update.js deployed (data, read later by collectstatic) while
# the systemd unit blocks and the dnsutils guard did not (code, already
# parsed before the pull).
#
# Record the digest at startup, then re-exec once after the pull if it moved.
SCRIPT_PATH="$(readlink -f "$0" 2>/dev/null || echo "$0")"
SCRIPT_ARGS=("$@")

script_digest() {
    if command -v sha256sum &> /dev/null; then
        sha256sum "$1" 2>/dev/null | awk '{print $1}'
    elif command -v md5sum &> /dev/null; then
        md5sum "$1" 2>/dev/null | awk '{print $1}'
    fi
}

SCRIPT_DIGEST_AT_START="$(script_digest "$SCRIPT_PATH" || true)"

reexec_if_self_changed() {
    # The re-executed run must never re-exec again, or a script that keeps
    # changing would loop forever.
    if [[ "${TINKO_UPDATE_REEXEC:-0}" == "1" ]]; then
        return 0
    fi

    local now
    now="$(script_digest "$SCRIPT_PATH" || true)"

    if [[ -z "$now" || -z "$SCRIPT_DIGEST_AT_START" || "$now" == "$SCRIPT_DIGEST_AT_START" ]]; then
        return 0
    fi

    log_warning "update.sh was replaced by the pull — this run is still on the old copy."
    log_info "Re-executing with the new version so its changes take effect now..."

    export TINKO_UPDATE_REEXEC=1
    # exec replaces this process, so the EXIT trap does NOT fire and the
    # emergency handler stays out of the way. The new run restarts the
    # service exactly as this one would have.
    exec /bin/bash "$SCRIPT_PATH" "${SCRIPT_ARGS[@]}"
}

# Load update infrastructure setup (tinko-update.service daemon install)
# Requires INSTALL_DIR and the log functions above.
# shellcheck source=scripts/update_infra.sh
source "$INSTALL_DIR/scripts/update_infra.sh"

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

# --- Live database protection ---------------------------------------------
#
# db.sqlite3 is written by the running app, so it is ALWAYS dirty when an
# update runs. git must never stash, merge or check out that file: doing so
# replaces the teacher's live data with whatever was last committed. The
# database is therefore moved out of the working tree for the duration of the
# pull and put back afterwards, on every path.
#
# This is also what makes it safe to stop tracking the database at all: the
# commit that untracks it would otherwise make the merge delete the live file.
DB_NAME="db.sqlite3"
DB_SAVED_PATH=""

# Recover a database left aside by an update that died mid-pull. Never deletes
# anything — if a live database is present too, both are kept.
recover_orphaned_db() {
    local leftover kept
    for leftover in "$INSTALL_DIR/$DB_NAME".update-tmp-*; do
        [[ -e "$leftover" ]] || continue
        if [[ -f "$INSTALL_DIR/$DB_NAME" ]]; then
            kept="${leftover}.recovered"
            mv -f "$leftover" "$kept"
            log_warning "Orphaned database copy found next to a live one; kept as $(basename "$kept")"
        else
            mv -f "$leftover" "$INSTALL_DIR/$DB_NAME"
            log_warning "Recovered the database left aside by an interrupted update"
        fi
    done
}

hide_live_db() {
    DB_SAVED_PATH=""
    [[ -f "$INSTALL_DIR/$DB_NAME" ]] || return 0
    DB_SAVED_PATH="$DB_NAME.update-tmp-$$"
    if mv "$INSTALL_DIR/$DB_NAME" "$INSTALL_DIR/$DB_SAVED_PATH"; then
        log_info "Moved the live database aside for the pull"
    else
        DB_SAVED_PATH=""
        log_error "Could not move $DB_NAME aside — the pull may overwrite live data"
    fi
}

restore_live_db() {
    [[ -n "$DB_SAVED_PATH" ]] || return 0
    # Overwrite whatever the merge left behind: the live database wins.
    if mv -f "$INSTALL_DIR/$DB_SAVED_PATH" "$INSTALL_DIR/$DB_NAME"; then
        log_success "Live database restored"
    else
        log_error "FAILED to restore $DB_NAME — it is still at $DB_SAVED_PATH"
    fi
    DB_SAVED_PATH=""
}

# --- Uploaded files protection --------------------------------------------
#
# media/ holds what the running app writes for the teacher: the school logo
# they uploaded, and the audio the routines plugin speaks. The logo was tracked
# in git, so every update stashed the teacher's upload, the merge checked the
# committed copy back out over it, and the logo the school had chosen was gone.
# The fix is to stop tracking media/ — and this guard is what makes that safe,
# because the commit that untracks those files makes the merge DELETE them from
# the working tree. Every file git still tracks under media/ is therefore moved
# out of the tree for the duration of the pull and moved back after it, on
# every path, exactly as the database is.
#
# The list comes from git, so this retires itself: after the untracking commit
# lands there is nothing tracked under media/ any more, the guard does nothing
# on every later update, and there is no leftover machinery to remove.
MEDIA_DIR="media"
MEDIA_SAVED_PATHS=()

# Recover files left aside by an update that died mid-pull. Never deletes
# anything — if a live file is present too, the leftover is kept beside it.
recover_orphaned_media() {
    local leftover live kept
    while IFS= read -r leftover; do
        [[ -n "$leftover" ]] || continue
        live="${leftover%%.update-tmp-*}"
        if [[ -e "$live" ]]; then
            kept="${leftover}.recovered"
            mv -f "$leftover" "$kept"
            log_warning "Orphaned uploaded file found next to a live one; kept as $(basename "$kept")"
        else
            mv -f "$leftover" "$live"
            log_warning "Recovered an uploaded file left aside by an interrupted update"
        fi
    done < <(find "$INSTALL_DIR/$MEDIA_DIR" -name '*.update-tmp-*' 2>/dev/null)
}

media_tracked_files() {
    git -C "$INSTALL_DIR" ls-files -- "$MEDIA_DIR" 2>/dev/null
}

hide_media() {
    MEDIA_SAVED_PATHS=()
    local tracked saved
    while IFS= read -r tracked; do
        [[ -n "$tracked" ]] || continue
        [[ -e "$INSTALL_DIR/$tracked" ]] || continue
        saved="$tracked.update-tmp-$$"
        if mv "$INSTALL_DIR/$tracked" "$INSTALL_DIR/$saved"; then
            MEDIA_SAVED_PATHS+=("$saved")
        else
            log_error "Could not move $tracked aside — the pull may delete it"
        fi
    done < <(media_tracked_files)
    if [[ ${#MEDIA_SAVED_PATHS[@]} -gt 0 ]]; then
        log_info "Moved ${#MEDIA_SAVED_PATHS[@]} uploaded file(s) aside for the pull"
    fi
}

restore_media() {
    [[ ${#MEDIA_SAVED_PATHS[@]} -gt 0 ]] || return 0
    local saved original
    for saved in "${MEDIA_SAVED_PATHS[@]}"; do
        original="${saved%%.update-tmp-*}"
        # Overwrite whatever the merge left behind: the upload wins. The
        # directory is recreated because the merge may have removed it along
        # with the file it checked out.
        mkdir -p "$(dirname "$INSTALL_DIR/$original")"
        if mv -f "$INSTALL_DIR/$saved" "$INSTALL_DIR/$original"; then
            log_success "Restored $original"
        else
            log_error "FAILED to restore $original — it is still at $saved"
        fi
    done
    MEDIA_SAVED_PATHS=()
}

# Pull latest changes from git
pull_latest() {
    update_status "pull" "in_progress"
    log_info "Pulling latest changes from git..."

    cd "$INSTALL_DIR"

    # Prevent git from prompting for credentials (hangs in non-interactive scripts)
    export GIT_TERMINAL_PROMPT=0

    recover_orphaned_db
    recover_orphaned_media
    # Before the stash, so neither the stash nor the merge can touch them.
    hide_live_db
    hide_media

    # Stash any local changes. Untracked files are excluded on purpose: `git
    # stash` does not touch them, so counting them here only made this branch
    # announce "local changes detected" on a tree where nothing would be stashed.
    STASHED=0
    if [[ -n $(git status --porcelain --untracked-files=no) ]]; then
        log_warning "Local changes detected. Stashing them..."
        git stash
        STASHED=1
    fi

    # Pull latest changes (timeout prevents hanging on network issues). The
    # output is captured so a failure can be reported as whatever git actually
    # said, instead of being guessed at — see the branch below.
    local pull_output pull_rc
    if pull_output=$(timeout 60 git pull 2>&1); then
        log_success "Latest changes pulled successfully"
        # Show what was updated
        log_info "Latest commits:"
        git log --oneline -5
        update_status "pull" "completed"
    else
        pull_rc=$?
        log_warning "Failed to pull — continuing with the current version."
        # The real reason, not a guess. Reporting every failure as "no internet
        # or network error" is what hid a broken `timeout VAR=value` invocation
        # for weeks: a loud, diagnosable error read as a network problem and the
        # update carried on with the old code.
        while IFS= read -r line; do
            [[ -n "$line" ]] && log_warning "  $line"
        done <<< "$pull_output"
        case "$pull_rc" in
            124) log_warning "  (git pull did not finish within 60 seconds)" ;;
        esac
        # Restore stashed changes since we didn't pull anything new
        if [[ "$STASHED" -eq 1 ]]; then
            log_info "Restoring stashed local changes..."
            git stash pop 2>/dev/null || true
        fi
        update_status "pull" "skipped"
    fi

    # Always, on both paths.
    restore_live_db
    restore_media
}

# Update Python dependencies
update_dependencies() {
    update_status "dependencies" "in_progress"
    log_info "Updating Python dependencies..."

    cd "$INSTALL_DIR"

    if [[ -f /proc/device-tree/model ]] && grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then
        # libportaudio2 is what sounddevice loads to reach the noise monitor's
        # microphone. Without it the import fails and the plugin quietly
        # reports simulated noise instead of the real room, which is very hard
        # to notice from the dashboard.
        if ! ldconfig -p 2>/dev/null | grep -q "libportaudio\.so\.2"; then
            log_info "libportaudio2 not found, installing for the noise monitor..."
            sudo apt-get install -y libportaudio2 || \
                log_warning "Could not install libportaudio2 - the noise monitor will run without a microphone"
        fi

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

    sudo tee /etc/systemd/system/tinko-wifi.service > /dev/null << EOF
[Unit]
Description=Tinko Wi-Fi Captive Portal Check
After=NetworkManager.service
Before=tinko.service
# StartLimit* belong in [Unit]; in [Service] systemd ignores them ("Unknown
# key ... ignoring"), which silently disables the retry bound.
StartLimitIntervalSec=120
StartLimitBurst=3

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

    # Ensure nftables is installed — the modern replacement for iptables.
    # On Debian Bookworm+ (newer Raspberry Pi OS), NetworkManager's hotspot
    # shared mode uses nftables for NAT masquerading. Without nftables,
    # the hotspot NAT silently fails.
    if ! command -v nft &> /dev/null; then
        log_info "nftables not found, installing..."
        sudo apt-get install -y nftables
    fi

    # Ensure the iptables-nft wrapper is available so that any legacy
    # iptables calls are translated to nftables.
    if ! command -v iptables &> /dev/null; then
        log_info "iptables not found, installing iptables-nft wrapper..."
        sudo apt-get install -y iptables
    fi

    # dnsutils (dig/nslookup) lets startup_check.sh actually verify that
    # dnsmasq answers on the hotspot IP; without it the check degrades to a
    # bare socket-bind test that never proves DNS resolution works.
    if ! command -v dig &> /dev/null; then
        log_info "dnsutils not found, installing for dnsmasq verification..."
        sudo apt-get install -y dnsutils
    fi

    # Ensure captive portal DNS configuration is present (needed for older systems too)
    if ! grep -q "address=/#/10.42.0.1" /etc/dnsmasq.conf 2>/dev/null; then
        log_info "Configuring dnsmasq for captive portal..."
        cat << 'EOF' | sudo tee -a /etc/dnsmasq.conf > /dev/null

# Tinko Captive Portal Configuration
address=/#/10.42.0.1
interface=wlan0
bind-interfaces
except-interface=lo
EOF
    else
        # Config exists — make sure all directives are present
        if ! grep -q "interface=wlan0" /etc/dnsmasq.conf 2>/dev/null; then
            echo "interface=wlan0" | sudo tee -a /etc/dnsmasq.conf > /dev/null
        fi
        if ! grep -q "bind-interfaces" /etc/dnsmasq.conf 2>/dev/null; then
            echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf > /dev/null
        fi
        if ! grep -q "except-interface=lo" /etc/dnsmasq.conf 2>/dev/null; then
            echo "except-interface=lo" | sudo tee -a /etc/dnsmasq.conf > /dev/null
        fi
    fi

    # Disable dnsmasq auto-start on boot. It should only run in hotspot
    # mode (managed by startup_check.sh / wifi_worker.sh). If dnsmasq
    # starts on boot with its wildcard DNS redirect (address=/#/10.42.0.1),
    # it breaks internet DNS resolution for the Pi itself.
    if systemctl is-enabled dnsmasq 2>/dev/null | grep -q "enabled"; then
        sudo systemctl stop dnsmasq 2>/dev/null || true
        sudo systemctl disable dnsmasq 2>/dev/null || true
        log_info "Disabled dnsmasq auto-start (will only run in hotspot mode)"
    fi

    # Disable DNS on NetworkManager's internal dnsmasq to prevent port 53 conflict.
    # NM runs its own dnsmasq for shared connections which binds to port 53 on the hotspot IP.
    # Our standalone dnsmasq needs port 53 for captive portal DNS redirection (address=/#/).
    sudo mkdir -p /etc/NetworkManager/dnsmasq-shared.d/
    if [[ ! -f /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf ]]; then
        echo "port=0" | sudo tee /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf > /dev/null
        log_info "Disabled DNS on NetworkManager's internal dnsmasq (port 53 conflict prevention)"
    fi

    # Prevent the Pi's own DNS from being trapped by dnsmasq's wildcard redirect.
    # Tell NetworkManager to use a hardcoded upstream DNS server instead of the
    # system default (which may point to 127.0.0.1 or the local dnsmasq).
    # This ensures the Pi can always resolve real hostnames for internet checks.
    sudo mkdir -p /etc/NetworkManager/conf.d/
    if [[ ! -f /etc/NetworkManager/conf.d/dns-upstream.conf ]]; then
        sudo tee /etc/NetworkManager/conf.d/dns-upstream.conf > /dev/null << 'EOF'
[global-dns-domain-*]
servers=8.8.8.8,8.8.4.4
EOF
        log_info "Configured NM to use upstream DNS (8.8.8.8) bypassing local dnsmasq"
    fi

    # Ensure systemd-resolved stub listener doesn't hijack DNS to 127.0.0.53.
    # On some systems, systemd-resolved intercepts all DNS queries via a stub
    # on 127.0.0.53:53, which would bypass NM's DNS configuration.
    if systemctl is-active --quiet systemd-resolved 2>/dev/null; then
        sudo mkdir -p /etc/systemd/resolved.conf.d/
        if [[ ! -f /etc/systemd/resolved.conf.d/no-stub.conf ]]; then
            sudo tee /etc/systemd/resolved.conf.d/no-stub.conf > /dev/null << 'EOF'
[Resolve]
DNSStubListener=no
EOF
            sudo systemctl restart systemd-resolved 2>/dev/null || true
            log_info "Disabled systemd-resolved stub listener (prevents 127.0.0.53 DNS hijack)"
        fi
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
        sudo chown $USER /etc/tinko-portal/key.pem
        log_success "TLS certificate generated"
    fi

    ensure_wifi_service

    log_success "wifi-connect files updated in $WIFI_DIR"
}

# Compile translations
compile_translations() {
    log_info "Compiling translations..."
    
    cd "$INSTALL_DIR"
    
    # Every catalogue — the project's own and each plugin's — is compiled by
    # this repository's own compiler, which uses polib from the venv.
    #
    # This used to call `django-admin compilemessages` for the project
    # catalogue, which shells out to GNU `msgfmt`. Nothing installs gettext
    # (the package that provides msgfmt) — not the install script, not the
    # update — so that call failed on every Pi and the interface catalogue was
    # never compiled at all. The polib compiler covers the same files, needs no
    # system package, and works with no internet, which matters because a Tinko
    # Pi is set up over its own hotspot before it has any. It produces
    # byte-identical .mo files to the committed ones.
    #
    # A failure is still not fatal — an interface left in English works, and an
    # update must never be stopped by it — but the reason is logged rather than
    # discarded, and the success line is only reached when it really succeeded:
    # swallowing the output once hid a catalogue that would not compile, and
    # the update reported translations compiled while the pages kept the text
    # they were last built with.
    if translation_output=$(uv run python compile_translations.py 2>&1); then
        log_success "Translations compiled"
    else
        log_warning "Translations did not compile — pages keep the text they were last built with:"
        while IFS= read -r line; do
            [[ -n "$line" ]] && log_warning "  $line"
        done <<< "$translation_output"
    fi
}

# Ensure the tinko.service file is up to date.
# The service file may drift from the install version (e.g., wrong port,
# missing environment vars). This rewrites it to match the current install config.
ensure_tinko_service() {
    if [[ ! -f /etc/systemd/system/${SERVICE_NAME}.service ]]; then
        log_warning "tinko.service not found — skipping service file update"
        return
    fi

    # Read the current port from the service file
    CURRENT_PORT=$(grep -oP '(?<=-p )\d+' /etc/systemd/system/${SERVICE_NAME}.service 2>/dev/null || echo "")

    if [[ "$CURRENT_PORT" != "80" ]]; then
        log_warning "tinko.service is using port ${CURRENT_PORT:-???} — updating to port 80..."
    fi

    # Ensure TLS key is readable by the service user.
    # Daphne runs as $USER and needs to read the private key for HTTPS.
    sudo chown $USER /etc/tinko-portal/key.pem 2>/dev/null || true

    # Ensure TLS certificate exists (shared with captive portal)
    if [[ ! -f /etc/tinko-portal/cert.pem ]] || [[ ! -f /etc/tinko-portal/key.pem ]]; then
        log_info "Generating self-signed TLS certificate..."
        sudo mkdir -p /etc/tinko-portal
        sudo openssl req -x509 -newkey rsa:2048 -keyout /etc/tinko-portal/key.pem \
            -out /etc/tinko-portal/cert.pem -days 3650 -nodes \
            -subj "/CN=tinko.local" 2>/dev/null
        sudo chmod 644 /etc/tinko-portal/cert.pem
        sudo chmod 600 /etc/tinko-portal/key.pem
        sudo chown $USER /etc/tinko-portal/key.pem
    fi

    UV_PATH="$HOME/.local/bin/uv"

    # Rewrite the service file — Daphne serves both HTTP (80) and HTTPS (443).
    # The self-signed cert from /etc/tinko-portal/ is reused.
    # No setcap needed since Daphne no longer needs to bind to port <1024
    # when using AmbientCapabilities (or when nginx fronts it).
    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Tinko Educational Platform
After=network.target
# StartLimit* belong in [Unit]; in [Service] systemd ignores them.
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=$USER
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=${INSTALL_DIR}"
Environment="DJANGO_SETTINGS_MODULE=config.settings"
Environment="EDUPI_DEBUG=False"
ExecStartPre=${UV_PATH} run python manage.py collectstatic --noinput
ExecStart=${UV_PATH} run daphne -b 0.0.0.0 -p 80 -e ssl:443:privateKey=/etc/tinko-portal/key.pem:certKey=/etc/tinko-portal/cert.pem config.asgi:application
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=5

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
    echo "  - Dashboard:       http://${PI_IP}/"
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
    # If the pull replaced this script, switch to the new copy before running
    # the stages whose code it may have changed.
    reexec_if_self_changed
    update_dependencies
    run_migrations
    collect_static
    compile_translations
    update_wifi_connect
    ensure_tinko_service
    setup_update_infrastructure
    restart_service
    print_summary
}

# Handle script interruption
trap 'log_error "Update interrupted"; exit 1' INT TERM

# Run main function
main "$@"
