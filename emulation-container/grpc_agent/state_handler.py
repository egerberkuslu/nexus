"""
State Handler for Emulation Container
Manages state capture, restore, and snapshot operations
"""

from __future__ import annotations

import logging
import subprocess
import json
import pickle
from typing import Dict, List, Any, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

try:
    import emulation_pb2  # type: ignore
except Exception:
    emulation_pb2 = None  # type: ignore


class StateHandler:
    """
    Handles state capture and restoration for network emulation
    Captures: routing tables, flow tables, ARP tables, interface stats, etc.
    """

    def __init__(self, emulation_manager=None):
        self.emulation_manager = emulation_manager
        self.snapshots: Dict[str, Dict] = {}
        self.snapshot_dir = "/var/lib/caduceus/snapshots"
        os.makedirs(self.snapshot_dir, exist_ok=True)

    def _node_cmd(self, device: str, cmd: str) -> str:
        """
        Execute a command in the context of a Mininet node when possible.
        Falls back to the host namespace if a node cannot be resolved.
        """
        if self.emulation_manager is not None and getattr(self.emulation_manager, "net", None) is not None:
            try:
                node = self.emulation_manager.get_device(device)
                out = node.cmd(cmd)
                return out or ""
            except Exception:
                pass
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return (res.stdout or "") + (res.stderr or "")
        except Exception:
            return ""

    # ===== gRPC helpers (emulation.proto) =====
    def capture_state(
        self,
        snapshot_name: str,
        devices: List[str],
        include_routing_tables: bool = True,
        include_flow_tables: bool = False,
        include_arp_tables: bool = True,
    ):
        if emulation_pb2 is None:
            raise RuntimeError("emulation_pb2 is not available")

        snapshot_name = snapshot_name or f"snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        if not devices and self.emulation_manager is not None:
            try:
                devices = list(getattr(self.emulation_manager.net, "nameToNode", {}).keys())
            except Exception:
                devices = []

        payload: Dict[str, Any] = {
            "snapshot_name": snapshot_name,
            "timestamp": datetime.utcnow().isoformat(),
            "devices": devices,
            "routing_tables": {},
            "arp_tables": {},
            "flow_tables": {},
        }

        if include_routing_tables:
            for device in devices:
                payload["routing_tables"][device] = self._routing_table_lines(device)

        if include_arp_tables:
            for device in devices:
                payload["arp_tables"][device] = self._arp_table_lines(device)

        if include_flow_tables:
            for device in devices:
                payload["flow_tables"][device] = self._flow_table_lines(device)

        state_bytes = json.dumps(payload, indent=2).encode("utf-8")
        return emulation_pb2.CaptureStateResponse(success=True, message="State captured", state_data=state_bytes)

    def restore_state(self, snapshot_name: str, state_data: bytes):
        if emulation_pb2 is None:
            raise RuntimeError("emulation_pb2 is not available")

        try:
            payload = json.loads((state_data or b"{}").decode("utf-8"))
        except Exception as e:
            return emulation_pb2.RestoreStateResponse(success=False, message=f"Invalid state_data: {e}")

        routing = payload.get("routing_tables") or {}
        arp = payload.get("arp_tables") or {}

        for device, lines in routing.items():
            if not isinstance(lines, list):
                continue
            self._restore_routing_table(device, {"routes": lines})

        for device, lines in arp.items():
            if not isinstance(lines, list):
                continue
            # Parse into the legacy structure expected by _restore_arp_table
            entries = []
            for line in lines:
                ent = self._parse_arp_line(line)
                if ent:
                    entries.append(ent)
            self._restore_arp_table(device, {"entries": entries})

        return emulation_pb2.RestoreStateResponse(success=True, message="State restored")

    def get_routing_table(self, device: str):
        if emulation_pb2 is None:
            raise RuntimeError("emulation_pb2 is not available")

        resp = emulation_pb2.GetRoutingTableResponse()
        for line in self._routing_table_lines(device):
            entry = self._parse_route_line(line)
            if not entry:
                continue
            resp.routes.append(
                emulation_pb2.RouteEntry(
                    destination=entry.get("destination", ""),
                    gateway=entry.get("gateway", ""),
                    interface=entry.get("interface", ""),
                    metric=int(entry.get("metric", 0) or 0),
                    protocol=entry.get("protocol", ""),
                )
            )
        return resp

    def get_arp_table(self, device: str):
        if emulation_pb2 is None:
            raise RuntimeError("emulation_pb2 is not available")

        resp = emulation_pb2.GetARPTableResponse()
        for line in self._arp_table_lines(device):
            ent = self._parse_arp_line(line)
            if not ent:
                continue
            resp.entries.append(
                emulation_pb2.ARPEntry(
                    ip=ent.get("ip", ""),
                    mac=ent.get("lladdr", ""),
                    interface=ent.get("dev", ""),
                    state=ent.get("state", ""),
                )
            )
        return resp

    def get_flow_table(self, switch: str):
        if emulation_pb2 is None:
            raise RuntimeError("emulation_pb2 is not available")

        resp = emulation_pb2.GetFlowTableResponse()
        for flow in self._parse_ovs_flows(self._flow_table_lines(switch)):
            resp.flows.append(
                emulation_pb2.FlowEntry(
                    priority=int(flow.get("priority", 0) or 0),
                    match=flow.get("match", ""),
                    actions=flow.get("actions", ""),
                    packet_count=int(flow.get("packet_count", 0) or 0),
                    byte_count=int(flow.get("byte_count", 0) or 0),
                    duration=int(flow.get("duration", 0) or 0),
                )
            )
        return resp

    def _routing_table_lines(self, device: str) -> List[str]:
        out = self._node_cmd(device, "ip route show")
        return [ln.strip() for ln in (out or "").splitlines() if ln.strip()]

    def _arp_table_lines(self, device: str) -> List[str]:
        out = self._node_cmd(device, "ip neigh show")
        return [ln.strip() for ln in (out or "").splitlines() if ln.strip()]

    def _flow_table_lines(self, switch: str) -> List[str]:
        # OVS flows live in the host namespace; attempt both host and node contexts.
        out = ""
        try:
            res = subprocess.run(
                ["ovs-ofctl", "dump-flows", switch],
                capture_output=True,
                text=True,
            )
            out = res.stdout or ""
        except Exception:
            out = ""
        if not out:
            out = self._node_cmd(switch, f"ovs-ofctl dump-flows {switch}")
        return [ln.strip() for ln in (out or "").splitlines() if ln.strip()]

    def _parse_route_line(self, line: str) -> Optional[Dict[str, Any]]:
        parts = (line or "").split()
        if not parts:
            return None
        entry: Dict[str, Any] = {"destination": parts[0], "gateway": "", "interface": "", "metric": 0, "protocol": ""}
        if parts[0] == "default":
            entry["destination"] = "default"
        if "via" in parts:
            try:
                entry["gateway"] = parts[parts.index("via") + 1]
            except Exception:
                pass
        if "dev" in parts:
            try:
                entry["interface"] = parts[parts.index("dev") + 1]
            except Exception:
                pass
        if "metric" in parts:
            try:
                entry["metric"] = int(parts[parts.index("metric") + 1])
            except Exception:
                entry["metric"] = 0
        if "proto" in parts:
            try:
                entry["protocol"] = parts[parts.index("proto") + 1]
            except Exception:
                pass
        return entry

    def _parse_arp_line(self, line: str) -> Optional[Dict[str, Any]]:
        parts = (line or "").split()
        if not parts:
            return None
        ent: Dict[str, Any] = {"ip": parts[0], "dev": "", "lladdr": "", "state": ""}
        if "dev" in parts:
            try:
                ent["dev"] = parts[parts.index("dev") + 1]
            except Exception:
                pass
        if "lladdr" in parts:
            try:
                ent["lladdr"] = parts[parts.index("lladdr") + 1]
            except Exception:
                pass
        # State is typically the last token (REACHABLE/STALE/FAILED/etc.)
        if len(parts) >= 2:
            ent["state"] = parts[-1]
        return ent

    def _parse_ovs_flows(self, lines: List[str]) -> List[Dict[str, Any]]:
        flows: List[Dict[str, Any]] = []
        for line in lines:
            if not line or line.startswith("NXST") or line.startswith("OFPST"):
                continue
            if "actions=" not in line:
                continue
            pre, actions = line.split("actions=", 1)
            fields = [p.strip() for p in pre.split(",") if p.strip()]
            flow: Dict[str, Any] = {
                "priority": 0,
                "match": pre.strip(),
                "actions": actions.strip(),
                "packet_count": 0,
                "byte_count": 0,
                "duration": 0,
            }
            for f in fields:
                if f.startswith("duration="):
                    try:
                        flow["duration"] = int(float(f.split("=", 1)[1]))
                    except Exception:
                        pass
                elif f.startswith("n_packets="):
                    try:
                        flow["packet_count"] = int(f.split("=", 1)[1])
                    except Exception:
                        pass
                elif f.startswith("n_bytes="):
                    try:
                        flow["byte_count"] = int(f.split("=", 1)[1])
                    except Exception:
                        pass
                elif f.startswith("priority="):
                    try:
                        flow["priority"] = int(f.split("=", 1)[1])
                    except Exception:
                        pass
            flows.append(flow)
        return flows

    def capture_complete_state(
        self,
        topology_id: str,
        devices: List[str],
        snapshot_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Capture complete network state
        
        Args:
            topology_id: Topology identifier
            devices: List of device names
            snapshot_name: Optional snapshot name
            
        Returns:
            Snapshot data
        """
        try:
            if not snapshot_name:
                snapshot_name = f"snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

            logger.info(f"Capturing state snapshot: {snapshot_name}")

            state = {
                "snapshot_id": snapshot_name,
                "topology_id": topology_id,
                "timestamp": datetime.utcnow().isoformat(),
                "devices": {},
                "links": {},
                "routing_tables": {},
                "flow_tables": {},
                "arp_tables": {},
                "interface_stats": {},
                "process_states": {}
            }

            for device in devices:
                logger.info(f"Capturing state for device: {device}")

                # Capture device configuration
                state["devices"][device] = self._capture_device_config(device)

                # Capture routing table
                state["routing_tables"][device] = self._capture_routing_table(device)

                # Capture ARP table
                state["arp_tables"][device] = self._capture_arp_table(device)

                # Capture interface statistics
                state["interface_stats"][device] = self._capture_interface_stats(device)

                # Capture process states (for routers)
                state["process_states"][device] = self._capture_process_state(device)

            # Capture link states
            state["links"] = self._capture_link_states(devices)

            # Store snapshot
            self.snapshots[snapshot_name] = state

            # Save to disk
            snapshot_file = os.path.join(self.snapshot_dir, f"{snapshot_name}.json")
            with open(snapshot_file, 'w') as f:
                json.dump(state, f, indent=2)

            logger.info(f"State snapshot captured successfully: {snapshot_name}")

            return {
                "success": True,
                "snapshot_id": snapshot_name,
                "timestamp": state["timestamp"],
                "devices_captured": len(devices),
                "snapshot_file": snapshot_file
            }

        except Exception as e:
            logger.error(f"Failed to capture state: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _capture_device_config(self, device: str) -> Dict[str, Any]:
        """Capture device configuration"""
        try:
            config = {
                "name": device,
                "interfaces": [],
                "type": "unknown"
            }

            # Get network interfaces
            result = subprocess.run(
                ["ip", "netns", "exec", device, "ip", "addr", "show"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                interfaces = []
                current_iface = {}
                
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line and line[0].isdigit():
                        # New interface
                        if current_iface:
                            interfaces.append(current_iface)
                        parts = line.split(':')
                        if len(parts) >= 2:
                            current_iface = {
                                "name": parts[1].strip(),
                                "addresses": []
                            }
                    elif "inet " in line:
                        # IPv4 address
                        parts = line.split()
                        if len(parts) >= 2:
                            current_iface.setdefault("addresses", []).append({
                                "family": "inet",
                                "address": parts[1]
                            })
                    elif "inet6 " in line:
                        # IPv6 address
                        parts = line.split()
                        if len(parts) >= 2:
                            current_iface.setdefault("addresses", []).append({
                                "family": "inet6",
                                "address": parts[1]
                            })
                
                if current_iface:
                    interfaces.append(current_iface)

                config["interfaces"] = interfaces

            return config

        except Exception as e:
            logger.error(f"Failed to capture device config for {device}: {e}")
            return {"name": device, "error": str(e)}

    def _capture_routing_table(self, device: str) -> Dict[str, Any]:
        """Capture routing table"""
        try:
            result = subprocess.run(
                ["ip", "netns", "exec", device, "ip", "route", "show"],
                capture_output=True,
                text=True
            )

            routes = []
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    routes.append(line)

            return {
                "routes": routes,
                "count": len(routes)
            }

        except Exception as e:
            logger.error(f"Failed to capture routing table for {device}: {e}")
            return {"routes": [], "error": str(e)}

    def _capture_arp_table(self, device: str) -> Dict[str, Any]:
        """Capture ARP table"""
        try:
            result = subprocess.run(
                ["ip", "netns", "exec", device, "ip", "neigh", "show"],
                capture_output=True,
                text=True
            )

            arp_entries = []
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 5:
                        arp_entries.append({
                            "ip": parts[0],
                            "dev": parts[2] if len(parts) > 2 else "",
                            "lladdr": parts[4] if len(parts) > 4 else "",
                            "state": parts[5] if len(parts) > 5 else ""
                        })

            return {
                "entries": arp_entries,
                "count": len(arp_entries)
            }

        except Exception as e:
            logger.error(f"Failed to capture ARP table for {device}: {e}")
            return {"entries": [], "error": str(e)}

    def _capture_interface_stats(self, device: str) -> Dict[str, Any]:
        """Capture interface statistics"""
        try:
            result = subprocess.run(
                ["ip", "netns", "exec", device, "ip", "-s", "link", "show"],
                capture_output=True,
                text=True
            )

            stats = {}
            if result.returncode == 0:
                current_iface = None
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line and line[0].isdigit():
                        parts = line.split(':')
                        if len(parts) >= 2:
                            current_iface = parts[1].strip()
                            stats[current_iface] = {}
                    elif "RX:" in line or "TX:" in line:
                        # Skip header lines
                        continue
                    elif current_iface and line:
                        # Parse stats line
                        parts = line.split()
                        if len(parts) >= 8:
                            stats[current_iface] = {
                                "rx_bytes": parts[0] if parts else "0",
                                "rx_packets": parts[1] if len(parts) > 1 else "0",
                                "tx_bytes": parts[4] if len(parts) > 4 else "0",
                                "tx_packets": parts[5] if len(parts) > 5 else "0"
                            }

            return stats

        except Exception as e:
            logger.error(f"Failed to capture interface stats for {device}: {e}")
            return {"error": str(e)}

    def _capture_process_state(self, device: str) -> Dict[str, Any]:
        """Capture running processes (for protocol daemons)"""
        try:
            result = subprocess.run(
                ["ip", "netns", "exec", device, "ps", "aux"],
                capture_output=True,
                text=True
            )

            processes = []
            if result.returncode == 0:
                for line in result.stdout.splitlines()[1:]:  # Skip header
                    parts = line.split(None, 10)
                    if len(parts) >= 11:
                        # Look for routing daemons
                        if any(daemon in parts[10] for daemon in ['ospfd', 'bgpd', 'ripd', 'isisd', 'zebra']):
                            processes.append({
                                "pid": parts[1],
                                "command": parts[10]
                            })

            return {
                "processes": processes,
                "count": len(processes)
            }

        except Exception as e:
            logger.error(f"Failed to capture process state for {device}: {e}")
            return {"processes": [], "error": str(e)}

    def _capture_link_states(self, devices: List[str]) -> Dict[str, Any]:
        """Capture link states between devices"""
        try:
            # Query OVS and Linux bridge for link information
            links = {}

            # Get OVS bridge info
            result = subprocess.run(
                ["ovs-vsctl", "show"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                links["ovs_topology"] = result.stdout
            
            # Get Linux bridge info
            result = subprocess.run(
                ["brctl", "show"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                links["linux_bridges"] = result.stdout

            return links

        except Exception as e:
            logger.error(f"Failed to capture link states: {e}")
            return {"error": str(e)}

    def restore_state(self, snapshot_id: str, devices: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Restore network state from snapshot
        
        Args:
            snapshot_id: Snapshot identifier
            devices: Optional list of devices to restore (None = all)
            
        Returns:
            Restore result
        """
        try:
            logger.info(f"Restoring state from snapshot: {snapshot_id}")

            # Load snapshot
            if snapshot_id not in self.snapshots:
                # Try loading from disk
                snapshot_file = os.path.join(self.snapshot_dir, f"{snapshot_id}.json")
                if os.path.exists(snapshot_file):
                    with open(snapshot_file, 'r') as f:
                        state = json.load(f)
                        self.snapshots[snapshot_id] = state
                else:
                    return {
                        "success": False,
                        "error": f"Snapshot {snapshot_id} not found"
                    }

            state = self.snapshots[snapshot_id]

            # Determine which devices to restore
            devices_to_restore = devices if devices else list(state["devices"].keys())

            restored_count = 0
            errors = []

            for device in devices_to_restore:
                try:
                    # Restore routing table
                    if device in state["routing_tables"]:
                        self._restore_routing_table(device, state["routing_tables"][device])

                    # Restore ARP table
                    if device in state["arp_tables"]:
                        self._restore_arp_table(device, state["arp_tables"][device])

                    restored_count += 1

                except Exception as e:
                    logger.error(f"Failed to restore state for {device}: {e}")
                    errors.append({"device": device, "error": str(e)})

            logger.info(f"State restored successfully from snapshot: {snapshot_id}")

            return {
                "success": True,
                "snapshot_id": snapshot_id,
                "devices_restored": restored_count,
                "errors": errors
            }

        except Exception as e:
            logger.error(f"Failed to restore state: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _restore_routing_table(self, device: str, routing_data: Dict[str, Any]):
        """Restore routing table"""
        try:
            # Clear existing routes
            subprocess.run(
                ["ip", "netns", "exec", device, "ip", "route", "flush", "table", "main"],
                capture_output=True
            )

            # Restore routes
            for route in routing_data.get("routes", []):
                if route.strip():
                    # Parse and restore each route
                    subprocess.run(
                        ["ip", "netns", "exec", device, "ip", "route", "add"] + route.split(),
                        capture_output=True
                    )

            logger.info(f"Routing table restored for {device}")

        except Exception as e:
            logger.error(f"Failed to restore routing table for {device}: {e}")
            raise

    def _restore_arp_table(self, device: str, arp_data: Dict[str, Any]):
        """Restore ARP table"""
        try:
            # ARP entries will automatically repopulate
            # But we can pre-populate static entries if needed
            for entry in arp_data.get("entries", []):
                if entry.get("lladdr"):
                    subprocess.run(
                        [
                            "ip", "netns", "exec", device,
                            "ip", "neigh", "add",
                            entry["ip"],
                            "lladdr", entry["lladdr"],
                            "dev", entry["dev"]
                        ],
                        capture_output=True
                    )

            logger.info(f"ARP table restored for {device}")

        except Exception as e:
            logger.error(f"Failed to restore ARP table for {device}: {e}")
            # Don't raise - ARP will repopulate naturally

    def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots"""
        snapshots = []

        # List from memory
        for snapshot_id, state in self.snapshots.items():
            snapshots.append({
                "snapshot_id": snapshot_id,
                "topology_id": state.get("topology_id"),
                "timestamp": state.get("timestamp"),
                "device_count": len(state.get("devices", {}))
            })

        # List from disk
        if os.path.exists(self.snapshot_dir):
            for filename in os.listdir(self.snapshot_dir):
                if filename.endswith('.json'):
                    snapshot_id = filename[:-5]  # Remove .json
                    if snapshot_id not in self.snapshots:
                        try:
                            snapshot_file = os.path.join(self.snapshot_dir, filename)
                            with open(snapshot_file, 'r') as f:
                                state = json.load(f)
                                snapshots.append({
                                    "snapshot_id": snapshot_id,
                                    "topology_id": state.get("topology_id"),
                                    "timestamp": state.get("timestamp"),
                                    "device_count": len(state.get("devices", {}))
                                })
                        except Exception as e:
                            logger.error(f"Failed to read snapshot {filename}: {e}")

        return snapshots

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot"""
        try:
            # Remove from memory
            if snapshot_id in self.snapshots:
                del self.snapshots[snapshot_id]

            # Remove from disk
            snapshot_file = os.path.join(self.snapshot_dir, f"{snapshot_id}.json")
            if os.path.exists(snapshot_file):
                os.remove(snapshot_file)

            logger.info(f"Snapshot deleted: {snapshot_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete snapshot {snapshot_id}: {e}")
            return False

    def get_snapshot_details(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed snapshot information"""
        if snapshot_id in self.snapshots:
            return self.snapshots[snapshot_id]

        # Try loading from disk
        snapshot_file = os.path.join(self.snapshot_dir, f"{snapshot_id}.json")
        if os.path.exists(snapshot_file):
            try:
                with open(snapshot_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load snapshot {snapshot_id}: {e}")

        return None
