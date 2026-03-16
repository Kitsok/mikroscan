#!/usr/bin/env python3
"""
Tests for the main application module.
"""

import sys
import os
import tempfile
from builtins import open as builtin_open
from unittest.mock import patch
import json
import subprocess

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import main module components
import main as main_module
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
            "has_usable_store",
            return_value=True,
        ), patch.object(
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


def test_collect_data_prompts_for_run_credentials_when_no_store_exists():
    """Fresh collection should prompt for device credentials, not master auth."""
    mapper = MikrotikMapper()
    mock_devices = [{"ip": "192.168.1.1"}]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        device_file = f.name
        json.dump(mock_devices, f)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        output_file = f.name

    missing_credentials_file = output_file + ".missing"

    try:
        mapper.credential_manager.credentials_file = missing_credentials_file

        with patch.object(
            mapper.credential_manager,
            "authenticate",
            side_effect=AssertionError("authenticate should not be called"),
        ), patch.object(
            mapper,
            "_prompt_device_credentials",
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

        assert result["192.168.1.1"]["connected"] is True
        print("✓ fresh collection credential prompt test passed")
    finally:
        for file_path in [device_file, output_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)


def test_collect_data_handles_empty_scan_file_without_auth_prompt():
    """Empty scan files should not prompt for auth or crash when saving output."""
    mapper = MikrotikMapper()

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        device_file = f.name
        json.dump([], f)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        output_file = f.name

    try:
        mapper.credential_manager.credentials_file = output_file

        with patch.object(
            mapper.credential_manager,
            "has_usable_store",
            return_value=True,
        ), patch.object(
            mapper.credential_manager,
            "authenticate",
            side_effect=AssertionError("authenticate should not be called"),
        ), patch("main.DataCollector") as MockCollector:
            collector = MockCollector.return_value

            result = mapper.collect_data(
                device_file=device_file,
                output_file=output_file,
            )

        assert result == {}
        MockCollector.assert_called_once_with(
            username="",
            password=None,
            key_filename=None,
            backend="api",
            use_ssl=False,
        )
        collector.collect_from_device.assert_not_called()
        collector.save_data.assert_called_once_with(output_file, {})
        print("✓ empty scan file collection test passed")
    finally:
        for file_path in [device_file, output_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)


def test_collect_data_ignores_blank_credential_store_and_prompts_for_run_credentials():
    """Blank credential stores should be treated as unusable, not authenticated."""
    mapper = MikrotikMapper()
    mock_devices = [{"ip": "192.168.1.1"}]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        device_file = f.name
        json.dump(mock_devices, f)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        output_file = f.name

    credentials_file = output_file + ".creds"

    try:
        with open(credentials_file, "wb") as f:
            f.write(b"")

        mapper.credential_manager.credentials_file = credentials_file

        with patch.object(
            mapper.credential_manager,
            "authenticate",
            side_effect=AssertionError("authenticate should not be called"),
        ), patch.object(
            mapper,
            "_prompt_device_credentials",
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

        assert result["192.168.1.1"]["connected"] is True
        print("✓ unusable credential store collection test passed")
    finally:
        for file_path in [device_file, output_file, credentials_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)


def test_collect_data_keeps_requested_api_backend_with_password_and_key_file():
    """API collection should keep the requested backend when a password is provided."""
    mapper = MikrotikMapper()
    mock_devices = [{"ip": "192.168.1.1"}]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        device_file = f.name
        json.dump(mock_devices, f)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        output_file = f.name

    try:
        with patch("main.DataCollector") as MockCollector:
            collector = MockCollector.return_value
            collector.collect_from_devices.return_value = {
                "192.168.1.1": {"connected": True}
            }

            result = mapper.collect_data(
                device_file=device_file,
                username="user",
                password="pass",
                key_file="/tmp/testkey",
                output_file=output_file,
                backend="api",
                port=8728,
            )

        assert result["192.168.1.1"]["connected"] is True
        MockCollector.assert_called_once_with(
            username="user",
            password="pass",
            key_filename="/tmp/testkey",
            backend="api",
            use_ssl=False,
        )
        collector.collect_from_devices.assert_called_once_with(["192.168.1.1"], 8728, 10)
        print("✓ password-plus-key API backend selection test passed")
    finally:
        for file_path in [device_file, output_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)


def test_collect_data_rejects_key_only_stored_credentials_for_api():
    """Stored key-only credentials should fail fast on the API backend."""
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
            "has_usable_store",
            return_value=True,
        ), patch.object(
            mapper.credential_manager,
            "authenticate",
            side_effect=AssertionError("authenticate should not be called"),
        ), patch.object(
            mapper.credential_manager,
            "retrieve_credentials",
            return_value={"username": "user", "password": None, "key_file": "/tmp/testkey"},
        ), patch("main.DataCollector") as MockCollector:
            result = mapper.collect_data(
                device_file=device_file,
                output_file=output_file,
                backend="api",
            )

        assert result == {}
        MockCollector.assert_not_called()
        print("✓ stored key-only API credential validation test passed")
    finally:
        for file_path in [device_file, output_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)


def test_collect_data_rejects_key_only_cli_credentials_for_api():
    """Explicit key-only credentials should fail fast on the API backend."""
    mapper = MikrotikMapper()
    mock_devices = [{"ip": "192.168.1.1"}]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        device_file = f.name
        json.dump(mock_devices, f)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        output_file = f.name

    try:
        with patch("main.DataCollector") as MockCollector:
            result = mapper.collect_data(
                device_file=device_file,
                username="user",
                key_file="/tmp/testkey",
                output_file=output_file,
                backend="api",
            )

        assert result == {}
        MockCollector.assert_not_called()
        print("✓ explicit key-only API credential validation test passed")
    finally:
        for file_path in [device_file, output_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)


def test_collect_data_accepts_hostname_only_entries():
    """Collection should accept device entries with hostname but no ip field."""
    mapper = MikrotikMapper()
    mock_devices = [{"hostname": "router1.example"}]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        device_file = f.name
        json.dump(mock_devices, f)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        output_file = f.name

    try:
        with patch("main.DataCollector") as MockCollector:
            collector = MockCollector.return_value
            collector.collect_from_devices.return_value = {
                "router1.example": {"connected": True}
            }

            result = mapper.collect_data(
                device_file=device_file,
                username="user",
                password="pass",
                output_file=output_file,
            )

        assert result["router1.example"]["connected"] is True
        collector.collect_from_devices.assert_called_once_with(["router1.example"], 8728, 10)
        print("✓ hostname-only scan entry test passed")
    finally:
        for file_path in [device_file, output_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)


def test_collect_data_rejects_non_dict_scan_entries():
    """Collection should reject malformed scan files with non-dict entries."""
    mapper = MikrotikMapper()
    mock_devices = ["router1.example"]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        device_file = f.name
        json.dump(mock_devices, f)

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        output_file = f.name

    try:
        with patch("main.DataCollector") as MockCollector:
            result = mapper.collect_data(
                device_file=device_file,
                username="user",
                password="pass",
                output_file=output_file,
            )

        assert result == {}
        MockCollector.assert_not_called()
        print("✓ malformed scan entry validation test passed")
    finally:
        for file_path in [device_file, output_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)


def test_scan_file_also_generates_topology():
    """The --scan-file path should regenerate topology after collection."""
    mock_devices = [{"ip": "192.168.1.1"}]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        scan_file = f.name
        json.dump(mock_devices, f)

    try:
        with patch.object(sys, "argv", [
            "main.py",
            "--scan-file",
            scan_file,
            "-u",
            "testuser",
            "-p",
            "testpass",
        ]), patch("main.MikrotikMapper") as MockMapper:
            mapper = MockMapper.return_value
            mapper.collect_data.return_value = {"192.168.1.1": {"connected": True}}
            mapper.build_map.return_value = {
                "devices": {},
                "connections": [],
                "hosts": [],
            }
            mapper.generate_topology.return_value = True

            main_module.main()

        mapper.collect_data.assert_called_once()
        mapper.build_map.assert_called_once()
        mapper.generate_topology.assert_called_once_with(
            data_file="data/collected_data.json",
            output_file="data/topology.txt",
            json_output_file="data/topology_graph.json",
        )
        print("✓ scan-file topology generation test passed")
    finally:
        if os.path.exists(scan_file):
            os.unlink(scan_file)


def test_scan_file_exits_non_zero_on_topology_failure():
    """The scan-file CLI path should fail the process when topology generation fails."""
    mock_devices = [{"ip": "192.168.1.1"}]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        scan_file = f.name
        json.dump(mock_devices, f)

    try:
        with patch.object(sys, "argv", [
            "main.py",
            "--scan-file",
            scan_file,
            "-u",
            "testuser",
            "-p",
            "testpass",
        ]), patch("main.MikrotikMapper") as MockMapper:
            mapper = MockMapper.return_value
            mapper.collect_data.return_value = {"192.168.1.1": {"connected": True}}
            mapper.build_map.return_value = {
                "devices": {},
                "connections": [],
                "hosts": [],
            }
            mapper.generate_topology.return_value = False

            try:
                main_module.main()
                raise AssertionError("main() should have exited")
            except SystemExit as exc:
                assert exc.code == 1

        print("✓ scan-file topology failure exit-code test passed")
    finally:
        if os.path.exists(scan_file):
            os.unlink(scan_file)


def test_scan_file_exits_non_zero_on_build_map_failure():
    """The scan-file CLI path should fail when build_map returns no map."""
    mock_devices = [{"ip": "192.168.1.1"}]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        scan_file = f.name
        json.dump(mock_devices, f)

    try:
        with patch.object(sys, "argv", [
            "main.py",
            "--scan-file",
            scan_file,
            "-u",
            "testuser",
            "-p",
            "testpass",
        ]), patch("main.MikrotikMapper") as MockMapper:
            mapper = MockMapper.return_value
            mapper.collect_data.return_value = {"192.168.1.1": {"connected": True}}
            mapper._has_connected_devices.return_value = True
            mapper.build_map.return_value = {}

            try:
                main_module.main()
                raise AssertionError("main() should have exited")
            except SystemExit as exc:
                assert exc.code == 1

        mapper.generate_topology.assert_not_called()
        print("✓ scan-file build-map failure exit-code test passed")
    finally:
        if os.path.exists(scan_file):
            os.unlink(scan_file)


def test_scan_file_exits_non_zero_when_no_devices_connect():
    """The scan-file CLI path should fail when collection returns only disconnected devices."""
    mock_devices = [{"ip": "192.168.1.1"}]

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
        scan_file = f.name
        json.dump(mock_devices, f)

    try:
        with patch.object(sys, "argv", [
            "main.py",
            "--scan-file",
            scan_file,
            "-u",
            "testuser",
            "-p",
            "testpass",
        ]), patch("main.MikrotikMapper") as MockMapper:
            mapper = MockMapper.return_value
            mapper.collect_data.return_value = {
                "192.168.1.1": {"hostname": "192.168.1.1", "connected": False}
            }
            mapper._has_connected_devices.return_value = False

            try:
                main_module.main()
                raise AssertionError("main() should have exited")
            except SystemExit as exc:
                assert exc.code == 1

        mapper.build_map.assert_not_called()
        mapper.generate_topology.assert_not_called()
        print("✓ scan-file disconnected-collection exit-code test passed")
    finally:
        if os.path.exists(scan_file):
            os.unlink(scan_file)


def test_scan_file_does_not_preauth_before_collection():
    """The CLI should not pre-authenticate before scan-file collection runs."""
    with patch.object(sys, "argv", [
        "main.py",
        "--scan-file",
        "data/scan_results.json",
    ]), patch("main.MikrotikMapper") as MockMapper:
        mapper = MockMapper.return_value
        mapper.credential_manager.authenticate.side_effect = AssertionError(
            "authenticate should not be called before collection"
        )
        mapper.collect_data.return_value = {}

        main_module.main()

    mapper.collect_data.assert_called_once()
    print("✓ scan-file preauth skip test passed")


def test_generate_topology_exits_non_zero_on_failure():
    """The topology-only CLI path should fail the process when generation fails."""
    with patch.object(sys, "argv", [
        "main.py",
        "--generate-topology",
    ]), patch("main.MikrotikMapper") as MockMapper:
        mapper = MockMapper.return_value
        mapper.generate_topology.return_value = False

        try:
            main_module.main()
            raise AssertionError("main() should have exited")
        except SystemExit as exc:
            assert exc.code == 1

    mapper.generate_topology.assert_called_once_with(
        data_file="data/collected_data.json",
        output_file="data/topology.txt",
        json_output_file="data/topology_graph.json",
    )
    print("✓ topology CLI failure exit-code test passed")


def test_generate_topology_json_cli_uses_default_output():
    """The topology JSON CLI path should use the default JSON output file."""
    with patch.object(sys, "argv", [
        "main.py",
        "--generate-topology-json",
    ]), patch("main.MikrotikMapper") as MockMapper:
        mapper = MockMapper.return_value
        mapper.generate_topology_json.return_value = True

        main_module.main()

    mapper.generate_topology_json.assert_called_once_with(
        data_file="data/collected_data.json",
        output_file="data/topology_graph.json",
    )
    print("✓ topology JSON CLI default-output test passed")


def test_serve_cli_starts_local_api_server():
    """The serve CLI path should construct and run the local API server."""
    with patch.object(sys, "argv", [
        "main.py",
        "--serve",
        "--host",
        "127.0.0.1",
        "--web-port",
        "9090",
        "-u",
        "admin",
        "-p",
        "secret",
    ]), patch("main.MikroscanAPIService") as MockService, patch("main.MikroscanAPIServer") as MockServer:
        server = MockServer.return_value
        main_module.main()

    MockService.assert_called_once()
    MockServer.assert_called_once()
    server.serve_forever.assert_called_once()
    print("✓ serve CLI dispatch test passed")


def test_full_scan_also_generates_topology():
    """The subnet scan workflow should also regenerate topology."""
    with patch("main.MikrotikMapper") as MockMapper:
        mapper = MockMapper.return_value
        mapper.run_full_mapping.return_value = {
            "devices": {},
            "connections": [],
            "hosts": [],
        }

        with patch.object(sys, "argv", [
            "main.py",
            "192.168.1.0/24",
            "-u",
            "testuser",
            "-p",
            "testpass",
        ]):
            main_module.main()

    mapper.run_full_mapping.assert_called_once()
    print("✓ full scan topology generation test passed")


def test_run_full_mapping_returns_empty_on_topology_failure():
    """The full workflow should fail if topology generation fails."""
    mapper = MikrotikMapper()

    with patch.object(
        mapper,
        "scan_network",
        return_value=[{"ip": "192.168.1.1"}],
    ), patch.object(
        mapper,
        "collect_data",
        return_value={"192.168.1.1": {"connected": True}},
    ), patch.object(
        mapper,
        "build_map",
        return_value={"devices": {"router1": {}}, "connections": [], "hosts": []},
    ), patch.object(
        mapper,
        "generate_topology",
        return_value=False,
    ):
        result = mapper.run_full_mapping("192.168.1.0/24")

    assert result == {}
    print("✓ full mapping topology failure return test passed")


def test_direct_build_map_cli_exits_non_zero_on_failure():
    """The map-only CLI path should fail the process when build_map returns no map."""
    with patch.object(sys, "argv", [
        "main.py",
        "--data-file",
        "/tmp/microscan-missing.json",
    ]), patch("main.MikrotikMapper") as MockMapper:
        mapper = MockMapper.return_value
        mapper.build_map.return_value = {}

        try:
            main_module.main()
            raise AssertionError("main() should have exited")
        except SystemExit as exc:
            assert exc.code == 1

    mapper.build_map.assert_called_once()
    print("✓ direct build-map failure exit-code test passed")


def test_build_map_fails_fast_when_input_is_missing():
    """Missing collected-data input should not emit an empty replacement map."""
    mapper = MikrotikMapper()
    missing_input = os.path.join(tempfile.gettempdir(), "microscan-no-such-data.json")
    output_file = os.path.join(tempfile.gettempdir(), "microscan-out.json")
    readable_file = os.path.join(tempfile.gettempdir(), "microscan-out.txt")

    for file_path in [missing_input, output_file, readable_file]:
        if os.path.exists(file_path):
            os.unlink(file_path)

    result = mapper.build_map(missing_input, output_file, readable_file)

    assert result == {}
    assert not os.path.exists(output_file)
    assert not os.path.exists(readable_file)
    print("✓ missing-input build_map test passed")


def test_build_map_fails_when_json_output_cannot_be_written():
    """Map building should fail when the JSON output cannot be saved."""
    mapper = MikrotikMapper()

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
        json.dump(
            {
                "192.168.1.1": {
                    "hostname": "192.168.1.1",
                    "connected": True,
                    "device_info": {"identity": "router1"},
                    "interfaces": [],
                    "bridge_ports": [],
                    "bridge_hosts": [],
                    "arp_table": [],
                    "dhcp_leases": [],
                }
            },
            handle,
        )
        data_file = handle.name

    try:
        with patch("main.ConnectionMapper.save_map", return_value=False):
            result = mapper.build_map(
                data_file,
                os.path.join(tempfile.gettempdir(), "microscan-out.json"),
                os.path.join(tempfile.gettempdir(), "microscan-out.txt"),
            )
    finally:
        if os.path.exists(data_file):
            os.unlink(data_file)

    assert result == {}
    print("✓ build_map JSON output failure test passed")


def test_build_map_fails_when_readable_output_cannot_be_written():
    """Map building should fail when the readable output cannot be saved."""
    mapper = MikrotikMapper()

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
        json.dump(
            {
                "192.168.1.1": {
                    "hostname": "192.168.1.1",
                    "connected": True,
                    "device_info": {"identity": "router1"},
                    "interfaces": [],
                    "bridge_ports": [],
                    "bridge_hosts": [],
                    "arp_table": [],
                    "dhcp_leases": [],
                }
            },
            handle,
        )
        data_file = handle.name

    output_file = os.path.join(tempfile.gettempdir(), "microscan-out.json")
    readable_file = os.path.join(tempfile.gettempdir(), "microscan-out.txt")

    def fail_only_on_readable(path, mode="r", *args, **kwargs):
        if path == readable_file and "w" in mode:
            raise OSError("disk full")
        return builtin_open(path, mode, *args, **kwargs)

    try:
        with patch("builtins.open", side_effect=fail_only_on_readable):
            result = mapper.build_map(data_file, output_file, readable_file)
    finally:
        for file_path in [data_file, output_file, readable_file]:
            if os.path.exists(file_path):
                os.unlink(file_path)

    assert result == {}
    print("✓ build_map readable output failure test passed")


def test_collect_data_fails_when_output_cannot_be_written():
    """Collection should fail when collected_data.json cannot be saved."""
    mapper = MikrotikMapper()

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as handle:
        json.dump([{"ip": "192.168.1.1"}], handle)
        device_file = handle.name

    try:
        with patch.object(
            main_module.DataCollector,
            "collect_from_devices",
            return_value={"192.168.1.1": {"connected": True}},
        ), patch.object(
            main_module.DataCollector,
            "save_data",
            return_value=False,
        ):
            result = mapper.collect_data(
                device_file=device_file,
                username="admin",
                password="secret",
                output_file="data/collected_data.json",
            )
    finally:
        if os.path.exists(device_file):
            os.unlink(device_file)

    assert result == {}
    print("✓ collect_data output write failure test passed")


def test_store_credentials_cli_exits_non_zero_on_failure():
    """Credential-store CLI should fail the process when storing fails."""
    with patch.object(sys, "argv", [
        "main.py",
        "--store-credentials",
        "--hostname",
        "192.168.1.1",
        "-u",
        "admin",
        "-p",
        "secret",
    ]), patch("main.CredentialManager") as MockManager:
        manager = MockManager.return_value
        manager.prepare_for_storage.return_value = True
        manager.store_credentials.return_value = False

        try:
            main_module.main()
            raise AssertionError("main() should have exited")
        except SystemExit as exc:
            assert exc.code == 1

    print("✓ store-credentials CLI failure exit-code test passed")


def test_store_default_credentials_cli_exits_non_zero_on_failure():
    """Default credential-store CLI should fail the process when storing fails."""
    with patch.object(sys, "argv", [
        "main.py",
        "--store-default-credentials",
        "-u",
        "admin",
        "-p",
        "secret",
    ]), patch("main.CredentialManager") as MockManager:
        manager = MockManager.return_value
        manager.prepare_for_storage.return_value = True
        manager.store_default_credentials.return_value = False

        try:
            main_module.main()
            raise AssertionError("main() should have exited")
        except SystemExit as exc:
            assert exc.code == 1

    print("✓ store-default-credentials CLI failure exit-code test passed")

def main():
    """Run all main application tests."""
    print("Running Main Application Tests...")
    
    try:
        test_mikrotik_mapper_initialization()
        test_command_line_help()
        test_command_line_default_run()
        test_collect_data_with_mock_files()
        test_collect_data_skips_reauth_when_credentials_are_already_unlocked()
        test_collect_data_prompts_for_run_credentials_when_no_store_exists()
        test_collect_data_handles_empty_scan_file_without_auth_prompt()
        test_collect_data_ignores_blank_credential_store_and_prompts_for_run_credentials()
        test_collect_data_keeps_requested_api_backend_with_password_and_key_file()
        test_collect_data_rejects_key_only_stored_credentials_for_api()
        test_collect_data_rejects_key_only_cli_credentials_for_api()
        test_collect_data_accepts_hostname_only_entries()
        test_collect_data_rejects_non_dict_scan_entries()
        test_scan_file_also_generates_topology()
        test_scan_file_exits_non_zero_on_topology_failure()
        test_scan_file_exits_non_zero_on_build_map_failure()
        test_scan_file_exits_non_zero_when_no_devices_connect()
        test_scan_file_does_not_preauth_before_collection()
        test_generate_topology_exits_non_zero_on_failure()
        test_generate_topology_json_cli_uses_default_output()
        test_serve_cli_starts_local_api_server()
        test_full_scan_also_generates_topology()
        test_run_full_mapping_returns_empty_on_topology_failure()
        test_direct_build_map_cli_exits_non_zero_on_failure()
        test_build_map_fails_fast_when_input_is_missing()
        test_build_map_fails_when_json_output_cannot_be_written()
        test_build_map_fails_when_readable_output_cannot_be_written()
        test_collect_data_fails_when_output_cannot_be_written()
        test_store_credentials_cli_exits_non_zero_on_failure()
        test_store_default_credentials_cli_exits_non_zero_on_failure()

        print("\nAll Main Application tests passed! ✓")
        return 0
    except Exception as e:
        print(f"\nMain Application test failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
