#!/bin/bash

# Give the Pi 15 seconds to settle its hardware on boot
sleep 15

# Ping Google's DNS to verify actual internet routing, not just a local connection
if ping -q -c 2 -W 2 8.8.8.8 >/dev/null; then
    echo "Internet verified. Booting Django server..."
    exit 0
else
    echo "No internet. Initializing setup mode..."
    
    # Check if our hotspot profile already exists from a previous run
    if ! nmcli connection show | grep -q "Tinko-Setup"; then
        # Create it for the first time
        sudo nmcli dev wifi hotspot ifname wlan0 ssid "Tinko-Setup" password "tinto1234" con-name "Tinko-Setup"
    else
        # Profile exists, just turn it on
        sudo nmcli connection up "Tinko-Setup"
    fi
    
    # Start the Flask Captive Portal
    sudo python3 portal.py
fi