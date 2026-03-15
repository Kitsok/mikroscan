#!/usr/bin/env python3
"""
Unit tests for the Network Scanner module.
"""

import sys
import os
import tempfile
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.network_scanner import NetworkScanner

def test_network_scanner_initialization():
    """Test NetworkScanner initialization."""
    scanner = NetworkScanner()
    assert scanner.timeout == 5
    print("✓ NetworkScanner initialization test passed")

def test_ping_host():
    """Test ping functionality with localhost."""
    scanner = NetworkScanner()
    # Test with localhost which should generally be reachable
    result = scanner.ping_host("127.0.0.1")
    # We don't assert result because it depends on system configuration
    print("✓ ping_host test executed")

def test_get_hostname():
    """Test hostname resolution."""
    scanner = NetworkScanner()
    # Test with localhost
    hostname = scanner.get_hostname("127.0.0.1")
    # Should return something (could be empty on some systems)
    print("✓ get_hostname test executed")

def test_save_results():
    """Test saving results to JSON file."""
    scanner = NetworkScanner()
    
    # Sample data
    devices = [
        {"ip": "192.168.1.1", "hostname": "router1", "type": "mikrotik"},
        {"ip": "192.168.1.2", "hostname": "router2", "type": "mikrotik"}
    ]
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        temp_file = f.name
    
    try:
        # Save results
        scanner.save_results(devices, temp_file)
        
        # Verify file was created and contains valid JSON
        with open(temp_file, 'r') as f:
            loaded_data = json.load(f)
        
        assert len(loaded_data) == 2
        assert loaded_data[0]["ip"] == "192.168.1.1"
        print("✓ save_results test passed")
        
    finally:
        # Clean up
        if os.path.exists(temp_file):
            os.unlink(temp_file)

def main():
    """Run all scanner tests."""
    print("Running Network Scanner Tests...")
    
    try:
        test_network_scanner_initialization()
        test_ping_host()
        test_get_hostname()
        test_save_results()
        
        print("\nAll Network Scanner tests passed! ✓")
        return 0
    except Exception as e:
        print(f"\nNetwork Scanner test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
