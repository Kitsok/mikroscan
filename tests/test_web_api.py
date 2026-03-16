#!/usr/bin/env python3
"""Focused tests for the local Mikroscan HTTP API."""

import json
import io
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.web_api import MikroscanAPIService, create_api_handler


class FakeCredentialManager:
    """Minimal credential-manager stub for API service tests."""

    def __init__(self):
        self.cipher_suite = object()

    def has_usable_store(self):
        return True


class FakeMapper:
    """Minimal mapper stub used by the local API tests."""

    def __init__(self):
        self.credential_manager = FakeCredentialManager()
        self.generate_topology_calls = []
        self.collect_data_calls = []
        self.build_map_calls = []
        self.run_full_mapping_calls = []

    def generate_topology(self, **kwargs):
        self.generate_topology_calls.append(kwargs)
        json_output_file = kwargs.get("json_output_file")
        if json_output_file:
            with open(json_output_file, "w") as handle:
                json.dump(
                    {
                        "version": 1,
                        "nodes": [],
                        "edges": [],
                        "root_ids": [],
                        "unresolved_hosts": [],
                    },
                    handle,
                )
        return True

    def collect_data(self, **kwargs):
        self.collect_data_calls.append(kwargs)
        return {"192.0.2.1": {"connected": True}}

    def _has_connected_devices(self, collected_data):
        return True

    def build_map(self, **kwargs):
        self.build_map_calls.append(kwargs)
        return {"devices": {"router": {}}, "connections": [], "hosts": {}}

    def run_full_mapping(self, **kwargs):
        self.run_full_mapping_calls.append(kwargs)
        return {"devices": {"router": {}}, "connections": [], "hosts": {}}


class TestWebAPI(unittest.TestCase):
    """Tests for the local HTTP API service and server."""

    def _make_service(self, mapper, topology_json_output):
        layout_handle = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        layout_handle.close()
        os.unlink(layout_handle.name)
        self.addCleanup(lambda: os.path.exists(layout_handle.name) and os.unlink(layout_handle.name))
        return MikroscanAPIService(
            mapper,
            scan_file="data/scan_results.json",
            data_file="data/collected_data.json",
            map_output="data/final_map.json",
            readable_output="data/connections.txt",
            topology_output="data/topology.txt",
            topology_json_output=topology_json_output,
            layout_output=layout_handle.name,
            username="admin",
            password="secret",
            key_file=None,
            backend="api",
            collection_port=8728,
            timeout=10,
            verbose=False,
            use_api_ssl=False,
        )

    def _wait_for_idle(self, service, timeout=1.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not service.get_status()["running"]:
                return
            time.sleep(0.01)
        raise AssertionError("service did not finish background action in time")

    def test_service_generate_topology_action_updates_status(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as handle:
            json.dump({"version": 1, "nodes": [], "edges": [], "root_ids": []}, handle)
            topology_json = handle.name

        try:
            mapper = FakeMapper()
            service = self._make_service(mapper, topology_json)

            started, message = service.trigger_generate_topology()
            self.assertTrue(started)
            self.assertEqual(message, "generate_topology")
            self._wait_for_idle(service)

            status = service.get_status()
            self.assertTrue(status["last_success"])
            self.assertEqual(status["last_action"], "generate_topology")
            self.assertEqual(len(mapper.generate_topology_calls), 1)
        finally:
            if os.path.exists(topology_json):
                os.unlink(topology_json)

    def test_service_scan_action_uses_scan_file_refresh(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as handle:
            json.dump({"version": 1, "nodes": [], "edges": [], "root_ids": []}, handle)
            topology_json = handle.name

        try:
            mapper = FakeMapper()
            service = self._make_service(mapper, topology_json)

            started, message = service.trigger_scan()
            self.assertTrue(started)
            self.assertEqual(message, "scan")
            self._wait_for_idle(service)

            status = service.get_status()
            self.assertTrue(status["last_success"])
            self.assertEqual(len(mapper.collect_data_calls), 1)
            self.assertEqual(len(mapper.build_map_calls), 1)
            self.assertEqual(len(mapper.generate_topology_calls), 1)
        finally:
            if os.path.exists(topology_json):
                os.unlink(topology_json)

    def test_service_layout_round_trip(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as handle:
            json.dump({"version": 1, "nodes": [], "edges": [], "root_ids": []}, handle)
            topology_json = handle.name

        try:
            mapper = FakeMapper()
            service = self._make_service(mapper, topology_json)

            saved = service.save_layout({
                "positions": {
                    "device:root": {"dx": 12, "dy": -4},
                    "host:test": {"dx": "7.5", "dy": 3},
                }
            })
            self.assertIn("saved_at", saved)

            loaded = service.load_layout()
            self.assertEqual(loaded["positions"]["device:root"]["dx"], 12.0)
            self.assertEqual(loaded["positions"]["device:root"]["dy"], -4.0)
            self.assertEqual(loaded["positions"]["host:test"]["dx"], 7.5)
            self.assertEqual(loaded["positions"]["host:test"]["dy"], 3.0)
        finally:
            if os.path.exists(topology_json):
                os.unlink(topology_json)

    def _invoke_handler(self, service, method, path, body=None):
        handler_cls = create_api_handler(service)
        handler = handler_cls.__new__(handler_cls)
        handler.path = path
        handler.command = method
        payload = body or b""
        handler.headers = {"Content-Length": str(len(payload))}
        handler.rfile = io.BytesIO(payload)
        handler.wfile = io.BytesIO()
        handler.responses = []
        handler.response_code = None
        handler.response_headers = []

        def send_response(code):
            handler.response_code = code

        def send_header(key, value):
            handler.response_headers.append((key, value))

        def end_headers():
            return None

        handler.send_response = send_response
        handler.send_header = send_header
        handler.end_headers = end_headers
        handler.address_string = lambda: "127.0.0.1"

        if method == "GET":
            handler.do_GET()
        else:
            handler.do_POST()

        handler.wfile.seek(0)
        return handler.response_code, json.loads(handler.wfile.read().decode("utf-8"))

    def _invoke_handler_raw(self, service, method, path, body=None):
        handler_cls = create_api_handler(service)
        handler = handler_cls.__new__(handler_cls)
        handler.path = path
        handler.command = method
        payload = body or b""
        handler.headers = {"Content-Length": str(len(payload))}
        handler.rfile = io.BytesIO(payload)
        handler.wfile = io.BytesIO()
        handler.response_code = None
        handler.response_headers = []

        def send_response(code):
            handler.response_code = code

        def send_header(key, value):
            handler.response_headers.append((key, value))

        def end_headers():
            return None

        handler.send_response = send_response
        handler.send_header = send_header
        handler.end_headers = end_headers
        handler.address_string = lambda: "127.0.0.1"

        if method == "GET":
            handler.do_GET()
        else:
            handler.do_POST()

        handler.wfile.seek(0)
        return handler.response_code, dict(handler.response_headers), handler.wfile.read()

    def test_http_handler_exposes_status_and_topology(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as handle:
            json.dump({"version": 1, "nodes": [{"id": "device:root"}], "edges": [], "root_ids": ["device:root"]}, handle)
            topology_json = handle.name

        try:
            mapper = FakeMapper()
            service = self._make_service(mapper, topology_json)

            status_code, status = self._invoke_handler(service, "GET", "/api/status")
            self.assertEqual(status_code, 200)
            self.assertIn("running", status)
            self.assertIn("topology", status)

            topology_code, topology = self._invoke_handler(service, "GET", "/api/topology")
            self.assertEqual(topology_code, 200)
            self.assertEqual(topology["version"], 1)
            self.assertEqual(topology["root_ids"], ["device:root"])

            action_code, payload = self._invoke_handler(
                service,
                "POST",
                "/api/generate-topology",
                b"{}",
            )
            self.assertEqual(action_code, 202)
            self.assertTrue(payload["started"])
        finally:
            if os.path.exists(topology_json):
                os.unlink(topology_json)

    def test_http_handler_serves_frontend_index(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as handle:
            json.dump({"version": 1, "nodes": [], "edges": [], "root_ids": []}, handle)
            topology_json = handle.name

        try:
            mapper = FakeMapper()
            service = self._make_service(mapper, topology_json)

            status_code, headers, payload = self._invoke_handler_raw(service, "GET", "/")
            self.assertEqual(status_code, 200)
            self.assertEqual(headers["Content-Type"], "text/html")
            self.assertIn(b"Mikroscan Topology", payload)
        finally:
            if os.path.exists(topology_json):
                os.unlink(topology_json)

    def test_http_handler_exposes_layout_endpoints(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as handle:
            json.dump({"version": 1, "nodes": [], "edges": [], "root_ids": []}, handle)
            topology_json = handle.name

        try:
            mapper = FakeMapper()
            service = self._make_service(mapper, topology_json)

            get_code, layout = self._invoke_handler(service, "GET", "/api/layout")
            self.assertEqual(get_code, 200)
            self.assertEqual(layout["positions"], {})

            post_code, saved = self._invoke_handler(
                service,
                "POST",
                "/api/layout",
                json.dumps({"positions": {"device:root": {"dx": 14, "dy": 6}}}).encode("utf-8"),
            )
            self.assertEqual(post_code, 200)
            self.assertEqual(saved["positions"]["device:root"]["dx"], 14.0)

            get_code, layout = self._invoke_handler(service, "GET", "/api/layout")
            self.assertEqual(get_code, 200)
            self.assertEqual(layout["positions"]["device:root"]["dy"], 6.0)
        finally:
            if os.path.exists(topology_json):
                os.unlink(topology_json)


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestWebAPI)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
