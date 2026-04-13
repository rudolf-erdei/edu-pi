#!/bin/bash
LOG_FILE="/var/log/tinko_wifi.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [startup_check] $1" | tee -a "$LOG_FILE"
}

log "=== Startup check beginning ==="

# Give the Pi 15 seconds to settle its hardware on boot
sleep 15

# Ping Google's DNS to verify actual internet routing, not just a local connection
if ping -q -c 2 -W 2 8.8.8.8 >/dev/null; then
    log "Internet verified. Booting Django server..."
    exit 0
else
    log "No internet detected. Initializing setup mode..."

    # Check if our hotspot profile already exists from a previous run
    if ! nmcli connection show | grep -q "^\s*Tinko-Setup\b"; then
        log "Creating hotspot 'Tinko-Setup' for the first time..."
        nmcli dev wifi hotspot ifname wlan0 ssid "Tinko-Setup" password "tinko1234" con-name "Tinko-Setup"
        log "Hotspot created successfully"
    else
        log "Hotspot profile exists, activating..."
        nmcli connection up "Tinko-Setup"
        log "Hotspot activated"
    fi

    # Restart dnsmasq so it binds to the hotspot interface IP
    log "Restarting dnsmasq to bind to hotspot interface..."
    systemctl restart dnsmasq
    log "dnsmasq restarted"

    # Start the Flask Captive Portal
    log "Starting Flask captive portal..."
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    python3 "$SCRIPT_DIR/portal.py" &
    PORTAL_PID=$!
    echo "$PORTAL_PID" > /run/tinko-portal.pid
    log "Flask portal started with PID $PORTAL_PID"

    # Watchdog: wait for the Flask process with a periodic health check.
    # If Flask dies unexpectedly, log it and exit the service so that:
    #   - Restart=on-failure can attempt recovery
    #   - Or systemd starts tinko.service (if Before= ordering is still set)
    # Timeout after 30 minutes to prevent the Pi from being stuck in setup mode forever.
    WATCHDOG_TIMEOUT=1800  # 30 minutes
    WATCHDOG_INTERVAL=30   # check every 30 seconds
    ELAPSED=0

    while kill -0 "$PORTAL_PID" 2>/dev/null; do
        if (( ELAPSED >= WATCHDOG_TIMEOUT )); then
            log "Watchdog: Flask portal has been running for 30 minutes. Killing it to exit setup mode."
            kill "$PORTAL_PID" 2>/dev/null
            rm -f /run/tinko-portal.pid
            break
        fi
        sleep "$WATCHDOG_INTERVAL"
        ELAPSED=$((ELAPSED + WATCHDOG_INTERVAL))
    done

    EXIT_CODE=$?
    if ! kill -0 "$PORTAL_PID" 2>/dev/null; then
        log "Flask portal has exited (elapsed: ${ELAPSED}s)"
    fi
    rm -f /run/tinko-portal.pid
    exit $EXIT_CODE
fi