#!/usr/bin/env python3
"""Unit tests for the topology builder tree output."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.topology_builder import TopologyBuilder


def test_generate_topology_output_builds_rooted_tree():
    """Test rooted topology output with recursive child-device expansion."""
    builder = TopologyBuilder()
    builder.devices_data = {
        "1.1.1.1": {
            "hostname": "1.1.1.1",
            "connected": True,
            "device_info": {"identity": "Root"},
            "interfaces": [
                {"name": "ether1", "mac_address": "AA:AA:AA:AA:AA:01"},
                {"name": "ether2", "mac_address": "AA:AA:AA:AA:AA:02"},
                {"name": "ether3", "mac_address": "AA:AA:AA:AA:AA:03"},
                {"name": "WAN-VLAN6", "type": "vlan", "mac_address": "AA:AA:AA:AA:AA:01"},
                {"name": "WAN-pppoe", "type": "pppoe-out"},
            ],
            "bridge_hosts": [
                {"interface": "ether1", "mac_address": "CC:CC:CC:CC:CC:01"},
                {"interface": "ether2", "mac_address": "BB:BB:BB:BB:BB:01"},
                {"interface": "ether3", "mac_address": "DD:DD:DD:DD:DD:01"},
            ],
            "dhcp_leases": [
                {
                    "mac_address": "CC:CC:CC:CC:CC:01",
                    "active_address": "192.168.0.10",
                    "host_name": "upstream-host",
                },
                {
                    "mac_address": "DD:DD:DD:DD:DD:01",
                    "active_address": "192.168.0.20",
                    "host_name": "direct-host",
                },
            ],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "8.8.8.8/32", "interface": "WAN-pppoe"}],
            "neighbors": [],
        },
        "192.168.0.2": {
            "hostname": "192.168.0.2",
            "connected": True,
            "device_info": {"identity": "Branch"},
            "interfaces": [
                {"name": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
                {"name": "wifi1", "mac_address": "BB:BB:BB:BB:BB:02"},
            ],
            "bridge_hosts": [
                {"interface": "ether1", "mac_address": "AA:AA:AA:AA:AA:01"},
                {"interface": "wifi1", "mac_address": "EE:EE:EE:EE:EE:01"},
            ],
            "dhcp_leases": [
                {
                    "mac_address": "EE:EE:EE:EE:EE:01",
                    "active_address": "192.168.0.30",
                    "host_name": "leaf-host",
                }
            ],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "192.168.0.2/24"}],
            "neighbors": [],
        },
    }

    builder.build_mac_name_map()
    builder.build_mac_ip_map()
    builder.build_ip_name_map()
    builder.build_mac_port_map()

    with tempfile.NamedTemporaryFile(mode="r", delete=False) as handle:
        output_file = handle.name

    try:
        builder.generate_topology_output(output_file)
        with open(output_file, "r") as handle:
            output = handle.read()
    finally:
        if os.path.exists(output_file):
            os.unlink(output_file)

    assert "NETWORK TOPOLOGY" in output
    assert "Root (1.1.1.1)" in output
    assert "WAN:" not in output
    assert "├─ ether1 [AA:AA:AA:AA:AA:01]" in output
    assert "│  └─ WAN-VLAN6 [AA:AA:AA:AA:AA:01] [vlan 6]" in output
    assert "│     └─ WAN-pppoe (8.8.8.8/32)" in output
    assert "Branch (192.168.0.2) [BB:BB:BB:BB:BB:01]" in output
    assert "├─ ether2" in output
    assert "│  └─ <ether1> Branch (192.168.0.2) [BB:BB:BB:BB:BB:01]" in output
    assert "│     └─ wifi1" in output or "   └─ wifi1" in output
    assert "leaf-host (192.168.0.30) [EE:EE:EE:EE:EE:01]" in output
    assert "direct-host (192.168.0.20) [DD:DD:DD:DD:DD:01]" in output
    assert "upstream-host" not in output
    print("✓ rooted topology tree test passed")


def test_generate_topology_output_hides_shared_segment_hosts_behind_single_child():
    """Hide hosts from the parent port when a single child device explains them."""
    builder = TopologyBuilder()
    builder.devices_data = {
        "1.1.1.1": {
            "hostname": "1.1.1.1",
            "connected": True,
            "device_info": {"identity": "Root"},
            "interfaces": [
                {"name": "ether1", "mac_address": "AA:AA:AA:AA:AA:01"},
            ],
            "bridge_hosts": [
                {"interface": "ether1", "mac_address": "BB:BB:BB:BB:BB:00"},
                {"interface": "ether1", "mac_address": "EE:EE:EE:EE:EE:01"},
            ],
            "dhcp_leases": [],
            "dns_static": [],
            "arp_table": [
                {
                    "mac_address": "EE:EE:EE:EE:EE:01",
                    "address": "192.168.0.30",
                }
            ],
            "ip_addresses": [{"address": "1.1.1.1/24"}],
            "neighbors": [],
        },
        "10.0.0.2": {
            "hostname": "10.0.0.2",
            "connected": True,
            "device_info": {"identity": "Branch"},
            "interfaces": [
                {"name": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
                {"name": "LAN", "type": "bridge", "mac_address": "BB:BB:BB:BB:BB:00"},
                {"name": "wifi1", "mac_address": "BB:BB:BB:BB:BB:02"},
            ],
            "bridge_hosts": [
                {"interface": "ether1", "mac_address": "AA:AA:AA:AA:AA:01"},
                {"interface": "wifi1", "mac_address": "EE:EE:EE:EE:EE:01"},
            ],
            "dhcp_leases": [
                {
                    "mac_address": "EE:EE:EE:EE:EE:01",
                    "active_address": "192.168.0.30",
                    "host_name": "leaf-host",
                }
            ],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "10.0.0.2/24"}],
            "neighbors": [],
        },
    }

    builder.build_mac_name_map()
    builder.build_mac_ip_map()
    builder.build_ip_name_map()
    builder.build_mac_port_map()

    with tempfile.NamedTemporaryFile(mode="r", delete=False) as handle:
        output_file = handle.name

    try:
        builder.generate_topology_output(output_file)
        with open(output_file, "r") as handle:
            output = handle.read()
    finally:
        if os.path.exists(output_file):
            os.unlink(output_file)

    assert "<LAN> Branch" not in output
    assert "Branch (10.0.0.2) [BB:BB:BB:BB:BB:00]" in output
    assert output.count("leaf-host (192.168.0.30) [EE:EE:EE:EE:EE:01]") == 1
    assert "└─ wifi1 [BB:BB:BB:BB:BB:02]" in output
    print("✓ shared-segment reduction test passed")


def main():
    """Run topology builder tests."""
    print("Running Topology Builder Tests...")

    try:
        test_generate_topology_output_builds_rooted_tree()
        test_generate_topology_output_hides_shared_segment_hosts_behind_single_child()
        print("\nAll Topology Builder tests passed! ✓")
        return 0
    except Exception as exc:
        print(f"\nTopology Builder test failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
