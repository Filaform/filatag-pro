#!/bin/bash
#
# FilaTag Pro - One-Click Installation Script
# 
# This script automates the complete installation of FilaTag Pro
# from GitHub repository to a fully configured system.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/your-org/filatag-pro/main/install.sh | bash
#   # or
#   wget -qO- https://raw.githubusercontent.com/your-org/filatag-pro/main/install.sh | bash
#   # or  
#   git clone https://github.com/your-org/filatag-pro.git && cd filatag-pro && ./install.sh
#

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Installation configuration
REPO_URL="https://github.com/your-organization/filatag-pro.git"
INSTALL_DIR="/opt/filatag"
USER="filatag"
VERSION="v2.0.0"

print_banner() {
    echo -e "${BLUE}"
    cat << 'EOF'
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║    ███████╗██╗██╗      █████╗ ████████╗ █████╗  ██████╗     ║
    ║    ██╔════╝██║██║     ██╔══██╗╚══██╔══╝██╔══██╗██╔════╝     ║
    ║    █████╗  ██║██║     ███████║   ██║   ███████║██║  ███╗    ║
    ║    ██╔══╝  ██║██║     ██╔══██║   ██║   ██╔══██║██║   ██║    ║
    ║    ██║     ██║███████╗██║  ██║   ██║   ██║  ██║╚██████╔╝    ║
    ║    ╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝     ║
    ║                                                              ║
    ║                        PRO v2.0.0                           ║
    ║              Professional RFID Programming System            ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
EOF
    echo -e "${NC}"
}

log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root. Please run as a regular user with sudo access."
    fi
}

check_os() {
    log "Checking operating system compatibility..."
    
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Check if it's Ubuntu/Debian based
        if command -v apt-get &> /dev/null; then
            log "Detected Debian/Ubuntu-based system"
            PACKAGE_MANAGER="apt"
        else
            error "Unsupported Linux distribution. This installer requires Debian/Ubuntu-based systems."
        fi
    else
        error "Unsupported operating system. FilaTag Pro requires Linux (Debian/Ubuntu-based)."
    fi
}

install_dependencies() {
    log "Installing system dependencies..."
    
    # Update package lists
    sudo apt update
    
    # Install essential packages
    sudo apt install -y \
        git curl wget \
        python3 python3-pip python3-venv \
        nodejs npm \
        build-essential \
        libopencv-dev python3-opencv \
        mongodb \
        supervisor nginx \
        usbutils
    
    # Install yarn (better than npm for our frontend)
    if ! command -v yarn &> /dev/null; then
        log "Installing Yarn package manager..."
        curl -fsSL https://dl.yarnpkg.com/debian/pubkey.gpg | sudo apt-key add -
        echo "deb https://dl.yarnpkg.com/debian/ stable main" | sudo tee /etc/apt/sources.list.d/yarn.list
        sudo apt update && sudo apt install -y yarn
    fi
    
    log "System dependencies installed successfully"
}

install_proxmark3() {
    log "Installing Proxmark3 Iceman fork..."
    
    # Check if Proxmark3 is already installed
    if command -v pm3 &> /dev/null; then
        local version=$(pm3 --version 2>&1 | grep -o 'v[0-9]\+\.[0-9]\+\.[0-9]\+' || echo "unknown")
        log "Proxmark3 already installed: $version"
        return 0
    fi
    
    # Install Proxmark3 build dependencies
    sudo apt install -y \
        build-essential pkg-config \
        libreadline-dev gcc-arm-none-eabi libnewlib-arm-none-eabi \
        qtbase5-dev qtbase5-dev-tools
    
    # Clone and build Proxmark3
    cd /tmp
    if [[ -d "proxmark3" ]]; then
        rm -rf proxmark3
    fi
    
    git clone https://github.com/RfidResearchGroup/proxmark3.git
    cd proxmark3
    
    log "Building Proxmark3... (this may take several minutes)"
    make clean && make all
    
    log "Installing Proxmark3..."
    sudo make install
    
    # Verify installation
    if command -v pm3 &> /dev/null; then
        log "Proxmark3 installed successfully"
    else
        error "Proxmark3 installation failed"
    fi
    
    cd ~
}

setup_udev_rules() {
    log "Setting up device permissions..."
    
    # Proxmark3 rules
    sudo tee /etc/udev/rules.d/77-proxmark3.rules > /dev/null << 'EOF'
# Proxmark3 RDV4.0, Proxmark3 Easy
SUBSYSTEM=="usb", ATTRS{idVendor}=="2d2d", ATTRS{idProduct}=="504d", GROUP="plugdev", MODE="0664"
SUBSYSTEM=="usb", ATTRS{idVendor}=="9ac4", ATTRS{idProduct}=="4b8f", GROUP="plugdev", MODE="0664"
# Proxmark3 RDV4.0 (CDC ACM)
KERNEL=="ttyACM[0-9]*", ATTRS{idVendor}=="2d2d", ATTRS{idProduct}=="504d", GROUP="plugdev", MODE="0664"
EOF

    # Camera rules
    sudo tee /etc/udev/rules.d/77-camera.rules > /dev/null << 'EOF'
# USB Camera devices
KERNEL=="video[0-9]*", GROUP="video", MODE="0664"
SUBSYSTEM=="video4linux", GROUP="video", MODE="0664"
EOF

    # Reload rules
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    
    # Add user to groups
    sudo usermod -a -G plugdev,video,dialout $USER
    
    log "Device permissions configured"
}

clone_repository() {
    log "Cloning FilaTag Pro repository..."
    
    # Remove existing installation if present
    if [[ -d "$INSTALL_DIR" ]]; then
        warn "Existing installation found at $INSTALL_DIR"
        read -p "Do you want to backup and continue? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo mv "$INSTALL_DIR" "${INSTALL_DIR}.backup.$(date +%Y%m%d_%H%M%S)"
            log "Existing installation backed up"
        else
            error "Installation cancelled"
        fi
    fi
    
    # Clone repository
    sudo mkdir -p "$INSTALL_DIR"
    sudo git clone "$REPO_URL" "$INSTALL_DIR"
    sudo chown -R $USER:$USER "$INSTALL_DIR"
    
    cd "$INSTALL_DIR"
    log "Repository cloned successfully"
}

install_application() {
    log "Installing FilaTag Pro application..."
    
    cd "$INSTALL_DIR"
    
    # Create Python virtual environment
    python3 -m venv venv
    source venv/bin/activate
    
    # Install Python dependencies
    pip install --upgrade pip
    pip install -r backend/requirements.txt
    
    # Install Node.js dependencies
    cd frontend
    yarn install --production
    cd ..
    
    # Make scripts executable
    chmod +x cli.py *.py
    
    log "Application dependencies installed"
}

setup_directories() {
    log "Setting up system directories..."
    
    # Create required directories
    sudo mkdir -p /opt/filatag/binaries
    sudo mkdir -p /etc/filatag
    sudo mkdir -p /var/log/filatag
    
    # Copy configuration files
    sudo cp "$INSTALL_DIR"/config/* /etc/filatag/ 2>/dev/null || true
    
    # Create sample binary files
    cd "$INSTALL_DIR"
    python3 -c "
import os
from pathlib import Path

binaries_path = Path('/opt/filatag/binaries')
binaries_path.mkdir(exist_ok=True)

for sku in ['pla001', 'abs002', 'petg003', 'tpu004', 'wood005']:
    with open(binaries_path / f'{sku}.bin', 'wb') as f:
        data = bytearray(1024)
        pattern = hash(sku) % 256
        for i in range(1024):
            data[i] = (pattern + i) % 256
        f.write(data)
    print(f'Created {sku}.bin')
"
    
    # Set proper permissions
    sudo chown -R $USER:$USER "$INSTALL_DIR"
    sudo chmod 755 /var/log/filatag
    
    log "Directory structure created"
}

configure_services() {
    log "Configuring system services..."
    
    # Create filatag user for services
    if ! id "filatag" &>/dev/null; then
        sudo useradd -r -s /bin/false -d "$INSTALL_DIR" filatag
        sudo usermod -a -G plugdev,video,dialout filatag
    fi
    
    # Install systemd service
    sudo cp "$INSTALL_DIR/filatag.service" /etc/systemd/system/
    
    # Configure supervisor (if config exists)
    if [[ -f "$INSTALL_DIR/config/supervisor.conf" ]]; then
        sudo cp "$INSTALL_DIR/config/supervisor.conf" /etc/supervisor/conf.d/filatag.conf
    fi
    
    # Enable and start MongoDB
    sudo systemctl enable mongodb
    sudo systemctl start mongodb
    
    # Start FilaTag services
    sudo systemctl daemon-reload
    sudo systemctl enable filatag
    
    log "Services configured"
}

test_installation() {
    log "Testing installation..."
    
    cd "$INSTALL_DIR"
    
    # Test CLI
    if python3 cli.py list-filaments > /dev/null 2>&1; then
        log "✓ CLI functionality working"
    else
        warn "CLI test failed - check configuration"
    fi
    
    # Test mock mode
    if timeout 10 python3 cli.py device-status --mock > /dev/null 2>&1; then
        log "✓ Mock mode working"
    else
        warn "Mock mode test failed"
    fi
    
    # Start services and test
    sudo systemctl start filatag
    sleep 5
    
    if curl -s http://localhost:3000 | grep -q "FilaTag"; then
        log "✓ Web interface accessible"
    else
        warn "Web interface test failed - services may need time to start"
    fi
    
    if curl -s http://localhost:8001/api/device/status > /dev/null 2>&1; then
        log "✓ API endpoints responding"
    else
        warn "API test failed - backend may need time to start"
    fi
}

print_completion() {
    log "Installation completed!"
    
    echo -e "\n${GREEN}╔══════════════════════════════════════════════════════════════╗"
    echo "║                    INSTALLATION COMPLETE                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝${NC}"
    
    echo -e "\n${YELLOW}Next Steps:${NC}"
    echo "1. Reboot the system to ensure all group permissions take effect:"
    echo "   sudo reboot"
    echo ""
    echo "2. After reboot, access FilaTag Pro:"
    echo "   • Web Interface: http://$(hostname -I | awk '{print $1}'):3000"
    echo "   • CLI Tool: cd $INSTALL_DIR && python3 cli.py --help"
    echo ""
    echo "3. Connect hardware:"
    echo "   • Plug in Proxmark3 via USB"
    echo "   • Connect USB camera for barcode scanning"
    echo "   • Connect 7-inch touchscreen if using kiosk mode"
    echo ""
    echo "4. Test the system:"
    echo "   • Run: python3 $INSTALL_DIR/filaform_demo.py"
    echo "   • Check device status in the web interface"
    echo "   • Try programming in mock mode first"
    echo ""
    echo -e "${YELLOW}Support Resources:${NC}"
    echo "• Documentation: $INSTALL_DIR/README.md"
    echo "• Logs: /var/log/filatag/actions.log"
    echo "• GitHub: $REPO_URL"
    echo "• Issues: ${REPO_URL}/issues"
    echo ""
    echo -e "${GREEN}FilaTag Pro v$VERSION installed successfully!${NC}"
}

# Main installation flow
main() {
    print_banner
    
    log "Starting FilaTag Pro installation..."
    
    check_root
    check_os
    install_dependencies
    install_proxmark3
    setup_udev_rules
    clone_repository
    install_application
    setup_directories
    configure_services
    test_installation
    print_completion
}

# Run main function
main "$@"