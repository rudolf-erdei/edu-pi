#!/bin/bash
SSID="$1"
PASSWORD="$2"
LOG_FILE="/var/log/tinko_wifi.log"
HOTSPOT_SSID="Tinko-Setup"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [wifi_worker] $1" | tee -a "$LOG_FILE"
}

log "Starting WiFi connection attempt for SSID: $SSID"

# Give the Flask web server 3 seconds to send the HTML "Wait Page" to the teacher's phone
sleep 3

# Does this SSID already have a saved profile on the Pi?
# If yes, it is a genuine network (configured earlier) — keep it. We only
# delete a profile that pre-existed in this process when we are sure it was
# created by a previous failed attempt, never a real saved network.
if nmcli -t -f NAME connection show 2>/dev/null | grep -Fxq "$SSID"; then
    SSID_SAVED=1
    log "'$SSID' already has a saved profile — keeping it"
else
    SSID_SAVED=0
fi

# Tear down the hotspot before attempting WiFi connection.
# A single WiFi radio cannot be in AP mode and station mode simultaneously.
nmcli connection down "$HOTSPOT_SSID" 2>/dev/null || true
sleep 1

# Remove any stale auto-created profile for this SSID (from prior failed
# attempts) — but never touch a pre-existing saved network.
if [[ "$SSID_SAVED" -eq 0 ]]; then
    nmcli connection delete "$SSID" 2>/dev/null || true
fi

# Attempt to connect to the new Wi-Fi.
# --wait 15 ensures it doesn't hang forever if the network drops.
if nmcli --wait 15 dev wifi connect "$SSID" password "$PASSWORD"; then
    log "Connection to '$SSID' successful!"
    # The Pi is now online.

    # Make sure the profile is active (a fresh auto-created profile may need
    # an explicit up) so NetworkManager rewrites resolv.conf to the real
    # network's DNS.
    nmcli connection up "$SSID" 2>/dev/null || true

    # Kill the Flask portal using its PID file (avoids killing unrelated processes)
    if [[ -f /run/tinko-portal.pid ]]; then
        PORTAL_PID=$(cat /run/tinko-portal.pid)
        if kill -0 "$PORTAL_PID" 2>/dev/null; then
            kill "$PORTAL_PID"
            log "Flask portal (PID $PORTAL_PID) stopped"
        else
            log "Flask portal PID $PORTAL_PID no longer running"
        fi
        rm -f /run/tinko-portal.pid
    else
        log "No PID file found, falling back to pkill"
        pkill -f "python3.*portal.py"
        log "Flask portal stopped via pkill"
    fi

    # Stop dnsmasq — it's only needed in hotspot mode for DNS redirection.
    # Its wildcard DNS (address=/#/10.42.0.1) would break internet access
    # if left running while connected to real WiFi.
    if systemctl stop dnsmasq 2>/dev/null; then
        log "dnsmasq stopped (no longer needed with WiFi internet)"
    else
        log "WARNING: dnsmasq stop returned nonzero (may already be stopped)"
    fi

    # Wait for tinko-wifi service to finish so systemd naturally starts tinko
    # via the Before=tinko.service ordering dependency (avoids double-start)
    log "WiFi setup complete. Django will start via systemd ordering."
else
    log "Connection to '$SSID' failed (wrong password or out of range). Reverting to hotspot..."
    # The connection failed. Bring the hotspot profile back up so the teacher can try again.
    if ! nmcli connection up "$HOTSPOT_SSID"; then
        log "ERROR: could not restore hotspot '$HOTSPOT_SSID'"
    else
        log "Hotspot '${HOTSPOT_SSID}' restored"
    fi

    # Restart dnsmasq so it re-binds to the restored hotspot interface IP.
    # Without this, DNS redirection may not work after the radio switch (AP -> station -> AP).
    if systemctl restart dnsmasq 2>/dev/null; then
        log "dnsmasq restarted after hotspot restore"
    else
        log "WARNING: dnsmasq restart failed after hotspot restore"
        log "DNS redirection may be unavailable until the portal restarts"
    fi
fi
