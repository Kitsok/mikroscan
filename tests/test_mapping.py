#!/usr/bin/env python3
"""
Unit tests for the Connection Mapper module.
"""

import sys
import os
import tempfile
import json
from unittest.mock import patch

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
        assert mapper.save_map(temp_file, sample_map) is True
        
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


def test_connection_mapper_cli_exits_non_zero_on_load_failure():
    """Standalone connection-mapper CLI should fail on unreadable input."""
    import lib.connection_mapper as connection_mapper_module

    original_argv = sys.argv[:]
    sys.argv = ["connection_mapper.py", "missing.json"]

    try:
        with patch.object(ConnectionMapper, "load_data", return_value=None):
            try:
                connection_mapper_module.main()
                raise AssertionError("main() should have exited")
            except SystemExit as exc:
                assert exc.code == 1
    finally:
        sys.argv = original_argv

    print("✓ connection mapper CLI exit-code test passed")

def test_generate_readable_output_uses_host_metadata_for_bridge_ports():
    """Test readable bridge-port output falls back to host metadata."""
    mapper = ConnectionMapper()

    mapper.connection_map = {
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
            }
        ],
        "hosts": {
            "00:11:22:33:44:55": {
                "mac_address": "00:11:22:33:44:55",
                "hostname": "host1",
                "ip_addresses": ["192.168.1.50"],
                "seen_on_devices": ["router1"]
            }
        }
    }

    descriptions = mapper.generate_readable_output()

    assert descriptions == [
        "ether1 on router1 is connected to host host1 [00:11:22:33:44:55]"
    ]
    print("✓ readable bridge host metadata test passed")

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


def test_duplicate_identities_get_unique_device_labels():
    """Duplicate RouterOS identities should not collapse devices in the map."""
    mapper = ConnectionMapper()

    mapper.set_data({
        "192.168.1.1": {
            "hostname": "192.168.1.1",
            "connected": True,
            "device_info": {"identity": "router"},
            "interfaces": [{"name": "ether1", "mac_address": "AA:AA:AA:AA:AA:01"}],
            "bridge_ports": [],
            "bridge_hosts": [],
            "arp_table": [],
            "dhcp_leases": [],
        },
        "192.168.1.2": {
            "hostname": "192.168.1.2",
            "connected": True,
            "device_info": {"identity": "router"},
            "interfaces": [{"name": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"}],
            "bridge_ports": [],
            "bridge_hosts": [],
            "arp_table": [],
            "dhcp_leases": [],
        },
    })

    connection_map = mapper.build_connection_map()

    assert "router (192.168.1.1)" in connection_map["devices"]
    assert "router (192.168.1.2)" in connection_map["devices"]
    assert len(connection_map["devices"]) == 2
    print("✓ duplicate identity device labels test passed")

def main():
    """Run all mapping tests."""
    print("Running Connection Mapper Tests...")
    
    try:
        test_connection_mapper_initialization()
        test_set_and_load_data()
        test_save_and_load_map()
        test_generate_readable_output()
        test_connection_mapper_cli_exits_non_zero_on_load_failure()
        test_generate_readable_output_uses_host_metadata_for_bridge_ports()
        test_host_connections_use_bridge_host_interface()
        test_managed_devices_are_not_added_as_hosts()
        test_duplicate_identities_get_unique_device_labels()
        
        print("\nAll Connection Mapper tests passed! ✓")
        return 0
    except Exception as e:
        print(f"\nConnection Mapper test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
