#!/usr/bin/env python3
"""
Test for data directory organization.
"""

import sys
import os
import tempfile
import unittest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from credential_manager import CredentialManager

class TestDataDirectory(unittest.TestCase):
    """Test data directory organization."""
    
    def test_data_directory_exists(self):
        """Test that data directory exists."""
        self.assertTrue(os.path.exists("data"), "Data directory should exist")
        self.assertTrue(os.path.isdir("data"), "Data directory should be a directory")
        print("✓ Data directory exists test passed")
    
    def test_credential_file_in_data_directory(self):
        """Test that credential manager uses data directory."""
        cred_manager = CredentialManager()
        self.assertTrue(cred_manager.credentials_file.startswith("data/"), 
                       "Credential file should be in data directory")
        print("✓ Credential file in data directory test passed")
    
    def test_data_directory_permissions(self):
        """Test that data directory has proper permissions."""
        # Check that we can write to the data directory
        test_file = "data/test_write_permission.tmp"
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            self.assertTrue(os.path.exists(test_file), "Should be able to write to data directory")
            os.remove(test_file)
            print("✓ Data directory permissions test passed")
        except Exception as e:
            self.fail(f"Cannot write to data directory: {e}")

if __name__ == "__main__":
    print("Running Data Directory Tests...")
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDataDirectory)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\nAll data directory tests completed successfully! ✓")
        sys.exit(0)
    else:
        print(f"\n{len(result.failures)} failures, {len(result.errors)} errors")
        sys.exit(1)