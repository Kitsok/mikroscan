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

# Set up logging
logger = logging.getLogger(__name__)

class MikrotikMapper:
    """Main application class for Mikrotik network mapping."""
    
    def __init__(self):
        """Initialize the Mikrotik mapper."""
        self.scanner = None
        self.collector = None
        self.mapper = None
        self.credential_manager = CredentialManager()
        
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
    
    def build_map(self, data_file: str, output_file: str = "data/connection_map.json",
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
    
    def generate_topology_diagram(self, data_file: str, output_file: str = "data/topology.txt"):
        """
        Generate a network topology diagram from collected data.
        
        Args:
            data_file (str): JSON file with collected device data
            output_file (str): Output file for topology diagram
        """
        import re  # Import regex module for parsing
        
        logger.info(f"Generating network topology diagram from {data_file}")
        
        # Load collected data
        try:
            with open(data_file, 'r') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load data from {data_file}: {e}")
            return False
        
        # Generate topology diagram
        topology_lines = []
        topology_lines.append("NETWORK TOPOLOGY DIAGRAM")
        topology_lines.append("=" * 25)
        topology_lines.append("")
        
        # Separate devices by type with better identification
        routers = []
        switches = []
        access_points = []
        other_devices = []
        
        # Collect all devices and their information
        all_devices = []
        
        for ip, device in data.items():
            if device.get('connected') and 'device_info' in device:
                identity = device['device_info'].get('identity', ip)
                model = device['device_info'].get('model', 'Unknown')
                all_devices.append({'identity': identity, 'ip': ip, 'device': device, 'model': model})
                
                # Categorize devices with more precise matching
                model_upper = model.upper()
                identity_lower = identity.lower()
                
                if any(router_model in model_upper for router_model in ['RB5009', 'RB4011', 'CCR1036', 'CCR2004', 'ROUTER']):
                    routers.append({'identity': identity, 'ip': ip, 'device': device, 'model': model})
                elif any(switch_model in model_upper for switch_model in ['CRS', 'CSS', 'CBS', 'SWITCH']):
                    switches.append({'identity': identity, 'ip': ip, 'device': device, 'model': model})
                elif any(ap_model in model_upper for ap_model in ['HAP', 'WAP', 'CAP']) or 'ap' in identity_lower:
                    access_points.append({'identity': identity, 'ip': ip, 'device': device, 'model': model})
                else:
                    other_devices.append({'identity': identity, 'ip': ip, 'device': device, 'model': model})
        
        # Helper function to correctly parse ARP entries
        def parse_arp_entry(key, value):
            """Parse ARP entry to reconstruct full MAC addresses."""
            # Sample: {"0 DC address=172.20.20.113 mac_address=C4": "0F:08:BE:26:D4 interface=LAN"}
            
            # Extract IP from key
            ip_match = re.search(r'address=([\d\.]+)', key)
            ip = ip_match.group(1) if ip_match else None
            
            # Extract MAC prefix from key
            mac_prefix_match = re.search(r'mac_address=([0-9A-F]{2})', key)
            mac_prefix = mac_prefix_match.group(1) if mac_prefix_match else None
            
            # Extract MAC suffix from value
            mac_suffix_match = re.search(r'^([0-9A-F:]{14})', value)
            mac_suffix = mac_suffix_match.group(1) if mac_suffix_match else None
            
            # Reconstruct full MAC if both parts exist
            full_mac = f"{mac_prefix}:{mac_suffix}" if mac_prefix and mac_suffix else None
            
            # Extract interface from value
            interface_match = re.search(r'interface=([^\s]+)', value)
            interface = interface_match.group(1) if interface_match else 'unknown'
            
            return {'ip': ip, 'mac': full_mac, 'interface': interface} if ip and full_mac else None
        
        # Create topology visualization
        topology_lines.append("Discovered Network Devices:")
        topology_lines.append("-" * 28)
        
        if routers:
            topology_lines.append(f"Routers ({len(routers)}):")
            for router in sorted(routers, key=lambda x: x['identity']):
                topology_lines.append(f"  • {router['identity']} ({router['ip']}) - {router['model']}")
        
        if switches:
            topology_lines.append(f"Switches ({len(switches)}):")
            for switch in sorted(switches, key=lambda x: x['identity']):
                topology_lines.append(f"  • {switch['identity']} ({switch['ip']}) - {switch['model']}")
        
        if access_points:
            topology_lines.append(f"Access Points ({len(access_points)}):")
            for ap in sorted(access_points, key=lambda x: x['identity']):
                topology_lines.append(f"  • {ap['identity']} ({ap['ip']}) - {ap['model']}")
        
        if other_devices:
            topology_lines.append(f"Other Devices ({len(other_devices)}):")
            for device in sorted(other_devices, key=lambda x: x['identity']):
                topology_lines.append(f"  • {device['identity']} ({device['ip']}) - {device['model']}")
        
        # Analyze connections based on ARP data with improved parsing
        topology_lines.append("")
        topology_lines.append("Network Connectivity Analysis:")
        topology_lines.append("-" * 30)
        
        # Find which devices can see the main router
        if routers:
            main_router = routers[0]  # Assume first router is main
            main_router_ip = main_router['ip']
            devices_seeing_router = []
            
            for device_info in all_devices:
                device = device_info['device']
                device_identity = device_info['identity']
                device_ip = device_info['ip']
                
                # Skip the router itself
                if device_ip == main_router_ip:
                    continue
                
                if 'arp_table' in device:
                    for arp_entry in device['arp_table']:
                        if arp_entry:  # Ensure entry exists
                            entry_key = list(arp_entry.keys())[0]
                            entry_value = list(arp_entry.values())[0]
                            parsed_entry = parse_arp_entry(entry_key, entry_value)
                            
                            if parsed_entry and parsed_entry['ip'] == main_router_ip:
                                devices_seeing_router.append(device_identity)
                                break
            
            topology_lines.append(f"Main Router: {main_router['identity']} ({main_router_ip})")
            topology_lines.append(f"Devices that can reach main router: {len(devices_seeing_router)}")
            if devices_seeing_router:
                topology_lines.append("  " + ", ".join(sorted(set(devices_seeing_router))))
        else:
            topology_lines.append("No routers detected in network")
        
        # Add inferred network structure
        topology_lines.append("")
        topology_lines.append("Inferred Network Structure:")
        topology_lines.append("-" * 27)
        
        if routers:
            main_router = routers[0]
            topology_lines.append(f"• {main_router['identity']} ({main_router_ip}) acts as core router")
        
        if switches:
            for switch in switches:
                topology_lines.append(f"• {switch['identity']} ({switch['ip']}) serves as managed switch")
        
        if access_points:
            ap_count = len(access_points)
            ap_names = [ap['identity'] for ap in access_points]
            topology_lines.append(f"• {ap_count} Access Points deployed: {', '.join(sorted(ap_names))}")
        
        topology_lines.append("• All devices operate within the same logical subnet")
        
        # Add intelligent recommendations based on device types and connections
        topology_lines.append("")
        topology_lines.append("Intelligent Recommendations:")
        topology_lines.append("-" * 26)
        
        if len(switches) == 1 and len(access_points) >= 2:
            topology_lines.append("• Current switch aggregation of AP connections provides good management")
        elif len(access_points) > 0:
            topology_lines.append("• Consider using managed switch to aggregate AP connections")
        
        if len(routers) >= 1:
            topology_lines.append("• Centralized routing through main router simplifies network management")
        
        topology_lines.append("• Use LLDP/CDP protocols for more accurate physical topology discovery")
        topology_lines.append("• Document switch port assignments for easier troubleshooting")
        topology_lines.append("• Monitor bandwidth utilization on key network segments")
        
        # Write to file
        try:
            with open(output_file, 'w') as f:
                f.write('\n'.join(topology_lines))
            logger.info(f"Topology diagram saved to {output_file}")
            print(f"\nNetwork Topology Diagram saved to: {output_file}")
            print("\n" + "\n".join(topology_lines))
            return True
        except Exception as e:
            logger.error(f"Failed to save topology diagram to {output_file}: {e}")
            return False
    
    def run_full_mapping(self, ip_range: str, username: str = None, password: str = None,
                         key_file: str = None, port: int = 22, timeout: int = 5,
                         verbose: bool = False) -> dict:
        """
        Run complete network mapping workflow.
        
        Args:
            ip_range (str): IP range to scan (CIDR notation)
            username (str): SSH username
            password (str, optional): SSH password
            key_file (str, optional): Private key file
            port (int): SSH port (default: 22)
            timeout (int): Timeout for operations
            verbose (bool): Enable verbose output
            
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
            timeout=timeout + 5  # Give more time for data collection
        )
        
        # Step 3: Build map
        connection_map = self.build_map(
            data_file="data/collected_data.json",
            output_file="data/final_map.json",
            readable_file="data/connections.txt"
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
  python3 main.py --scan-file data/scan_results.json -u admin -p password
  
  # Use existing collected data
  python3 main.py --data-file data/collected_data.json
  
  # Generate network topology diagram
  python3 main.py --generate-topology --data-file data/collected_data.json
  
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
        help="Use existing scan results file"
    )
    
    parser.add_argument(
        "--data-file",
        help="Use existing collected data file"
    )
    
    parser.add_argument(
        "--generate-topology",
        action="store_true",
        help="Generate network topology diagram from collected data"
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
        help="SSH username for Mikrotik devices (will prompt if not provided with --store-* options)"
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
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output, particularly for scanning process"
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
            username = input("SSH Username: ").strip()
            if not username:
                parser.error("--store-credentials requires username")
        
        # Get password if not provided
        password = args.password
        if not password and not args.key_file:
            password = getpass.getpass("SSH Password: ")
        
        # Create credential manager and store credentials
        cred_manager = CredentialManager()
        if cred_manager.set_master_password():
            if cred_manager.store_credentials(args.hostname, username, password, args.key_file):
                print(f"Credentials for {args.hostname} stored successfully")
            else:
                print(f"Failed to store credentials for {args.hostname}")
        else:
            print("Failed to set master password")
        return
    
    # Handle default credential storage
    if args.store_default_credentials:
        # Get username if not provided
        username = args.username
        if not username:
            username = input("SSH Username: ").strip()
            if not username:
                parser.error("--store-default-credentials requires username")
        
        # Get password if not provided
        password = args.password
        if not password and not args.key_file:
            password = getpass.getpass("SSH Password: ")
        
        # Create credential manager and store default credentials
        cred_manager = CredentialManager()
        if cred_manager.set_master_password():
            if cred_manager.store_default_credentials(username, password, args.key_file):
                print("Default credentials stored successfully")
            else:
                print("Failed to store default credentials")
        else:
            print("Failed to set master password")
        return
    
    # Handle topology generation (doesn't need authentication)
    if args.generate_topology:
        # Generate network topology diagram
        if not args.data_file:
            parser.error("--generate-topology requires --data-file")
        
        # Create mapper just for topology generation
        mapper = MikrotikMapper()
        logger.info("Generating network topology diagram")
        mapper.generate_topology_diagram(
            data_file=args.data_file,
            output_file="data/topology.txt"
        )
        return
    
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
                output_file="data/collected_data.json",
                port=args.ssh_port,
                timeout=args.timeout
            )
            
            if connection_map:
                connection_map = mapper.build_map(
                    data_file="data/collected_data.json",
                    output_file=args.output,
                    readable_file="data/connections.txt"
                )
                
        elif args.generate_topology:
            # Generate network topology diagram
            if not args.data_file:
                parser.error("--generate-topology requires --data-file")
            
            logger.info("Generating network topology diagram")
            mapper.generate_topology_diagram(
                data_file=args.data_file,
                output_file="data/topology.txt"
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
                timeout=args.timeout,
                verbose=args.verbose
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