#!/usr/bin/env python3
"""
Test for SSH port routing fix and verbose mode.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import MikrotikMapper

class TestFeatures(unittest.TestCase):
    """Test features including SSH port routing and verbose mode."""
    
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
    
    @patch('scanner.network_scanner.NetworkScanner')
    def test_verbose_mode_scanner_creation(self, mock_scanner_class):
        """Test that verbose mode is passed to NetworkScanner."""
        # Mock scanner instance
        mock_scanner_instance = MagicMock()
        mock_scanner_instance.scan_for_mikrotik_devices.return_value = [
            {"ip": "192.168.1.1", "hostname": "router1", "type": "mikrotik"}
        ]
        mock_scanner_class.return_value = mock_scanner_instance
        
        # Create mapper
        mapper = MikrotikMapper()
        
        # Call scan_network with verbose=True
        result = mapper.scan_network(
            ip_range="192.168.1.0/24",
            verbose=True
        )
        
        # Verify that NetworkScanner was instantiated with verbose=True
        self.assertTrue(mock_scanner_class.called)
        call_args = mock_scanner_class.call_args
        if call_args:
            args, kwargs = call_args
            self.assertIn('verbose', kwargs)
            self.assertTrue(kwargs['verbose'])
            print("✓ Verbose mode test passed - verbose parameter correctly passed to scanner")
        else:
            print("✓ Verbose mode test executed")

if __name__ == "__main__":
    print("Running Feature Tests (SSH Port Routing and Verbose Mode)...")
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFeatures)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("\nAll feature tests completed successfully! ✓")
        sys.exit(0)
    else:
        print(f"\n{len(result.failures)} failures, {len(result.errors)} errors")
        sys.exit(1)