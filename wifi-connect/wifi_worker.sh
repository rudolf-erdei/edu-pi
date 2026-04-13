#!/bin/bash
SSID="$1"
PASSWORD="$2"
LOG_FILE="/var/log/tinko_wifi.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [wifi_worker] $1" | tee -a "$LOG_FILE"
}

log "Starting WiFi connection attempt for SSID: $SSID"

# Give the Flask web server 3 seconds to send the HTML "Wait Page" to the teacher's phone
sleep 3

# Attempt to connect to the new Wi-Fi.
# --wait 15 ensures it doesn't hang forever if the network drops.
if sudo nmcli --wait 15 dev wifi connect "$SSID" password "$PASSWORD"; then
    log "Connection to '$SSID' successful!"
    # The Pi is now online.

    # Kill the Flask portal using its PID file (avoids killing unrelated processes)
    if [[ -f /run/tinko-portal.pid ]]; then
        PORTAL_PID=$(cat /run/tinko-portal.pid)
        if sudo kill -0 "$PORTAL_PID" 2>/dev/null; then
            sudo kill "$PORTAL_PID"
            log "Flask portal (PID $PORTAL_PID) stopped"
        else
            log "Flask portal PID $PORTAL_PID no longer running"
        fi
        sudo rm -f /run/tinko-portal.pid
    else
        log "No PID file found, falling back to pkill"
        sudo pkill -f portal.py
        log "Flask portal stopped via pkill"
    fi

    # Wait for tinko-wifi service to finish so systemd naturally starts tinko
    # via the Before=tinko.service ordering dependency (avoids double-start)
    log "WiFi setup complete. Django will start via systemd ordering."
else
    log "Connection to '$SSID' failed (wrong password or out of range). Reverting to hotspot..."
    # The connection failed. Bring the hotspot profile back up so the teacher can try again.
    sudo nmcli connection up "Tinko-Setup"
    log "Hotspot 'Tinko-Setup' restored"
fi