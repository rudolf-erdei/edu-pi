from flask import Flask, request, render_template_string
import subprocess

app = Flask(__name__)

# Helper function to ask NetworkManager for nearby Wi-Fi networks
def get_available_ssids():
    try:
        # Run the nmcli command to list only the SSIDs
        result = subprocess.check_output(['nmcli', '-t', '-f', 'SSID', 'dev', 'wifi'], text=True)
        
        # Split the output by line
        ssids = result.split('\n')
        
        # Clean up the list: remove blanks, remove duplicates, and remove our own hotspot
        clean_ssids = list(set([s.strip() for s in ssids if s.strip() and s.strip() != 'Robot-Setup']))
        
        # Sort them alphabetically for a better user experience
        clean_ssids.sort()
        return clean_ssids
    except Exception as e:
        # If the scan fails for any reason, return an empty list so the page still loads
        print(f"Wi-Fi scan failed: {e}")
        return []

HTML_FORM = """
<!DOCTYPE html>
<html>
<head><title>Tinko Setup</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family: Arial; text-align: center; margin-top: 50px;">
    <h2>Connect Tinko to Wi-Fi</h2>
    <form action="/connect" method="POST">
        <input list="network-list" type="text" name="ssid" placeholder="Wi-Fi Name (SSID)" required style="padding: 10px; margin: 10px; width: 80%;"><br>
        <input type="password" name="password" placeholder="Password" required style="padding: 10px; margin: 10px; width: 80%;"><br>
        <button type="submit" style="padding: 15px 30px; background: #007BFF; color: white; border: none; border-radius: 5px;">Connect</button>
    </form>
    <datalist id="network-list">
        {% for ssid in ssids %}
        <option value="{{ ssid }}">
        {% endfor %}
    </datalist>
</body>
</html>
"""

WAIT_PAGE = """
<!DOCTYPE html>
<html>
<head><title>Connecting...</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family: Arial; text-align: center; margin-top: 50px;">
    <h2>Testing Connection to "{{ ssid }}"...</h2>
    <p>Your phone will now disconnect from the Tinko.</p>
    <p><strong>If successful:</strong> The "Tinko-Setup" network will disappear. You can close this window!</p>
    <p><strong>If it fails:</strong> The "Tinko-Setup" network will reappear in about 20 seconds. Reconnect to it and try again.</p>
</body>
</html>
"""

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def index(path):
    found_networks = get_available_ssids()
    return render_template_string(HTML_FORM, ssids=found_networks)

@app.route('/connect', methods=['POST'])
def connect():
    ssid = request.form['ssid']
    password = request.form['password']
    
    # Spawn the worker script in the background. 
    # We pass the SSID and Password as arguments.
    subprocess.Popen(['sudo', 'bash', '/home/pi/wifi_worker.sh', ssid, password])
    
    # Immediately return the wait page BEFORE the Wi-Fi radio resets
    return render_template_string(WAIT_PAGE, ssid=ssid)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)