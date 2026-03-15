#!/usr/bin/env python3
"""
SSH connection module for Mikrotik devices.
Handles SSH connections and command execution on Mikrotik routers.
"""

import logging
import paramiko
import socket
import time
from typing import Dict, List, Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MikrotikSSHClient:
    """SSH client for connecting to Mikrotik devices."""
    
    def __init__(self, hostname: str, username: str, password: str = None, 
                 key_filename: str = None, port: int = 22, timeout: int = 10):
        """
        Initialize the SSH client.
        
        Args:
            hostname (str): Hostname or IP address of the Mikrotik device
            username (str): SSH username
            password (str, optional): SSH password
            key_filename (str, optional): Path to private key file
            port (int): SSH port (default: 22)
            timeout (int): Connection timeout in seconds (default: 10)
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.key_filename = key_filename
        self.port = port
        self.timeout = timeout
        self.client = None
        self.connected = False
    
    def connect(self) -> bool:
        """
        Establish SSH connection to the Mikrotik device.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect using provided credentials
            self.client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                key_filename=self.key_filename,
                timeout=self.timeout,
                look_for_keys=False,
                allow_agent=False
            )
            
            self.connected = True
            logger.info(f"Successfully connected to {self.hostname}")
            return True
            
        except paramiko.AuthenticationException:
            logger.error(f"Authentication failed for {self.hostname}")
            return False
        except paramiko.SSHException as e:
            logger.error(f"SSH error connecting to {self.hostname}: {e}")
            return False
        except socket.timeout:
            logger.error(f"Connection timeout connecting to {self.hostname}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting to {self.hostname}: {e}")
            return False
    
    def disconnect(self):
        """Close the SSH connection."""
        if self.client:
            self.client.close()
            self.connected = False
            logger.info(f"Disconnected from {self.hostname}")
    
    def execute_command(self, command: str) -> Tuple[str, str, int]:
        """
        Execute a command on the Mikrotik device.
        
        Args:
            command (str): Command to execute
            
        Returns:
            Tuple[str, str, int]: stdout, stderr, exit_code
        """
        if not self.connected:
            logger.error("Not connected to device")
            return "", "Not connected", 1
        
        try:
            # Mikrotik uses shell commands with specific formatting
            stdin, stdout, stderr = self.client.exec_command(command, timeout=self.timeout)
            
            # Read outputs
            stdout_text = stdout.read().decode('utf-8')
            stderr_text = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            return stdout_text, stderr_text, exit_code
            
        except Exception as e:
            logger.error(f"Error executing command '{command}' on {self.hostname}: {e}")
            return "", str(e), 1
    
    def get_device_info(self) -> Dict:
        """
        Get basic device information.
        
        Returns:
            Dict: Device information
        """
        info = {
            "hostname": self.hostname,
            "identity": "",
            "version": "",
            "model": "",
            "architecture": ""
        }
        
        # Get system identity
        stdout, _, _ = self.execute_command("/system identity print")
        if stdout:
            # Parse identity from output
            lines = stdout.strip().split('\n')
            for line in lines:
                if 'name:' in line:
                    info["identity"] = line.split('name:')[1].strip()
                    break
        
        # Get system resource information
        stdout, _, _ = self.execute_command("/system resource print")
        if stdout:
            # Parse resource info
            lines = stdout.strip().split('\n')
            for line in lines:
                if 'version:' in line:
                    info["version"] = line.split('version:')[1].strip()
                elif 'board-name:' in line:
                    info["model"] = line.split('board-name:')[1].strip()
                elif ' architecture-name:' in line:
                    info["architecture"] = line.split('architecture-name:')[1].strip()
        
        return info
    
    def get_interfaces(self) -> List[Dict]:
        """
        Get information about network interfaces.
        
        Returns:
            List[Dict]: List of interface information
        """
        interfaces = []
        
        # Get interface information
        stdout, _, _ = self.execute_command("/interface print detail")
        if stdout:
            # Parse interfaces
            current_interface = {}
            for line in stdout.strip().split('\n'):
                line = line.strip()
                
                # Empty line indicates end of current interface
                if not line:
                    if current_interface:
                        interfaces.append(current_interface)
                        current_interface = {}
                    continue
                
                # Skip header lines
                if line.startswith('Flags:') or line.startswith('Columns:'):
                    continue
                
                # Parse key-value pairs
                if ':' in line and not line.startswith('#'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().replace('*', '').replace('-', '_')
                        value = parts[1].strip()
                        current_interface[key] = value
            
            # Add last interface if exists
            if current_interface:
                interfaces.append(current_interface)
        
        return interfaces
    
    def get_bridge_ports(self) -> List[Dict]:
        """
        Get information about bridge ports.
        
        Returns:
            List[Dict]: List of bridge port information
        """
        bridge_ports = []
        
        # Get bridge port information
        stdout, _, _ = self.execute_command("/interface bridge port print detail")
        if stdout:
            # Parse bridge ports
            current_port = {}
            for line in stdout.strip().split('\n'):
                line = line.strip()
                
                # Empty line indicates end of current port
                if not line:
                    if current_port:
                        bridge_ports.append(current_port)
                        current_port = {}
                    continue
                
                # Skip header lines
                if line.startswith('Flags:') or line.startswith('Columns:'):
                    continue
                
                # Parse key-value pairs
                if ':' in line and not line.startswith('#'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().replace('*', '').replace('-', '_')
                        value = parts[1].strip()
                        current_port[key] = value
            
            # Add last port if exists
            if current_port:
                bridge_ports.append(current_port)
        
        return bridge_ports
    
    def get_arp_table(self) -> List[Dict]:
        """
        Get ARP table entries.
        
        Returns:
            List[Dict]: List of ARP table entries
        """
        arp_entries = []
        
        # Get ARP table
        stdout, _, _ = self.execute_command("/ip arp print detail")
        if stdout:
            # Parse ARP entries
            current_entry = {}
            for line in stdout.strip().split('\n'):
                line = line.strip()
                
                # Empty line indicates end of current entry
                if not line:
                    if current_entry:
                        arp_entries.append(current_entry)
                        current_entry = {}
                    continue
                
                # Skip header lines
                if line.startswith('Flags:') or line.startswith('Columns:'):
                    continue
                
                # Parse key-value pairs
                if ':' in line and not line.startswith('#'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().replace('*', '').replace('-', '_')
                        value = parts[1].strip()
                        current_entry[key] = value
            
            # Add last entry if exists
            if current_entry:
                arp_entries.append(current_entry)
        
        return arp_entries
    
    def get_dhcp_leases(self) -> List[Dict]:
        """
        Get DHCP lease information.
        
        Returns:
            List[Dict]: List of DHCP lease information
        """
        dhcp_leases = []
        
        # Get DHCP leases
        stdout, _, _ = self.execute_command("/ip dhcp-server lease print detail")
        if stdout:
            # Parse DHCP leases
            current_lease = {}
            for line in stdout.strip().split('\n'):
                line = line.strip()
                
                # Empty line indicates end of current lease
                if not line:
                    if current_lease:
                        dhcp_leases.append(current_lease)
                        current_lease = {}
                    continue
                
                # Skip header lines
                if line.startswith('Flags:') or line.startswith('Columns:'):
                    continue
                
                # Parse key-value pairs
                if ':' in line and not line.startswith('#'):
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip().replace('*', '').replace('-', '_')
                        value = parts[1].strip()
                        current_lease[key] = value
            
            # Add last lease if exists
            if current_lease:
                dhcp_leases.append(current_lease)
        
        return dhcp_leases

def main():
    """Example usage of the MikrotikSSHClient."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Connect to Mikrotik device via SSH")
    parser.add_argument("hostname", help="Mikrotik device IP or hostname")
    parser.add_argument("-u", "--username", required=True, help="SSH username")
    parser.add_argument("-p", "--password", help="SSH password")
    parser.add_argument("-k", "--key-file", help="Private key file")
    parser.add_argument("--port", type=int, default=22, help="SSH port")
    parser.add_argument("--timeout", type=int, default=10, help="Connection timeout")
    
    args = parser.parse_args()
    
    # Create SSH client
    ssh_client = MikrotikSSHClient(
        hostname=args.hostname,
        username=args.username,
        password=args.password,
        key_filename=args.key_file,
        port=args.port,
        timeout=args.timeout
    )
    
    # Connect to device
    if not ssh_client.connect():
        print("Failed to connect to device")
        return
    
    try:
        # Get device information
        print("Getting device information...")
        device_info = ssh_client.get_device_info()
        print(json.dumps(device_info, indent=2))
        
        # Get interfaces
        print("\nGetting interfaces...")
        interfaces = ssh_client.get_interfaces()
        print(f"Found {len(interfaces)} interfaces")
        
        # Get bridge ports
        print("\nGetting bridge ports...")
        bridge_ports = ssh_client.get_bridge_ports()
        print(f"Found {len(bridge_ports)} bridge ports")
        
        # Get ARP table
        print("\nGetting ARP table...")
        arp_table = ssh_client.get_arp_table()
        print(f"Found {len(arp_table)} ARP entries")
        
        # Get DHCP leases
        print("\nGetting DHCP leases...")
        dhcp_leases = ssh_client.get_dhcp_leases()
        print(f"Found {len(dhcp_leases)} DHCP leases")
        
    finally:
        ssh_client.disconnect()

if __name__ == "__main__":
    main()