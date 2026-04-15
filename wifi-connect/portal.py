from flask import Flask, request, render_template_string, redirect
import subprocess
import os
import ssl
import threading
import http.server
import signal
import sys

# LCD display support for captive portal mode
# Shows WiFi credentials on the physical screen during setup
_lcd_device = None
_lcd_backlight = None
_lcd_cs_pin = None
_lcd_dc_pin = None
_lcd_rst_pin = None
_lcd_width = 320
_lcd_height = 240

try:
    import digitalio
    import board
    import adafruit_rgb_display.ili9341 as ili9341
    from gpiozero import PWMLED
    from PIL import Image, ImageDraw

    LCD_AVAILABLE = True
except ImportError:
    LCD_AVAILABLE = False


def _init_lcd():
    """Initialize the ILI9341 LCD display. Returns True on success."""
    global _lcd_device, _lcd_backlight, _lcd_cs_pin, _lcd_dc_pin, _lcd_rst_pin

    if not LCD_AVAILABLE:
        print("LCD: Libraries not available, skipping display")
        return False

    try:
        _lcd_cs_pin = digitalio.DigitalInOut(board.D22)
        _lcd_dc_pin = digitalio.DigitalInOut(board.D24)
        _lcd_rst_pin = digitalio.DigitalInOut(board.D23)
        spi = board.SPI()

        _lcd_device = ili9341.ILI9341(
            spi,
            rotation=90,  # landscape
            cs=_lcd_cs_pin,
            dc=_lcd_dc_pin,
            rst=_lcd_rst_pin,
            baudrate=16000000,
        )

        _lcd_width = 320
        _lcd_height = 240

        _lcd_backlight = PWMLED(18)
        _lcd_backlight.value = 1.0  # full brightness

        print(f"LCD: Initialized {_lcd_width}x{_lcd_height}")
        return True

    except Exception as e:
        print(f"LCD: Initialization failed: {e}")
        _lcd_device = None
        _lcd_backlight = None
        _lcd_cs_pin = None
        _lcd_dc_pin = None
        _lcd_rst_pin = None
        return False


def _show_wifi_on_lcd(ssid, password):
    """Display WiFi credentials on the LCD screen."""
    if not _lcd_device:
        return

    try:
        img = Image.new("RGB", (_lcd_width, _lcd_height), "black")
        draw = ImageDraw.Draw(img)

        # Use default font — PIL's built-in bitmap font
        # For the small TFT, default font is readable at close range

        # Title: "Tinko WiFi Setup" centered at top
        title = "Tinko WiFi Setup"
        bbox = draw.textbbox((0, 0), title)
        tw = bbox[2] - bbox[0]
        draw.text(((_lcd_width - tw) // 2, 20), title, fill="white")

        # Separator line
        draw.line([(40, 50), (280, 50)], fill="gray", width=1)

        # SSID line
        ssid_label = f"WiFi: {ssid}"
        bbox = draw.textbbox((0, 0), ssid_label)
        tw = bbox[2] - bbox[0]
        draw.text(((_lcd_width - tw) // 2, 70), ssid_label, fill="white")

        # Password line
        pass_label = f"Pass: {password}"
        bbox = draw.textbbox((0, 0), pass_label)
        tw = bbox[2] - bbox[0]
        draw.text(((_lcd_width - tw) // 2, 100), pass_label, fill="white")

        # Instructions
        line1 = "Connect, then"
        bbox = draw.textbbox((0, 0), line1)
        tw = bbox[2] - bbox[0]
        draw.text(((_lcd_width - tw) // 2, 160), line1, fill="gray")

        line2 = "open browser"
        bbox = draw.textbbox((0, 0), line2)
        tw = bbox[2] - bbox[0]
        draw.text(((_lcd_width - tw) // 2, 185), line2, fill="gray")

        _lcd_device.image(img)
        print(f"LCD: Showing WiFi credentials (SSID: {ssid})")

    except Exception as e:
        print(f"LCD: Failed to display WiFi info: {e}")


def _clear_lcd():
    """Clear the LCD screen and release resources."""
    global _lcd_device, _lcd_backlight, _lcd_cs_pin, _lcd_dc_pin, _lcd_rst_pin

    if not _lcd_device:
        return

    try:
        img = Image.new("RGB", (_lcd_width, _lcd_height), "black")
        _lcd_device.image(img)
        print("LCD: Screen cleared")
    except Exception as e:
        print(f"LCD: Failed to clear screen: {e}")

    try:
        if _lcd_backlight:
            _lcd_backlight.close()
            _lcd_backlight = None
    except Exception as e:
        print(f"LCD: Failed to release backlight: {e}")

    for pin in (_lcd_cs_pin, _lcd_dc_pin, _lcd_rst_pin):
        if pin:
            try:
                pin.deinit()
            except Exception as e:
                print(f"LCD: Failed to deinit pin: {e}")

    _lcd_cs_pin = None
    _lcd_dc_pin = None
    _lcd_rst_pin = None
    _lcd_device = None


def _handle_sigterm(signum, frame):
    """SIGTERM handler: clear LCD before exit."""
    print("Portal received SIGTERM, cleaning up LCD...")
    _clear_lcd()
    sys.exit(0)


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
    # Initialize LCD and show WiFi credentials during captive portal
    hotspot_ssid = os.environ.get('HOTSPOT_SSID', 'Tinko-Setup')
    hotspot_password = os.environ.get('HOTSPOT_PASSWORD', 'tinko1234')

    if _init_lcd():
        _show_wifi_on_lcd(hotspot_ssid, hotspot_password)

    # Register SIGTERM handler after LCD init so cleanup works on exit
    signal.signal(signal.SIGTERM, _handle_sigterm)

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