#!/usr/bin/env python3
"""
Network scanner module for Mikrotik Mapper.
Scans IP ranges for active hosts and identifies potential Mikrotik devices.
"""

import argparse
import ipaddress
import json
import logging
import socket
import subprocess
import sys
import threading
from typing import List, Dict, Set

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NetworkScanner:
    """Network scanner for finding active hosts and identifying Mikrotik devices."""
    
    def __init__(self, timeout: int = 5):
        """
        Initialize the network scanner.
        
        Args:
            timeout (int): Timeout for network operations in seconds
        """
        self.timeout = timeout
        self.active_hosts = []
        self.mikrotik_devices = []
    
    def ping_host(self, ip: str) -> bool:
        """
        Ping a single host to check if it's active.
        
        Args:
            ip (str): IP address to ping
            
        Returns:
            bool: True if host responds, False otherwise
        """
        try:
            # Use system ping command
            if sys.platform.startswith('win'):
                cmd = ['ping', '-n', '1', '-w', str(self.timeout * 1000), ip]
            else:
                cmd = ['ping', '-c', '1', '-W', str(self.timeout), ip]
            
            result = subprocess.run(cmd, capture_output=True, timeout=self.timeout + 1)
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception as e:
            logger.debug(f"Error pinging {ip}: {e}")
            return False
    
    def scan_range(self, ip_range: str) -> List[str]:
        """
        Scan an IP range for active hosts.
        
        Args:
            ip_range (str): IP range in CIDR notation (e.g., '192.168.1.0/24')
            
        Returns:
            List[str]: List of active IP addresses
        """
        try:
            network = ipaddress.ip_network(ip_range, strict=False)
        except ValueError as e:
            logger.error(f"Invalid IP range: {ip_range} - {e}")
            return []
        
        active_hosts = []
        total_hosts = network.num_addresses
        
        logger.info(f"Scanning {total_hosts} hosts in {ip_range}...")
        
        for i, ip in enumerate(network.hosts()):
            if self.ping_host(str(ip)):
                active_hosts.append(str(ip))
                logger.debug(f"Found active host: {ip}")
            
            # Progress indicator for larger networks
            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i + 1}/{total_hosts} hosts scanned")
        
        logger.info(f"Scan complete. Found {len(active_hosts)} active hosts.")
        return active_hosts
    
    def identify_mikrotik(self, ip: str) -> bool:
        """
        Check if an active host is likely a Mikrotik device.
        This checks for common Mikrotik characteristics.
        
        Args:
            ip (str): IP address to check
            
        Returns:
            bool: True if likely a Mikrotik device, False otherwise
        """
        try:
            # Try to get banner or check for common Mikrotik ports
            # Port 8291 is commonly used by Winbox (Mikrotik management tool)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, 8291))
            sock.close()
            
            if result == 0:
                logger.debug(f"Mikrotik service detected on {ip}:8291")
                return True
                
            # Check for HTTP server that might be RouterOS
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, 80))
            sock.close()
            
            if result == 0:
                # Could do HTTP header check here for more accuracy
                logger.debug(f"Potential Mikrotik device detected on {ip}")
                return True
                
        except Exception as e:
            logger.debug(f"Error checking {ip} for Mikrotik characteristics: {e}")
            
        return False
    
    def scan_for_mikrotik_devices(self, ip_range: str, save_to_file: str = None) -> List[Dict]:
        """
        Scan network range and identify Mikrotik devices.
        
        Args:
            ip_range (str): IP range in CIDR notation
            save_to_file (str): Optional file path to save results
            
        Returns:
            List[Dict]: List of identified Mikrotik devices with details
        """
        # First scan for active hosts
        active_hosts = self.scan_range(ip_range)
        
        mikrotik_devices = []
        logger.info(f"Checking {len(active_hosts)} active hosts for Mikrotik devices...")
        
        for i, ip in enumerate(active_hosts):
            logger.debug(f"Checking {ip} for Mikrotik characteristics ({i+1}/{len(active_hosts)})")
            if self.identify_mikrotik(ip):
                device_info = {
                    "ip": ip,
                    "hostname": self.get_hostname(ip),
                    "type": "mikrotik"
                }
                mikrotik_devices.append(device_info)
                logger.info(f"Identified Mikrotik device: {ip}")
        
        logger.info(f"Found {len(mikrotik_devices)} potential Mikrotik devices")
        
        # Save to file if requested
        if save_to_file:
            self.save_results(mikrotik_devices, save_to_file)
            
        return mikrotik_devices
    
    def get_hostname(self, ip: str) -> str:
        """
        Try to resolve hostname for an IP address.
        
        Args:
            ip (str): IP address
            
        Returns:
            str: Hostname if resolved, otherwise empty string
        """
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except Exception:
            return ""
    
    def save_results(self, devices: List[Dict], filename: str):
        """
        Save scan results to a JSON file.
        
        Args:
            devices (List[Dict]): List of device information
            filename (str): Output file path
        """
        try:
            with open(filename, 'w') as f:
                json.dump(devices, f, indent=2)
            logger.info(f"Results saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save results to {filename}: {e}")

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description="Network scanner for Mikrotik devices")
    parser.add_argument("ip_range", help="IP range to scan (CIDR notation)")
    parser.add_argument("-o", "--output", help="Output file for results (JSON format)")
    parser.add_argument("-t", "--timeout", type=int, default=5, help="Timeout for network operations (seconds)")
    
    args = parser.parse_args()
    
    scanner = NetworkScanner(timeout=args.timeout)
    devices = scanner.scan_for_mikrotik_devices(args.ip_range, args.output)
    
    if not args.output:
        print(json.dumps(devices, indent=2))

if __name__ == "__main__":
    main()