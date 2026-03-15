#!/usr/bin/env python3
"""
Test runner for Mikrotik Network Mapper.
Prompts user for passwords and runs all tests.
"""

import getpass
import subprocess
import sys
import os

def run_test_script(script_name, description):
    """Run a test script and report results."""
    print(f"\nRunning {description}...")
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            print(f"  ✓ {description} PASSED")
            return True
        else:
            print(f"  ✗ {description} FAILED")
            print(f"    Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"  ✗ {description} TIMED OUT")
        return False
    except Exception as e:
        print(f"  ✗ {description} ERROR: {e}")
        return False

def main():
    """Main test runner."""
    print("Mikrotik Network Mapper - Test Suite")
    print("=" * 40)
    
    # Change to project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    # Prompt for test credentials
    print("\nPlease provide test credentials for Mikrotik devices:")
    test_hostname = input("Test device hostname/IP (leave blank to skip integration tests): ").strip()
    
    if test_hostname:
        test_username = input("SSH Username: ").strip()
        test_password = getpass.getpass("SSH Password: ")
        master_password = getpass.getpass("Master Password for credential storage: ")
        confirm_master = getpass.getpass("Confirm Master Password: ")
        
        if master_password != confirm_master:
            print("Master passwords do not match!")
            return 1
        
        # Set environment variables for tests
        os.environ['TEST_HOSTNAME'] = test_hostname
        os.environ['TEST_USERNAME'] = test_username
        os.environ['TEST_PASSWORD'] = test_password
        os.environ['MASTER_PASSWORD'] = master_password
    
    # Run unit tests
    test_files = [
        ("tests/test_scanner.py", "Network Scanner Tests"),
        ("tests/test_ssh.py", "SSH Connection Tests"),
        ("tests/test_data_collector.py", "Data Collector Tests"),
        ("tests/test_mapping.py", "Connection Mapper Tests"),
        ("tests/test_credential_manager.py", "Credential Manager Tests")
    ]
    
    passed = 0
    total = 0
    
    for test_file, description in test_files:
        if os.path.exists(test_file):
            total += 1
            if run_test_script(test_file, description):
                passed += 1
    
    # Run integration tests if credentials provided
    if test_hostname and os.path.exists("tests/test_integration.py"):
        total += 1
        if run_test_script("tests/test_integration.py", "Integration Tests"):
            passed += 1
    
    # Summary
    print("\n" + "=" * 40)
    print(f"Test Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("All tests passed! ✓")
        return 0
    else:
        print("Some tests failed! ✗")
        return 1

if __name__ == "__main__":
    sys.exit(main())