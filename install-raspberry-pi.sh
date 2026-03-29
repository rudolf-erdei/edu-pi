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
        alsa-utils || true
    
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

# Setup GPIO permissions
setup_gpio() {
    log_info "Setting up GPIO permissions..."
    
    # Add user to gpio group
    sudo usermod -a -G gpio $USER
    
    log_success "User '$USER' added to gpio group"
    log_warning "You may need to log out and back in for GPIO permissions to take effect"
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

# Create systemd service
setup_systemd_service() {
    log_info "Setting up systemd service..."
    
    read -p "Set up Tinko to start automatically on boot? (Y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Nn]$ ]]; then
        log_info "Skipping systemd service setup"
        log_info "To start manually, run:"
        log_info "  cd ${INSTALL_DIR}"
        log_info "  uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application"
        return
    fi
    
    # Get UV path
    UV_PATH="$HOME/.local/bin/uv"
    
    # Create service file
    sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null << EOF
[Unit]
Description=Tinko Educational Platform
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=${INSTALL_DIR}
Environment="PATH=$HOME/.local/bin"
Environment="PYTHONPATH=${INSTALL_DIR}"
Environment="DJANGO_SETTINGS_MODULE=config.settings"
Environment="EDUPI_DEBUG=False"
ExecStartPre=${UV_PATH} run python manage.py migrate --noinput
ExecStartPre=${UV_PATH} run python manage.py collectstatic --noinput
ExecStart=${UV_PATH} run daphne -b 0.0.0.0 -p 8000 config.asgi:application
Restart=always
RestartSec=3

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
            if sudo netstat -tlnp 2>/dev/null | grep -q ":8000.*0.0.0.0"; then
                log_success "Service is accessible from other devices on port 8000"
            elif sudo ss -tlnp 2>/dev/null | grep -q ":8000.*0.0.0.0"; then
                log_success "Service is accessible from other devices on port 8000"
            elif sudo netstat -tlnp 2>/dev/null | grep -q "127.0.0.1:8000"; then
                log_error "Service is only listening on localhost (127.0.0.1:8000)"
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
                    log_info "Ensure ExecStart line contains: -b 0.0.0.0 -p 8000"
                    log_info "  sudo systemctl daemon-reload"
                    log_info "  sudo systemctl start ${SERVICE_NAME}"
                fi
            else
                log_warning "Could not verify port binding. Please check manually:"
                log_info "  sudo netstat -tlnp | grep 8000"
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
    echo "  - Dashboard:       http://${PI_IP}:8000/"
    echo "  - Admin Panel:     http://${PI_IP}:8000/admin/"
    echo "  - Noise Monitor:   http://${PI_IP}:8000/plugins/edupi/noise_monitor/"
    echo "  - Routines:        http://${PI_IP}:8000/plugins/edupi/routines/"
    echo "  - Activity Timer:  http://${PI_IP}:8000/plugins/edupi/activity_timer/"
    echo "  - Touch Piano:     http://${PI_IP}:8000/plugins/edupi/touch_piano/"
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
    test_installation
    setup_systemd_service
    
    print_summary
}

# Handle script interruption
trap 'log_error "Installation interrupted"; exit 1' INT TERM

# Run main function
main "$@"
