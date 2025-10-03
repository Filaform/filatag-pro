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

async def program_spool(sku: str, spool_id: str, operator: Optional[str] = None, mock: bool = False):
    """Program both RFID tags for a spool"""
    config['mock_mode'] = mock
    
    if mock:
        print_warning("Running in MOCK MODE - no actual hardware will be programmed")
    
    print_info(f"Starting programming session for SKU: {sku}, Spool: {spool_id}")
    
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
    print_info(f"Operator: {operator or 'Not specified'}")
    
    # Generate session ID
    session_id = f"cli_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Log session start
    log_action("cli_session_started", session_id, {
        "sku": sku,
        "spool_id": spool_id,
        "operator": operator,
        "mock_mode": mock
    })
    
    # Check device if not in mock mode
    if not mock:
        device_path = await detect_proxmark_device()
        if not device_path:
            print_error("No Proxmark3 device found")
            return 1
        print_success(f"Using device: {device_path}")
    
    # Program both tags
    for tag_num in [1, 2]:
        print(f"\n🏷️  Programming Tag #{tag_num}")
        print("=" * 40)
        
        if not mock:
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
        result = await program_tag(binary_path, filament.keys)
        
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
            verified = await verify_tag(binary_path, result["hash"], filament.keys)
            
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
    print("\n🎉 Programming Complete!")
    print("=" * 40)
    print_success(f"Both tags programmed successfully for spool {spool_id}")
    
    log_action("session_completed", session_id, {
        "sku": sku,
        "spool_id": spool_id,
        "status": "success"
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