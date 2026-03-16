#!/usr/bin/env python3
"""
Main application for Mikrotik Mapper.
Coordinates all modules and provides command-line interface.
"""

import argparse
import getpass
import json
import logging
import os
import sys
from typing import List

from lib.network_scanner import NetworkScanner
from lib.data_collector import DataCollector
from lib.connection_mapper import ConnectionMapper
from lib.credential_manager import CredentialManager
from lib.topology_builder import TopologyBuilder
from lib.web_api import MicroscanAPIService, MicroscanAPIServer

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
DEFAULT_DATA_FILE = "data/collected_data.json"
DEFAULT_SCAN_FILE = "data/scan_results.json"
DEFAULT_TOPOLOGY_JSON_FILE = "data/topology_graph.json"
DEFAULT_LAYOUT_FILE = "data/topology_layout.json"

class MikrotikMapper:
    """Main application class for Mikrotik network mapping."""
    
    def __init__(self):
        """Initialize the Mikrotik mapper."""
        self.scanner = None
        self.collector = None
        self.mapper = None
        self.credential_manager = CredentialManager()

    def _prompt_device_credentials(self) -> dict:
        """Prompt interactively for device credentials for the current run."""
        username = input("Device Username: ").strip()
        if not username:
            logger.error("Device username is required")
            return {}

        password = getpass.getpass("Device Password: ")
        return {
            "username": username,
            "password": password,
            "key_file": None,
        }

    def _has_connected_devices(self, collected_data: dict) -> bool:
        """Return True when at least one collected device connected successfully."""
        if not isinstance(collected_data, dict):
            return False

        return any(
            isinstance(device_data, dict) and device_data.get("connected", False)
            for device_data in collected_data.values()
        )

    def scan_network(self, ip_range: str, output_file: str = "data/mikrotik_devices.json", 
                     timeout: int = 5, verbose: bool = False) -> List[dict]:
        """
        Scan network for Mikrotik devices.
        
        Args:
            ip_range (str): IP range to scan (CIDR notation)
            output_file (str): File to save scan results
            timeout (int): Timeout for network operations
            verbose (bool): Enable verbose output
            
        Returns:
            List[dict]: List of discovered Mikrotik devices
        """
        logger.info(f"Scanning network range: {ip_range}")
        
        self.scanner = NetworkScanner(timeout=timeout, verbose=verbose)
        devices = self.scanner.scan_for_mikrotik_devices(ip_range, output_file)
        
        logger.info(f"Scan complete. Found {len(devices)} potential Mikrotik devices.")
        return devices
    
    def collect_data(self, device_file: str, username: str = None, password: str = None,
                     key_file: str = None, output_file: str = "data/device_data.json",
                     port: int = 8728, timeout: int = 10, backend: str = "api",
                     use_api_ssl: bool = False) -> dict:
        """
        Collect data from Mikrotik devices.
        
        Args:
            device_file (str): JSON file with device information from scan
            username (str): SSH username (optional if using stored credentials)
            password (str, optional): SSH password
            key_file (str, optional): Private key file
            output_file (str): File to save collected data
            port (int): Requested backend port
            timeout (int): Connection timeout
            backend (str): Collection backend
            use_api_ssl (bool): Use TLS with the RouterOS API backend
            
        Returns:
            dict: Collected device data
        """
        logger.info(f"Loading device list from {device_file}")
        
        # Load device list
        try:
            with open(device_file, 'r') as f:
                devices = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load device list from {device_file}: {e}")
            return {}
        
        # Extract hostnames/IPs
        hostnames = []
        for device in devices:
            if not isinstance(device, dict):
                logger.error(f"Invalid device entry in {device_file}: {device}")
                return {}
            endpoint = device.get("ip") or device.get("hostname")
            if not endpoint:
                logger.error(f"Invalid device entry in {device_file}: {device}")
                return {}
            hostnames.append(endpoint)
        logger.info(f"Collecting data from {len(hostnames)} devices")

        if not hostnames:
            logger.warning(f"No devices found in {device_file}")
            self.collector = DataCollector(
                username=username or "",
                password=password,
                key_filename=key_file,
                backend=backend,
                use_ssl=use_api_ssl if backend == "api" else False,
            )
            if not self.collector.save_data(output_file, {}):
                logger.error(f"Failed to save empty collection output to {output_file}")
            return {}
        
        # If no username provided, try to get stored credentials
        if not username:
            credentials_file_exists = self.credential_manager.has_usable_store()
            prompted_credentials = None

            if credentials_file_exists and not self.credential_manager.cipher_suite:
                # Authenticate with master password
                if not self.credential_manager.authenticate():
                    logger.error("Failed to authenticate with master password")
                    return {}

            # Use stored credentials for each device when available and
            # fall back to a single interactive prompt for the current run.
            all_data = {}
            for hostname in hostnames:
                cred_data = {}
                if credentials_file_exists:
                    cred_data = self.credential_manager.retrieve_credentials(hostname)

                if not cred_data:
                    if prompted_credentials is None:
                        logger.warning(
                            f"No stored credentials available for {hostname}. "
                            "Prompting for device credentials for this run."
                        )
                        prompted_credentials = self._prompt_device_credentials()

                    if not prompted_credentials:
                        logger.error("No device credentials available for data collection")
                        return {}

                    cred_data = prompted_credentials

                if (
                    backend == "api"
                    and cred_data.get("key_file")
                    and not cred_data.get("password")
                ):
                    logger.error(
                        "Stored credentials for %s only provide SSH key auth, "
                        "but the RouterOS API backend requires a password",
                        hostname,
                    )
                    return {}
                
                self.collector = DataCollector(
                    username=cred_data.get("username", ""),
                    password=cred_data.get("password"),
                    key_filename=cred_data.get("key_file"),
                    backend=backend,
                    use_ssl=use_api_ssl if backend == "api" else False,
                )

                # Collect data from this device
                device_data = self.collector.collect_from_device(
                    hostname,
                    port,
                    timeout,
                )
                all_data[hostname] = device_data
            
            data = all_data
        else:
            if backend == "api" and key_file and not password:
                logger.error(
                    "The RouterOS API backend requires a password; "
                    "SSH key-only credentials are not supported"
                )
                return {}

            # Create data collector with provided credentials
            self.collector = DataCollector(
                username=username,
                password=password,
                key_filename=key_file,
                backend=backend,
                use_ssl=use_api_ssl if backend == "api" else False,
            )

            # Collect data
            data = self.collector.collect_from_devices(
                hostnames,
                port,
                timeout,
            )
        
        # Save data
        if not self.collector.save_data(output_file, data):
            logger.error(f"Failed to save collected data to {output_file}")
            return {}
        
        logger.info("Data collection complete")
        return data
    
    def build_map(self, data_file: str, output_file: str = "data/final_map.json",
                  readable_file: str = "data/connections.txt") -> dict:
        """
        Build connection map from collected data.
        
        Args:
            data_file (str): JSON file with collected device data
            output_file (str): File to save connection map (JSON)
            readable_file (str): File to save human-readable connections
            
        Returns:
            dict: Connection map
        """
        logger.info(f"Building connection map from {data_file}")
        if not os.path.exists(data_file):
            logger.error(f"Collected data file does not exist: {data_file}")
            return {}
        
        # Create connection mapper
        self.mapper = ConnectionMapper()
        
        # Load data and build map
        loaded_data = self.mapper.load_data(data_file)
        if loaded_data is None:
            logger.error(f"Failed to load collected data from {data_file}")
            return {}
        connection_map = self.mapper.build_connection_map()
        
        # Save JSON map
        if not self.mapper.save_map(output_file, connection_map):
            logger.error(f"Failed to save connection map output to {output_file}")
            return {}
        
        # Generate and save readable output
        descriptions = self.mapper.generate_readable_output()
        try:
            output_dir = os.path.dirname(readable_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(readable_file, 'w') as f:
                for desc in descriptions:
                    f.write(desc + '\n')
            logger.info(f"Readable connection descriptions saved to {readable_file}")
        except Exception as e:
            logger.error(f"Failed to save readable output to {readable_file}: {e}")
            return {}
        
        logger.info("Connection map building complete")
        return connection_map
    
    def generate_topology(self, data_file: str = DEFAULT_DATA_FILE,
                          output_file: str = "data/topology.txt",
                          json_output_file: str = DEFAULT_TOPOLOGY_JSON_FILE):
        """
        Generate network topology from collected data.
        
        Args:
            data_file (str): JSON file with collected device data
            output_file (str): Output file for topology
            json_output_file (str): Output file for structured topology JSON
        """
        logger.info(f"Generating topology from {data_file}")

        builder = TopologyBuilder()
        if builder.build_complete_topology(data_file, output_file, json_output_file):
            logger.info("Topology generation complete")
            return True

        logger.error("Failed to generate topology")
        return False

    def generate_topology_json(
        self,
        data_file: str = DEFAULT_DATA_FILE,
        output_file: str = DEFAULT_TOPOLOGY_JSON_FILE,
    ) -> bool:
        """Generate only the structured topology JSON model."""
        logger.info(f"Generating structured topology JSON from {data_file}")

        builder = TopologyBuilder()
        if not builder.load_data(data_file):
            logger.error("Failed to load topology input data")
            return False

        builder.build_mac_name_map()
        builder.build_mac_ip_map()
        builder.build_ip_name_map()
        builder.build_mac_port_map()
        topology_model = builder.build_topology_model()
        if not builder.save_topology_model(output_file, topology_model):
            logger.error("Failed to save structured topology JSON")
            return False

        logger.info("Structured topology JSON generation complete")
        return True
    
    def run_full_mapping(self, ip_range: str, username: str = None, password: str = None,
                         key_file: str = None, port: int = 8728, timeout: int = 5,
                         verbose: bool = False, backend: str = "api",
                         use_api_ssl: bool = False,
                         output_file: str = "data/final_map.json",
                         readable_file: str = "data/connections.txt",
                         topology_file: str = "data/topology.txt",
                         topology_json_file: str = DEFAULT_TOPOLOGY_JSON_FILE) -> dict:
        """
        Run complete network mapping workflow.
        
        Args:
            ip_range (str): IP range to scan (CIDR notation)
            username (str): SSH username
            password (str, optional): SSH password
            key_file (str, optional): Private key file
            port (int): Requested backend port
            timeout (int): Timeout for operations
            verbose (bool): Enable verbose output
            backend (str): Collection backend
            use_api_ssl (bool): Use TLS with the RouterOS API backend
            output_file (str): File to save connection map (JSON)
            readable_file (str): File to save human-readable connections
            topology_file (str): File to save generated topology
            topology_json_file (str): File to save structured topology JSON
            
        Returns:
            dict: Final connection map
        """
        logger.info("Running full network mapping workflow")
        
        # Step 1: Scan network
        devices = self.scan_network(
            ip_range=ip_range,
            output_file="data/scan_results.json",
            timeout=timeout,
            verbose=verbose
        )
        
        if not devices:
            logger.warning("No Mikrotik devices found. Exiting.")
            return {}
        
        # Step 2: Collect data
        data = self.collect_data(
            device_file="data/scan_results.json",
            username=username,
            password=password,
            key_file=key_file,
            output_file="data/collected_data.json",
            port=port,
            timeout=timeout + 5,  # Give more time for data collection
            backend=backend,
            use_api_ssl=use_api_ssl,
        )

        if not self._has_connected_devices(data):
            logger.warning("No device data collected. Exiting.")
            return {}
        
        # Step 3: Build map
        connection_map = self.build_map(
            data_file="data/collected_data.json",
            output_file=output_file,
            readable_file=readable_file
        )
        if not connection_map:
            logger.warning("Connection map generation failed. Exiting.")
            return {}

        topology_generated = self.generate_topology(
            data_file=DEFAULT_DATA_FILE,
            output_file=topology_file,
            json_output_file=topology_json_file,
        )

        if not topology_generated:
            logger.warning("Full network mapping completed without topology output")
            return {}

        logger.info("Full network mapping workflow complete")
        return connection_map
    
def main():
    """Main command-line interface."""
    parser = argparse.ArgumentParser(
        description="Mikrotik Network Mapper - Maps connections between Mikrotik devices and hosts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scan network and map connections
  python3 main.py 192.168.1.0/24 -u admin -p password
  
  # Use existing scan results
  python3 main.py --scan-file -u admin -p password

  # Use native RouterOS API instead of SSH
  python3 main.py --scan-file --backend api --api-port 8728 -u admin -p password
  
  # Build map from existing collected data
  python3 main.py --data-file data/collected_data.json
  
  # Generate network topology
  python3 main.py --generate-topology
  
  # Store default credentials (will prompt for username/password)
  python3 main.py --store-default-credentials
  
  # Store credentials for specific host (will prompt for username/password)
  python3 main.py --store-credentials --hostname 192.168.1.1
        """
    )
    
    # Network scanning options
    parser.add_argument(
        "ip_range",
        nargs="?",
        help="IP range to scan for Mikrotik devices (CIDR notation)"
    )
    
    # Input file options
    parser.add_argument(
        "--scan-file",
        nargs="?",
        const=DEFAULT_SCAN_FILE,
        help="Use existing scan results file (default: data/scan_results.json)"
    )
    
    parser.add_argument(
        "--data-file",
        help="Use existing collected data file"
    )
    
    parser.add_argument(
        "--generate-topology",
        action="store_true",
        help="Generate network topology from collected data"
    )

    parser.add_argument(
        "--generate-topology-json",
        action="store_true",
        help="Generate structured topology JSON from collected data"
    )

    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run the local HTTP API server"
    )
    
    # Credential management
    parser.add_argument(
        "--store-credentials",
        action="store_true",
        help="Store credentials for a host (requires --hostname)"
    )
    
    parser.add_argument(
        "--store-default-credentials",
        action="store_true",
        help="Store default credentials for all hosts"
    )
    
    parser.add_argument(
        "--hostname",
        help="Hostname or IP address for credential storage"
    )
    
    # SSH authentication
    parser.add_argument(
        "-u", "--username",
        help="Device username for MikroTik access (prompted for --store-* if omitted)"
    )
    
    parser.add_argument(
        "-p", "--password",
        help="Device password for MikroTik access"
    )
    
    parser.add_argument(
        "-k", "--key-file",
        help="Private key file for SSH authentication"
    )
    
    # Network options
    parser.add_argument(
        "--backend",
        choices=["ssh", "api"],
        default="api",
        help="Collection backend for live device access (default: api)"
    )

    parser.add_argument(
        "--ssh-port",
        type=int,
        default=22,
        help="SSH port (default: 22)"
    )

    parser.add_argument(
        "--api-port",
        type=int,
        default=8728,
        help="RouterOS API port (default: 8728)"
    )

    parser.add_argument(
        "--api-ssl",
        dest="api_ssl",
        action="store_true",
        default=False,
        help="Use TLS for the native RouterOS API backend"
    )

    parser.add_argument(
        "--no-api-ssl",
        dest="api_ssl",
        action="store_false",
        help="Disable TLS for the native RouterOS API backend (default)"
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host/interface for the local HTTP API server (default: 127.0.0.1)"
    )

    parser.add_argument(
        "--web-port",
        type=int,
        default=8080,
        help="Port for the local HTTP API server (default: 8080)"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Network timeout in seconds (default: 10)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output, particularly for scanning process"
    )
    
    # Output options
    parser.add_argument(
        "-o", "--output",
        default="data/final_map.json",
        help="Output file for connection map (default: data/final_map.json)"
    )
    
    parser.add_argument(
        "--readable-output",
        default="data/connections.txt",
        help="File for human-readable connections (default: data/connections.txt)"
    )

    parser.add_argument(
        "--topology-json-output",
        default=DEFAULT_TOPOLOGY_JSON_FILE,
        help=f"Output file for structured topology JSON (default: {DEFAULT_TOPOLOGY_JSON_FILE})"
    )
    
    args = parser.parse_args()
    
    # Set up logging level based on verbose flag
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Handle credential storage
    if args.store_credentials:
        if not args.hostname:
            parser.error("--store-credentials requires --hostname")
        
        # Get username if not provided
        username = args.username
        if not username:
            username = input("Device Username: ").strip()
            if not username:
                parser.error("--store-credentials requires username")
        
        # Get password if not provided
        password = args.password
        if not password and not args.key_file:
            password = getpass.getpass("Device Password: ")
        
        # Create credential manager and store credentials
        cred_manager = CredentialManager()
        if cred_manager.prepare_for_storage():
            if cred_manager.store_credentials(args.hostname, username, password, args.key_file):
                print(f"Credentials for {args.hostname} stored successfully")
            else:
                print(f"Failed to store credentials for {args.hostname}")
                sys.exit(1)
        else:
            print("Failed to unlock credential store")
            sys.exit(1)
        return
    
    # Handle default credential storage
    if args.store_default_credentials:
        # Get username if not provided
        username = args.username
        if not username:
            username = input("Device Username: ").strip()
            if not username:
                parser.error("--store-default-credentials requires username")
        
        # Get password if not provided
        password = args.password
        if not password and not args.key_file:
            password = getpass.getpass("Device Password: ")
        
        # Create credential manager and store default credentials
        cred_manager = CredentialManager()
        if cred_manager.prepare_for_storage():
            if cred_manager.store_default_credentials(username, password, args.key_file):
                print("Default credentials stored successfully")
            else:
                print("Failed to store default credentials")
                sys.exit(1)
        else:
            print("Failed to unlock credential store")
            sys.exit(1)
        return
    
    # Handle topology generation (doesn't need authentication)
    if args.generate_topology:
        mapper = MikrotikMapper()
        logger.info("Generating network topology")
        if not mapper.generate_topology(
            data_file=args.data_file or DEFAULT_DATA_FILE,
            output_file="data/topology.txt",
            json_output_file=args.topology_json_output,
        ):
            sys.exit(1)
        return

    if args.generate_topology_json:
        mapper = MikrotikMapper()
        logger.info("Generating structured topology JSON")
        if not mapper.generate_topology_json(
            data_file=args.data_file or DEFAULT_DATA_FILE,
            output_file=args.topology_json_output,
        ):
            sys.exit(1)
        return
    
    # Create mapper
    mapper = MikrotikMapper()

    needs_live_collection = bool(args.ip_range or args.scan_file or args.serve)
    # Get password if needed and not provided
    if needs_live_collection and args.username and not args.password and not args.key_file:
        args.password = getpass.getpass("Device Password: ")

    collection_port = args.api_port if args.backend == "api" else args.ssh_port
    connection_map = {}
    
    try:
        if args.serve:
            if not args.username and mapper.credential_manager.has_usable_store():
                logger.info("Unlocking credential store for local API server")
                if not mapper.credential_manager.authenticate():
                    logger.error("Failed to unlock credential store for API server")
                    sys.exit(1)

            service = MicroscanAPIService(
                mapper,
                scan_file=args.scan_file or DEFAULT_SCAN_FILE,
                data_file=args.data_file or DEFAULT_DATA_FILE,
                map_output=args.output,
                readable_output=args.readable_output,
                topology_output="data/topology.txt",
                topology_json_output=args.topology_json_output,
                layout_output=DEFAULT_LAYOUT_FILE,
                username=args.username,
                password=args.password,
                key_file=args.key_file,
                backend=args.backend,
                collection_port=collection_port,
                timeout=args.timeout,
                verbose=args.verbose,
                use_api_ssl=args.api_ssl,
            )
            server = MicroscanAPIServer(args.host, args.web_port, service)
            server.serve_forever()
            return

        if args.scan_file:
            # Collect data and build map
            logger.info("Collecting data, building map, and generating topology from scan file")
            collected_data = mapper.collect_data(
                device_file=args.scan_file,
                username=args.username,
                password=args.password,
                key_file=args.key_file,
                output_file="data/collected_data.json",
                port=collection_port,
                timeout=args.timeout,
                backend=args.backend,
                use_api_ssl=args.api_ssl,
            )
            
            if mapper._has_connected_devices(collected_data):
                connection_map = mapper.build_map(
                    data_file=DEFAULT_DATA_FILE,
                    output_file=args.output,
                    readable_file=args.readable_output
                )
                if not connection_map:
                    sys.exit(1)
                if not mapper.generate_topology(
                    data_file=DEFAULT_DATA_FILE,
                    output_file="data/topology.txt",
                    json_output_file=args.topology_json_output,
                ):
                    sys.exit(1)
            else:
                logger.warning("No data collected from scan file input")
                sys.exit(1)

        elif args.ip_range:
            # Run full workflow
            logger.info("Running full network mapping workflow")
            connection_map = mapper.run_full_mapping(
                ip_range=args.ip_range,
                username=args.username,
                password=args.password,
                key_file=args.key_file,
                port=collection_port,
                timeout=args.timeout,
                verbose=args.verbose,
                backend=args.backend,
                use_api_ssl=args.api_ssl,
                output_file=args.output,
                readable_file=args.readable_output,
                topology_file="data/topology.txt",
                topology_json_file=args.topology_json_output,
            )
            if not connection_map:
                sys.exit(1)

        else:
            # Directly build map from existing data
            data_file = args.data_file or DEFAULT_DATA_FILE
            logger.info("Building map from existing data file")
            connection_map = mapper.build_map(
                data_file=data_file,
                output_file=args.output,
                readable_file=args.readable_output
            )
            if not connection_map:
                sys.exit(1)
        
        # Display summary
        if connection_map and "devices" in connection_map:
            device_count = len(connection_map["devices"])
            connection_count = len(connection_map.get("connections", []))
            host_count = len(connection_map.get("hosts", []))
            
            print(f"\nMapping Summary:")
            print(f"  Devices mapped: {device_count}")
            print(f"  Hosts identified: {host_count}")
            print(f"  Connections found: {connection_count}")
            print(f"  JSON map saved to: {args.output}")
            print(f"  Readable output saved to: {args.readable_output}")
        else:
            print("No connection map was generated.")
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
