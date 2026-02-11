from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

import docker
import grpc
from fastapi import HTTPException

import emulation_pb2
import emulation_pb2_grpc

logger = logging.getLogger(__name__)

MININET_NAME_MAX_LEN = 10


def wait_for_grpc_ready(channel: grpc.Channel, timeout: int = 30) -> bool:
    """Wait for gRPC channel to be ready, with exponential backoff."""
    deadline = time.time() + timeout
    attempt = 0
    delay = 0.2

    while time.time() < deadline:
        remaining = deadline - time.time()
        if remaining <= 0:
            return False

        attempt += 1
        try:
            grpc.channel_ready_future(channel).result(timeout=min(2.0, remaining))
            logger.info("✅ gRPC channel ready after %d attempts", attempt)
            return True
        except grpc.FutureTimeoutError:
            sleep_for = min(delay, max(0.0, deadline - time.time()))
            if sleep_for <= 0:
                continue
            logger.info("Waiting for gRPC channel... attempt %d (retrying in %.2fs)", attempt, sleep_for)
            time.sleep(sleep_for)
            delay = min(delay * 1.5, 2.0)
        except Exception as exc:
            logger.error("Error checking gRPC channel readiness: %s", exc)
            return False

    return False


def _enforce_mininet_name_limit(value: str) -> str:
    """Ensure runtime-safe names stay within Linux interface length limits."""
    candidate = (value or "").strip("-") or "device"

    if candidate[0].isdigit():
        candidate = f"n{candidate}"

    if len(candidate) <= MININET_NAME_MAX_LEN:
        return candidate

    suffix = hashlib.sha1(candidate.encode()).hexdigest()[:4]
    prefix_len = max(MININET_NAME_MAX_LEN - len(suffix) - 1, 1)
    prefix = candidate[:prefix_len].strip("-") or "n"
    candidate = f"{prefix}-{suffix}" if prefix else f"n{suffix}"

    if candidate[0].isdigit():
        candidate = f"n{candidate}"

    return candidate[:MININET_NAME_MAX_LEN]


def _sanitize_display_name(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", (name or "").strip())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    if not cleaned:
        cleaned = "device"
    cleaned = cleaned.lower()
    if cleaned[0].isdigit():
        cleaned = f"n{cleaned}"
    return _enforce_mininet_name_limit(cleaned)


def runtime_device_name(device_id: Optional[str], display_name: Optional[str]) -> str:
    """Create stable runtime name for a device based on its display name if available."""
    if display_name:
        return _sanitize_display_name(display_name)

    if device_id:
        suffix = hashlib.sha1(str(device_id).encode()).hexdigest()[:8]
        return _enforce_mininet_name_limit(f"device-{suffix}")

    return _enforce_mininet_name_limit("device")


def runtime_link_key(node1_id: str, node2_id: str) -> str:
    """Create a deterministic key for a link based on node IDs."""
    ordered = sorted([node1_id or "", node2_id or ""])
    return f"{ordered[0]}__{ordered[1]}"


def resolve_runtime_name(node_id: Optional[str], display_name: Optional[str], client: Optional["gRPCClient"] = None) -> str:
    """Resolve runtime name using cached mapping or deterministic fallback."""
    mapping = getattr(client, "node_id_to_runtime", None)
    if mapping:
        if node_id:
            runtime = mapping.get(node_id)
            if runtime:
                return runtime
        if display_name:
            runtime = mapping.get(display_name)
            if runtime:
                return runtime
    return runtime_device_name(node_id, display_name)


def parse_ip_link_interfaces(stdout: str) -> List[str]:
    interfaces: List[str] = []
    for line in (stdout or "").splitlines():
        m = re.match(r"^\\d+:\\s+([^:]+):", line.strip())
        if not m:
            continue
        iface = m.group(1).strip().split("@", 1)[0]
        if iface and iface != "lo":
            interfaces.append(iface)
    return interfaces


def pick_default_interface(interfaces: List[str]) -> Optional[str]:
    if not interfaces:
        return None
    for suffix in ("-eth0", "eth0"):
        for iface in interfaces:
            if iface.endswith(suffix):
                return iface
    for iface in interfaces:
        if "eth" in iface:
            return iface
    return interfaces[0]


class gRPCClient:
    """gRPC client for emulation container."""

    def __init__(self):
        self.channel = None
        self.stub = None
        self.node_id_to_runtime: dict[str, str] = {}

    def close(self) -> None:
        if self.channel:
            self.channel.close()

    def start_emulation(self, topology_id: str, topology_data: Dict[str, Any]) -> Dict[str, Any]:
        """Start emulation via gRPC."""
        try:
            nodes_all = topology_data.get("nodes", topology_data.get("devices", [])) or []
            controller_node_ids: set[str] = set()
            if isinstance(nodes_all, list):
                for n in nodes_all:
                    if not isinstance(n, dict):
                        continue
                    dt = str(n.get("device_type") or n.get("type") or "").strip().lower()
                    if dt in ("controller", "sdn_controller", "sdncontroller"):
                        nid = n.get("id") or n.get("node_id")
                        if nid:
                            controller_node_ids.add(str(nid))

            nodes: list[dict[str, Any]] = []
            if isinstance(nodes_all, list):
                for n in nodes_all:
                    if not isinstance(n, dict):
                        continue
                    dt = str(n.get("device_type") or n.get("type") or "").strip().lower()
                    nid = n.get("id") or n.get("node_id")
                    if dt in ("controller", "sdn_controller", "sdncontroller") or (
                        nid and str(nid) in controller_node_ids
                    ):
                        continue
                    nodes.append(n)

            self.node_id_to_name: dict[str, str] = {}
            self.node_id_to_runtime = {}
            for node in nodes:
                node_id = node.get("id")
                node_name = node.get("name")
                runtime_name = runtime_device_name(node_id, node_name)
                if node_id:
                    self.node_id_to_name[node_id] = node_name
                    self.node_id_to_runtime[node_id] = runtime_name
                self.node_id_to_runtime[node_name] = runtime_name

            options_dict = topology_data.get("options", {})
            if not isinstance(options_dict, dict):
                options_dict = {}

            links = topology_data.get("links", []) or []
            if controller_node_ids and isinstance(links, list):
                filtered_links = []
                for l in links:
                    if not isinstance(l, dict):
                        continue
                    a = l.get("node1", l.get("source_node_id", l.get("source", "")))
                    b = l.get("node2", l.get("target_node_id", l.get("target", "")))
                    if (a and str(a) in controller_node_ids) or (b and str(b) in controller_node_ids):
                        continue
                    filtered_links.append(l)
                links = filtered_links

            topology_def = emulation_pb2.TopologyDefinition(
                devices=[self._convert_device(d) for d in nodes],
                links=[self._convert_link(l) for l in links],
                controllers=[self._convert_controller(c) for c in topology_data.get("controllers", [])],
            )

            for key, value in options_dict.items():
                topology_def.options[key] = str(value)

            request = emulation_pb2.StartEmulationRequest(topology_id=topology_id, topology=topology_def)

            for key, value in options_dict.items():
                request.options[key] = str(value)

            try:
                timeout_seconds = int(os.getenv("EMULATION_START_TIMEOUT_SECONDS", "120"))
            except Exception:
                timeout_seconds = 120
            timeout_seconds = max(15, min(600, timeout_seconds))

            response = self.stub.StartEmulation(request, timeout=timeout_seconds)

            return {"success": response.success, "message": response.message, "emulation_id": response.emulation_id}

        except grpc.RpcError as exc:
            logger.error("gRPC error starting emulation: %s", exc)
            return {"success": False, "message": f"gRPC error: {exc.details()}", "emulation_id": ""}

    def stop_emulation(self, emulation_id: str, cleanup: bool = True) -> Dict[str, Any]:
        try:
            request = emulation_pb2.StopEmulationRequest(emulation_id=emulation_id, cleanup=cleanup)
            response = self.stub.StopEmulation(request, timeout=120)
            return {"success": response.success, "message": response.message}
        except grpc.RpcError as exc:
            logger.error("gRPC error stopping emulation: %s", exc)
            return {"success": False, "message": f"gRPC error: {exc.details()}"}

    def pause_emulation(self, emulation_id: str) -> Dict[str, Any]:
        try:
            request = emulation_pb2.PauseEmulationRequest(emulation_id=emulation_id)
            response = self.stub.PauseEmulation(request, timeout=15)
            return {"success": response.success, "message": response.message}
        except grpc.RpcError as exc:
            logger.error("gRPC error pausing emulation: %s", exc)
            return {"success": False, "message": f"gRPC error: {exc.details()}"}

    def resume_emulation(self, emulation_id: str) -> Dict[str, Any]:
        try:
            request = emulation_pb2.ResumeEmulationRequest(emulation_id=emulation_id)
            response = self.stub.ResumeEmulation(request, timeout=30)
            return {"success": response.success, "message": response.message}
        except grpc.RpcError as exc:
            logger.error("gRPC error resuming emulation: %s", exc)
            return {"success": False, "message": f"gRPC error: {exc.details()}"}

    def get_status(self, emulation_id: str) -> Dict[str, Any]:
        try:
            request = emulation_pb2.EmulationStatusRequest(emulation_id=emulation_id)
            response = self.stub.GetEmulationStatus(request, timeout=15)

            return {
                "status": response.status.lower(),
                "uptime_seconds": response.uptime_seconds,
                "device_count": response.device_count,
                "link_count": response.link_count,
                "metadata": dict(response.metadata),
            }

        except grpc.RpcError as exc:
            logger.error("gRPC error getting status: %s", exc)
            if exc.code() == grpc.StatusCode.NOT_FOUND:
                raise HTTPException(status_code=404, detail=f"Emulation {emulation_id} not found: {exc.details()}") from exc
            raise HTTPException(status_code=500, detail=f"gRPC error: {exc.details()}") from exc

    def execute_command(self, device: str, command: str) -> Dict[str, Any]:
        try:
            request = emulation_pb2.ExecuteCommandRequest(device=device, command=command, stream_output=False)
            response = self.stub.ExecuteCommand(request, timeout=20)
            return {
                "success": response.success,
                "stdout": response.stdout,
                "stderr": response.stderr,
                "exit_code": response.exit_code,
            }
        except grpc.RpcError as exc:
            logger.error("gRPC error executing command: %s", exc)
            return {"success": False, "stdout": "", "stderr": f"gRPC error: {exc.details()}", "exit_code": -1}

    def list_devices(self, device_type: str = "") -> Dict[str, Any]:
        try:
            request = emulation_pb2.ListDevicesRequest(device_type=device_type)
            response = self.stub.ListDevices(request, timeout=30)

            devices: list[dict[str, Any]] = []
            for device in response.devices:
                ip = device.properties.get("ip", "")
                if not ip and device.interfaces:
                    ip = device.interfaces[0].ip

                display_name = device.properties.get("display_name") or device.properties.get("original_name") or device.name
                runtime_name = device.name
                node_id = device.properties.get("node_id")

                if node_id:
                    self.node_id_to_runtime[node_id] = runtime_name
                if display_name:
                    self.node_id_to_runtime[display_name] = runtime_name
                self.node_id_to_runtime[runtime_name] = runtime_name

                device_dict = {
                    "name": display_name,
                    "runtime_name": runtime_name,
                    "type": device.type,
                    "device_type": device.type,
                    "status": device.status,
                    "ip": ip,
                    "properties": dict(device.properties),
                    "interfaces": [
                        {"name": intf.name, "mac": intf.mac, "ip": intf.ip, "status": intf.status}
                        for intf in device.interfaces
                    ],
                }
                devices.append(device_dict)

            return {"success": True, "devices": devices}

        except grpc.RpcError as exc:
            logger.error("gRPC error listing devices: %s", exc)
            return {"success": False, "devices": [], "error": str(exc)}

    def list_links(self, node: str = "") -> Dict[str, Any]:
        try:
            request = emulation_pb2.ListLinksRequest(node=str(node or ""))
            response = self.stub.ListLinks(request, timeout=30)

            links: list[dict[str, Any]] = []
            for link in response.links:
                links.append(
                    {
                        "node1": link.node1,
                        "node2": link.node2,
                        "port1": link.port1,
                        "port2": link.port2,
                        "status": link.status,
                        "params": {
                            "bandwidth": getattr(getattr(link, "params", None), "bandwidth", None),
                            "delay": getattr(getattr(link, "params", None), "delay", None),
                            "loss": getattr(getattr(link, "params", None), "loss", None),
                        },
                    }
                )
            return {"success": True, "links": links}
        except grpc.RpcError as exc:
            logger.error("gRPC error listing links: %s", exc)
            return {"success": False, "links": [], "error": str(exc)}

    def _convert_device(self, device: Dict[str, Any]) -> emulation_pb2.Device:
        device_type = device.get("type", device.get("device_type", ""))

        node_id = device.get("id", device.get("node_id", ""))
        display_name = device.get("name", "")
        runtime_name = runtime_device_name(node_id, display_name)

        pb_device = emulation_pb2.Device(name=runtime_name, type=device_type)

        properties = device.get("properties", {})
        if isinstance(properties, dict):
            for key, value in properties.items():
                if value is None:
                    continue
                if isinstance(value, (dict, list)):
                    pb_device.properties[key] = json.dumps(value)
                else:
                    pb_device.properties[key] = str(value)

        if node_id:
            pb_device.properties["node_id"] = str(node_id)

        if display_name:
            pb_device.properties["display_name"] = display_name
            pb_device.properties["original_name"] = display_name

        return pb_device

    def _convert_link(self, link: Dict[str, Any]) -> emulation_pb2.Link:
        bandwidth = link.get("bandwidth", 0)
        if bandwidth is None or isinstance(bandwidth, str):
            bandwidth = 0

        delay = link.get("delay", 0)
        if delay is None or isinstance(delay, str):
            delay = 0

        loss = link.get("loss", 0)
        if loss is None:
            loss = 0

        max_queue = link.get("max_queue_size", 1000)
        if max_queue is None:
            max_queue = 1000

        params = emulation_pb2.LinkParams(
            bandwidth=int(bandwidth),
            delay=int(delay),
            loss=float(loss),
            max_queue_size=int(max_queue),
        )

        node1_id = link.get("node1", link.get("source_node_id", link.get("source", "")))
        node2_id = link.get("node2", link.get("target_node_id", link.get("target", "")))

        runtime_map = getattr(self, "node_id_to_runtime", {})
        node1_name = runtime_map.get(node1_id) or runtime_device_name(node1_id, node1_id)
        node2_name = runtime_map.get(node2_id) or runtime_device_name(node2_id, node2_id)

        port1 = link.get("port1", link.get("source_port", ""))
        port2 = link.get("port2", link.get("target_port", ""))
        if port1 is None:
            port1 = ""
        if port2 is None:
            port2 = ""

        return emulation_pb2.Link(
            node1=str(node1_name),
            node2=str(node2_name),
            port1=str(port1),
            port2=str(port2),
            params=params,
        )

    def _convert_controller(self, controller: Dict[str, Any]) -> emulation_pb2.Controller:
        return emulation_pb2.Controller(
            name=controller.get("name", ""),
            ip=controller.get("ip", ""),
            port=controller.get("port", 6653),
            type=controller.get("type", ""),
        )


class gRPCClientManager:
    """Manages gRPC clients for multiple emulation containers."""

    def __init__(
        self,
        *,
        active_emulations: Any,
        docker_client: Any,
        emulation_grpc_port: str,
    ):
        self.clients: dict[str, gRPCClient] = {}
        self.lock = threading.Lock()
        self._active_emulations = active_emulations
        self._docker_client = docker_client
        self._emulation_grpc_port = emulation_grpc_port

    def create_client(self, topology_id: str, container_name: str, port: int) -> gRPCClient:
        with self.lock:
            client = gRPCClient()
            default_port = int(port or int(self._emulation_grpc_port))

            host_override = os.getenv("EMULATION_GRPC_HOST")

            candidates: list[str] = []
            if container_name:
                candidates.append(f"{container_name}:50051")
            else:
                if host_override:
                    candidates.append(f"{host_override}:{default_port}")
                candidates.append(f"localhost:{default_port}")

            last_error: Optional[Exception] = None
            for endpoint in candidates:
                channel = grpc.insecure_channel(
                    endpoint,
                    options=[
                        ("grpc.max_send_message_length", 100 * 1024 * 1024),
                        ("grpc.max_receive_message_length", 100 * 1024 * 1024),
                        ("grpc.keepalive_time_ms", 60000),
                        ("grpc.keepalive_timeout_ms", 20000),
                        ("grpc.http2.max_pings_without_data", 2),
                    ],
                )
                if wait_for_grpc_ready(channel, timeout=10):
                    client.channel = channel
                    client.stub = emulation_pb2_grpc.EmulationServiceStub(channel)
                    self.clients[topology_id] = client
                    logger.info("✅ Created gRPC client for topology %s at %s", topology_id, endpoint)
                    return client

                channel.close()
                last_error = RuntimeError(f"gRPC backend not reachable at {endpoint}")
                logger.warning("Failed to connect to emulation backend at %s; trying next candidate.", endpoint)

            raise RuntimeError(f"Unable to establish gRPC connection for topology {topology_id}") from last_error

    def get_client(self, topology_id: str) -> Optional[gRPCClient]:
        return self.clients.get(topology_id)

    def remove_client(self, topology_id: str) -> None:
        with self.lock:
            client = self.clients.pop(topology_id, None)
            if client:
                try:
                    client.close()
                    logger.info("Closed gRPC client for topology %s", topology_id)
                except Exception as exc:
                    logger.warning("Error closing gRPC client for %s: %s", topology_id, exc)

    def get_or_create(self, topology_id: str) -> Optional[gRPCClient]:
        client = self.get_client(topology_id)
        if client:
            return client

        container_name = None
        emulation_info = self._active_emulations.get(topology_id) if self._active_emulations else None
        if emulation_info:
            container_name = emulation_info.get("container_name")
        if not container_name:
            container_name = f"caduceus-emu-{topology_id[:8]}"

        if self._docker_client and container_name:
            try:
                self._docker_client.containers.get(container_name)
                return self.create_client(topology_id, container_name, int(self._emulation_grpc_port))
            except docker.errors.NotFound:
                return None
            except Exception as exc:
                logger.error("Failed to reconnect to container %s: %s", container_name, exc)

        return None

