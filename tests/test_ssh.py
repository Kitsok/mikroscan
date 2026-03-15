#!/usr/bin/env python3
"""
Unit tests for the SSH module.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ssh.mikrotik_ssh import MikrotikSSHClient

def test_ssh_client_initialization():
    """Test MikrotikSSHClient initialization."""
    client = MikrotikSSHClient(
        hostname="192.168.1.1",
        username="admin",
        password="password"
    )
    
    assert client.hostname == "192.168.1.1"
    assert client.username == "admin"
    assert client.password == "password"
    assert client.port == 22
    assert client.timeout == 10
    assert client.connected == False
    print("✓ MikrotikSSHClient initialization test passed")

def test_ssh_client_with_custom_port():
    """Test MikrotikSSHClient with custom port."""
    client = MikrotikSSHClient(
        hostname="192.168.1.1",
        username="admin",
        password="password",
        port=2222,
        timeout=30
    )
    
    assert client.port == 2222
    assert client.timeout == 30
    print("✓ MikrotikSSHClient custom port test passed")

def test_parse_interface_output():
    """Test parsing of interface output (mock data)."""
    # This is a simplified test - in real scenario, we'd need mock SSH connections
    print("✓ Interface parsing test placeholder executed")

def test_parse_bridge_output():
    """Test parsing of bridge port output (mock data)."""
    # This is a simplified test - in real scenario, we'd need mock SSH connections
    print("✓ Bridge parsing test placeholder executed")

def main():
    """Run all SSH tests."""
    print("Running SSH Module Tests...")
    
    try:
        test_ssh_client_initialization()
        test_ssh_client_with_custom_port()
        test_parse_interface_output()
        test_parse_bridge_output()
        
        print("\nAll SSH Module tests passed! ✓")
        return 0
    except Exception as e:
        print(f"\nSSH Module test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())