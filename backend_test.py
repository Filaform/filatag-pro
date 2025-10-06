#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Filatag RFID Programmer
Tests all API endpoints and functionality in mock mode
"""

import requests
import sys
import json
import time
from datetime import datetime

class FilatagAPITester:
    def __init__(self, base_url="https://mifare-writer.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.session_id = None

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

    def test_filaments_api(self):
        """Test filaments API endpoint"""
        success, data = self.run_test(
            "Get Filaments List",
            "GET",
            "filaments",
            200
        )
        
        if success and isinstance(data, list):
            print(f"   Found {len(data)} filaments")
            for filament in data[:3]:  # Show first 3
                print(f"   • {filament.get('sku', 'Unknown')}: {filament.get('name', 'Unknown')}")
            
            # Verify required fields
            if data:
                required_fields = ['sku', 'name', 'description', 'binary_file']
                first_filament = data[0]
                missing_fields = [field for field in required_fields if field not in first_filament]
                if missing_fields:
                    print(f"⚠️  Missing fields in filament data: {missing_fields}")
                else:
                    print("   All required fields present")
        
        return success

    def test_device_status_api(self):
        """Test device status API endpoint"""
        success, data = self.run_test(
            "Get Device Status",
            "GET",
            "device/status",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Connected: {data.get('connected', 'Unknown')}")
            print(f"   Device Path: {data.get('device_path', 'None')}")
            print(f"   Mock Mode: {data.get('mock_mode', 'Unknown')}")
            
            # Verify required fields
            required_fields = ['connected', 'device_path', 'output', 'mock_mode']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"⚠️  Missing fields in device status: {missing_fields}")
            else:
                print("   All required fields present")
        
        return success

    def test_config_api(self):
        """Test configuration API endpoints"""
        # Test GET config
        success, data = self.run_test(
            "Get Configuration",
            "GET",
            "config",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Mock Mode: {data.get('mock_mode', 'Unknown')}")
            print(f"   Retries: {data.get('retries', 'Unknown')}")
            print(f"   Strict Verification: {data.get('strict_verification', 'Unknown')}")
        
        return success

    def test_logs_api(self):
        """Test logs API endpoint"""
        success, data = self.run_test(
            "Get Logs",
            "GET",
            "logs?limit=10",
            200
        )
        
        if success and isinstance(data, list):
            print(f"   Found {len(data)} log entries")
            if data:
                latest_log = data[-1]
                print(f"   Latest: {latest_log.get('action', 'Unknown')} at {latest_log.get('timestamp', 'Unknown')}")
        
        return success

    def test_programming_session_api(self):
        """Test programming session API endpoints"""
        # Test starting a programming session
        session_data = {
            "sku": "PLA001",
            "spool_id": f"TEST_{int(time.time())}",
            "operator": "APITester"
        }
        
        success, data = self.run_test(
            "Start Programming Session",
            "POST",
            "programming/start",
            200,
            session_data
        )
        
        if success and isinstance(data, dict):
            self.session_id = data.get('id')
            print(f"   Session ID: {self.session_id}")
            print(f"   SKU: {data.get('sku', 'Unknown')}")
            print(f"   Spool ID: {data.get('spool_id', 'Unknown')}")
            print(f"   Tag1 Status: {data.get('tag1_status', 'Unknown')}")
            print(f"   Tag2 Status: {data.get('tag2_status', 'Unknown')}")
            
            # Verify required fields
            required_fields = ['id', 'sku', 'spool_id', 'tag1_status', 'tag2_status', 'started_at']
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                print(f"⚠️  Missing fields in session data: {missing_fields}")
            else:
                print("   All required fields present")
        
        return success

    def test_get_programming_session(self):
        """Test getting programming session status"""
        if not self.session_id:
            print("❌ No session ID available for testing")
            return False
        
        success, data = self.run_test(
            "Get Programming Session Status",
            "GET",
            f"programming/{self.session_id}",
            200
        )
        
        if success and isinstance(data, dict):
            print(f"   Session ID: {data.get('id', 'Unknown')}")
            print(f"   Tag1 Status: {data.get('tag1_status', 'Unknown')}")
            print(f"   Tag2 Status: {data.get('tag2_status', 'Unknown')}")
        
        return success

    def test_program_tag_api(self):
        """Test programming individual tags"""
        if not self.session_id:
            print("❌ No session ID available for testing")
            return False
        
        # Test programming Tag 1
        success1, data1 = self.run_test(
            "Program Tag 1",
            "POST",
            f"programming/{self.session_id}/tag/1",
            200
        )
        
        if success1:
            print("   Tag 1 programming initiated")
            # Wait a moment for background processing
            time.sleep(2)
            
            # Check session status
            success_status, status_data = self.run_test(
                "Check Tag 1 Status",
                "GET",
                f"programming/{self.session_id}",
                200
            )
            
            if success_status:
                tag1_status = status_data.get('tag1_status', 'unknown')
                print(f"   Tag 1 Status after programming: {tag1_status}")
        
        # Test programming Tag 2
        success2, data2 = self.run_test(
            "Program Tag 2",
            "POST",
            f"programming/{self.session_id}/tag/2",
            200
        )
        
        if success2:
            print("   Tag 2 programming initiated")
            # Wait a moment for background processing
            time.sleep(2)
            
            # Check final session status
            success_status, status_data = self.run_test(
                "Check Final Session Status",
                "GET",
                f"programming/{self.session_id}",
                200
            )
            
            if success_status:
                tag1_status = status_data.get('tag1_status', 'unknown')
                tag2_status = status_data.get('tag2_status', 'unknown')
                print(f"   Final Status - Tag 1: {tag1_status}, Tag 2: {tag2_status}")
        
        return success1 and success2

    def test_error_handling(self):
        """Test API error handling"""
        print(f"\n🔍 Testing Error Handling...")
        
        # Test invalid SKU
        invalid_session_data = {
            "sku": "INVALID_SKU",
            "spool_id": "TEST_ERROR",
            "operator": "ErrorTester"
        }
        
        success, data = self.run_test(
            "Invalid SKU Error Handling",
            "POST",
            "programming/start",
            404,  # Expecting 404 for invalid SKU
            invalid_session_data
        )
        
        # Test invalid session ID
        success2, data2 = self.run_test(
            "Invalid Session ID Error Handling",
            "GET",
            "programming/invalid-session-id",
            404  # Expecting 404 for invalid session
        )
        
        # Test invalid tag number
        if self.session_id:
            success3, data3 = self.run_test(
                "Invalid Tag Number Error Handling",
                "POST",
                f"programming/{self.session_id}/tag/99",
                400  # Expecting 400 for invalid tag number
            )
        else:
            success3 = True  # Skip if no session available
        
        return success and success2 and success3

    def run_all_tests(self):
        """Run all API tests"""
        print("=" * 60)
        print("  FILATAG RFID PROGRAMMER - BACKEND API TESTING")
        print("=" * 60)
        print(f"Testing against: {self.base_url}")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Core API Tests
        tests = [
            ("Filaments API", self.test_filaments_api),
            ("Device Status API", self.test_device_status_api),
            ("Configuration API", self.test_config_api),
            ("Logs API", self.test_logs_api),
            ("Programming Session API", self.test_programming_session_api),
            ("Get Programming Session", self.test_get_programming_session),
            ("Program Tags API", self.test_program_tag_api),
            ("Error Handling", self.test_error_handling),
        ]
        
        for test_name, test_func in tests:
            try:
                test_func()
            except Exception as e:
                print(f"❌ {test_name} failed with exception: {e}")
        
        # Print results
        print("\n" + "=" * 60)
        print("  TEST RESULTS")
        print("=" * 60)
        print(f"Tests Run: {self.tests_run}")
        print(f"Tests Passed: {self.tests_passed}")
        print(f"Tests Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed / self.tests_run * 100):.1f}%" if self.tests_run > 0 else "0%")
        
        if self.tests_passed == self.tests_run:
            print("\n🎉 All tests passed! Backend API is working correctly.")
            return 0
        else:
            print(f"\n⚠️  {self.tests_run - self.tests_passed} test(s) failed. Check the output above for details.")
            return 1

def main():
    """Main test runner"""
    tester = FilatagAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())