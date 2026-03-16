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

import lib.data_collector as data_collector_module
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


class FakeAPIClient(FakeSSHClient):
    """Minimal fake RouterOS API client for collection tests."""

    pass


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
        self.assertEqual(collector.backend, "api")

    @patch.dict("lib.data_collector.DataCollector.CLIENTS", {"api": FakeAPIClient}, clear=False)
    def test_collect_from_device_defaults_to_api_port(self):
        collector = DataCollector(username="admin", password="password", backend="api")
        result = collector.collect_from_device("192.168.1.1")

        self.assertTrue(result["connected"])
        self.assertEqual(collector._create_client("192.168.1.1", None, 10).kwargs["port"], 8728)

    @patch.dict("lib.data_collector.DataCollector.CLIENTS", {"ssh": FakeSSHClient}, clear=False)
    def test_collect_from_device_collects_all_sections(self):
        collector = DataCollector(username="admin", password="password", backend="ssh")
        result = collector.collect_from_device("192.168.1.1")

        self.assertTrue(result["connected"])
        self.assertEqual(result["device_info"]["identity"], "router1")
        self.assertEqual(len(result["bridge_hosts"]), 1)
        self.assertEqual(result["bridge_hosts"][0]["interface"], "ether1")
        self.assertEqual(len(result["ip_addresses"]), 1)
        self.assertEqual(result["ip_addresses"][0]["address"], "203.0.113.5/24")

    @patch.dict(
        "lib.data_collector.DataCollector.CLIENTS",
        {"ssh": PartiallyFailingSSHClient},
        clear=False,
    )
    def test_collect_from_device_continues_after_single_getter_failure(self):
        collector = DataCollector(username="admin", password="password", backend="ssh")
        result = collector.collect_from_device("192.168.1.1")

        self.assertTrue(result["connected"])
        self.assertEqual(result["bridge_hosts"], [])
        self.assertEqual(len(result["ip_addresses"]), 1)
        self.assertEqual(result["ip_addresses"][0]["address"], "203.0.113.5/24")

    @patch.dict("lib.data_collector.DataCollector.CLIENTS", {"api": FakeAPIClient}, clear=False)
    def test_collect_from_device_supports_api_backend(self):
        collector = DataCollector(
            username="admin",
            password="password",
            backend="api",
            use_ssl=True,
        )
        result = collector.collect_from_device("192.168.1.1", port=8729)

        self.assertTrue(result["connected"])
        self.assertEqual(result["device_info"]["identity"], "router1")

    def test_data_collector_rejects_unknown_backend(self):
        with self.assertRaises(ValueError):
            DataCollector(username="admin", backend="bogus")

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
            self.assertTrue(collector.save_data(temp_file, sample_data))
            loaded_data = collector.load_data(temp_file)
            self.assertEqual(loaded_data["192.168.1.1"]["device_info"]["identity"], "router1")
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    @patch.object(data_collector_module.DataCollector, "collect_from_devices", return_value={})
    def test_cli_ssh_backend_defaults_port_to_none(self, mock_collect):
        with patch.object(sys, "argv", [
            "data_collector.py",
            "192.168.1.1",
            "--backend",
            "ssh",
            "-u",
            "admin",
        ]):
            data_collector_module.main()

        mock_collect.assert_called_once_with(
            ["192.168.1.1"],
            None,
            10,
        )


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestDataCollector)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
