#!/usr/bin/env python3
"""
Network scanner module for Mikrotik Mapper.
Scans IP ranges for active hosts and identifies potential Mikrotik devices.
"""

import argparse
import ipaddress
import json
import logging
import os
import socket
import subprocess
import sys
import threading
from typing import List, Dict, Set

logger = logging.getLogger(__name__)

PING_COUNT = 3
PING_WAIT_SECONDS = 1
PING_WAIT_MILLISECONDS = 100

class NetworkScanner:
    """Network scanner for finding active hosts and identifying Mikrotik devices."""
    
    def __init__(self, timeout: int = 5, verbose: bool = False):
        """
        Initialize the network scanner.
        
        Args:
            timeout (int): Timeout for network operations in seconds
            verbose (bool): Enable verbose output
        """
        self.timeout = timeout
        self.verbose = verbose
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
                cmd = ['ping', '-n', str(PING_COUNT), '-w', str(PING_WAIT_MILLISECONDS), ip]
            else:
                cmd = [
                    'ping',
                    '-c',
                    str(PING_COUNT),
                    '-i',
                    str(PING_WAIT_SECONDS),
                    '-W',
                    str(PING_WAIT_SECONDS),
                    ip,
                ]
            
            if self.verbose:
                logger.info(f"Pinging {ip}...")
            
            result = subprocess.run(cmd, capture_output=True, timeout=PING_COUNT + 1)
            success = result.returncode == 0
            
            if self.verbose:
                if success:
                    logger.info(f"Host {ip} is responsive")
                else:
                    logger.info(f"Host {ip} is not responsive")
            
            return success
        except subprocess.TimeoutExpired:
            if self.verbose:
                logger.info(f"Timeout pinging {ip}")
            return False
        except Exception as e:
            if self.verbose:
                logger.info(f"Error pinging {ip}: {e}")
            else:
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
            network = ipaddress.ip_network(ip_range, strict=True)
        except ValueError as e:
            logger.error(f"Invalid IP range: {ip_range} - {e}")
            return []

        hosts = list(network.hosts())
        active_hosts = []
        total_hosts = len(hosts)

        logger.info(f"Scanning {total_hosts} hosts in {network.with_prefixlen}...")

        for i, ip in enumerate(hosts):
            if self.ping_host(str(ip)):
                active_hosts.append(str(ip))
                if self.verbose:
                    logger.info(f"Found active host: {ip}")
                else:
                    logger.debug(f"Found active host: {ip}")
            
            # Progress indicator for larger networks
            if (i + 1) % 50 == 0:
                logger.info(f"Progress: {i + 1}/{total_hosts} hosts scanned")
            elif self.verbose and (i + 1) % 10 == 0:
                # More frequent updates in verbose mode
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
        if self.verbose:
            logger.info(f"Checking {ip} for Mikrotik characteristics...")
        
        try:
            # Try to get banner or check for common Mikrotik ports
            # Port 8291 is commonly used by Winbox (Mikrotik management tool)
            if self.verbose:
                logger.info(f"  Testing port 8291 (Winbox) on {ip}...")
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, 8291))
            sock.close()
            
            if result == 0:
                if self.verbose:
                    logger.info(f"  Mikrotik service detected on {ip}:8291")
                else:
                    logger.debug(f"Mikrotik service detected on {ip}:8291")
                return True
                
            # Check for HTTP server that might be RouterOS
            if self.verbose:
                logger.info(f"  Testing port 80 (HTTP) on {ip}...")
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, 80))
            sock.close()
            
            if result == 0:
                # Could do HTTP header check here for more accuracy
                if self.verbose:
                    logger.info(f"  Potential Mikrotik device detected on {ip} (HTTP server found)")
                else:
                    logger.debug(f"Potential Mikrotik device detected on {ip}")
                return True
                
        except Exception as e:
            if self.verbose:
                logger.info(f"  Error checking {ip} for Mikrotik characteristics: {e}")
            else:
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
            if self.verbose:
                logger.info(f"Checking {ip} for Mikrotik characteristics ({i+1}/{len(active_hosts)})")
            else:
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
            if not self.save_results(mikrotik_devices, save_to_file):
                logger.error(
                    f"Aborting scan results because they could not be saved to {save_to_file}"
                )
                return []
            
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
    
    def save_results(self, devices: List[Dict], filename: str) -> bool:
        """
        Save scan results to a JSON file.
        
        Args:
            devices (List[Dict]): List of device information
            filename (str): Output file path
        """
        try:
            output_dir = os.path.dirname(filename)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(filename, 'w') as f:
                json.dump(devices, f, indent=2)
            logger.info(f"Results saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save results to {filename}: {e}")
            return False

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
