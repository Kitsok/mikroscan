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
    
    @patch('main.MikrotikMapper.generate_topology', return_value=True)
    @patch('main.MikrotikMapper.build_map', return_value={"devices": {}, "connections": [], "hosts": {}})
    @patch('main.MikrotikMapper.collect_data', return_value={})
    @patch('main.MikrotikMapper.scan_network')
    def test_run_full_mapping_passes_port(
        self,
        mock_scan_network,
        mock_collect_data,
        mock_build_map,
        mock_generate_topology,
    ):
        """Test that run_full_mapping passes port parameter correctly."""
        mock_scan_network.return_value = [
            {"ip": "192.168.1.1", "hostname": "router1", "type": "mikrotik"}
        ]
        mock_collect_data.return_value = {"192.168.1.1": {"connected": True}}
        
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
        
        self.assertTrue(mock_collect_data.called)

        call_args = mock_collect_data.call_args
        if call_args:
            args, kwargs = call_args
            port_in_args = len(args) > 5 and args[5] == 10021
            port_in_kwargs = 'port' in kwargs and kwargs['port'] == 10021
            
            self.assertTrue(port_in_args or port_in_kwargs, 
                          f"Port 10021 not found in call args={args} kwargs={kwargs}")
            print("✓ Port routing test passed - port correctly passed to collect_data")
        else:
            print("✓ Port routing test executed")

        mock_build_map.assert_called_once_with(
            data_file="data/collected_data.json",
            output_file="data/final_map.json",
            readable_file="data/connections.txt",
        )

        mock_generate_topology.assert_called_once_with(
            data_file="data/collected_data.json",
            output_file="data/topology.txt",
        )
        print("✓ Full mapping topology generation test passed")

    @patch('main.MikrotikMapper.generate_topology', return_value=True)
    @patch('main.MikrotikMapper.build_map', return_value={"devices": {}, "connections": [], "hosts": {}})
    @patch('main.MikrotikMapper.collect_data', return_value={"192.168.1.1": {"connected": True}})
    @patch('main.MikrotikMapper.scan_network', return_value=[{"ip": "192.168.1.1"}])
    def test_run_full_mapping_honors_output_paths(
        self,
        mock_scan_network,
        mock_collect_data,
        mock_build_map,
        mock_generate_topology,
    ):
        """run_full_mapping should honor caller-provided output paths."""
        mapper = MikrotikMapper()

        result = mapper.run_full_mapping(
            ip_range="192.168.1.0/24",
            output_file="custom/map.json",
            readable_file="custom/readable.txt",
            topology_file="custom/topology.txt",
        )

        self.assertTrue(result)
        mock_build_map.assert_called_once_with(
            data_file="data/collected_data.json",
            output_file="custom/map.json",
            readable_file="custom/readable.txt",
        )
        mock_generate_topology.assert_called_once_with(
            data_file="data/collected_data.json",
            output_file="custom/topology.txt",
        )
        print("✓ Full mapping output path test passed")
    
    @patch('main.NetworkScanner')
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

    @patch('main.NetworkScanner')
    def test_scan_network_returns_no_devices_when_results_cannot_be_saved(
        self,
        mock_scanner_class,
    ):
        """scan_network should not continue on stale results when saving fails."""
        mock_scanner_instance = MagicMock()
        mock_scanner_instance.scan_for_mikrotik_devices.return_value = []
        mock_scanner_class.return_value = mock_scanner_instance

        mapper = MikrotikMapper()
        result = mapper.scan_network(
            ip_range="192.168.1.0/24",
            output_file="data/scan_results.json",
        )

        self.assertEqual(result, [])
        mock_scanner_instance.scan_for_mikrotik_devices.assert_called_once_with(
            "192.168.1.0/24",
            "data/scan_results.json",
        )
        print("✓ Scan results save-failure propagation test passed")

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
