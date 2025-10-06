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

### Essential Components
- **Linux SBC**: Raspberry Pi 4B (4GB RAM recommended) or compatible ARM64/x86_64 system
- **Touchscreen**: 7-inch display with 1024x600 resolution (capacitive touch recommended)
- **Proxmark3**: Iceman fork v4.18994+ ⚠️ Original Proxmark3 firmware NOT supported
- **USB Camera**: For barcode scanning (UPC/EAN compatible)
- **RFID Tags**: MIFARE Classic S50 (1K) tags for filament spools

### Recommended Setup
- **Mounting**: Industrial touchscreen enclosure for manufacturing environment
- **Connectivity**: Ethernet connection for reliable network access
- **Power**: 5V 3A+ power supply for stable operation
- **Storage**: 32GB+ microSD card (Class 10 or better)

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

## Tech Stack

- **Backend**: FastAPI + Python with async Proxmark3 communication
- **Frontend**: React with real-time WebSocket updates
- **Database**: MongoDB for session and log storage
- **Hardware**: Proxmark3 Iceman fork for RFID operations
