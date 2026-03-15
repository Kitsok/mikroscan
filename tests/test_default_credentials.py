#!/usr/bin/env python3
"""
Test for default credential functionality.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from credential_manager import CredentialManager

class TestDefaultCredentials(unittest.TestCase):
    """Test default credential functionality."""
    
    @patch('credential_manager.CredentialManager._save_encrypted_credentials')
    @patch('credential_manager.CredentialManager.load_all_credentials')
    def test_store_default_credentials(self, mock_load, mock_save):
        """Test storing default credentials."""
        # Mock credential manager
        cred_manager = CredentialManager()
        cred_manager.cipher_suite = MagicMock()
        
        # Mock load to return empty dict
        mock_load.return_value = {}
        
        # Mock save to succeed
        mock_save.return_value = None
        
        # Test storing default credentials
        result = cred_manager.store_default_credentials("admin", "password123")
        
        # Verify the call was made
        self.assertTrue(mock_save.called)
        print("✓ Default credentials storage test passed")
    
    @patch('credential_manager.CredentialManager.load_all_credentials')
    def test_retrieve_default_credentials_fallback(self, mock_load):
        """Test retrieving default credentials as fallback."""
        # Mock credential manager
        cred_manager = CredentialManager()
        cred_manager.cipher_suite = MagicMock()
        
        # Mock load to return only default credentials
        mock_load.return_value = {
            "__default__": "encrypted_default_data"
        }
        
        # Mock cipher suite decryption
        mock_decrypted_data = '{"username": "admin", "password": "defaultpass", "key_file": null}'
        cred_manager.cipher_suite.decrypt.return_value = mock_decrypted_data.encode()
        
        # Test retrieving credentials for a host without specific credentials
        result = cred_manager.retrieve_credentials("192.168.1.100")
        
        # Verify default credentials were returned
        self.assertEqual(result["username"], "admin")
        self.assertEqual(result["password"], "defaultpass")
        print("✓ Default credentials fallback test passed")
    
    @patch('credential_manager.CredentialManager.load_all_credentials')
    def test_retrieve_host_specific_over_default(self, mock_load):
        """Test that host-specific credentials take precedence over default."""
        # Mock credential manager
        cred_manager = CredentialManager()
        cred_manager.cipher_suite = MagicMock()
        
        # Mock load to return both host-specific and default credentials
        mock_load.return_value = {
            "192.168.1.100": "encrypted_host_data",
            "__default__": "encrypted_default_data"
        }
        
        # Mock cipher suite decryption for host-specific credentials
        mock_host_decrypted_data = '{"username": "specialuser", "password": "specialpass", "key_file": null}'
        cred_manager.cipher_suite.decrypt.return_value = mock_host_decrypted_data.encode()
        
        # Test retrieving credentials for a host with specific credentials
        result = cred_manager.retrieve_credentials("192.168.1.100")
        
        # Verify host-specific credentials were returned
        self.assertEqual(result["username"], "specialuser")
        self.assertEqual(result["password"], "specialpass")
        print("✓ Host-specific credentials precedence test passed")

if __name__ == "__main__":
    print("Running Default Credential Tests...")
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDefaultCredentials)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\nAll default credential tests completed successfully! ✓")
        sys.exit(0)
    else:
        print(f"\n{len(result.failures)} failures, {len(result.errors)} errors")
        sys.exit(1)