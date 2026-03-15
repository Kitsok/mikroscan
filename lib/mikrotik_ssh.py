#!/usr/bin/env python3
"""
SSH connection module for Mikrotik devices.
Handles SSH connections and command execution on Mikrotik routers.
"""

import logging
import paramiko
import re
import socket
import time
from typing import Dict, List, Optional, Tuple
import os

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
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
            logger.debug(f"Executing command on {self.hostname}: {command}")
            
            # Mikrotik uses shell commands with specific formatting
            stdin, stdout, stderr = self.client.exec_command(command, timeout=self.timeout)
            
            # Read outputs
            stdout_text = stdout.read().decode('utf-8')
            stderr_text = stderr.read().decode('utf-8')
            exit_code = stdout.channel.recv_exit_status()
            
            # RouterOS sometimes reports command syntax errors via stdout while
            # still returning an apparently successful channel status.
            if not stderr_text and self._looks_like_command_error(stdout_text):
                stderr_text = stdout_text.strip()
                stdout_text = ""
                exit_code = 1

            # Log command and response for debugging
            self._log_command_response(command, stdout_text, stderr_text, exit_code)
            
            logger.debug(f"Command '{command}' executed with exit code {exit_code}")
            
            return stdout_text, stderr_text, exit_code
            
        except Exception as e:
            logger.error(f"Error executing command '{command}' on {self.hostname}: {e}")
            return "", str(e), 1

    def _looks_like_command_error(self, output: str) -> bool:
        """
        Detect RouterOS command errors that are returned via stdout.

        Args:
            output (str): Command stdout

        Returns:
            bool: True if output looks like a command error, False otherwise
        """
        if not output:
            return False

        normalized = output.strip().lower()
        error_prefixes = (
            "expected end of command",
            "bad command name",
            "script error:",
            "syntax error",
            "failure:",
            "input does not match any value",
            "no such item",
        )
        return normalized.startswith(error_prefixes)
    
    def _log_command_response(self, command: str, stdout: str, stderr: str, exit_code: int):
        """
        Log command and response to debug files.
        
        Args:
            command (str): Command that was executed
            stdout (str): Standard output
            stderr (str): Standard error
            exit_code (int): Exit code
        """
        try:
            # Create logs directory if it doesn't exist
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # Create log filename based on command
            # Sanitize command name for filesystem
            cmd_name = "".join(c for c in command if c.isalnum() or c in (' ', '-', '_')).rstrip()
            cmd_name = cmd_name.replace('/', '_').replace(' ', '_').replace('-', '_')
            log_file = f"{log_dir}/{self.hostname}_{cmd_name}.log"
            
            # Write command and response to log file
            with open(log_file, 'w') as f:
                f.write(f"HOST: {self.hostname}\n")
                f.write(f"COMMAND: {command}\n")
                f.write(f"EXIT_CODE: {exit_code}\n")
                f.write("=" * 50 + "\n")
                f.write("STDOUT:\n")
                f.write(stdout if stdout else "(empty)")
                f.write("\n" + "=" * 50 + "\n")
                f.write("STDERR:\n")
                f.write(stderr if stderr else "(empty)")
                f.write("\n" + "=" * 50 + "\n")
                
            logger.debug(f"Command response logged to {log_file}")
            
        except Exception as e:
            logger.warning(f"Failed to log command response: {e}")
    
    def _parse_key_value_line(self, line: str, target_dict: Dict):
        """
        Parse key=value pairs from a line and add to target dictionary.
        
        Args:
            line (str): Line to parse
            target_dict (Dict): Dictionary to add parsed key-value pairs to
        """
        pattern = re.compile(r'([^\s=]+)=(?:"([^"]*)"|(\S+))')
        for match in pattern.finditer(line):
            key = match.group(1).strip().replace('*', '').replace('-', '_')
            value = match.group(2) if match.group(2) is not None else match.group(3).strip()
            target_dict[key] = value

    def _parse_detail_records(self, stdout: str) -> List[Dict]:
        """Parse RouterOS `print detail` output into a list of dictionaries."""
        records = []
        current_record = {}

        if not stdout:
            return records

        for line in stdout.strip().split('\n'):
            line = line.strip()

            if not line:
                if current_record:
                    records.append(current_record)
                    current_record = {}
                continue

            if line.startswith('Flags:') or line.startswith('Columns:'):
                continue

            if line.startswith(';;;'):
                continue

            self._parse_key_value_line(line, current_record)

        if current_record:
            records.append(current_record)

        return records

    def _parse_colon_records(self, stdout: str) -> List[Dict]:
        """Parse RouterOS monitor output with `key: value` lines."""
        records = []
        current_record = {}

        if not stdout:
            return records

        for raw_line in stdout.strip().split('\n'):
            line = raw_line.strip()
            if not line:
                continue

            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip().replace('-', '_').replace(' ', '_')
            value = value.strip()

            # A new `name:` line starts the next monitor record.
            if key == "name" and current_record:
                records.append(current_record)
                current_record = {}

            current_record[key] = value

        if current_record:
            records.append(current_record)

        return records
    
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

        stdout, _, _ = self.execute_command("/interface print detail")
        interfaces = self._parse_detail_records(stdout)

        ethernet_stdout, _, _ = self.execute_command("/interface ethernet print detail")
        ethernet_interfaces = self._parse_detail_records(ethernet_stdout)
        if ethernet_interfaces and interfaces:
            interfaces_by_name = {
                interface.get("name"): interface
                for interface in interfaces
                if interface.get("name")
            }

            for ethernet_interface in ethernet_interfaces:
                interface_name = ethernet_interface.get("name")
                if interface_name and interface_name in interfaces_by_name:
                    interfaces_by_name[interface_name].update(ethernet_interface)
                    if "poe_out" in ethernet_interface:
                        poe_stdout, _, _ = self.execute_command(
                            f"/interface ethernet poe monitor {interface_name} once"
                        )
                        poe_monitors = self._parse_colon_records(poe_stdout)
                        if poe_monitors:
                            interfaces_by_name[interface_name].update(poe_monitors[0])
        
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
                
                # Skip comment lines
                if line.startswith(';;;'):
                    continue
                
                # Parse key=value pairs from the line
                self._parse_key_value_line(line, current_port)
            
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
                
                # Skip comment lines
                if line.startswith(';;;'):
                    continue
                
                # Parse key=value pairs from the line
                self._parse_key_value_line(line, current_entry)
            
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
                
                # Skip comment lines
                if line.startswith(';;;'):
                    continue
                
                # Parse key=value pairs from the line
                self._parse_key_value_line(line, current_lease)
            
            # Add last lease if exists
            if current_lease:
                dhcp_leases.append(current_lease)

        return dhcp_leases
    
    def get_neighbors(self) -> List[Dict]:
        """
        Get neighbor information using /ip neighbor print.
        
        Returns:
            List[Dict]: List of neighbor information
        """
        neighbors = []
        
        # Get neighbor information
        stdout, _, _ = self.execute_command("/ip neighbor print detail")
        if stdout:
            # Parse neighbors
            current_neighbor = {}
            for line in stdout.strip().split('\n'):
                line = line.strip()
                
                # Empty line indicates end of current neighbor
                if not line:
                    if current_neighbor:
                        neighbors.append(current_neighbor)
                        current_neighbor = {}
                    continue
                
                # Skip header lines
                if line.startswith('Flags:') or line.startswith('Columns:'):
                    continue
                
                # Skip comment lines
                if line.startswith(';;;'):
                    continue
                
                # Parse key=value pairs from the line
                self._parse_key_value_line(line, current_neighbor)
            
            # Add last neighbor if exists
            if current_neighbor:
                neighbors.append(current_neighbor)
        
        return neighbors
    
    def get_dns_static_entries(self) -> List[Dict]:
        """
        Get static DNS entries using /ip dns static print.
        
        Returns:
            List[Dict]: List of static DNS entries
        """
        dns_entries = []
        
        # Get DNS static entries
        stdout, _, _ = self.execute_command("/ip dns static print detail")
        if stdout:
            # Parse DNS entries
            current_entry = {}
            for line in stdout.strip().split('\n'):
                line = line.strip()
                
                # Empty line indicates end of current entry
                if not line:
                    if current_entry:
                        dns_entries.append(current_entry)
                        current_entry = {}
                    continue
                
                # Skip header lines
                if line.startswith('Flags:') or line.startswith('Columns:'):
                    continue
                
                # Skip comment lines
                if line.startswith(';;;'):
                    continue
                
                # Parse key=value pairs from the line
                self._parse_key_value_line(line, current_entry)
            
            # Add last entry if exists
            if current_entry:
                dns_entries.append(current_entry)
        
        return dns_entries

    def get_bridge_host_entries(self) -> List[Dict]:
        """
        Get bridge host entries using /interface bridge host print.

        Returns:
            List[Dict]: List of bridge host entries
        """
        bridge_hosts = []

        stdout, _, _ = self.execute_command("/interface bridge host print detail")
        if stdout:
            current_entry = {}
            for line in stdout.strip().split('\n'):
                line = line.strip()

                if not line:
                    if current_entry:
                        bridge_hosts.append(current_entry)
                        current_entry = {}
                    continue

                if line.startswith('Flags:') or line.startswith('Columns:'):
                    continue

                if line.startswith(';;;'):
                    continue

                self._parse_key_value_line(line, current_entry)

            if current_entry:
                bridge_hosts.append(current_entry)

        return bridge_hosts
    
    def get_ip_addresses(self) -> List[Dict]:
        """
        Get IP address information using /ip address print.
        
        Returns:
            List[Dict]: List of IP address information
        """
        ip_addresses = []
        
        # Get IP address information
        stdout, _, _ = self.execute_command("/ip address print detail")
        if stdout:
            # Parse IP addresses
            current_address = {}
            for line in stdout.strip().split('\n'):
                line = line.strip()
                
                # Empty line indicates end of current address
                if not line:
                    if current_address:
                        ip_addresses.append(current_address)
                        current_address = {}
                    continue
                
                # Skip header lines
                if line.startswith('Flags:') or line.startswith('Columns:'):
                    continue
                
                # Skip comment lines
                if line.startswith(';;;'):
                    continue
                
                # Parse key=value pairs from the line
                self._parse_key_value_line(line, current_address)
            
            # Add last address if exists
            if current_address:
                ip_addresses.append(current_address)
        
        return ip_addresses

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
