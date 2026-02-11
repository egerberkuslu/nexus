# Network & Container Control Documentation

## 📚 Documentation Overview

You now have comprehensive guides for controlling networks in Caduceus-Flux. Here's what you need:

---

## 🚀 Getting Started (Pick Your Path)

### Path 1: "Just Show Me How" (5 minutes)
👉 Read: [QUICK_START_NETWORK_CONTROL.md](QUICK_START_NETWORK_CONTROL.md)
- Copy-paste commands
- Essential APIs only
- 30-second workflow
- All device types listed

### Path 2: "I Want Examples" (15 minutes)
👉 Read: [NETWORK_CONTROL_EXAMPLES.md](NETWORK_CONTROL_EXAMPLES.md)
- 8 complete, ready-to-run examples
- WiFi networks
- Routed networks
- Docker containers
- Live modifications
- Performance testing

### Path 3: "Show Me Everything" (30 minutes)
👉 Read: [NETWORK_CONTROL_GUIDE.md](NETWORK_CONTROL_GUIDE.md)
- Complete API reference
- All endpoints documented
- Python SDK examples
- Troubleshooting guide
- Configuration reference

---

## 📋 What You Can Control

### Network Types
- ✅ **Wired Networks** - Hosts + Switches
- ✅ **Routed Networks** - Multi-subnet with routers
- ✅ **WiFi Networks** - Access Points + Stations
- ✅ **Docker Networks** - Container-based nodes
- ✅ **P4 Networks** - Programmable switches
- ✅ **Mixed Networks** - All types combined

### Operations
- ✅ **Create** - Define topologies in JSON
- ✅ **Start** - Activate networks via API
- ✅ **Stop** - Cleanup and destroy
- ✅ **Add** - Insert devices while running
- ✅ **Remove** - Delete devices while running
- ✅ **Update** - Modify device/link properties
- ✅ **Execute** - Run commands on devices
- ✅ **Pause/Resume** - Freeze and unfreeze
- ✅ **Monitor** - Check status and stats

---

## 🔧 Quick Command Reference

### 1. Create Network (Save to Database)
```bash
curl -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d @topology.json
```

### 2. Start Network (Run Emulation)
```bash
curl -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d '{"topology_id": "YOUR_ID"}'
```

### 3. Test Connectivity (Execute Commands)
```bash
curl -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{"device_name": "h1", "command": "ping 10.0.0.2"}'
```

### 4. Add Device (While Running!)
```bash
curl -X POST http://localhost:8002/api/topologies/ID/apply \
  -H "Content-Type: application/json" \
  -d '{
    "changes": {
      "add_devices": [{
        "id": "h3",
        "name": "Host 3",
        "device_type": "host",
        "properties": {"ip": "10.0.0.3/24"}
      }],
      ...
    },
    "commit": true
  }'
```

### 5. Stop Network (Cleanup)
```bash
curl -X POST http://localhost:8002/api/emulation/stop/EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}'
```

---

## 🏗️ Architecture

```
You (User/Script)
    │
    ├─ REST API ──────► Orchestrator Service (8002)
    │                      │
    │                      ├─ gRPC ──────► Mininet-WiFi Container (:50051)
    │                      │                  │
    │                      │                  └─ Real Network!
    │                      │
    │                      └─ REST ──────► Topology Service (8001)
    │
    └─ REST API ──────► Topology Service (8001)
```

### Key Services

| Service | Port | Purpose |
|---------|------|---------|
| **Topology Service** | 8001 | Create/store/manage topology definitions |
| **Orchestrator** | 8002 | Control emulation lifecycle |
| **Device Manager** | 8004 | Manage device properties |
| **Protocol Manager** | 8003 | Routing protocol configuration |
| **Monitoring** | 8011 | Metrics and health |
| **gRPC (Emulation)** | 50051 | Direct communication with Mininet-WiFi |

---

## 📊 Supported Device Types

| Type | Purpose | Example |
|------|---------|---------|
| **host** | Linux container with network namespace | `{"device_type": "host"}` |
| **switch** | Open vSwitch (OVS) | `{"device_type": "switch"}` |
| **router** | FRRouting or BIRD daemon | `{"device_type": "router"}` |
| **accesspoint** | WiFi 802.11 Access Point | `{"device_type": "accesspoint"}` |
| **station** | WiFi mobile client | `{"device_type": "station"}` |
| **docker** | Docker container | `{"device_type": "docker"}` |
| **p4switch** | P4-programmable switch | `{"device_type": "p4switch"}` |

---

## 🎯 Common Scenarios

### Scenario 1: Test Basic Connectivity
```bash
# 1. Create topology with 2 hosts and a switch
# 2. Start emulation
# 3. Ping from h1 to h2
# 4. Stop
👉 Example: NETWORK_CONTROL_EXAMPLES.md → Example 1
```

### Scenario 2: WiFi Network Testing
```bash
# 1. Create AP and WiFi stations
# 2. Test WiFi connectivity
# 3. Measure signal strength
👉 Example: NETWORK_CONTROL_EXAMPLES.md → Example 2
```

### Scenario 3: Multi-Subnet Routing
```bash
# 1. Create routed network with 2 subnets
# 2. Test cross-subnet routing
# 3. Check OSPF convergence
👉 Example: NETWORK_CONTROL_EXAMPLES.md → Example 3
```

### Scenario 4: Live Network Modification
```bash
# 1. Start network
# 2. Add host while running
# 3. Remove host while running
# 4. Verify connectivity
👉 Example: NETWORK_CONTROL_EXAMPLES.md → Example 5
```

### Scenario 5: Performance Testing
```bash
# 1. Create network with loss/delay parameters
# 2. Measure latency
# 3. Measure packet loss
# 4. Measure throughput
👉 Example: NETWORK_CONTROL_EXAMPLES.md → Example 6
```

---

## 🐍 Python Usage

```python
import requests

# Configuration
ORCH = "http://localhost:8002"
TOPO = "http://localhost:8001"

# Create topology
topo = {
    "name": "My Network",
    "nodes": [...],
    "links": [...]
}
r = requests.post(f"{TOPO}/api/topologies", json=topo)
topo_id = r.json()['topology_id']

# Start emulation
r = requests.post(f"{ORCH}/api/emulation/start",
                 json={"topology_id": topo_id})
emul_id = r.json()['emulation_id']

# Execute command
r = requests.post(f"{ORCH}/api/emulation/execute",
                 json={"device_name": "h1", "command": "ping 10.0.0.2"})
print(r.json()['output'])

# Stop
requests.post(f"{ORCH}/api/emulation/stop/{emul_id}",
             json={"cleanup": True})
```

See [NETWORK_CONTROL_GUIDE.md](NETWORK_CONTROL_GUIDE.md) for complete Python SDK.

---

## 🛠️ Environment Configuration

Key environment variables (in `.env`):

```env
# Orchestrator Service
EMULATION_GRPC_HOST=localhost
EMULATION_GRPC_PORT=50051
TOPOLOGY_SERVICE_URL=http://topology-service:8001
TOPOLOGY_REQUEST_TIMEOUT=10.0

# Topology Service
POSTGRES_DB=caduceus_flux
POSTGRES_USER=caduceus
POSTGRES_PASSWORD=changeme_postgres_password

# Redis (for state tracking)
REDIS_HOST=caduceus-redis
REDIS_PORT=6379

# RabbitMQ (for events)
RABBITMQ_USER=caduceus
RABBITMQ_PASSWORD=changeme_rabbitmq_password
```

---

## 📈 Monitoring & Debugging

### Check Service Health
```bash
# Orchestrator
curl http://localhost:8002/health

# Topology Service
curl http://localhost:8001/health

# View Consul services
curl http://localhost:8500/ui/
```

### View Logs
```bash
# Follow orchestrator logs
docker logs caduceus-orchestrator-service -f

# Follow topology service logs
docker logs caduceus-topology-service -f
```

### Check Active Emulations
```bash
# List all running networks
curl http://localhost:8002/api/emulation/active

# Get specific network status
curl http://localhost:8002/api/emulation/status/EMUL_ID

# List all devices in active networks
curl http://localhost:8002/api/emulation/devices
```

---

## 🔍 Troubleshooting

### Problem: Cannot connect to API
**Solution:** Check service is running
```bash
docker compose ps | grep orchestrator
curl http://localhost:8002/health
```

### Problem: Emulation fails to start
**Solution:** Check gRPC connection to Mininet
```bash
grpcurl -plaintext localhost:50051 list
docker logs caduceus-orchestrator-service | tail -50
```

### Problem: Changes don't apply
**Solution:** Verify topology version
```bash
curl http://localhost:8001/api/topologies/YOUR_ID | jq '.version'
```

### Problem: Commands timeout
**Solution:** Increase timeout
```bash
# Check current timeout
docker exec caduceus-orchestrator-service env | grep TIMEOUT

# Update in docker-compose.yml or .env
TOPOLOGY_REQUEST_TIMEOUT=30.0
```

---

## 📚 Complete Documentation Map

```
📚 Network Control Documentation
├── 📄 QUICK_START_NETWORK_CONTROL.md      ← START HERE (5 min)
│   └─ Copy-paste commands, essential APIs
│
├── 📄 NETWORK_CONTROL_EXAMPLES.md         ← Examples (15 min)
│   ├─ Example 1: Simple 2-host network
│   ├─ Example 2: WiFi network
│   ├─ Example 3: Router network
│   ├─ Example 4: Docker container network
│   ├─ Example 5: Live modifications
│   ├─ Example 6: Performance testing
│   ├─ Example 7: Complex multi-layer
│   └─ Example 8: Helper functions
│
├── 📄 NETWORK_CONTROL_GUIDE.md            ← Full Reference (30 min)
│   ├─ Architecture overview
│   ├─ All API endpoints documented
│   ├─ Request/response examples
│   ├─ Device types
│   ├─ Link parameters
│   ├─ Python SDK examples
│   ├─ Monitoring guide
│   ├─ Troubleshooting
│   └─ Configuration reference
│
├── 📄 EMULATION_ARCHITECTURE.md           ← System Design
│   └─ How everything is connected
│
└── 📄 NETWORK_CONTROL_README.md           ← This file
    └─ Navigation and overview
```

---

## ✅ Checklist: Before You Start

- [ ] All services are running (`docker compose ps`)
- [ ] Orchestrator service is healthy (http://localhost:8002/health)
- [ ] Topology service is healthy (http://localhost:8001/health)
- [ ] You've read this README
- [ ] You know which guide to follow

---

## 🚀 Next Steps

### For Quick Testing
1. Read [QUICK_START_NETWORK_CONTROL.md](QUICK_START_NETWORK_CONTROL.md)
2. Copy the "Complete Workflow" script
3. Run it!

### For Learning
1. Read [NETWORK_CONTROL_EXAMPLES.md](NETWORK_CONTROL_EXAMPLES.md)
2. Run Example 1 (simple network)
3. Modify it and experiment
4. Progress to other examples

### For Integration
1. Read [NETWORK_CONTROL_GUIDE.md](NETWORK_CONTROL_GUIDE.md)
2. Use the Python SDK section
3. Build your control application

---

## 📞 API Endpoints at a Glance

### Orchestrator Service (Port 8002)
```
POST   /api/emulation/start              - Start network
POST   /api/emulation/stop/{id}          - Stop network
POST   /api/emulation/pause/{id}         - Pause network
POST   /api/emulation/resume/{id}        - Resume network
GET    /api/emulation/status/{id}        - Get status
GET    /api/emulation/active             - List active
GET    /api/emulation/devices            - List devices
POST   /api/emulation/execute            - Run command
POST   /api/topologies/{id}/apply        - Apply changes
GET    /health                           - Health check
```

### Topology Service (Port 8001)
```
POST   /api/topologies                   - Create topology
GET    /api/topologies                   - List topologies
GET    /api/topologies/{id}              - Get topology
PUT    /api/topologies/{id}              - Update topology
DELETE /api/topologies/{id}              - Delete topology
GET    /health                           - Health check
```

---

## 💡 Key Concepts

### Topology
A **JSON definition** of your network (devices, links, properties). Stored in database.

### Emulation
An **active running network**. Created by sending a topology to the orchestrator. Each emulation has a unique `emulation_id`.

### Device
A **network node** (host, switch, router, AP, etc.). Can be added/removed while emulation is running.

### Link
A **connection between devices**. Can have bandwidth, delay, loss, jitter parameters.

### Atomic Operations
**All-or-nothing changes**. Apply multiple device/link changes together - all succeed or all rollback.

---

## 🎓 Learning Path

**Beginner (1 hour):**
1. Read QUICK_START_NETWORK_CONTROL.md
2. Run Example 1
3. Test with curl commands

**Intermediate (2-3 hours):**
1. Run Examples 2-5
2. Modify examples
3. Create your own topology

**Advanced (1-2 days):**
1. Read NETWORK_CONTROL_GUIDE.md
2. Build Python integration
3. Deploy to production

---

**You're all set!** Pick a guide and start building networks. 🚀
