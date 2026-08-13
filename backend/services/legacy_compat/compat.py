#!/usr/bin/env python3
"""Legacy :5000 compatibility service for the Nexus frontend.

Several older frontend components (StorageManager, SimulationSnapshots,
NetworkConfigurationManager, TopologyBuilder, LLM*) were written against the
original monolithic backend at http://localhost:5000/api/* and were never
migrated to the microservice split behind nginx. Those calls now hit a dead
:5000 port (ERR_CONNECTION_REFUSED), so those UI panels break.

This service revives :5000: it answers every legacy endpoint the frontend calls,
mapping to the real microservices where an equivalent exists and returning a
valid, graceful empty payload otherwise, always with CORS headers (the browser
calls :5000 cross-origin from the :80 page). No frontend rebuild needed.

Runs as a dependency-free stdlib HTTP server (tiny image), on the nexus docker
network so it can reach the services by name.
"""
import json
import os
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOPOLOGY = os.environ.get("TOPOLOGY_URL", "http://topology-service:8001")
ORCH = os.environ.get("ORCH_URL", "http://orchestrator-service:8002")
SNAPSHOT = os.environ.get("SNAPSHOT_URL", "http://snapshot-service:8006")
CONTROLLER = os.environ.get("CONTROLLER_URL", "http://controller-manager-service:8005")
DEVICE = os.environ.get("DEVICE_URL", "http://device-manager-service:8004")
AI_GW = os.environ.get("AI_GATEWAY_URL", "http://ai-gateway-service:8014")


def _req(method, url, body=None, timeout=15):
    data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
    r = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw or b"null")
            except Exception:
                return resp.status, raw.decode(errors="replace")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, None
    except Exception:
        return 0, None


def upstream_topologies():
    st, d = _req("GET", f"{TOPOLOGY}/api/topologies")
    return d if isinstance(d, list) else []


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,PATCH,OPTIONS"
        )
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_OPTIONS(self):
        self._send(204, {})

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    def route(self, method):
        path = self.path.split("?")[0].rstrip("/") or "/"
        body = self._body()

        # ---- storage: topologies (map to topology-service) ----
        if path == "/api/storage/topologies":
            if method == "GET":
                tops = upstream_topologies()
                return self._send(200, {"success": True, "topologies": tops})
            if method == "POST":
                try:
                    payload = json.loads(body or b"{}")
                except Exception:
                    payload = {}
                st, d = _req("POST", f"{TOPOLOGY}/api/topologies", payload)
                ok = st in (200, 201)
                return self._send(
                    200 if ok else 502,
                    {"success": ok, "topology": d}
                    if ok
                    else {"success": False, "error": "save failed"},
                )
        if path.startswith("/api/storage/topologies/"):
            tid = path.rsplit("/", 1)[-1]
            if method == "GET":
                st, d = _req("GET", f"{TOPOLOGY}/api/topologies/{tid}")
                ok = st == 200
                return self._send(
                    200 if ok else 404,
                    {"success": ok, "topology": d}
                    if ok
                    else {"success": False, "error": "not found"},
                )
            if method == "DELETE":
                st, _ = _req("DELETE", f"{TOPOLOGY}/api/topologies/{tid}")
                return self._send(200, {"success": st in (200, 204)})
            if method == "PUT":
                try:
                    payload = json.loads(body or b"{}")
                except Exception:
                    payload = {}
                st, d = _req("PUT", f"{TOPOLOGY}/api/topologies/{tid}", payload)
                return self._send(200, {"success": st == 200, "topology": d})

        # ---- storage: configurations (no backing store yet -> graceful empty) ----
        if path == "/api/storage/configurations":
            if method == "GET":
                return self._send(200, {"success": True, "configurations": []})
            if method == "POST":
                return self._send(200, {"success": True})

        # ---- snapshots (map to snapshot-service, wrap) ----
        if path == "/api/snapshots" or path.startswith("/api/snapshots"):
            if method == "GET":
                st, d = _req("GET", f"{SNAPSHOT}/api/snapshots")
                snaps = (
                    d
                    if isinstance(d, list)
                    else (d.get("snapshots") if isinstance(d, dict) else []) or []
                )
                return self._send(200, {"success": True, "snapshots": snaps})
            if method == "POST":
                try:
                    payload = json.loads(body or b"{}")
                except Exception:
                    payload = {}
                st, d = _req("POST", f"{SNAPSHOT}/api/snapshots", payload)
                return self._send(200, {"success": st in (200, 201), "snapshot": d})

        # ---- network status ----
        # NOTE: components read nested fields (topology_summary.hosts, .stats.hosts,
        # .hosts.map, .links) WITHOUT null-guards, so every such field MUST be
        # present and well-typed or the whole React tree throws and unmounts
        # (white screen). Ship a complete, safe, empty shape.
        if path == "/api/network/status":
            st, d = _req("GET", f"{ORCH}/api/emulation/active")
            active = bool(d) if d else False
            return self._send(
                200,
                {
                    "success": True,
                    "running": active,
                    "status": "running" if active else "stopped",
                    "hosts": [],
                    "switches": [],
                    "links": [],
                    "nodes": [],
                    "stats": {"hosts": 0, "switches": 0, "links": 0, "nodes": 0},
                    "topology_summary": {"hosts": 0, "switches": 0, "links": 0},
                },
            )

        # ---- full topology ----
        if path == "/api/topology/full":
            return self._send(
                200,
                {
                    "success": True,
                    "hosts": [],
                    "switches": [],
                    "links": [],
                    "nodes": [],
                    "controllers": [],
                    "stats": {
                        "hosts": 0,
                        "switches": 0,
                        "links": 0,
                        "nodes": 0,
                        "controllers": 0,
                    },
                    "topology_summary": {"hosts": 0, "switches": 0, "links": 0},
                },
            )

        # ---- controller endpoints ----
        if path.startswith("/api/controller/"):
            return self._send(
                200,
                {
                    "success": True,
                    "status": "unknown",
                    "controllers": [],
                    "apps": [],
                    "config": {},
                },
            )

        # ---- switch available (static OVS-style list) ----
        if path == "/api/switch/available":
            return self._send(
                200, {"success": True, "switches": ["ovs", "ovsk", "lxbr"]}
            )

        # ---- LLM status / generation (best-effort via ai-gateway) ----
        if path == "/api/llm/status":
            st, d = _req("GET", f"{AI_GW}/health")
            return self._send(
                200,
                {
                    "success": True,
                    "available": st == 200,
                    "status": "ready" if st == 200 else "down",
                },
            )
        if path == "/api/llm/generate-topology":
            return self._send(
                200,
                {
                    "success": False,
                    "error": "LLM topology generation not wired in compat layer",
                },
            )

        if path == "/api/test":
            return self._send(200, {"success": True, "message": "compat :5000 alive"})

        # ---- generic fallback: proxy to topology-service, then graceful empty ----
        st, d = _req(method, f"{TOPOLOGY}{path}", body if body else None)
        if st and 200 <= st < 300:
            return self._send(st, d if d is not None else {"success": True})
        return self._send(
            200,
            {"success": True, "data": [], "note": "compat: no backend for %s" % path},
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    print("legacy-compat listening on :%d" % port, flush=True)
    ThreadingHTTPServer(("0.0.0.0", port), H).serve_forever()
