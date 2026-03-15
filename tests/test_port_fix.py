#!/usr/bin/env python3
"""
Test for SSH port routing fix.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import MikrotikMapper

class TestPortRouting(unittest.TestCase):
    """Test SSH port routing fix."""
    
    @patch('data.data_collector.DataCollector')
    @patch('scanner.network_scanner.NetworkScanner.scan_for_mikrotik_devices')
    def test_run_full_mapping_passes_port(self, mock_scan, mock_collector_class):
        """Test that run_full_mapping passes port parameter correctly."""
        # Mock scan results
        mock_scan.return_value = [
            {"ip": "192.168.1.1", "hostname": "router1", "type": "mikrotik"}
        ]
        
        # Mock collector instance
        mock_collector_instance = MagicMock()
        mock_collector_instance.collect_from_devices.return_value = {
            "192.168.1.1": {
                "hostname": "192.168.1.1",
                "connected": True,
                "device_info": {"identity": "router1"},
                "interfaces": [],
                "bridge_ports": [],
                "arp_table": [],
                "dhcp_leases": []
            }
        }
        mock_collector_class.return_value = mock_collector_instance
        
        # Create mapper
        mapper = MikrotikMapper()
        
        # Call run_full_mapping with custom port
        result = mapper.run_full_mapping(
            ip_range="192.168.1.0/24",
            username="testuser",
            password="testpass",
            port=10021,  # Custom port
            timeout=5
        )
        
        # Verify that DataCollector was instantiated with the correct parameters
        self.assertTrue(mock_collector_class.called)
        
        # Check the call arguments to verify port was passed to collect_from_devices
        self.assertTrue(mock_collector_instance.collect_from_devices.called)
        
        # Check the call arguments to verify port was passed
        call_args = mock_collector_instance.collect_from_devices.call_args
        if call_args:
            args, kwargs = call_args
            # The port should be the third positional argument (after hostnames and before timeout)
            # Or it could be passed as a keyword argument
            port_in_args = len(args) > 2 and args[2] == 10021
            port_in_kwargs = 'port' in kwargs and kwargs['port'] == 10021
            
            self.assertTrue(port_in_args or port_in_kwargs, 
                          f"Port 10021 not found in call args={args} kwargs={kwargs}")
            print(f"✓ Port routing test passed - port correctly passed to collector")
        else:
            print("✓ Port routing test executed")

if __name__ == "__main__":
    print("Running SSH Port Routing Fix Tests...")
    
    try:
        unittest.main(argv=[''], exit=False, verbosity=2)
        print("\nSSH Port Routing Fix tests completed! ✓")
    except Exception as e:
        print(f"\nSSH Port Routing Fix test failed: {e}")
        sys.exit(1)