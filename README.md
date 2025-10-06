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

Create udev rules for Proxmark3 device access:

```bash
sudo tee /etc/udev/rules.d/77-proxmark3.rules << EOF
# Proxmark3 RDV4.0, Proxmark3 Easy
SUBSYSTEM=="usb", ATTRS{idVendor}=="2d2d", ATTRS{idProduct}=="504d", GROUP="plugdev", MODE="0664"
SUBSYSTEM=="usb", ATTRS{idVendor}=="9ac4", ATTRS{idProduct}=="4b8f", GROUP="plugdev", MODE="0664"
# Proxmark3 RDV4.0 (CDC ACM)
KERNEL=="ttyACM[0-9]*", ATTRS{idVendor}=="2d2d", ATTRS{idProduct}=="504d", GROUP="plugdev", MODE="0664"
EOF

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger

# Add current user to plugdev group
sudo usermod -a -G plugdev $USER
```

### 3. Install Application

```bash
# Clone or copy the application files to /opt/filatag
sudo mkdir -p /opt/filatag
sudo cp -r /app/* /opt/filatag/
cd /opt/filatag

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies  
pip install -r backend/requirements.txt

# Install Node.js dependencies
cd frontend && npm install
cd ..
```

### 4. Create Directory Structure

```bash
# Create required directories
sudo mkdir -p /opt/filatag/binaries
sudo mkdir -p /etc/filatag
sudo mkdir -p /var/log/filatag

# Set permissions
sudo chown -R $USER:$USER /opt/filatag
sudo chmod 755 /var/log/filatag
```

### 5. Configure Application

```bash
# Copy configuration files
sudo cp /opt/filatag/filatag.service /etc/systemd/system/
sudo cp config/config.json /etc/filatag/
sudo cp config/mapping.json /etc/filatag/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable filatag
sudo systemctl start filatag

# Check service status
sudo systemctl status filatag
```

## Usage

### Web Interface

1. **Access**: Open `http://[raspberry-pi-ip]:3000` in your browser
2. **Select Filament**: Choose SKU from searchable dropdown
3. **Enter Spool ID**: Provide unique spool identifier
4. **Program Tags**: Follow on-screen prompts for Tag #1 and Tag #2
5. **View Logs**: Check programming history and results

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
