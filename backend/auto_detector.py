#!/usr/bin/env python3
"""
Auto-detection module for RFID tags and automatic programming workflow

This module handles continuous RFID tag detection and triggers automatic
programming when tags are placed on the Proxmark3 antenna.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Callable
from enum import Enum
import json
from datetime import datetime, timezone

# Import from main server
from server import (
    run_proxmark_command, 
    verify_card_type,
    program_tag,
    verify_tag,
    log_action,
    config,
    BINARIES_PATH
)

logger = logging.getLogger(__name__)

class AutoDetectionState(str, Enum):
    IDLE = "idle"
    SCANNING = "scanning" 
    TAG_DETECTED = "tag_detected"
    PROGRAMMING = "programming"
    VERIFYING = "verifying"
    COMPLETE = "complete"
    ERROR = "error"

class TagAutoDetector:
    """Automatic RFID tag detection and programming"""
    
    def __init__(self):
        self.state = AutoDetectionState.IDLE
        self.scanning = False
        self.current_session = None
        self.detection_interval = 1.0  # Seconds between detection attempts
        self.last_detection_time = 0
        self.detection_cooldown = 2.0  # Seconds cooldown after programming
        self.callbacks = {}
        
        # Current programming context
        self.selected_sku = None
        self.selected_binary = None
        self.current_tag_number = 1
        self.session_id = None
        
    def set_callback(self, event: str, callback: Callable):
        """Set callback function for events"""
        self.callbacks[event] = callback
        
    def _emit_event(self, event: str, data: Dict[str, Any] = None):
        """Emit event to callback if registered"""
        if event in self.callbacks:
            try:
                self.callbacks[event](data or {})
            except Exception as e:
                logger.error(f"Error in callback for {event}: {e}")
    
    async def detect_tag_presence(self) -> bool:
        """Check if RFID tag is present on antenna"""
        try:
            # Use 'hf 14a info' to detect tag presence
            result = await run_proxmark_command("hf 14a info", timeout=3)
            
            if result["success"]:
                output = result["output"].lower()
                # Check for MIFARE Classic indicators
                return ("mifare" in output and 
                        ("classic" in output or "1k" in output) and
                        "uid:" in output)
            
            return False
            
        except Exception as e:
            logger.error(f"Error detecting tag presence: {e}")
            return False
    
    async def start_auto_detection(self, sku: str, session_id: str):
        """Start automatic tag detection for given SKU"""
        if self.scanning:
            logger.warning("Auto-detection already running")
            return False
        
        # Set up programming context
        self.selected_sku = sku
        self.session_id = session_id
        self.selected_binary = BINARIES_PATH / f"{sku.lower()}.bin"
        self.current_tag_number = 1
        
        if not self.selected_binary.exists():
            logger.error(f"Binary file not found: {self.selected_binary}")
            return False
        
        self.scanning = True
        self.state = AutoDetectionState.SCANNING
        
        logger.info(f"Started auto-detection for SKU: {sku}")
        self._emit_event("detection_started", {
            "sku": sku,
            "session_id": session_id,
            "tag_number": self.current_tag_number
        })
        
        # Start detection loop
        asyncio.create_task(self._detection_loop())
        return True
    
    def stop_auto_detection(self):
        """Stop automatic detection"""
        self.scanning = False
        self.state = AutoDetectionState.IDLE
        self.current_session = None
        
        logger.info("Stopped auto-detection")
        self._emit_event("detection_stopped", {})
    
    async def _detection_loop(self):
        """Main detection loop"""
        while self.scanning:
            try:
                current_time = time.time()
                
                # Respect detection interval and cooldown
                if current_time - self.last_detection_time < self.detection_interval:
                    await asyncio.sleep(0.5)
                    continue
                
                # Only detect if we're in scanning state
                if self.state != AutoDetectionState.SCANNING:
                    await asyncio.sleep(0.5)
                    continue
                
                # Check for tag presence
                tag_present = await self.detect_tag_presence()
                
                if tag_present:
                    logger.info(f"Tag detected for programming Tag #{self.current_tag_number}")
                    self.state = AutoDetectionState.TAG_DETECTED
                    
                    self._emit_event("tag_detected", {
                        "tag_number": self.current_tag_number,
                        "sku": self.selected_sku
                    })
                    
                    # Start programming automatically
                    success = await self._program_detected_tag()
                    
                    if success:
                        # Move to next tag or complete
                        if self.current_tag_number < 2:
                            self.current_tag_number = 2
                            self.state = AutoDetectionState.SCANNING
                            self._emit_event("ready_for_next_tag", {
                                "tag_number": self.current_tag_number
                            })
                        else:
                            self.state = AutoDetectionState.COMPLETE
                            self._emit_event("session_complete", {
                                "sku": self.selected_sku,
                                "session_id": self.session_id
                            })
                            self.scanning = False
                    else:
                        self.state = AutoDetectionState.ERROR
                        self._emit_event("programming_error", {
                            "tag_number": self.current_tag_number,
                            "error": "Programming failed"
                        })
                    
                    # Set cooldown
                    self.last_detection_time = current_time
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Error in detection loop: {e}")
                self.state = AutoDetectionState.ERROR
                self._emit_event("detection_error", {"error": str(e)})
                await asyncio.sleep(2.0)
    
    async def _program_detected_tag(self) -> bool:
        """Program the currently detected tag"""
        try:
            self.state = AutoDetectionState.PROGRAMMING
            
            self._emit_event("programming_started", {
                "tag_number": self.current_tag_number,
                "sku": self.selected_sku
            })
            
            # Verify card type
            if not await verify_card_type():
                logger.error("Invalid card type detected")
                return False
            
            # Program the tag
            result = await program_tag(self.selected_binary)
            
            if not result["success"]:
                logger.error(f"Programming failed: {result['error']}")
                return False
            
            self._emit_event("programming_completed", {
                "tag_number": self.current_tag_number,
                "hash": result["hash"]
            })
            
            # Verify if strict mode is enabled
            if config.get("strict_verification", True):
                self.state = AutoDetectionState.VERIFYING
                
                self._emit_event("verification_started", {
                    "tag_number": self.current_tag_number
                })
                
                verified = await verify_tag(
                    self.selected_binary, 
                    result["hash"]
                )
                
                if verified:
                    self._emit_event("verification_completed", {
                        "tag_number": self.current_tag_number,
                        "status": "pass"
                    })
                else:
                    logger.error("Tag verification failed")
                    return False
            
            # Log successful programming
            log_action("tag_auto_programmed", self.session_id, {
                "tag_number": self.current_tag_number,
                "sku": self.selected_sku,
                "hash": result["hash"],
                "auto_detected": True
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Error programming tag: {e}")
            self.state = AutoDetectionState.ERROR
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current detection status"""
        return {
            "state": self.state.value,
            "scanning": self.scanning,
            "selected_sku": self.selected_sku,
            "current_tag_number": self.current_tag_number,
            "session_id": self.session_id
        }

# Global auto-detector instance
auto_detector = None

def get_auto_detector() -> TagAutoDetector:
    """Get global auto-detector instance"""
    global auto_detector
    if not auto_detector:
        auto_detector = TagAutoDetector()
    return auto_detector

async def start_auto_programming_session(sku: str) -> str:
    """Start new auto-programming session"""
    detector = get_auto_detector()
    
    # Generate session ID
    session_id = f"auto_{int(time.time())}"
    
    # Start auto-detection
    success = await detector.start_auto_detection(sku, session_id)
    
    if success:
        log_action("auto_session_started", session_id, {
            "sku": sku,
            "mode": "auto_detection"
        })
        return session_id
    else:
        raise Exception("Failed to start auto-detection")

def stop_auto_programming_session():
    """Stop current auto-programming session"""
    detector = get_auto_detector() 
    detector.stop_auto_detection()

if __name__ == "__main__":
    # Test auto-detection
    import sys
    import os
    sys.path.append(os.path.dirname(__file__))
    
    async def test_auto_detection():
        logging.basicConfig(level=logging.INFO)
        
        print("Testing auto-detection...")
        
        # Enable mock mode for testing
        config["mock_mode"] = True
        
        detector = get_auto_detector()
        
        # Set up callbacks
        def on_event(event_name):
            def callback(data):
                print(f"📡 Event: {event_name} - {data}")
            return callback
        
        detector.set_callback("detection_started", on_event("Detection Started"))
        detector.set_callback("tag_detected", on_event("Tag Detected"))
        detector.set_callback("programming_started", on_event("Programming Started"))
        detector.set_callback("programming_completed", on_event("Programming Completed"))
        detector.set_callback("ready_for_next_tag", on_event("Ready for Next Tag"))
        detector.set_callback("session_complete", on_event("Session Complete"))
        
        # Start session
        session_id = await start_auto_programming_session("PLA001")
        print(f"✅ Started auto-programming session: {session_id}")
        
        # Wait for completion or timeout
        timeout = 30
        start_time = time.time()
        
        while detector.scanning and (time.time() - start_time) < timeout:
            status = detector.get_status()
            print(f"Status: {status['state']} | Tag: {status['current_tag_number']}")
            await asyncio.sleep(2)
        
        stop_auto_programming_session()
        print("✅ Test completed")
    
    # Run test
    asyncio.run(test_auto_detection())