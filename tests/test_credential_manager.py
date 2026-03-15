#!/usr/bin/env python3
"""
Unit tests for the Credential Manager module.
"""

import sys
import os
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from credential_manager import CredentialManager

def test_credential_manager_initialization():
    """Test CredentialManager initialization."""
    # Create temporary file for testing
    with tempfile.NamedTemporaryFile(delete=False, suffix='.encrypted') as f:
        temp_file = f.name
    
    try:
        cred_manager = CredentialManager(temp_file)
        
        assert cred_manager.credentials_file == temp_file
        assert cred_manager.master_key is None
        assert cred_manager.cipher_suite is None
        print("✓ CredentialManager initialization test passed")
        
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def test_derive_key():
    """Test key derivation (private method)."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.encrypted') as f:
        temp_file = f.name
    
    try:
        cred_manager = CredentialManager(temp_file)
        
        # Test key derivation
        salt = os.urandom(16)
        key = cred_manager._derive_key("testpassword", salt)
        
        assert len(key) == 44  # Base64 encoded 32-byte key
        print("✓ Key derivation test passed")
        
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def test_store_and_retrieve_credentials():
    """Test storing and retrieving credentials."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.encrypted') as f:
        temp_file = f.name
    
    try:
        cred_manager = CredentialManager(temp_file)
        
        # Set master password
        result = cred_manager.set_master_password("testmasterpassword")
        assert result == True
        
        # Store credentials
        result = cred_manager.store_credentials(
            "192.168.1.1", 
            "admin", 
            "password123", 
            "/path/to/key"
        )
        assert result == True
        
        # Retrieve credentials
        credentials = cred_manager.retrieve_credentials("192.168.1.1")
        assert credentials["username"] == "admin"
        assert credentials["password"] == "password123"
        assert credentials["key_file"] == "/path/to/key"
        print("✓ Store and retrieve credentials test passed")
        
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def test_authentication():
    """Test authentication with master password."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.encrypted') as f:
        temp_file = f.name
    
    try:
        cred_manager = CredentialManager(temp_file)
        
        # Set master password and store credentials
        cred_manager.set_master_password("testmasterpassword")
        cred_manager.store_credentials("192.168.1.1", "admin", "password123")
        
        # Create new credential manager instance
        new_cred_manager = CredentialManager(temp_file)
        
        # Authenticate with correct password
        result = new_cred_manager.authenticate("testmasterpassword")
        assert result == True
        
        # Verify we can retrieve credentials
        credentials = new_cred_manager.retrieve_credentials("192.168.1.1")
        assert credentials["username"] == "admin"
        print("✓ Authentication test passed")
        
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def main():
    """Run all credential manager tests."""
    print("Running Credential Manager Tests...")
    
    try:
        test_credential_manager_initialization()
        test_derive_key()
        test_store_and_retrieve_credentials()
        test_authentication()
        
        print("\nAll Credential Manager tests passed! ✓")
        return 0
    except Exception as e:
        print(f"\nCredential Manager test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())