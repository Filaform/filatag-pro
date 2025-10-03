#!/usr/bin/env python3
"""
Filatag CLI Tool - Headless RFID programming for filament spools

Usage:
    python cli.py program --sku SKU123 --spool SPOOL0001 [--operator michael] [--mock]
    python cli.py list-filaments
    python cli.py device-status [--mock]
    python cli.py verify --binary-file path/to/file.bin [--mock]

Examples:
    python cli.py program --sku PLA001 --spool SPOOL001 --operator john
    python cli.py program --sku ABS002 --spool SPOOL002 --mock
    python cli.py list-filaments
    python cli.py device-status
"""

import sys
import json
import asyncio
import argparse
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

# Import from backend server
sys.path.append(str(Path(__file__).parent / 'backend'))
from server import (
    load_filament_mapping, 
    detect_proxmark_device,
    run_proxmark_command,
    program_tag,
    verify_tag,
    verify_card_type,
    log_action,
    BINARIES_PATH,
    config
)

def setup_logging(verbose: bool = False):
    """Setup CLI logging"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def print_success(message: str):
    """Print success message with color"""
    print(f"✅ {message}")

def print_error(message: str):
    """Print error message with color"""
    print(f"❌ {message}")

def print_warning(message: str):
    """Print warning message with color"""
    print(f"⚠️  {message}")

def print_info(message: str):
    """Print info message"""
    print(f"ℹ️  {message}")

async def list_filaments():
    """List available filaments"""
    print_info("Loading available filaments...")
    
    mapping = load_filament_mapping()
    
    if not mapping:
        print_error("No filaments found in mapping file")
        return 1
    
    print(f"\n📦 Available Filaments ({len(mapping)} total):")
    print("=" * 70)
    
    for sku, filament in mapping.items():
        binary_path = BINARIES_PATH / filament.binary_file
        binary_exists = binary_path.exists()
        
        print(f"SKU:         {filament.sku}")
        print(f"Name:        {filament.name}")
        print(f"Description: {filament.description}")
        print(f"Binary File: {filament.binary_file} {'✅' if binary_exists else '❌ MISSING'}")
        if filament.keys:
            print(f"Custom Keys: {len(filament.keys)} keys configured")
        print("-" * 70)
    
    return 0

async def device_status(mock: bool = False):
    """Check device status"""
    config['mock_mode'] = mock
    
    if mock:
        print_info("Running in mock mode")
    
    print_info("Checking Proxmark3 device status...")
    
    # Try to detect device
    device_path = await detect_proxmark_device()
    
    if device_path:
        print_success(f"Proxmark3 detected at {device_path}")
        
        # Get detailed status
        result = await run_proxmark_command("hw status")
        
        if result["success"]:
            print_success("Device communication successful")
            print("\n📡 Device Information:")
            print("=" * 50)
            print(result["output"])
        else:
            print_error("Failed to communicate with device")
            print(f"Error: {result['error']}")
            return 1
    else:
        print_error("No Proxmark3 device found")
        print_info("Check connections and ensure device is powered on")
        return 1
    
    return 0

async def program_spool(sku: str, spool_id: str = None, operator: Optional[str] = None, mock: bool = False, auto_detect: bool = True):
    """Program both RFID tags for a spool with optional auto-detection"""
    config['mock_mode'] = mock
    
    if mock:
        print_warning("Running in MOCK MODE - no actual hardware will be programmed")
    
    # Generate spool ID if not provided (for auto mode)
    if not spool_id:
        spool_id = f"AUTO_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print_info(f"Starting programming session for SKU: {sku}")
    print_info(f"Auto-detection mode: {'Enabled' if auto_detect else 'Disabled'}")
    
    # Load filament mapping
    mapping = load_filament_mapping()
    
    if sku not in mapping:
        print_error(f"SKU '{sku}' not found in filament mapping")
        return 1
    
    filament = mapping[sku]
    binary_path = BINARIES_PATH / filament.binary_file
    
    if not binary_path.exists():
        print_error(f"Binary file not found: {binary_path}")
        return 1
    
    print_info(f"Filament: {filament.name}")
    print_info(f"Binary file: {filament.binary_file}")
    print_info(f"Spool ID: {spool_id}")
    
    # Generate session ID
    session_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Log session start
    log_action("cli_session_started", session_id, {
        "sku": sku,
        "spool_id": spool_id,
        "operator": operator,
        "mock_mode": mock,
        "auto_detect": auto_detect
    })
    
    # Check device if not in mock mode
    if not mock:
        device_path = await detect_proxmark_device()
        if not device_path:
            print_error("No Proxmark3 device found")
            return 1
        print_success(f"Using device: {device_path}")
    
    if auto_detect:
        return await program_spool_auto_detect(sku, session_id, binary_path, filament.keys)
    else:
        return await program_spool_manual(sku, spool_id, session_id, binary_path, filament.keys, operator)

async def program_spool_auto_detect(sku: str, session_id: str, binary_path: Path, keys: Optional[List[str]]):
    """Program spool using auto-detection mode"""
    print("\n🤖 Auto-Detection Mode")
    print("=" * 50)
    print_info("Tags will be automatically detected and programmed when placed on antenna")
    
    # Import auto-detector
    from server import get_auto_detector
    
    detector = get_auto_detector()
    
    # Set up event handlers
    events = {
        'tag_detected': False,
        'programming_started': False,
        'programming_completed': False,
        'ready_for_next_tag': False,
        'session_complete': False,
        'error': False
    }
    
    def on_tag_detected(data):
        events['tag_detected'] = True
        print_success(f"Tag #{data['tag_number']} detected automatically!")
    
    def on_programming_started(data):
        events['programming_started'] = True
        print_info(f"Auto-programming Tag #{data['tag_number']}...")
    
    def on_programming_completed(data):
        events['programming_completed'] = True
        print_success(f"Tag #{data['tag_number']} programmed and verified!")
    
    def on_ready_for_next_tag(data):
        events['ready_for_next_tag'] = True
        print("\n" + "🏷️" * 20)
        print_info(f"Ready for Tag #{data['tag_number']}")
        print_info("Remove previous tag and place next tag on antenna...")
        print("🏷️" * 20)
    
    def on_session_complete(data):
        events['session_complete'] = True
        print("\n🎉 AUTO-PROGRAMMING COMPLETE!")
        print("=" * 50)
        print_success("Both tags programmed successfully using auto-detection!")
    
    def on_error(data):
        events['error'] = True
        print_error(f"Auto-programming error: {data.get('error', 'Unknown error')}")
    
    # Register callbacks
    detector.set_callback('tag_detected', on_tag_detected)
    detector.set_callback('programming_started', on_programming_started)  
    detector.set_callback('programming_completed', on_programming_completed)
    detector.set_callback('ready_for_next_tag', on_ready_for_next_tag)
    detector.set_callback('session_complete', on_session_complete)
    detector.set_callback('programming_error', on_error)
    detector.set_callback('detection_error', on_error)
    
    # Start auto-detection
    success = await detector.start_auto_detection(sku, session_id)
    if not success:
        print_error("Failed to start auto-detection")
        return 1
    
    print_info("Auto-detection started! Place Tag #1 on Proxmark3 antenna...")
    
    # Wait for completion or timeout
    timeout = 300  # 5 minutes
    start_time = time.time()
    
    while detector.scanning and (time.time() - start_time) < timeout:
        status = detector.get_status()
        
        # Print status updates
        if status['state'] == 'scanning':
            print(f"⏳ Waiting for Tag #{status['current_tag_number']}...", end='\r')
        
        await asyncio.sleep(1)
        
        # Check for completion or error
        if events['session_complete']:
            break
        if events['error']:
            return 1
    
    # Stop detection
    detector.stop_auto_detection()
    
    if events['session_complete']:
        log_action("cli_auto_session_completed", session_id, {
            "sku": sku,
            "status": "success",
            "mode": "auto_detection"
        })
        return 0
    else:
        print_error("Auto-programming timed out or was interrupted")
        return 1

async def program_spool_manual(sku: str, spool_id: str, session_id: str, binary_path: Path, keys: Optional[List[str]], operator: Optional[str]):
    """Program spool using manual mode (legacy)"""
    print("\n🔧 Manual Programming Mode")
    print("=" * 40)
    
    # Program both tags manually
    for tag_num in [1, 2]:
        print(f"\n🏷️  Programming Tag #{tag_num}")
        print("=" * 40)
        
        if not config.get('mock_mode', False):
            input(f"Place Tag #{tag_num} on the Proxmark3 antenna and press Enter...")
        else:
            print_info(f"Mock: Simulating Tag #{tag_num} placement")
        
        # Verify card type first
        print_info("Verifying card type...")
        if not await verify_card_type():
            print_error("Card is not MIFARE Classic 1K or not detected")
            log_action("tag_failed", session_id, {
                "tag_num": tag_num,
                "error": "Invalid card type or not detected"
            })
            return 1
        
        print_success("MIFARE Classic 1K detected")
        
        # Program the tag
        print_info("Writing binary data to tag...")
        result = await program_tag(binary_path, keys)
        
        if not result["success"]:
            print_error(f"Failed to program Tag #{tag_num}: {result['error']}")
            log_action("tag_failed", session_id, {
                "tag_num": tag_num,
                "error": result["error"]
            })
            return 1
        
        print_success(f"Tag #{tag_num} programmed successfully")
        
        # Verify the tag
        if config.get("strict_verification", True):
            print_info("Verifying written data...")
            verified = await verify_tag(binary_path, result["hash"], keys)
            
            if verified:
                print_success(f"Tag #{tag_num} verification PASSED")
                log_action("tag_programmed", session_id, {
                    "tag_num": tag_num,
                    "status": "pass",
                    "hash": result["hash"]
                })
            else:
                print_error(f"Tag #{tag_num} verification FAILED")
                log_action("tag_failed", session_id, {
                    "tag_num": tag_num,
                    "error": "Verification failed",
                    "hash": result["hash"]
                })
                return 1
        else:
            print_info("Verification skipped (tolerant mode)")
            log_action("tag_programmed", session_id, {
                "tag_num": tag_num,
                "status": "pass_no_verify",
                "hash": result["hash"]
            })
    
    # Success
    print("\n🎉 Manual Programming Complete!")
    print("=" * 40)
    print_success(f"Both tags programmed successfully for spool {spool_id}")
    
    log_action("cli_session_completed", session_id, {
        "sku": sku,
        "spool_id": spool_id,
        "status": "success",
        "mode": "manual"
    })
    
    return 0

async def verify_binary(binary_file: Path, mock: bool = False):
    """Verify a binary file can be read and programmed"""
    config['mock_mode'] = mock
    
    print_info(f"Verifying binary file: {binary_file}")
    
    if not binary_file.exists():
        print_error(f"Binary file not found: {binary_file}")
        return 1
    
    # Check file size
    file_size = binary_file.stat().st_size
    print_info(f"File size: {file_size} bytes")
    
    if file_size != 1024:
        print_error(f"Invalid file size: {file_size} (expected 1024 bytes for MIFARE Classic 1K)")
        return 1
    
    print_success("File size is correct for MIFARE Classic 1K")
    
    # Read and validate content
    try:
        with open(binary_file, "rb") as f:
            data = f.read()
        
        print_success("Binary file read successfully")
        
        # Calculate hash
        import hashlib
        file_hash = hashlib.sha256(data).hexdigest()
        print_info(f"SHA256 hash: {file_hash}")
        
        # Show some sample data
        print_info("First 16 bytes (hex): " + data[:16].hex().upper())
        print_info("Last 16 bytes (hex):  " + data[-16:].hex().upper())
        
    except Exception as e:
        print_error(f"Failed to read binary file: {e}")
        return 1
    
    return 0

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Filatag CLI - RFID Programming Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Program command
    program_parser = subparsers.add_parser('program', help='Program RFID tags for a spool')
    program_parser.add_argument('--sku', required=True, help='Filament SKU')
    program_parser.add_argument('--spool', required=True, help='Spool ID')
    program_parser.add_argument('--operator', help='Operator name (optional)')
    program_parser.add_argument('--mock', action='store_true', help='Use mock mode for testing')
    
    # List filaments command
    subparsers.add_parser('list-filaments', help='List available filaments')
    
    # Device status command
    status_parser = subparsers.add_parser('device-status', help='Check Proxmark3 device status')
    status_parser.add_argument('--mock', action='store_true', help='Use mock mode')
    
    # Verify binary command
    verify_parser = subparsers.add_parser('verify', help='Verify a binary file')
    verify_parser.add_argument('--binary-file', required=True, type=Path, help='Path to binary file')
    verify_parser.add_argument('--mock', action='store_true', help='Use mock mode')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Run appropriate command
    try:
        if args.command == 'program':
            result = asyncio.run(program_spool(
                args.sku, args.spool, args.operator, args.mock
            ))
        elif args.command == 'list-filaments':
            result = asyncio.run(list_filaments())
        elif args.command == 'device-status':
            result = asyncio.run(device_status(args.mock))
        elif args.command == 'verify':
            result = asyncio.run(verify_binary(args.binary_file, args.mock))
        else:
            parser.print_help()
            result = 1
        
        return result
        
    except KeyboardInterrupt:
        print_error("Operation cancelled by user")
        return 130
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())