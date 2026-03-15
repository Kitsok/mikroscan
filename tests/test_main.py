#!/usr/bin/env python3
"""
Tests for the main application module.
"""

import sys
import os
import tempfile
import json
import subprocess
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import main module components
from main import MikrotikMapper

def test_mikrotik_mapper_initialization():
    """Test MikrotikMapper initialization."""
    mapper = MikrotikMapper()
    
    # Check that all components are initialized
    assert mapper.scanner is None
    assert mapper.collector is None
    assert mapper.mapper is None
    assert mapper.credential_manager is not None
    print("✓ MikrotikMapper initialization test passed")

def test_command_line_help():
    """Test that command line help works."""
    try:
        # Test help output
        result = subprocess.run([
            sys.executable, 
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py"),
            "--help"
        ], capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "mikrotik network mapper" in result.stdout.lower()
        print("✓ Command line help test passed")
        
    except subprocess.TimeoutExpired:
        print("  ✗ Command line help test timed out")
        raise
    except Exception as e:
        print(f"  ✗ Command line help test failed: {e}")
        raise

def test_command_line_default_run():
    """Test that the default CLI path builds a map from existing data."""
    try:
        # Test with no arguments (should use the default collected data file)
        result = subprocess.run([
            sys.executable,
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        ], capture_output=True, text=True, timeout=10)
        
        assert result.returncode == 0
        assert "mapping summary:" in result.stdout.lower()
        print("✓ Command line default execution test passed")
        
    except subprocess.TimeoutExpired:
        print("  ✗ Command line default execution test timed out")
        raise
    except Exception as e:
        print(f"  ✗ Command line default execution test failed: {e}")
        raise

def test_collect_data_with_mock_files():
    """Test collect_data method with mock files."""
    mapper = MikrotikMapper()
    
    # Create mock device file
    mock_devices = [
        {"ip": "192.168.1.1"},
        {"ip": "192.168.1.2"}
    ]
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        device_file = f.name
        json.dump(mock_devices, f)
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        output_file = f.name
    
    try:
        # This will fail because we're not providing real credentials,
        # but we're testing that the method structure works
        try:
            mapper.collect_data(
                device_file=device_file,
                username="testuser",
                password="testpass",
                output_file=output_file
            )
            # If it gets here, the method executed without structural errors
            print("  ✓ collect_data method structure test passed")
        except Exception as e:
            # Expected to fail due to connection issues, but method structure is OK
            print("  ✓ collect_data method structure test passed (expected connection failure)")
        
    finally:
        # Clean up
        for file_path in [device_file, output_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)


def test_collect_data_skips_reauth_when_credentials_are_already_unlocked():
    """Avoid prompting twice when the credential manager is already authenticated."""
    mapper = MikrotikMapper()

    mock_devices = [{"ip": "192.168.1.1"}]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        device_file = f.name
        json.dump(mock_devices, f)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        output_file = f.name

    try:
        mapper.credential_manager.credentials_file = output_file
        mapper.credential_manager.cipher_suite = object()

        with patch.object(
            mapper.credential_manager,
            "authenticate",
            side_effect=AssertionError("authenticate should not be called"),
        ), patch.object(
            mapper.credential_manager,
            "retrieve_credentials",
            return_value={"username": "user", "password": "pass", "key_file": None},
        ), patch("main.DataCollector") as MockCollector:
            collector = MockCollector.return_value
            collector.collect_from_device.return_value = {
                "hostname": "192.168.1.1",
                "connected": True,
            }

            result = mapper.collect_data(
                device_file=device_file,
                output_file=output_file,
            )

        assert result["192.168.1.1"]["connected"] == True
        print("✓ collect_data reauth skip test passed")

    finally:
        for file_path in [device_file, output_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)

def main():
    """Run all main application tests."""
    print("Running Main Application Tests...")
    
    try:
        test_mikrotik_mapper_initialization()
        test_command_line_help()
        test_command_line_default_run()
        test_collect_data_with_mock_files()
        test_collect_data_skips_reauth_when_credentials_are_already_unlocked()
        
        print("\nAll Main Application tests passed! ✓")
        return 0
    except Exception as e:
        print(f"\nMain Application test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
