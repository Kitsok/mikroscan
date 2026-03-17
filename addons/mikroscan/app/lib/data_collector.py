#!/usr/bin/env python3
"""
Data collection module for Mikrotik Mapper.
Coordinates data gathering from multiple Mikrotik devices.
"""

import json
import logging
import os
from typing import Dict, List, Any, Type

from lib.mikrotik_api import MikrotikAPIClient
from lib.mikrotik_ssh import MikrotikSSHClient

logger = logging.getLogger(__name__)

class DataCollector:
    """Collects network data from Mikrotik devices."""

    CLIENTS: Dict[str, Type] = {
        "ssh": MikrotikSSHClient,
        "api": MikrotikAPIClient,
    }

    def __init__(
        self,
        username: str,
        password: str = None,
        key_filename: str = None,
        backend: str = "api",
        use_ssl: bool = False,
    ):
        """
        Initialize the data collector.
        
        Args:
            username (str): Username for MikroTik device access
            password (str, optional): Password
            key_filename (str, optional): Path to private key file
            backend (str): Collection backend (`ssh` or `api`)
            use_ssl (bool): Whether to use TLS for the API backend
        """
        if backend not in self.CLIENTS:
            raise ValueError(f"Unsupported backend: {backend}")

        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.backend = backend
        self.use_ssl = use_ssl
        self.collected_data = {}

    def _create_client(self, hostname: str, port: int, timeout: int):
        """Create a backend client for a single device."""
        client_class = self.CLIENTS[self.backend]
        if port is None:
            port = 8728 if self.backend == "api" else 22
        kwargs = {
            "hostname": hostname,
            "username": self.username,
            "password": self.password,
            "key_filename": self.key_filename,
            "port": port,
            "timeout": timeout,
        }
        if self.backend == "api":
            kwargs["use_ssl"] = self.use_ssl
        return client_class(**kwargs)
    
    def collect_from_device(self, hostname: str, port: int = None, timeout: int = 10) -> Dict:
        """
        Collect data from a single Mikrotik device.
        
        Args:
            hostname (str): Device hostname or IP address
            port (int): Backend port
            timeout (int): Connection timeout in seconds (default: 10)
            
        Returns:
            Dict: Collected data from the device
        """
        logger.info(f"Collecting data from {hostname}")
        
        client = self._create_client(hostname, port, timeout)
        
        device_data = {
            "hostname": hostname,
            "connected": False,
            "device_info": {},
            "interfaces": [],
            "bridge_ports": [],
            "arp_table": [],
            "dhcp_leases": [],
            "neighbors": [],
            "dns_static": [],
            "bridge_hosts": [],
            "ip_addresses": []
        }
        
        # Connect to device
        if not client.connect():
            logger.error(f"Failed to connect to {hostname}")
            return device_data
        
        try:
            device_data["connected"] = True

            logger.debug(f"Getting device info from {hostname}")
            try:
                device_data["device_info"] = client.get_device_info()
            except Exception as e:
                logger.error(f"Failed to collect device info from {hostname}: {e}")

            list_getters = [
                ("interfaces", "interfaces", client.get_interfaces),
                ("bridge ports", "bridge_ports", client.get_bridge_ports),
                ("ARP table", "arp_table", client.get_arp_table),
                ("DHCP leases", "dhcp_leases", client.get_dhcp_leases),
                ("neighbors", "neighbors", client.get_neighbors),
                ("DNS static entries", "dns_static", client.get_dns_static_entries),
                ("bridge host entries", "bridge_hosts", client.get_bridge_host_entries),
                ("IP addresses", "ip_addresses", client.get_ip_addresses),
            ]

            for label, key, getter in list_getters:
                logger.debug(f"Getting {label} from {hostname}")
                try:
                    device_data[key] = getter()
                    logger.debug(f"Collected {len(device_data[key])} {label} from {hostname}")
                except Exception as e:
                    logger.error(f"Failed to collect {label} from {hostname}: {e}")
            
            logger.info(f"Successfully collected data from {hostname}")
            
        except Exception as e:
            logger.error(f"Error collecting data from {hostname}: {e}")
        finally:
            client.disconnect()
        
        return device_data
    
    def collect_from_devices(self, hostnames: List[str], port: int = None, timeout: int = 10) -> Dict:
        """
        Collect data from multiple Mikrotik devices sequentially.
        
        Args:
            hostnames (List[str]): List of device hostnames or IP addresses
            port (int): Backend port
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
    
    def save_data(self, filename: str, data: Dict = None) -> bool:
        """
        Save collected data to a JSON file.
        
        Args:
            filename (str): Output file path
            data (Dict, optional): Data to save (uses internally stored data if not provided)
        """
        if data is None:
            data = self.collected_data
        
        try:
            output_dir = os.path.dirname(filename)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Data saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save data to {filename}: {e}")
            return False
    
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
    parser.add_argument("-u", "--username", required=True, help="Device username")
    parser.add_argument("-p", "--password", help="Device password")
    parser.add_argument("-k", "--key-file", help="Private key file")
    parser.add_argument("-o", "--output", help="Output file for collected data")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Backend port (default: 8728 for api, 22 for ssh)",
    )
    parser.add_argument(
        "--backend",
        choices=sorted(DataCollector.CLIENTS),
        default="api",
        help="Collection backend (default: api)",
    )
    parser.add_argument(
        "--api-ssl",
        dest="api_ssl",
        action="store_true",
        default=False,
        help="Use TLS with the RouterOS API backend",
    )
    parser.add_argument(
        "--no-api-ssl",
        dest="api_ssl",
        action="store_false",
        help="Disable TLS with the RouterOS API backend (default)",
    )
    parser.add_argument("--timeout", type=int, default=10, help="Connection timeout")
    
    args = parser.parse_args()
    
    # Create data collector
    collector = DataCollector(
        username=args.username,
        password=args.password,
        key_filename=args.key_file,
        backend=args.backend,
        use_ssl=args.api_ssl,
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
