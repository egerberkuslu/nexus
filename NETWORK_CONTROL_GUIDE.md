# Caduceus-Flux Network & Container Control Guide

## Overview

Caduceus-Flux provides a complete microservices-based platform to control Mininet-WiFi and Containernet networks. Here's how to control everything:

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│  Web UI / REST Client / Scripts                             │
│  (curl, Postman, Python requests, etc.)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST
┌──────────────────────▼──────────────────────────────────────┐
│  API Gateway (nginx:80)                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API
    ┌──────────────────┼──────────────────┐
    │                  │                  │
    ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Orchestrator │  │   Topology   │  │ Device Mgr   │
│ (:8002)      │  │   (:8001)    │  │   (:8004)    │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                  │
       └─────────────┬───┴──────────────────┘
                     │ gRPC
        ┌────────────▼────────────┐
        │  Emulation Container    │
        │  (:50051 gRPC)          │
        │  (Systemd Service)      │
        │                         │
        │ ┌─────────────────────┐ │
        │ │ Mininet-WiFi        │ │
        │ │ ├─ Hosts            │ │
        │ │ ├─ Switches         │ │
        │ │ ├─ Routers          │ │
        │ │ ├─ WiFi APs         │ │
        │ │ ├─ WiFi Stations    │ │
        │ │ └─ Docker Containers│ │
        │ └─────────────────────┘ │
        │                         │
        │ ┌─────────────────────┐ │
        │ │ Routing Services    │ │
        │ │ ├─ Open vSwitch     │ │
        │ │ ├─ FRRouting        │ │
        │ │ └─ BIRD             │ │
        │ └─────────────────────┘ │
        │                         │
        └─────────────────────────┘
```

---

## 1. API Endpoints - Orchestrator Service (Port 8002)

### Start an Emulation

**Endpoint:** `POST /api/emulation/start`

**Description:** Start a new emulation from a topology definition

**Request Body:**
```json
{
  "topology_id": "my-topology-123",
  "options": {
    "autoStart": true,
    "autoAddRoutes": true
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Emulation started successfully",
  "emulation_id": "emul-abc123def"
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d '{
    "topology_id": "my-topology-123",
    "options": {}
  }'
```

---

### Stop an Emulation

**Endpoint:** `POST /api/emulation/stop/{emulation_id}`

**Description:** Stop a running emulation and cleanup resources

**Request Body:**
```json
{
  "cleanup": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Emulation stopped successfully",
  "emulation_id": "emul-abc123def"
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8002/api/emulation/stop/emul-abc123def \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}'
```

---

### Apply Topology Changes (Live)

**Endpoint:** `POST /api/topologies/{topology_id}/apply`

**Description:** Apply staged changes to a running topology (add/remove/update devices and links)

**Request Body:**
```json
{
  "changes": {
    "add_devices": [
      {
        "id": "h3",
        "name": "Host 3",
        "device_type": "host",
        "properties": {
          "ip": "10.0.0.3/24",
          "mac": "00:00:00:00:00:03"
        }
      }
    ],
    "update_devices": [
      {
        "id": "h1",
        "properties": {
          "ip": "10.0.0.100/24"
        }
      }
    ],
    "remove_devices": ["old_host"],
    "add_links": [
      {
        "source_node_id": "h3",
        "target_node_id": "s1",
        "bandwidth": 100,
        "delay": 1,
        "loss": 0
      }
    ],
    "update_links": [],
    "remove_links": []
  },
  "commit": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Changes applied successfully",
  "applied": {
    "devices_added": 1,
    "devices_updated": 1,
    "devices_removed": 1,
    "links_added": 1
  },
  "rollback_performed": false
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8002/api/topologies/my-topology-123/apply \
  -H "Content-Type: application/json" \
  -d '{
    "changes": {
      "add_devices": [{
        "id": "h3",
        "name": "Host 3",
        "device_type": "host",
        "properties": {"ip": "10.0.0.3/24"}
      }],
      "update_devices": [],
      "remove_devices": [],
      "add_links": [],
      "update_links": [],
      "remove_links": []
    },
    "commit": true
  }'
```

---

### Pause an Emulation

**Endpoint:** `POST /api/emulation/pause/{emulation_id}`

**Description:** Pause a running emulation (network frozen, can resume)

**Response:**
```json
{
  "success": true,
  "message": "Emulation paused successfully",
  "emulation_id": "emul-abc123def"
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8002/api/emulation/pause/emul-abc123def \
  -H "Content-Type: application/json"
```

---

### Resume an Emulation

**Endpoint:** `POST /api/emulation/resume/{emulation_id}`

**Description:** Resume a paused emulation

**Response:**
```json
{
  "success": true,
  "message": "Emulation resumed successfully",
  "emulation_id": "emul-abc123def"
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8002/api/emulation/resume/emul-abc123def \
  -H "Content-Type: application/json"
```

---

### Get Emulation Status

**Endpoint:** `GET /api/emulation/status/{emulation_id}`

**Description:** Get the current status of an emulation

**Response:**
```json
{
  "success": true,
  "emulation_id": "emul-abc123def",
  "topology_id": "my-topology-123",
  "status": "running",
  "uptime_seconds": 3600,
  "node_count": 5,
  "link_count": 4,
  "created_at": "2025-01-01T12:00:00Z"
}
```

**Example with curl:**
```bash
curl http://localhost:8002/api/emulation/status/emul-abc123def
```

---

### List Active Emulations

**Endpoint:** `GET /api/emulation/active`

**Description:** List all currently running emulations

**Response:**
```json
[
  {
    "emulation_id": "emul-abc123def",
    "topology_id": "my-topology-123",
    "status": "running",
    "created_at": "2025-01-01T12:00:00Z"
  }
]
```

**Example with curl:**
```bash
curl http://localhost:8002/api/emulation/active
```

---

### Get Emulation Devices

**Endpoint:** `GET /api/emulation/devices`

**Description:** List all devices in active emulation(s)

**Response:**
```json
[
  {
    "name": "h1",
    "device_type": "host",
    "status": "running",
    "properties": {
      "ip": "10.0.0.1/24",
      "mac": "00:00:00:00:00:01"
    }
  },
  {
    "name": "s1",
    "device_type": "switch",
    "status": "running",
    "properties": {
      "switch_type": "ovs",
      "dpid": "0000000000000001"
    }
  }
]
```

**Example with curl:**
```bash
curl http://localhost:8002/api/emulation/devices
```

---

### Execute Command in Emulation

**Endpoint:** `POST /api/emulation/execute`

**Description:** Execute a command on a specific device in the emulation

**Request Body:**
```json
{
  "device_name": "h1",
  "command": "ping -c 4 10.0.0.2"
}
```

**Response:**
```json
{
  "success": true,
  "device_name": "h1",
  "command": "ping -c 4 10.0.0.2",
  "output": "PING 10.0.0.2 (10.0.0.2) 56(84) bytes of data.\n64 bytes from 10.0.0.2: icmp_seq=1 time=1.23 ms\n...",
  "exit_code": 0
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "h1",
    "command": "ping -c 4 10.0.0.2"
  }'
```

---

## 2. API Endpoints - Topology Service (Port 8001)

### Create Topology

**Endpoint:** `POST /api/topologies`

**Description:** Create a new topology definition

**Request Body:**
```json
{
  "name": "My Network",
  "description": "A test network",
  "version": "1.0",
  "nodes": [
    {
      "name": "h1",
      "device_type": "host",
      "x": 100,
      "y": 200,
      "properties": {
        "ip": "10.0.0.1/24",
        "mac": "00:00:00:00:00:01"
      }
    },
    {
      "name": "s1",
      "device_type": "switch",
      "x": 200,
      "y": 100,
      "properties": {
        "switch_type": "ovs",
        "openflow_version": "1.3"
      }
    }
  ],
  "links": [
    {
      "source_node_id": "h1",
      "target_node_id": "s1",
      "bandwidth": 100,
      "delay": 1,
      "loss": 0
    }
  ]
}
```

**Example with curl:**
```bash
curl -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @topology.json
```

---

### Get Topology

**Endpoint:** `GET /api/topologies/{topology_id}`

**Example with curl:**
```bash
curl http://localhost:8001/api/topologies/my-topology-123
```

---

### List Topologies

**Endpoint:** `GET /api/topologies`

**Example with curl:**
```bash
curl http://localhost:8001/api/topologies
```

---

### Update Topology

**Endpoint:** `PUT /api/topologies/{topology_id}`

**Example with curl:**
```bash
curl -X PUT http://localhost:8001/api/topologies/my-topology-123 \
  -H "Content-Type: application/json" \
  -d @updated-topology.json
```

---

### Delete Topology

**Endpoint:** `DELETE /api/topologies/{topology_id}`

**Example with curl:**
```bash
curl -X DELETE http://localhost:8001/api/topologies/my-topology-123
```

---

## 3. Supported Device Types

### Host
```json
{
  "name": "h1",
  "device_type": "host",
  "properties": {
    "ip": "10.0.0.1/24",
    "mac": "00:00:00:00:00:01",
    "default_route": "via 10.0.0.254"
  }
}
```

### Switch (Open vSwitch)
```json
{
  "name": "s1",
  "device_type": "switch",
  "properties": {
    "switch_type": "ovs",
    "openflow_version": "1.3",
    "datapath_id": "0000000000000001",
    "controller": "127.0.0.1:6653"
  }
}
```

### Router
```json
{
  "name": "r1",
  "device_type": "router",
  "properties": {
    "router_daemon": "frr",
    "protocols": ["ospf", "bgp"],
    "ospf_config": {
      "area": "0.0.0.0"
    },
    "bgp_config": {
      "asn": 65001
    }
  }
}
```

### WiFi Access Point
```json
{
  "name": "ap1",
  "device_type": "accesspoint",
  "properties": {
    "ssid": "TestNetwork",
    "mode": "11g",
    "channel": 6,
    "txpower": 20,
    "security": "wpa2",
    "password": "testpass123"
  }
}
```

### WiFi Station
```json
{
  "name": "sta1",
  "device_type": "station",
  "properties": {
    "ip": "10.0.0.10/24",
    "position": "100,200,0",
    "mobility": {
      "model": "RandomWaypoint",
      "max_speed": 5.0
    }
  }
}
```

### Docker Container
```json
{
  "name": "server1",
  "device_type": "docker",
  "properties": {
    "image": "ubuntu:22.04",
    "command": "/bin/bash",
    "environment": {
      "NODE_ENV": "production"
    },
    "volumes": [
      "/data:/container/data"
    ],
    "ports": [
      "8080:8080"
    ]
  }
}
```

### P4 Switch
```json
{
  "name": "p4s1",
  "device_type": "p4switch",
  "properties": {
    "program": "/path/to/program.p4",
    "architecture": "simple_switch",
    "compiler_options": ""
  }
}
```

---

## 4. Link Parameters

```json
{
  "source_node_id": "h1",
  "target_node_id": "s1",
  "source_port": "h1-eth0",
  "target_port": "s1-eth1",
  "bandwidth": 100,          // Mbps
  "delay": 1,                // ms
  "loss": 0.5,               // percentage (0-100)
  "max_queue_size": 1000,    // packets
  "jitter": 0.1,             // ms (optional)
  "properties": {}
}
```

---

## 5. Complete Example Workflow

### Step 1: Create a Topology
```bash
# Create topology.json with your network definition
cat > topology.json << 'EOF'
{
  "name": "My Network",
  "description": "WiFi + Wired Network",
  "nodes": [
    {
      "name": "h1",
      "device_type": "host",
      "properties": {"ip": "10.0.0.1/24"}
    },
    {
      "name": "h2",
      "device_type": "host",
      "properties": {"ip": "10.0.0.2/24"}
    },
    {
      "name": "s1",
      "device_type": "switch",
      "properties": {"switch_type": "ovs", "openflow_version": "1.3"}
    },
    {
      "name": "ap1",
      "device_type": "accesspoint",
      "properties": {"ssid": "TestNet", "channel": 6, "mode": "11g"}
    },
    {
      "name": "sta1",
      "device_type": "station",
      "properties": {"ip": "10.0.1.10/24"}
    }
  ],
  "links": [
    {"source_node_id": "h1", "target_node_id": "s1", "bandwidth": 100, "delay": 1},
    {"source_node_id": "h2", "target_node_id": "s1", "bandwidth": 100, "delay": 1},
    {"source_node_id": "s1", "target_node_id": "ap1", "bandwidth": 100, "delay": 1}
  ]
}
EOF
```

### Step 2: Save to Topology Service
```bash
# Create the topology
TOPOLOGY_ID=$(curl -s -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @topology.json | jq -r '.topology_id')

echo "Created topology: $TOPOLOGY_ID"
```

### Step 3: Start Emulation
```bash
# Start the network
curl -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPOLOGY_ID\"}"
```

### Step 4: Test Connectivity
```bash
# Ping from h1 to h2
curl -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "h1",
    "command": "ping -c 4 10.0.0.2"
  }'
```

### Step 5: Apply Live Changes
```bash
# Add a new host while network is running
curl -X POST http://localhost:8002/api/topologies/$TOPOLOGY_ID/apply \
  -H "Content-Type: application/json" \
  -d '{
    "changes": {
      "add_devices": [{
        "id": "h3",
        "name": "Host 3",
        "device_type": "host",
        "properties": {"ip": "10.0.0.3/24"}
      }],
      "add_links": [{
        "source_node_id": "h3",
        "target_node_id": "s1",
        "bandwidth": 100,
        "delay": 1
      }],
      "update_devices": [],
      "remove_devices": [],
      "update_links": [],
      "remove_links": []
    },
    "commit": true
  }'
```

### Step 6: Stop Emulation
```bash
# Get active emulation
EMULATION_ID=$(curl -s http://localhost:8002/api/emulation/active | jq -r '.[0].emulation_id')

# Stop the network
curl -X POST http://localhost:8002/api/emulation/stop/$EMULATION_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}'
```

---

## 6. Python Helper Script

Create a Python script for easier control:

```python
import requests
import json
import time

BASE_URL_ORCHESTRATOR = "http://localhost:8002"
BASE_URL_TOPOLOGY = "http://localhost:8001"

class CaduceusController:
    def __init__(self):
        self.orch_url = BASE_URL_ORCHESTRATOR
        self.topo_url = BASE_URL_TOPOLOGY

    def create_topology(self, topology_dict):
        """Create a topology"""
        resp = requests.post(
            f"{self.topo_url}/api/topologies",
            json=topology_dict
        )
        return resp.json()

    def start_emulation(self, topology_id):
        """Start emulation"""
        resp = requests.post(
            f"{self.orch_url}/api/emulation/start",
            json={"topology_id": topology_id}
        )
        return resp.json()

    def stop_emulation(self, emulation_id):
        """Stop emulation"""
        resp = requests.post(
            f"{self.orch_url}/api/emulation/stop/{emulation_id}",
            json={"cleanup": True}
        )
        return resp.json()

    def apply_changes(self, topology_id, changes):
        """Apply topology changes"""
        resp = requests.post(
            f"{self.orch_url}/api/topologies/{topology_id}/apply",
            json={"changes": changes, "commit": True}
        )
        return resp.json()

    def execute_command(self, device_name, command):
        """Execute command on device"""
        resp = requests.post(
            f"{self.orch_url}/api/emulation/execute",
            json={"device_name": device_name, "command": command}
        )
        return resp.json()

    def get_status(self, emulation_id):
        """Get emulation status"""
        resp = requests.get(
            f"{self.orch_url}/api/emulation/status/{emulation_id}"
        )
        return resp.json()

    def list_active(self):
        """List active emulations"""
        resp = requests.get(f"{self.orch_url}/api/emulation/active")
        return resp.json()

# Usage
if __name__ == "__main__":
    ctrl = CaduceusController()

    # Create topology
    topo = {
        "name": "Test Network",
        "nodes": [
            {"name": "h1", "device_type": "host", "properties": {"ip": "10.0.0.1/24"}},
            {"name": "h2", "device_type": "host", "properties": {"ip": "10.0.0.2/24"}},
            {"name": "s1", "device_type": "switch", "properties": {"switch_type": "ovs"}}
        ],
        "links": [
            {"source_node_id": "h1", "target_node_id": "s1"},
            {"source_node_id": "h2", "target_node_id": "s1"}
        ]
    }

    result = ctrl.create_topology(topo)
    topo_id = result['topology_id']
    print(f"Created topology: {topo_id}")

    # Start emulation
    result = ctrl.start_emulation(topo_id)
    emul_id = result['emulation_id']
    print(f"Started emulation: {emul_id}")

    # Wait for network to stabilize
    time.sleep(2)

    # Test connectivity
    result = ctrl.execute_command("h1", "ping -c 4 10.0.0.2")
    print(f"Ping result:\n{result['output']}")

    # Check status
    result = ctrl.get_status(emul_id)
    print(f"Status: {result['status']}")

    # Stop emulation
    result = ctrl.stop_emulation(emul_id)
    print(f"Stopped: {result['success']}")
```

---

## 7. Monitoring & Debugging

### Check Service Health
```bash
# Orchestrator health
curl http://localhost:8002/health

# Topology service
curl http://localhost:8001/health

# View Consul services
curl http://localhost:8500/ui/
```

### View Logs
```bash
# Orchestrator logs
docker logs caduceus-orchestrator-service -f

# Topology service logs
docker logs caduceus-topology-service -f

# Device manager logs
docker logs caduceus-device-manager-service -f
```

### Check Active Emulations in Redis
```bash
# Connect to Redis
redis-cli -h localhost -p 6379

# List active emulations
KEYS active_emulations:*
GET active_emulations:topology-123
```

### Check RabbitMQ Events
```bash
# Open RabbitMQ Management UI
# http://localhost:15672
# Username: caduceus / Password: changeme_rabbitmq_password

# View published events
# Check "emulation.started", "topology.applied", etc. exchanges
```

---

## 8. Common Issues & Solutions

### Problem: Emulation fails to start

**Solution 1:** Check gRPC connection
```bash
# Test gRPC connection
grpcurl -plaintext localhost:50051 list
```

**Solution 2:** Check emulation container logs
```bash
# If running systemd service
sudo journalctl -u caduceus-emulation -f

# If running in Docker
docker logs caduceus-emulation-container
```

### Problem: Changes don't apply

**Solution:** Check topology version consistency
```bash
# Get topology details
curl http://localhost:8001/api/topologies/my-topology-123

# Ensure you're using correct version in apply request
```

### Problem: Device commands timeout

**Solution:** Increase timeout
```bash
# Check service configuration
docker exec caduceus-orchestrator-service env | grep TIMEOUT
```

---

## 9. Configuration Reference

Key environment variables (in `.env` file):

```env
# Orchestrator
EMULATION_GRPC_HOST=localhost
EMULATION_GRPC_PORT=50051
SERVICE_PORT=8002
TOPOLOGY_SERVICE_URL=http://topology-service:8001
TOPOLOGY_REQUEST_TIMEOUT=10.0

# Topology Service
SERVICE_PORT=8001
POSTGRES_DB=caduceus_flux
POSTGRES_USER=caduceus
POSTGRES_PASSWORD=changeme_postgres_password

# Redis
REDIS_HOST=caduceus-redis
REDIS_PORT=6379
REDIS_PASSWORD=changeme_redis_password

# RabbitMQ
RABBITMQ_USER=caduceus
RABBITMQ_PASSWORD=changeme_rabbitmq_password
RABBITMQ_VHOST=/caduceus-flux
```

---

## 10. WebSocket Events (Real-time Updates)

The system publishes events to WebSocket for real-time updates:

```javascript
// JavaScript example
const ws = new WebSocket('ws://localhost:8002/ws');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  console.log('Event:', msg.type);
  console.log('Data:', msg.data);
};

// Event types:
// - emulation.started
// - emulation.stopped
// - topology.applied
// - device.added
// - device.removed
// - link.updated
// - command.executed
```

---

**Summary:**

You can control networks by:
1. **REST APIs** - HTTP requests to orchestrator/topology services
2. **Python SDK** - Use requests library for scripting
3. **curl commands** - Direct shell commands
4. **WebSocket** - Real-time event monitoring
5. **gRPC** - Direct communication with emulation container

All changes are atomic, versioned, and can be rolled back automatically on failure!
