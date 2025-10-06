#!/usr/bin/env python3
"""
Python 3.9.2 Compatibility Test for Filatag Backend
Tests that all required packages can be imported successfully
"""

import sys
import importlib

def test_python_version():
    """Test Python version compatibility"""
    print(f"Python version: {sys.version}")
    version_info = sys.version_info
    
    if version_info.major == 3 and version_info.minor >= 9:
        print("✅ Python version is compatible (3.9+)")
        return True
    else:
        print("❌ Python version is not compatible (requires 3.9+)")
        return False

def test_package_imports():
    """Test that all required packages can be imported"""
    required_packages = [
        'fastapi',
        'uvicorn', 
        'starlette',
        'pydantic',
        'motor',
        'pymongo',
        'numpy',
        'cv2',  # opencv-python
        'pandas',
        'dotenv',  # python-dotenv
        'pyzbar',
        'jwt',  # PyJWT
        'passlib',
        'jose',  # python-jose
        'cryptography',
        'requests',
        'httpx',
        'boto3',
        'botocore',
        'click',
        'rich',
        'typer',
        'dateutil',  # python-dateutil
        'typing_extensions',
        'email_validator',
        'certifi',
        'charset_normalizer',
        'idna',
        'urllib3',
        'six',
        'pytz',
        'packaging'
    ]
    
    successful_imports = 0
    failed_imports = []
    
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package}")
            successful_imports += 1
        except ImportError as e:
            print(f"❌ {package} - {str(e)}")
            failed_imports.append(package)
        except Exception as e:
            print(f"⚠️  {package} - Unexpected error: {str(e)}")
            failed_imports.append(package)
    
    print(f"\nImport Results:")
    print(f"Successful: {successful_imports}/{len(required_packages)}")
    print(f"Failed: {len(failed_imports)}")
    
    if failed_imports:
        print(f"Failed packages: {', '.join(failed_imports)}")
        return False
    else:
        print("🎉 All required packages imported successfully!")
        return True

def test_backend_server_imports():
    """Test that the backend server can import its dependencies"""
    try:
        # Test importing the main server module components
        from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
        from fastapi.responses import StreamingResponse, Response
        from starlette.middleware.cors import CORSMiddleware
        from dotenv import load_dotenv
        from motor.motor_asyncio import AsyncIOMotorClient
        from pydantic import BaseModel, Field
        from typing import List, Optional, Dict, Any
        from datetime import datetime, timezone
        from enum import Enum
        import uuid
        import hashlib
        import base64
        import os
        import logging
        import json
        import asyncio
        import subprocess
        import time
        from pathlib import Path
        
        print("✅ All backend server imports successful")
        return True
        
    except ImportError as e:
        print(f"❌ Backend server import failed: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Backend server import error: {str(e)}")
        return False

def main():
    """Main compatibility test runner"""
    print("=" * 60)
    print("  PYTHON 3.9.2 COMPATIBILITY TEST")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 3
    
    # Test 1: Python version
    if test_python_version():
        tests_passed += 1
    
    print("\n" + "-" * 40)
    
    # Test 2: Package imports
    if test_package_imports():
        tests_passed += 1
    
    print("\n" + "-" * 40)
    
    # Test 3: Backend server imports
    if test_backend_server_imports():
        tests_passed += 1
    
    print("\n" + "=" * 60)
    print("  COMPATIBILITY TEST RESULTS")
    print("=" * 60)
    print(f"Tests Passed: {tests_passed}/{total_tests}")
    
    if tests_passed == total_tests:
        print("🎉 All compatibility tests passed!")
        print("Backend is ready for Python 3.9.2 deployment")
        return 0
    else:
        print(f"⚠️  {total_tests - tests_passed} test(s) failed")
        print("Some compatibility issues may exist")
        return 1

if __name__ == "__main__":
    sys.exit(main())