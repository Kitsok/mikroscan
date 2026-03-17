#!/usr/bin/env python3
"""Local HTTP API and static frontend for topology viewing and refresh actions."""

import json
import logging
import mimetypes
import os
import subprocess
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse

from lib.topology_builder import TopologyBuilder

logger = logging.getLogger(__name__)
WEB_ROOT = Path(__file__).resolve().parent.parent / "web"
BUILD_INFO_FILE = WEB_ROOT / "build_info.json"
VERSION_FILE = WEB_ROOT.parent / "VERSION"


class MikroscanAPIService:
    """Coordinate Mikroscan topology reads and background refresh actions."""

    def __init__(
        self,
        mapper,
        *,
        scan_file: str,
        data_file: str,
        map_output: str,
        readable_output: str,
        topology_output: str,
        topology_json_output: str,
        layout_output: str,
        state_output: str,
        username: str | None,
        password: str | None,
        key_file: str | None,
        backend: str,
        collection_port: int,
        timeout: int,
        verbose: bool,
        use_api_ssl: bool,
        refresh_interval: int = 0,
        default_scan_range: str = "",
    ):
        self.mapper = mapper
        self.scan_file = scan_file
        self.data_file = data_file
        self.map_output = map_output
        self.readable_output = readable_output
        self.topology_output = topology_output
        self.topology_json_output = topology_json_output
        self.layout_output = layout_output
        self.state_output = state_output
        self.username = username
        self.password = password
        self.key_file = key_file
        self.backend = backend
        self.collection_port = collection_port
        self.timeout = timeout
        self.verbose = verbose
        self.use_api_ssl = use_api_ssl
        self.refresh_interval = max(0, int(refresh_interval))
        self.default_scan_range = default_scan_range.strip()

        self._status_lock = threading.Lock()
        self._worker_thread: threading.Thread | None = None
        self._scheduler_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._status = {
            "running": False,
            "current_action": "",
            "last_action": "",
            "last_started_at": "",
            "last_finished_at": "",
            "last_success": None,
            "last_error": "",
            "last_result": {},
            "last_scan_range": "",
        }
        self._load_runtime_state()

    def _utc_now(self) -> str:
        """Return the current UTC timestamp in ISO8601 form."""
        return datetime.now(timezone.utc).isoformat()

    def _topology_summary(self) -> Dict[str, Any]:
        """Read quick summary counts from the structured topology file."""
        if not os.path.exists(self.topology_json_output):
            return {}

        try:
            with open(self.topology_json_output, "r") as handle:
                model = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("Topology JSON summary unavailable: %s", exc)
            return {}
        except Exception as exc:
            logger.error("Failed to read topology JSON summary: %s", exc)
            return {}

        return {
            "generated_at": model.get("generated_at", ""),
            "root_count": len(model.get("root_ids", [])),
            "node_count": len(model.get("nodes", [])),
            "edge_count": len(model.get("edges", [])),
            "unresolved_host_count": len(model.get("unresolved_hosts", [])),
        }

    def _build_id(self) -> str:
        """Resolve the current build identifier for UI display."""
        env_build_id = os.environ.get("MIKROSCAN_BUILD_ID", "").strip()
        if env_build_id:
            return env_build_id

        project_root = WEB_ROOT.parent
        git_dir = project_root / ".git"
        if git_dir.exists():
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--short", "HEAD"],
                    cwd=project_root,
                    capture_output=True,
                    text=True,
                    timeout=2,
                    check=True,
                )
                build_id = result.stdout.strip()
                if build_id:
                    return build_id
            except Exception as exc:
                logger.debug("Unable to resolve git build id: %s", exc)

        if BUILD_INFO_FILE.exists():
            try:
                with open(BUILD_INFO_FILE, "r") as handle:
                    payload = json.load(handle)
                build_id = str(payload.get("build_id", "")).strip()
                if build_id:
                    return build_id
            except Exception as exc:
                logger.debug("Unable to read build info file: %s", exc)

        version = self._app_version()
        if version != "unknown":
            return version
        return "unknown"

    def _app_version(self) -> str:
        """Resolve the current installable version for UI display."""
        env_version = os.environ.get("MIKROSCAN_VERSION", "").strip()
        if env_version:
            return env_version

        if VERSION_FILE.exists():
            try:
                version = VERSION_FILE.read_text(encoding="utf-8").strip()
                if version:
                    return version
            except Exception as exc:
                logger.debug("Unable to read VERSION file: %s", exc)

        if BUILD_INFO_FILE.exists():
            try:
                with open(BUILD_INFO_FILE, "r") as handle:
                    payload = json.load(handle)
                version = str(payload.get("version", "")).strip()
                if version:
                    return version
            except Exception as exc:
                logger.debug("Unable to read build version from build_info.json: %s", exc)

        return "unknown"

    def get_status(self) -> Dict[str, Any]:
        """Return current API service status plus topology summary."""
        with self._status_lock:
            status = dict(self._status)

        status["topology"] = self._topology_summary()
        status["build_id"] = self._build_id()
        status["app_version"] = self._app_version()
        status["scan_file"] = self.scan_file
        status["data_file"] = self.data_file
        status["auto_refresh_interval"] = self.refresh_interval
        status["auto_refresh_enabled"] = self.refresh_interval > 0
        status["default_scan_range"] = self.default_scan_range
        return status

    def _load_runtime_state(self) -> None:
        """Load persistent service UI state."""
        if not os.path.exists(self.state_output):
            return
        try:
            with open(self.state_output, "r") as handle:
                payload = json.load(handle)
        except Exception as exc:
            logger.debug("Unable to load service state: %s", exc)
            return

        last_scan_range = str(payload.get("last_scan_range", "")).strip()
        if last_scan_range:
            self._status["last_scan_range"] = last_scan_range

    def _save_runtime_state(self) -> None:
        """Persist service UI state."""
        try:
            output_dir = os.path.dirname(self.state_output)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(self.state_output, "w") as handle:
                json.dump(
                    {
                        "last_scan_range": self._status.get("last_scan_range", ""),
                        "saved_at": self._utc_now(),
                    },
                    handle,
                    indent=2,
                )
        except Exception as exc:
            logger.debug("Unable to save service state: %s", exc)

    def load_topology_model(self) -> Dict[str, Any]:
        """Load the current structured topology JSON."""
        with open(self.topology_json_output, "r") as handle:
            return json.load(handle)

    def _load_topology_model_if_exists(self) -> Dict[str, Any] | None:
        """Load an existing topology model if present."""
        if not os.path.exists(self.topology_json_output):
            return None
        try:
            return self.load_topology_model()
        except Exception as exc:
            logger.debug("Unable to load existing topology model: %s", exc)
            return None

    def _save_topology_outputs(self, topology_model: Dict[str, Any]) -> None:
        """Persist structured and text topology artifacts."""
        output_dir = os.path.dirname(self.topology_json_output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(self.topology_json_output, "w") as handle:
            json.dump(topology_model, handle, indent=2)

        builder = TopologyBuilder()
        lines = builder.render_topology_model_text(topology_model)
        topology_dir = os.path.dirname(self.topology_output)
        if topology_dir:
            os.makedirs(topology_dir, exist_ok=True)
        with open(self.topology_output, "w") as handle:
            handle.write("\n".join(lines))

    def _iter_tree_items(
        self,
        roots: list[Dict[str, Any]],
        *,
        section: str,
    ) -> Dict[str, Dict[str, Any]]:
        """Index tree items with their parent and section."""
        indexed: Dict[str, Dict[str, Any]] = {}

        def walk(item: Dict[str, Any], parent_id: str | None, depth: int) -> None:
            indexed[item["node_id"]] = {
                "item": item,
                "parent_id": parent_id,
                "depth": depth,
                "section": section,
            }
            for child in item.get("children", []):
                walk(child, item["node_id"], depth + 1)

        for root in roots:
            walk(root, None, 0)
        return indexed

    def _merge_offline_devices(
        self,
        previous_model: Dict[str, Any] | None,
        current_model: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Retain missing managed devices as offline nodes in the new topology."""
        if not previous_model:
            return current_model

        current_nodes_by_id = {
            node["id"]: dict(node)
            for node in current_model.get("nodes", [])
        }
        edges_by_key = {
            (
                edge.get("from"),
                edge.get("to"),
                edge.get("kind"),
                str(edge.get("remote_interface") or ""),
            ): dict(edge)
            for edge in current_model.get("edges", [])
        }
        previous_nodes_by_id = {
            node["id"]: node
            for node in previous_model.get("nodes", [])
        }

        previous_index = {}
        previous_index.update(
            self._iter_tree_items(previous_model.get("roots", []), section="roots")
        )
        previous_index.update(
            self._iter_tree_items(
                previous_model.get("unreached_roots", []),
                section="unreached_roots",
            )
        )

        current_index = {}
        current_index.update(
            self._iter_tree_items(current_model.get("roots", []), section="roots")
        )
        current_index.update(
            self._iter_tree_items(
                current_model.get("unreached_roots", []),
                section="unreached_roots",
            )
        )

        missing_devices = []
        for node_id, prev_node in previous_nodes_by_id.items():
            if prev_node.get("kind") != "device" or prev_node.get("type") != "mikrotik":
                continue
            if node_id in current_nodes_by_id:
                continue
            previous_item = previous_index.get(node_id)
            if not previous_item:
                continue
            if previous_item["item"].get("already_shown"):
                continue
            missing_devices.append((previous_item["depth"], node_id))

        for _depth, node_id in sorted(missing_devices):
            prev_node = dict(previous_nodes_by_id[node_id])
            prev_node["offline"] = True
            prev_node["status"] = "offline"
            current_nodes_by_id[node_id] = prev_node

            prev_meta = previous_index[node_id]
            prev_item = prev_meta["item"]
            offline_item = {
                "node_id": node_id,
                "kind": "device",
                "children": [],
            }
            for key in ("remote_interface", "display_mac"):
                if prev_item.get(key):
                    offline_item[key] = prev_item[key]

            parent_id = prev_meta["parent_id"]
            if parent_id and parent_id in current_index:
                parent_item = current_index[parent_id]["item"]
                if not any(child.get("node_id") == node_id for child in parent_item.get("children", [])):
                    parent_item.setdefault("children", []).append(offline_item)
                edge_key = (
                    parent_id,
                    node_id,
                    "links_to",
                    str(offline_item.get("remote_interface") or ""),
                )
                edges_by_key[edge_key] = {
                    "from": parent_id,
                    "to": node_id,
                    "kind": "links_to",
                    **(
                        {"remote_interface": offline_item["remote_interface"]}
                        if offline_item.get("remote_interface")
                        else {}
                    ),
                }
                current_index[node_id] = {
                    "item": offline_item,
                    "parent_id": parent_id,
                    "depth": prev_meta["depth"],
                    "section": current_index[parent_id]["section"],
                }
                continue

            section = prev_meta["section"]
            target_roots = current_model.setdefault(section, [])
            if not any(root.get("node_id") == node_id for root in target_roots):
                target_roots.append(offline_item)
            current_index[node_id] = {
                "item": offline_item,
                "parent_id": None,
                "depth": prev_meta["depth"],
                "section": section,
            }

        current_model["nodes"] = sorted(
            current_nodes_by_id.values(),
            key=lambda node: (node["kind"], node["id"]),
        )
        current_model["edges"] = sorted(
            edges_by_key.values(),
            key=lambda edge: (edge["from"], edge["to"], edge["kind"]),
        )
        current_model["root_ids"] = [
            item["node_id"] for item in current_model.get("roots", [])
        ]
        return current_model

    def load_layout(self) -> Dict[str, Any]:
        """Load persisted browser layout positions."""
        if not os.path.exists(self.layout_output):
            return {"positions": {}}

        try:
            with open(self.layout_output, "r") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("Layout file unavailable: %s", exc)
            return {"positions": {}}

        positions = payload.get("positions", {})
        if not isinstance(positions, dict):
            return {"positions": {}}
        return {"positions": positions}

    def save_layout(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Persist browser layout positions."""
        positions = payload.get("positions", {})
        if not isinstance(positions, dict):
            raise ValueError("layout payload must contain a positions object")

        normalized_positions = {}
        for node_id, position in positions.items():
            if not isinstance(node_id, str) or not isinstance(position, dict):
                continue

            x = position.get("x")
            y = position.get("y")
            if x is None or y is None:
                continue
            try:
                normalized_positions[node_id] = {
                    "x": float(x),
                    "y": float(y),
                    "parent_id": str(position.get("parent_id", "") or ""),
                }
            except (TypeError, ValueError):
                continue

        output_dir = os.path.dirname(self.layout_output)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        saved_payload = {
            "positions": normalized_positions,
            "saved_at": self._utc_now(),
        }
        with open(self.layout_output, "w") as handle:
            json.dump(saved_payload, handle, indent=2)

        return saved_payload

    def load_static_file(self, request_path: str) -> tuple[bytes, str]:
        """Load one static frontend asset from the local web directory."""
        relative_path = request_path.lstrip("/") or "index.html"
        file_path = (WEB_ROOT / relative_path).resolve()

        try:
            file_path.relative_to(WEB_ROOT)
        except ValueError as exc:
            raise FileNotFoundError("invalid static path") from exc

        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"static asset not found: {relative_path}")

        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        return file_path.read_bytes(), content_type

    def _credentials_ready_for_live_actions(self) -> tuple[bool, str]:
        """Check whether the server can run live collection without prompting."""
        if self.username:
            return True, ""

        if self.mapper.credential_manager.cipher_suite:
            return True, ""

        if self.mapper.credential_manager.has_usable_store():
            return (
                False,
                "credential store is locked; restart the server and unlock it first",
            )

        return (
            False,
            "no live collection credentials are configured for this server process",
        )

    def _build_result_summary(self, connection_map: Dict[str, Any] | None) -> Dict[str, Any]:
        """Build a compact action result summary."""
        connection_map = connection_map or {}
        return {
            "device_count": len(connection_map.get("devices", {})),
            "host_count": len(connection_map.get("hosts", {})),
            "connection_count": len(connection_map.get("connections", [])),
        }

    def _run_generate_topology(self) -> Dict[str, Any]:
        """Generate topology artifacts from the current collected data."""
        previous_model = self._load_topology_model_if_exists()
        if not self.mapper.generate_topology(
            data_file=self.data_file,
            output_file=self.topology_output,
            json_output_file=self.topology_json_output,
        ):
            raise RuntimeError("topology generation failed")

        merged_model = self._merge_offline_devices(
            previous_model,
            self.load_topology_model(),
        )
        self._save_topology_outputs(merged_model)
        return self._topology_summary()

    def _run_scan_refresh(self, ip_range: str | None = None) -> Dict[str, Any]:
        """Run a live refresh using either scan_file or a fresh network scan."""
        credentials_ready, error_message = self._credentials_ready_for_live_actions()
        if not credentials_ready:
            raise RuntimeError(error_message)

        previous_model = self._load_topology_model_if_exists()
        effective_scan_range = (ip_range or "").strip()
        with self._status_lock:
            self._status["last_scan_range"] = effective_scan_range
        self._save_runtime_state()

        if effective_scan_range:
            connection_map = self.mapper.run_full_mapping(
                ip_range=effective_scan_range,
                username=self.username,
                password=self.password,
                key_file=self.key_file,
                port=self.collection_port,
                timeout=self.timeout,
                verbose=self.verbose,
                backend=self.backend,
                use_api_ssl=self.use_api_ssl,
                scan_output_file=self.scan_file,
                data_output_file=self.data_file,
                output_file=self.map_output,
                readable_file=self.readable_output,
                topology_file=self.topology_output,
                topology_json_file=self.topology_json_output,
            )
            if not connection_map:
                raise RuntimeError("full network refresh failed")
            merged_model = self._merge_offline_devices(
                previous_model,
                self.load_topology_model(),
            )
            self._save_topology_outputs(merged_model)
            return self._build_result_summary(connection_map)

        collected_data = self.mapper.collect_data(
            device_file=self.scan_file,
            username=self.username,
            password=self.password,
            key_file=self.key_file,
            output_file=self.data_file,
            port=self.collection_port,
            timeout=self.timeout,
            backend=self.backend,
            use_api_ssl=self.use_api_ssl,
        )
        if not self.mapper._has_connected_devices(collected_data):
            raise RuntimeError("no devices connected during refresh")

        connection_map = self.mapper.build_map(
            data_file=self.data_file,
            output_file=self.map_output,
            readable_file=self.readable_output,
        )
        if not connection_map:
            raise RuntimeError("map generation failed")

        if not self.mapper.generate_topology(
            data_file=self.data_file,
            output_file=self.topology_output,
            json_output_file=self.topology_json_output,
        ):
            raise RuntimeError("topology generation failed")

        merged_model = self._merge_offline_devices(
            previous_model,
            self.load_topology_model(),
        )
        self._save_topology_outputs(merged_model)
        return self._build_result_summary(connection_map)

    def _start_background_action(
        self,
        action_name: str,
        worker: Callable[[], Dict[str, Any]],
    ) -> tuple[bool, str]:
        """Start one background action if the service is idle."""
        with self._status_lock:
            if self._status["running"]:
                return False, f"service is busy with {self._status['current_action']}"

            self._status.update({
                "running": True,
                "current_action": action_name,
                "last_action": action_name,
                "last_started_at": self._utc_now(),
                "last_error": "",
                "last_result": {},
            })

        def run():
            try:
                result = worker()
                with self._status_lock:
                    self._status.update({
                        "running": False,
                        "current_action": "",
                        "last_finished_at": self._utc_now(),
                        "last_success": True,
                        "last_error": "",
                        "last_result": result,
                    })
            except Exception as exc:
                logger.error("Background action %s failed: %s", action_name, exc)
                with self._status_lock:
                    self._status.update({
                        "running": False,
                        "current_action": "",
                        "last_finished_at": self._utc_now(),
                        "last_success": False,
                        "last_error": str(exc),
                        "last_result": {},
                    })

        self._worker_thread = threading.Thread(
            target=run,
            name=f"mikroscan-{action_name}",
            daemon=True,
        )
        self._worker_thread.start()
        return True, action_name

    def trigger_generate_topology(self) -> tuple[bool, str]:
        """Start background topology generation."""
        return self._start_background_action(
            "generate_topology",
            self._run_generate_topology,
        )

    def trigger_scan(self, ip_range: str | None = None) -> tuple[bool, str]:
        """Start a background refresh action."""
        return self._start_background_action(
            "scan",
            lambda: self._run_scan_refresh(ip_range=ip_range),
        )

    def _auto_refresh_loop(self) -> None:
        """Trigger periodic refreshes of the known-device set."""
        while not self._stop_event.wait(self.refresh_interval):
            if self.refresh_interval <= 0:
                continue
            ready, error_message = self._credentials_ready_for_live_actions()
            if not ready:
                logger.debug("Skipping scheduled refresh: %s", error_message)
                continue
            started, message = self.trigger_scan()
            if started:
                logger.info("Triggered scheduled known-device refresh")
            else:
                logger.debug("Skipped scheduled refresh: %s", message)

    def start(self) -> None:
        """Start background service helpers."""
        if self.refresh_interval <= 0 or self._scheduler_thread:
            return
        self._stop_event.clear()
        self._scheduler_thread = threading.Thread(
            target=self._auto_refresh_loop,
            name="mikroscan-auto-refresh",
            daemon=True,
        )
        self._scheduler_thread.start()

    def stop(self) -> None:
        """Stop background service helpers."""
        self._stop_event.set()


def create_api_handler(service: MikroscanAPIService):
    """Create a request handler class bound to one API service."""

    class MikroscanAPIHandler(BaseHTTPRequestHandler):
        """HTTP handler for the local Mikroscan API."""

        def _is_client_allowed(self) -> bool:
            allowed = os.environ.get("MIKROSCAN_ALLOWED_CLIENTS", "").strip()
            if not allowed:
                return True

            allowed_clients = {
                entry.strip()
                for entry in allowed.split(",")
                if entry.strip()
            }
            return self.client_address[0] in allowed_clients

        def log_message(self, format: str, *args):
            logger.debug("%s - %s", self.address_string(), format % args)

        def _send_json(self, code: int, payload: Dict[str, Any]):
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_bytes(self, code: int, payload: bytes, content_type: str):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _read_json_body(self) -> Dict[str, Any]:
            content_length = int(self.headers.get("Content-Length", "0"))
            if content_length <= 0:
                return {}

            raw_body = self.rfile.read(content_length)
            if not raw_body:
                return {}
            return json.loads(raw_body.decode("utf-8"))

        def do_GET(self):
            if not self._is_client_allowed():
                self._send_json(403, {"error": "forbidden"})
                return

            path = urlparse(self.path).path
            if path == "/" or not path.startswith("/api/"):
                asset_path = "index.html" if path == "/" else path.lstrip("/")
                try:
                    payload, content_type = service.load_static_file(asset_path)
                except FileNotFoundError:
                    self._send_json(404, {"error": "not found"})
                    return
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                    return

                self._send_bytes(200, payload, content_type)
                return

            if path == "/api/status":
                self._send_json(200, service.get_status())
                return

            if path == "/api/topology":
                if not os.path.exists(service.topology_json_output):
                    self._send_json(404, {"error": "topology JSON not found"})
                    return
                try:
                    self._send_json(200, service.load_topology_model())
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                return

            if path == "/api/layout":
                self._send_json(200, service.load_layout())
                return

            self._send_json(404, {"error": "not found"})

        def do_POST(self):
            if not self._is_client_allowed():
                self._send_json(403, {"error": "forbidden"})
                return

            path = urlparse(self.path).path
            try:
                body = self._read_json_body()
            except Exception as exc:
                self._send_json(400, {"error": f"invalid JSON body: {exc}"})
                return

            if path == "/api/generate-topology":
                started, message = service.trigger_generate_topology()
                status_code = 202 if started else 409
                self._send_json(status_code, {"started": started, "message": message})
                return

            if path == "/api/scan":
                started, message = service.trigger_scan(body.get("ip_range"))
                status_code = 202 if started else 409
                self._send_json(status_code, {"started": started, "message": message})
                return

            if path == "/api/layout":
                try:
                    payload = service.save_layout(body)
                except ValueError as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                except Exception as exc:
                    self._send_json(500, {"error": str(exc)})
                    return

                self._send_json(200, payload)
                return

            self._send_json(404, {"error": "not found"})

    return MikroscanAPIHandler


class MikroscanAPIServer:
    """Threading HTTP server wrapper for the local Mikroscan API."""

    def __init__(self, host: str, port: int, service: MikroscanAPIService):
        self.host = host
        self.port = port
        self.service = service
        handler = create_api_handler(service)
        self.httpd = ThreadingHTTPServer((host, port), handler)

    def serve_forever(self):
        """Serve requests until interrupted."""
        actual_host, actual_port = self.httpd.server_address
        logger.info(
            "Mikroscan API server listening on http://%s:%s",
            actual_host,
            actual_port,
        )
        self.service.start()
        try:
            self.httpd.serve_forever()
        finally:
            self.service.stop()

    def shutdown(self):
        """Stop the API server."""
        self.service.stop()
        self.httpd.shutdown()
        self.httpd.server_close()
