#!/bin/bash
SSID="$1"
PASSWORD="$2"

# Give the Flask web server 3 seconds to send the HTML "Wait Page" to the teacher's phone
sleep 3

# Attempt to connect to the new Wi-Fi. 
# --wait 15 ensures it doesn't hang forever if the network drops.
if sudo nmcli --wait 15 dev wifi connect "$SSID" password "$PASSWORD"; then
    echo "Connection Successful!"
    # The Pi is now online. 
    # (Optional: Add a python script here to make the robot beep triumphantly!)
    
    # Kill the Flask portal since we don't need it taking up memory anymore
    sudo pkill -f portal.py
else
    echo "Connection Failed (Wrong password or out of range). Reverting..."
    # The connection failed. Bring the hotspot profile back up so the teacher can try again.
    sudo nmcli connection up "Robot-Setup"
fi