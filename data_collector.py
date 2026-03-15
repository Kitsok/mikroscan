#!/usr/bin/env python3
"""
Data collection module for Mikrotik Mapper.
Coordinates data gathering from multiple Mikrotik devices.
"""

import json
import logging
from typing import Dict, List, Any

from ssh.mikrotik_ssh import MikrotikSSHClient

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataCollector:
    """Collects network data from Mikrotik devices."""
    
    def __init__(self, username: str, password: str = None, key_filename: str = None):
        """
        Initialize the data collector.
        
        Args:
            username (str): SSH username for Mikrotik devices
            password (str, optional): SSH password
            key_filename (str, optional): Path to private key file
        """
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.collected_data = {}
    
    def collect_from_device(self, hostname: str, port: int = 22, timeout: int = 10) -> Dict:
        """
        Collect data from a single Mikrotik device.
        
        Args:
            hostname (str): Device hostname or IP address
            port (int): SSH port (default: 22)
            timeout (int): Connection timeout in seconds (default: 10)
            
        Returns:
            Dict: Collected data from the device
        """
        logger.info(f"Collecting data from {hostname}")
        
        # Create SSH client
        ssh_client = MikrotikSSHClient(
            hostname=hostname,
            username=self.username,
            password=self.password,
            key_filename=self.key_filename,
            port=port,
            timeout=timeout
        )
        
        device_data = {
            "hostname": hostname,
            "connected": False,
            "device_info": {},
            "interfaces": [],
            "bridge_ports": [],
            "arp_table": [],
            "dhcp_leases": []
        }
        
        # Connect to device
        if not ssh_client.connect():
            logger.error(f"Failed to connect to {hostname}")
            return device_data
        
        try:
            device_data["connected"] = True
            
            # Get device information
            logger.debug(f"Getting device info from {hostname}")
            device_data["device_info"] = ssh_client.get_device_info()
            
            # Get interfaces
            logger.debug(f"Getting interfaces from {hostname}")
            device_data["interfaces"] = ssh_client.get_interfaces()
            
            # Get bridge ports
            logger.debug(f"Getting bridge ports from {hostname}")
            device_data["bridge_ports"] = ssh_client.get_bridge_ports()
            
            # Get ARP table
            logger.debug(f"Getting ARP table from {hostname}")
            device_data["arp_table"] = ssh_client.get_arp_table()
            
            # Get DHCP leases
            logger.debug(f"Getting DHCP leases from {hostname}")
            device_data["dhcp_leases"] = ssh_client.get_dhcp_leases()
            
            logger.info(f"Successfully collected data from {hostname}")
            
        except Exception as e:
            logger.error(f"Error collecting data from {hostname}: {e}")
        finally:
            ssh_client.disconnect()
        
        return device_data
    
    def collect_from_devices(self, hostnames: List[str], port: int = 22, timeout: int = 10) -> Dict:
        """
        Collect data from multiple Mikrotik devices sequentially.
        
        Args:
            hostnames (List[str]): List of device hostnames or IP addresses
            port (int): SSH port (default: 22)
            timeout (int): Connection timeout in seconds (default: 10)
            
        Returns:
            Dict: All collected data indexed by hostname
        """
        logger.info(f"Collecting data from {len(hostnames)} devices")
        
        all_data = {}
        
        for i, hostname in enumerate(hostnames):
            logger.info(f"Processing device {i+1}/{len(hostnames)}: {hostname}")
            device_data = self.collect_from_device(hostname, port, timeout)
            all_data[hostname] = device_data
        
        logger.info("Data collection completed")
        self.collected_data = all_data
        return all_data
    
    def save_data(self, filename: str, data: Dict = None):
        """
        Save collected data to a JSON file.
        
        Args:
            filename (str): Output file path
            data (Dict, optional): Data to save (uses internally stored data if not provided)
        """
        if data is None:
            data = self.collected_data
        
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Data saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save data to {filename}: {e}")
    
    def load_data(self, filename: str) -> Dict:
        """
        Load previously collected data from a JSON file.
        
        Args:
            filename (str): Input file path
            
        Returns:
            Dict: Loaded data
        """
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            logger.info(f"Data loaded from {filename}")
            self.collected_data = data
            return data
        except Exception as e:
            logger.error(f"Failed to load data from {filename}: {e}")
            return {}

def main():
    """Example usage of the DataCollector."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Collect data from Mikrotik devices")
    parser.add_argument("hostnames", nargs="+", help="Mikrotik device IPs or hostnames")
    parser.add_argument("-u", "--username", required=True, help="SSH username")
    parser.add_argument("-p", "--password", help="SSH password")
    parser.add_argument("-k", "--key-file", help="Private key file")
    parser.add_argument("-o", "--output", help="Output file for collected data")
    parser.add_argument("--port", type=int, default=22, help="SSH port")
    parser.add_argument("--timeout", type=int, default=10, help="Connection timeout")
    
    args = parser.parse_args()
    
    # Create data collector
    collector = DataCollector(
        username=args.username,
        password=args.password,
        key_filename=args.key_file
    )
    
    # Collect data from devices
    data = collector.collect_from_devices(args.hostnames, args.port, args.timeout)
    
    # Save data if output file specified
    if args.output:
        collector.save_data(args.output, data)
    else:
        # Otherwise print to stdout
        print(json.dumps(data, indent=2, default=str))

if __name__ == "__main__":
    main()