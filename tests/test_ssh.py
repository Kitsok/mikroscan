#!/usr/bin/env python3
"""
Unit tests for the MikroTik SSH client parsing logic.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.mikrotik_ssh import MikrotikSSHClient


class RecordingSSHClient(MikrotikSSHClient):
    """SSH client test double that records commands and returns canned output."""

    def __init__(self, responses):
        super().__init__(hostname="192.168.1.1", username="admin", password="password")
        self.responses = responses
        self.commands = []

    def execute_command(self, command):
        self.commands.append(command)
        return self.responses.get(command, ("", "", 0))


class TestMikrotikSSHClient(unittest.TestCase):
    """Tests for SSH parsing helpers."""

    def test_ssh_client_initialization(self):
        client = MikrotikSSHClient(
            hostname="192.168.1.1",
            username="admin",
            password="password",
            port=2222,
            timeout=30,
        )
        self.assertEqual(client.hostname, "192.168.1.1")
        self.assertEqual(client.username, "admin")
        self.assertEqual(client.password, "password")
        self.assertEqual(client.port, 2222)
        self.assertEqual(client.timeout, 30)
        self.assertFalse(client.connected)

    def test_get_dhcp_leases_uses_supported_command(self):
        stdout = (
            " 0 address=192.168.1.10 mac-address=00:11:22:33:44:55 host-name=host1\n"
            "\n"
            " 1 address=192.168.1.11 mac-address=00:11:22:33:44:66 host-name=host2\n"
        )
        client = RecordingSSHClient({
            "/ip dhcp-server lease print detail": (stdout, "", 0),
        })

        leases = client.get_dhcp_leases()

        self.assertEqual(client.commands, ["/ip dhcp-server lease print detail"])
        self.assertEqual(len(leases), 2)
        self.assertEqual(leases[0]["address"], "192.168.1.10")
        self.assertEqual(leases[0]["mac_address"], "00:11:22:33:44:55")
        self.assertEqual(leases[1]["host_name"], "host2")

    def test_get_bridge_host_entries_parses_output(self):
        stdout = (
            " 0 mac-address=00:11:22:33:44:55 on-interface=bridge interface=ether1\n"
            "\n"
            " 1 mac-address=AA:BB:CC:DD:EE:FF on-interface=bridge interface=sfp-sfpplus1\n"
        )
        client = RecordingSSHClient({
            "/interface bridge host print detail": (stdout, "", 0),
        })

        entries = client.get_bridge_host_entries()

        self.assertEqual(client.commands, ["/interface bridge host print detail"])
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["interface"], "ether1")
        self.assertEqual(entries[1]["mac_address"], "AA:BB:CC:DD:EE:FF")

    def test_detects_routeros_error_text(self):
        client = MikrotikSSHClient(hostname="192.168.1.1", username="admin", password="password")

        self.assertTrue(client._looks_like_command_error("expected end of command (line 1 column 36)\n"))
        self.assertFalse(client._looks_like_command_error(" 0 address=192.168.1.10 mac-address=00:11:22:33:44:55\n"))


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestMikrotikSSHClient)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
