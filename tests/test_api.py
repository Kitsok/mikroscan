#!/usr/bin/env python3
"""Unit tests for the native RouterOS API client."""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.mikrotik_api import MikrotikAPIClient


class FakeResource:
    """Simple resource wrapper returning canned records."""

    def __init__(self, records):
        self.records = records

    def get(self, **kwargs):
        return list(self.records)

    def call(self, command, arguments=None, queries=None, additional_queries=()):
        return list(self.records)


class FakeApi:
    """Minimal RouterOS API facade for tests."""

    def __init__(self, resources):
        self.resources = resources

    def get_resource(self, path):
        return FakeResource(self.resources.get(path, []))


class FakePool:
    """Fake pool returned by routeros_api.RouterOsApiPool."""

    def __init__(self, api):
        self.api = api
        self.disconnected = False

    def get_api(self):
        return self.api

    def disconnect(self):
        self.disconnected = True


class TestMikrotikAPIClient(unittest.TestCase):
    """Tests for API client normalization and connection setup."""

    def test_normalize_record_rewrites_routeros_keys(self):
        client = MikrotikAPIClient(hostname="192.168.1.1", username="admin", password="password")
        record = {
            ".id": "*1",
            "mac-address": "00:11:22:33:44:55",
            "board-name": "RB5009",
        }

        normalized = client._normalize_record(record)

        self.assertEqual(normalized["id"], "*1")
        self.assertEqual(normalized["mac_address"], "00:11:22:33:44:55")
        self.assertEqual(normalized["board_name"], "RB5009")

    @patch("lib.mikrotik_api.routeros_api")
    def test_connect_uses_routeros_api_pool(self, routeros_api_module):
        resources = {
            "/system/identity": [{"name": "router1"}],
            "/system/resource": [{"version": "7.17", "board-name": "RB5009"}],
        }
        fake_api = FakeApi(resources)
        fake_pool = FakePool(fake_api)
        routeros_api_module.RouterOsApiPool.return_value = fake_pool

        client = MikrotikAPIClient(
            hostname="192.168.1.1",
            username="admin",
            password="password",
            port=8729,
            use_ssl=True,
        )

        self.assertTrue(client.connect())
        info = client.get_device_info()

        routeros_api_module.RouterOsApiPool.assert_called_once_with(
            "192.168.1.1",
            username="admin",
            password="password",
            port=8729,
            use_ssl=True,
            plaintext_login=False,
        )
        self.assertEqual(info["identity"], "router1")
        self.assertEqual(info["model"], "RB5009")

        client.disconnect()
        self.assertFalse(client.connected)
        self.assertTrue(fake_pool.disconnected)

    def test_get_interfaces_merges_poe_monitor_details(self):
        resources = {
            "/interface": [
                {"name": "ether1", "type": "ether"},
                {"name": "bridge1", "type": "bridge"},
            ],
            "/interface/ethernet": [
                {"name": "ether1", "mac-address": "00:11:22:33:44:55", "poe-out": "auto-on"},
            ],
            "/interface/ethernet/poe": [
                {
                    "name": "ether1",
                    "poe-out": "auto-on",
                    "poe-out-status": "powered-on",
                    "poe-out-power": "12.5W",
                    "poe-out-voltage": "53.2V",
                },
            ],
        }
        client = MikrotikAPIClient(hostname="192.168.1.1", username="admin", password="password")
        client.api = FakeApi(resources)
        client.connected = True

        interfaces = client.get_interfaces()

        self.assertEqual(interfaces[0]["poe_out"], "auto-on")
        self.assertEqual(interfaces[0]["poe_out_status"], "powered-on")
        self.assertEqual(interfaces[0]["poe_out_power"], "12.5W")
        self.assertEqual(interfaces[0]["poe_out_voltage"], "53.2V")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMikrotikAPIClient)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
