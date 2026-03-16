#!/usr/bin/env python3
"""
Unit tests for the Credential Manager module.
"""

import sys
import os
import tempfile
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.credential_manager import CredentialManager
import lib.credential_manager as credential_manager_module

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

def test_authentication_without_store_fails():
    """authenticate() should not initialize a new store implicitly."""
    temp_file = os.path.join(tempfile.gettempdir(), "microscan-missing-credentials.encrypted")
    if os.path.exists(temp_file):
        os.unlink(temp_file)

    cred_manager = CredentialManager(temp_file)
    assert cred_manager.authenticate("testmasterpassword") == False
    print("✓ Missing-store authentication test passed")

def test_prepare_for_storage_preserves_existing_credentials():
    """prepare_for_storage() should unlock and append to an existing store."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.encrypted') as f:
        temp_file = f.name

    try:
        cred_manager = CredentialManager(temp_file)
        assert cred_manager.prepare_for_storage("testmasterpassword") == True
        assert cred_manager.store_credentials("192.168.1.1", "admin", "password123") == True

        new_cred_manager = CredentialManager(temp_file)
        assert new_cred_manager.prepare_for_storage("testmasterpassword") == True
        assert new_cred_manager.store_credentials("192.168.1.2", "admin2", "password456") == True

        verify_manager = CredentialManager(temp_file)
        assert verify_manager.authenticate("testmasterpassword") == True
        assert verify_manager.retrieve_credentials("192.168.1.1")["password"] == "password123"
        assert verify_manager.retrieve_credentials("192.168.1.2")["password"] == "password456"
        print("✓ Existing-store append test passed")
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_prepare_for_storage_treats_truncated_store_as_new():
    """prepare_for_storage() should not authenticate a truncated store."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.encrypted') as f:
        temp_file = f.name

    try:
        with open(temp_file, "wb") as handle:
            handle.write(b"short")

        cred_manager = CredentialManager(temp_file)

        with patch.object(
            cred_manager,
            "authenticate",
            side_effect=AssertionError("authenticate should not be called"),
        ):
            assert cred_manager.prepare_for_storage("testmasterpassword") == True
            assert cred_manager.cipher_suite is not None
        print("✓ Truncated-store prepare_for_storage test passed")
    finally:
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_store_action_uses_prepare_for_storage():
    """The CLI store action should initialize a new store via prepare_for_storage()."""
    with patch.object(sys, "argv", [
        "credential_manager.py",
        "store",
        "--hostname",
        "192.168.1.1",
        "--username",
        "admin",
        "--password",
        "password123",
    ]), patch.object(
        credential_manager_module.CredentialManager,
        "prepare_for_storage",
        return_value=True,
    ) as prepare_mock, patch.object(
        credential_manager_module.CredentialManager,
        "authenticate",
        side_effect=AssertionError("authenticate should not be used for store"),
    ), patch.object(
        credential_manager_module.CredentialManager,
        "store_credentials",
        return_value=True,
    ) as store_mock:
        credential_manager_module.main()

    prepare_mock.assert_called_once_with()
    store_mock.assert_called_once_with(
        "192.168.1.1",
        "admin",
        "password123",
        None,
    )
    print("✓ Store action prepare_for_storage test passed")

def main():
    """Run all credential manager tests."""
    print("Running Credential Manager Tests...")
    
    try:
        test_credential_manager_initialization()
        test_derive_key()
        test_store_and_retrieve_credentials()
        test_authentication()
        test_authentication_without_store_fails()
        test_prepare_for_storage_preserves_existing_credentials()
        test_prepare_for_storage_treats_truncated_store_as_new()
        test_store_action_uses_prepare_for_storage()
        
        print("\nAll Credential Manager tests passed! ✓")
        return 0
    except Exception as e:
        print(f"\nCredential Manager test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
