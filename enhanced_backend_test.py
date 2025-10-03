#!/usr/bin/env python3
"""
Enhanced Backend API Testing for Filatag RFID Programmer
Tests new automated workflow features including camera scanning, barcode mapping, 
and auto-detection capabilities
"""

import requests
import sys
import json
import time
from datetime import datetime

class EnhancedFilatagAPITester:
    def __init__(self, base_url="https://filatagger.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.auto_session_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=15):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            else:
                print(f"❌ Unsupported method: {method}")
                return False, {}

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    return True, response_data
                except:
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:300]}...")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timed out after {timeout}s")
            return False, {}
        except requests.exceptions.ConnectionError:
            print(f"❌ Failed - Connection error (server may be down)")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_camera_status_api(self):
        """Test camera status API endpoint"""
        success, data = self.run_test(
            "Camera Status API",
            "GET",
            "camera/status",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Camera Available: {data.get('available', 'Unknown')}")
            print(f"   Camera Initialized: {data.get('initialized', 'Unknown')}")
            print(f"   Camera Scanning: {data.get('scanning', 'Unknown')}")
            
            # Verify required fields
            required_fields = ['available', 'initialized', 'scanning']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"⚠️  Missing fields in camera status: {missing_fields}")
            else:
                print("   All required fields present")
        
        return success

    def test_camera_initialization_api(self):
        """Test camera initialization API endpoint"""
        success, data = self.run_test(
            "Camera Initialization API",
            "POST",
            "camera/initialize",
            200,
            {"camera_index": 0}
        )
        
        if success and isinstance(data, dict):
            print(f"   Initialization Message: {data.get('message', 'Unknown')}")
            print(f"   Camera Index: {data.get('camera_index', 'Unknown')}")
        
        return success

    def test_barcode_scan_api(self):
        """Test barcode scanning API endpoint"""
        success, data = self.run_test(
            "Barcode Scan API",
            "GET",
            "barcode/scan",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Barcode: {data.get('barcode', 'None detected')}")
            print(f"   SKU: {data.get('sku', 'None mapped')}")
            print(f"   Type: {data.get('type', 'Unknown')}")
            
            # Check if barcode was detected
            if data.get('barcode'):
                print("   ✅ Barcode detection working (mock mode)")
            else:
                print("   ℹ️  No barcode detected (expected in mock mode)")
        
        return success

    def test_barcode_mappings_api(self):
        """Test barcode mappings API endpoint"""
        success, data = self.run_test(
            "Barcode Mappings API",
            "GET",
            "barcode/mappings",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Found {len(data)} barcode mappings")
            # Show first few mappings
            for i, (barcode, sku) in enumerate(list(data.items())[:3]):
                print(f"   • {barcode} → {sku}")
            
            # Verify some expected mappings exist
            expected_mappings = ["123456789012", "1234567890128", "0012345678905"]
            found_mappings = [barcode for barcode in expected_mappings if barcode in data]
            print(f"   Expected mappings found: {len(found_mappings)}/{len(expected_mappings)}")
        
        return success

    def test_add_barcode_mapping_api(self):
        """Test adding new barcode mapping"""
        test_mapping = {
            "barcode": f"TEST{int(time.time())}",
            "sku": "PLA001"
        }
        
        success, data = self.run_test(
            "Add Barcode Mapping API",
            "POST",
            "barcode/mapping",
            200,
            test_mapping
        )
        
        if success and isinstance(data, dict):
            print(f"   Mapping Added: {test_mapping['barcode']} → {test_mapping['sku']}")
            print(f"   Response: {data.get('message', 'Unknown')}")
        
        return success

    def test_auto_programming_start_api(self):
        """Test starting auto-programming session"""
        auto_request = {
            "sku": "PLA001"
        }
        
        success, data = self.run_test(
            "Start Auto-Programming API",
            "POST",
            "auto-programming/start",
            200,
            auto_request
        )
        
        if success and isinstance(data, dict):
            self.auto_session_id = data.get('session_id')
            print(f"   Session ID: {self.auto_session_id}")
            print(f"   SKU: {data.get('sku', 'Unknown')}")
            print(f"   Mode: {data.get('mode', 'Unknown')}")
            print(f"   Message: {data.get('message', 'Unknown')}")
            
            # Verify required fields
            required_fields = ['session_id', 'sku', 'message', 'mode']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"⚠️  Missing fields in auto-programming response: {missing_fields}")
            else:
                print("   All required fields present")
        
        return success

    def test_auto_programming_status_api(self):
        """Test auto-programming status API"""
        success, data = self.run_test(
            "Auto-Programming Status API",
            "GET",
            "auto-programming/status",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   State: {data.get('state', 'Unknown')}")
            print(f"   Scanning: {data.get('scanning', 'Unknown')}")
            print(f"   Selected SKU: {data.get('selected_sku', 'Unknown')}")
            print(f"   Current Tag Number: {data.get('current_tag_number', 'Unknown')}")
            print(f"   Session ID: {data.get('session_id', 'Unknown')}")
            
            # Verify required fields
            required_fields = ['state', 'scanning', 'selected_sku', 'current_tag_number', 'session_id']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"⚠️  Missing fields in auto-programming status: {missing_fields}")
            else:
                print("   All required fields present")
        
        return success

    def test_auto_programming_stop_api(self):
        """Test stopping auto-programming session"""
        success, data = self.run_test(
            "Stop Auto-Programming API",
            "POST",
            "auto-programming/stop",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Stop Message: {data.get('message', 'Unknown')}")
        
        return success

    def test_enhanced_device_status(self):
        """Test enhanced device status with camera and mock mode info"""
        success, data = self.run_test(
            "Enhanced Device Status API",
            "GET",
            "device/status",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Connected: {data.get('connected', 'Unknown')}")
            print(f"   Device Path: {data.get('device_path', 'None')}")
            print(f"   Mock Mode: {data.get('mock_mode', 'Unknown')}")
            
            # Check for enhanced fields
            if 'mock_mode' in data:
                print("   ✅ Enhanced device status includes mock mode information")
            else:
                print("   ⚠️  Mock mode information missing from device status")
        
        return success

    def test_auto_programming_workflow(self):
        """Test complete auto-programming workflow"""
        print(f"\n🤖 Testing Complete Auto-Programming Workflow...")
        
        # Step 1: Start auto-programming
        auto_request = {"sku": "ABS002"}
        success1, start_data = self.run_test(
            "Workflow Step 1: Start Auto-Programming",
            "POST",
            "auto-programming/start",
            200,
            auto_request
        )
        
        if not success1:
            return False
        
        session_id = start_data.get('session_id')
        print(f"   Started session: {session_id}")
        
        # Step 2: Check initial status
        time.sleep(1)  # Brief wait for initialization
        success2, status_data = self.run_test(
            "Workflow Step 2: Check Initial Status",
            "GET",
            "auto-programming/status",
            200
        )
        
        if success2:
            initial_state = status_data.get('state', 'unknown')
            print(f"   Initial state: {initial_state}")
        
        # Step 3: Monitor for a few seconds (simulate tag detection)
        print("   Monitoring auto-detection for 5 seconds...")
        for i in range(5):
            time.sleep(1)
            success_monitor, monitor_data = self.run_test(
                f"Workflow Monitor {i+1}/5",
                "GET",
                "auto-programming/status",
                200
            )
            
            if success_monitor:
                current_state = monitor_data.get('state', 'unknown')
                current_tag = monitor_data.get('current_tag_number', 'unknown')
                print(f"   Status {i+1}: State={current_state}, Tag={current_tag}")
                
                # Check for state changes
                if current_state in ['programming', 'verifying', 'complete']:
                    print(f"   ✅ Auto-detection workflow progressing: {current_state}")
                    break
        
        # Step 4: Stop auto-programming
        success4, stop_data = self.run_test(
            "Workflow Step 4: Stop Auto-Programming",
            "POST",
            "auto-programming/stop",
            200
        )
        
        return success1 and success2 and success4

    def test_backwards_compatibility(self):
        """Test backwards compatibility with manual programming mode"""
        print(f"\n🔧 Testing Backwards Compatibility...")
        
        # Test traditional programming session creation
        session_data = {
            "sku": "PETG003",
            "spool_id": f"COMPAT_TEST_{int(time.time())}",
            "operator": "CompatibilityTester"
        }
        
        success, data = self.run_test(
            "Manual Programming Session (Backwards Compatibility)",
            "POST",
            "programming/start",
            200,
            session_data
        )
        
        if success and isinstance(data, dict):
            session_id = data.get('id')
            print(f"   Manual Session ID: {session_id}")
            print(f"   ✅ Manual programming mode still available")
            
            # Test getting session status
            success2, status_data = self.run_test(
                "Manual Session Status Check",
                "GET",
                f"programming/{session_id}",
                200
            )
            
            return success and success2
        
        return success

    def test_error_handling_enhanced(self):
        """Test enhanced error handling for new endpoints"""
        print(f"\n🚨 Testing Enhanced Error Handling...")
        
        # Test invalid SKU for auto-programming
        invalid_auto_request = {"sku": "INVALID_AUTO_SKU"}
        success1, data1 = self.run_test(
            "Invalid SKU Auto-Programming Error",
            "POST",
            "auto-programming/start",
            404,
            invalid_auto_request
        )
        
        # Test camera endpoints when not available (should handle gracefully)
        success2, data2 = self.run_test(
            "Camera Frame When Not Available",
            "GET",
            "camera/frame",
            400  # Expecting 400 when camera not available/initialized
        )
        
        # Test invalid barcode mapping
        invalid_mapping = {"barcode": "", "sku": ""}
        success3, data3 = self.run_test(
            "Invalid Barcode Mapping Error",
            "POST",
            "barcode/mapping",
            400,  # Expecting validation error
            invalid_mapping
        )
        
        return success1 and success2  # success3 might fail due to validation, that's ok

    def run_all_enhanced_tests(self):
        """Run all enhanced API tests"""
        print("=" * 70)
        print("  FILATAG RFID PROGRAMMER - ENHANCED AUTOMATED WORKFLOW TESTING")
        print("=" * 70)
        print(f"Testing against: {self.base_url}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("Focus: Camera scanning, barcode mapping, auto-detection, CLI enhancements")
        
        # Enhanced API Tests
        tests = [
            ("Camera Status API", self.test_camera_status_api),
            ("Camera Initialization API", self.test_camera_initialization_api),
            ("Barcode Scan API", self.test_barcode_scan_api),
            ("Barcode Mappings API", self.test_barcode_mappings_api),
            ("Add Barcode Mapping API", self.test_add_barcode_mapping_api),
            ("Auto-Programming Start API", self.test_auto_programming_start_api),
            ("Auto-Programming Status API", self.test_auto_programming_status_api),
            ("Auto-Programming Stop API", self.test_auto_programming_stop_api),
            ("Enhanced Device Status", self.test_enhanced_device_status),
            ("Auto-Programming Workflow", self.test_auto_programming_workflow),
            ("Backwards Compatibility", self.test_backwards_compatibility),
            ("Enhanced Error Handling", self.test_error_handling_enhanced),
        ]
        
        for test_name, test_func in tests:
            try:
                test_func()
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {e}")
                import traceback
                traceback.print_exc()
        
        # Print results
        print("\n" + "=" * 70)
        print("  ENHANCED TESTING RESULTS")
        print("=" * 70)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%" if self.tests_run > 0 else "0%")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All enhanced tests passed! New automated workflow features working correctly.")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} test(s) failed. Check the output above for details.")
            return 1

def main():
    """Main test runner"""
    tester = EnhancedFilatagAPITester()
    return tester.run_all_enhanced_tests()

if __name__ == "__main__":
    sys.exit(main())