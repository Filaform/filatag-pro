from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, Response
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import json
import asyncio
import subprocess
import time
import hashlib
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum
import uuid
import signal
import base64


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Configuration
BINARIES_PATH = Path("/opt/filatag/binaries")
MAPPING_FILE = Path("/etc/filatag/mapping.json") 
LOG_FILE = Path("/var/log/filatag/actions.log")
CONFIG_FILE = Path("/etc/filatag/config.json")

# Ensure directories exist for development
os.makedirs(BINARIES_PATH, exist_ok=True)
os.makedirs(LOG_FILE.parent, exist_ok=True)
os.makedirs(MAPPING_FILE.parent, exist_ok=True)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="Filatag RFID Programmer", version="1.0.0")
api_router = APIRouter(prefix="/api")

# Global config
config = {
    "device_path": "/dev/ttyACM0",
    "retries": 3,
    "verification_timeout": 30,
    "strict_verification": True,
    "mock_mode": True,  # Enable mock mode for demonstration
    "default_keys": ["FFFFFFFFFFFF", "000000000000"],
    "git_repo_url": "https://github.com/Filaform/filatag-pro.git"
}

# Load config if exists
if CONFIG_FILE.exists():
    with open(CONFIG_FILE) as f:
        config.update(json.load(f))

def load_config():
    """Load current configuration"""
    return config.copy()

# Enums
class TagStatus(str, Enum):
    PENDING = "pending"
    WRITING = "writing"
    VERIFYING = "verifying" 
    PASS = "pass"
    FAIL = "fail"
    ERROR = "error"

class VerificationMode(str, Enum):
    STRICT = "strict"
    TOLERANT = "tolerant"

# Models
class Filament(BaseModel):
    sku: str
    name: str
    description: str
    binary_file: str
    keys: Optional[List[str]] = None

class ProgrammingSession(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sku: str
    spool_id: str
    operator: Optional[str] = None
    tag1_status: TagStatus = TagStatus.PENDING
    tag2_status: TagStatus = TagStatus.PENDING
    tag1_hash: Optional[str] = None
    tag2_hash: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    logs: List[str] = Field(default_factory=list)
    retries_used: int = 0

class ProgrammingRequest(BaseModel):
    sku: str
    spool_id: str
    operator: Optional[str] = None

class ProxmarkCommand(BaseModel):
    command: str
    timeout: int = 30
    mock: bool = False

# Global state for active sessions
active_sessions: Dict[str, ProgrammingSession] = {}

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def log_action(action_type: str, session_id: str, data: Dict[str, Any]):
    """Log structured action to file"""
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action_type,
        "session_id": session_id,
        **data
    }
    
    try:
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to write log: {e}")

def load_filament_mapping() -> Dict[str, Filament]:
    """Load filament mapping from JSON file"""
    if not MAPPING_FILE.exists():
        # Create sample mapping for development
        sample_mapping = {
            "PLA001": {
                "sku": "PLA001", 
                "name": "Premium PLA Red",
                "description": "High-quality PLA filament in vibrant red",
                "binary_file": "pla001.bin"
            },
            "ABS002": {
                "sku": "ABS002",
                "name": "Industrial ABS Black", 
                "description": "Strong ABS filament for industrial applications",
                "binary_file": "abs002.bin"
            },
            "PETG003": {
                "sku": "PETG003",
                "name": "Clear PETG Natural",
                "description": "Crystal clear PETG for transparent prints",
                "binary_file": "petg003.bin"
            }
        }
        with open(MAPPING_FILE, "w") as f:
            json.dump(sample_mapping, f, indent=2)
    
    try:
        with open(MAPPING_FILE) as f:
            data = json.load(f)
            return {sku: Filament(**info) for sku, info in data.items()}
    except Exception as e:
        logger.error(f"Failed to load mapping: {e}")
        return {}

def create_sample_binaries():
    """Create sample binary files for development"""
    for sku in ["PLA001", "ABS002", "PETG003"]:
        binary_path = BINARIES_PATH / f"{sku.lower()}.bin"
        if not binary_path.exists():
            # Create a sample 1KB binary (MIFARE Classic 1K size)
            sample_data = bytearray(1024)
            # Fill with some pattern
            for i in range(1024):
                sample_data[i] = i % 256
            with open(binary_path, "wb") as f:
                f.write(sample_data)

async def detect_proxmark_device() -> Optional[str]:
    """Auto-detect Proxmark3 device path"""
    # In mock mode, always return a mock device path
    if config.get("mock_mode", False):
        return "/dev/ttyACM0"
    
    possible_paths = ["/dev/ttyACM0", "/dev/ttyACM1", "/dev/ttyUSB0", "/dev/ttyUSB1"]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                # Try to communicate with device
                result = await run_proxmark_command(f"hw status", timeout=5, device_path=path)
                if "Proxmark3" in result.get("output", ""):
                    return path
            except:
                continue
    return None

async def run_proxmark_command(command: str, timeout: int = 30, device_path: str = None, mock: bool = None) -> Dict[str, Any]:
    """Execute proxmark command and return result"""
    if mock is None:
        mock = config.get("mock_mode", False)
    
    if mock:
        return await mock_proxmark_command(command)
    
    device = device_path or config["device_path"]
    
    try:
        # Build proxmark command
        cmd = ["pm3", "-c", command]
        if device:
            cmd.extend(["-p", device])
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), 
            timeout=timeout
        )
        
        return {
            "success": process.returncode == 0,
            "output": stdout.decode() if stdout else "",
            "error": stderr.decode() if stderr else "",
            "return_code": process.returncode
        }
        
    except asyncio.TimeoutError:
        return {
            "success": False,
            "output": "",
            "error": f"Command timed out after {timeout}s",
            "return_code": -1
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "return_code": -1
        }

# Global mock storage to simulate written data
mock_tag_data = {}

async def mock_proxmark_command(command: str) -> Dict[str, Any]:
    """Mock proxmark command for testing"""
    global mock_tag_data
    await asyncio.sleep(0.2)  # Simulate command delay
    
    if "hw status" in command:
        return {
            "success": True,
            "output": "Proxmark3 RFID instrument\nFirmware............ Iceman/master/v4.18994",
            "error": "",
            "return_code": 0
        }
    elif "hf 14a info" in command:
        return {
            "success": True,
            "output": "UID: 12 34 56 78\nATQA: 00 04\nSAK: 08\nType: MIFARE Classic 1K",
            "error": "",
            "return_code": 0
        }
    elif "hf mf wrbl" in command:
        # Parse write command: "hf mf wrbl <block> A <key> <data>"
        parts = command.split()
        if len(parts) >= 6:
            block_num = int(parts[3])
            hex_data = parts[6]
            # Store the written data for later reading
            mock_tag_data[block_num] = hex_data
        
        return {
            "success": True,
            "output": "Block written successfully",
            "error": "",
            "return_code": 0
        }
    elif "hf mf rdbl" in command:
        # Parse read command: "hf mf rdbl <block> A <key>"
        parts = command.split()
        if len(parts) >= 4:
            block_num = int(parts[3])
            # Return previously written data or default pattern
            if block_num in mock_tag_data:
                hex_data = mock_tag_data[block_num]
                # Format as Proxmark3 would output
                formatted_hex = ' '.join(hex_data[i:i+2] for i in range(0, len(hex_data), 2))
                return {
                    "success": True,
                    "output": f"Block data: {formatted_hex.upper()}",
                    "error": "",
                    "return_code": 0
                }
            else:
                # Default pattern for unwritten blocks
                pattern = f"{block_num:02X}" * 16
                formatted_hex = ' '.join(pattern[i:i+2] for i in range(0, len(pattern), 2))
                return {
                    "success": True,
                    "output": f"Block data: {formatted_hex}",
                    "error": "",
                    "return_code": 0
                }
        
        return {
            "success": True,
            "output": "Block data: 00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F",
            "error": "",
            "return_code": 0
        }
    else:
        return {
            "success": True,
            "output": f"Mock response for: {command}",
            "error": "",
            "return_code": 0
        }

async def verify_card_type() -> bool:
    """Verify that the card is MIFARE Classic 1K"""
    result = await run_proxmark_command("hf 14a info")
    if not result["success"]:
        return False
    
    output = result["output"].lower()
    return "mifare classic" in output and ("1k" in output or "1024" in output)

async def program_tag(binary_path: Path, keys: List[str] = None) -> Dict[str, Any]:
    """Program a single RFID tag with binary data"""
    if keys is None:
        keys = config["default_keys"]
    
    # Verify card type first
    if not await verify_card_type():
        return {
            "success": False,
            "error": "Card is not MIFARE Classic 1K",
            "hash": None
        }
    
    # Read binary file
    if not binary_path.exists():
        return {
            "success": False,
            "error": f"Binary file not found: {binary_path}",
            "hash": None
        }
    
    with open(binary_path, "rb") as f:
        binary_data = f.read()
    
    if len(binary_data) != 1024:
        return {
            "success": False,
            "error": f"Invalid binary size: {len(binary_data)} (expected 1024)",
            "hash": None
        }
    
    # Calculate hash for verification
    binary_hash = hashlib.sha256(binary_data).hexdigest()
    
    # Program sectors (skip sector 0 block 0 - manufacturer data)
    for sector in range(16):  # MIFARE Classic 1K has 16 sectors
        for block in range(4):  # Each sector has 4 blocks
            block_num = sector * 4 + block
            
            # Skip manufacturer block and trailer blocks
            if block_num == 0 or (block + 1) % 4 == 0:
                continue
            
            # Get block data
            start_byte = block_num * 16
            end_byte = start_byte + 16
            block_data = binary_data[start_byte:end_byte]
            
            # Convert to hex string
            hex_data = block_data.hex().upper()
            
            # Write block
            for key in keys:
                cmd = f"hf mf wrbl {block_num} A {key} {hex_data}"
                result = await run_proxmark_command(cmd)
                if result["success"]:
                    break
            else:
                return {
                    "success": False,
                    "error": f"Failed to write block {block_num}",
                    "hash": binary_hash
                }
    
    return {
        "success": True,
        "error": None,
        "hash": binary_hash
    }

async def verify_tag(binary_path: Path, expected_hash: str, keys: List[str] = None) -> bool:
    """Verify tag contents match expected binary"""
    if keys is None:
        keys = config["default_keys"]
    
    # In mock mode, always return True for verification
    if config.get("mock_mode", False):
        await asyncio.sleep(1)  # Simulate verification time
        return True
    
    read_data = bytearray(1024)
    
    # Read all blocks
    for sector in range(16):
        for block in range(4):
            block_num = sector * 4 + block
            
            # Skip trailer blocks for reading
            if (block + 1) % 4 == 0:
                continue
            
            # Read block
            success = False
            for key in keys:
                cmd = f"hf mf rdbl {block_num} A {key}"
                result = await run_proxmark_command(cmd)
                if result["success"]:
                    # Parse hex data from output
                    output_lines = result["output"].split('\n')
                    for line in output_lines:
                        if "Block data:" in line or str(block_num) in line:
                            hex_part = line.split(':')[-1].strip()
                            hex_bytes = hex_part.replace(' ', '')
                            if len(hex_bytes) == 32:  # 16 bytes * 2 hex chars
                                block_data = bytes.fromhex(hex_bytes)
                                start_byte = block_num * 16
                                read_data[start_byte:start_byte + 16] = block_data
                                success = True
                                break
                    if success:
                        break
            
            if not success:
                logger.error(f"Failed to read block {block_num}")
                return False
    
    # Calculate hash of read data
    read_hash = hashlib.sha256(read_data).hexdigest()
    return read_hash == expected_hash

# Import auto-detection and camera modules
try:
    from camera_scanner import initialize_camera_scanner, get_scanner, get_barcode_mapper, cleanup_camera_scanner
    from auto_detector import get_auto_detector, start_auto_programming_session, stop_auto_programming_session
    CAMERA_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Camera/barcode scanning not available: {e}")
    CAMERA_AVAILABLE = False

# New Models for Auto Detection
class AutoProgrammingRequest(BaseModel):
    sku: str

class BarcodeMapping(BaseModel):
    barcode: str
    sku: str

class CameraStatus(BaseModel):
    available: bool
    initialized: bool
    scanning: bool

# API Routes
@api_router.get("/filaments", response_model=List[Filament])
async def get_filaments():
    """Get list of available filaments"""
    mapping = load_filament_mapping()
    return list(mapping.values())

@api_router.get("/device/status")
async def get_device_status():
    """Check Proxmark3 device status"""
    device_path = await detect_proxmark_device()
    if device_path:
        config["device_path"] = device_path
        result = await run_proxmark_command("hw status")
        return {
            "connected": result["success"],
            "device_path": device_path,
            "output": result["output"],
            "mock_mode": config.get("mock_mode", False)
        }
    else:
        return {
            "connected": False,
            "device_path": None,
            "output": "No Proxmark3 device found",
            "mock_mode": config.get("mock_mode", False)
        }

@api_router.post("/programming/start", response_model=ProgrammingSession)
async def start_programming_session(request: ProgrammingRequest):
    """Start a new programming session"""
    mapping = load_filament_mapping()
    
    if request.sku not in mapping:
        raise HTTPException(status_code=404, detail=f"SKU {request.sku} not found")
    
    filament = mapping[request.sku]
    binary_path = BINARIES_PATH / filament.binary_file
    
    if not binary_path.exists():
        raise HTTPException(status_code=404, detail=f"Binary file not found: {filament.binary_file}")
    
    session = ProgrammingSession(
        sku=request.sku,
        spool_id=request.spool_id,
        operator=request.operator
    )
    
    active_sessions[session.id] = session
    
    log_action("session_started", session.id, {
        "sku": request.sku,
        "spool_id": request.spool_id,
        "operator": request.operator
    })
    
    return session

@api_router.post("/programming/{session_id}/tag/{tag_num}")
async def program_tag_endpoint(session_id: str, tag_num: int, background_tasks: BackgroundTasks):
    """Program a specific tag (1 or 2) in the session"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if tag_num not in [1, 2]:
        raise HTTPException(status_code=400, detail="Tag number must be 1 or 2")
    
    session = active_sessions[session_id]
    mapping = load_filament_mapping()
    filament = mapping[session.sku]
    binary_path = BINARIES_PATH / filament.binary_file
    
    # Update status
    if tag_num == 1:
        session.tag1_status = TagStatus.WRITING
    else:
        session.tag2_status = TagStatus.WRITING
    
    # Program tag in background
    background_tasks.add_task(program_tag_background, session_id, tag_num, binary_path, filament.keys)
    
    return {"message": f"Programming tag {tag_num} started"}

async def program_tag_background(session_id: str, tag_num: int, binary_path: Path, keys: Optional[List[str]]):
    """Background task to program and verify a tag"""
    session = active_sessions[session_id]
    
    try:
        # Program the tag
        result = await program_tag(binary_path, keys)
        
        if result["success"]:
            # Update status and hash
            if tag_num == 1:
                session.tag1_status = TagStatus.VERIFYING
                session.tag1_hash = result["hash"]
            else:
                session.tag2_status = TagStatus.VERIFYING 
                session.tag2_hash = result["hash"]
            
            # Verify the tag
            if config["strict_verification"]:
                verified = await verify_tag(binary_path, result["hash"], keys)
                final_status = TagStatus.PASS if verified else TagStatus.FAIL
            else:
                final_status = TagStatus.PASS
            
            # Update final status
            if tag_num == 1:
                session.tag1_status = final_status
            else:
                session.tag2_status = final_status
            
            log_action("tag_programmed", session_id, {
                "tag_num": tag_num,
                "status": final_status.value,
                "hash": result["hash"],
                "retries": 0
            })
            
        else:
            # Programming failed
            if tag_num == 1:
                session.tag1_status = TagStatus.FAIL
            else:
                session.tag2_status = TagStatus.FAIL
            
            log_action("tag_failed", session_id, {
                "tag_num": tag_num,
                "error": result["error"],
                "retries": 0
            })
    
    except Exception as e:
        if tag_num == 1:
            session.tag1_status = TagStatus.ERROR
        else:
            session.tag2_status = TagStatus.ERROR
        
        log_action("tag_error", session_id, {
            "tag_num": tag_num,
            "error": str(e),
            "retries": 0
        })

@api_router.get("/programming/{session_id}", response_model=ProgrammingSession)
async def get_programming_session(session_id: str):
    """Get programming session status"""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return active_sessions[session_id]

@api_router.get("/config")
async def get_config():
    """Get current configuration"""
    return config

@api_router.post("/config")
async def update_config(new_config: dict):
    """Update configuration"""
    config.update(new_config)
    
    # Save to file
    os.makedirs(CONFIG_FILE.parent, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
    
    return config

@api_router.get("/logs")
async def get_logs(limit: int = 100):
    """Get recent log entries"""
    logs = []
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    line = line.strip()
                    if line:
                        try:
                            logs.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return {"logs": logs, "total": len(logs)}
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return {"logs": [], "total": 0, "error": str(e)}

@api_router.post("/logs/clear")
async def clear_logs():
    """Clear all log entries"""
    try:
        if LOG_FILE.exists():
            # Backup current logs before clearing
            backup_file = LOG_FILE.with_suffix('.backup')
            with open(LOG_FILE, 'r') as src, open(backup_file, 'w') as dst:
                dst.write(src.read())
            
            # Clear the log file
            with open(LOG_FILE, 'w') as f:
                f.write("")
            
            log_action("logs_cleared", "system", {
                "cleared_by": "user_request",
                "backup_created": str(backup_file)
            })
            
            return {"message": "Logs cleared successfully", "backup": str(backup_file)}
        else:
            return {"message": "No log file found"}
    except Exception as e:
        logger.error(f"Error clearing logs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear logs: {e}")

# New Auto-Detection Endpoints
@api_router.get("/camera/status")
async def get_camera_status():
    """Get camera system status"""
    if not CAMERA_AVAILABLE:
        return CameraStatus(available=False, initialized=False, scanning=False)
    
    scanner = get_scanner()
    return CameraStatus(
        available=True,
        initialized=scanner is not None and scanner.cap is not None,
        scanning=scanner is not None and scanner.scanning
    )

@api_router.post("/camera/initialize")
async def initialize_camera(camera_index: int = 0):
    """Initialize camera system"""
    if not CAMERA_AVAILABLE:
        raise HTTPException(status_code=400, detail="Camera system not available")
    
    success = initialize_camera_scanner(camera_index)
    if success:
        return {"message": "Camera initialized successfully", "camera_index": camera_index}
    else:
        raise HTTPException(status_code=500, detail="Failed to initialize camera")

@api_router.get("/camera/frame")
async def get_camera_frame():
    """Get current camera frame as JPEG"""
    if not CAMERA_AVAILABLE:
        raise HTTPException(status_code=400, detail="Camera system not available")
    
    scanner = get_scanner()
    if not scanner:
        raise HTTPException(status_code=400, detail="Camera not initialized")
    
    frame = scanner.get_camera_frame()
    if frame is None:
        raise HTTPException(status_code=500, detail="Failed to capture frame")
    
    # Convert frame to JPEG
    import cv2
    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    
    return Response(content=buffer.tobytes(), media_type="image/jpeg")

@api_router.get("/barcode/scan")
async def scan_barcode():
    """Scan for barcode in current camera view"""
    if not CAMERA_AVAILABLE:
        raise HTTPException(status_code=400, detail="Camera system not available")
    
    scanner = get_scanner()
    if not scanner:
        raise HTTPException(status_code=400, detail="Camera not initialized")
    
    # Try to get latest scan from continuous scanning
    scan_result = scanner.get_latest_scan()
    if scan_result:
        mapper = get_barcode_mapper()
        sku = mapper.get_sku_from_barcode(scan_result['data'])
        
        return {
            "barcode": scan_result['data'],
            "type": scan_result['type'],
            "sku": sku,
            "timestamp": scan_result['timestamp']
        }
    
    # If no continuous scan available, try single scan
    scan_result = scanner.scan_single_frame()
    if scan_result:
        mapper = get_barcode_mapper()
        sku = mapper.get_sku_from_barcode(scan_result['data'])
        
        return {
            "barcode": scan_result['data'],
            "type": scan_result['type'], 
            "sku": sku,
            "timestamp": scan_result['timestamp']
        }
    
    return {"barcode": None, "sku": None}

@api_router.get("/barcode/mappings")
async def get_barcode_mappings():
    """Get all barcode to SKU mappings"""
    if not CAMERA_AVAILABLE:
        return {}
    
    mapper = get_barcode_mapper()
    return mapper.get_all_mappings()

@api_router.post("/barcode/mapping")
async def add_barcode_mapping(mapping: BarcodeMapping):
    """Add new barcode to SKU mapping"""
    if not CAMERA_AVAILABLE:
        raise HTTPException(status_code=400, detail="Camera system not available")
    
    mapper = get_barcode_mapper()
    mapper.add_barcode_mapping(mapping.barcode, mapping.sku)
    
    return {"message": f"Added mapping: {mapping.barcode} -> {mapping.sku}"}

@api_router.post("/auto-programming/start")
async def start_auto_programming(request: AutoProgrammingRequest):
    """Start automatic programming session with auto-detection"""
    mapping = load_filament_mapping()
    
    if request.sku not in mapping:
        raise HTTPException(status_code=404, detail=f"SKU {request.sku} not found")
    
    try:
        session_id = await start_auto_programming_session(request.sku)
        
        return {
            "session_id": session_id,
            "sku": request.sku,
            "message": "Auto-programming started. Place Tag #1 on Proxmark3 antenna.",
            "mode": "auto_detection"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start auto-programming: {e}")

@api_router.post("/auto-programming/stop")
async def stop_auto_programming():
    """Stop current auto-programming session"""
    try:
        stop_auto_programming_session()
        return {"message": "Auto-programming stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop auto-programming: {e}")

@api_router.get("/auto-programming/status") 
async def get_auto_programming_status():
    """Get current auto-programming status"""
    detector = get_auto_detector()
    return detector.get_status()

@api_router.get("/system/git-status")
async def check_git_status():
    """Check if git updates are available"""
    try:
        # Load configuration to get git repository URL
        config = load_config()
        git_repo_url = config.get('git_repo_url', 'https://github.com/Filaform/filatag-pro.git')
        
        # Get current project directory (assuming we're in /opt/filatag or similar)
        project_dir = Path(__file__).parent.parent
        
        # Check if we have a git repository, if not try to initialize
        git_dir = project_dir / '.git'
        if not git_dir.exists():
            # Initialize git repository
            init_result = subprocess.run([
                'git', 'init'
            ], cwd=project_dir, capture_output=True, text=True, timeout=30)
            
            if init_result.returncode != 0:
                return {
                    "status": "error",
                    "message": f"Failed to initialize git repository: {init_result.stderr}",
                    "updates_available": False
                }
            
            # Add remote origin
            remote_result = subprocess.run([
                'git', 'remote', 'add', 'origin', git_repo_url
            ], cwd=project_dir, capture_output=True, text=True, timeout=30)
            
            if remote_result.returncode != 0:
                return {
                    "status": "error",
                    "message": f"Failed to add git remote: {remote_result.stderr}",
                    "updates_available": False
                }
        else:
            # Check if remote exists, if not add it
            remote_check = subprocess.run([
                'git', 'remote', 'get-url', 'origin'
            ], cwd=project_dir, capture_output=True, text=True, timeout=10)
            
            if remote_check.returncode != 0:
                # Remote doesn't exist, add it
                remote_result = subprocess.run([
                    'git', 'remote', 'add', 'origin', git_repo_url
                ], cwd=project_dir, capture_output=True, text=True, timeout=30)
            else:
                # Update remote URL in case it changed in settings
                remote_result = subprocess.run([
                    'git', 'remote', 'set-url', 'origin', git_repo_url
                ], cwd=project_dir, capture_output=True, text=True, timeout=30)
        
        # Fetch latest changes from remote
        result = subprocess.run([
            'git', 'fetch', 'origin'
        ], cwd=project_dir, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            return {
                "status": "error", 
                "message": f"Failed to fetch from remote: {result.stderr}",
                "updates_available": False
            }
        
        # Check if local is behind remote
        result = subprocess.run([
            'git', 'rev-list', '--count', 'HEAD..origin/main'
        ], cwd=project_dir, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            # Try master branch if main doesn't exist
            result = subprocess.run([
                'git', 'rev-list', '--count', 'HEAD..origin/master'
            ], cwd=project_dir, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            commits_behind = int(result.stdout.strip()) if result.stdout.strip() else 0
            updates_available = commits_behind > 0
            
            # Get current commit info
            current_commit_result = subprocess.run([
                'git', 'log', '--oneline', '-1'
            ], cwd=project_dir, capture_output=True, text=True, timeout=10)
            
            current_commit = current_commit_result.stdout.strip() if current_commit_result.returncode == 0 else "Unknown"
            
            # Get latest remote commit info if updates available
            latest_commit = ""
            if updates_available:
                latest_commit_result = subprocess.run([
                    'git', 'log', '--oneline', '-1', 'origin/main'
                ], cwd=project_dir, capture_output=True, text=True, timeout=10)
                
                if latest_commit_result.returncode != 0:
                    # Try master branch
                    latest_commit_result = subprocess.run([
                        'git', 'log', '--oneline', '-1', 'origin/master'
                    ], cwd=project_dir, capture_output=True, text=True, timeout=10)
                
                latest_commit = latest_commit_result.stdout.strip() if latest_commit_result.returncode == 0 else "Unknown"
            
            return {
                "status": "success",
                "updates_available": updates_available,
                "commits_behind": commits_behind,
                "current_commit": current_commit,
                "latest_commit": latest_commit,
                "message": f"{commits_behind} update(s) available" if updates_available else "Up to date"
            }
        else:
            return {
                "status": "error",
                "message": "Failed to check git status",
                "updates_available": False
            }
            
    except subprocess.TimeoutExpired:
        return {
            "status": "error", 
            "message": "Git operation timed out",
            "updates_available": False
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": str(e),
            "updates_available": False
        }

@api_router.post("/system/git-update")
async def install_git_updates():
    """Install git updates"""
    try:
        # Load configuration to get git repository URL
        config = load_config()
        git_repo_url = config.get('git_repo_url', 'https://github.com/Filaform/filatag-pro.git')
        
        project_dir = Path(__file__).parent.parent
        
        # Check if we have a git repository, if not try to clone instead of pull
        git_dir = project_dir / '.git'
        if not git_dir.exists():
            return {
                "status": "error",
                "message": "No git repository found. Use 'Check Updates' first to initialize repository tracking, or clone the repository manually.",
                "restart_required": False
            }
        
        # Ensure remote is set to correct URL
        remote_check = subprocess.run([
            'git', 'remote', 'get-url', 'origin'
        ], cwd=project_dir, capture_output=True, text=True, timeout=10)
        
        if remote_check.returncode != 0:
            # Remote doesn't exist, add it
            remote_result = subprocess.run([
                'git', 'remote', 'add', 'origin', git_repo_url
            ], cwd=project_dir, capture_output=True, text=True, timeout=30)
        else:
            # Update remote URL in case it changed in settings
            remote_result = subprocess.run([
                'git', 'remote', 'set-url', 'origin', git_repo_url
            ], cwd=project_dir, capture_output=True, text=True, timeout=30)
        
        # Stash any local changes
        stash_result = subprocess.run([
            'git', 'stash', 'push', '-m', f'Auto-stash before update {datetime.now().isoformat()}'
        ], cwd=project_dir, capture_output=True, text=True, timeout=30)
        
        # Pull latest changes
        pull_result = subprocess.run([
            'git', 'pull', 'origin', 'main'
        ], cwd=project_dir, capture_output=True, text=True, timeout=60)
        
        if pull_result.returncode != 0:
            # Try master branch if main fails
            pull_result = subprocess.run([
                'git', 'pull', 'origin', 'master'
            ], cwd=project_dir, capture_output=True, text=True, timeout=60)
        
        if pull_result.returncode == 0:
            # Update Python dependencies if requirements.txt changed
            requirements_file = project_dir / "backend" / "requirements.txt"
            if requirements_file.exists():
                pip_result = subprocess.run([
                    'pip', 'install', '-r', str(requirements_file)
                ], capture_output=True, text=True, timeout=300)
                
                if pip_result.returncode != 0:
                    logger.warning(f"Failed to update Python dependencies: {pip_result.stderr}")
            
            # Update Node.js dependencies if package.json changed
            package_json = project_dir / "frontend" / "package.json"
            if package_json.exists():
                yarn_result = subprocess.run([
                    'yarn', 'install'
                ], cwd=project_dir / "frontend", capture_output=True, text=True, timeout=300)
                
                if yarn_result.returncode != 0:
                    logger.warning(f"Failed to update Node.js dependencies: {yarn_result.stderr}")
            
            # Get new commit info
            new_commit_result = subprocess.run([
                'git', 'log', '--oneline', '-1'
            ], cwd=project_dir, capture_output=True, text=True, timeout=10)
            
            new_commit = new_commit_result.stdout.strip() if new_commit_result.returncode == 0 else "Unknown"
            
            return {
                "status": "success",
                "message": "Updates installed successfully. Please restart the application.",
                "new_commit": new_commit,
                "restart_required": True
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to pull updates: {pull_result.stderr}",
                "restart_required": False
            }
            
    except subprocess.TimeoutExpired:
        return {
            "status": "error", 
            "message": "Update operation timed out",
            "restart_required": False
        }
    except Exception as e:
        return {
            "status": "error", 
            "message": str(e),
            "restart_required": False
        }

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Initialize application"""
    create_sample_binaries()
    load_filament_mapping()
    
    # Initialize camera system if available
    if CAMERA_AVAILABLE:
        try:
            camera_initialized = initialize_camera_scanner()
            if camera_initialized:
                logger.info("Camera system initialized successfully")
            else:
                logger.warning("Camera system available but failed to initialize")
        except Exception as e:
            logger.warning(f"Failed to initialize camera system: {e}")
    
    logger.info("Filatag RFID Programmer started")

@app.on_event("shutdown")
async def shutdown_db_client():
    # Clean up camera system
    if CAMERA_AVAILABLE:
        try:
            cleanup_camera_scanner()
        except Exception as e:
            logger.error(f"Error cleaning up camera: {e}")
    
    client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)