#!/usr/bin/env python3
"""
Credential Manager for Mikrotik Mapper.
Handles encryption and decryption of SSH credentials using a master password.
"""

import base64
import getpass
import hashlib
import json
import logging
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CredentialManager:
    """Manages encrypted storage and retrieval of SSH credentials."""
    
    def __init__(self, credentials_file: str = "data/credentials.encrypted"):
        """
        Initialize the credential manager.
        
        Args:
            credentials_file (str): File to store encrypted credentials
        """
        self.credentials_file = credentials_file
        self.master_key = None
        self.cipher_suite = None
    
    def _derive_key(self, master_password: str, salt: bytes) -> bytes:
        """
        Derive encryption key from master password and salt.
        
        Args:
            master_password (str): Master password
            salt (bytes): Salt for key derivation
            
        Returns:
            bytes: Derived encryption key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))
        return key
    
    def set_master_password(self, master_password: str = None) -> bool:
        """
        Set the master password and initialize encryption.
        
        Args:
            master_password (str, optional): Master password. If not provided, will prompt.
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not master_password:
            master_password = getpass.getpass("Enter master password for credential storage: ")
            confirm_password = getpass.getpass("Confirm master password: ")
            
            if master_password != confirm_password:
                logger.error("Passwords do not match")
                return False
        
        # Generate salt for key derivation
        salt = os.urandom(16)
        
        # Derive key from password
        key = self._derive_key(master_password, salt)
        
        # Create cipher suite
        self.cipher_suite = Fernet(key)
        self.master_key = key
        
        logger.info("Master password set successfully")
        return True
    
    def authenticate(self, master_password: str = None) -> bool:
        """
        Authenticate with master password to access credentials.
        
        Args:
            master_password (str, optional): Master password. If not provided, will prompt.
            
        Returns:
            bool: True if authentication successful, False otherwise
        """
        if not os.path.exists(self.credentials_file):
            logger.info("No existing credentials file found")
            return self.set_master_password(master_password)
        
        if not master_password:
            master_password = getpass.getpass("Enter master password to access credentials: ")
        
        try:
            # Read salt and encrypted data
            with open(self.credentials_file, 'rb') as f:
                salt = f.read(16)
                encrypted_data = f.read()
            
            # Derive key from password
            key = self._derive_key(master_password, salt)
            
            # Test decryption
            cipher_suite = Fernet(key)
            cipher_suite.decrypt(encrypted_data)
            
            # If we get here, password is correct
            self.master_key = key
            self.cipher_suite = cipher_suite
            logger.info("Authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def store_credentials(self, hostname: str, username: str, password: str = None, 
                         key_file: str = None) -> bool:
        """
        Store SSH credentials for a specific host.
        
        Args:
            hostname (str): Hostname or IP address
            username (str): SSH username
            password (str, optional): SSH password
            key_file (str, optional): Path to private key file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.cipher_suite:
            logger.error("Master password not set. Call set_master_password() first.")
            return False
        
        # Load existing credentials
        credentials = self.load_all_credentials()
        
        # Prepare credential data
        cred_data = {
            "username": username,
            "password": password,
            "key_file": key_file
        }
        
        # Encrypt credential data
        try:
            cred_json = json.dumps(cred_data)
            encrypted_cred = self.cipher_suite.encrypt(cred_json.encode())
            credentials[hostname] = base64.b64encode(encrypted_cred).decode()
            
            # Save all credentials
            self._save_encrypted_credentials(credentials)
            logger.info(f"Credentials for {hostname} stored successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store credentials for {hostname}: {e}")
            return False
    
    def store_default_credentials(self, username: str, password: str = None, 
                                 key_file: str = None) -> bool:
        """
        Store default SSH credentials for all hosts.
        
        Args:
            username (str): SSH username
            password (str, optional): SSH password
            key_file (str, optional): Path to private key file
            
        Returns:
            bool: True if successful, False otherwise
        """
        return self.store_credentials("__default__", username, password, key_file)
    
    def retrieve_credentials(self, hostname: str) -> dict:
        """
        Retrieve SSH credentials for a specific host.
        Falls back to default credentials if host-specific credentials not found.
        
        Args:
            hostname (str): Hostname or IP address
            
        Returns:
            dict: Credential data with username, password, and key_file
        """
        if not self.cipher_suite:
            logger.error("Master password not set. Call authenticate() first.")
            return {}
        
        # Load all credentials
        credentials = self.load_all_credentials()
        
        # Check for host-specific credentials first
        if hostname in credentials:
            try:
                # Decrypt credential data
                encrypted_cred = base64.b64decode(credentials[hostname])
                decrypted_cred = self.cipher_suite.decrypt(encrypted_cred)
                cred_data = json.loads(decrypted_cred.decode())
                
                logger.debug(f"Host-specific credentials for {hostname} retrieved successfully")
                return cred_data
                
            except Exception as e:
                logger.error(f"Failed to retrieve credentials for {hostname}: {e}")
                return {}
        
        # Fall back to default credentials
        if "__default__" in credentials:
            try:
                # Decrypt default credential data
                encrypted_cred = base64.b64decode(credentials["__default__"])
                decrypted_cred = self.cipher_suite.decrypt(encrypted_cred)
                cred_data = json.loads(decrypted_cred.decode())
                
                logger.debug(f"Default credentials retrieved for {hostname}")
                return cred_data
                
            except Exception as e:
                logger.error(f"Failed to retrieve default credentials: {e}")
        
        logger.warning(f"No credentials found for {hostname}")
        return {}
    
    def load_all_credentials(self) -> dict:
        """
        Load all encrypted credentials from file.
        
        Returns:
            dict: Dictionary of encrypted credentials
        """
        if not os.path.exists(self.credentials_file):
            return {}
        
        try:
            with open(self.credentials_file, 'rb') as f:
                salt = f.read(16)
                encrypted_data = f.read()
            
            if not encrypted_data:
                return {}
            
            # Decrypt data
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode())
            
            return credentials
            
        except Exception as e:
            logger.error(f"Failed to load credentials: {e}")
            return {}
    
    def _save_encrypted_credentials(self, credentials: dict):
        """
        Save encrypted credentials to file.
        
        Args:
            credentials (dict): Dictionary of encrypted credentials
        """
        if not self.cipher_suite:
            raise Exception("Master password not set")
        
        try:
            # Generate new salt for this save operation
            salt = os.urandom(16)
            
            # Encrypt credentials data
            cred_json = json.dumps(credentials)
            encrypted_data = self.cipher_suite.encrypt(cred_json.encode())
            
            # Write salt and encrypted data
            with open(self.credentials_file, 'wb') as f:
                f.write(salt)
                f.write(encrypted_data)
                
        except Exception as e:
            logger.error(f"Failed to save credentials: {e}")
            raise

def main():
    """Example usage of the CredentialManager."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Credential Manager for Mikrotik Mapper")
    parser.add_argument("action", choices=["store", "retrieve"], help="Action to perform")
    parser.add_argument("--hostname", help="Hostname or IP address")
    parser.add_argument("--username", help="SSH username")
    parser.add_argument("--password", help="SSH password")
    parser.add_argument("--key-file", help="Path to private key file")
    
    args = parser.parse_args()
    
    # Create credential manager
    cred_manager = CredentialManager()
    
    if args.action == "store":
        if not args.hostname or not args.username:
            print("Hostname and username required for storing credentials")
            return
        
        # Authenticate first
        if not cred_manager.authenticate():
            print("Authentication failed")
            return
        
        # Store credentials
        if cred_manager.store_credentials(args.hostname, args.username, args.password, args.key_file):
            print(f"Credentials for {args.hostname} stored successfully")
        else:
            print(f"Failed to store credentials for {args.hostname}")
    
    elif args.action == "retrieve":
        if not args.hostname:
            print("Hostname required for retrieving credentials")
            return
        
        # Authenticate first
        if not cred_manager.authenticate():
            print("Authentication failed")
            return
        
        # Retrieve credentials
        credentials = cred_manager.retrieve_credentials(args.hostname)
        if credentials:
            print(f"Credentials for {args.hostname}:")
            print(f"  Username: {credentials['username']}")
            print(f"  Password: {'*' * len(credentials.get('password', '')) if credentials.get('password') else 'None'}")
            print(f"  Key File: {credentials.get('key_file', 'None')}")
        else:
            print(f"No credentials found for {args.hostname}")

if __name__ == "__main__":
    main()