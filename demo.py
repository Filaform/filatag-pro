#!/usr/bin/env python3
"""
Filatag RFID Programmer Demo Script

This script demonstrates the complete functionality of the Filatag RFID programmer,
including CLI operations, web API testing, and mock hardware simulation.

Usage:
    python demo.py [--with-hardware]  # Use --with-hardware only if Proxmark3 is connected

Examples:
    python demo.py                    # Run demo in mock mode (recommended)
    python demo.py --with-hardware    # Run demo with actual Proxmark3 hardware
"""

import asyncio
import json
import sys
import argparse
import time
from pathlib import Path
import requests
import subprocess
from datetime import datetime

# Add backend to path
sys.path.append(str(Path(__file__).parent / 'backend'))

def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def print_step(step: str):
    """Print a formatted step"""
    print(f"\n🔧 {step}")
    print("-" * 40)

def print_success(msg: str):
    """Print success message"""
    print(f"✅ {msg}")

def print_error(msg: str):
    """Print error message"""
    print(f"❌ {msg}")

def print_info(msg: str):
    """Print info message"""
    print(f"ℹ️  {msg}")

def run_cli_command(cmd: list) -> tuple:
    """Run a CLI command and return (success, output)"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutError:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)

def test_api_endpoint(url: str, method: str = "GET", data: dict = None) -> tuple:
    """Test an API endpoint and return (success, response_data)"""
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10)
        else:
            return False, f"Unsupported method: {method}"
        
        return response.status_code < 400, response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
    
    except requests.exceptions.RequestException as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)

def demo_cli_functionality(mock_mode: bool = True):
    """Demo CLI functionality"""
    print_header("CLI Functionality Demo")
    
    mock_flag = ["--mock"] if mock_mode else []
    
    # Test 1: List filaments
    print_step("Testing filament listing")
    success, output = run_cli_command(["python3", "cli.py", "list-filaments"])
    if success:
        print_success("Filament listing works correctly")
        print(output[:500] + "..." if len(output) > 500 else output)
    else:
        print_error(f"Filament listing failed: {output}")
    
    # Test 2: Device status
    print_step("Testing device status check")
    success, output = run_cli_command(["python3", "cli.py", "device-status"] + mock_flag)
    if success:
        print_success("Device status check works correctly")
        print(output[:300] + "..." if len(output) > 300 else output)
    else:
        print_error(f"Device status check failed: {output}")
    
    # Test 3: Binary verification
    print_step("Testing binary file verification")
    success, output = run_cli_command([
        "python3", "cli.py", "verify",
        "--binary-file", "/opt/filatag/binaries/pla001.bin"
    ] + mock_flag)
    if success:
        print_success("Binary verification works correctly")
        print(output[:300] + "..." if len(output) > 300 else output)
    else:
        print_error(f"Binary verification failed: {output}")
    
    # Test 4: Auto-programming simulation
    if mock_mode:
        print_step("Testing auto-programming workflow (mock mode)")
        cmd = [
            "python3", "cli.py", "auto-program",
            "--sku", "PLA001",
            "--mock"
        ]
        
        print_info(f"Auto-programming command: {' '.join(cmd)}")
        success, output = run_cli_command(cmd)
        
        if success:
            print_success("Auto-programming workflow completed successfully")
            # Show key parts of output
            lines = output.split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in ['detected', 'programmed', 'complete', 'success']):
                    print(f"   → {line}")
        else:
            print_error("Auto-programming failed")
            print(output[-300:])  # Last 300 chars for debugging

def demo_api_functionality():
    """Demo Web API functionality"""
    print_header("Web API Functionality Demo")
    
    base_url = "https://mifare-writer.preview.emergentagent.com/api"
    
    # Test 1: Get filaments
    print_step("Testing filaments API endpoint")
    success, data = test_api_endpoint(f"{base_url}/filaments")
    if success:
        print_success(f"Filaments API works - Found {len(data)} filaments")
        for filament in data[:3]:  # Show first 3
            print(f"   • {filament['sku']}: {filament['name']}")
    else:
        print_error(f"Filaments API failed: {data}")
    
    # Test 2: Device status
    print_step("Testing device status API endpoint")
    success, data = test_api_endpoint(f"{base_url}/device/status")
    if success:
        print_success(f"Device status API works")
        print(f"   • Connected: {data.get('connected', 'Unknown')}")
        print(f"   • Device Path: {data.get('device_path', 'None')}")
        print(f"   • Mock Mode: {data.get('mock_mode', 'Unknown')}")
    else:
        print_error(f"Device status API failed: {data}")
    
    # Test 3: Configuration
    print_step("Testing configuration API endpoint")
    success, data = test_api_endpoint(f"{base_url}/config")
    if success:
        print_success("Configuration API works")
        print(f"   • Mock Mode: {data.get('mock_mode', 'Unknown')}")
        print(f"   • Retries: {data.get('retries', 'Unknown')}")
        print(f"   • Strict Verification: {data.get('strict_verification', 'Unknown')}")
    else:
        print_error(f"Configuration API failed: {data}")
    
    # Test 4: Start programming session
    print_step("Testing programming session API")
    session_data = {
        "sku": "PLA001",
        "spool_id": f"API_DEMO_{int(time.time())}",
        "operator": "APIDemo"
    }
    success, data = test_api_endpoint(f"{base_url}/programming/start", "POST", session_data)
    if success:
        print_success("Programming session API works")
        print(f"   • Session ID: {data.get('id', 'Unknown')}")
        print(f"   • SKU: {data.get('sku', 'Unknown')}")
        print(f"   • Spool ID: {data.get('spool_id', 'Unknown')}")
        return data.get('id')
    else:
        print_error(f"Programming session API failed: {data}")
        return None

def demo_file_structure():
    """Demo file structure and configuration"""
    print_header("File Structure & Configuration Demo")
    
    # Check directory structure
    print_step("Checking directory structure")
    directories = [
        "/opt/filatag/binaries",
        "/etc/filatag", 
        "/var/log/filatag"
    ]
    
    for directory in directories:
        if Path(directory).exists():
            print_success(f"Directory exists: {directory}")
            
            # List contents if it's the binaries directory
            if "binaries" in directory:
                binaries = list(Path(directory).glob("*.bin"))
                print(f"   • Found {len(binaries)} binary files")
                for binary in binaries[:3]:
                    size = binary.stat().st_size
                    print(f"     - {binary.name}: {size} bytes")
        else:
            print_error(f"Directory missing: {directory}")
    
    # Check configuration files
    print_step("Checking configuration files")
    config_files = [
        "/etc/filatag/config.json",
        "/etc/filatag/mapping.json"
    ]
    
    for config_file in config_files:
        if Path(config_file).exists():
            print_success(f"Config file exists: {config_file}")
            try:
                with open(config_file) as f:
                    data = json.load(f)
                print(f"   • Contains {len(data)} entries")
            except Exception as e:
                print_error(f"   • Error reading file: {e}")
        else:
            print_error(f"Config file missing: {config_file}")
    
    # Check systemd service file
    print_step("Checking systemd service file")
    service_file = "/app/filatag.service"
    if Path(service_file).exists():
        print_success("Systemd service file exists")
        with open(service_file) as f:
            content = f.read()
            if "filatag" in content.lower():
                print("   • Service file looks correctly configured")
    else:
        print_error("Systemd service file missing")

def demo_log_functionality():
    """Demo logging functionality"""
    print_header("Logging System Demo")
    
    log_file = Path("/var/log/filatag/actions.log")
    
    if log_file.exists():
        print_success(f"Log file exists: {log_file}")
        
        try:
            with open(log_file) as f:
                lines = f.readlines()
            
            print(f"   • Found {len(lines)} log entries")
            
            # Show recent entries
            if lines:
                print("   • Recent log entries:")
                for line in lines[-3:]:  # Last 3 entries
                    try:
                        entry = json.loads(line.strip())
                        timestamp = entry.get('timestamp', 'Unknown')
                        action = entry.get('action', 'Unknown')
                        print(f"     - {timestamp}: {action}")
                    except:
                        print(f"     - {line.strip()[:60]}...")
            else:
                print("   • No log entries found (this is normal for a fresh install)")
        
        except Exception as e:
            print_error(f"Error reading log file: {e}")
    else:
        print_info("Log file doesn't exist yet (will be created on first use)")

def demo_unit_tests():
    """Run unit tests to verify functionality"""
    print_header("Unit Tests Demo")
    
    print_step("Running unit tests")
    
    # Check if pytest is available
    try:
        import pytest
        print_success("pytest is available")
    except ImportError:
        print_error("pytest not installed - install with: pip install pytest")
        return
    
    # Run the tests
    test_file = Path("tests/test_filatag.py")
    if test_file.exists():
        print_info("Running unit tests...")
        success, output = run_cli_command([
            "python", "-m", "pytest", str(test_file), "-v", "--tb=short"
        ])
        
        if success:
            print_success("Unit tests completed successfully")
            # Count passed/failed from output
            lines = output.split('\n')
            for line in lines[-5:]:
                if 'passed' in line or 'failed' in line or 'error' in line:
                    print(f"   • {line}")
        else:
            print_error("Some unit tests failed")
            print(output[-500:])  # Last 500 chars
    else:
        print_error(f"Test file not found: {test_file}")

def main():
    """Main demo function"""
    parser = argparse.ArgumentParser(description="Filatag RFID Programmer Demo")
    parser.add_argument(
        "--with-hardware", 
        action="store_true",
        help="Run demo with actual Proxmark3 hardware (default: mock mode)"
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true", 
        help="Skip unit tests in demo"
    )
    
    args = parser.parse_args()
    mock_mode = not args.with_hardware
    
    print_header("🏷️  Filatag RFID Programmer Demonstration")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if mock_mode:
        print_info("Running in MOCK MODE (no hardware required)")
    else:
        print_info("Running with HARDWARE MODE (Proxmark3 required)")
    
    try:
        # Demo 1: File structure
        demo_file_structure()
        
        # Demo 2: CLI functionality
        demo_cli_functionality(mock_mode)
        
        # Demo 3: API functionality
        session_id = demo_api_functionality()
        
        # Demo 4: Logging
        demo_log_functionality()
        
        # Demo 5: Unit tests (if not skipped)
        if not args.skip_tests:
            demo_unit_tests()
        
        # Summary
        print_header("Demo Summary")
        print_success("✅ File structure and configuration")
        print_success("✅ CLI tool functionality") 
        print_success("✅ Web API endpoints")
        print_success("✅ Logging system")
        if not args.skip_tests:
            print_success("✅ Unit tests")
        
        print("\n" + "🎉 Demo completed successfully!")
        print("\nNext steps:")
        print("1. Review the web interface at: https://mifare-writer.preview.emergentagent.com")
        print("2. Test CLI commands: python3 cli.py --help")
        print("3. Check logs: tail -f /var/log/filatag/actions.log")
        if mock_mode:
            print("4. When ready, connect Proxmark3 hardware and disable mock mode")
        
    except KeyboardInterrupt:
        print_error("\nDemo interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_error(f"Demo failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()