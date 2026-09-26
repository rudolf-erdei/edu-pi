from flask import Flask, request, render_template_string, redirect
import glob
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

# Pillow is imported apart from the GPIO stack: it is what draws the screen, so
# it is worth having even on an interpreter that turns out to have no LCD.
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None

try:
    import digitalio
    import board
    import adafruit_rgb_display.ili9341 as ili9341
    from gpiozero import PWMLED

    LCD_AVAILABLE = True
except ImportError:
    LCD_AVAILABLE = False

#: Fonts to try for the LCD text, in preference order. Raspberry Pi OS ships
#: the DejaVu family; the fallback is PIL's built-in bitmap font, which is
#: small but always there.
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
)

#: Credential lines are drawn at the largest of these that fits the screen, so
#: a long network name shrinks rather than running off the edge.
CREDENTIAL_SIZES = (30, 26, 22, 18, 16, 14, 12, 11)

#: Set in the environment before re-exec, so the portal can never re-exec twice.
REEXEC_ENV_FLAG = "TINKO_PORTAL_REEXEC"

#: Everything the portal needs from an interpreter: the LCD stack, and Flask to
#: keep serving the setup page afterwards.
REQUIRED_IMPORTS = ("board", "digitalio", "adafruit_rgb_display", "PIL", "flask")


def _can_run_portal_with_lcd(python: str) -> bool:
    """Whether an interpreter can drive the LCD and still serve the portal.

    Args:
        python: Path to a Python interpreter.

    Returns:
        bool: True if every module in REQUIRED_IMPORTS imports under it.
    """
    try:
        result = subprocess.run(
            [python, "-c", "import " + ", ".join(REQUIRED_IMPORTS)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except Exception:
        return False
    return result.returncode == 0


def _lcd_capable_interpreters():
    """Candidate interpreters that may carry the LCD libraries, best first.

    Yields:
        str: Paths to try, which may not exist.
    """
    candidates = []
    override = os.environ.get("TINKO_VENV_PYTHON")
    if override:
        candidates.append(override)
    # This script is copied out of the project at install time, so its own
    # directory is the sibling of the project directory that owns the venv.
    candidates.extend(
        sorted(glob.glob(os.path.join(SCRIPT_DIR, "*", ".venv", "bin", "python")))
    )
    candidates.extend(sorted(glob.glob("/opt/*/.venv/bin/python")))

    seen = set()
    for path in candidates:
        if path not in seen:
            seen.add(path)
            yield path


def use_lcd_capable_interpreter() -> None:
    """Re-run the portal under an interpreter that has the LCD libraries.

    The portal is launched with the system ``python3``, but the adafruit/PIL
    stack used to draw on the LCD is installed only in the project venv. Under
    the system interpreter the import above fails, the screen stays dark, and
    nothing on the page says so — so switch interpreters instead of giving up
    on the screen.

    ``os.execv`` keeps the PID, so the launcher's pidfile and its watchdog
    still point at this process.

    Returns:
        None: It either returns, having found nothing better, or never returns.
    """
    if os.environ.get(REEXEC_ENV_FLAG) == "1":
        return  # Already re-exec'd once. Never loop.
    if _can_run_portal_with_lcd(sys.executable):
        return

    for candidate in _lcd_capable_interpreters():
        if os.path.abspath(candidate) == os.path.abspath(sys.executable):
            continue
        if not _can_run_portal_with_lcd(candidate):
            continue
        print(f"LCD: re-running the portal under {candidate}")
        os.environ[REEXEC_ENV_FLAG] = "1"
        try:
            os.execv(candidate, [candidate, os.path.abspath(__file__), *sys.argv[1:]])
        except OSError as e:
            # A candidate that answers the import check can still fail to
            # execute (a venv symlinked to an interpreter that is gone). The
            # portal must survive that: no screen is bad, no setup page is worse.
            print(f"LCD: could not re-run under {candidate}: {e}")
            os.environ.pop(REEXEC_ENV_FLAG, None)

    print("LCD: no interpreter with the LCD libraries found; screen stays dark")


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


def _lcd_font(size: int):
    """Return a font of about the requested size.

    Args:
        size: Desired height in pixels.

    Returns:
        The first available font from FONT_CANDIDATES, else None, which makes
        PIL draw with its built-in bitmap font.
    """
    if ImageFont is None:
        return None
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return None


def _text_width(draw, text: str, font) -> int:
    """Width in pixels that ``text`` occupies in ``font``.

    Args:
        draw: The ImageDraw to measure with.
        text: The text to measure.
        font: Font to measure with, or None for PIL's default.

    Returns:
        int: Width in pixels.
    """
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _line_height(font) -> int:
    """Vertical distance to leave between two lines drawn with ``font``."""
    return getattr(font, "size", CREDENTIAL_SIZES[-1]) + 4


def _truncate_to_fit(draw, text: str, font, max_width: int) -> str:
    """Shorten ``text`` until it fits, marking the cut.

    Args:
        draw: The ImageDraw to measure with.
        text: The text to shorten.
        font: Font it will be drawn in.
        max_width: Available width in pixels.

    Returns:
        str: The longest prefix that fits, ending in an ellipsis.
    """
    for cut in range(len(text) - 1, 0, -1):
        candidate = text[:cut].rstrip() + "..."
        if _text_width(draw, candidate, font) <= max_width:
            return candidate
    return "..."


def _fitted_font(draw, text: str, max_width: int):
    """Largest credential font whose rendering of ``text`` fits the screen.

    Args:
        draw: The ImageDraw to measure with.
        text: The line to be drawn.
        max_width: Available width in pixels.

    Returns:
        A font from CREDENTIAL_SIZES, the smallest if none of them fit.
    """
    for size in CREDENTIAL_SIZES:
        font = _lcd_font(size)
        if _text_width(draw, text, font) <= max_width:
            return font
    return _lcd_font(CREDENTIAL_SIZES[-1])


def _fit_credential(draw, text: str, max_width: int):
    """Choose the font and the lines that show a credential in full.

    Shrinking is tried first, then wrapping, and only then clipping: a password
    shown short is a password that does not work, so the text is never cut
    while there is any way to show all of it.

    Args:
        draw: The ImageDraw to measure with.
        text: The network name or password.
        max_width: Available width in pixels.

    Returns:
        tuple: ``(font, lines)``. Two lines only when the smallest size cannot
        hold the text on one.
    """
    font = _fitted_font(draw, text, max_width)
    if _text_width(draw, text, font) <= max_width:
        return font, [text]

    smallest = _lcd_font(CREDENTIAL_SIZES[-1])
    half = (len(text) + 1) // 2
    split = [text[:half], text[half:]]
    if all(_text_width(draw, line, smallest) <= max_width for line in split):
        return smallest, split

    return smallest, [_truncate_to_fit(draw, text, smallest, max_width)]


def _draw_centred(draw, text: str, y: int, font, fill: str) -> None:
    """Draw one line of text horizontally centred on the LCD.

    Args:
        draw: The ImageDraw to draw with.
        text: The line to be drawn.
        y: Top edge of the line, in pixels.
        font: Font to draw with, or None for PIL's default.
        fill: Text colour.

    Returns:
        None
    """
    width = _text_width(draw, text, font)
    draw.text(((_lcd_width - width) // 2, y), text, font=font, fill=fill)


def _draw_credential(draw, text: str, y: int, max_width: int) -> None:
    """Draw a network name or password, wrapped if it cannot fit on one line.

    Args:
        draw: The ImageDraw to draw with.
        text: The credential to draw.
        y: Top edge of the first line, in pixels.
        max_width: Available width in pixels.

    Returns:
        None
    """
    font, lines = _fit_credential(draw, text, max_width)
    for number, line in enumerate(lines):
        _draw_centred(draw, line, y + number * _line_height(font), font, "white")


def _show_wifi_on_lcd(ssid, password):
    """Display the hotspot name and password on the LCD screen.

    This is the whole point of the screen in setup mode: a teacher who has just
    unboxed the Pi has no other way to learn what to connect their phone to.
    """
    if not _lcd_device:
        return

    try:
        img = Image.new("RGB", (_lcd_width, _lcd_height), "black")
        draw = ImageDraw.Draw(img)
        max_width = _lcd_width - 28

        _draw_centred(draw, "Tinko WiFi Setup", 12, _lcd_font(22), "white")
        draw.line([(30, 46), (_lcd_width - 30, 46)], fill="gray", width=1)

        _draw_centred(draw, "NETWORK", 58, _lcd_font(14), "gray")
        _draw_credential(draw, ssid, 76, max_width)

        _draw_centred(draw, "PASSWORD", 122, _lcd_font(14), "gray")
        _draw_credential(draw, password, 140, max_width)

        draw.line([(30, 186), (_lcd_width - 30, 186)], fill="gray", width=1)
        _draw_centred(draw, "Connect, then open", 200, _lcd_font(14), "gray")
        _draw_centred(draw, "a browser", 220, _lcd_font(14), "gray")

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

def _in_hotspot_mode():
    """True when wlan0 is associated to the Tinko-Setup hotspot (AP mode)."""
    try:
        state = subprocess.check_output(
            ['nmcli', '-g', 'GENERAL.STATE', 'device', 'show', 'wlan0'], text=True, timeout=5
        ).strip()
        conn = subprocess.check_output(
            ['nmcli', '-g', 'GENERAL.CONNECTION', 'device', 'show', 'wlan0'], text=True, timeout=5
        ).strip()
        return state.startswith('connected') and conn == 'Tinko-Setup'
    except Exception:
        return False


# Helper function to ask NetworkManager for nearby Wi-Fi networks
def get_available_ssids():
    # A single radio cannot scan while serving the hotspot — skip the scan
    # instead of blocking the page render on a doomed nmcli call.
    if _in_hotspot_mode():
        return []
    try:
        # Run the nmcli command to list only the SSIDs
        result = subprocess.check_output(['nmcli', '-t', '-f', 'SSID', 'dev', 'wifi'], text=True, timeout=8)

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
@app.route('/ncsi.txt')
@app.route('/library/test/success.html')
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
    # The system python3 cannot import the LCD libraries, so switch to an
    # interpreter that can before serving anything.
    use_lcd_capable_interpreter()

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
            try:
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(CERT_PATH, KEY_PATH)
                server = http.server.HTTPServer(('0.0.0.0', 443), RedirectHandler)
                server.socket = ctx.wrap_socket(server.socket, server_side=True)
                server.serve_forever()
            except OSError as e:
                # Port 443 already taken (e.g. daphne HTTPS). HTTPS captive
                # detection degrades to HTTP-only; do not crash the portal.
                print(f"HTTPS redirect server could not bind port 443: {e}")
            except Exception as e:
                print(f"HTTPS redirect server error: {e}")

        https_thread = threading.Thread(target=run_https, daemon=True)
        https_thread.start()
        print("HTTPS redirect server started on port 443")

    # Start the main HTTP Flask server on port 80 (override for testing).
    PORTAL_PORT = int(os.environ.get('PORTAL_PORT', '80'))
    app.run(host='0.0.0.0', port=PORTAL_PORT)