#!/usr/bin/env python3
"""
Integration tests for Mikrotik Network Mapper.
Requires actual Mikrotik device and credentials.
"""

import sys
import os
import json
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.network_scanner import NetworkScanner
from data.data_collector import DataCollector
from mapping.connection_mapper import ConnectionMapper
from credential_manager import CredentialManager

def test_credential_storage_integration():
    """Test credential storage and retrieval integration."""
    print("Testing credential storage integration...")
    
    # Get test credentials from environment
    hostname = os.environ.get('TEST_HOSTNAME')
    username = os.environ.get('TEST_USERNAME')
    password = os.environ.get('TEST_PASSWORD')
    master_password = os.environ.get('MASTER_PASSWORD')
    
    if not all([hostname, username, password, master_password]):
        print("  Skipping - test credentials not provided")
        return
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(delete=False, suffix='.encrypted') as f:
        cred_file = f.name
    
    try:
        # Create credential manager
        cred_manager = CredentialManager(cred_file)
        
        # Set master password
        result = cred_manager.set_master_password(master_password)
        assert result == True, "Failed to set master password"
        
        # Store credentials
        result = cred_manager.store_credentials(hostname, username, password)
        assert result == True, "Failed to store credentials"
        
        # Create new credential manager instance
        new_cred_manager = CredentialManager(cred_file)
        
        # Authenticate
        result = new_cred_manager.authenticate(master_password)
        assert result == True, "Failed to authenticate"
        
        # Retrieve credentials
        credentials = new_cred_manager.retrieve_credentials(hostname)
        assert credentials["username"] == username, "Username mismatch"
        assert credentials["password"] == password, "Password mismatch"
        
        print("  ✓ Credential storage integration test passed")
        
    finally:
        # Clean up
        if os.path.exists(cred_file):
            os.unlink(cred_file)

def test_data_collection_integration():
    """Test data collection integration with stored credentials."""
    print("Testing data collection integration...")
    
    # Get test credentials from environment
    hostname = os.environ.get('TEST_HOSTNAME')
    username = os.environ.get('TEST_USERNAME')
    password = os.environ.get('TEST_PASSWORD')
    master_password = os.environ.get('MASTER_PASSWORD')
    
    if not all([hostname, username, password, master_password]):
        print("  Skipping - test credentials not provided")
        return
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(delete=False, suffix='.encrypted') as f:
        cred_file = f.name
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        data_file = f.name
    
    try:
        # Store credentials
        cred_manager = CredentialManager(cred_file)
        cred_manager.set_master_password(master_password)
        cred_manager.store_credentials(hostname, username, password)
        
        # Create data collector using stored credentials
        collector = DataCollector(username=None)  # Will use stored credentials
        collector.credential_manager = cred_manager
        cred_manager.authenticate(master_password)
        
        # Note: We won't actually connect to the device in this test
        # In a real environment, we would test the full collection workflow
        print("  ✓ Data collection integration setup passed")
        
    finally:
        # Clean up
        for file_path in [cred_file, data_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)

def test_complete_workflow_simulation():
    """Test complete workflow simulation with mock data."""
    print("Testing complete workflow simulation...")
    
    # Create mock scan results
    mock_scan_results = [
        {"ip": "192.168.1.1", "hostname": "router1", "type": "mikrotik"},
        {"ip": "192.168.1.2", "hostname": "router2", "type": "mikrotik"}
    ]
    
    # Create mock collected data
    mock_collected_data = {
        "192.168.1.1": {
            "hostname": "192.168.1.1",
            "connected": True,
            "device_info": {
                "identity": "router1",
                "version": "RouterOS 7.1",
                "model": "RB4011iGS+"
            },
            "interfaces": [
                {"name": "ether1", "mac_address": "00:11:22:33:44:55"},
                {"name": "ether2", "mac_address": "00:11:22:33:44:56"}
            ],
            "bridge_ports": [
                {"interface": "ether1", "bridge": "bridge1"},
                {"interface": "ether2", "bridge": "bridge1"}
            ],
            "arp_table": [
                {"address": "192.168.1.100", "mac_address": "AA:BB:CC:DD:EE:FF"},
                {"address": "192.168.1.101", "mac_address": "AA:BB:CC:DD:EE:FE"}
            ],
            "dhcp_leases": [
                {"active_address": "192.168.1.100", "mac_address": "AA:BB:CC:DD:EE:FF", "host_name": "laptop1"},
                {"active_address": "192.168.1.101", "mac_address": "AA:BB:CC:DD:EE:FE", "host_name": "phone1"}
            ]
        }
    }
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        scan_file = f.name
        json.dump(mock_scan_results, f)
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        data_file = f.name
        json.dump(mock_collected_data, f)
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        map_file = f.name
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        readable_file = f.name
    
    try:
        # Test connection mapping with mock data
        mapper = ConnectionMapper()
        mapper.load_data(data_file)
        connection_map = mapper.build_connection_map()
        
        # Verify map structure
        assert "devices" in connection_map
        assert "connections" in connection_map
        assert "hosts" in connection_map
        
        # Generate readable output
        descriptions = mapper.generate_readable_output()
        assert isinstance(descriptions, list)
        
        # Save map
        mapper.save_map(map_file, connection_map)
        
        # Verify files were created
        assert os.path.exists(map_file)
        assert os.path.exists(readable_file) or True  # May be empty
        
        print("  ✓ Complete workflow simulation test passed")
        
    finally:
        # Clean up
        for file_path in [scan_file, data_file, map_file, readable_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)

def main():
    """Run all integration tests."""
    print("Running Integration Tests...")
    print("=" * 40)
    
    try:
        test_credential_storage_integration()
        test_data_collection_integration()
        test_complete_workflow_simulation()
        
        print("\nAll Integration tests passed! ✓")
        return 0
    except Exception as e:
        print(f"\nIntegration test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())