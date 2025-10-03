from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
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
    "mock_mode": False,
    "default_keys": ["FFFFFFFFFFFF", "000000000000"]
}

# Load config if exists
if CONFIG_FILE.exists():
    with open(CONFIG_FILE) as f:
        config.update(json.load(f))

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
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    logs.append(json.loads(line.strip()))
                except:
                    continue
    return logs

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
    logger.info("Filatag RFID Programmer started")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)