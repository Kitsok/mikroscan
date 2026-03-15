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
                {
                    "name": "ether1",
                    "type": "ether",
                    "mac_address": "AA:AA:AA:AA:AA:01",
                    "poe_out": "auto-on",
                    "poe_out_power": "12.5W",
                },
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
    assert "├─ ether1 [AA:AA:AA:AA:AA:01] [PoE: 12.5W]" in output
    assert "│  └─ WAN-VLAN6 [AA:AA:AA:AA:AA:01] [vlan 6]" in output
    assert "│     └─ WAN-pppoe (8.8.8.8/32)" in output
    assert "Branch (192.168.0.2) [BB:BB:BB:BB:BB:01]" in output
    assert "├─ ether2" in output
    assert "│  └─ <ether1> Branch (192.168.0.2) [BB:BB:BB:BB:BB:01]" in output
    assert "            └─ wifi1" in output or "         └─ wifi1" in output
    assert "leaf-host (192.168.0.30) [EE:EE:EE:EE:EE:01]" in output
    assert "direct-host (192.168.0.20) [DD:DD:DD:DD:DD:01]" in output
    assert "UNRESOLVED HOSTS" in output
    assert "upstream-host (192.168.0.10) [CC:CC:CC:CC:CC:01]" in output
    print("✓ rooted topology tree test passed")


def test_nested_child_device_ports_keep_tree_indentation():
    """Nested device subtrees should keep tree prefixes, not label-width spacing."""
    builder = TopologyBuilder()
    builder.devices_data = {
        "1.1.1.1": {
            "hostname": "1.1.1.1",
            "connected": True,
            "device_info": {"identity": "Root"},
            "interfaces": [
                {"name": "sfp1", "mac_address": "AA:AA:AA:AA:AA:01"},
            ],
            "bridge_hosts": [
                {"interface": "sfp1", "mac_address": "BB:BB:BB:BB:BB:01"},
            ],
            "dhcp_leases": [],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "1.1.1.1/24"}],
            "neighbors": [],
        },
        "2.2.2.2": {
            "hostname": "2.2.2.2",
            "connected": True,
            "device_info": {"identity": "ChildWithLongName"},
            "interfaces": [
                {"name": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
                {"name": "ether2", "mac_address": "BB:BB:BB:BB:BB:02"},
            ],
            "bridge_hosts": [
                {"interface": "ether1", "mac_address": "AA:AA:AA:AA:AA:01"},
                {"interface": "ether2", "mac_address": "CC:CC:CC:CC:CC:01"},
            ],
            "dhcp_leases": [
                {
                    "mac_address": "CC:CC:CC:CC:CC:01",
                    "active_address": "192.168.0.10",
                    "host_name": "leaf-host",
                }
            ],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "2.2.2.2/24"}],
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
            lines = handle.read().splitlines()
    finally:
        if os.path.exists(output_file):
            os.unlink(output_file)

    child_line = next(line for line in lines if "ChildWithLongName" in line)
    port_line = next(line for line in lines if "ether2 [BB:BB:BB:BB:BB:02]" in line)

    assert child_line.startswith("   └─ <ether1> ChildWithLongName")
    assert port_line.startswith("            └─ ether2 [BB:BB:BB:BB:BB:02]")
    print("✓ nested child indentation test passed")


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
    assert "UNRESOLVED HOSTS" not in output
    print("✓ shared-segment reduction test passed")


def test_shared_segment_child_keeps_vertical_continuation_for_following_host():
    """A device subtree on a shared segment must preserve the vertical branch."""
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
                {"interface": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
                {"interface": "ether1", "mac_address": "CC:CC:CC:CC:CC:01"},
            ],
            "dhcp_leases": [
                {
                    "mac_address": "CC:CC:CC:CC:CC:01",
                    "active_address": "192.168.0.50",
                    "host_name": "segment-host",
                }
            ],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "1.1.1.1/24"}],
            "neighbors": [],
        },
        "2.2.2.2": {
            "hostname": "2.2.2.2",
            "connected": True,
            "device_info": {"identity": "Branch"},
            "interfaces": [
                {"name": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
                {"name": "wifi1", "mac_address": "BB:BB:BB:BB:BB:02"},
            ],
            "bridge_hosts": [
                {"interface": "wifi1", "mac_address": "DD:DD:DD:DD:DD:01"},
            ],
            "dhcp_leases": [
                {
                    "mac_address": "DD:DD:DD:DD:DD:01",
                    "active_address": "192.168.0.60",
                    "host_name": "wifi-host",
                }
            ],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "2.2.2.2/24"}],
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

    assert "└─ [shared segment]" in output
    assert "   ├─ <ether1> Branch (2.2.2.2) [BB:BB:BB:BB:BB:01]" in output
    assert "   │           └─ wifi1 [BB:BB:BB:BB:BB:02]" in output
    assert "   └─ segment-host (192.168.0.50) [CC:CC:CC:CC:CC:01]" in output
    print("✓ shared-segment child continuation test passed")


def test_device_bridge_mac_endpoint_uses_reciprocal_physical_port_label():
    """A managed device seen via its bridge MAC should still show the uplink port."""
    builder = TopologyBuilder()
    builder.devices_data = {
        "1.1.1.1": {
            "hostname": "1.1.1.1",
            "connected": True,
            "device_info": {"identity": "Root"},
            "interfaces": [
                {"name": "ether7", "mac_address": "AA:AA:AA:AA:AA:07"},
            ],
            "bridge_hosts": [
                {"interface": "ether7", "mac_address": "BB:BB:BB:BB:BB:00"},
            ],
            "dhcp_leases": [],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "1.1.1.1/24"}],
            "neighbors": [],
        },
        "2.2.2.2": {
            "hostname": "2.2.2.2",
            "connected": True,
            "device_info": {"identity": "Branch"},
            "interfaces": [
                {"name": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
                {"name": "LAN", "type": "bridge", "mac_address": "BB:BB:BB:BB:BB:00"},
                {"name": "wifi1", "mac_address": "BB:BB:BB:BB:BB:02"},
            ],
            "bridge_hosts": [
                {"interface": "ether1", "mac_address": "AA:AA:AA:AA:AA:07"},
                {"interface": "wifi1", "mac_address": "CC:CC:CC:CC:CC:01"},
            ],
            "dhcp_leases": [
                {
                    "mac_address": "CC:CC:CC:CC:CC:01",
                    "active_address": "192.168.0.30",
                    "host_name": "leaf-host",
                }
            ],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "2.2.2.2/24"}],
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

    assert "<ether1> Branch (2.2.2.2) [BB:BB:BB:BB:BB:00]" in output
    print("✓ reciprocal remote-port label test passed")


def test_generate_topology_output_marks_multi_device_ports_as_shared_segments():
    """Render a shared-segment node when one port still has multiple peer MikroTiks."""
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
                {"interface": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
                {"interface": "ether1", "mac_address": "CC:CC:CC:CC:CC:01"},
                {"interface": "ether1", "mac_address": "DD:DD:DD:DD:DD:01"},
            ],
            "dhcp_leases": [
                {
                    "mac_address": "DD:DD:DD:DD:DD:01",
                    "active_address": "192.168.0.30",
                    "host_name": "segment-host",
                }
            ],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "1.1.1.1/24"}],
            "neighbors": [],
        },
        "10.0.0.2": {
            "hostname": "10.0.0.2",
            "connected": True,
            "device_info": {"identity": "BranchA"},
            "interfaces": [
                {"name": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
            ],
            "bridge_hosts": [
                {"interface": "ether1", "mac_address": "AA:AA:AA:AA:AA:01"},
            ],
            "dhcp_leases": [],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "10.0.0.2/24"}],
            "neighbors": [],
        },
        "10.0.0.3": {
            "hostname": "10.0.0.3",
            "connected": True,
            "device_info": {"identity": "BranchB"},
            "interfaces": [
                {"name": "ether1", "mac_address": "CC:CC:CC:CC:CC:01"},
            ],
            "bridge_hosts": [
                {"interface": "ether1", "mac_address": "AA:AA:AA:AA:AA:01"},
            ],
            "dhcp_leases": [],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "10.0.0.3/24"}],
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

    assert "└─ [shared segment]" in output
    assert "├─ <ether1> BranchA (10.0.0.2) [BB:BB:BB:BB:BB:01]" in output
    assert "├─ <ether1> BranchB (10.0.0.3) [CC:CC:CC:CC:CC:01]" in output
    assert "└─ segment-host (192.168.0.30) [DD:DD:DD:DD:DD:01]" in output
    print("✓ shared segment rendering test passed")


def test_generate_topology_output_marks_device_plus_hosts_as_shared_segment():
    """Render a shared-segment node for one MikroTik plus multiple hosts."""
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
                {"interface": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
                {"interface": "ether1", "mac_address": "DD:DD:DD:DD:DD:01"},
                {"interface": "ether1", "mac_address": "EE:EE:EE:EE:EE:01"},
            ],
            "dhcp_leases": [
                {
                    "mac_address": "DD:DD:DD:DD:DD:01",
                    "active_address": "192.168.0.30",
                    "host_name": "host-a",
                },
                {
                    "mac_address": "EE:EE:EE:EE:EE:01",
                    "active_address": "192.168.0.31",
                    "host_name": "host-b",
                },
            ],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "1.1.1.1/24"}],
            "neighbors": [],
        },
        "10.0.0.2": {
            "hostname": "10.0.0.2",
            "connected": True,
            "device_info": {"identity": "Branch"},
            "interfaces": [
                {"name": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
            ],
            "bridge_hosts": [
                {"interface": "ether1", "mac_address": "AA:AA:AA:AA:AA:01"},
            ],
            "dhcp_leases": [],
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

    assert "└─ [shared segment]" in output
    assert "├─ <ether1> Branch (10.0.0.2) [BB:BB:BB:BB:BB:01]" in output
    assert "├─ host-a (192.168.0.30) [DD:DD:DD:DD:DD:01]" in output
    assert "└─ host-b (192.168.0.31) [EE:EE:EE:EE:EE:01]" in output
    print("✓ device-plus-hosts shared segment test passed")


def test_generate_topology_output_marks_device_plus_single_host_as_shared_segment():
    """Render a shared-segment node for one MikroTik plus one direct host."""
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
                {"interface": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
                {"interface": "ether1", "mac_address": "DD:DD:DD:DD:DD:01"},
            ],
            "dhcp_leases": [
                {
                    "mac_address": "DD:DD:DD:DD:DD:01",
                    "active_address": "192.168.0.30",
                    "host_name": "host-a",
                },
            ],
            "dns_static": [],
            "arp_table": [],
            "ip_addresses": [{"address": "1.1.1.1/24"}],
            "neighbors": [],
        },
        "10.0.0.2": {
            "hostname": "10.0.0.2",
            "connected": True,
            "device_info": {"identity": "Branch"},
            "interfaces": [
                {"name": "ether1", "mac_address": "BB:BB:BB:BB:BB:01"},
            ],
            "bridge_hosts": [
                {"interface": "ether1", "mac_address": "AA:AA:AA:AA:AA:01"},
            ],
            "dhcp_leases": [],
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

    assert "└─ [shared segment]" in output
    assert "├─ <ether1> Branch (10.0.0.2) [BB:BB:BB:BB:BB:01]" in output
    assert "└─ host-a (192.168.0.30) [DD:DD:DD:DD:DD:01]" in output
    print("✓ device-plus-single-host shared segment test passed")


def main():
    """Run topology builder tests."""
    print("Running Topology Builder Tests...")

    try:
        test_generate_topology_output_builds_rooted_tree()
        test_generate_topology_output_hides_shared_segment_hosts_behind_single_child()
        test_generate_topology_output_marks_multi_device_ports_as_shared_segments()
        test_generate_topology_output_marks_device_plus_hosts_as_shared_segment()
        test_generate_topology_output_marks_device_plus_single_host_as_shared_segment()
        print("\nAll Topology Builder tests passed! ✓")
        return 0
    except Exception as exc:
        print(f"\nTopology Builder test failed: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
