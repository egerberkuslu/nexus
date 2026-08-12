"""
Device Manager Service (Port 8004)
Handles runtime device operations - add, remove, update devices in running emulation
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging
import asyncio
import grpc
from datetime import datetime
import shlex
import re
import uuid

import httpx

# Import shared components
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))

from shared.messaging.rabbitmq import RabbitMQPublisher
from shared.utils.consul_client import ConsulClient
from shared.database.postgres import SessionLocal, init_db
from shared.models.runtime import RuntimeDevice

# gRPC stubs (generated during the container build from proto/emulation.proto)
try:
    import emulation_pb2  # type: ignore
    import emulation_pb2_grpc  # type: ignore
except Exception:
    emulation_pb2 = None  # type: ignore
    emulation_pb2_grpc = None  # type: ignore

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Caduceus-Flux Device Manager Service",
    description="Runtime device operations for network emulation",
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

# Configuration
GRPC_HOST = os.getenv("EMULATION_CONTAINER_HOST", "emulation-container")
GRPC_PORT = int(os.getenv("EMULATION_CONTAINER_PORT", "50051"))
SERVICE_PORT = 8004
ORCHESTRATOR_URL = (os.getenv("ORCHESTRATOR_URL", "http://orchestrator-service:8002") or "").rstrip("/")
DEVICE_MANAGER_HTTP_TIMEOUT_SECONDS = float(os.getenv("DEVICE_MANAGER_HTTP_TIMEOUT_SECONDS", "45"))
# Position updates are latency sensitive (streamed at ~10 Hz), so they get a short timeout.
DEVICE_MANAGER_GRPC_TIMEOUT_SECONDS = float(os.getenv("DEVICE_MANAGER_GRPC_TIMEOUT_SECONDS", "5"))

# In-memory device registry
device_registry: Dict[str, Dict] = {}


async def _resolve_running_topology_id(client: httpx.AsyncClient) -> Optional[str]:
    try:
        resp = await client.get(f"{ORCHESTRATOR_URL}/api/emulation/active")
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            for item in (data.get("emulations") or []):
                if isinstance(item, dict) and item.get("status") == "running" and item.get("topology_id"):
                    return str(item["topology_id"])
    except Exception:
        return None
    return None


def _load_registry_from_db() -> None:
    db = SessionLocal()
    try:
        rows = db.query(RuntimeDevice).order_by(RuntimeDevice.updated_at.desc()).limit(2000).all()
        for r in rows:
            if r.status != "active":
                continue
            device_registry[r.name] = {
                "name": r.name,
                "device_type": r.device_type,
                "properties": r.properties or {},
                "status": r.status,
                "created_at": r.created_at or datetime.utcnow(),
                "topology_id": r.topology_id,
                "runtime_name": r.runtime_name,
            }
        logger.info("Loaded %s runtime devices from DB", len(device_registry))
    finally:
        db.close()


# Pydantic models
class DeviceBase(BaseModel):
    name: str = Field(..., description="Device name")
    device_type: str = Field(..., description="Device type: host, switch, router, ap, station, container, p4switch")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Device properties")


class HostDevice(DeviceBase):
    device_type: str = "host"
    properties: Dict[str, Any] = Field(
        ...,
        example={
            "ip": "10.0.0.1/24",
            "mac": "00:00:00:00:00:01",
            "defaultRoute": "via 10.0.0.254"
        }
    )


class SwitchDevice(DeviceBase):
    device_type: str = "switch"
    properties: Dict[str, Any] = Field(
        ...,
        example={
            "dpid": "0000000000000001",
            "openflow_version": "1.3",
            "switch_type": "ovs"
        }
    )


class RouterDevice(DeviceBase):
    device_type: str = "router"
    properties: Dict[str, Any] = Field(
        ...,
        example={
            "router_id": "1.1.1.1",
            "protocols": ["ospf", "bgp"],
            "interfaces": [
                {"name": "eth0", "ip": "10.0.0.1/24"},
                {"name": "eth1", "ip": "10.0.1.1/24"}
            ]
        }
    )


class AccessPointDevice(DeviceBase):
    device_type: str = "ap"
    properties: Dict[str, Any] = Field(
        ...,
        example={
            "ssid": "MyNetwork",
            "mode": "g",
            "channel": "1",
            "security": "wpa2",
            "password": "password123"
        }
    )


class DeviceUpdate(BaseModel):
    properties: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


class DevicePosition(BaseModel):
    x: float
    y: float
    z: float


class DeviceResponse(BaseModel):
    name: str
    device_type: str
    properties: Dict[str, Any]
    status: str
    created_at: datetime
    topology_id: Optional[str] = None


class LinkConfig(BaseModel):
    source_device: str
    target_device: str
    source_port: Optional[int] = None
    target_port: Optional[int] = None
    bandwidth: Optional[int] = None  # Mbps
    delay: Optional[int] = None  # ms
    loss: Optional[float] = None  # percentage
    jitter: Optional[int] = None  # ms


# Helper functions
def _emulation_grpc_target(topology_id: Optional[str] = None) -> str:
    """Resolve the gRPC endpoint of the emulation container serving a topology.

    Each running topology gets its own container named `caduceus-emu-<id[:8]>`
    (same convention as the monitoring and metrics services); the configured
    EMULATION_CONTAINER_HOST is only the single-topology fallback.
    """
    if topology_id:
        return f"caduceus-emu-{str(topology_id)[:8]}:{GRPC_PORT}"
    return f"{GRPC_HOST}:{GRPC_PORT}"


async def get_grpc_channel(topology_id: Optional[str] = None):
    """Get gRPC channel to emulation container"""
    try:
        channel = grpc.aio.insecure_channel(_emulation_grpc_target(topology_id))
        return channel
    except Exception as e:
        logger.error(f"Failed to create gRPC channel: {e}")
        raise HTTPException(status_code=503, detail="Emulation container unavailable")


def publish_event(event_type: str, data: Dict):
    """Publish device event to message broker"""
    try:
        rabbitmq_publisher.publish(
            exchange="caduceus",
            routing_key=f"device.{event_type}",
            message=data
        )
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")


def _split_config_list(value: Any) -> List[str]:
    """Split string or list representations into normalized list of strings."""
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [entry.strip() for entry in re.split(r'[\n,;]+', value) if entry.strip()]
    return []


async def _orchestrator_execute(device_name: str, command: str) -> Dict[str, Any]:
    device = device_registry.get(device_name) or {}
    topology_id = device.get("topology_id")
    if not topology_id:
        raise RuntimeError("Device topology_id is unknown")
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{ORCHESTRATOR_URL}/api/emulation/execute",
            json={"device": device_name, "command": command, "topology_id": topology_id},
        )
        resp.raise_for_status()
        return resp.json()


async def _execute_commands(device_name: str, commands: List[str]):
    """Execute a list of shell commands on the device, logging failures."""
    for command in commands:
        if not command:
            continue
        try:
            result = await _orchestrator_execute(device_name, command)
            if (result.get("exit_code") or 0) != 0:
                logger.warning(
                    "Command failed on %s: %s (stderr: %s)",
                    device_name,
                    command,
                    result.get("stderr", ""),
                )
        except Exception as exc:
            logger.warning("Command failed on %s: %s (error: %s)", device_name, command, exc)


async def _apply_host_runtime_config(device_name: str, properties: Dict[str, Any]):
    """Apply host runtime configuration using shell commands."""
    interface = properties.get('primary_interface') or f"{device_name}-eth0"
    commands: List[str] = []

    if 'ip' in properties and properties['ip']:
        commands.append(f'ip addr flush dev {interface}')
        commands.append(f'ip addr add {properties["ip"]} dev {interface}')

    if 'ip6' in properties and properties['ip6']:
        commands.append(f'ip -6 addr flush dev {interface}')
        commands.append(f'ip -6 addr add {properties["ip6"]} dev {interface}')

    if 'mac' in properties and properties['mac']:
        commands.append(f'ip link set dev {interface} address {properties["mac"]}')

    if 'mtu' in properties and properties['mtu']:
        commands.append(f'ip link set dev {interface} mtu {properties["mtu"]}')

    if 'default_route' in properties or 'defaultRoute' in properties:
        cmds = ['ip route del default || true']
        default_route = properties.get('default_route') or properties.get('defaultRoute')
        if default_route:
            route_spec = str(default_route).strip()
            if route_spec:
                if ' ' in route_spec:
                    cmds.append(f'ip route add default {route_spec}')
                else:
                    cmds.append(f'ip route add default via {route_spec}')
        commands.extend(cmds)

    if 'static_routes' in properties:
        for route in _split_config_list(properties.get('static_routes')):
            commands.append(f'ip route add {route} || true')

    if 'dns_servers' in properties:
        dns_entries = _split_config_list(properties.get('dns_servers'))
        commands.append('cat /dev/null > /etc/resolv.conf')
        for entry in dns_entries:
            nameserver_entry = f"nameserver {entry}"
            commands.append(f'echo {shlex.quote(nameserver_entry)} >> /etc/resolv.conf')

    if 'startup_commands' in properties:
        startup_commands = properties.get('startup_commands')
        if isinstance(startup_commands, list):
            commands.extend(str(cmd).strip() for cmd in startup_commands if str(cmd).strip())
        else:
            commands.extend(
                cmd.strip() for cmd in str(startup_commands).splitlines() if cmd.strip()
            )

    await _execute_commands(device_name, commands)


async def _apply_switch_runtime_config(device_name: str, properties: Dict[str, Any]):
    """Apply controller/OpenFlow settings to a running switch."""
    commands: List[str] = []

    controller_value = properties.get('controller')
    controller_ip = properties.get('controller_ip')
    controller_port = properties.get('controller_port')

    controller_endpoint = None
    if controller_value:
        controller_value = str(controller_value).strip()
        if controller_value:
            controller_endpoint = controller_value
    elif controller_ip:
        controller_endpoint = f"{controller_ip}:{controller_port or 6653}"

    if controller_endpoint:
        parts = controller_endpoint.split(':')
        ctrl_ip = parts[0]
        ctrl_port = int(parts[1]) if len(parts) > 1 else 6653
        commands.append(f'ovs-vsctl set-controller {device_name} tcp:{ctrl_ip}:{ctrl_port}')

    if 'openflow_version' in properties and properties['openflow_version']:
        version_str = str(properties['openflow_version']).strip()
        if version_str:
            protocol = version_str if version_str.lower().startswith('openflow') else f"OpenFlow{version_str.replace('.', '')}"
            commands.append(f'ovs-vsctl set bridge {device_name} protocols={protocol}')

    await _execute_commands(device_name, commands)


async def _apply_runtime_configuration(device: Dict[str, Any], update: DeviceUpdate):
    """Apply runtime configuration changes based on device type."""
    if not update.properties:
        return

    device_type = device.get("device_type")
    properties = device.get("properties", {})
    merged_properties = {**properties, **update.properties}

    if device_type == 'host':
        await _apply_host_runtime_config(device["name"], merged_properties)
    elif device_type == 'router':
        await _apply_host_runtime_config(device["name"], merged_properties)
    elif device_type == 'switch':
        await _apply_switch_runtime_config(device["name"], merged_properties)


# API endpoints

@app.on_event("startup")
async def startup_event():
    """Service startup"""
    logger.info("Starting Device Manager Service...")
    try:
        init_db()
        _load_registry_from_db()
        consul_client.register_service("device-manager", SERVICE_PORT)
        rabbitmq_publisher.connect()
        logger.info("Device Manager Service started successfully")
    except Exception as e:
        logger.error(f"Startup error: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Service shutdown"""
    logger.info("Shutting down Device Manager Service...")
    consul_client.deregister_service("device-manager")
    rabbitmq_publisher.disconnect()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "device-manager",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/devices", response_model=DeviceResponse, status_code=201)
async def add_device(
    device: DeviceBase,
    topology_id: Optional[str] = None,
    background_tasks: BackgroundTasks = None
):
    """
    Add a device to running emulation
    Supports: host, switch, router, ap, station, container, p4switch
    """
    try:
        # Validate device doesn't already exist
        if device.name in device_registry:
            raise HTTPException(status_code=409, detail=f"Device {device.name} already exists")

        resolved_topology_id = topology_id
        async with httpx.AsyncClient(timeout=httpx.Timeout(DEVICE_MANAGER_HTTP_TIMEOUT_SECONDS)) as client:
            if not resolved_topology_id:
                resolved_topology_id = await _resolve_running_topology_id(client)
            if not resolved_topology_id:
                raise HTTPException(status_code=400, detail="topology_id is required (or there must be a running emulation)")

            logger.info(f"Adding device: {device.name} (type: {device.device_type}) to topology {resolved_topology_id}")
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/api/emulation/devices/add",
                json={
                    "topology_id": resolved_topology_id,
                    "name": device.name,
                    "device_type": device.device_type,
                    "properties": device.properties or {},
                    "node_id": (device.properties or {}).get("node_id") or None,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            runtime_name = result.get("runtime_name")

        # Store device in registry
        device_data = {
            "name": device.name,
            "device_type": device.device_type,
            "properties": device.properties,
            "status": "active",
            "created_at": datetime.utcnow(),
            "topology_id": resolved_topology_id,
            "runtime_name": runtime_name,
        }
        device_registry[device.name] = device_data

        # Persist runtime state
        db = SessionLocal()
        try:
            row = RuntimeDevice(
                id=uuid.uuid4().hex,
                topology_id=resolved_topology_id,
                ns_instance_id=(device.properties or {}).get("ns_instance_id"),
                name=device.name,
                runtime_name=runtime_name,
                device_type=device.device_type,
                status="active",
                properties=device.properties or {},
                created_at=device_data["created_at"],
                updated_at=device_data["created_at"],
                last_seen_at=datetime.utcnow(),
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

        # Publish event
        publish_event("added", device_data)

        return DeviceResponse(**device_data)

    except HTTPException:
        raise
    except Exception as e:
        detail = str(e) or repr(e)
        logger.error(f"Error adding device: {detail}")
        raise HTTPException(status_code=500, detail=detail)


@app.get("/api/devices", response_model=List[DeviceResponse])
async def list_devices(
    device_type: Optional[str] = None,
    topology_id: Optional[str] = None
):
    """List all devices"""
    devices = list(device_registry.values())

    # Filter by device type
    if device_type:
        devices = [d for d in devices if d["device_type"] == device_type]

    # Filter by topology
    if topology_id:
        devices = [d for d in devices if d.get("topology_id") == topology_id]

    return [DeviceResponse(**d) for d in devices]


@app.get("/api/devices/{device_name}", response_model=DeviceResponse)
async def get_device(device_name: str):
    """Get device details"""
    if device_name not in device_registry:
        raise HTTPException(status_code=404, detail=f"Device {device_name} not found")

    return DeviceResponse(**device_registry[device_name])


@app.put("/api/devices/{device_name}", response_model=DeviceResponse)
async def update_device(device_name: str, update: DeviceUpdate):
    """Update device properties"""
    if device_name not in device_registry:
        raise HTTPException(status_code=404, detail=f"Device {device_name} not found")

    device = device_registry[device_name]

    # Update properties
    if update.properties:
        device["properties"].update(update.properties)

    # Update status
    if update.status:
        device["status"] = update.status

    try:
        await _apply_runtime_configuration(device, update)
    except Exception as exc:
        logger.warning(f"Runtime configuration update failed for {device_name}: {exc}")

    # Persist updates (best-effort)
    try:
        topology_id = device.get("topology_id")
        db = SessionLocal()
        try:
            if topology_id:
                db.query(RuntimeDevice).filter(RuntimeDevice.name == device_name, RuntimeDevice.topology_id == topology_id).update(
                    {
                        "properties": device.get("properties") or {},
                        "status": device.get("status") or "active",
                        "updated_at": datetime.utcnow(),
                        "last_seen_at": datetime.utcnow(),
                    }
                )
                db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.warning("Failed to persist runtime device update for %s: %s", device_name, exc)

    # Publish event
    publish_event("updated", device)

    return DeviceResponse(**device)


@app.put("/api/devices/{device_name}/position")
async def set_device_position(device_name: str, position: DevicePosition):
    """Move a station or access point in the running emulation.

    Built for an external physics service (Gazebo) streaming float 3D positions
    at ~10 Hz, so the coordinates are forwarded unrounded and no RabbitMQ event
    is published per update.
    """
    if device_name not in device_registry:
        raise HTTPException(status_code=404, detail=f"Device {device_name} not found")

    if not (emulation_pb2 and emulation_pb2_grpc):
        raise HTTPException(status_code=503, detail="gRPC stubs not available in device manager service")

    device = device_registry[device_name]
    topology_id = device.get("topology_id")

    channel = await get_grpc_channel(topology_id)
    try:
        stub = emulation_pb2_grpc.EmulationServiceStub(channel)
        response = await stub.SetPosition(
            emulation_pb2.SetPositionRequest(
                device_name=device_name,
                x=position.x,
                y=position.y,
                z=position.z,
            ),
            timeout=DEVICE_MANAGER_GRPC_TIMEOUT_SECONDS,
        )
    except grpc.aio.AioRpcError as exc:
        logger.error("SetPosition gRPC call failed for %s: %s", device_name, exc)
        raise HTTPException(status_code=503, detail=f"Emulation container unavailable: {exc.details()}")
    except Exception as exc:
        logger.error("SetPosition failed for %s: %s", device_name, exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        await channel.close()

    if not response.success:
        raise HTTPException(status_code=400, detail=response.message)

    # Keep the in-memory registry in sync so GET /api/devices reports the move.
    device.setdefault("properties", {})["position"] = f"{position.x},{position.y},{position.z}"

    return {
        "device": device_name,
        "x": position.x,
        "y": position.y,
        "z": position.z,
        "message": response.message,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.delete("/api/devices/{device_name}", status_code=204)
async def remove_device(device_name: str):
    """Remove device from running emulation"""
    if device_name not in device_registry:
        raise HTTPException(status_code=404, detail=f"Device {device_name} not found")

    device = device_registry.get(device_name) or {}
    topology_id = device.get("topology_id")
    if not topology_id:
        raise HTTPException(status_code=400, detail="Device topology_id is unknown; cannot remove")

    async with httpx.AsyncClient(timeout=httpx.Timeout(DEVICE_MANAGER_HTTP_TIMEOUT_SECONDS)) as client:
        logger.info(f"Removing device: {device_name} from topology {topology_id}")
        resp = await client.delete(
            f"{ORCHESTRATOR_URL}/api/emulation/devices/{device_name}",
            params={"topology_id": topology_id},
        )
        resp.raise_for_status()

    device = device_registry.pop(device_name)

    db = SessionLocal()
    try:
        db.query(RuntimeDevice).filter(RuntimeDevice.name == device_name, RuntimeDevice.topology_id == topology_id).update(
            {"status": "deleted", "updated_at": datetime.utcnow()}
        )
        db.commit()
    finally:
        db.close()

    # Publish event
    publish_event("removed", device)

    return None


@app.post("/api/devices/{device_name}/execute")
async def execute_command(device_name: str, command: str):
    """Execute command on device"""
    if device_name not in device_registry:
        raise HTTPException(status_code=404, detail=f"Device {device_name} not found")

    device = device_registry.get(device_name) or {}
    topology_id = device.get("topology_id")
    if not topology_id:
        raise HTTPException(status_code=400, detail="Device topology_id is unknown; cannot execute")

    async with httpx.AsyncClient(timeout=60.0) as client:
        logger.info(f"Executing command on {device_name} (topology {topology_id}): {command}")
        resp = await client.post(
            f"{ORCHESTRATOR_URL}/api/emulation/execute",
            json={"device": device_name, "command": command, "topology_id": topology_id},
        )
        resp.raise_for_status()
        result = resp.json()

    return {
        "device": device_name,
        "command": command,
        "output": (result.get("stdout", "") or "") + (result.get("stderr", "") or ""),
        "exit_code": result.get("exit_code", 0),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/links", status_code=201)
async def add_link(link: LinkConfig):
    """Add link between devices"""
    # Validate devices exist
    if link.source_device not in device_registry:
        raise HTTPException(status_code=404, detail=f"Source device {link.source_device} not found")
    if link.target_device not in device_registry:
        raise HTTPException(status_code=404, detail=f"Target device {link.target_device} not found")

    topology_id = device_registry.get(link.source_device, {}).get("topology_id") or device_registry.get(link.target_device, {}).get("topology_id")
    if not topology_id:
        raise HTTPException(status_code=400, detail="topology_id is unknown for these devices; cannot add link")

    async with httpx.AsyncClient(timeout=httpx.Timeout(DEVICE_MANAGER_HTTP_TIMEOUT_SECONDS)) as client:
        logger.info(f"Adding link: {link.source_device} <-> {link.target_device} (topology {topology_id})")
        resp = await client.post(
            f"{ORCHESTRATOR_URL}/api/emulation/links/add",
            json={
                "topology_id": topology_id,
                "node1": link.source_device,
                "node2": link.target_device,
                "bandwidth": int(link.bandwidth or 0),
                "delay": int(link.delay or 0),
                "loss": float(link.loss or 0.0),
                "max_queue_size": 1000,
            },
        )
        resp.raise_for_status()

    link_data = {
        "source": link.source_device,
        "target": link.target_device,
        "properties": {
            "bandwidth": link.bandwidth,
            "delay": link.delay,
            "loss": link.loss,
            "jitter": link.jitter
        },
        "status": "active",
        "created_at": datetime.utcnow().isoformat()
    }

    # Publish event
    publish_event("link.added", link_data)

    return link_data


@app.get("/api/devices/{device_name}/interfaces")
async def get_device_interfaces(device_name: str):
    """Get device network interfaces"""
    if device_name not in device_registry:
        raise HTTPException(status_code=404, detail=f"Device {device_name} not found")

    device = device_registry.get(device_name) or {}
    topology_id = device.get("topology_id")
    if not topology_id:
        raise HTTPException(status_code=400, detail="Device topology_id is unknown")

    async with httpx.AsyncClient(timeout=httpx.Timeout(DEVICE_MANAGER_HTTP_TIMEOUT_SECONDS)) as client:
        resp = await client.get(f"{ORCHESTRATOR_URL}/api/emulation/devices", params={"topology_id": topology_id})
        resp.raise_for_status()
        data = resp.json()
        for d in (data.get("devices") or []):
            if d.get("name") == device_name or d.get("runtime_name") == device.get("runtime_name"):
                return {"device": device_name, "interfaces": d.get("interfaces") or []}
    return {"device": device_name, "interfaces": []}


@app.get("/api/devices/{device_name}/stats")
async def get_device_stats(device_name: str):
    """Get device statistics"""
    if device_name not in device_registry:
        raise HTTPException(status_code=404, detail=f"Device {device_name} not found")

    raise HTTPException(status_code=501, detail="Device stats not implemented (use monitoring service)")


@app.post("/api/devices/batch", status_code=201)
async def add_devices_batch(devices: List[DeviceBase]):
    """Add multiple devices at once"""
    added_devices = []
    errors = []

    for device in devices:
        try:
            if device.name in device_registry:
                errors.append({"device": device.name, "error": "Already exists"})
                continue

            device_data = {
                "name": device.name,
                "device_type": device.device_type,
                "properties": device.properties,
                "status": "active",
                "created_at": datetime.utcnow(),
                "topology_id": None
            }
            device_registry[device.name] = device_data
            added_devices.append(device_data)

            # Publish event
            publish_event("added", device_data)

        except Exception as e:
            errors.append({"device": device.name, "error": str(e)})

    return {
        "added": len(added_devices),
        "errors": len(errors),
        "devices": added_devices,
        "error_details": errors
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=SERVICE_PORT)
