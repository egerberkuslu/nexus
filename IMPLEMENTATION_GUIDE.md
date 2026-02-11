# Caduceus-Flux Implementation Guide

## Project Overview

Caduceus-Flux is a comprehensive microservices-based network emulation platform that provides runtime protocol switching, multi-protocol support, and complete network lifecycle management.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                          │
│              Topology Designer, WebShell, Monitoring             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Nginx API Gateway                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    MCP Server (Port 8012)                        │
│              Unified API & Service Orchestration                 │
└─────┬───────────────────────────────────────────────────────────┘
      │
      ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Microservices Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  Topology (8001)    │  Orchestrator (8002)  │  Protocol (8003)  │
│  Device (8004)      │  Controller (8005)    │  Snapshot (8006)  │
│  WebShell (8007)    │  Export/Import (8008) │  Generator (8009) │
│  P4 Manager (8010)  │  Monitoring (8011)    │  MCP Server (8012)│
└────────────┬────────────────────────────────────────────────────┘
             │
             ↓ (gRPC)
┌─────────────────────────────────────────────────────────────────┐
│              Unified Emulation Container (Port 50051)            │
├─────────────────────────────────────────────────────────────────┤
│  Mininet + Mininet-WiFi + Containernet + OVS + FRR + BIRD + P4  │
│                        gRPC Agent Server                         │
└─────────────────────────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Message Broker (RabbitMQ)                     │
│              Inter-Service Communication & Events                │
└─────────────────────────────────────────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                  │
├─────────────────────────────────────────────────────────────────┤
│  PostgreSQL  │  MongoDB  │  Redis  │  InfluxDB  │  Consul       │
└─────────────────────────────────────────────────────────────────┘
```

## Complete File Structure

```
caduceus-flux/
├── README.md                          # ✅ Created
├── .env.example                       # ✅ Created
├── docker-compose.yml                 # ✅ Created
├── IMPLEMENTATION_GUIDE.md            # ✅ Current file
│
├── backend/
│   ├── proto/
│   │   └── emulation.proto            # ✅ gRPC protocol definition
│   │
│   ├── shared/
│   │   ├── models/
│   │   │   └── topology.py            # ✅ SQLAlchemy models
│   │   ├── schemas/
│   │   │   └── topology_schema.py     # ✅ Pydantic schemas
│   │   ├── database/
│   │   │   ├── postgres.py            # ✅ PostgreSQL connection
│   │   │   ├── mongodb.py             # ⚠️ TODO
│   │   │   └── redis.py               # ⚠️ TODO
│   │   ├── messaging/
│   │   │   ├── rabbitmq.py            # ✅ RabbitMQ client
│   │   │   └── kafka.py               # ⚠️ TODO (alternative)
│   │   ├── utils/
│   │   │   ├── consul_client.py       # ✅ Service discovery
│   │   │   ├── logger.py              # ⚠️ TODO
│   │   │   └── grpc_client.py         # ⚠️ TODO
│   │   └── plugins/
│   │       ├── base.py                # ⚠️ TODO - Plugin base classes
│   │       ├── protocol_plugin.py     # ⚠️ TODO
│   │       └── device_plugin.py       # ⚠️ TODO
│   │
│   ├── services/
│   │   ├── topology/                  # ✅ Port 8001 - CRUD operations
│   │   │   ├── main.py                # ✅ Complete implementation
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   ├── orchestrator/              # ⚠️ Port 8002 - Emulation lifecycle
│   │   │   ├── main.py                # ⚠️ TODO
│   │   │   ├── grpc_client.py         # ⚠️ TODO
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   ├── protocol_manager/          # ⚠️ Port 8003 - Protocol switching
│   │   │   ├── main.py                # ⚠️ TODO
│   │   │   ├── plugins/               # ⚠️ TODO
│   │   │   │   ├── ospf.py
│   │   │   │   ├── bgp.py
│   │   │   │   ├── rip.py
│   │   │   │   ├── openflow.py
│   │   │   │   └── wireless.py
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   ├── device_manager/            # ⚠️ Port 8004 - Runtime device ops
│   │   │   ├── main.py                # ⚠️ TODO
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   ├── controller_manager/        # ⚠️ Port 8005 - SDN controllers
│   │   │   ├── main.py                # ⚠️ TODO
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   ├── snapshot/                  # ⚠️ Port 8006 - State management
│   │   │   ├── main.py                # ⚠️ TODO
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   ├── webshell/                  # ⚠️ Port 8007 - Web terminal
│   │   │   ├── main.py                # ⚠️ TODO
│   │   │   ├── websocket_handler.py   # ⚠️ TODO
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   ├── export_import/             # ⚠️ Port 8008 - Script generation
│   │   │   ├── main.py                # ⚠️ TODO
│   │   │   ├── mininet_exporter.py    # ⚠️ TODO
│   │   │   ├── graphml_exporter.py    # ⚠️ TODO
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   ├── topology_generator/        # ⚠️ Port 8009 - Auto-generation
│   │   │   ├── main.py                # ⚠️ TODO
│   │   │   ├── generators/            # ⚠️ TODO
│   │   │   │   ├── tree.py
│   │   │   │   ├── mesh.py
│   │   │   │   ├── fat_tree.py
│   │   │   │   └── custom.py
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   ├── p4_manager/                # ⚠️ Port 8010 - P4 compilation
│   │   │   ├── main.py                # ⚠️ TODO
│   │   │   ├── compiler.py            # ⚠️ TODO
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   ├── monitoring/                # ⚠️ Port 8011 - Metrics collection
│   │   │   ├── main.py                # ⚠️ TODO
│   │   │   ├── collectors/            # ⚠️ TODO
│   │   │   │   ├── prometheus.py
│   │   │   │   └── influxdb.py
│   │   │   ├── Dockerfile             # ⚠️ TODO
│   │   │   └── requirements.txt       # ⚠️ TODO
│   │   │
│   │   └── mcp_server/                # ⚠️ Port 8012 - Unified API
│   │       ├── main.py                # ⚠️ TODO
│   │       ├── aggregator.py          # ⚠️ TODO
│   │       ├── Dockerfile             # ⚠️ TODO
│   │       └── requirements.txt       # ⚠️ TODO
│   │
│   └── migrations/                    # ⚠️ TODO - Alembic migrations
│       ├── alembic.ini
│       └── versions/
│
├── emulation-container/
│   ├── Dockerfile                     # ✅ Created
│   ├── grpc_agent/
│   │   ├── server.py                  # ✅ gRPC server implementation
│   │   ├── emulation_manager.py       # ✅ Core emulation manager
│   │   ├── device_handler.py          # ⚠️ TODO
│   │   ├── link_handler.py            # ⚠️ TODO
│   │   ├── protocol_handler.py        # ⚠️ TODO
│   │   ├── state_handler.py           # ⚠️ TODO
│   │   └── monitoring_handler.py      # ⚠️ TODO
│   ├── protocols/                     # ⚠️ TODO - Protocol implementations
│   │   ├── frr_manager.py
│   │   ├── bird_manager.py
│   │   ├── ovs_manager.py
│   │   ├── wireless_manager.py
│   │   └── p4_manager.py
│   └── scripts/
│       └── entrypoint.sh              # ✅ Container startup script
│
├── controllers/                       # SDN controller containers
│   ├── osken/
│   │   ├── Dockerfile                 # ⚠️ TODO
│   │   └── simple_switch.py           # ⚠️ TODO
│   ├── ryu/
│   │   ├── Dockerfile                 # ⚠️ TODO
│   │   └── simple_switch.py           # ⚠️ TODO
│   ├── opendaylight/
│   │   └── README.md                  # ⚠️ TODO
│   └── onos/
│       └── README.md                  # ⚠️ TODO
│
├── frontend/
│   ├── package.json                   # ⚠️ TODO
│   ├── tsconfig.json                  # ⚠️ TODO
│   ├── Dockerfile                     # ⚠️ TODO
│   ├── public/
│   │   └── index.html                 # ⚠️ TODO
│   └── src/
│       ├── App.tsx                    # ⚠️ TODO
│       ├── components/
│       │   ├── TopologyDesigner.tsx   # ⚠️ TODO - React Flow integration
│       │   ├── WebShell.tsx           # ⚠️ TODO - xterm.js integration
│       │   ├── DevicePanel.tsx        # ⚠️ TODO
│       │   ├── LinkEditor.tsx         # ⚠️ TODO
│       │   └── MonitoringDashboard.tsx # ⚠️ TODO
│       ├── pages/
│       │   ├── Home.tsx               # ⚠️ TODO
│       │   ├── ProjectList.tsx        # ⚠️ TODO
│       │   ├── TopologyEditor.tsx     # ⚠️ TODO
│       │   └── Monitoring.tsx         # ⚠️ TODO
│       ├── services/
│       │   ├── api.ts                 # ⚠️ TODO - API client
│       │   └── websocket.ts           # ⚠️ TODO - WebSocket client
│       ├── hooks/
│       │   ├── useTopology.ts         # ⚠️ TODO
│       │   └── useWebShell.ts         # ⚠️ TODO
│       └── types/
│           └── topology.ts            # ⚠️ TODO
│
├── infrastructure/
│   ├── nginx/
│   │   ├── nginx.conf                 # ⚠️ TODO
│   │   └── conf.d/
│   │       └── default.conf           # ⚠️ TODO
│   ├── prometheus/
│   │   └── prometheus.yml             # ⚠️ TODO
│   ├── grafana/
│   │   ├── dashboards/                # ⚠️ TODO
│   │   │   ├── topology-overview.json
│   │   │   ├── device-metrics.json
│   │   │   └── protocol-stats.json
│   │   └── datasources/               # ⚠️ TODO
│   │       └── datasources.yml
│   └── databases/
│       └── postgres/
│           └── init.sql               # ⚠️ TODO
│
├── examples/                          # Example topologies
│   ├── simple-topology.json           # ⚠️ TODO
│   ├── fat-tree.json                  # ⚠️ TODO
│   ├── wireless-mesh.json             # ⚠️ TODO
│   └── p4-switch.json                 # ⚠️ TODO
│
├── tests/
│   ├── unit/                          # ⚠️ TODO
│   ├── integration/                   # ⚠️ TODO
│   └── e2e/                           # ⚠️ TODO
│
└── docs/
    ├── API.md                         # ⚠️ TODO
    ├── PROTOCOLS.md                   # ⚠️ TODO
    ├── PLUGINS.md                     # ⚠️ TODO
    └── DEPLOYMENT.md                  # ⚠️ TODO
```

## Implementation Status Legend

- ✅ **Created**: File/component has been implemented
- ⚠️ **TODO**: File/component needs to be implemented
- 🔄 **In Progress**: File/component is being worked on

## Quick Start Guide

### 1. Prerequisites

```bash
# Install Docker and Docker Compose
docker --version  # 24.0+
docker-compose --version  # 2.20+

# System requirements
# - 16GB RAM minimum
# - 50GB disk space
# - Linux kernel 4.15+ (for network namespaces)
```

### 2. Setup

```bash
# Clone and configure
cd caduceus-flux
cp .env.example .env
# Edit .env with your settings

# Build and start all services
docker-compose up -d

# Check service health
docker-compose ps
```

### 3. Access Points

- **Frontend UI**: http://localhost:3000
- **MCP Server API**: http://localhost:8012/docs
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090
- **RabbitMQ Management**: http://localhost:15672 (caduceus/changeme)

## Service Implementation Templates

### Microservice Template Structure

Each microservice follows this pattern:

```python
# backend/services/{service_name}/main.py

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import logging

from shared.messaging.rabbitmq import RabbitMQPublisher, RabbitMQConsumer
from shared.utils.consul_client import ConsulClient

logger = logging.getLogger(__name__)

app = FastAPI(
    title=f"Caduceus-Flux {ServiceName} Service",
    description="Service description",
    version="1.0.0"
)

# CORS
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

@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {ServiceName} Service...")
    consul_client.register_service("{service-name}", PORT)
    rabbitmq_publisher.connect()
    logger.info(f"{ServiceName} Service started")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info(f"Shutting down {ServiceName} Service...")
    consul_client.deregister_service("{service-name}")
    rabbitmq_publisher.disconnect()

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "{service-name}"}

# Add endpoints here...

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
```

### Dockerfile Template

```dockerfile
# backend/services/{service_name}/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Copy shared code
COPY shared/ /app/shared/

# Copy service code
COPY services/{service_name}/ /app/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE {PORT}

# Run service
CMD ["python", "main.py"]
```

### Requirements Template

```txt
# backend/services/{service_name}/requirements.txt

fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
alembic==1.12.1
psycopg2-binary==2.9.9
pymongo==4.6.0
redis==5.0.1
pika==1.3.2
python-consul==1.1.0
grpcio==1.59.0
grpcio-tools==1.59.0
pydantic==2.5.0
python-multipart==0.0.6
```

## Key Implementation Details

### 1. Protocol Plugin System

The Protocol Manager Service uses a plugin architecture:

```python
# backend/shared/plugins/protocol_plugin.py

from abc import ABC, abstractmethod
from typing import Dict, Any

class ProtocolPlugin(ABC):
    """Base class for all protocol plugins"""

    name: str
    version: str
    protocol_type: str  # routing, openflow, wireless, etc.

    @abstractmethod
    def configure(self, device: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Configure protocol on device"""
        pass

    @abstractmethod
    def enable(self, device: str) -> bool:
        """Enable protocol"""
        pass

    @abstractmethod
    def disable(self, device: str) -> bool:
        """Disable protocol"""
        pass

    @abstractmethod
    def get_status(self, device: str) -> Dict[str, Any]:
        """Get protocol status"""
        pass

    @abstractmethod
    def switch_from(self, device: str, to_protocol: str, preserve_config: bool) -> bool:
        """Switch to another protocol"""
        pass
```

Example OSPF plugin:

```python
# backend/services/protocol_manager/plugins/ospf.py

from shared.plugins.protocol_plugin import ProtocolPlugin

class OSPFPlugin(ProtocolPlugin):
    name = "ospf"
    version = "2"
    protocol_type = "routing"

    def configure(self, device: str, config: Dict[str, Any]) -> Dict[str, Any]:
        # Generate FRRouting OSPF configuration
        router_id = config.get("router_id")
        area = config.get("area", "0.0.0.0")
        networks = config.get("networks", [])

        ospf_config = f"""
router ospf
  ospf router-id {router_id}
  network {" area ".join([f"{net} area {area}" for net in networks])}
"""
        # Apply via gRPC to emulation container
        # ...
        return {"success": True, "config": ospf_config}

    def enable(self, device: str) -> bool:
        # Enable OSPF daemon
        return True

    def disable(self, device: str) -> bool:
        # Disable OSPF daemon
        return True

    def get_status(self, device: str) -> Dict[str, Any]:
        # Get OSPF neighbors, routes, etc.
        return {"status": "active", "neighbors": []}

    def switch_from(self, device: str, to_protocol: str, preserve_config: bool) -> bool:
        # Gracefully switch to another protocol
        return True
```

### 2. Runtime Protocol Switching

The key feature is hot-swapping protocols without restart:

```python
# Example: Switch from OSPF to BGP

# 1. Capture current routing state
current_routes = capture_routing_table(device)

# 2. Disable OSPF gracefully
ospf_plugin.disable(device)

# 3. Configure BGP with equivalent routes
bgp_config = translate_config(ospf_config, "bgp")
bgp_plugin.configure(device, bgp_config)

# 4. Enable BGP
bgp_plugin.enable(device)

# 5. Verify routing continuity
verify_routes(device, current_routes)
```

### 3. WebShell Implementation

WebShell service provides terminal access via WebSocket + xterm.js:

```python
# backend/services/webshell/websocket_handler.py

from fastapi import WebSocket
import asyncio
import pty
import os
import struct
import fcntl
import termios

class WebShellHandler:
    async def connect(self, websocket: WebSocket, device: str):
        await websocket.accept()

        # Create PTY for device
        master, slave = pty.openpty()

        # Execute command in device namespace
        cmd = f"docker exec -it {device} /bin/bash"
        pid = os.fork()

        if pid == 0:
            # Child process
            os.setsid()
            os.dup2(slave, 0)
            os.dup2(slave, 1)
            os.dup2(slave, 2)
            os.execvp("/bin/bash", ["/bin/bash"])

        # Parent process - relay between WebSocket and PTY
        try:
            while True:
                # Read from WebSocket
                data = await websocket.receive_text()
                os.write(master, data.encode())

                # Read from PTY
                output = os.read(master, 4096)
                await websocket.send_text(output.decode())

        except Exception as e:
            print(f"WebShell error: {e}")
        finally:
            os.close(master)
            os.close(slave)
```

### 4. Snapshot System

Complete state capture including all device configurations:

```python
# backend/services/snapshot/state_capture.py

class StateCaptureService:
    async def capture_complete_state(self, topology_id: str) -> Dict:
        state = {
            "topology_id": topology_id,
            "timestamp": datetime.utcnow(),
            "devices": {},
            "links": {},
            "routing_tables": {},
            "flow_tables": {},
            "arp_tables": {},
            "wireless_associations": {},
            "container_states": {}
        }

        # Get all devices
        devices = await get_devices(topology_id)

        for device in devices:
            # Capture device configuration
            state["devices"][device.name] = {
                "type": device.type,
                "properties": device.properties,
                "interfaces": await get_interfaces(device.name),
                "processes": await get_processes(device.name)
            }

            # Capture routing table
            if device.type == "router":
                state["routing_tables"][device.name] = await get_routing_table(device.name)

            # Capture flow table
            if device.type == "switch":
                state["flow_tables"][device.name] = await get_flow_table(device.name)

            # Capture ARP table
            state["arp_tables"][device.name] = await get_arp_table(device.name)

        # Store in MongoDB
        snapshot_id = await mongodb.snapshots.insert_one(state)

        return snapshot_id
```

### 5. Export to Mininet Python

Export service generates executable Mininet scripts:

```python
# backend/services/export_import/mininet_exporter.py

class MininetExporter:
    def export_topology(self, topology: Topology) -> str:
        """Generate Mininet Python script from topology"""

        script = """#!/usr/bin/env python3
from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSKernelSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel

def topology():
    net = Mininet(controller=RemoteController, switch=OVSKernelSwitch)

    # Add controller
"""

        # Add controllers
        for ctrl in topology.controllers:
            script += f"    c{ctrl.name} = net.addController('{ctrl.name}', controller=RemoteController, ip='{ctrl.ip}', port={ctrl.port})\n"

        script += "\n    # Add hosts\n"

        # Add hosts
        for node in topology.nodes:
            if node.device_type == "host":
                ip = node.properties.get("ip", "")
                script += f"    {node.name} = net.addHost('{node.name}', ip='{ip}')\n"

        script += "\n    # Add switches\n"

        # Add switches
        for node in topology.nodes:
            if node.device_type == "switch":
                script += f"    {node.name} = net.addSwitch('{node.name}')\n"

        script += "\n    # Add links\n"

        # Add links
        for link in topology.links:
            params = []
            if link.bandwidth:
                params.append(f"bw={link.bandwidth}")
            if link.delay:
                params.append(f"delay='{link.delay}ms'")
            if link.loss:
                params.append(f"loss={link.loss}")

            params_str = ", ".join(params)
            script += f"    net.addLink({link.source_node.name}, {link.target_node.name}"
            if params_str:
                script += f", {params_str}"
            script += ")\n"

        script += """
    net.start()
    CLI(net)
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    topology()
"""

        return script
```

## Database Schemas

### PostgreSQL Tables

Already implemented in `backend/shared/models/topology.py`:
- projects
- topologies
- nodes
- links
- controllers
- snapshots
- protocols
- protocol_plugins

### MongoDB Collections

```javascript
// snapshot_states collection
{
  _id: ObjectId,
  snapshot_id: "uuid",
  timestamp: ISODate,
  topology_id: "uuid",
  devices: {
    "h1": {
      type: "host",
      properties: {...},
      interfaces: [...],
      processes: [...]
    }
  },
  routing_tables: {...},
  flow_tables: {...},
  arp_tables: {...}
}
```

### Redis Keys

```
# Session cache
session:{session_id} -> JSON

# Device command queues
device:{device_name}:commands -> LIST

# Pub/Sub channels
emulation:events:{topology_id}
metrics:updates:{device_name}
```

### InfluxDB Measurements

```
# Device metrics
device_metrics,device=h1,topology=topo1 bytes_sent=1000,bytes_received=2000 timestamp

# Link metrics
link_metrics,link=h1-s1,topology=topo1 bandwidth_usage=50.5,packet_loss=0.1 timestamp

# Protocol metrics
protocol_metrics,device=r1,protocol=ospf neighbors=3,routes=10 timestamp
```

## Frontend Components

### Topology Designer (React Flow)

```tsx
// frontend/src/components/TopologyDesigner.tsx

import React, { useCallback } from 'react';
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Background,
  Controls,
  MiniMap,
} from 'reactflow';
import 'reactflow/dist/style.css';

export const TopologyDesigner: React.FC = () => {
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  const onConnect = useCallback(
    (params) => setEdges((eds) => addEdge(params, eds)),
    []
  );

  const addDevice = (type: string) => {
    const newNode: Node = {
      id: `${type}-${Date.now()}`,
      type: 'default',
      position: { x: 100, y: 100 },
      data: { label: type, deviceType: type },
    };
    setNodes((nds) => [...nds, newNode]);
  };

  return (
    <div style={{ height: '100vh' }}>
      <div className="toolbar">
        <button onClick={() => addDevice('host')}>Add Host</button>
        <button onClick={() => addDevice('switch')}>Add Switch</button>
        <button onClick={() => addDevice('router')}>Add Router</button>
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onConnect={onConnect}
        onNodesChange={(changes) => setNodes((nds) => applyNodeChanges(changes, nds))}
        onEdgesChange={(changes) => setEdges((eds) => applyEdgeChanges(changes, eds))}
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
};
```

### WebShell (xterm.js)

```tsx
// frontend/src/components/WebShell.tsx

import React, { useEffect, useRef } from 'react';
import { Terminal } from 'xterm';
import { FitAddon } from 'xterm-addon-fit';
import 'xterm/css/xterm.css';

interface WebShellProps {
  device: string;
}

export const WebShell: React.FC<WebShellProps> = ({ device }) => {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!terminalRef.current) return;

    // Create terminal
    const term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = term;

    // Connect WebSocket
    const ws = new WebSocket(`ws://localhost:8007/ws/shell/${device}`);
    wsRef.current = ws;

    ws.onopen = () => {
      term.writeln('Connected to ' + device);
    };

    ws.onmessage = (event) => {
      term.write(event.data);
    };

    ws.onerror = (error) => {
      term.writeln('\r\nWebSocket error: ' + error);
    };

    ws.onclose = () => {
      term.writeln('\r\nConnection closed');
    };

    // Send input to WebSocket
    term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data);
      }
    });

    // Cleanup
    return () => {
      ws.close();
      term.dispose();
    };
  }, [device]);

  return <div ref={terminalRef} style={{ height: '100%', width: '100%' }} />;
};
```

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_topology_service.py

import pytest
from fastapi.testclient import TestClient
from backend.services.topology.main import app

client = TestClient(app)

def test_create_project():
    response = client.post(
        "/api/projects",
        json={"name": "Test Project", "description": "Test"}
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Test Project"

def test_create_topology():
    # Create project first
    project_response = client.post(
        "/api/projects",
        json={"name": "Test Project"}
    )
    project_id = project_response.json()["id"]

    # Create topology
    response = client.post(
        "/api/topologies",
        json={
            "project_id": project_id,
            "name": "Test Topology",
            "nodes": [],
            "links": [],
            "controllers": []
        }
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Test Topology"
```

### Integration Tests

```python
# tests/integration/test_emulation_flow.py

import pytest
import asyncio

async def test_complete_emulation_flow():
    # 1. Create topology
    topology = await create_topology()

    # 2. Start emulation
    emulation = await start_emulation(topology.id)
    assert emulation.status == "running"

    # 3. Add device at runtime
    device = await add_device("h3", "10.0.0.3/24")
    assert device.name == "h3"

    # 4. Execute command
    result = await execute_command("h3", "ping -c 3 10.0.0.1")
    assert result.exit_code == 0

    # 5. Take snapshot
    snapshot = await take_snapshot("checkpoint-1")
    assert snapshot.success

    # 6. Stop emulation
    await stop_emulation(emulation.id)
```

## Deployment

### Production Deployment

```bash
# 1. Configure production environment
cp .env.example .env.production
# Edit .env.production with production settings

# 2. Build images
docker-compose -f docker-compose.yml -f docker-compose.prod.yml build

# 3. Deploy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. Initialize database
docker-compose exec mcp-server python -m alembic upgrade head

# 5. Verify deployment
curl http://localhost/health
```

### Kubernetes Deployment

```yaml
# k8s/deployment.yml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: topology-service
spec:
  replicas: 3
  selector:
    matchLabels:
      app: topology-service
  template:
    metadata:
      labels:
        app: topology-service
    spec:
      containers:
      - name: topology-service
        image: caduceus-flux/topology-service:latest
        ports:
        - containerPort: 8001
        env:
        - name: POSTGRES_HOST
          value: postgres-service
        - name: RABBITMQ_HOST
          value: rabbitmq-service
```

## Monitoring and Observability

### Prometheus Metrics

Each service exposes metrics at `/metrics`:

```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
request_count = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
request_duration = Histogram('http_request_duration_seconds', 'HTTP request duration')

# Emulation metrics
active_emulations = Gauge('active_emulations_total', 'Number of active emulations')
device_count = Gauge('device_count_total', 'Total number of devices')
```

### Grafana Dashboards

Pre-configured dashboards for:
1. Topology Overview - Active emulations, device distribution
2. Device Metrics - CPU, memory, network I/O per device
3. Protocol Statistics - Routing convergence, flow table size
4. Link Performance - Bandwidth usage, packet loss
5. Service Health - API response times, error rates

## Security Considerations

1. **Authentication**: JWT-based authentication for all API endpoints
2. **Authorization**: Role-based access control (RBAC)
3. **Network Isolation**: Emulation networks isolated in separate namespaces
4. **Secret Management**: Use Docker secrets or Vault for credentials
5. **API Rate Limiting**: Prevent abuse with rate limiters
6. **Input Validation**: Strict validation of all user inputs
7. **Container Security**: Run containers with minimal privileges

## Performance Tuning

1. **Database Connection Pooling**: Configure optimal pool sizes
2. **Caching Strategy**: Use Redis for frequently accessed data
3. **Async Operations**: Use async/await for I/O operations
4. **Message Queue**: Batch operations where possible
5. **gRPC Optimization**: Use streaming for large data transfers
6. **Frontend Optimization**: Code splitting, lazy loading

## Troubleshooting

### Common Issues

1. **Emulation container won't start**
   - Check kernel modules: `lsmod | grep mac80211_hwsim`
   - Verify Docker privileged mode enabled

2. **Services can't communicate**
   - Check RabbitMQ connection
   - Verify Consul service registration

3. **WebShell not connecting**
   - Check WebSocket connection
   - Verify device exists in emulation

4. **Protocol switching fails**
   - Check protocol plugin loaded
   - Verify device supports protocol

## Next Steps

To complete the implementation:

1. **Implement remaining microservices** following the templates provided
2. **Create protocol plugins** for OSPF, BGP, RIP, IS-IS, OpenFlow, wireless
3. **Build frontend components** using React + TypeScript
4. **Write comprehensive tests** for all services
5. **Set up CI/CD pipeline** for automated testing and deployment
6. **Create example topologies** demonstrating all features
7. **Write API documentation** using OpenAPI/Swagger

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines on:
- Code style
- Testing requirements
- Pull request process
- Plugin development

## License

Apache 2.0 - See [LICENSE](LICENSE)

## Support

- Documentation: https://docs.caduceus-flux.io
- Issues: https://github.com/your-org/caduceus-flux/issues
- Discussions: https://github.com/your-org/caduceus-flux/discussions
