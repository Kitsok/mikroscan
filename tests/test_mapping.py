#!/usr/bin/env python3
"""
Unit tests for the Connection Mapper module.
"""

import sys
import os
import tempfile
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.connection_mapper import ConnectionMapper

def test_connection_mapper_initialization():
    """Test ConnectionMapper initialization."""
    mapper = ConnectionMapper()
    
    assert mapper.devices_data == {}
    assert mapper.connection_map == {}
    print("✓ ConnectionMapper initialization test passed")

def test_set_and_load_data():
    """Test setting and loading data."""
    mapper = ConnectionMapper()
    
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
    
    # Set data directly
    mapper.set_data(sample_data)
    assert len(mapper.devices_data) == 1
    assert mapper.devices_data["192.168.1.1"]["hostname"] == "192.168.1.1"
    print("✓ set_data test passed")

def test_save_and_load_map():
    """Test saving and loading connection map to/from JSON file."""
    mapper = ConnectionMapper()
    
    # Sample connection map
    sample_map = {
        "devices": {
            "router1": {
                "hostname": "192.168.1.1",
                "info": {"identity": "router1"}
            }
        },
        "connections": [
            {
                "source_device": "router1",
                "source_interface": "ether1",
                "type": "bridge_port"
            }
        ],
        "hosts": {}
    }
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_file = f.name
    
    try:
        # Save map
        mapper.save_map(temp_file, sample_map)
        
        # Create new mapper and load data
        new_mapper = ConnectionMapper()
        loaded_map = new_mapper.load_data(temp_file)
        
        assert len(loaded_map["devices"]) == 1
        assert loaded_map["devices"]["router1"]["hostname"] == "192.168.1.1"
        print("✓ save/load map test passed")
        
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def test_generate_readable_output():
    """Test generating readable output."""
    mapper = ConnectionMapper()
    
    # Sample connection map
    sample_map = {
        "devices": {
            "router1": {
                "hostname": "192.168.1.1",
                "info": {"identity": "router1"}
            }
        },
        "connections": [
            {
                "source_device": "router1",
                "source_interface": "ether1",
                "mac_address": "00:11:22:33:44:55",
                "type": "bridge_port"
            },
            {
                "source_device": "router1",
                "source_interface": "ether2",
                "destination_host": "host1",
                "type": "host_connection"
            }
        ],
        "hosts": {}
    }
    
    mapper.connection_map = sample_map
    descriptions = mapper.generate_readable_output()
    
    assert len(descriptions) == 2
    assert "ether1 on router1 is connected to device with MAC 00:11:22:33:44:55" in descriptions
    assert "ether2 on router1 is connected to host host1" in descriptions
    print("✓ generate_readable_output test passed")

def test_host_connections_use_bridge_host_interface():
    """Test host connections resolve their interface from bridge host data."""
    mapper = ConnectionMapper()

    mapper.set_data({
        "192.168.1.1": {
            "hostname": "192.168.1.1",
            "connected": True,
            "device_info": {"identity": "router1"},
            "interfaces": [{"name": "bridge", "mac_address": "AA:BB:CC:DD:EE:FF"}],
            "bridge_ports": [{"interface": "ether3"}],
            "bridge_hosts": [
                {"interface": "ether3", "mac_address": "00:11:22:33:44:55"}
            ],
            "arp_table": [
                {"address": "192.168.1.50", "mac_address": "00:11:22:33:44:55"}
            ],
            "dhcp_leases": [
                {"mac_address": "00:11:22:33:44:55", "host_name": "host1"}
            ]
        }
    })

    connection_map = mapper.build_connection_map()
    host_connections = [
        connection for connection in connection_map["connections"]
        if connection["type"] == "host_connection"
    ]

    assert len(host_connections) == 1
    assert host_connections[0]["source_interface"] == "ether3"
    assert host_connections[0]["destination_host"] == "host1"
    print("✓ host interface resolution test passed")

def test_managed_devices_are_not_added_as_hosts():
    """Test managed device MACs and identities are excluded from host output."""
    mapper = ConnectionMapper()

    mapper.set_data({
        "192.168.1.1": {
            "hostname": "192.168.1.1",
            "connected": True,
            "device_info": {"identity": "router1"},
            "interfaces": [{"name": "ether1", "mac_address": "AA:BB:CC:DD:EE:FF"}],
            "bridge_ports": [{"interface": "ether2"}],
            "bridge_hosts": [
                {"interface": "ether2", "mac_address": "00:11:22:33:44:55"},
                {"interface": "ether2", "mac_address": "66:77:88:99:AA:BB"},
            ],
            "arp_table": [
                {"address": "192.168.1.2", "mac_address": "AA:BB:CC:DD:EE:FF"},
                {"address": "192.168.1.3", "mac_address": "66:77:88:99:AA:BB"},
                {"address": "192.168.1.50", "mac_address": "00:11:22:33:44:55"},
            ],
            "dhcp_leases": [
                {"mac_address": "66:77:88:99:AA:BB", "host_name": "router1"},
                {"mac_address": "00:11:22:33:44:55", "host_name": "host1"},
            ]
        }
    })

    connection_map = mapper.build_connection_map()

    assert "AA:BB:CC:DD:EE:FF" not in connection_map["hosts"]
    assert "66:77:88:99:AA:BB" not in connection_map["hosts"]
    assert "00:11:22:33:44:55" in connection_map["hosts"]
    host_connections = [
        connection for connection in connection_map["connections"]
        if connection["type"] == "host_connection"
    ]
    assert len(host_connections) == 1
    assert host_connections[0]["destination_host"] == "host1"
    print("✓ managed device host suppression test passed")

def main():
    """Run all mapping tests."""
    print("Running Connection Mapper Tests...")
    
    try:
        test_connection_mapper_initialization()
        test_set_and_load_data()
        test_save_and_load_map()
        test_generate_readable_output()
        test_host_connections_use_bridge_host_interface()
        test_managed_devices_are_not_added_as_hosts()
        
        print("\nAll Connection Mapper tests passed! ✓")
        return 0
    except Exception as e:
        print(f"\nConnection Mapper test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
