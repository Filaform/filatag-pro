#!/usr/bin/env python3
"""
Camera-based barcode scanner for Filatag RFID Programmer

This module handles USB webcam integration and UPC/EAN barcode scanning
to automatically detect filament types from spool barcodes.
"""

import cv2
import numpy as np
from pyzbar import pyzbar
import logging
import asyncio
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
import threading
import queue

logger = logging.getLogger(__name__)

class BarcodeScanner:
    """USB webcam barcode scanner for filament identification"""
    
    def __init__(self, camera_index: int = 0, auto_scan: bool = True):
        self.camera_index = camera_index
        self.auto_scan = auto_scan
        self.cap = None
        self.scanning = False
        self.last_scan_time = 0
        self.scan_cooldown = 2.0  # Seconds between scans
        self.scan_queue = queue.Queue()
        self.scan_thread = None
        
    def initialize_camera(self) -> bool:
        """Initialize USB webcam"""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                logger.error(f"Failed to open camera at index {self.camera_index}")
                return False
                
            # Set camera properties for better barcode scanning
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
            
            # Test camera by taking a frame
            ret, frame = self.cap.read()
            if not ret:
                logger.error("Camera opened but cannot read frames")
                return False
                
            logger.info(f"Camera initialized successfully at index {self.camera_index}")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing camera: {e}")
            return False
    
    def detect_barcodes(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Detect UPC/EAN barcodes in frame"""
        try:
            # Convert to grayscale for better barcode detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Apply some image processing to improve barcode detection
            # Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Detect barcodes
            barcodes = pyzbar.decode(blurred)
            
            results = []
            for barcode in barcodes:
                # Extract barcode data and type
                barcode_data = barcode.data.decode('utf-8')
                barcode_type = barcode.type
                
                # Get bounding box coordinates
                (x, y, w, h) = barcode.rect
                
                # Only process UPC/EAN barcodes
                if barcode_type in ['EAN13', 'EAN8', 'UPCA', 'UPCE']:
                    results.append({
                        'data': barcode_data,
                        'type': barcode_type,
                        'bbox': (x, y, w, h),
                        'timestamp': time.time()
                    })
                    
                    logger.info(f"Detected {barcode_type} barcode: {barcode_data}")
            
            return results
            
        except Exception as e:
            logger.error(f"Error detecting barcodes: {e}")
            return []
    
    def scan_single_frame(self) -> Optional[Dict[str, Any]]:
        """Scan single frame for barcodes"""
        if not self.cap or not self.cap.isOpened():
            return None
            
        try:
            ret, frame = self.cap.read()
            if not ret:
                return None
                
            barcodes = self.detect_barcodes(frame)
            return barcodes[0] if barcodes else None
            
        except Exception as e:
            logger.error(f"Error scanning frame: {e}")
            return None
    
    def start_continuous_scan(self):
        """Start continuous barcode scanning in background thread"""
        if self.scanning:
            return
            
        self.scanning = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()
        logger.info("Started continuous barcode scanning")
    
    def stop_continuous_scan(self):
        """Stop continuous scanning"""
        self.scanning = False
        if self.scan_thread:
            self.scan_thread.join(timeout=2.0)
        logger.info("Stopped continuous barcode scanning")
    
    def _scan_loop(self):
        """Continuous scanning loop (runs in background thread)"""
        while self.scanning and self.cap and self.cap.isOpened():
            try:
                current_time = time.time()
                
                # Respect cooldown period
                if current_time - self.last_scan_time < self.scan_cooldown:
                    time.sleep(0.1)
                    continue
                
                ret, frame = self.cap.read()
                if not ret:
                    time.sleep(0.1)
                    continue
                
                barcodes = self.detect_barcodes(frame)
                if barcodes:
                    # Put the first detected barcode in queue
                    try:
                        self.scan_queue.put_nowait(barcodes[0])
                        self.last_scan_time = current_time
                    except queue.Full:
                        pass  # Queue full, skip this scan
                
                time.sleep(0.1)  # Small delay to prevent excessive CPU usage
                
            except Exception as e:
                logger.error(f"Error in scan loop: {e}")
                time.sleep(1.0)
    
    def get_latest_scan(self) -> Optional[Dict[str, Any]]:
        """Get latest barcode scan from queue (non-blocking)"""
        try:
            return self.scan_queue.get_nowait()
        except queue.Empty:
            return None
    
    def get_camera_frame(self) -> Optional[np.ndarray]:
        """Get current camera frame for preview"""
        if not self.cap or not self.cap.isOpened():
            return None
            
        try:
            ret, frame = self.cap.read()
            return frame if ret else None
        except Exception as e:
            logger.error(f"Error getting camera frame: {e}")
            return None
    
    def close(self):
        """Clean up camera resources"""
        self.stop_continuous_scan()
        
        if self.cap:
            self.cap.release()
            self.cap = None
        
        logger.info("Camera scanner closed")

class FilamentBarcodeMapper:
    """Maps UPC/EAN barcodes to filament SKUs"""
    
    def __init__(self, mapping_file: Path = None):
        self.mapping_file = mapping_file or Path("/etc/filatag/barcode_mapping.json")
        self.barcode_to_sku = {}
        self.load_mapping()
    
    def load_mapping(self):
        """Load barcode to SKU mapping from file"""
        try:
            if self.mapping_file.exists():
                import json
                with open(self.mapping_file) as f:
                    self.barcode_to_sku = json.load(f)
                logger.info(f"Loaded {len(self.barcode_to_sku)} barcode mappings")
            else:
                # Create default mapping
                self.create_default_mapping()
        except Exception as e:
            logger.error(f"Error loading barcode mapping: {e}")
            self.create_default_mapping()
    
    def create_default_mapping(self):
        """Create default barcode to SKU mapping"""
        # Sample UPC/EAN codes for demonstration
        default_mapping = {
            "123456789012": "PLA001",    # UPC-A format
            "123456789013": "ABS002",
            "123456789014": "PETG003", 
            "123456789015": "TPU004",
            "123456789016": "WOOD005",
            "1234567890128": "PLA001",   # EAN-13 format  
            "1234567890135": "ABS002",
            "1234567890142": "PETG003",
            "1234567890159": "TPU004",
            "1234567890166": "WOOD005"
        }
        
        self.barcode_to_sku = default_mapping
        self.save_mapping()
        logger.info("Created default barcode mapping")
    
    def save_mapping(self):
        """Save current mapping to file"""
        try:
            import json
            import os
            os.makedirs(self.mapping_file.parent, exist_ok=True)
            
            with open(self.mapping_file, 'w') as f:
                json.dump(self.barcode_to_sku, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving barcode mapping: {e}")
    
    def get_sku_from_barcode(self, barcode: str) -> Optional[str]:
        """Get SKU for given barcode"""
        return self.barcode_to_sku.get(barcode)
    
    def add_barcode_mapping(self, barcode: str, sku: str):
        """Add new barcode to SKU mapping"""
        self.barcode_to_sku[barcode] = sku
        self.save_mapping()
        logger.info(f"Added barcode mapping: {barcode} -> {sku}")
    
    def get_all_mappings(self) -> Dict[str, str]:
        """Get all barcode to SKU mappings"""
        return self.barcode_to_sku.copy()

# Global scanner instance
scanner = None
barcode_mapper = None

def get_scanner() -> Optional[BarcodeScanner]:
    """Get global scanner instance"""
    return scanner

def get_barcode_mapper() -> FilamentBarcodeMapper:
    """Get global barcode mapper instance"""
    global barcode_mapper
    if not barcode_mapper:
        barcode_mapper = FilamentBarcodeMapper()
    return barcode_mapper

def initialize_camera_scanner(camera_index: int = 0) -> bool:
    """Initialize global camera scanner"""
    global scanner
    
    try:
        scanner = BarcodeScanner(camera_index)
        success = scanner.initialize_camera()
        
        if success and scanner.auto_scan:
            scanner.start_continuous_scan()
            
        return success
        
    except Exception as e:
        logger.error(f"Failed to initialize camera scanner: {e}")
        return False

def cleanup_camera_scanner():
    """Clean up global scanner"""
    global scanner
    if scanner:
        scanner.close()
        scanner = None

if __name__ == "__main__":
    # Test script
    logging.basicConfig(level=logging.INFO)
    
    print("Testing camera barcode scanner...")
    
    # Initialize scanner
    if initialize_camera_scanner():
        print("✅ Camera initialized successfully")
        
        # Test barcode mapping
        mapper = get_barcode_mapper()
        print(f"✅ Loaded {len(mapper.get_all_mappings())} barcode mappings")
        
        # Scan for 10 seconds
        print("📷 Scanning for barcodes for 10 seconds...")
        start_time = time.time()
        
        while time.time() - start_time < 10:
            scan_result = scanner.get_latest_scan()
            if scan_result:
                barcode = scan_result['data']
                sku = mapper.get_sku_from_barcode(barcode)
                print(f"🏷️  Detected: {barcode} -> SKU: {sku or 'Unknown'}")
            
            time.sleep(0.5)
        
        cleanup_camera_scanner()
        print("✅ Test completed")
        
    else:
        print("❌ Failed to initialize camera")