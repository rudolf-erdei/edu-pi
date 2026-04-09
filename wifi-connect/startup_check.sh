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
    if ! nmcli connection show | grep -q "Tinko-Setup"; then
        log "Creating hotspot 'Tinko-Setup' for the first time..."
        sudo nmcli dev wifi hotspot ifname wlan0 ssid "Tinko-Setup" password "tinko1234" con-name "Tinko-Setup"
        log "Hotspot created successfully"
    else
        log "Hotspot profile exists, activating..."
        sudo nmcli connection up "Tinko-Setup"
        log "Hotspot activated"
    fi

    # Start the Flask Captive Portal
    log "Starting Flask captive portal..."
    sudo python3 /home/pi/portal.py
fi