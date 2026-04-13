from flask import Flask, request, render_template_string, redirect
import subprocess
import shlex
import os
import ssl
import threading
import http.server

app = Flask(__name__)

# Path to the wifi worker script - can be overridden via environment variable
# Default: same directory as this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WIFI_WORKER_SCRIPT = os.environ.get('WIFI_WORKER_SCRIPT', os.path.join(SCRIPT_DIR, 'wifi_worker.sh'))


def validate_wifi_input(ssid: str, password: str) -> bool:
    """Validate SSID and password to prevent command injection."""
    if not ssid or not password:
        return False
    if len(ssid) > 32 or len(password) > 64:
        return False
    # Block control characters (0x00-0x1f and 0x7f)
    for c in ssid + password:
        if ord(c) < 32 or ord(c) == 127:
            return False
    return True

# Helper function to ask NetworkManager for nearby Wi-Fi networks
def get_available_ssids():
    try:
        # Run the nmcli command to list only the SSIDs
        result = subprocess.check_output(['nmcli', '-t', '-f', 'SSID', 'dev', 'wifi'], text=True)
        
        # Split the output by line
        ssids = result.split('\n')
        
        # Clean up the list: remove blanks, remove duplicates, and remove our own hotspot
        clean_ssids = list(set([s.strip() for s in ssids if s.strip() and s.strip() != 'Tinko-Setup']))
        
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
    <p style="color: #666; font-size: 14px;">Type your Wi-Fi name below. Scanning is unavailable in hotspot mode.</p>
    {% if error %}
    <div style="color: red; margin-bottom: 15px;">{{ error }}</div>
    {% endif %}
    <form action="/connect" method="POST">
        <input list="network-list" type="text" name="ssid" placeholder="Wi-Fi Name (SSID)" required style="padding: 10px; margin: 10px; width: 80%;"><br>
        <input type="password" name="password" placeholder="Password" required style="padding: 10px; margin: 10px; width: 80%;"><br>
        <button type="submit" style="padding: 15px 30px; background: #007BFF; color: white; border: none; border-radius: 5px;">Connect</button>
    </form>
    {% if ssids %}
    <datalist id="network-list">
        {% for ssid in ssids %}
        <option value="{{ ssid }}">
        {% endfor %}
    </datalist>
    {% endif %}
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

# Captive portal detection URLs - redirect to the setup page.
# These URLs are probed by OS-level connectivity checks (Android, Apple, Windows).
# Returning a 302 redirect triggers the "Sign in to Wi-Fi" notification.
@app.route('/generate_204')
@app.route('/gen_204')
@app.route('/hotspot-detect.html')
@app.route('/connecttest.txt')
def captive_portal_redirect():
    return redirect('http://10.42.0.1/', code=302)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def index(path):
    found_networks = get_available_ssids()
    return render_template_string(HTML_FORM, ssids=found_networks)

@app.route('/connect', methods=['POST'])
def connect():
    ssid = request.form.get('ssid', '').strip()
    password = request.form.get('password', '')

    # Validate inputs to prevent command injection
    if not validate_wifi_input(ssid, password):
        return render_template_string(HTML_FORM, ssids=get_available_ssids(), error="Invalid input provided."), 400

    # Spawn the worker script safely using list args (no shell injection).
    # No sudo needed — portal.py runs as root (started by startup_check.sh which
    # runs as root via tinko-wifi.service).
    subprocess.Popen(['bash', WIFI_WORKER_SCRIPT, ssid, password])

    # Immediately return the wait page BEFORE the Wi-Fi radio resets
    return render_template_string(WAIT_PAGE, ssid=ssid)

if __name__ == '__main__':
    # Start HTTPS redirect server on port 443 in a background thread.
    # Some Android devices use HTTPS for captive portal checks.
    # A self-signed cert is sufficient — Android's connectivity check
    # does not enforce cert validation, it just needs a response.
    CERT_PATH = '/etc/tinko-portal/cert.pem'
    KEY_PATH = '/etc/tinko-portal/key.pem'

    if os.path.exists(CERT_PATH) and os.path.exists(KEY_PATH):
        class RedirectHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302)
                self.send_header('Location', f'http://10.42.0.1{self.path}')
                self.end_headers()

            do_POST = do_GET  # type: ignore[assignment]

            def log_message(self, format, *args):
                pass  # Suppress access logs for the redirect server

        def run_https():
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(CERT_PATH, KEY_PATH)
            server = http.server.HTTPServer(('0.0.0.0', 443), RedirectHandler)
            server.socket = ctx.wrap_socket(server.socket, server_side=True)
            server.serve_forever()

        https_thread = threading.Thread(target=run_https, daemon=True)
        https_thread.start()
        print("HTTPS redirect server started on port 443")

    # Start the main HTTP Flask server on port 80
    app.run(host='0.0.0.0', port=80)