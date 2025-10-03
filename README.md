# Filatag RFID Programmer

A complete RFID programming solution for filament spools using Proxmark3 hardware. This application programs two 13.56 MHz MIFARE Classic S50 (1K) RFID tags per spool with binary data specific to each filament SKU.

## Features

- **Web Interface**: Responsive web UI accessible from any device on the LAN
- **Real-time Programming**: Live progress tracking with Proxmark3 output streaming  
- **Dual Tag Programming**: Program two RFID tags per spool with verification
- **CLI Tool**: Headless command-line interface for automated workflows
- **Mock Mode**: Complete testing and development without hardware
- **Structured Logging**: JSON logs with full audit trail
- **Device Auto-detection**: Automatic Proxmark3 USB device detection
- **Flexible Configuration**: Configurable retry logic, verification modes, and keys

## Hardware Requirements

- **Linux SBC**: Raspberry Pi 4 or similar (2GB+ RAM recommended)
- **Proxmark3**: Iceman fork v4.18994+ (original version NOT supported)
- **RFID Tags**: MIFARE Classic S50 (1K) tags

## Installation

### 1. Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y python3 python3-pip python3-venv nodejs npm git

# Install Proxmark3 (Iceman fork)
# Follow official installation guide at: https://github.com/RfidResearchGroup/proxmark3
```

### 2. Setup Proxmark3 Permissions

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
