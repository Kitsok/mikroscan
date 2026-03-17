#!/usr/bin/env python3
"""Native RouterOS API client for MikroTik devices."""

import logging
from typing import Any, Dict, List

try:
    import routeros_api
except ImportError:  # pragma: no cover - exercised indirectly by connect()
    routeros_api = None


logger = logging.getLogger(__name__)


class MikrotikAPIClient:
    """RouterOS native API client."""

    def __init__(
        self,
        hostname: str,
        username: str,
        password: str = None,
        key_filename: str = None,
        port: int = 8728,
        timeout: int = 10,
        use_ssl: bool = False,
    ):
        self.hostname = hostname
        self.username = username
        self.password = password or ""
        self.key_filename = key_filename
        self.port = port
        self.timeout = timeout
        self.use_ssl = use_ssl
        self.pool = None
        self.api = None
        self.connected = False

    def connect(self) -> bool:
        """Establish a RouterOS API connection."""
        if routeros_api is None:
            logger.error(
                "routeros-api is not installed. Run `pip3 install -r requirements.txt`."
            )
            return False

        try:
            if self.key_filename:
                logger.warning("RouterOS API backend ignores key files")

            self.pool = routeros_api.RouterOsApiPool(
                self.hostname,
                username=self.username,
                password=self.password,
                port=self.port,
                use_ssl=self.use_ssl,
                plaintext_login=not self.use_ssl,
            )
            self.pool.set_timeout(self.timeout)
            self.api = self.pool.get_api()
            self.connected = True
            logger.info(f"Successfully connected to {self.hostname} via RouterOS API")
            return True
        except Exception as exc:
            logger.error(f"API error connecting to {self.hostname}: {exc}")
            return False

    def disconnect(self):
        """Close the RouterOS API connection."""
        if self.pool:
            try:
                self.pool.disconnect()
            except Exception as exc:
                logger.warning(f"Failed to disconnect API session from {self.hostname}: {exc}")
        self.pool = None
        self.api = None
        self.connected = False

    def _normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize RouterOS API keys to the existing collector schema."""
        normalized = {}
        for key, value in record.items():
            normalized[key.lstrip(".").replace("-", "_")] = value
        return normalized

    def _resource_get(self, path: str, **kwargs) -> List[Dict[str, Any]]:
        """Read a resource via RouterOS API and normalize the results."""
        if not self.connected or self.api is None:
            raise RuntimeError("Not connected to device")

        resource = self.api.get_resource(path)
        return [self._normalize_record(record) for record in resource.get(**kwargs)]

    def _resource_call(
        self,
        path: str,
        command: str,
        arguments: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """Call a RouterOS command and normalize any returned rows."""
        if not self.connected or self.api is None:
            raise RuntimeError("Not connected to device")

        resource = self.api.get_resource(path)
        rows = resource.call(command, arguments or {})
        return [self._normalize_record(record) for record in rows]

    def get_device_info(self) -> Dict[str, Any]:
        """Get basic device information."""
        info = {
            "hostname": self.hostname,
            "identity": "",
            "version": "",
            "model": "",
            "architecture": "",
        }

        identity_rows = self._resource_get("/system/identity")
        if identity_rows:
            info["identity"] = identity_rows[0].get("name", "")

        resource_rows = self._resource_get("/system/resource")
        if resource_rows:
            resource = resource_rows[0]
            info["version"] = resource.get("version", "")
            info["model"] = resource.get("board_name", "")
            info["architecture"] = resource.get("architecture_name", "")

        return info

    def get_interfaces(self) -> List[Dict[str, Any]]:
        """Get information about network interfaces."""
        interfaces = self._resource_get("/interface")
        interfaces_by_name = {
            interface.get("name"): interface
            for interface in interfaces
            if interface.get("name")
        }

        for ethernet_interface in self._resource_get("/interface/ethernet"):
            interface_name = ethernet_interface.get("name")
            if interface_name and interface_name in interfaces_by_name:
                interfaces_by_name[interface_name].update(ethernet_interface)
                if "poe_out" in ethernet_interface:
                    try:
                        poe_rows = self._resource_call(
                            "/interface/ethernet/poe",
                            "monitor",
                            {"numbers": interface_name, "once": None},
                        )
                    except Exception as exc:
                        logger.debug(
                            "PoE monitor failed for %s on %s via API: %s",
                            interface_name,
                            self.hostname,
                            exc,
                        )
                        poe_rows = []

                    if poe_rows:
                        interfaces_by_name[interface_name].update(poe_rows[0])

        return interfaces

    def get_bridge_ports(self) -> List[Dict[str, Any]]:
        return self._resource_get("/interface/bridge/port")

    def get_arp_table(self) -> List[Dict[str, Any]]:
        return self._resource_get("/ip/arp")

    def get_dhcp_leases(self) -> List[Dict[str, Any]]:
        return self._resource_get("/ip/dhcp-server/lease")

    def get_neighbors(self) -> List[Dict[str, Any]]:
        return self._resource_get("/ip/neighbor")

    def get_dns_static_entries(self) -> List[Dict[str, Any]]:
        return self._resource_get("/ip/dns/static")

    def get_bridge_host_entries(self) -> List[Dict[str, Any]]:
        return self._resource_get("/interface/bridge/host")

    def get_ip_addresses(self) -> List[Dict[str, Any]]:
        return self._resource_get("/ip/address")
