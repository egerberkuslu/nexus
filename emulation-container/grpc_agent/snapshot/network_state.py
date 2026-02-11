"""
Network state capture and restore for Mininet/Containernet networks
Captures routing tables, ARP tables, flow tables, and interface configurations
"""

from __future__ import annotations

import logging
import subprocess
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class NetworkStateCapture:
    """
    Captures comprehensive network state from Mininet/Containernet devices
    """

    def __init__(self, emulation_manager):
        """
        Initialize network state capture

        Args:
            emulation_manager: Reference to EmulationManager instance
        """
        self.em = emulation_manager

    def capture_all(
        self,
        devices: Optional[List[str]] = None,
        include_routing: bool = True,
        include_arp: bool = True,
        include_flows: bool = True,
        include_interfaces: bool = True
    ) -> Dict[str, Any]:
        """
        Capture complete network state

        Args:
            devices: List of device names to capture (None = all)
            include_routing: Capture routing tables
            include_arp: Capture ARP tables
            include_flows: Capture flow tables (switches only)
            include_interfaces: Capture interface configurations

        Returns:
            Dict with all captured state
        """
        target_devices = devices or list(self.em.devices.keys())

        state = {
            "captured_at": datetime.utcnow().isoformat(),
            "device_count": len(target_devices)
        }

        if include_routing:
            state["routing_tables"] = self._capture_routing_tables(target_devices)

        if include_arp:
            state["arp_tables"] = self._capture_arp_tables(target_devices)

        if include_flows:
            state["flow_tables"] = self._capture_flow_tables()

        if include_interfaces:
            state["interface_configs"] = self._capture_interfaces(target_devices)

        # Also capture link states
        state["link_states"] = self._capture_link_states()

        logger.info(f"Captured network state for {len(target_devices)} devices")
        return state

    def _capture_routing_tables(self, devices: List[str]) -> Dict[str, Any]:
        """Capture routing tables from all devices"""
        tables = {}

        for device_name in devices:
            device_info = self.em.devices.get(device_name)
            if not device_info:
                continue

            node = device_info.get('node')
            if not node:
                continue

            try:
                tables[device_name] = {
                    "ipv4": self._parse_routes(node.cmd('ip route show 2>/dev/null').strip()),
                    "ipv6": self._parse_routes(node.cmd('ip -6 route show 2>/dev/null').strip())
                }
            except Exception as e:
                logger.warning(f"Failed to capture routes for {device_name}: {e}")
                tables[device_name] = {"error": str(e)}

        return tables

    def _parse_routes(self, route_output: str) -> List[Dict[str, Any]]:
        """Parse ip route output into structured format"""
        routes = []
        for line in route_output.split('\n'):
            line = line.strip()
            if not line:
                continue

            route = {"raw": line}

            # Parse destination
            parts = line.split()
            if parts:
                if parts[0] == 'default':
                    route["destination"] = "default"
                else:
                    route["destination"] = parts[0]

                # Parse gateway
                if 'via' in parts:
                    idx = parts.index('via')
                    if idx + 1 < len(parts):
                        route["gateway"] = parts[idx + 1]

                # Parse device
                if 'dev' in parts:
                    idx = parts.index('dev')
                    if idx + 1 < len(parts):
                        route["device"] = parts[idx + 1]

                # Parse metric
                if 'metric' in parts:
                    idx = parts.index('metric')
                    if idx + 1 < len(parts):
                        route["metric"] = int(parts[idx + 1])

            routes.append(route)

        return routes

    def _capture_arp_tables(self, devices: List[str]) -> Dict[str, Any]:
        """Capture ARP tables from all devices"""
        tables = {}

        for device_name in devices:
            device_info = self.em.devices.get(device_name)
            if not device_info:
                continue

            node = device_info.get('node')
            if not node:
                continue

            try:
                output = node.cmd('ip neigh show 2>/dev/null').strip()
                tables[device_name] = self._parse_arp(output)
            except Exception as e:
                logger.warning(f"Failed to capture ARP for {device_name}: {e}")
                tables[device_name] = {"error": str(e)}

        return tables

    def _parse_arp(self, arp_output: str) -> List[Dict[str, Any]]:
        """Parse ip neigh output into structured format"""
        entries = []
        for line in arp_output.split('\n'):
            line = line.strip()
            if not line:
                continue

            parts = line.split()
            if len(parts) >= 4:
                entry = {
                    "ip": parts[0],
                    "device": parts[2] if 'dev' in parts else None,
                    "state": parts[-1] if parts[-1] in ['REACHABLE', 'STALE', 'DELAY', 'PROBE', 'FAILED', 'PERMANENT'] else 'UNKNOWN'
                }

                # Find MAC address (lladdr)
                if 'lladdr' in parts:
                    idx = parts.index('lladdr')
                    if idx + 1 < len(parts):
                        entry["mac"] = parts[idx + 1]

                entries.append(entry)

        return entries

    def _capture_flow_tables(self) -> Dict[str, Any]:
        """Capture OpenFlow flow tables from switches"""
        tables = {}

        for device_name, device_info in self.em.devices.items():
            device_type = device_info.get('type', '')
            if device_type not in ['switch', 'ovs', 'p4switch']:
                continue

            try:
                result = subprocess.run(
                    ['ovs-ofctl', 'dump-flows', device_name],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0:
                    flows = self._parse_flows(result.stdout.strip())
                    tables[device_name] = {
                        "flows": flows,
                        "count": len(flows)
                    }
            except Exception as e:
                logger.warning(f"Failed to capture flows for {device_name}: {e}")
                tables[device_name] = {"error": str(e)}

        return tables

    def _parse_flows(self, flow_output: str) -> List[Dict[str, Any]]:
        """Parse ovs-ofctl dump-flows output"""
        flows = []
        for line in flow_output.split('\n'):
            line = line.strip()
            if not line or line.startswith('NXST_FLOW') or line.startswith('OFPST_FLOW'):
                continue

            flow = {"raw": line}

            # Parse basic flow attributes
            if 'cookie=' in line:
                for part in line.split(','):
                    part = part.strip()
                    if '=' in part:
                        key, value = part.split('=', 1)
                        flow[key] = value

            flows.append(flow)

        return flows

    def _capture_interfaces(self, devices: List[str]) -> Dict[str, Any]:
        """Capture interface configurations from all devices"""
        configs = {}

        for device_name in devices:
            device_info = self.em.devices.get(device_name)
            if not device_info:
                continue

            node = device_info.get('node')
            if not node:
                continue

            try:
                output = node.cmd('ip addr show 2>/dev/null').strip()
                configs[device_name] = self._parse_interfaces(output)
            except Exception as e:
                logger.warning(f"Failed to capture interfaces for {device_name}: {e}")
                configs[device_name] = {"error": str(e)}

        return configs

    def _parse_interfaces(self, ip_output: str) -> List[Dict[str, Any]]:
        """Parse ip addr show output"""
        interfaces = []
        current_intf = None

        for line in ip_output.split('\n'):
            if not line:
                continue

            # New interface line starts with a number
            if line[0].isdigit():
                if current_intf:
                    interfaces.append(current_intf)

                parts = line.split(':')
                if len(parts) >= 2:
                    current_intf = {
                        "name": parts[1].strip().split('@')[0],
                        "addresses": [],
                        "state": "UP" if "UP" in line else "DOWN"
                    }

                    # Parse MAC
                    if 'link/ether' in line:
                        mac_parts = line.split('link/ether')
                        if len(mac_parts) > 1:
                            current_intf["mac"] = mac_parts[1].split()[0]

            elif current_intf:
                line = line.strip()

                # Parse MAC address
                if line.startswith('link/ether'):
                    current_intf["mac"] = line.split()[1]

                # Parse IPv4 address
                elif line.startswith('inet '):
                    parts = line.split()
                    if len(parts) >= 2:
                        current_intf["addresses"].append({
                            "type": "ipv4",
                            "address": parts[1]
                        })

                # Parse IPv6 address
                elif line.startswith('inet6 '):
                    parts = line.split()
                    if len(parts) >= 2:
                        current_intf["addresses"].append({
                            "type": "ipv6",
                            "address": parts[1]
                        })

        if current_intf:
            interfaces.append(current_intf)

        return interfaces

    def _capture_link_states(self) -> List[Dict[str, Any]]:
        """Capture current link states"""
        links = []

        for link_id, link_info in getattr(self.em, 'links', {}).items():
            links.append({
                "id": link_id,
                "source": link_info.get('source'),
                "target": link_info.get('target'),
                "bandwidth": link_info.get('bandwidth'),
                "delay": link_info.get('delay'),
                "loss": link_info.get('loss'),
                "status": link_info.get('status', 'up')
            })

        return links

    # ==================== Restore Methods ====================

    def restore_all(
        self,
        state: Dict[str, Any],
        devices: Optional[List[str]] = None,
        restore_routing: bool = True,
        restore_arp: bool = True,
        restore_flows: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Restore network state

        Args:
            state: Captured state dict
            devices: Specific devices to restore (None = all)
            restore_routing: Restore routing tables
            restore_arp: Restore ARP tables
            restore_flows: Restore flow tables

        Returns:
            List of errors (empty if successful)
        """
        errors = []
        target_devices = devices or list(state.get('routing_tables', {}).keys())

        if restore_routing:
            for device in target_devices:
                if device in state.get('routing_tables', {}):
                    try:
                        self._restore_routing_table(device, state['routing_tables'][device])
                    except Exception as e:
                        errors.append({
                            'device': device,
                            'component': 'routing',
                            'error': str(e)
                        })

        if restore_arp:
            for device in target_devices:
                if device in state.get('arp_tables', {}):
                    try:
                        self._restore_arp_table(device, state['arp_tables'][device])
                    except Exception as e:
                        errors.append({
                            'device': device,
                            'component': 'arp',
                            'error': str(e)
                        })

        if restore_flows:
            for switch in state.get('flow_tables', {}).keys():
                try:
                    self._restore_flow_table(switch, state['flow_tables'][switch])
                except Exception as e:
                    errors.append({
                        'device': switch,
                        'component': 'flows',
                        'error': str(e)
                    })

        return errors

    def _restore_routing_table(self, device_name: str, routes: Dict[str, Any]):
        """Restore routing table for a device"""
        device_info = self.em.devices.get(device_name)
        if not device_info:
            raise ValueError(f"Device {device_name} not found")

        node = device_info.get('node')
        if not node:
            raise ValueError(f"No node for device {device_name}")

        # Restore IPv4 routes
        for route in routes.get('ipv4', []):
            if 'raw' in route:
                # Use raw command
                cmd = f"ip route replace {route['raw']}"
            elif route.get('destination'):
                cmd = f"ip route replace {route['destination']}"
                if route.get('gateway'):
                    cmd += f" via {route['gateway']}"
                if route.get('device'):
                    cmd += f" dev {route['device']}"
            else:
                continue

            try:
                node.cmd(cmd)
            except Exception as e:
                logger.warning(f"Failed to restore route on {device_name}: {e}")

    def _restore_arp_table(self, device_name: str, entries: List[Dict[str, Any]]):
        """Restore ARP table for a device"""
        device_info = self.em.devices.get(device_name)
        if not device_info:
            raise ValueError(f"Device {device_name} not found")

        node = device_info.get('node')
        if not node:
            raise ValueError(f"No node for device {device_name}")

        for entry in entries:
            if entry.get('ip') and entry.get('mac') and entry.get('device'):
                cmd = f"ip neigh replace {entry['ip']} lladdr {entry['mac']} dev {entry['device']}"
                try:
                    node.cmd(cmd)
                except Exception as e:
                    logger.warning(f"Failed to restore ARP entry on {device_name}: {e}")

    def _restore_flow_table(self, switch_name: str, flows: Dict[str, Any]):
        """Restore flow table for a switch"""
        # Clear existing flows first
        subprocess.run(
            ['ovs-ofctl', 'del-flows', switch_name],
            capture_output=True,
            timeout=10
        )

        # Add flows back
        for flow in flows.get('flows', []):
            if 'raw' in flow:
                # Parse and add flow
                raw = flow['raw']
                # Remove metadata fields
                for field in ['duration', 'n_packets', 'n_bytes', 'idle_age', 'hard_age']:
                    if f'{field}=' in raw:
                        raw = ','.join(p for p in raw.split(',') if not p.strip().startswith(f'{field}='))

                try:
                    subprocess.run(
                        ['ovs-ofctl', 'add-flow', switch_name, raw],
                        capture_output=True,
                        timeout=10
                    )
                except Exception as e:
                    logger.warning(f"Failed to restore flow on {switch_name}: {e}")


# Export
__all__ = ['NetworkStateCapture']
