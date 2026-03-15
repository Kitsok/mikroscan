#!/usr/bin/env python3
"""
Mapping engine for Mikrotik Mapper.
Processes collected data and builds connection relationships.
"""

import json
import logging
import os
from typing import Dict, List, Set, Tuple, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConnectionMapper:
    """Maps network connections between Mikrotik devices and hosts."""
    
    def __init__(self):
        """Initialize the connection mapper."""
        self.devices_data = {}
        self.connection_map = {}
        self.device_mac_map = {}
        self.host_interface_map = {}
        self.managed_device_names = set()

    def _clean_name(self, name: str) -> str:
        """Normalize device and host names for comparisons."""
        if not name:
            return ""
        return name.strip().strip('"').strip()
    
    def load_data(self, filename: str) -> Dict:
        """
        Load collected device data from a JSON file.
        
        Args:
            filename (str): Input file path
            
        Returns:
            Dict: Loaded device data
        """
        try:
            with open(filename, 'r') as f:
                self.devices_data = json.load(f)
            logger.info(f"Device data loaded from {filename}")
            return self.devices_data
        except Exception as e:
            logger.error(f"Failed to load data from {filename}: {e}")
            return {}
    
    def set_data(self, data: Dict):
        """
        Set device data directly.
        
        Args:
            data (Dict): Device data
        """
        self.devices_data = data
    
    def build_connection_map(self) -> Dict:
        """
        Build connection map from collected device data.
        
        Returns:
            Dict: Connection map in JSON format
        """
        logger.info("Building connection map")
        
        # Initialize connection map structure
        self.connection_map = {
            "devices": {},
            "connections": [],
            "hosts": {}
        }
        self.device_mac_map = self._build_device_mac_map()
        self.host_interface_map = self._build_host_interface_map()
        self.managed_device_names = {
            self._clean_name(device_data.get("device_info", {}).get("identity", hostname))
            for hostname, device_data in self.devices_data.items()
            if device_data.get("connected", False)
        }
        
        # Process each device
        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                logger.warning(f"Skipping disconnected device: {hostname}")
                continue
            
            # Add device to map
            device_id = device_data["device_info"].get("identity", hostname)
            self.connection_map["devices"][device_id] = {
                "hostname": hostname,
                "info": device_data["device_info"],
                "interfaces": device_data["interfaces"]
            }
            
            # Process bridge ports to understand device interconnections
            bridge_connections = self._process_bridge_ports(device_data, device_id)
            self.connection_map["connections"].extend(bridge_connections)
        
        # Process ARP table and DHCP leases to identify hosts
        self._process_hosts()
        
        # Connect hosts to the network
        host_connections = self._connect_hosts()
        self.connection_map["connections"].extend(host_connections)
        
        logger.info(f"Connection map built with {len(self.connection_map['devices'])} devices and {len(self.connection_map['connections'])} connections")
        return self.connection_map
    
    def _process_bridge_ports(self, device_data: Dict, device_id: str) -> List[Dict]:
        """
        Process bridge port information to find device-to-device connections.
        
        Args:
            device_data (Dict): Data collected from a device
            device_id (str): Identifier for the device
            
        Returns:
            List[Dict]: List of connections between devices
        """
        connections = []
        bridge_ports = device_data.get("bridge_ports", [])
        bridge_hosts = device_data.get("bridge_hosts", [])
        interfaces = device_data.get("interfaces", [])

        valid_ports = {
            port.get("interface")
            for port in bridge_ports
            if port.get("interface")
        }

        local_macs = {
            (iface.get("mac_address") or iface.get("link_layer_address") or "").upper()
            for iface in interfaces
            if iface.get("mac_address") or iface.get("link_layer_address")
        }

        seen_connections = set()

        for host in bridge_hosts:
            interface_name = host.get("interface")
            mac_address = (host.get("mac_address") or "").upper()

            if not interface_name or not mac_address:
                continue

            if valid_ports and interface_name not in valid_ports:
                continue

            # Ignore MACs owned by the local device. Using interface MACs here
            # creates false "connected to itself" links.
            if mac_address in local_macs:
                continue

            connection_key = (interface_name, mac_address)
            if connection_key in seen_connections:
                continue
            seen_connections.add(connection_key)

            connections.append({
                "source_device": device_id,
                "source_interface": interface_name,
                "mac_address": mac_address,
                "destination_device": self.device_mac_map.get(mac_address),
                "type": "bridge_port"
            })

        return connections

    def _build_device_mac_map(self) -> Dict[str, str]:
        """Build a MAC-to-device-name map for collected MikroTik devices."""
        mac_map = {}

        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue

            device_id = device_data.get("device_info", {}).get("identity", hostname)
            for interface in device_data.get("interfaces", []):
                mac = (interface.get("mac_address") or interface.get("link_layer_address") or "").upper()
                if mac:
                    mac_map[mac] = device_id

        return mac_map

    def _build_host_interface_map(self) -> Dict[str, Dict[str, str]]:
        """Build per-device MAC-to-interface mappings from bridge host data."""
        host_interface_map = {}

        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue

            device_id = device_data.get("device_info", {}).get("identity", hostname)
            device_host_map = {}
            for host in device_data.get("bridge_hosts", []):
                mac_address = (host.get("mac_address") or "").upper()
                interface_name = host.get("interface") or host.get("on_interface")
                if mac_address and interface_name and mac_address not in device_host_map:
                    device_host_map[mac_address] = interface_name

            host_interface_map[device_id] = device_host_map

        return host_interface_map
    
    def _process_hosts(self):
        """Process ARP table and DHCP leases to identify hosts."""
        all_arp_entries = []
        all_dhcp_leases = []
        
        # Collect ARP entries and DHCP leases from all devices
        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue
            
            device_id = device_data["device_info"].get("identity", hostname)
            
            # Collect ARP entries
            for arp_entry in device_data.get("arp_table", []):
                arp_entry["_source_device"] = device_id
                all_arp_entries.append(arp_entry)
            
            # Collect DHCP leases
            for lease in device_data.get("dhcp_leases", []):
                lease["_source_device"] = device_id
                all_dhcp_leases.append(lease)
        
        # Process ARP entries to identify hosts
        for arp_entry in all_arp_entries:
            ip_address = arp_entry.get("address")
            mac_address = (arp_entry.get("mac_address") or "").upper()
            source_device = arp_entry.get("_source_device")
            
            if ip_address and mac_address:
                if mac_address in self.device_mac_map:
                    continue
                if mac_address not in self.connection_map["hosts"]:
                    self.connection_map["hosts"][mac_address] = {
                        "mac_address": mac_address,
                        "ip_addresses": [ip_address],
                        "seen_on_devices": [source_device]
                    }
                else:
                    # Update existing host record
                    host = self.connection_map["hosts"][mac_address]
                    if ip_address not in host["ip_addresses"]:
                        host["ip_addresses"].append(ip_address)
                    if source_device not in host["seen_on_devices"]:
                        host["seen_on_devices"].append(source_device)
        
        # Process DHCP leases to enhance host information
        for lease in all_dhcp_leases:
            mac_address = (lease.get("mac_address") or "").upper()
            active_address = lease.get("active_address")
            host_name = self._clean_name(lease.get("host_name", ""))

            if not mac_address:
                continue

            if mac_address in self.device_mac_map or host_name in self.managed_device_names:
                self.connection_map["hosts"].pop(mac_address, None)
                continue
            
            if mac_address and mac_address in self.connection_map["hosts"]:
                host = self.connection_map["hosts"][mac_address]
                if active_address and active_address not in host["ip_addresses"]:
                    host["ip_addresses"].append(active_address)
                
                # Add hostname if available
                if host_name and "hostname" not in host:
                    host["hostname"] = host_name
    
    def _connect_hosts(self) -> List[Dict]:
        """
        Connect identified hosts to the network.
        
        Returns:
            List[Dict]: List of host connections
        """
        connections = []
        
        # For each host, try to determine which interface it's connected to
        for mac_address, host in self.connection_map["hosts"].items():
            # Simple approach: if we see this MAC in ARP tables, 
            # assume it's directly connected to the device that reported it
            if host["seen_on_devices"]:
                # For simplicity, connect to the first device that reported this host
                source_device = host["seen_on_devices"][0]
                source_interface = self.host_interface_map.get(source_device, {}).get(
                    mac_address.upper(),
                    "unknown"
                )
                
                connection = {
                    "source_device": source_device,
                    "source_interface": source_interface,
                    "destination_host": host.get("hostname", mac_address),
                    "mac_address": mac_address,
                    "ip_addresses": host["ip_addresses"],
                    "type": "host_connection"
                }
                connections.append(connection)
        
        return connections
    
    def get_connections_by_device(self, device_id: str) -> List[Dict]:
        """
        Get all connections for a specific device.
        
        Args:
            device_id (str): Device identifier
            
        Returns:
            List[Dict]: List of connections involving the device
        """
        return [
            conn for conn in self.connection_map.get("connections", [])
            if conn.get("source_device") == device_id
        ]
    
    def get_host_connections(self) -> List[Dict]:
        """
        Get all host connections.
        
        Returns:
            List[Dict]: List of host connections
        """
        return [
            conn for conn in self.connection_map.get("connections", [])
            if conn.get("type") == "host_connection"
        ]
    
    def save_map(self, filename: str, connection_map: Dict = None):
        """
        Save connection map to a JSON file.
        
        Args:
            filename (str): Output file path
            connection_map (Dict, optional): Map to save (uses internally stored map if not provided)
        """
        if connection_map is None:
            connection_map = self.connection_map
        
        try:
            output_dir = os.path.dirname(filename)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(filename, 'w') as f:
                json.dump(connection_map, f, indent=2, default=str)
            logger.info(f"Connection map saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save connection map to {filename}: {e}")
    
    def generate_readable_output(self) -> List[str]:
        """
        Generate human-readable connection descriptions.
        
        Returns:
            List[str]: List of connection descriptions
        """
        if not self.connection_map:
            logger.warning("No connection map available. Call build_connection_map() first.")
            return []
        
        descriptions = []
        
        # Describe device-to-device connections
        for connection in self.connection_map.get("connections", []):
            conn_type = connection.get("type", "unknown")
            
            if conn_type == "bridge_port":
                source_device = connection.get("source_device", "unknown")
                source_interface = connection.get("source_interface", "unknown")
                mac_address = connection.get("mac_address", "unknown")
                destination_device = connection.get("destination_device")
                if destination_device:
                    descriptions.append(
                        f"{source_interface} on {source_device} is connected to device {destination_device} [{mac_address}]"
                    )
                else:
                    host = self.connection_map.get("hosts", {}).get(mac_address, {})
                    host_label = host.get("hostname")
                    if not host_label:
                        ip_addresses = host.get("ip_addresses", [])
                        if ip_addresses:
                            host_label = ip_addresses[0]

                    if host_label:
                        descriptions.append(
                            f"{source_interface} on {source_device} is connected to host {host_label} [{mac_address}]"
                        )
                    else:
                        descriptions.append(
                            f"{source_interface} on {source_device} is connected to device with MAC {mac_address}"
                        )
            
            elif conn_type == "host_connection":
                source_device = connection.get("source_device", "unknown")
                source_interface = connection.get("source_interface", "unknown")
                destination_host = connection.get("destination_host", "unknown")
                descriptions.append(f"{source_interface} on {source_device} is connected to host {destination_host}")
        
        return descriptions

def main():
    """Example usage of the ConnectionMapper."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build connection map from collected Mikrotik data")
    parser.add_argument("input_file", help="JSON file with collected device data")
    parser.add_argument("-o", "--output", help="Output file for connection map")
    parser.add_argument("-r", "--readable", action="store_true", help="Generate readable output")
    
    args = parser.parse_args()
    
    # Create connection mapper
    mapper = ConnectionMapper()
    
    # Load data
    mapper.load_data(args.input_file)
    
    # Build connection map
    connection_map = mapper.build_connection_map()
    
    # Save map if output file specified
    if args.output:
        mapper.save_map(args.output, connection_map)
        print(f"Connection map saved to {args.output}")
    
    # Generate readable output if requested
    if args.readable:
        descriptions = mapper.generate_readable_output()
        print("\nConnection Descriptions:")
        print("========================")
        for desc in descriptions:
            print(desc)
    
    # Print summary to stdout if no output file
    if not args.output and not args.readable:
        print(json.dumps(connection_map, indent=2, default=str))

if __name__ == "__main__":
    main()
