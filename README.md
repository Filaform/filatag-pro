# FilaTag Pro - Professional RFID Programming System

A complete, production-ready RFID programming solution for filament spools using Proxmark3 hardware. FilaTag Pro programs two 13.56 MHz MIFARE Classic S50 (1K) RFID tags per spool with automated barcode scanning and detection capabilities.

## 🚀 Features

- **🖥️ Touchscreen Interface**: Optimized for 7-inch displays (1024x600) with touch-friendly controls
- **📷 Barcode Scanning**: Automatic filament detection via USB webcam with UPC/EAN support
- **🤖 Auto-Detection**: Automatic RFID tag detection and programming when placed on antenna
- **⚡ Real-time Updates**: Live progress tracking with WebSocket communication
- **🎯 Dual Tag Programming**: Program and verify two RFID tags per spool automatically
- **💻 CLI Tool**: Complete command-line interface for headless operations
- **🧪 Mock Mode**: Full simulation for testing and development without hardware
- **📊 Structured Logging**: JSON audit logs with clear functionality and export
- **⚙️ Comprehensive Settings**: Device paths, verification modes, camera configuration
- **🔒 Security**: MIFARE key management and secure configuration storage

## 🏭 Hardware Requirements

### Tested & Supported Platforms

#### Sonic Pad (Primary Target)
- **OS**: Debian 11 (Bullseye)
- **Kernel**: 4.9.191
- **CPU**: 4-core ARM Cortex-A53 @ 1.5 GHz (aarch64)
- **Python**: 3.11.9+ (3.9.2+ minimum supported)
- **Memory**: ~2 GB RAM
- **Display**: Built-in touchscreen interface
- **Status**: ✅ Fully supported with native desktop app

#### Raspberry Pi 4B+ (Alternative)
- **OS**: Raspberry Pi OS (64-bit) or Ubuntu 20.04+
- **CPU**: ARM Cortex-A72 quad-core @ 1.8 GHz
- **Memory**: 4GB+ RAM recommended
- **Display**: 7-inch touchscreen (1024x600 resolution)
- **Status**: ✅ Fully supported

### Essential Components
- **Proxmark3**: Iceman fork v4.18994+ ⚠️ Original Proxmark3 firmware NOT supported
- **USB Camera**: For barcode scanning (UPC/EAN compatible)
- **RFID Tags**: MIFARE Classic S50 (1K) tags for filament spools

### For Headless Systems (No Desktop Environment)
FilaTag Pro includes a **native desktop application** that works without a desktop environment:
- Uses `pywebview` for embedded GUI on systems without X11/Wayland
- Automatically detects and adapts to available GUI frameworks
- Perfect for industrial controllers and embedded devices

## 📥 Installation

### Prerequisites

Before installing FilaTag Pro, ensure you have:
- Fresh Raspberry Pi OS (64-bit) or Ubuntu 20.04+ installation
- Internet connectivity for downloading dependencies
- sudo/root access for system configuration
- Basic familiarity with Linux command line

### Step 1: Clone from GitHub

```bash
# Clone the FilaTag Pro repository
git clone https://github.com/your-organization/filatag-pro.git
cd filatag-pro

# Or download and extract if you don't have git
wget https://github.com/your-organization/filatag-pro/archive/main.zip
unzip main.zip
cd filatag-pro-main
```

### Step 2: Install System Dependencies

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install essential packages
sudo apt install -y \
    python3 python3-pip python3-venv \
    nodejs npm yarn \
    git curl wget \
    build-essential \
    libopencv-dev python3-opencv \
    mongodb \
    supervisor nginx

# Install Proxmark3 Iceman Fork
cd /tmp
git clone https://github.com/RfidResearchGroup/proxmark3.git
cd proxmark3
make clean && make all
sudo make install

# Verify Proxmark3 installation
pm3 --version
```

### Step 3: Setup Proxmark3 Permissions

Create udev rules for hardware device access:

```bash
# Create Proxmark3 device rules
sudo tee /etc/udev/rules.d/77-proxmark3.rules << 'EOF'
# Proxmark3 RDV4.0, Proxmark3 Easy
SUBSYSTEM=="usb", ATTRS{idVendor}=="2d2d", ATTRS{idProduct}=="504d", GROUP="plugdev", MODE="0664"
SUBSYSTEM=="usb", ATTRS{idVendor}=="9ac4", ATTRS{idProduct}=="4b8f", GROUP="plugdev", MODE="0664"
# Proxmark3 RDV4.0 (CDC ACM)
KERNEL=="ttyACM[0-9]*", ATTRS{idVendor}=="2d2d", ATTRS{idProduct}=="504d", GROUP="plugdev", MODE="0664"
EOF

# Create camera device rules (optional, for specific camera access)
sudo tee -a /etc/udev/rules.d/77-camera.rules << 'EOF'
# USB Camera devices
KERNEL=="video[0-9]*", GROUP="video", MODE="0664"
SUBSYSTEM=="video4linux", GROUP="video", MODE="0664"
EOF

# Reload udev rules and add user to groups
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -a -G plugdev,video,dialout $USER

# Logout and login again for group changes to take effect
echo "Please logout and login again for group permissions to take effect"
```

### Step 4: Install FilaTag Pro Application

```bash
# Navigate back to cloned repository
cd /path/to/filatag-pro  # Or wherever you cloned it

# Copy application to system directory
sudo mkdir -p /opt/filatag
sudo cp -r * /opt/filatag/
sudo chown -R $USER:$USER /opt/filatag
cd /opt/filatag

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r backend/requirements.txt

# Install Node.js dependencies (using yarn for better performance)
cd frontend
yarn install
cd ..

# Make CLI executable
chmod +x cli.py
chmod +x *.py
```

### Step 5: Create Directory Structure and Configuration

```bash
# Create system directories
sudo mkdir -p /opt/filatag/binaries
sudo mkdir -p /etc/filatag
sudo mkdir -p /var/log/filatag

# Copy configuration files from repository
sudo cp /opt/filatag/config/config.json /etc/filatag/
sudo cp /opt/filatag/config/mapping.json /etc/filatag/
sudo cp /opt/filatag/config/barcode_mapping.json /etc/filatag/

# Create sample binary files (for testing)
cd /opt/filatag
python3 -c "
import os
from pathlib import Path

binaries_path = Path('/opt/filatag/binaries')
binaries_path.mkdir(exist_ok=True)

for sku in ['pla001', 'abs002', 'petg003', 'tpu004', 'wood005']:
    with open(binaries_path / f'{sku}.bin', 'wb') as f:
        # Create 1KB sample binary data
        data = bytearray(1024)
        pattern = hash(sku) % 256
        for i in range(1024):
            data[i] = (pattern + i) % 256
        f.write(data)
    print(f'Created {sku}.bin (1024 bytes)')
"

# Set proper permissions
sudo chown -R filatag:filatag /opt/filatag
sudo chown -R filatag:filatag /etc/filatag
sudo chown -R filatag:filatag /var/log/filatag
sudo chmod 755 /var/log/filatag
sudo chmod 644 /etc/filatag/*
```

### Step 6: Configure Services

```bash
# Create user for running FilaTag services
sudo useradd -r -s /bin/false -d /opt/filatag filatag
sudo usermod -a -G plugdev,video,dialout filatag

# Install systemd service file
sudo cp /opt/filatag/filatag.service /etc/systemd/system/

# Configure supervisor for service management
sudo cp /opt/filatag/config/supervisor.conf /etc/supervisor/conf.d/filatag.conf

# Configure MongoDB for FilaTag
sudo systemctl enable mongodb
sudo systemctl start mongodb

# Create MongoDB database and user
mongo << 'EOF'
use filatag_db
db.createUser({
  user: "filatag",
  pwd: "secure_password_here",
  roles: [{ role: "readWrite", db: "filatag_db" }]
})
EOF

# Start and enable services
sudo systemctl daemon-reload
sudo systemctl enable filatag
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start filatag:*

# Check service status
sudo systemctl status filatag
sudo supervisorctl status
```

### Step 7: Verify Installation

```bash
# Test CLI functionality
cd /opt/filatag
python3 cli.py list-filaments
python3 cli.py device-status --mock

# Test auto-programming in mock mode
python3 cli.py auto-program --sku PLA001 --mock

# Run comprehensive demo
python3 filaform_demo.py

# Check web interface (should show FilaTag Pro interface)
curl -s http://localhost:3000 | grep "FilaTag PRO"

# Check API endpoints
curl -s http://localhost:8001/api/device/status
curl -s http://localhost:8001/api/filaments

# Verify logs
tail -f /var/log/filatag/actions.log
```

## 🚀 Quick Start Guide

### First Time Setup

1. **Connect Hardware**: 
   - Plug in Proxmark3 via USB
   - Connect USB camera for barcode scanning
   - Ensure 7-inch touchscreen is connected and configured

2. **Access Web Interface**: 
   - Open browser on connected device
   - Navigate to `http://[raspberry-pi-ip]:3000`
   - You should see the FilaTag Pro interface

3. **Test System**:
   - Check "Status" tab to verify Proxmark3 and camera connection
   - Try programming a test spool in mock mode
   - Review logs to ensure everything is working

### Daily Operation

1. **Power On**: System should auto-start with touchscreen interface
2. **Scan Barcode**: Point camera at filament spool barcode (optional)
3. **Select Filament**: Choose from dropdown or use barcode detection
4. **Start Programming**: Tap the green "START PROGRAMMING" button
5. **Place Tags**: Follow on-screen prompts for Tag #1 and Tag #2
6. **Complete**: System automatically programs and verifies both tags

## 💻 Usage

### Touchscreen Interface (Primary Method)

**Optimized for 7-inch displays (1024x600 resolution)**

1. **Access**: Touch interface should auto-start on boot
2. **Barcode Scan**: Camera automatically detects UPC/EAN barcodes
3. **Select Filament**: Touch dropdown or use auto-detected type
4. **Start Programming**: Large green button starts automated workflow
5. **Follow Prompts**: Place Tag #1, then Tag #2 when prompted
6. **View Status**: Check system status and logs via touch navigation

### CLI Tool

```bash
# List available filaments
python3 /app/cli.py list-filaments

# Check device status
python3 /app/cli.py device-status

# Program a spool (interactive)
python3 /app/cli.py program --sku PLA001 --spool SPOOL001 --operator john

# Program in mock mode (for testing)
python3 /app/cli.py program --sku PLA001 --spool SPOOL001 --mock

# Verify binary file
python3 /app/cli.py verify --binary-file /path/to/file.bin
```

## Mock Mode

For development and testing without hardware:

### Enable Mock Mode
```bash
# Temporary (current session)
export FILATAG_MOCK=true

# Permanent (in config)
echo '{"mock_mode": true}' > /etc/filatag/config.json
```

### Mock Features
- Simulates all Proxmark3 commands
- Realistic command delays and responses
- Full programming workflow testing
- No hardware required

## 🛠️ Development & Contributing

### Development Setup

```bash
# Clone repository for development
git clone https://github.com/your-organization/filatag-pro.git
cd filatag-pro

# Install development dependencies
pip install -r requirements-dev.txt
yarn install --dev

# Run in development mode
# Backend (with hot reload)
cd backend && python server.py

# Frontend (with hot reload)  
cd frontend && yarn start

# Run tests
python -m pytest tests/
yarn test
```

### Project Structure

```
filatag-pro/
├── backend/                 # FastAPI backend application
│   ├── server.py           # Main server application
│   ├── camera_scanner.py   # Barcode scanning module
│   ├── auto_detector.py    # RFID auto-detection module
│   └── requirements.txt    # Python dependencies
├── frontend/               # React frontend application  
│   ├── src/
│   │   ├── App.js         # Main application component
│   │   ├── components/ui/ # Shadcn UI components
│   │   └── App.css        # Touchscreen-optimized styles
│   ├── public/            # Static assets and favicon
│   └── package.json       # Node.js dependencies
├── config/                # Configuration templates
│   ├── config.json        # System configuration
│   ├── mapping.json       # Filament SKU mapping
│   └── supervisor.conf    # Service configuration
├── tests/                 # Test suites
│   ├── test_filatag.py   # Unit tests
│   └── integration/       # Integration tests
├── cli.py                 # Command-line interface
├── filaform_demo.py      # Comprehensive demo script
├── filatag.service       # Systemd service file
└── README.md             # This file
```

### Contributing

1. Fork the repository on GitHub
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Reporting Issues

Please report issues on the GitHub issue tracker with:
- FilaTag Pro version
- Hardware configuration (Raspberry Pi model, Proxmark3 version)
- Steps to reproduce the issue
- Expected vs actual behavior
- Log files from `/var/log/filatag/actions.log`

## 🧪 Tech Stack

- **Backend**: FastAPI + Python 3.9+ with async Proxmark3 communication
- **Frontend**: React 19 with Shadcn UI components, optimized for touchscreens
- **Database**: MongoDB for session storage and audit logging
- **Hardware**: Proxmark3 Iceman fork v4.18994+ for RFID operations
- **Camera**: OpenCV + pyzbar for UPC/EAN barcode scanning
- **Services**: Supervisor for process management, systemd for system integration

## 📋 System Requirements

### Minimum Requirements
- **CPU**: ARM Cortex-A72 1.5GHz (Raspberry Pi 4B) or equivalent x86_64
- **RAM**: 2GB (4GB recommended for optimal performance)
- **Storage**: 16GB microSD/eMMC (32GB recommended)
- **Display**: 7-inch touchscreen with 1024x600 resolution
- **USB Ports**: 2x USB 2.0+ (Proxmark3 + camera)
- **Network**: Ethernet or Wi-Fi for web interface access

### Recommended Configuration
- **Device**: Raspberry Pi 4B (4GB RAM)
- **Display**: Official Raspberry Pi 7" touchscreen or equivalent
- **Storage**: SanDisk Extreme 32GB microSD (Class 10, A2)
- **Case**: Industrial touchscreen enclosure with DIN rail mounting
- **Power**: Official Raspberry Pi 4 Power Supply (5.1V, 3A)

## 🔄 Updates & Maintenance

### Updating FilaTag Pro

```bash
# Navigate to installation directory
cd /opt/filatag

# Backup current configuration
sudo cp -r /etc/filatag /etc/filatag.backup.$(date +%Y%m%d)

# Pull latest changes from GitHub
git pull origin main

# Update Python dependencies
source venv/bin/activate
pip install -r backend/requirements.txt

# Update frontend dependencies
cd frontend && yarn install && cd ..

# Restart services
sudo supervisorctl restart filatag:*

# Verify update
python3 cli.py device-status --mock
```

### Backup & Restore

```bash
# Create backup
sudo tar -czf filatag-backup-$(date +%Y%m%d).tar.gz \
    /etc/filatag/ \
    /opt/filatag/binaries/ \
    /var/log/filatag/

# Restore from backup
sudo tar -xzf filatag-backup-YYYYMMDD.tar.gz -C /
sudo systemctl restart filatag
```

## 🚀 Deployment Options

### Production Deployment (Recommended)

```bash
# Using systemd service
sudo systemctl enable filatag
sudo systemctl start filatag

# Auto-start touchscreen interface on boot
sudo systemctl enable lightdm
echo "@chromium-browser --kiosk --disable-infobars http://localhost:3000" >> ~/.config/lxsession/LXDE-pi/autostart
```

### Kiosk Mode Setup (Manufacturing Environment)

```bash
# Configure automatic login
sudo raspi-config  # Enable auto-login to desktop

# Hide cursor and disable screen blanking
echo "xset s off && xset -dpms && xset s noblank" >> ~/.xsessionrc

# Auto-start FilaTag Pro interface
cat > ~/.config/autostart/filatag.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=FilaTag Pro
Exec=chromium-browser --kiosk --disable-infobars --touch-events --disable-pinch http://localhost:3000
EOF
```

## 📞 Support & Documentation

### Getting Help

1. **GitHub Issues**: Report bugs and feature requests at [GitHub Repository](https://github.com/your-organization/filatag-pro/issues)
2. **Documentation**: Complete API documentation available in `/docs/` folder
3. **Community**: Join discussions in GitHub Discussions
4. **Commercial Support**: Contact Filaform for enterprise support options

### Troubleshooting Resources

- **Logs**: Check `/var/log/filatag/actions.log` for detailed operation logs
- **Mock Mode**: Use `--mock` flag for testing without hardware
- **Demo Script**: Run `python3 filaform_demo.py` for comprehensive system test
- **Health Check**: Visit `http://localhost:8001/api/device/status` for API status

## 📜 License & Legal

This project is licensed under the MIT License. See [LICENSE](LICENSE) file for details.

### Third-Party Licenses
- **Proxmark3**: GPL v2 - RRG/Iceman firmware required
- **React**: MIT License
- **FastAPI**: MIT License  
- **MongoDB**: Server Side Public License (SSPL)
- **OpenCV**: Apache License 2.0

## 📊 Version History

- **v2.0.0** (Current): FilaTag Pro with touchscreen interface
  - 7-inch touchscreen optimization (1024x600)
  - Automated barcode scanning with UPC/EAN support
  - Auto-detection and programming workflow
  - Professional Filaform branding
  - Enhanced logging with clear functionality
  - Comprehensive settings management
  - Production-ready kiosk interface

- **v1.5.0**: Enhanced automation features
  - Auto RFID detection and programming
  - Camera integration for barcode scanning
  - Real-time status updates and progress tracking
  - Enhanced CLI with auto-program command

- **v1.0.0**: Initial release
  - Basic web UI and CLI interface
  - MIFARE Classic 1K support
  - Dual tag programming per spool
  - Mock mode for testing
  - Structured JSON logging

---

**FilaTag Pro** - Professional RFID Programming System by [Filaform](https://filaform.com)

For commercial licensing, enterprise support, or custom development inquiries, please contact: support@filaform.com