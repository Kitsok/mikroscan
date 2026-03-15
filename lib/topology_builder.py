#!/usr/bin/env python3
"""Topology builder for MikroTik Mapper."""

import ipaddress
import json
import logging
import os
import re
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TopologyBuilder:
    """Builds a rooted network topology tree from collected device data."""
    
    def __init__(self):
        """Initialize the topology builder."""
        self.devices_data = {}
        self.mac_name_map = {}
        self.mac_ip_map = {}
        self.ip_name_map = {}
        self.mac_port_map = {}

    def _clean_name(self, name: str) -> str:
        """Normalize display names parsed from RouterOS output."""
        if not name:
            return ""
        return name.strip().strip('"').strip()

    def _build_known_device_maps(self):
        """
        Build MAC-to-device and MAC-to-IP maps from the collected MikroTik
        devices themselves.

        Returns:
            tuple[dict, dict]: MAC-to-name and MAC-to-IP mappings
        """
        device_name_map = {}
        device_ip_map = {}

        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue

            device_name = self._clean_name(
                device_data.get("device_info", {}).get("identity", hostname)
            )
            device_ip = device_data.get("hostname", hostname)

            for interface in device_data.get("interfaces", []):
                mac = (interface.get("mac_address") or interface.get("link_layer_address") or "").upper()
                if not mac:
                    continue
                if mac == "00:00:00:00:00:00":
                    continue
                if device_name:
                    device_name_map[mac] = device_name
                if device_ip:
                    device_ip_map[mac] = device_ip

        return device_name_map, device_ip_map

    def _build_known_identity_ip_map(self) -> Dict[str, str]:
        """Build a mapping of managed device identity to management IP."""
        identity_ip_map = {}

        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue

            identity = self._clean_name(
                device_data.get("device_info", {}).get("identity", hostname)
            )
            management_ip = device_data.get("hostname", hostname)
            if identity and management_ip:
                identity_ip_map[identity] = management_ip

        return identity_ip_map

    def _is_physical_interface(self, interface: str) -> bool:
        """Return True for physical-facing interfaces we want in the tree."""
        if not interface:
            return False

        interface = interface.lower()
        return any(
            interface.startswith(prefix)
            for prefix in ("ether", "wifi", "wlan", "sfp", "combo")
        )

    def _build_local_device_mac_sets(self) -> Dict[str, Set[str]]:
        """Build a map of managed device names to their own interface MACs."""
        device_mac_sets = defaultdict(set)

        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue

            device_name = self._clean_name(
                device_data.get("device_info", {}).get("identity", hostname)
            )
            for interface in device_data.get("interfaces", []):
                mac = (
                    interface.get("mac_address")
                    or interface.get("link_layer_address")
                    or ""
                ).upper()
                if mac and mac != "00:00:00:00:00:00":
                    device_mac_sets[device_name].add(mac)

        return device_mac_sets

    def _find_public_ip_entries(self, device_data: Dict[str, Any]) -> List[Dict[str, str]]:
        """Return public IPv4 addresses with their owning interface names."""
        public_entries = []

        for ip_entry in device_data.get("ip_addresses", []):
            address = ip_entry.get("address", "")
            if not address:
                continue

            ip_part = address.split("/")[0]
            if not self._is_public_ip(ip_part):
                continue

            interface_name = (
                ip_entry.get("actual_interface")
                or ip_entry.get("interface")
                or ""
            )
            public_entries.append({
                "address": address,
                "interface": interface_name,
            })

        return public_entries

    def _score_interface_parent_candidate(
        self,
        child_interface: Dict[str, Any],
        candidate_interface: Dict[str, Any],
    ) -> int:
        """Rank likely lower-layer parent interfaces for WAN chain inference."""
        child_name = self._clean_name(child_interface.get("name", "")).lower()
        candidate_name = self._clean_name(candidate_interface.get("name", "")).lower()
        candidate_type = candidate_interface.get("type", "").lower()
        candidate_default = self._clean_name(
            candidate_interface.get("default_name", "")
        ).lower()
        score = 0

        if "wan" in child_name and "wan" in candidate_name:
            score += 10
        if candidate_type == "vlan":
            score += 8
        elif candidate_type == "ether":
            score += 6

        child_mac = (child_interface.get("mac_address") or "").upper()
        candidate_mac = (candidate_interface.get("mac_address") or "").upper()
        if child_mac and candidate_mac and child_mac == candidate_mac:
            score += 20

        if candidate_default and candidate_default in child_name:
            score += 6
        if candidate_name and candidate_name in child_name:
            score += 4

        shared_tokens = (
            set(token for token in re.split(r"[^a-z0-9]+", child_name) if token)
            & set(token for token in re.split(r"[^a-z0-9]+", candidate_name) if token)
        ) - {"pppoe", "out", "vlan"}
        score += len(shared_tokens) * 2

        return score

    def _find_interface_parent(
        self,
        interface_name: str,
        interfaces_by_name: Dict[str, Dict[str, Any]],
    ) -> str:
        """Infer a lower-layer parent interface for the given interface."""
        current_interface = interfaces_by_name.get(interface_name)
        if not current_interface:
            return ""

        for key in (
            "interface",
            "master_interface",
            "parent_interface",
            "underlying_interface",
            "running_on",
        ):
            parent_name = self._clean_name(current_interface.get(key, ""))
            if parent_name and parent_name in interfaces_by_name:
                return parent_name

        candidate_scores = []
        for candidate_name, candidate_interface in interfaces_by_name.items():
            if candidate_name == interface_name:
                continue

            score = self._score_interface_parent_candidate(
                current_interface,
                candidate_interface,
            )
            if score > 0:
                candidate_scores.append((score, candidate_name))

        if not candidate_scores:
            return ""

        candidate_scores.sort(reverse=True)
        best_score, best_name = candidate_scores[0]
        if best_score < 8:
            return ""
        return best_name

    def _build_wan_chain(
        self,
        device_data: Dict[str, Any],
        public_entry: Dict[str, str],
    ) -> List[str]:
        """Build physical-to-logical WAN interface chain for a public IP."""
        interfaces_by_name = {
            self._clean_name(interface.get("name", "")): interface
            for interface in device_data.get("interfaces", [])
            if interface.get("name")
        }

        chain = []
        current_name = self._clean_name(public_entry.get("interface", ""))
        seen_names = set()

        while current_name and current_name not in seen_names:
            chain.append(current_name)
            seen_names.add(current_name)
            current_name = self._find_interface_parent(current_name, interfaces_by_name)

        chain.reverse()
        return chain

    def _format_root_wan_summary(self, device_data: Dict[str, Any]) -> str:
        """Format WAN summary including physical-to-logical interface chain."""
        public_entries = self._find_public_ip_entries(device_data)
        if not public_entries:
            return ""

        formatted_entries = []
        for public_entry in public_entries[:3]:
            chain = self._build_wan_chain(device_data, public_entry)
            if chain:
                formatted_entries.append(
                    f"{' -> '.join(chain)} ({public_entry['address']})"
                )
            else:
                formatted_entries.append(public_entry["address"])

        return " | ".join(formatted_entries)

    def _get_interfaces_by_name(
        self,
        device_data: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Map interface names to interface records."""
        return {
            self._clean_name(interface.get("name", "")): interface
            for interface in device_data.get("interfaces", [])
            if interface.get("name")
        }

    def _get_interface_mac(self, interface_data: Dict[str, Any]) -> str:
        """Return the best MAC address available for an interface."""
        return (
            interface_data.get("mac_address")
            or interface_data.get("link_layer_address")
            or ""
        ).upper()

    def _get_vlan_label(self, interface_name: str, interface_data: Dict[str, Any]) -> str:
        """Return a display suffix for VLAN interfaces when VLAN ID is known."""
        if interface_data.get("type", "").lower() != "vlan":
            return ""

        vlan_id = (
            interface_data.get("vlan_id")
            or interface_data.get("vlanid")
            or interface_data.get("vlan")
            or ""
        )
        if not vlan_id:
            match = re.search(r"vlan[-_ ]?(\d+)", interface_name, re.IGNORECASE)
            if match:
                vlan_id = match.group(1)

        if vlan_id:
            return f" [vlan {vlan_id}]"
        return ""

    def _format_interface_label(
        self,
        interface_name: str,
        interface_data: Dict[str, Any],
        address: str = "",
    ) -> str:
        """Format an interface node label for the topology tree."""
        label = interface_name
        if address:
            label += f" ({address})"

        mac_address = self._get_interface_mac(interface_data)
        if mac_address:
            label += f" [{mac_address}]"

        label += self._get_vlan_label(interface_name, interface_data)
        return label

    def _build_wan_port_overrides(
        self,
        device_data: Dict[str, Any],
    ) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, str]]:
        """Build synthetic WAN branches rendered under the root WAN port."""
        public_entries = self._find_public_ip_entries(device_data)
        if not public_entries:
            return {}, {}

        interfaces_by_name = self._get_interfaces_by_name(device_data)
        port_overrides: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        port_labels: Dict[str, str] = {}

        for public_entry in public_entries[:3]:
            chain = self._build_wan_chain(device_data, public_entry)
            if not chain:
                continue

            root_port = chain[0]
            root_interface = interfaces_by_name.get(root_port, {})
            if not port_labels.get(root_port):
                if len(chain) == 1:
                    port_labels[root_port] = self._format_interface_label(
                        root_port,
                        root_interface,
                        public_entry["address"],
                    )
                else:
                    port_labels[root_port] = self._format_interface_label(
                        root_port,
                        root_interface,
                    )

            chain_labels = []
            for chain_index, interface_name in enumerate(chain[1:], start=1):
                interface_data = interfaces_by_name.get(interface_name, {})
                address = (
                    public_entry["address"]
                    if chain_index == len(chain) - 1
                    else ""
                )
                chain_labels.append(
                    self._format_interface_label(
                        interface_name,
                        interface_data,
                        address=address,
                    )
                )

            if chain_labels:
                port_overrides[root_port].append({
                    "type": "wan_chain",
                    "chain_labels": chain_labels,
                })

        return dict(port_overrides), port_labels
        
    def _is_public_ip(self, ip):
        """
        Check if an IP address is public (not private/rfc1918).
        
        Args:
            ip (str): IP address to check
            
        Returns:
            bool: True if public IP, False if private
        """
        if not ip:
            return False

        try:
            address = ipaddress.ip_address(ip)
            return address.is_global and not address.is_multicast
        except ValueError:
            return False
    
    def _identify_edge_routers(self):
        """
        Identify edge routers (devices with public IP addresses).
        
        Returns:
            dict: Dictionary mapping device names to lists of public IPs
        """
        edge_routers = defaultdict(list)
        
        # Check each device's IP addresses
        for device_ip, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue
                
            device_name = device_data["device_info"].get("identity", device_ip)
            public_ips = []
            
            # Look through IP address information for public IPs
            for ip_entry in device_data.get("ip_addresses", []):
                # Get the IP address/network (format like "192.168.1.1/24")
                address = ip_entry.get("address", "")
                if "/" in address:
                    ip_part = address.split("/")[0]
                    if self._is_public_ip(ip_part):
                        if address not in public_ips:
                            public_ips.append(address)
                elif "." in address:  # Just IP without CIDR
                    if self._is_public_ip(address):
                        if address not in public_ips:
                            public_ips.append(address)
            
            # If device has public IPs, it's an edge router
            if public_ips:
                edge_routers[device_name] = public_ips
        
        logger.info(f"Identified {len(edge_routers)} edge routers")
        return edge_routers
        
    def load_data(self, filename: str) -> bool:
        """
        Load collected device data from a JSON file.
        
        Args:
            filename (str): Input file path
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with open(filename, 'r') as f:
                self.devices_data = json.load(f)
            logger.info(f"Device data loaded from {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to load data from {filename}: {e}")
            return False
    
    def build_mac_name_map(self):
        """
        Build comprehensive MAC-to-name mapping from multiple sources.
        Priority: DNS > DHCP > Neighbors
        """
        logger.info("Building MAC-to-name mapping...")
        
        # Temporary maps for each source
        device_map, _ = self._build_known_device_maps()
        dns_map = {}
        dhcp_map = {}
        neighbor_map = {}

        dns_ip_map = {}

        # Process DNS static entries into IP-to-name mappings first. RouterOS
        # DNS static records typically provide name/address pairs, not MACs.
        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue

            for dns_entry in device_data.get("dns_static", []):
                ip = dns_entry.get("address", "")
                name = dns_entry.get("name", "")
                if ip and name:
                    dns_ip_map[ip] = name

        # Resolve DNS names to MACs through DHCP and ARP IP associations.
        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue

            for dhcp_entry in device_data.get("dhcp_leases", []):
                mac = dhcp_entry.get("mac_address", "").upper()
                ip = dhcp_entry.get("active_address") or dhcp_entry.get("address", "")
                name = self._clean_name(dns_ip_map.get(ip, ""))
                if mac and name:
                    dns_map[mac] = name

            for arp_entry in device_data.get("arp_table", []):
                mac = arp_entry.get("mac_address", "").upper()
                ip = arp_entry.get("address", "")
                name = self._clean_name(dns_ip_map.get(ip, ""))
                if mac and name and mac not in dns_map:
                    dns_map[mac] = name
        
        # Process DHCP leases (medium priority)
        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue
                
            for dhcp_entry in device_data.get("dhcp_leases", []):
                mac = dhcp_entry.get("mac_address", "").upper()
                host_name = self._clean_name(dhcp_entry.get("host_name", ""))
                if mac and host_name:
                    dhcp_map[mac] = host_name
        
        # Process neighbors (lowest priority)
        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue
                
            for neighbor in device_data.get("neighbors", []):
                mac = neighbor.get("mac_address", "").upper()
                identity = self._clean_name(neighbor.get("identity", ""))
                if mac and identity:
                    neighbor_map[mac] = identity
        
        # Build final map with priority
        all_macs = set(device_map.keys()) | set(dns_map.keys()) | set(dhcp_map.keys()) | set(neighbor_map.keys())
        
        for mac in all_macs:
            if mac in device_map:
                self.mac_name_map[mac] = device_map[mac]
            elif mac in dns_map:
                self.mac_name_map[mac] = dns_map[mac]
            elif mac in dhcp_map:
                self.mac_name_map[mac] = dhcp_map[mac]
            elif mac in neighbor_map:
                self.mac_name_map[mac] = neighbor_map[mac]
        
        logger.info(f"Built MAC-to-name map with {len(self.mac_name_map)} entries")
    
    def build_mac_ip_map(self):
        """Build MAC-to-IP mapping from DHCP leases."""
        logger.info("Building MAC-to-IP mapping...")

        _, device_ip_map = self._build_known_device_maps()
        self.mac_ip_map.update(device_ip_map)
        
        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue
                
            for dhcp_entry in device_data.get("dhcp_leases", []):
                mac = dhcp_entry.get("mac_address", "").upper()
                active_address = dhcp_entry.get("active_address", "")
                if mac and active_address:
                    self.mac_ip_map[mac] = active_address
        
        logger.info(f"Built MAC-to-IP map with {len(self.mac_ip_map)} entries")
    
    def build_ip_name_map(self):
        """Build IP-to-name mapping from DNS static entries."""
        logger.info("Building IP-to-name mapping...")
        
        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue
                
            for dns_entry in device_data.get("dns_static", []):
                ip = dns_entry.get("address", "")
                name = dns_entry.get("name", "")
                if ip and name:
                    self.ip_name_map[ip] = name
        
        logger.info(f"Built IP-to-name map with {len(self.ip_name_map)} entries")
    
    def build_mac_port_map(self):
        """Build MAC-to-physical port mapping from bridge host entries."""
        logger.info("Building MAC-to-port mapping...")
        
        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue
                
            device_name = device_data["device_info"].get("identity", hostname)
            
            for bridge_host in device_data.get("bridge_hosts", []):
                mac = bridge_host.get("mac_address", "").upper()
                interface = bridge_host.get("interface", "")
                if mac and interface:
                    if self._is_physical_interface(interface):
                        self.mac_port_map[mac] = {
                            "device": device_name,
                            "port": interface
                        }
        
        logger.info(f"Built MAC-to-port map with {len(self.mac_port_map)} entries")
    
    def _build_device_port_endpoints(self) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """Build per-device endpoint lists keyed by physical port."""
        device_name_map, device_ip_map = self._build_known_device_maps()
        managed_identity_ip_map = self._build_known_identity_ip_map()
        local_device_mac_sets = self._build_local_device_mac_sets()
        device_port_endpoints: Dict[str, Dict[str, Dict[Tuple[str, str], Dict[str, Any]]]] = (
            defaultdict(lambda: defaultdict(dict))
        )

        for hostname, device_data in self.devices_data.items():
            if not device_data.get("connected", False):
                continue

            device_name = self._clean_name(
                device_data.get("device_info", {}).get("identity", hostname)
            )

            for bridge_host in device_data.get("bridge_hosts", []):
                mac = bridge_host.get("mac_address", "").upper()
                port = bridge_host.get("interface") or bridge_host.get("on_interface") or ""

                if not mac or not self._is_physical_interface(port):
                    continue
                if mac == "00:00:00:00:00:00":
                    continue
                if mac in local_device_mac_sets.get(device_name, set()):
                    continue

                if mac in device_name_map:
                    remote_name = self._clean_name(device_name_map[mac])
                    if not remote_name or remote_name == device_name:
                        continue

                    key = ("device", remote_name)
                    endpoint = {
                        "type": "device",
                        "name": remote_name,
                        "mac": mac,
                        "ip": managed_identity_ip_map.get(
                            remote_name,
                            device_ip_map.get(mac, "Unknown IP"),
                        ),
                    }
                else:
                    host_name = self._clean_name(self.mac_name_map.get(mac, ""))
                    host_ip = self.mac_ip_map.get(mac, "Unknown IP")
                    display_name = host_name or host_ip or mac
                    key = ("host", mac)
                    endpoint = {
                        "type": "host",
                        "name": display_name,
                        "mac": mac,
                        "ip": host_ip,
                    }

                device_port_endpoints[device_name][port][key] = endpoint

        normalized_endpoints = {}
        for device_name, port_map in device_port_endpoints.items():
            normalized_endpoints[device_name] = {}
            for port, endpoints in port_map.items():
                normalized_endpoints[device_name][port] = sorted(
                    endpoints.values(),
                    key=lambda endpoint: (
                        endpoint["type"] != "device",
                        endpoint["name"].lower(),
                        endpoint["mac"],
                    ),
                )

        return normalized_endpoints

    def _find_upstream_port(
        self,
        device_name: str,
        parent_name: str,
        device_port_endpoints: Dict[str, Dict[str, List[Dict[str, Any]]]],
    ) -> str:
        """Return the local port on device_name that faces parent_name."""
        for port in sorted(device_port_endpoints.get(device_name, {})):
            endpoints = device_port_endpoints[device_name][port]
            for endpoint in endpoints:
                if endpoint["type"] == "device" and endpoint["name"] == parent_name:
                    return port
        return ""

    def _format_endpoint_label(self, endpoint: Dict[str, Any]) -> str:
        """Format a device or host endpoint for topology output."""
        label = endpoint["name"]
        ip = endpoint.get("ip", "")
        mac = endpoint["mac"]

        if endpoint["type"] == "device":
            if ip and ip != "Unknown IP":
                return f"{label} ({ip}) [{mac}]"
            return f"{label} [{mac}]"

        if ip and ip != "Unknown IP" and ip != label:
            return f"{label} ({ip}) [{mac}]"
        return f"{label} [{mac}]"

    def _render_device_tree(
        self,
        device_name: str,
        device_port_endpoints: Dict[str, Dict[str, List[Dict[str, Any]]]],
        visited_devices: Set[str],
        upstream_port: str = "",
        prefix: str = "",
        port_overrides: Dict[str, List[Dict[str, Any]]] = None,
        port_labels: Dict[str, str] = None,
    ) -> List[str]:
        """Render a recursive per-port tree for one managed device."""
        lines = []
        port_overrides = port_overrides or {}
        port_labels = port_labels or {}
        ports = [
            port
            for port in sorted(
                set(device_port_endpoints.get(device_name, {})) | set(port_overrides)
            )
            if port != upstream_port
        ]

        for port_index, port in enumerate(ports):
            port_connector = "└─" if port_index == len(ports) - 1 else "├─"
            port_prefix = prefix + ("   " if port_index == len(ports) - 1 else "│  ")
            display_port = port_labels.get(port, port)
            lines.append(f"{prefix}{port_connector} {display_port}")

            endpoints = port_overrides.get(
                port,
                device_port_endpoints.get(device_name, {}).get(port, []),
            )
            if any(endpoint["type"] == "device" for endpoint in endpoints):
                endpoints = [
                    endpoint for endpoint in endpoints
                    if endpoint["type"] == "device"
                ]

            for endpoint_index, endpoint in enumerate(endpoints):
                endpoint_connector = "└─" if endpoint_index == len(endpoints) - 1 else "├─"
                endpoint_prefix = port_prefix + (
                    "   " if endpoint_index == len(endpoints) - 1 else "│  "
                )

                if endpoint["type"] == "wan_chain":
                    chain_labels = endpoint.get("chain_labels", [])
                    if not chain_labels:
                        continue

                    lines.append(f"{port_prefix}{endpoint_connector} {chain_labels[0]}")
                    chain_prefix = endpoint_prefix
                    for chain_label in chain_labels[1:]:
                        lines.append(f"{chain_prefix}└─ {chain_label}")
                        chain_prefix += "   "
                    continue

                if endpoint["type"] == "device":
                    child_name = endpoint["name"]
                    if child_name in visited_devices:
                        lines.append(
                            f"{port_prefix}{endpoint_connector} "
                            f"{self._format_endpoint_label(endpoint)} [already shown]"
                        )
                        continue

                    lines.append(
                        f"{port_prefix}{endpoint_connector} "
                        f"{self._format_endpoint_label(endpoint)}"
                    )
                    visited_devices.add(child_name)
                    child_upstream_port = self._find_upstream_port(
                        child_name,
                        device_name,
                        device_port_endpoints,
                    )
                    child_lines = self._render_device_tree(
                        child_name,
                        device_port_endpoints,
                        visited_devices,
                        upstream_port=child_upstream_port,
                        prefix=endpoint_prefix,
                    )
                    if child_lines:
                        lines.extend(child_lines)
                    else:
                        lines.append(f"{endpoint_prefix}└─ no downstream endpoints")
                    continue

                lines.append(
                    f"{port_prefix}{endpoint_connector} "
                    f"{self._format_endpoint_label(endpoint)}"
                )

        return lines

    def generate_topology_output(self, output_file: str = "data/topology.txt"):
        """
        Generate the final rooted topology tree.
        
        Args:
            output_file (str): Output file path
        """
        logger.info("Generating topology output...")
        
        device_port_endpoints = self._build_device_port_endpoints()
        managed_identity_ip_map = self._build_known_identity_ip_map()
        edge_routers = self._identify_edge_routers()
        connected_device_data = {
            self._clean_name(device_data.get("device_info", {}).get("identity", hostname)): device_data
            for hostname, device_data in self.devices_data.items()
            if device_data.get("connected", False)
        }
        connected_devices = sorted(
            self._clean_name(device_data.get("device_info", {}).get("identity", hostname))
            for hostname, device_data in self.devices_data.items()
            if device_data.get("connected", False)
        )
        root_devices = sorted(edge_routers.keys()) or connected_devices[:1]
        remaining_devices = [
            device_name for device_name in connected_devices
            if device_name not in root_devices
        ]

        lines = []
        lines.append("NETWORK TOPOLOGY")
        lines.append("================")
        lines.append("")

        globally_rendered = set()

        for root_device in root_devices:
            if root_device in globally_rendered:
                continue

            root_ip = managed_identity_ip_map.get(root_device, "Unknown IP")
            header = f"{root_device} ({root_ip})"
            lines.append(header)
            root_device_data = connected_device_data.get(root_device, {})
            port_overrides, port_labels = self._build_wan_port_overrides(root_device_data)
            visited_devices = {root_device}
            tree_lines = self._render_device_tree(
                root_device,
                device_port_endpoints,
                visited_devices,
                port_overrides=port_overrides,
                port_labels=port_labels,
            )
            if tree_lines:
                lines.extend(tree_lines)
            else:
                lines.append("└─ no port data")
            lines.append("")
            globally_rendered.update(visited_devices)

        unattached_devices = [
            device_name
            for device_name in remaining_devices
            if device_name not in globally_rendered
        ]
        if unattached_devices:
            lines.append("UNREACHED MANAGED DEVICES")
            lines.append("------------------------")
            for device_name in unattached_devices:
                device_ip = managed_identity_ip_map.get(device_name, "Unknown IP")
                lines.append(f"{device_name} ({device_ip})")
                tree_lines = self._render_device_tree(
                    device_name,
                    device_port_endpoints,
                    {device_name},
                )
                if tree_lines:
                    lines.extend(tree_lines)
                else:
                    lines.append("└─ no port data")
                lines.append("")

        # Write to file
        try:
            output_dir = os.path.dirname(output_file)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(output_file, 'w') as f:
                f.write('\n'.join(lines))
            logger.info(f"Topology output saved to {output_file}")
            print(f"Topology saved to: {output_file}")
        except Exception as e:
            logger.error(f"Failed to save topology output to {output_file}: {e}")
    
    def build_complete_topology(self, data_file: str, output_file: str = "data/topology.txt"):
        """
        Execute the complete topology building process.
        
        Args:
            data_file (str): Input data file
            output_file (str): Output file for topology
        """
        # Load data
        if not self.load_data(data_file):
            return False
        
        # Build mapping tables
        self.build_mac_name_map()
        self.build_mac_ip_map()
        self.build_ip_name_map()
        self.build_mac_port_map()

        # Generate output
        self.generate_topology_output(output_file)
        
        return True

def main():
    """Example usage of the TopologyBuilder."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build network topology from collected MikroTik data")
    parser.add_argument("input_file", help="JSON file with collected device data")
    parser.add_argument("-o", "--output", default="data/topology.txt", help="Output file for topology")
    
    args = parser.parse_args()
    
    # Create topology builder
    builder = TopologyBuilder()
    
    # Build topology
    if builder.build_complete_topology(args.input_file, args.output):
        print(f"Successfully built topology in {args.output}")
    else:
        print("Failed to build topology")

if __name__ == "__main__":
    main()
