#!/usr/bin/env python3
"""
Unit tests for Filatag RFID Programmer

Run with: python -m pytest tests/test_filatag.py -v
"""

import pytest
import asyncio
import json
import tempfile
from pathlib import Path
import sys

# Add backend to path
sys.path.append(str(Path(__file__).parent.parent / 'backend'))

from server import (
    load_filament_mapping,
    mock_proxmark_command,
    verify_card_type,
    program_tag,
    verify_tag,
    config
)

class TestFilamentMapping:
    """Test filament mapping functionality"""
    
    def test_load_filament_mapping_creates_sample(self, tmp_path):
        """Test that load_filament_mapping creates sample data when file doesn't exist"""
        # Temporarily override the mapping file path
        import server
        original_path = server.MAPPING_FILE
        server.MAPPING_FILE = tmp_path / "test_mapping.json"
        
        try:
            mapping = load_filament_mapping()
            assert len(mapping) > 0
            assert "PLA001" in mapping
            assert mapping["PLA001"].name == "Premium PLA Red"
        finally:
            server.MAPPING_FILE = original_path
    
    def test_load_filament_mapping_from_file(self, tmp_path):
        """Test loading filament mapping from existing file"""
        # Create test mapping file
        test_mapping = {
            "TEST001": {
                "sku": "TEST001",
                "name": "Test Filament",
                "description": "Test description",
                "binary_file": "test001.bin"
            }
        }
        
        mapping_file = tmp_path / "test_mapping.json"
        with open(mapping_file, 'w') as f:
            json.dump(test_mapping, f)
        
        # Temporarily override the mapping file path
        import server
        original_path = server.MAPPING_FILE
        server.MAPPING_FILE = mapping_file
        
        try:
            mapping = load_filament_mapping()
            assert len(mapping) == 1
            assert "TEST001" in mapping
            assert mapping["TEST001"].name == "Test Filament"
        finally:
            server.MAPPING_FILE = original_path

class TestProxmarkMock:
    """Test Proxmark3 mock functionality"""
    
    @pytest.mark.asyncio
    async def test_mock_hw_status(self):
        """Test mock hardware status command"""
        result = await mock_proxmark_command("hw status")
        assert result["success"] == True
        assert "Proxmark3" in result["output"]
        assert "Iceman" in result["output"]
    
    @pytest.mark.asyncio
    async def test_mock_card_info(self):
        """Test mock card info command"""
        result = await mock_proxmark_command("hf 14a info")
        assert result["success"] == True
        assert "MIFARE Classic 1K" in result["output"]
        assert "UID:" in result["output"]
    
    @pytest.mark.asyncio
    async def test_mock_write_read_consistency(self):
        """Test that mock write and read commands are consistent"""
        # Clear any existing mock data
        import server
        server.mock_tag_data = {}
        
        # Write to block 4
        write_data = "00112233445566778899AABBCCDDEEFF"
        write_cmd = f"hf mf wrbl 4 A FFFFFFFFFFFF {write_data}"
        write_result = await mock_proxmark_command(write_cmd)
        assert write_result["success"] == True
        
        # Read from block 4
        read_cmd = "hf mf rdbl 4 A FFFFFFFFFFFF"
        read_result = await mock_proxmark_command(read_cmd)
        assert read_result["success"] == True
        
        # Extract hex data from read result
        output_line = read_result["output"]
        assert "Block data:" in output_line
        hex_data = output_line.split("Block data:")[-1].strip().replace(" ", "")
        assert hex_data == write_data

class TestCardOperations:
    """Test RFID card operations"""
    
    @pytest.mark.asyncio
    async def test_verify_card_type_mock(self):
        """Test card type verification in mock mode"""
        # Enable mock mode
        config["mock_mode"] = True
        
        result = await verify_card_type()
        assert result == True
        
        # Restore original config
        config["mock_mode"] = False
    
    @pytest.mark.asyncio
    async def test_program_tag_mock(self, tmp_path):
        """Test tag programming in mock mode"""
        # Enable mock mode
        config["mock_mode"] = True
        
        # Create test binary file
        binary_data = bytearray(1024)
        for i in range(1024):
            binary_data[i] = i % 256
        
        binary_file = tmp_path / "test.bin"
        with open(binary_file, "wb") as f:
            f.write(binary_data)
        
        # Clear mock data
        import server
        server.mock_tag_data = {}
        
        # Program the tag
        result = await program_tag(binary_file)
        
        assert result["success"] == True
        assert result["hash"] is not None
        assert len(result["hash"]) == 64  # SHA256 hex string
        
        # Restore original config
        config["mock_mode"] = False
    
    @pytest.mark.asyncio
    async def test_verify_tag_mock(self, tmp_path):
        """Test tag verification in mock mode"""
        # Enable mock mode
        config["mock_mode"] = True
        
        # Create test binary file
        binary_data = bytearray(1024)
        for i in range(1024):
            binary_data[i] = i % 256
        
        binary_file = tmp_path / "test.bin"
        with open(binary_file, "wb") as f:
            f.write(binary_data)
        
        # Calculate expected hash
        import hashlib
        expected_hash = hashlib.sha256(binary_data).hexdigest()
        
        # Verify tag (should always return True in mock mode)
        result = await verify_tag(binary_file, expected_hash)
        assert result == True
        
        # Restore original config
        config["mock_mode"] = False

class TestBinaryFiles:
    """Test binary file operations"""
    
    def test_binary_file_creation(self, tmp_path):
        """Test creating and validating binary files"""
        binary_file = tmp_path / "test.bin"
        
        # Create 1KB binary file
        data = bytearray(1024)
        for i in range(1024):
            data[i] = (i * 7) % 256  # Some pattern
        
        with open(binary_file, "wb") as f:
            f.write(data)
        
        # Verify file
        assert binary_file.exists()
        assert binary_file.stat().st_size == 1024
        
        # Read and verify content
        with open(binary_file, "rb") as f:
            read_data = f.read()
        
        assert len(read_data) == 1024
        assert read_data == data

class TestConfigManagement:
    """Test configuration management"""
    
    def test_config_defaults(self):
        """Test that config has required default values"""
        assert "device_path" in config
        assert "retries" in config
        assert "verification_timeout" in config
        assert "strict_verification" in config
        assert "default_keys" in config
        
        assert isinstance(config["retries"], int)
        assert config["retries"] > 0
        assert isinstance(config["verification_timeout"], int)
        assert isinstance(config["strict_verification"], bool)
        assert isinstance(config["default_keys"], list)
        assert len(config["default_keys"]) > 0
    
    def test_mock_mode_toggle(self):
        """Test toggling mock mode"""
        original_mock = config.get("mock_mode", False)
        
        # Toggle mock mode
        config["mock_mode"] = True
        assert config["mock_mode"] == True
        
        config["mock_mode"] = False
        assert config["mock_mode"] == False
        
        # Restore original
        config["mock_mode"] = original_mock

# Integration test fixtures
@pytest.fixture
def sample_binary_file(tmp_path):
    """Create a sample 1KB binary file for testing"""
    binary_file = tmp_path / "sample.bin"
    data = bytearray(1024)
    
    # Create a recognizable pattern
    for i in range(1024):
        data[i] = (i + 0x42) % 256
    
    with open(binary_file, "wb") as f:
        f.write(data)
    
    return binary_file

@pytest.fixture
def sample_mapping_file(tmp_path):
    """Create a sample mapping file for testing"""
    mapping_data = {
        "TEST001": {
            "sku": "TEST001",
            "name": "Test PLA Red",
            "description": "Test filament for unit tests",
            "binary_file": "test001.bin"
        },
        "TEST002": {
            "sku": "TEST002",
            "name": "Test ABS Blue", 
            "description": "Another test filament",
            "binary_file": "test002.bin",
            "keys": ["FFFFFFFFFFFF", "123456789ABC"]
        }
    }
    
    mapping_file = tmp_path / "test_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump(mapping_data, f, indent=2)
    
    return mapping_file

class TestIntegration:
    """Integration tests"""
    
    @pytest.mark.asyncio
    async def test_full_programming_workflow_mock(self, sample_binary_file):
        """Test complete programming workflow in mock mode"""
        # Enable mock mode
        config["mock_mode"] = True
        
        # Clear mock data
        import server
        server.mock_tag_data = {}
        
        try:
            # Step 1: Verify card type
            card_ok = await verify_card_type()
            assert card_ok == True
            
            # Step 2: Program the tag
            program_result = await program_tag(sample_binary_file)
            assert program_result["success"] == True
            assert program_result["hash"] is not None
            
            # Step 3: Verify the tag
            verify_result = await verify_tag(
                sample_binary_file, 
                program_result["hash"]
            )
            assert verify_result == True
            
        finally:
            # Restore original config
            config["mock_mode"] = False

if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v"])