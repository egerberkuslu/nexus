# Quick Start: Network Control Commands

## 30-Second Summary

```
1. Create topology (JSON)
   ↓
2. POST to http://localhost:8001/api/topologies  (save definition)
   ↓
3. POST to http://localhost:8002/api/emulation/start  (start network)
   ↓
4. Network is running! Test with curl commands
   ↓
5. Apply changes with /api/topologies/{id}/apply (live updates)
   ↓
6. POST to /api/emulation/stop/{id}  (cleanup)
```

---

## Essential Commands

### 1. Create & Start Network (2 steps)

**Step 1: Define topology (topology.json)**
```json
{
  "name": "Simple Network",
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
```

**Step 2: Create topology**
```bash
curl -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @topology.json
```

**Response:** Gets `topology_id` → Save it!

**Step 3: Start network**
```bash
curl -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d '{"topology_id": "YOUR_TOPOLOGY_ID"}'
```

**Response:** Gets `emulation_id` → Save it!

---

### 2. Test Network

```bash
# Test host to host connectivity
curl -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping -c 4 10.0.0.2"}'

# Response shows ping output
```

---

### 3. Add Devices Live (while network runs)

```bash
curl -X POST http://localhost:8002/api/topologies/YOUR_TOPOLOGY_ID/apply \
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

---

### 4. Stop Network

```bash
curl -X POST http://localhost:8002/api/emulation/stop/YOUR_EMULATION_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}'
```

---

## All Device Types (Copypaste)

### Host
```json
{
  "id": "h1",
  "name": "Host 1",
  "device_type": "host",
  "properties": {
    "ip": "10.0.0.1/24",
    "mac": "00:00:00:00:00:01"
  }
}
```

### Switch (OVS)
```json
{
  "id": "s1",
  "name": "Switch 1",
  "device_type": "switch",
  "properties": {
    "switch_type": "ovs",
    "openflow_version": "1.3"
  }
}
```

### Router
```json
{
  "id": "r1",
  "name": "Router 1",
  "device_type": "router",
  "properties": {
    "router_daemon": "frr",
    "protocols": ["ospf", "bgp"]
  }
}
```

### WiFi AP
```json
{
  "id": "ap1",
  "name": "Access Point 1",
  "device_type": "accesspoint",
  "properties": {
    "ssid": "TestNetwork",
    "mode": "11g",
    "channel": 6,
    "txpower": 20
  }
}
```

### WiFi Station
```json
{
  "id": "sta1",
  "name": "WiFi Client 1",
  "device_type": "station",
  "properties": {
    "ip": "10.0.1.10/24"
  }
}
```

### Docker Container
```json
{
  "id": "docker1",
  "name": "Docker Container 1",
  "device_type": "docker",
  "properties": {
    "image": "ubuntu:22.04",
    "command": "/bin/bash"
  }
}
```

---

## All Link Parameters

```json
{
  "source_node_id": "h1",
  "target_node_id": "s1",
  "bandwidth": 100,        // Mbps
  "delay": 1,              // milliseconds
  "loss": 0.5,             // percentage (0-100)
  "max_queue_size": 1000   // packets
}
```

---

## Monitoring Commands

```bash
# List active emulations
curl http://localhost:8002/api/emulation/active

# Get specific emulation status
curl http://localhost:8002/api/emulation/status/YOUR_EMULATION_ID

# List all devices
curl http://localhost:8002/api/emulation/devices

# Check service health
curl http://localhost:8002/health
```

---

## Complete Workflow (Copy & Paste)

```bash
#!/bin/bash

# 1. Create topology
TOPO=$(cat << 'EOF'
{
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
EOF
)

TOPO_ID=$(curl -s -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d "$TOPO" | jq -r '.topology_id')

echo "Topology ID: $TOPO_ID"

# 2. Start emulation
EMUL=$(curl -s -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}")

EMUL_ID=$(echo $EMUL | jq -r '.emulation_id')
echo "Emulation ID: $EMUL_ID"

# 3. Wait for network to start
sleep 2

# 4. Test ping
echo "Testing connectivity..."
curl -s -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping -c 4 10.0.0.2"}' | jq '.output'

# 5. Check status
echo "Status:"
curl -s http://localhost:8002/api/emulation/status/$EMUL_ID | jq '.'

# 6. Stop network
echo "Stopping network..."
curl -s -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}' | jq '.'
```

---

## Common Patterns

### Pattern 1: Create → Start → Test → Stop

```bash
# Store IDs in variables
TOPO_ID="topology-123"
EMUL_ID="emul-456"

# Start
curl -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}"

# Test
curl -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ifconfig"}'

# Stop
curl -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}'
```

### Pattern 2: Pause → Modify → Resume

```bash
# Pause network
curl -X POST http://localhost:8002/api/emulation/pause/$EMUL_ID

# Apply changes
curl -X POST http://localhost:8002/api/topologies/$TOPO_ID/apply \
  -H "Content-Type: application/json" \
  -d '{"changes": {...}, "commit": true}'

# Resume network
curl -X POST http://localhost:8002/api/emulation/resume/$EMUL_ID
```

### Pattern 3: Live Add Device

```bash
curl -X POST http://localhost:8002/api/topologies/$TOPO_ID/apply \
  -H "Content-Type: application/json" \
  -d '{
    "changes": {
      "add_devices": [{
        "id": "h10",
        "name": "Host 10",
        "device_type": "host",
        "properties": {"ip": "10.0.0.10/24"}
      }],
      "add_links": [{
        "source_node_id": "h10",
        "target_node_id": "s1"
      }],
      "update_devices": [],
      "remove_devices": [],
      "update_links": [],
      "remove_links": []
    },
    "commit": true
  }'
```

---

## Key Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| Frontend | 3000 | Web UI |
| Topology Service | 8001 | Manage topology definitions |
| Orchestrator | 8002 | Control emulation |
| Protocol Manager | 8003 | Routing protocols |
| Device Manager | 8004 | Device control |
| Controller Manager | 8005 | SDN controllers |
| Snapshot Service | 8006 | Snapshots/restore |
| WebShell | 8007 | Terminal access |
| Export/Import | 8008 | Data export |
| Topology Generator | 8009 | Auto generate |
| P4 Manager | 8010 | P4 switches |
| Monitoring | 8011 | Metrics |
| MCP Server | 8012 | Protocol conversion |
| gRPC (Mininet) | 50051 | Emulation container |

---

## Python Quick Script

```python
import requests
import json

# Configuration
ORCH = "http://localhost:8002"
TOPO = "http://localhost:8001"

# Helper functions
def create_topo(topo_dict):
    r = requests.post(f"{TOPO}/api/topologies", json=topo_dict)
    return r.json()['topology_id']

def start_emul(topo_id):
    r = requests.post(f"{ORCH}/api/emulation/start",
                     json={"topology_id": topo_id})
    return r.json()['emulation_id']

def exec_cmd(device, cmd):
    r = requests.post(f"{ORCH}/api/emulation/execute",
                     json={"device_name": device, "command": cmd})
    return r.json()['output']

def stop_emul(emul_id):
    requests.post(f"{ORCH}/api/emulation/stop/{emul_id}",
                 json={"cleanup": True})

def apply_changes(topo_id, changes):
    r = requests.post(f"{ORCH}/api/topologies/{topo_id}/apply",
                     json={"changes": changes, "commit": True})
    return r.json()

# Example usage
if __name__ == "__main__":
    topo_def = {
        "name": "Test",
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

    topo_id = create_topo(topo_def)
    emul_id = start_emul(topo_id)
    print(exec_cmd("h1", "ping -c 4 10.0.0.2"))
    stop_emul(emul_id)
```

---

## Need More?

- **Full Guide:** See [NETWORK_CONTROL_GUIDE.md](NETWORK_CONTROL_GUIDE.md)
- **Architecture:** See [EMULATION_ARCHITECTURE.md](EMULATION_ARCHITECTURE.md)
- **Implementation:** See [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)
- **Frontend Guide:** See [FRONTEND_QUICKSTART.md](FRONTEND_QUICKSTART.md)
