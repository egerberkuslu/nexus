"""
Export/Import Service (Port 8008)
Exports topologies to various formats (Mininet Python, GraphML, JSON)
Imports topologies from external formats
"""

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging
import json
import keyword
import re
from datetime import datetime

# Import shared components
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.messaging.rabbitmq import RabbitMQPublisher
from shared.utils.consul_client import ConsulClient
from shared.models.topology import Topology, Node, Link
from shared.schemas.topology_schema import TopologyExport

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Caduceus-Flux Export/Import Service",
    description="Topology export and import in multiple formats",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service clients
consul_client = ConsulClient()
rabbitmq_publisher = RabbitMQPublisher()

SERVICE_PORT = 8008


# Pydantic models
class ExportFormat(BaseModel):
    format: str = Field(..., description="Export format: mininet, mininet-wifi, containernet, graphml, json, yaml")
    topology_id: str = Field(..., description="Topology ID to export")
    options: Dict[str, Any] = Field(default_factory=dict, description="Format-specific options")


class ExportResponse(BaseModel):
    format: str
    topology_id: str
    content: str
    filename: str
    timestamp: datetime


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return False


def _coerce_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _coerce_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        # allow comma-separated values
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _safe_py_identifier(raw: str, used: set[str]) -> str:
    name = str(raw or "").strip()
    if not name:
        name = "n"
    name = re.sub(r"\W+", "_", name)
    if re.match(r"^\d", name):
        name = f"n_{name}"
    if keyword.iskeyword(name):
        name = f"{name}_"
    if not name:
        name = "n"
    base = name
    i = 2
    while name in used:
        name = f"{base}_{i}"
        i += 1
    used.add(name)
    return name


def _maybe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _position_from_node(node: Dict[str, Any], props: Dict[str, Any]) -> Optional[str]:
    position = props.get("position") or props.get("coordinates")
    if isinstance(position, str) and position.strip():
        return position.strip()
    if isinstance(position, (list, tuple)):
        coords = []
        for v in position:
            fv = _maybe_float(v)
            if fv is None:
                return None
            coords.append(fv)
        if len(coords) >= 3:
            return f"{coords[0]},{coords[1]},{coords[2]}"
        if len(coords) == 2:
            return f"{coords[0]},{coords[1]},0"
        return None

    x = _maybe_float(node.get("x"))
    y = _maybe_float(node.get("y"))
    if x is None or y is None:
        return None
    if x == 0.0 and y == 0.0:
        return None
    return f"{x},{y},0"


def _node_index(topology_data: Dict[str, Any]) -> tuple[dict[str, Dict[str, Any]], dict[str, str]]:
    """Return (node_by_id, name_by_id) for link resolution."""
    nodes = topology_data.get("nodes") or topology_data.get("devices") or []
    node_by_id: dict[str, Dict[str, Any]] = {}
    name_by_id: dict[str, str] = {}
    if not isinstance(nodes, list):
        return node_by_id, name_by_id
    for n in nodes:
        if not isinstance(n, dict):
            continue
        nid = n.get("id")
        name = n.get("name")
        if isinstance(nid, str) and nid:
            node_by_id[nid] = n
            if isinstance(name, str) and name:
                name_by_id[nid] = name
    return node_by_id, name_by_id


def _resolve_node_name(node_id: Any, name_by_id: dict[str, str]) -> Optional[str]:
    if isinstance(node_id, str) and node_id in name_by_id:
        return name_by_id[node_id]
    return None


# Mininet Python exporter
class MininetExporter:
    """Export topology to Mininet Python script"""

    @staticmethod
    def export(topology_data: Dict) -> str:
        """Generate Mininet Python script"""

        nodes = topology_data.get("nodes") or topology_data.get("devices") or []
        if not isinstance(nodes, list):
            nodes = []
        node_by_id, name_by_id = _node_index(topology_data)

        used_vars: set[str] = set()
        var_by_node_name: dict[str, str] = {}
        for n in nodes:
            if not isinstance(n, dict):
                continue
            nname = n.get("name")
            if isinstance(nname, str) and nname:
                var_by_node_name[nname] = _safe_py_identifier(nname, used_vars)

        script = """#!/usr/bin/env python3
\"\"\"
Mininet topology script
Generated by Caduceus-Flux
Topology: {topology_name}
Generated: {timestamp}
\"\"\"

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSKernelSwitch, Host
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink

def topology():
    \"\"\"Create custom topology\"\"\"
    
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch, link=TCLink, autoSetMacs=True)

    info('*** Adding controller\\n')
""".format(
            topology_name=topology_data.get("name", "Unknown"),
            timestamp=datetime.utcnow().isoformat()
        )

        # Add controllers
        controllers = topology_data.get("controllers", [])
        if controllers:
            for i, ctrl in enumerate(controllers):
                ctrl_name = ctrl.get("name", f"c{i}")
                ctrl_ip = ctrl.get("ip", "127.0.0.1")
                ctrl_port = ctrl.get("port", 6653)
                ctrl_var = _safe_py_identifier(str(ctrl_name), used_vars)
                ctrl_label = str(ctrl_name)
                script += f"    {ctrl_var} = net.addController('{ctrl_label}', controller=RemoteController, ip='{ctrl_ip}', port={int(ctrl_port)})\n"
        else:
            script += "    c0 = net.addController('c0')\n"

        # Add hosts/routers
        script += "\n    info('*** Adding hosts\\n')\n"
        for node in nodes:
            if not isinstance(node, dict):
                continue
            dtype = str(node.get("device_type") or node.get("type") or "").strip().lower()
            if dtype not in {"host", "router"}:
                continue
            name = str(node.get("name") or "")
            if not name:
                continue
            var = var_by_node_name.get(name) or _safe_py_identifier(name, used_vars)
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            ip = str(props.get("ip") or "").strip()
            mac = str(props.get("mac") or "").strip()
            default_route = str(props.get("default_route") or props.get("defaultRoute") or "").strip()

            params: list[str] = []
            if ip:
                params.append(f"ip='{ip}'")
            if mac:
                params.append(f"mac='{mac}'")
            if default_route:
                params.append(f"defaultRoute='{default_route}'")

            params_str = (", " + ", ".join(params)) if params else ""
            script += f"    {var} = net.addHost('{name}'{params_str})\n"

        # Add switches (including p4switch as plain switch)
        script += "\n    info('*** Adding switches\\n')\n"
        for node in nodes:
            if not isinstance(node, dict):
                continue
            dtype = str(node.get("device_type") or node.get("type") or "").strip().lower()
            if dtype not in {"switch", "p4switch", "p4_switch"}:
                continue
            name = str(node.get("name") or "")
            if not name:
                continue
            var = var_by_node_name.get(name) or _safe_py_identifier(name, used_vars)
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            dpid = str(props.get("dpid") or props.get("datapath_id") or "").strip()

            if dpid:
                script += f"    {var} = net.addSwitch('{name}', dpid='{dpid}')\n"
            else:
                script += f"    {var} = net.addSwitch('{name}')\n"

        # Add links
        script += "\n    info('*** Creating links\\n')\n"
        links = topology_data.get("links") or []
        if isinstance(links, list):
            for link in links:
                if not isinstance(link, dict):
                    continue
                source_id = link.get("source_node_id") or link.get("source") or link.get("node1")
                target_id = link.get("target_node_id") or link.get("target") or link.get("node2")
                source_name = _resolve_node_name(source_id, name_by_id) or str(source_id or "")
                target_name = _resolve_node_name(target_id, name_by_id) or str(target_id or "")
                if not source_name or not target_name:
                    continue
                source_var = var_by_node_name.get(source_name)
                target_var = var_by_node_name.get(target_name)
                if not source_var or not target_var:
                    continue

                params: list[str] = []
                bw = link.get("bandwidth")
                delay = link.get("delay")
                loss = link.get("loss")
                max_queue = link.get("max_queue_size") or link.get("max_queue")
                if bw is not None:
                    try:
                        params.append(f"bw={float(bw)}")
                    except Exception:
                        pass
                if delay is not None:
                    try:
                        params.append(f"delay='{float(delay)}ms'")
                    except Exception:
                        pass
                if loss is not None:
                    try:
                        params.append(f"loss={float(loss)}")
                    except Exception:
                        pass
                if max_queue is not None:
                    try:
                        params.append(f"max_queue_size={int(max_queue)}")
                    except Exception:
                        pass

                params_str = (", " + ", ".join(params)) if params else ""
                script += f"    net.addLink({source_var}, {target_var}{params_str})\n"

        # Add network startup and CLI
        script += """
    info('*** Starting network\\n')
    net.start()
    
    info('*** Running CLI\\n')
    CLI(net)
    
    info('*** Stopping network\\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    topology()
"""

        return script


class MininetWiFiExporter:
    """Export topology to Mininet-WiFi Python script"""

    @staticmethod
    def export(topology_data: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> str:
        options = options or {}

        nodes = topology_data.get("nodes") or topology_data.get("devices") or []
        if not isinstance(nodes, list):
            nodes = []
        _, name_by_id = _node_index(topology_data)

        used_vars: set[str] = set()
        var_by_node_name: dict[str, str] = {}
        for n in nodes:
            if not isinstance(n, dict):
                continue
            nname = n.get("name")
            if isinstance(nname, str) and nname:
                var_by_node_name[nname] = _safe_py_identifier(nname, used_vars)

        script = """#!/usr/bin/env python3
\"\"\"
Mininet-WiFi topology script
Generated by Caduceus-Flux
Topology: {topology_name}
Generated: {timestamp}
\"\"\"

from mn_wifi.net import Mininet_wifi
from mn_wifi.node import OVSKernelAP
from mn_wifi.cli import CLI
from mininet.node import RemoteController, OVSKernelSwitch
from mininet.log import setLogLevel, info
from mininet.link import TCLink

def topology():
    net = Mininet_wifi(controller=RemoteController, switch=OVSKernelSwitch, accessPoint=OVSKernelAP, link=TCLink, autoSetMacs=True)

    info('*** Adding controller\\n')
""".format(
            topology_name=topology_data.get("name", "Unknown"),
            timestamp=datetime.utcnow().isoformat(),
        )

        controllers = topology_data.get("controllers", [])
        if controllers:
            for i, ctrl in enumerate(controllers):
                ctrl_name = ctrl.get("name", f"c{i}")
                ctrl_ip = ctrl.get("ip", "127.0.0.1")
                ctrl_port = ctrl.get("port", 6653)
                ctrl_var = _safe_py_identifier(str(ctrl_name), used_vars)
                ctrl_label = str(ctrl_name)
                script += f"    {ctrl_var} = net.addController('{ctrl_label}', controller=RemoteController, ip='{ctrl_ip}', port={int(ctrl_port)})\n"
        else:
            script += "    c0 = net.addController('c0')\n"

        script += "\n    info('*** Adding stations\\n')\n"
        for node in nodes:
            if not isinstance(node, dict):
                continue
            dtype = str(node.get("device_type") or node.get("type") or "").strip().lower()
            if dtype not in {"station", "sta"}:
                continue
            name = str(node.get("name") or "")
            if not name:
                continue
            var = var_by_node_name.get(name) or _safe_py_identifier(name, used_vars)
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            ip = str(props.get("ip") or "").strip()
            mac = str(props.get("mac") or "").strip()
            position = _position_from_node(node, props)

            params: list[str] = []
            if ip:
                params.append(f"ip='{ip}'")
            if mac:
                params.append(f"mac='{mac}'")
            if position:
                params.append(f"position='{position}'")

            security = str(props.get("security") or "").strip()
            passwd = str(props.get("password") or props.get("passwd") or props.get("psk") or "").strip()
            if security and security.lower() != "open" and passwd:
                params.append(f"encrypt='{security}'")
                params.append(f"passwd='{passwd}'")

            params_str = (", " + ", ".join(params)) if params else ""
            script += f"    {var} = net.addStation('{name}'{params_str})\n"

        script += "\n    info('*** Adding access points\\n')\n"
        for node in nodes:
            if not isinstance(node, dict):
                continue
            dtype = str(node.get("device_type") or node.get("type") or "").strip().lower()
            if dtype not in {"ap", "accesspoint", "access_point"}:
                continue
            name = str(node.get("name") or "")
            if not name:
                continue
            var = var_by_node_name.get(name) or _safe_py_identifier(name, used_vars)
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            ssid = str(props.get("ssid") or name).strip()
            mode = str(props.get("mode") or "g").strip()
            channel = str(props.get("channel") or "1").strip()
            position = _position_from_node(node, props)

            params = [f"ssid='{ssid}'", f"mode='{mode}'", f"channel='{channel}'"]
            if position:
                params.append(f"position='{position}'")
            params_str = ", ".join(params)
            script += f"    {var} = net.addAccessPoint('{name}', {params_str})\n"

        script += "\n    info('*** Adding hosts\\n')\n"
        for node in nodes:
            if not isinstance(node, dict):
                continue
            dtype = str(node.get("device_type") or node.get("type") or "").strip().lower()
            if dtype not in {"host", "router"}:
                continue
            name = str(node.get("name") or "")
            if not name:
                continue
            var = var_by_node_name.get(name) or _safe_py_identifier(name, used_vars)
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            ip = str(props.get("ip") or "").strip()
            mac = str(props.get("mac") or "").strip()
            default_route = str(props.get("default_route") or props.get("defaultRoute") or "").strip()

            params: list[str] = []
            if ip:
                params.append(f"ip='{ip}'")
            if mac:
                params.append(f"mac='{mac}'")
            if default_route:
                params.append(f"defaultRoute='{default_route}'")
            params_str = (", " + ", ".join(params)) if params else ""
            script += f"    {var} = net.addHost('{name}'{params_str})\n"

        script += "\n    info('*** Adding switches\\n')\n"
        for node in nodes:
            if not isinstance(node, dict):
                continue
            dtype = str(node.get("device_type") or node.get("type") or "").strip().lower()
            if dtype not in {"switch", "p4switch", "p4_switch"}:
                continue
            name = str(node.get("name") or "")
            if not name:
                continue
            var = var_by_node_name.get(name) or _safe_py_identifier(name, used_vars)
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}
            dpid = str(props.get("dpid") or props.get("datapath_id") or "").strip()
            if dpid:
                script += f"    {var} = net.addSwitch('{name}', dpid='{dpid}')\n"
            else:
                script += f"    {var} = net.addSwitch('{name}')\n"

        script += "\n    info('*** Configuring wifi nodes\\n')\n"
        script += "    net.configureWifiNodes()\n"
        model = str(options.get('propagation_model') or 'logDistance')
        exp = options.get('propagation_exp')
        if exp is None:
            exp = 4
        try:
            exp = int(exp)
        except Exception:
            exp = 4
        script += f"    net.setPropagationModel(model='{model}', exp={exp})\n"

        script += "\n    info('*** Creating links\\n')\n"
        links = topology_data.get("links") or []
        if isinstance(links, list):
            for link in links:
                if not isinstance(link, dict):
                    continue
                source_id = link.get("source_node_id") or link.get("source") or link.get("node1")
                target_id = link.get("target_node_id") or link.get("target") or link.get("node2")
                source_name = _resolve_node_name(source_id, name_by_id) or str(source_id or "")
                target_name = _resolve_node_name(target_id, name_by_id) or str(target_id or "")
                if not source_name or not target_name:
                    continue
                source_var = var_by_node_name.get(source_name)
                target_var = var_by_node_name.get(target_name)
                if not source_var or not target_var:
                    continue

                params: list[str] = []
                bw = link.get("bandwidth")
                delay = link.get("delay")
                loss = link.get("loss")
                max_queue = link.get("max_queue_size") or link.get("max_queue")
                if bw is not None:
                    try:
                        params.append(f"bw={float(bw)}")
                    except Exception:
                        pass
                if delay is not None:
                    try:
                        params.append(f"delay='{float(delay)}ms'")
                    except Exception:
                        pass
                if loss is not None:
                    try:
                        params.append(f"loss={float(loss)}")
                    except Exception:
                        pass
                if max_queue is not None:
                    try:
                        params.append(f"max_queue_size={int(max_queue)}")
                    except Exception:
                        pass

                params_str = (", " + ", ".join(params)) if params else ""
                script += f"    net.addLink({source_var}, {target_var}{params_str})\n"

        script += """
    info('*** Starting network\\n')
    net.start()

    info('*** Running CLI\\n')
    CLI(net)

    info('*** Stopping network\\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    topology()
"""
        return script


class ContainernetExporter:
    """Export topology to Containernet Python script (Docker-aware, WiFi-aware when available)."""

    @staticmethod
    def export(topology_data: Dict[str, Any], options: Optional[Dict[str, Any]] = None) -> str:
        options = options or {}

        nodes = topology_data.get("nodes") or topology_data.get("devices") or []
        if not isinstance(nodes, list):
            nodes = []
        _, name_by_id = _node_index(topology_data)

        used_vars: set[str] = set()
        var_by_node_name: dict[str, str] = {}
        for n in nodes:
            if not isinstance(n, dict):
                continue
            nname = n.get("name")
            if isinstance(nname, str) and nname:
                var_by_node_name[nname] = _safe_py_identifier(nname, used_vars)

        script = """#!/usr/bin/env python3
\"\"\"
Containernet topology script
Generated by Caduceus-Flux
Topology: {topology_name}
Generated: {timestamp}
\"\"\"

try:
    from mininet.net import Containernet
except Exception:
    from containernet.net import Containernet

try:
    from mininet.node import Docker
except Exception:
    from containernet.node import Docker

from mininet.node import RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import TCLink

def topology():
    net = Containernet(controller=RemoteController, switch=OVSKernelSwitch, link=TCLink, autoSetMacs=True, autoStaticArp=True, build=False)

    info('*** Adding controller\\n')
""".format(
            topology_name=topology_data.get("name", "Unknown"),
            timestamp=datetime.utcnow().isoformat(),
        )

        controllers = topology_data.get("controllers", [])
        if controllers:
            for i, ctrl in enumerate(controllers):
                ctrl_name = ctrl.get("name", f"c{i}")
                ctrl_ip = ctrl.get("ip", "127.0.0.1")
                ctrl_port = ctrl.get("port", 6653)
                ctrl_var = _safe_py_identifier(str(ctrl_name), used_vars)
                ctrl_label = str(ctrl_name)
                script += f"    {ctrl_var} = net.addController('{ctrl_label}', controller=RemoteController, ip='{ctrl_ip}', port={int(ctrl_port)})\n"
        else:
            script += "    c0 = net.addController('c0')\n"

        script += "\n    info('*** Adding nodes\\n')\n"
        for node in nodes:
            if not isinstance(node, dict):
                continue
            dtype = str(node.get("device_type") or node.get("type") or "").strip().lower()
            name = str(node.get("name") or "")
            if not name:
                continue
            var = var_by_node_name.get(name) or _safe_py_identifier(name, used_vars)
            props = node.get("properties") if isinstance(node.get("properties"), dict) else {}

            is_dockerized = _as_bool(props.get("dockerized")) or bool(props.get("docker_image") or props.get("image")) or dtype in {"docker", "container"}
            docker_image = str(props.get("docker_image") or props.get("image") or "ubuntu:22.04").strip()
            docker_command = props.get("docker_command") or props.get("command")
            docker_env = _coerce_dict(props.get("docker_environment") or props.get("environment"))
            docker_volumes = props.get("docker_volumes") or props.get("volumes")
            docker_ports = props.get("docker_ports") or props.get("ports")
            publish_all = props.get("docker_publish_all_ports")
            if publish_all is None:
                publish_all = props.get("publish_all_ports")

            ip = str(props.get("ip") or "").strip()
            mac = str(props.get("mac") or "").strip()
            default_route = str(props.get("default_route") or props.get("defaultRoute") or "").strip()

            if dtype in {"switch", "p4switch", "p4_switch"}:
                dpid = str(props.get("dpid") or props.get("datapath_id") or "").strip()
                if dpid:
                    script += f"    {var} = net.addSwitch('{name}', dpid='{dpid}')\n"
                else:
                    script += f"    {var} = net.addSwitch('{name}')\n"
                continue

            if dtype in {"ap", "accesspoint", "access_point"}:
                # Prefer WiFi-enabled Containernet builds; otherwise AP behaves like a switch.
                ssid = str(props.get("ssid") or name).strip()
                mode = str(props.get("mode") or "g").strip()
                channel = str(props.get("channel") or "1").strip()
                position = _position_from_node(node, props)

                params = [f"ssid='{ssid}'", f"mode='{mode}'", f"channel='{channel}'"]
                if position:
                    params.append(f"position='{position}'")
                params_str = ", ".join(params)
                script += "    if hasattr(net, 'addAccessPoint'):\n"
                script += f"        {var} = net.addAccessPoint('{name}', {params_str})\n"
                script += "    else:\n"
                script += f"        {var} = net.addSwitch('{name}')\n"
                continue

            if dtype in {"station", "sta"}:
                position = _position_from_node(node, props)

                params: list[str] = []
                if ip:
                    params.append(f"ip='{ip}'")
                if mac:
                    params.append(f"mac='{mac}'")
                if position:
                    params.append(f"position='{position}'")

                security = str(props.get("security") or "").strip()
                passwd = str(props.get("password") or props.get("passwd") or props.get("psk") or "").strip()
                if security and security.lower() != "open" and passwd:
                    params.append(f"encrypt='{security}'")
                    params.append(f"passwd='{passwd}'")
                params_str = (", " + ", ".join(params)) if params else ""
                script += "    if hasattr(net, 'addStation'):\n"
                script += f"        {var} = net.addStation('{name}'{params_str})\n"
                script += "    else:\n"
                fallback_host_params: list[str] = []
                if ip:
                    fallback_host_params.append(f"ip='{ip}'")
                if mac:
                    fallback_host_params.append(f"mac='{mac}'")
                if default_route:
                    fallback_host_params.append(f"defaultRoute='{default_route}'")
                fallback_param_str = (", " + ", ".join(fallback_host_params)) if fallback_host_params else ""
                script += f"        {var} = net.addHost('{name}'{fallback_param_str})\n"
                continue

            if is_dockerized and dtype in {"host", "router", "docker", "container"}:
                docker_kwargs: list[str] = ["cls=Docker", f"dimage={docker_image!r}", "rm=True"]
                if ip:
                    docker_kwargs.append(f"ip='{ip}'")
                if mac:
                    docker_kwargs.append(f"mac='{mac}'")
                if default_route:
                    docker_kwargs.append(f"defaultRoute='{default_route}'")

                if docker_command:
                    if isinstance(docker_command, (list, tuple)):
                        dcmd = " ".join(str(part) for part in docker_command if str(part).strip())
                    else:
                        dcmd = str(docker_command)
                    if dcmd.strip():
                        docker_kwargs.append(f"dcmd={dcmd!r}")

                if docker_env:
                    docker_kwargs.append(f"environment={docker_env!r}")

                if docker_volumes:
                    docker_kwargs.append(f"volumes={_coerce_list(docker_volumes)!r}")

                if docker_ports:
                    docker_kwargs.append(f"ports={docker_ports!r}")

                if publish_all is not None:
                    docker_kwargs.append(f"publish_all_ports={str(_as_bool(publish_all))}")

                script += f"    {var} = net.addHost('{name}', {', '.join(docker_kwargs)})\n"
                continue

            # Default: regular host (router exported as host)
            host_kwargs: list[str] = []
            if ip:
                host_kwargs.append(f"ip='{ip}'")
            if mac:
                host_kwargs.append(f"mac='{mac}'")
            if default_route:
                host_kwargs.append(f"defaultRoute='{default_route}'")
            kwargs_str = (", " + ", ".join(host_kwargs)) if host_kwargs else ""
            script += f"    {var} = net.addHost('{name}'{kwargs_str})\n"

        wifi_nodes_present = any(
            str((n or {}).get("device_type") or (n or {}).get("type") or "").strip().lower() in {"ap", "accesspoint", "access_point", "station", "sta"}
            for n in nodes
            if isinstance(n, dict)
        )

        if wifi_nodes_present and _as_bool(options.get("configure_wifi", True)):
            script += "\n    info('*** Configuring wifi nodes (if supported)\\n')\n"
            script += "    if hasattr(net, 'configureWifiNodes'):\n"
            script += "        net.configureWifiNodes()\n"
            model = str(options.get('propagation_model') or 'logDistance')
            exp = options.get('propagation_exp')
            if exp is None:
                exp = 4
            try:
                exp = int(exp)
            except Exception:
                exp = 4
            script += "        if hasattr(net, 'setPropagationModel'):\n"
            script += f"            net.setPropagationModel(model='{model}', exp={exp})\n"

        script += "\n    info('*** Creating links\\n')\n"
        links = topology_data.get("links") or []
        if isinstance(links, list):
            for link in links:
                if not isinstance(link, dict):
                    continue
                source_id = link.get("source_node_id") or link.get("source") or link.get("node1")
                target_id = link.get("target_node_id") or link.get("target") or link.get("node2")
                source_name = _resolve_node_name(source_id, name_by_id) or str(source_id or "")
                target_name = _resolve_node_name(target_id, name_by_id) or str(target_id or "")
                if not source_name or not target_name:
                    continue
                source_var = var_by_node_name.get(source_name)
                target_var = var_by_node_name.get(target_name)
                if not source_var or not target_var:
                    continue

                params: list[str] = []
                bw = link.get("bandwidth")
                delay = link.get("delay")
                loss = link.get("loss")
                max_queue = link.get("max_queue_size") or link.get("max_queue")
                if bw is not None:
                    try:
                        params.append(f"bw={float(bw)}")
                    except Exception:
                        pass
                if delay is not None:
                    try:
                        params.append(f"delay='{float(delay)}ms'")
                    except Exception:
                        pass
                if loss is not None:
                    try:
                        params.append(f"loss={float(loss)}")
                    except Exception:
                        pass
                if max_queue is not None:
                    try:
                        params.append(f"max_queue_size={int(max_queue)}")
                    except Exception:
                        pass

                params_str = (", " + ", ".join(params)) if params else ""
                script += f"    net.addLink({source_var}, {target_var}{params_str})\n"

        script += """
    info('*** Starting network\\n')
    net.build()
    net.start()

    info('*** Running CLI\\n')
    CLI(net)

    info('*** Stopping network\\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    topology()
"""
        return script


# GraphML exporter
class GraphMLExporter:
    """Export topology to GraphML format"""

    @staticmethod
    def export(topology_data: Dict) -> str:
        """Generate GraphML XML"""
        
        graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
         http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  
  <!-- Graph attributes -->
  <key id="name" for="graph" attr.name="name" attr.type="string"/>
  <key id="description" for="graph" attr.name="description" attr.type="string"/>
  
  <!-- Node attributes -->
  <key id="device_type" for="node" attr.name="device_type" attr.type="string"/>
  <key id="ip" for="node" attr.name="ip" attr.type="string"/>
  <key id="mac" for="node" attr.name="mac" attr.type="string"/>
  
  <!-- Edge attributes -->
  <key id="bandwidth" for="edge" attr.name="bandwidth" attr.type="int"/>
  <key id="delay" for="edge" attr.name="delay" attr.type="int"/>
  <key id="loss" for="edge" attr.name="loss" attr.type="double"/>
  
  <graph id="G" edgedefault="undirected">
    <data key="name">{name}</data>
    <data key="description">{description}</data>
""".format(
            name=topology_data.get("name", "Unknown"),
            description=topology_data.get("description", "")
        )

        # Add nodes
        for node in topology_data.get("nodes", []):
            node_id = node.get("id", node.get("name"))
            name = node.get("name")
            device_type = node.get("device_type", "unknown")
            properties = node.get("properties", {})
            
            graphml += f'    <node id="{node_id}">\n'
            graphml += f'      <data key="device_type">{device_type}</data>\n'
            
            if properties.get("ip"):
                graphml += f'      <data key="ip">{properties["ip"]}</data>\n'
            if properties.get("mac"):
                graphml += f'      <data key="mac">{properties["mac"]}</data>\n'
            
            graphml += '    </node>\n'

        # Add edges
        for i, link in enumerate(topology_data.get("links", [])):
            source = link.get("source_node_id") or link.get("source") or link.get("node1")
            target = link.get("target_node_id") or link.get("target") or link.get("node2")
            
            if not source or not target:
                continue
            
            graphml += f'    <edge id="e{i}" source="{source}" target="{target}">\n'
            
            if link.get("bandwidth"):
                graphml += f'      <data key="bandwidth">{link["bandwidth"]}</data>\n'
            if link.get("delay"):
                graphml += f'      <data key="delay">{link["delay"]}</data>\n'
            if link.get("loss"):
                graphml += f'      <data key="loss">{link["loss"]}</data>\n'
            
            graphml += '    </edge>\n'

        graphml += """  </graph>
</graphml>
"""

        return graphml


# Helper functions
def publish_event(event_type: str, data: Dict):
    """Publish export/import event"""
    try:
        rabbitmq_publisher.publish(
            exchange="caduceus",
            routing_key=f"export_import.{event_type}",
            message=data
        )
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")


# API endpoints

@app.on_event("startup")
async def startup_event():
    """Service startup"""
    logger.info("Starting Export/Import Service...")
    try:
        consul_client.register_service("export-import", SERVICE_PORT)
        rabbitmq_publisher.connect()
        logger.info("Export/Import Service started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Service shutdown"""
    logger.info("Shutting down Export/Import Service...")
    consul_client.deregister_service("export-import")
    rabbitmq_publisher.disconnect()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "export-import",
        "supported_formats": ["mininet", "mininet-wifi", "containernet", "graphml", "json", "yaml"],
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/export", response_model=ExportResponse)
async def export_topology(export_request: ExportFormat):
    """
    Export topology to specified format
    
    Supported formats:
    - mininet: Mininet Python script
    - mininet-wifi: Mininet-WiFi Python script
    - containernet: Containernet Python script
    - graphml: GraphML XML format
    - json: JSON format
    - yaml: YAML format
    """
    try:
        logger.info(f"Exporting topology {export_request.topology_id} to {export_request.format}")

        # Fetch topology from Topology Service
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"http://topology-service:8001/api/topologies/{export_request.topology_id}")
                if response.status_code == 200:
                    topology_data = response.json()
                else:
                    raise HTTPException(status_code=404, detail=f"Topology {export_request.topology_id} not found")
            except httpx.HTTPError as e:
                logger.error(f"Failed to fetch topology: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to fetch topology: {str(e)}")

        # Export based on format
        content = ""
        filename = ""

        fmt = export_request.format.lower().strip()
        fmt_aliases = {
            "mininet_wifi": "mininet-wifi",
            "mininetwifi": "mininet-wifi",
            "wifi": "mininet-wifi",
            "containernet": "containernet",
            "container-net": "containernet",
        }
        fmt = fmt_aliases.get(fmt, fmt)

        if fmt == "mininet":
            content = MininetExporter.export(topology_data)
            filename = f"{topology_data['name'].replace(' ', '_').lower()}.py"

        elif fmt == "mininet-wifi":
            content = MininetWiFiExporter.export(topology_data, export_request.options or {})
            filename = f"{topology_data['name'].replace(' ', '_').lower()}_wifi.py"

        elif fmt == "containernet":
            content = ContainernetExporter.export(topology_data, export_request.options or {})
            filename = f"{topology_data['name'].replace(' ', '_').lower()}_containernet.py"
            
        elif fmt == "graphml":
            content = GraphMLExporter.export(topology_data)
            filename = f"{topology_data['name'].replace(' ', '_').lower()}.graphml"
            
        elif fmt == "json":
            content = json.dumps(topology_data, indent=2)
            filename = f"{topology_data['name'].replace(' ', '_').lower()}.json"
            
        elif fmt == "yaml":
            # YAML export
            import yaml
            content = yaml.dump(topology_data, default_flow_style=False)
            filename = f"{topology_data['name'].replace(' ', '_').lower()}.yaml"
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported export format: {export_request.format}"
            )

        # Publish event
        publish_event("exported", {
            "topology_id": export_request.topology_id,
            "format": fmt
        })

        return ExportResponse(
            format=fmt,
            topology_id=export_request.topology_id,
            content=content,
            filename=filename,
            timestamp=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/export/{topology_id}/{format}")
async def export_topology_direct(topology_id: str, format: str):
    """
    Direct export endpoint - returns file for download
    """
    try:
        export_request = ExportFormat(
            format=format,
            topology_id=topology_id,
            options={}
        )

        result = await export_topology(export_request)

        # Determine content type
        fmt = (format or "").lower().strip()
        if fmt in {"mininet_wifi", "mininetwifi", "wifi"}:
            fmt = "mininet-wifi"
        if fmt in {"container-net"}:
            fmt = "containernet"

        content_type = "text/plain"
        if fmt in {"mininet", "mininet-wifi", "containernet"}:
            content_type = "text/x-python"
        elif fmt == "json":
            content_type = "application/json"
        elif fmt == "graphml":
            content_type = "application/xml"
        elif fmt == "yaml":
            content_type = "application/x-yaml"

        return Response(
            content=result.content,
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{result.filename}"'
            }
        )

    except Exception as e:
        logger.error(f"Error in direct export: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/formats")
async def list_formats():
    """List supported export/import formats"""
    return {
        "export_formats": [
            {
                "name": "mininet",
                "description": "Mininet Python script (.py)",
                "extensions": [".py"]
            },
            {
                "name": "mininet-wifi",
                "description": "Mininet-WiFi Python script (.py)",
                "extensions": [".py"]
            },
            {
                "name": "containernet",
                "description": "Containernet Python script (.py)",
                "extensions": [".py"]
            },
            {
                "name": "graphml",
                "description": "GraphML XML format (.graphml)",
                "extensions": [".graphml", ".xml"]
            },
            {
                "name": "json",
                "description": "JSON format (.json)",
                "extensions": [".json"]
            },
            {
                "name": "yaml",
                "description": "YAML format (.yaml, .yml)",
                "extensions": [".yaml", ".yml"]
            }
        ],
        "import_formats": [
            {
                "name": "json",
                "description": "JSON topology format",
                "extensions": [".json"]
            },
            {
                "name": "graphml",
                "description": "GraphML topology format",
                "extensions": [".graphml", ".xml"]
            }
        ]
    }


@app.post("/api/import")
async def import_topology(content: str, format: str):
    """
    Import topology from external format
    
    Supports:
    - JSON
    - GraphML
    """
    try:
        logger.info(f"Importing topology from {format} format")

        topology_data = None

        if format.lower() == "json":
            topology_data = json.loads(content)
            
        elif format.lower() == "graphml":
            # Parse GraphML (simplified)
            # In production, use proper XML parser
            topology_data = {
                "name": "Imported from GraphML",
                "nodes": [],
                "links": []
            }
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported import format: {format}"
            )

        # Save to database via Topology Service
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "http://topology-service:8001/api/topologies/import",
                    json=topology_data
                )
                if response.status_code in [200, 201]:
                    topology_data = response.json()
            except httpx.HTTPError as e:
                logger.warning(f"Failed to save topology to database: {e}")

        # Publish event
        publish_event("imported", {
            "format": format,
            "node_count": len(topology_data.get("nodes", []))
        })

        return {
            "success": True,
            "format": format,
            "topology": topology_data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing topology: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
