#!/usr/bin/env python3
"""
Unit tests for the Data Collector module.
"""

import sys
import os
import tempfile
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.data_collector import DataCollector

def test_data_collector_initialization():
    """Test DataCollector initialization."""
    collector = DataCollector(
        username="admin",
        password="password"
    )
    
    assert collector.username == "admin"
    assert collector.password == "password"
    assert collector.key_filename is None
    print("✓ DataCollector initialization test passed")

def test_data_collector_with_key_file():
    """Test DataCollector with key file."""
    collector = DataCollector(
        username="admin",
        key_filename="/path/to/key"
    )
    
    assert collector.username == "admin"
    assert collector.key_filename == "/path/to/key"
    assert collector.password is None
    print("✓ DataCollector key file test passed")

def test_save_and_load_data():
    """Test saving and loading data to/from JSON file."""
    collector = DataCollector(username="admin")
    
    # Sample data
    sample_data = {
        "192.168.1.1": {
            "hostname": "192.168.1.1",
            "connected": True,
            "device_info": {"identity": "router1"},
            "interfaces": [{"name": "ether1"}],
            "bridge_ports": [],
            "arp_table": [],
            "dhcp_leases": []
        }
    }
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_file = f.name
    
    try:
        # Save data
        collector.save_data(temp_file, sample_data)
        
        # Load data
        loaded_data = collector.load_data(temp_file)
        
        assert len(loaded_data) == 1
        assert loaded_data["192.168.1.1"]["hostname"] == "192.168.1.1"
        assert loaded_data["192.168.1.1"]["device_info"]["identity"] == "router1"
        print("✓ save/load data test passed")
        
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def main():
    """Run all data collector tests."""
    print("Running Data Collector Tests...")
    
    try:
        test_data_collector_initialization()
        test_data_collector_with_key_file()
        test_save_and_load_data()
        
        print("\nAll Data Collector tests passed! ✓")
        return 0
    except Exception as e:
        print(f"\nData Collector test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())