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
    # (Optional: Add a python script here to make the robot beep triumphantly!)

    # Kill the Flask portal since we don't need it taking up memory anymore
    sudo pkill -f portal.py
    log "Flask portal stopped"

    # Start the Django application
    log "Starting Django application..."
    sudo systemctl start tinko
    log "Django started successfully"
else
    log "Connection to '$SSID' failed (wrong password or out of range). Reverting to hotspot..."
    # The connection failed. Bring the hotspot profile back up so the teacher can try again.
    sudo nmcli connection up "Tinko-Setup"
    log "Hotspot 'Tinko-Setup' restored"
fi