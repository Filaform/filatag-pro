#!/usr/bin/env python3
"""
Extended Backend API Testing for Filatag RFID Programmer
Tests additional endpoints like camera, barcode scanning, auto-detection, and logs clearing
"""

import requests
import sys
import json
import time
from datetime import datetime

class ExtendedFilatagAPITester:
    def __init__(self, base_url="https://mifare-writer.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=10):
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
                print(f"   Response: {response.text[:200]}...")
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
            "Get Camera Status",
            "GET",
            "camera/status",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Available: {data.get('available', 'Unknown')}")
            print(f"   Initialized: {data.get('initialized', 'Unknown')}")
            print(f"   Scanning: {data.get('scanning', 'Unknown')}")
            
            # Verify required fields
            required_fields = ['available', 'initialized', 'scanning']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"⚠️  Missing fields in camera status: {missing_fields}")
            else:
                print("   All required fields present")
        
        return success

    def test_barcode_scan_api(self):
        """Test barcode scanning API endpoint"""
        success, data = self.run_test(
            "Scan Barcode",
            "GET",
            "barcode/scan",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Barcode: {data.get('barcode', 'None')}")
            print(f"   SKU: {data.get('sku', 'None')}")
            
            # This endpoint should return barcode and sku fields even if null
            expected_fields = ['barcode', 'sku']
            missing_fields = [field for field in expected_fields if field not in data]
            if missing_fields:
                print(f"⚠️  Missing fields in barcode scan: {missing_fields}")
            else:
                print("   All expected fields present")
        
        return success

    def test_barcode_mappings_api(self):
        """Test barcode mappings API endpoint"""
        success, data = self.run_test(
            "Get Barcode Mappings",
            "GET",
            "barcode/mappings",
            200
        )
        
        if success:
            print(f"   Mappings type: {type(data)}")
            if isinstance(data, dict):
                print(f"   Number of mappings: {len(data)}")
            else:
                print(f"   Mappings data: {data}")
        
        return success

    def test_auto_programming_status_api(self):
        """Test auto-programming status API endpoint"""
        success, data = self.run_test(
            "Get Auto-Programming Status",
            "GET",
            "auto-programming/status",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Status data keys: {list(data.keys())}")
            # Print some status information if available
            for key, value in data.items():
                print(f"   {key}: {value}")
        
        return success

    def test_logs_clear_api(self):
        """Test logs clearing API endpoint"""
        success, data = self.run_test(
            "Clear Logs",
            "POST",
            "logs/clear",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Message: {data.get('message', 'Unknown')}")
            if 'backup' in data:
                print(f"   Backup created: {data.get('backup', 'Unknown')}")
        
        return success

    def test_config_update_api(self):
        """Test configuration update API endpoint"""
        # Test updating configuration
        test_config = {
            "test_setting": "test_value",
            "mock_mode": True
        }
        
        success, data = self.run_test(
            "Update Configuration",
            "POST",
            "config",
            200,
            test_config
        )
        
        if success and isinstance(data, dict):
            print(f"   Updated config contains test_setting: {'test_setting' in data}")
            print(f"   Mock mode: {data.get('mock_mode', 'Unknown')}")
        
        return success

    def test_auto_programming_start_stop(self):
        """Test auto-programming start/stop endpoints"""
        # Test starting auto-programming
        auto_request = {
            "sku": "PLA001"
        }
        
        success1, data1 = self.run_test(
            "Start Auto-Programming",
            "POST",
            "auto-programming/start",
            200,
            auto_request
        )
        
        if success1 and isinstance(data1, dict):
            print(f"   Session ID: {data1.get('session_id', 'Unknown')}")
            print(f"   SKU: {data1.get('sku', 'Unknown')}")
            print(f"   Mode: {data1.get('mode', 'Unknown')}")
        
        # Test stopping auto-programming
        success2, data2 = self.run_test(
            "Stop Auto-Programming",
            "POST",
            "auto-programming/stop",
            200
        )
        
        if success2 and isinstance(data2, dict):
            print(f"   Stop message: {data2.get('message', 'Unknown')}")
        
        return success1 and success2

    def run_extended_tests(self):
        """Run all extended API tests"""
        print("=" * 60)
        print("  FILATAG RFID PROGRAMMER - EXTENDED BACKEND API TESTING")
        print("=" * 60)
        print(f"Testing against: {self.base_url}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Extended API Tests
        tests = [
            ("Camera Status API", self.test_camera_status_api),
            ("Barcode Scan API", self.test_barcode_scan_api),
            ("Barcode Mappings API", self.test_barcode_mappings_api),
            ("Auto-Programming Status API", self.test_auto_programming_status_api),
            ("Logs Clear API", self.test_logs_clear_api),
            ("Config Update API", self.test_config_update_api),
            ("Auto-Programming Start/Stop", self.test_auto_programming_start_stop),
        ]
        
        for test_name, test_func in tests:
            try:
                test_func()
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {e}")
        
        # Print results
        print("\n" + "=" * 60)
        print("  EXTENDED TEST RESULTS")
        print("=" * 60)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%" if self.tests_run > 0 else "0%")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All extended tests passed! All backend APIs are working correctly.")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} extended test(s) failed. Check the output above for details.")
            return 1

def main():
    """Main test runner"""
    tester = ExtendedFilatagAPITester()
    return tester.run_extended_tests()

if __name__ == "__main__":
    sys.exit(main())