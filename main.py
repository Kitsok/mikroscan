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

from scanner.network_scanner import NetworkScanner
from data.data_collector import DataCollector
from mapping.connection_mapper import ConnectionMapper
from credential_manager import CredentialManager

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MikrotikMapper:
    """Main application class for Mikrotik network mapping."""
    
    def __init__(self):
        """Initialize the Mikrotik mapper."""
        self.scanner = None
        self.collector = None
        self.mapper = None
        self.credential_manager = CredentialManager()
        
    def scan_network(self, ip_range: str, output_file: str = "mikrotik_devices.json", 
                     timeout: int = 5) -> List[dict]:
        """
        Scan network for Mikrotik devices.
        
        Args:
            ip_range (str): IP range to scan (CIDR notation)
            output_file (str): File to save scan results
            timeout (int): Timeout for network operations
            
        Returns:
            List[dict]: List of discovered Mikrotik devices
        """
        logger.info(f"Scanning network range: {ip_range}")
        
        self.scanner = NetworkScanner(timeout=timeout)
        devices = self.scanner.scan_for_mikrotik_devices(ip_range, output_file)
        
        logger.info(f"Scan complete. Found {len(devices)} potential Mikrotik devices.")
        return devices
    
    def collect_data(self, device_file: str, username: str = None, password: str = None,
                     key_file: str = None, output_file: str = "device_data.json",
                     port: int = 22, timeout: int = 10) -> dict:
        """
        Collect data from Mikrotik devices.
        
        Args:
            device_file (str): JSON file with device information from scan
            username (str): SSH username (optional if using stored credentials)
            password (str, optional): SSH password
            key_file (str, optional): Private key file
            output_file (str): File to save collected data
            port (int): SSH port
            timeout (int): Connection timeout
            
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
        hostnames = [device["ip"] for device in devices]
        logger.info(f"Collecting data from {len(hostnames)} devices")
        
        # If no username provided, try to get stored credentials
        if not username:
            # Authenticate with master password
            if not self.credential_manager.authenticate():
                logger.error("Failed to authenticate with master password")
                return {}
            
            # Use stored credentials for each device
            all_data = {}
            for hostname in hostnames:
                # Get stored credentials for this host
                cred_data = self.credential_manager.retrieve_credentials(hostname)
                if not cred_data:
                    logger.warning(f"No stored credentials for {hostname}, skipping")
                    continue
                
                # Create data collector with stored credentials
                self.collector = DataCollector(
                    username=cred_data.get("username", ""),
                    password=cred_data.get("password"),
                    key_filename=cred_data.get("key_file")
                )
                
                # Collect data from this device
                device_data = self.collector.collect_from_device(hostname, port, timeout)
                all_data[hostname] = device_data
            
            data = all_data
        else:
            # Store credentials if provided
            if username and (password or key_file):
                # Set master password and store credentials
                if self.credential_manager.set_master_password():
                    for hostname in hostnames:
                        self.credential_manager.store_credentials(hostname, username, password, key_file)
            
            # Create data collector with provided credentials
            self.collector = DataCollector(
                username=username,
                password=password,
                key_filename=key_file
            )
            
            # Collect data
            data = self.collector.collect_from_devices(hostnames, port, timeout)
        
        # Save data
        self.collector.save_data(output_file, data)
        
        logger.info("Data collection complete")
        return data
    
    def build_map(self, data_file: str, output_file: str = "connection_map.json",
                  readable_file: str = "connections.txt") -> dict:
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
        
        # Create connection mapper
        self.mapper = ConnectionMapper()
        
        # Load data and build map
        self.mapper.load_data(data_file)
        connection_map = self.mapper.build_connection_map()
        
        # Save JSON map
        self.mapper.save_map(output_file, connection_map)
        
        # Generate and save readable output
        descriptions = self.mapper.generate_readable_output()
        try:
            with open(readable_file, 'w') as f:
                for desc in descriptions:
                    f.write(desc + '\n')
            logger.info(f"Readable connection descriptions saved to {readable_file}")
        except Exception as e:
            logger.error(f"Failed to save readable output to {readable_file}: {e}")
        
        logger.info("Connection map building complete")
        return connection_map
    
    def run_full_mapping(self, ip_range: str, username: str = None, password: str = None,
                         key_file: str = None, port: int = 22, timeout: int = 5) -> dict:
        """
        Run complete network mapping workflow.
        
        Args:
            ip_range (str): IP range to scan (CIDR notation)
            username (str): SSH username
            password (str, optional): SSH password
            key_file (str, optional): Private key file
            port (int): SSH port (default: 22)
            timeout (int): Timeout for operations
            
        Returns:
            dict: Final connection map
        """
        logger.info("Running full network mapping workflow")
        
        # Step 1: Scan network
        devices = self.scan_network(
            ip_range=ip_range,
            output_file="scan_results.json",
            timeout=timeout
        )
        
        if not devices:
            logger.warning("No Mikrotik devices found. Exiting.")
            return {}
        
        # Step 2: Collect data
        data = self.collect_data(
            device_file="scan_results.json",
            username=username,
            password=password,
            key_file=key_file,
            output_file="collected_data.json",
            port=port,
            timeout=timeout + 5  # Give more time for data collection
        )
        
        # Step 3: Build map
        connection_map = self.build_map(
            data_file="collected_data.json",
            output_file="final_map.json",
            readable_file="connections.txt"
        )
        
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
  python3 main.py --scan-file scan_results.json -u admin -p password
  
  # Use existing collected data
  python3 main.py --data-file collected_data.json
  
  # Store credentials for later use
  python3 main.py --store-credentials --hostname 192.168.1.1 -u admin -p password
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
        help="Use existing scan results file"
    )
    
    parser.add_argument(
        "--data-file",
        help="Use existing collected data file"
    )
    
    # Credential management
    parser.add_argument(
        "--store-credentials",
        action="store_true",
        help="Store credentials for a host (requires --hostname)"
    )
    
    parser.add_argument(
        "--hostname",
        help="Hostname or IP address for credential storage"
    )
    
    # SSH authentication
    parser.add_argument(
        "-u", "--username",
        help="SSH username for Mikrotik devices"
    )
    
    parser.add_argument(
        "-p", "--password",
        help="SSH password for Mikrotik devices"
    )
    
    parser.add_argument(
        "-k", "--key-file",
        help="Private key file for SSH authentication"
    )
    
    # Network options
    parser.add_argument(
        "--ssh-port",
        type=int,
        default=22,
        help="SSH port (default: 22)"
    )
    
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Network timeout in seconds (default: 10)"
    )
    
    # Output options
    parser.add_argument(
        "-o", "--output",
        default="final_map.json",
        help="Output file for connection map (default: final_map.json)"
    )
    
    parser.add_argument(
        "--readable-output",
        default="connections.txt",
        help="File for human-readable connections (default: connections.txt)"
    )
    
    args = parser.parse_args()
    
    # Handle credential storage
    if args.store_credentials:
        if not args.hostname or not args.username:
            parser.error("--store-credentials requires --hostname and --username")
        
        # Get password if not provided
        password = args.password
        if not password and not args.key_file:
            password = getpass.getpass("SSH Password: ")
        
        # Create credential manager and store credentials
        cred_manager = CredentialManager()
        if cred_manager.set_master_password():
            if cred_manager.store_credentials(args.hostname, args.username, password, args.key_file):
                print(f"Credentials for {args.hostname} stored successfully")
            else:
                print(f"Failed to store credentials for {args.hostname}")
        else:
            print("Failed to set master password")
        return
    
    # Validate arguments for mapping operations
    if not args.ip_range and not args.scan_file and not args.data_file:
        parser.error("Either IP range, scan file, or data file must be provided")
    
    # Create mapper
    mapper = MikrotikMapper()
    
    # Authenticate for operations that need stored credentials
    if not args.username and not args.password and not args.key_file:
        # Try to authenticate with master password to use stored credentials
        if not mapper.credential_manager.authenticate():
            print("Authentication failed. Cannot access stored credentials.")
            sys.exit(1)
    
    # Get password if needed and not provided
    if (args.ip_range or args.scan_file) and args.username and not args.password and not args.key_file:
        args.password = getpass.getpass("SSH Password: ")
    
    try:
        if args.data_file:
            # Directly build map from existing data
            logger.info("Building map from existing data file")
            connection_map = mapper.build_map(
                data_file=args.data_file,
                output_file=args.output,
                readable_file=args.readable_output
            )
            
        elif args.scan_file:
            # Collect data and build map
            logger.info("Collecting data and building map from scan file")
            connection_map = mapper.collect_data(
                device_file=args.scan_file,
                username=args.username,
                password=args.password,
                key_file=args.key_file,
                output_file="collected_data.json",
                port=args.ssh_port,
                timeout=args.timeout
            )
            
            if connection_map:
                connection_map = mapper.build_map(
                    data_file="collected_data.json",
                    output_file=args.output,
                    readable_file=args.readable_output
                )
                
        else:
            # Run full workflow
            logger.info("Running full network mapping workflow")
            connection_map = mapper.run_full_mapping(
                ip_range=args.ip_range,
                username=args.username,
                password=args.password,
                key_file=args.key_file,
                port=args.ssh_port,
                timeout=args.timeout
            )
        
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