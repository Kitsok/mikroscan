#!/usr/bin/env python3
"""
Unit tests for the data collection module.
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.data_collector import DataCollector


class FakeSSHClient:
    """Minimal fake SSH client for collection tests."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.disconnected = False

    def connect(self):
        return True

    def disconnect(self):
        self.disconnected = True

    def get_device_info(self):
        return {"identity": "router1"}

    def get_interfaces(self):
        return [{"name": "ether1"}]

    def get_bridge_ports(self):
        return [{"interface": "ether1"}]

    def get_arp_table(self):
        return [{"address": "192.168.1.10", "mac_address": "00:11:22:33:44:55"}]

    def get_dhcp_leases(self):
        return [{"active_address": "192.168.1.10", "mac_address": "00:11:22:33:44:55"}]

    def get_neighbors(self):
        return [{"identity": "router2", "mac_address": "66:77:88:99:AA:BB"}]

    def get_dns_static_entries(self):
        return [{"name": "host1", "address": "192.168.1.10"}]

    def get_bridge_host_entries(self):
        return [{"interface": "ether1", "mac_address": "00:11:22:33:44:55"}]

    def get_ip_addresses(self):
        return [{"address": "203.0.113.5/24", "interface": "ether1"}]


class PartiallyFailingSSHClient(FakeSSHClient):
    """Fake SSH client that fails one getter but continues for others."""

    def get_bridge_host_entries(self):
        raise RuntimeError("bridge host unsupported")


class TestDataCollector(unittest.TestCase):
    """Tests for collection behavior."""

    def test_data_collector_initialization(self):
        collector = DataCollector(username="admin", password="password")
        self.assertEqual(collector.username, "admin")
        self.assertEqual(collector.password, "password")
        self.assertIsNone(collector.key_filename)

    @patch("lib.data_collector.MikrotikSSHClient", FakeSSHClient)
    def test_collect_from_device_collects_all_sections(self):
        collector = DataCollector(username="admin", password="password")
        result = collector.collect_from_device("192.168.1.1")

        self.assertTrue(result["connected"])
        self.assertEqual(result["device_info"]["identity"], "router1")
        self.assertEqual(len(result["bridge_hosts"]), 1)
        self.assertEqual(result["bridge_hosts"][0]["interface"], "ether1")
        self.assertEqual(len(result["ip_addresses"]), 1)
        self.assertEqual(result["ip_addresses"][0]["address"], "203.0.113.5/24")

    @patch("lib.data_collector.MikrotikSSHClient", PartiallyFailingSSHClient)
    def test_collect_from_device_continues_after_single_getter_failure(self):
        collector = DataCollector(username="admin", password="password")
        result = collector.collect_from_device("192.168.1.1")

        self.assertTrue(result["connected"])
        self.assertEqual(result["bridge_hosts"], [])
        self.assertEqual(len(result["ip_addresses"]), 1)
        self.assertEqual(result["ip_addresses"][0]["address"], "203.0.113.5/24")

    def test_save_and_load_data(self):
        collector = DataCollector(username="admin")
        sample_data = {
            "192.168.1.1": {
                "hostname": "192.168.1.1",
                "connected": True,
                "device_info": {"identity": "router1"},
                "interfaces": [{"name": "ether1"}],
                "bridge_ports": [],
                "arp_table": [],
                "dhcp_leases": [],
                "neighbors": [],
                "dns_static": [],
                "bridge_hosts": [],
                "ip_addresses": [],
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as handle:
            temp_file = handle.name

        try:
            collector.save_data(temp_file, sample_data)
            loaded_data = collector.load_data(temp_file)
            self.assertEqual(loaded_data["192.168.1.1"]["device_info"]["identity"], "router1")
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDataCollector)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
