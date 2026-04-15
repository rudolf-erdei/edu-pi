#!/bin/bash
#
# Tinko - Educational Raspberry Pi Platform - Install Script
# This script sets up Tinko on a Raspberry Pi for production use
#
# Usage: bash install-raspberry-pi.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
# This script assumes it is run from the cloned repository directory
INSTALL_DIR="$(pwd)"
SERVICE_NAME="tinko"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "This script should not be run as root/sudo"
        log_info "It will use sudo when necessary. Please run as normal user (pi)."
        exit 1
    fi
}

# Check if running on Raspberry Pi
check_platform() {
    log_info "Checking platform..."
    
    if [[ -f /proc/device-tree/model ]]; then
        MODEL=$(cat /proc/device-tree/model)
        if [[ $MODEL == *"Raspberry Pi"* ]]; then
            log_success "Raspberry Pi detected: $MODEL"
            return 0
        fi
    fi
    
    if [[ -f /etc/rpi-issue ]]; then
        log_success "Raspberry Pi detected"
        return 0
    fi
    
    log_warning "This doesn't appear to be a Raspberry Pi"
    log_info "The script will attempt to continue, but GPIO features won't work"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
}

# Check internet connectivity
check_internet() {
    log_info "Checking internet connectivity..."
    if ! curl -s --max-time 10 https://github.com > /dev/null; then
        log_error "No internet connection detected"
        log_info "Internet is required for downloading dependencies"
        exit 1
    fi
    log_success "Internet connection verified"
}

# Update system packages
update_system() {
    log_info "Updating system packages..."
    sudo apt-get update
    sudo apt-get upgrade -y
    log_success "System packages updated"
}

# Install system dependencies
install_system_deps() {
    log_info "Installing system dependencies..."
    
    # Install packages that are typically available
    sudo apt-get install -y \
        git \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        libportaudio2 \
        libsdl2-dev \
        libsdl2-mixer-2.0-0 \
        portaudio19-dev \
        ffmpeg \
        libespeak1 \
        libasound2-dev \
        curl \
        build-essential \
        pkg-config \
        libjpeg-dev \
        libpng-dev \
        libfreetype6-dev \
        liblcms2-dev \
        libopenjp2-7-dev \
        libtiff5-dev \
        libwebp-dev \
        libharfbuzz-dev \
        libfribidi-dev \
        wireless-tools \
        alsa-utils \
        nftables \
        iptables \
        libcap2-bin || true
    
    # Try to install optional packages (some may not be available on certain systems)
    log_info "Attempting to install optional packages..."
    
    # libatlas-base-dev is optional (for NumPy optimization, but not required)
    sudo apt-get install -y libatlas-base-dev 2>/dev/null || {
        log_warning "libatlas-base-dev not available (optional package, continuing...)"
    }
    
    log_success "System dependencies installed"
}

# Install UV package manager
install_uv() {
    log_info "Installing UV package manager..."
    
    if command -v uv &> /dev/null; then
        log_warning "UV is already installed, skipping..."
        uv self update || true
        return
    fi
    
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Source the environment
    export PATH="$HOME/.local/bin:$PATH"
    
    if ! command -v uv &> /dev/null; then
        log_error "UV installation failed"
        exit 1
    fi
    
    log_success "UV package manager installed"
}

# Install Python dependencies
install_python_deps() {
    log_info "Installing Python dependencies..."
    
    cd "$INSTALL_DIR"
    
    # Install base dependencies
    log_info "Installing base dependencies..."
    uv sync
    
    # Install Raspberry Pi specific dependencies
    log_info "Installing GPIO dependencies..."
    uv sync --extra pi
    
    log_success "Python dependencies installed"
}

# Create environment configuration
setup_environment() {
    log_info "Setting up environment configuration..."
    
    cd "$INSTALL_DIR"
    
    # Get Raspberry Pi IP address
    PI_IP=$(hostname -I | awk '{print $1}')
    
    # Get current timezone
    CURRENT_TZ=$(timedatectl show --property=Timezone --value 2>/dev/null || echo "Europe/Bucharest")
    
    # Generate a random secret key
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    
    # Check if .env already exists
    if [[ -f .env ]]; then
        log_warning ".env file already exists"
        read -p "Overwrite? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Keeping existing .env file"
            return
        fi
        cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    fi
    
    cat > .env << EOF
# Tinko Environment Configuration
# Generated on $(date)

# Security
DEBUG=False
SECRET_KEY=${SECRET_KEY}
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0,${PI_IP},tinko.local

# Localization
TIME_ZONE=${CURRENT_TZ}

# Application Settings
EDUPI_DEBUG=False
EOF
    
    log_success "Environment file created at $INSTALL_DIR/.env"
    log_info "IP Address configured: $PI_IP"
    log_info "Time zone configured: $CURRENT_TZ"
}

# Run Django migrations
run_migrations() {
    log_info "Running database migrations..."
    
    cd "$INSTALL_DIR"
    uv run python manage.py migrate --noinput
    
    log_success "Database migrations completed"
}

# Create superuser
create_superuser() {
    log_info "Creating admin user..."
    
    cd "$INSTALL_DIR"
    
    # Check if superuser already exists
    SUPERUSER_EXISTS=$(uv run python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); print(User.objects.filter(is_superuser=True).exists())" 2>/dev/null || echo "False")
    
    if [[ "$SUPERUSER_EXISTS" == "True" ]]; then
        log_warning "Superuser already exists, skipping creation"
        return
    fi
    
    log_info "Creating superuser with default credentials:"
    log_info "  Username: admin"
    log_info "  Password: admin123"
    log_warning "  ⚠️  Please change these after first login!"
    
    uv run python manage.py shell << 'PYTHON'
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', '', 'admin123')
    print("Superuser created successfully")
else:
    print("Superuser already exists")
PYTHON
    
    log_success "Admin user created"
}

# Collect static files
collect_static() {
    log_info "Collecting static files..."
    
    cd "$INSTALL_DIR"
    uv run python manage.py collectstatic --noinput
    
    log_success "Static files collected"
}

# Compile translations
compile_translations() {
    log_info "Compiling translations..."

    cd "$INSTALL_DIR"

    # Compile project translations
    uv run django-admin compilemessages 2>/dev/null || log_warning "No project translations to compile"

    # Compile plugin translations
    if [[ -f scripts/compile_translations.py ]]; then
        python3 scripts/compile_translations.py
    fi

    log_success "Translations compiled"
}

# Setup wifi-connect (captive portal for headless WiFi configuration)
setup_wifi_connect() {
    log_info "Setting up wifi-connect..."

    WIFI_DIR="$HOME"

    # Check if wifi-connect directory exists in the repo
    if [[ ! -d "$INSTALL_DIR/wifi-connect" ]]; then
        log_warning "wifi-connect directory not found in repo, skipping"
        return
    fi

    # Install dnsmasq for captive portal DNS redirection
    log_info "Installing dnsmasq..."
    sudo apt-get install -y dnsmasq

    # Install nftables — the modern replacement for iptables.
    # On Debian Bookworm+ (newer Raspberry Pi OS), iptables is phased out
    # in favor of nftables. NetworkManager's hotspot shared mode uses
    # nftables for NAT masquerading on these systems. Without nftables,
    # the hotspot NAT silently fails and connected clients can't route traffic.
    if ! command -v nft &> /dev/null; then
        log_info "nftables not found, installing..."
        sudo apt-get install -y nftables
    fi

    # Ensure the iptables-nft wrapper is available so that any legacy
    # iptables calls (from NM or other tools) are translated to nftables.
    if ! command -v iptables &> /dev/null; then
        log_info "iptables not found, installing iptables-nft wrapper..."
        sudo apt-get install -y iptables
    fi

    # Disable dnsmasq auto-start on boot. It should only run in hotspot
    # mode (managed by startup_check.sh / wifi_worker.sh). If dnsmasq
    # starts on boot with its wildcard DNS redirect (address=/#/10.42.0.1),
    # it breaks internet DNS resolution for the Pi itself.
    sudo systemctl stop dnsmasq 2>/dev/null || true
    sudo systemctl disable dnsmasq 2>/dev/null || true
    log_info "dnsmasq auto-start disabled (will only run in hotspot mode)"

    # Check for dnsmasq version with known wildcard DNS bug
    DNSMASQ_VERSION=$(dnsmasq --version 2>/dev/null | head -1 | grep -oP '\d+\.\d+' | head -1)
    if [[ "$DNSMASQ_VERSION" == "2.86" ]]; then
        log_warning "dnsmasq 2.86 has a known bug with address=/#/ wildcard DNS redirection. Consider upgrading."
    fi

    # Configure dnsmasq for captive portal
    if [[ ! -f /etc/dnsmasq.conf.backup ]]; then
        sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.backup
    fi

    # Add captive portal configuration if not already present
    if ! grep -q "address=/#/10.42.0.1" /etc/dnsmasq.conf 2>/dev/null; then
        log_info "Configuring dnsmasq for captive portal..."
        cat << 'EOF' | sudo tee -a /etc/dnsmasq.conf > /dev/null

# Tinko Captive Portal Configuration
address=/#/10.42.0.1
interface=wlan0
bind-interfaces
except-interface=lo
EOF
    else
        # Config exists — make sure all directives are present
        if ! grep -q "interface=wlan0" /etc/dnsmasq.conf 2>/dev/null; then
            echo "interface=wlan0" | sudo tee -a /etc/dnsmasq.conf > /dev/null
        fi
        if ! grep -q "bind-interfaces" /etc/dnsmasq.conf 2>/dev/null; then
            echo "bind-interfaces" | sudo tee -a /etc/dnsmasq.conf > /dev/null
        fi
        if ! grep -q "except-interface=lo" /etc/dnsmasq.conf 2>/dev/null; then
            echo "except-interface=lo" | sudo tee -a /etc/dnsmasq.conf > /dev/null
        fi
    fi

    # Disable DNS on NetworkManager's internal dnsmasq to prevent port 53 conflict.
    # NM runs its own dnsmasq for shared connections which binds to port 53 on the hotspot IP.
    # Our standalone dnsmasq needs port 53 for captive portal DNS redirection (address=/#/).
    sudo mkdir -p /etc/NetworkManager/dnsmasq-shared.d/
    echo "port=0" | sudo tee /etc/NetworkManager/dnsmasq-shared.d/no-dns.conf > /dev/null
    log_info "Configured NM dnsmasq to disable DNS (port 53 conflict prevention)"

    # Prevent the Pi's own DNS from being trapped by dnsmasq's wildcard redirect.
    # Tell NetworkManager to use a hardcoded upstream DNS server instead of the
    # system default (which may point to 127.0.0.1 or the local dnsmasq).
    # This ensures the Pi can always resolve real hostnames for internet checks.
    sudo mkdir -p /etc/NetworkManager/conf.d/
    sudo tee /etc/NetworkManager/conf.d/dns-upstream.conf > /dev/null << 'EOF'
[global-dns-domain-*]
servers=8.8.8.8,8.8.4.4
EOF
    log_info "Configured NM to use upstream DNS (8.8.8.8) bypassing local dnsmasq"

    # Ensure systemd-resolved stub listener doesn't hijack DNS to 127.0.0.53.
    # On some systems, systemd-resolved intercepts all DNS queries via a stub
    # on 127.0.0.53:53, which would bypass NM's DNS configuration.
    if systemctl is-active --quiet systemd-resolved 2>/dev/null; then
        sudo mkdir -p /etc/systemd/resolved.conf.d/
        sudo tee /etc/systemd/resolved.conf.d/no-stub.conf > /dev/null << 'EOF'
[Resolve]
DNSStubListener=no
EOF
        sudo systemctl restart systemd-resolved 2>/dev/null || true
        log_info "Disabled systemd-resolved stub listener (prevents 127.0.0.53 DNS hijack)"
    fi

    # Disable NetworkManager's periodic connectivity checks.
    # These checks can cause WiFi disconnects in hotspot mode by detecting
    # no internet and attempting to reconfigure the interface.
    sudo mkdir -p /etc/NetworkManager/conf.d/
    sudo tee /etc/NetworkManager/conf.d/no-connectivity-check.conf > /dev/null << EOF
[connectivity]
interval=0
EOF
    log_info "Disabled NetworkManager connectivity checks (prevents hotspot disconnects)"

    # Copy wifi-connect files to home directory
    log_info "Copying wifi-connect files..."
    sudo cp "$INSTALL_DIR/wifi-connect/portal.py" "$WIFI_DIR/"
    sudo cp "$INSTALL_DIR/wifi-connect/startup_check.sh" "$WIFI_DIR/"
    sudo cp "$INSTALL_DIR/wifi-connect/wifi_worker.sh" "$WIFI_DIR/"

    # Make shell scripts executable
    sudo chmod +x "$WIFI_DIR/startup_check.sh"
    sudo chmod +x "$WIFI_DIR/wifi_worker.sh"

    # Set ownership to current user
    sudo chown $USER:$USER "$WIFI_DIR/portal.py"
    sudo chown $USER:$USER "$WIFI_DIR/startup_check.sh"
    sudo chown $USER:$USER "$WIFI_DIR/wifi_worker.sh"

    # Create systemd service for wifi captive portal
    log_info "Creating tinko-wifi systemd service..."
    sudo tee /etc/systemd/system/tinko-wifi.service > /dev/null << EOF
[Unit]
Description=Tinko Wi-Fi Captive Portal Check
After=NetworkManager.service
Before=tinko.service

[Service]
Type=oneshot
RemainAfterExit=no
ExecStart=/bin/bash $WIFI_DIR/startup_check.sh
User=root
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable service
    sudo systemctl daemon-reload
    sudo systemctl enable tinko-wifi.service

    # Install Flask for the captive portal
    log_info "Installing Flask for captive portal..."
    sudo apt-get install -y python3-flask || pip3 install Flask

    # Generate self-signed TLS cert for HTTPS captive portal checks
    log_info "Generating self-signed TLS certificate for captive portal..."
    sudo mkdir -p /etc/tinko-portal
    sudo openssl req -x509 -newkey rsa:2048 -keyout /etc/tinko-portal/key.pem \
        -out /etc/tinko-portal/cert.pem -days 3650 -nodes \
        -subj "/CN=Tinko-Setup" 2>/dev/null
    sudo chmod 644 /etc/tinko-portal/cert.pem
    sudo chmod 600 /etc/tinko-portal/key.pem
    sudo chown $USER /etc/tinko-portal/key.pem
    log_success "TLS certificate generated for captive portal HTTPS"

    # Modify Django service to wait for network
    if [[ -f /etc/systemd/system/tinko.service ]]; then
        log_info "Configuring Django service to wait for network..."
        # Check if already configured
        if ! grep -q "Wants=network-online.target" /etc/systemd/system/tinko.service 2>/dev/null; then
            # Add network dependency
            sudo sed -i '/^\[Unit\]/a Wants=network-online.target\nAfter=network-online.target' /etc/systemd/system/tinko.service
            sudo systemctl daemon-reload
        fi
    fi

    log_success "wifi-connect setup complete"
    log_info "Hotspot credentials: SSID='Tinko-Setup', Password='tinko1234'"
    log_info "To check wifi service: sudo journalctl -u tinko-wifi.service -f"
}

# Setup GPIO permissions
setup_gpio() {
    log_info "Setting up GPIO permissions..."
    
    # Add user to gpio and spi groups
    sudo usermod -a -G gpio $USER
    sudo usermod -a -G spi $USER
    
    # Add www-data to gpio and spi groups for web server access
    sudo usermod -a -G gpio www-data
    sudo usermod -a -G spi www-data
    
    log_success "User '$USER' and www-data added to gpio and spi groups"
    log_warning "You may need to log out and back in for GPIO permissions to take effect"
    log_warning "SPI access requires www-data to be in spi group for web interface"
}

# Configure audio
configure_audio() {
    log_info "Configuring audio..."
    
    # Ensure audio output is configured
    if command -v raspi-config &> /dev/null; then
        log_info "Audio configuration available via: sudo raspi-config"
        log_info "Navigate to: System Options > Audio"
    fi
    
    # Test audio device detection
    if command -v aplay &> /dev/null; then
        log_info "Available audio devices:"
        aplay -l 2>/dev/null | head -5 || log_warning "No audio devices detected yet"
    fi
    
    log_success "Audio configuration complete"
}

# Setup systemd service
setup_systemd_service() {
    log_info "Setting up systemd service..."

    read -p "Set up Tinko to start automatically on boot? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log_info "Skipping systemd service setup"
        log_info "To start manually, run:"
        log_info "  cd ${INSTALL_DIR}"
        log_info "  uv run daphne -b 0.0.0.0 -p 80 config.asgi:application"
        return
    fi

    # Get UV path
    UV_PATH="$HOME/.local/bin/uv"

    # Ensure TLS certificate exists for HTTPS
    if [[ ! -f /etc/tinko-portal/cert.pem ]] || [[ ! -f /etc/tinko-portal/key.pem ]]; then
        log_info "Generating self-signed TLS certificate..."
        sudo mkdir -p /etc/tinko-portal
        sudo openssl req -x509 -newkey rsa:2048 -keyout /etc/tinko-portal/key.pem \
            -out /etc/tinko-portal/cert.pem -days 3650 -nodes \
            -subj "/CN=tinko.local" 2>/dev/null
        sudo chmod 644 /etc/tinko-portal/cert.pem
        sudo chmod 600 /etc/tinko-portal/key.pem
        sudo chown $USER /etc/tinko-portal/key.pem
    fi

    # Create service file — Daphne serves both HTTP (80) and HTTPS (443).
    # AmbientCapabilities grants CAP_NET_BIND_SERVICE at service start time,
    # allowing Daphne to bind to privileged ports without setcap on the binary.
    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Tinko Educational Platform
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=${INSTALL_DIR}"
Environment="DJANGO_SETTINGS_MODULE=config.settings"
Environment="EDUPI_DEBUG=False"
ExecStartPre=${UV_PATH} run python manage.py collectstatic --noinput
ExecStart=${UV_PATH} run daphne -b 0.0.0.0 -p 80 -e ssl:443:privateKey=/etc/tinko-portal/key.pem:certKey=/etc/tinko-portal/cert.pem config.asgi:application
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=60

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd
    sudo systemctl daemon-reload

    # Enable service
    sudo systemctl enable ${SERVICE_NAME}

    log_success "Systemd service created and enabled"
    log_info "Service commands:"
    log_info "  Start:   sudo systemctl start ${SERVICE_NAME}"
    log_info "  Stop:    sudo systemctl stop ${SERVICE_NAME}"
    log_info "  Status:  sudo systemctl status ${SERVICE_NAME}"
    log_info "  Logs:    sudo journalctl -u ${SERVICE_NAME} -f"

    # Start the service
    read -p "Start the service now? (Y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        sudo systemctl start ${SERVICE_NAME}
        sleep 2

        if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
            log_success "Tinko service is running!"

            # Verify network binding
            log_info "Verifying network binding..."
            sleep 2

            # Check if listening on all interfaces
            if sudo netstat -tlnp 2>/dev/null | grep -q ":80.*0.0.0.0"; then
                log_success "Service is accessible from other devices on port 80"
            elif sudo ss -tlnp 2>/dev/null | grep -q ":80.*0.0.0.0"; then
                log_success "Service is accessible from other devices on port 80"
            elif sudo netstat -tlnp 2>/dev/null | grep -q "127.0.0.1:80"; then
                log_error "Service is only listening on localhost (127.0.0.1:80)"
                log_warning "This means the service is NOT accessible from other devices!"
                log_info "Checking service file configuration..."

                # Check if the service file has the correct binding
                if sudo grep -q "daphne.*-b 0.0.0.0" /etc/systemd/system/${SERVICE_NAME}.service 2>/dev/null; then
                    log_info "Service file has correct -b 0.0.0.0 flag"
                    log_info "Try restarting the service:"
                    log_info "  sudo systemctl restart ${SERVICE_NAME}"
                else
                    log_error "Service file is missing -b 0.0.0.0 flag"
                    log_info "To fix, edit the service file:"
                    log_info "  sudo systemctl stop ${SERVICE_NAME}"
                    log_info "  sudo nano /etc/systemd/system/${SERVICE_NAME}.service"
                    log_info "Ensure ExecStart line contains: -b 0.0.0.0 -p 80"
                    log_info "  sudo systemctl daemon-reload"
                    log_info "  sudo systemctl start ${SERVICE_NAME}"
                fi
            else
                log_warning "Could not verify port binding. Please check manually:"
                log_info "  sudo netstat -tlnp | grep 80"
            fi
        else
            log_error "Service failed to start. Check logs with:"
            log_info "  sudo journalctl -u ${SERVICE_NAME} -f"
        fi
    fi
}

# Test installation
test_installation() {
    log_info "Testing installation..."
    
    cd "$INSTALL_DIR"
    
    # Test Python imports
    uv run python -c "import django; print(f'Django version: {django.VERSION}')" || {
        log_error "Django import test failed"
        return 1
    }
    
    # Test GPIO import (may fail on non-Pi, that's ok)
    uv run python -c "import gpiozero; print('GPIO Zero available')" 2>/dev/null || {
        log_warning "GPIO Zero not available (expected on non-Pi systems)"
    }
    
    # Test database connection
    uv run python manage.py check --deploy 2>/dev/null || {
        log_warning "Django deployment check had warnings (this is normal for initial setup)"
    }
    
    log_success "Installation test completed"
}

# Print installation summary
print_summary() {
    PI_IP=$(hostname -I | awk '{print $1}')
    
    echo
    echo "=========================================="
    echo -e "${GREEN}Tinko Installation Complete!${NC}"
    echo "=========================================="
    echo
    echo "Access Tinko at:"
    echo "  - Dashboard:       http://${PI_IP}:/"
    echo "  - Admin Panel:     http://${PI_IP}:/admin/"
    echo "  - Noise Monitor:   http://${PI_IP}:/plugins/edupi/noise_monitor/"
    echo "  - Routines:        http://${PI_IP}:/plugins/edupi/routines/"
    echo "  - Activity Timer:  http://${PI_IP}:/plugins/edupi/activity_timer/"
    echo "  - Touch Piano:     http://${PI_IP}:/plugins/edupi/touch_piano/"
    echo
    echo "Default Admin Credentials:"
    echo "  Username: admin"
    echo "  Password: admin123"
    echo -e "  ${RED}⚠️  Please change these after first login!${NC}"
    echo
    echo "Installation Directory: ${INSTALL_DIR}"
    echo
    
    if systemctl is-enabled ${SERVICE_NAME} &>/dev/null 2>&1; then
        echo "Service Status:"
        echo "  - Auto-start: Enabled"
        SERVICE_STATUS=$(sudo systemctl is-active ${SERVICE_NAME} 2>/dev/null || echo "unknown")
        echo "  - Current status: ${SERVICE_STATUS}"
        echo
        echo "Service Commands:"
        echo "  sudo systemctl start ${SERVICE_NAME}"
        echo "  sudo systemctl stop ${SERVICE_NAME}"
        echo "  sudo systemctl restart ${SERVICE_NAME}"
        echo "  sudo journalctl -u ${SERVICE_NAME} -f"
    else
        echo "To start manually:"
        echo "  cd ${INSTALL_DIR}"
        echo "  uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application"
        echo
        echo "To set up auto-start later:"
        echo "  sudo systemctl enable ${SERVICE_NAME}"
    fi
    echo
    echo "Hardware Wiring Quick Reference:"
    echo "  Activity Timer:    RGB LED on GPIO 17, 27, 22 (R, G, B)"
    echo "  Noise Monitor:     2x RGB LEDs on GPIO 5, 6, 13 and 19, 26, 16"
    echo "  Touch Piano:       6 touch inputs on GPIO 23, 24, 10, 9, 25, 11"
    echo
    echo "See docs/developer/hardware/wiring.md for detailed wiring instructions"
    echo
    echo "WiFi Captive Portal (for headless setup):"
    echo "  Hotspot SSID: Tinko-Setup"
    echo "  Hotspot Password: tinko1234"
    echo "  Service: sudo systemctl status tinko-wifi.service"
    echo "  Logs: sudo journalctl -u tinko-wifi.service -f"
    echo
    
    log_warning "IMPORTANT: Log out and log back in for GPIO permissions to take effect"
    log_info "After logging back in, verify audio with: speaker-test -t wav"
    echo
    echo "Troubleshooting Network Access:"
    echo "  If you cannot access from other devices:"
    echo "  1. Verify port binding: sudo netstat -tlnp | grep 8000"
    echo "     Should show: 0.0.0.0:8000 (not 127.0.0.1:8000)"
    echo "  2. Check firewall: sudo ufw status"
    echo "  3. Check service logs: sudo journalctl -u ${SERVICE_NAME} -f"
    echo "  4. Verify ALLOWED_HOSTS in .env file includes your IP/hostname"
    echo
    echo "To manually start for testing:"
    echo "  cd ${INSTALL_DIR}"
    echo "  uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application"
    echo
}

# Check if Tinko is already installed and handle update
handle_existing_installation() {
    log_info "Checking for existing Tinko installation..."
    
    # Check if service exists
    if systemctl list-unit-files | grep -q "${SERVICE_NAME}.service"; then
        log_warning "Tinko service already exists!"
        
        # Check if service is running
        SERVICE_WAS_RUNNING=false
        if sudo systemctl is-active --quiet ${SERVICE_NAME} 2>/dev/null; then
            SERVICE_WAS_RUNNING=true
            log_info "Service is currently running"
            
            log_info "Stopping Tinko service for update..."
            sudo systemctl stop ${SERVICE_NAME}
            sleep 2
            
            if sudo systemctl is-active --quiet ${SERVICE_NAME} 2>/dev/null; then
                log_error "Failed to stop service. Please stop it manually:"
                log_info "  sudo systemctl stop ${SERVICE_NAME}"
                exit 1
            fi
            log_success "Service stopped successfully"
        else
            log_info "Service is not running"
        fi
        
        # Store the fact that we're updating
        export TINKO_UPDATE_MODE=true
        export TINKO_SERVICE_WAS_RUNNING=$SERVICE_WAS_RUNNING
        
        log_info "Update mode activated - will restart service after installation"
    else
        log_info "No existing Tinko installation found"
        export TINKO_UPDATE_MODE=false
        export TINKO_SERVICE_WAS_RUNNING=false
    fi
}

# Restart service after update if it was running
restart_service_after_update() {
    if [[ "$TINKO_UPDATE_MODE" == "true" && "$TINKO_SERVICE_WAS_RUNNING" == "true" ]]; then
        log_info "Restarting Tinko service after update..."
        
        # Reload systemd in case service file changed
        sudo systemctl daemon-reload
        
        # Wait for port 80 to be fully released (avoids crash-restart loop)
        log_info "Waiting for port 80 to be released..."
        for i in $(seq 1 15); do
            if ! sudo ss -tlnp 2>/dev/null | grep -q ":80\b"; then
                log_success "Port 80 is free"
                break
            fi
            if [[ "$i" -eq 15 ]]; then
                log_warning "Port 80 still in use after 15s, forcing start anyway"
            else
                sleep 1
            fi
        done
        
        sudo systemctl restart ${SERVICE_NAME}
        sleep 2
        
        if sudo systemctl is-active --quiet ${SERVICE_NAME}; then
            log_success "Service restarted successfully!"
            
            # Verify network binding
            log_info "Verifying network binding..."
            sleep 2
            
            if sudo netstat -tlnp 2>/dev/null | grep -q ":8000.*0.0.0.0"; then
                log_success "Service is accessible from other devices on port 8000"
            elif sudo ss -tlnp 2>/dev/null | grep -q ":8000.*0.0.0.0"; then
                log_success "Service is accessible from other devices on port 8000"
            elif sudo netstat -tlnp 2>/dev/null | grep -q "127.0.0.1:8000"; then
                log_warning "Service is only listening on localhost (127.0.0.1:8000)"
            fi
        else
            log_error "Service failed to restart. Check logs with:"
            log_info "  sudo journalctl -u ${SERVICE_NAME} -f"
        fi
    fi
}

# Main installation function
main() {
    echo
    echo "=========================================="
    echo "Tinko - Raspberry Pi Installation Script"
    echo "=========================================="
    echo
    echo "This script will:"
    echo "  1. Update system packages"
    echo "  2. Install system dependencies"
    echo "  3. Install UV package manager"
    echo "  4. Install Python dependencies"
    echo "  5. Configure environment"
    echo "  6. Run database migrations"
    echo "  7. Create admin user"
    echo "  8. Set up GPIO permissions"
    echo "  9. Optionally set up auto-start service"
    echo
    
    read -p "Continue with installation? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log_info "Installation cancelled"
        exit 0
    fi
    
    check_root
    check_platform
    check_internet
    handle_existing_installation
    
    log_info "Starting installation..."
    
    update_system
    install_system_deps
    install_uv
    install_python_deps
    setup_environment
    run_migrations
    create_superuser
    collect_static
    compile_translations
    setup_gpio
    configure_audio
    setup_wifi_connect
    test_installation
    setup_systemd_service
    restart_service_after_update
    
    print_summary
}

# Handle script interruption
trap 'log_error "Installation interrupted"; exit 1' INT TERM

# Run main function
main "$@"
