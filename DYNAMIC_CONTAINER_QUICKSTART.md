# Dynamic Container Architecture - Quick Start

## 🎯 What Changed

**OLD**: One static emulation container handles all topologies
**NEW**: Each topology gets its own dedicated container spawned on-demand

---

## 🚀 Quick Start (5 Steps)

### Step 1: Build the Dynamic Image (5 min)

```bash
cd /home/ege/Desktop/cadeceus-flux-mininet-from-strach/caduceus-flux

docker build \
  -f emulation-container/Dockerfile.dynamic \
  -t caduceus-emulation:dynamic \
  .
```

**Expected**: Image `caduceus-emulation:dynamic` built successfully

---

### Step 2: Remove Static Container (1 min)

Edit `docker-compose.yml` and **comment out** the static emulation-container:

```yaml
# Remove or comment this entire section:
# emulation-container:
#   build:
#     context: .
#     dockerfile: emulation-container/Dockerfile
#   ...
```

Then restart services:
```bash
docker compose down
docker compose up -d
```

---

### Step 3: Apply Database Migrations (2 min)

```bash
# Connect to PostgreSQL
docker exec -it caduceus-postgres psql -U caduceus -d caduceus_flux

# Copy-paste these migrations:
ALTER TABLE topologies ADD COLUMN IF NOT EXISTS emulation_id VARCHAR(255);
ALTER TABLE topologies ADD COLUMN IF NOT EXISTS container_id VARCHAR(255);
ALTER TABLE topologies ADD COLUMN IF NOT EXISTS container_name VARCHAR(255);
ALTER TABLE topologies ADD COLUMN IF NOT EXISTS container_port INTEGER;
ALTER TABLE topologies ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'created';
ALTER TABLE topologies ADD COLUMN IF NOT EXISTS started_at TIMESTAMP;
ALTER TABLE topologies ADD COLUMN IF NOT EXISTS stopped_at TIMESTAMP;

CREATE TABLE IF NOT EXISTS emulation_containers (
    id SERIAL PRIMARY KEY,
    emulation_id VARCHAR(255) UNIQUE NOT NULL,
    topology_id UUID NOT NULL REFERENCES topologies(id),
    container_id VARCHAR(255) NOT NULL,
    container_name VARCHAR(255) NOT NULL,
    grpc_port INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'starting',
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    stopped_at TIMESTAMP,
    ip_address VARCHAR(50),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_emulation_topology ON emulation_containers(topology_id);
CREATE INDEX IF NOT EXISTS idx_emulation_container ON emulation_containers(container_id);

\q
```

---

### Step 4: Update Orchestrator Code (Manual)

**File**: `backend/services/orchestrator/main.py`

**Find** the `start_emulation_endpoint` function (around line 689)

**Replace** with the code from [DYNAMIC_CONTAINER_IMPLEMENTATION.md](./DYNAMIC_CONTAINER_IMPLEMENTATION.md) section "D. Orchestrator Service Updates"

Key changes:
- Add `import docker`
- Spawn container with `docker_client.containers.run()`
- Store container info in database
- Connect to container's gRPC port

**Also update** `stop_emulation_endpoint` (around line 1151) to remove containers.

---

### Step 5: Test (5 min)

```bash
# 1. Create topology
curl -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d '{
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
  }'

# Save the topology_id from response

# 2. Start emulation (spawns container)
TOPO_ID="<your-topology-id>"

curl -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}"

# Expected: Returns emulation_id, container_id, grpc_port

# 3. Verify container is running
docker ps | grep emulation-

# Should see: emulation-<topology-id>-<emulation-id>

# 4. Test connectivity
curl -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "h1",
    "command": "ping -c 4 10.0.0.2"
  }'

# 5. Stop (removes container)
EMUL_ID="<your-emulation-id>"

curl -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}'

# Verify container is gone
docker ps | grep emulation-
```

---

## 📋 Architecture Overview

```
User creates topology
    ↓
Stored in PostgreSQL (status="created")
    ↓
User clicks "Start"
    ↓
POST /api/emulation/start
    ↓
Orchestrator spawns NEW container:
  - docker run caduceus-emulation:dynamic
  - Name: emulation-<topology-id>-<emulation-id>
  - Port: Random (50051-50151)
  - Environment: TOPOLOGY_ID, EMULATION_ID
    ↓
Container starts:
  - Loads WiFi modules
  - Starts Open vSwitch
  - Starts gRPC server on port 50051 (internal)
    ↓
Orchestrator connects to container's gRPC
    ↓
Sends topology definition
    ↓
Container creates Mininet-WiFi network
    ↓
Database updated:
  - topologies.container_id = "abc123"
  - topologies.status = "running"
  - emulation_containers table populated
    ↓
User interacts:
  - Execute commands via gRPC
  - Monitor status
    ↓
User clicks "Stop"
    ↓
Orchestrator stops and removes container
    ↓
Database updated: status="stopped"
```

---

## 🔍 Key Benefits

| Feature | Static Container | Dynamic Containers |
|---------|-----------------|-------------------|
| Isolation | ❌ All topologies share | ✅ Each topology isolated |
| Scalability | ❌ Limited | ✅ Spawn unlimited |
| Resource Tracking | ❌ Hard to track | ✅ Per-topology metrics |
| Debugging | ❌ Mixed logs | ✅ Separate logs per topology |
| State Management | ❌ Complex | ✅ Simple (container = topology) |
| Clean Shutdown | ❌ Affects all | ✅ Independent |

---

## 📁 Files Created

1. **emulation-container/Dockerfile.dynamic**
   - Based on your working scripts
   - Mininet-WiFi + Containernet + gRPC
   - Optimized for dynamic spawning

2. **emulation-container/scripts/entrypoint-dynamic.sh**
   - Container initialization script
   - WiFi, OVS, namespace setup

3. **DYNAMIC_CONTAINER_IMPLEMENTATION.md**
   - Complete implementation guide (18 KB)
   - Database schemas
   - Code examples
   - Full orchestrator updates

4. **DYNAMIC_CONTAINER_QUICKSTART.md** (this file)
   - 5-step quick start
   - Testing procedures

---

## ⚠️ Prerequisites

- Docker installed and running
- All Caduceus-Flux services running
- PostgreSQL accessible
- Sufficient resources (2GB RAM per container recommended)

---

## 🐛 Troubleshooting

### Container fails to start

**Check**:
```bash
docker logs emulation-<id>
```

**Common issues**:
- WiFi module not loaded on host
- OVS database creation failed
- Port already in use

**Solution**:
```bash
# On host
sudo modprobe mac80211_hwsim radios=4
```

### gRPC connection timeout

**Check**:
```bash
docker exec emulation-<id> netstat -tlnp | grep 50051
```

**Solution**: Increase `wait_for_container_ready` timeout in orchestrator

### Multiple containers on same port

**Check** port allocation in orchestrator logs

**Solution**: Verify `find_available_port()` function works correctly

---

## 📞 Next Steps

1. ✅ Build dynamic image
2. ✅ Apply migrations
3. ⏳ Update orchestrator code
4. ⏳ Test single topology
5. ⏳ Test multiple topologies
6. ⏳ Add resource limits
7. ⏳ Implement cleanup job

---

## 🎓 How It Works

**Container Lifecycle**:

```
CREATE → SPAWN → INIT → READY → RUNNING → STOPPED → REMOVED
   ↓       ↓      ↓       ↓        ↓         ↓         ↓
  Save   Docker  WiFi    gRPC    Mininet   docker    Clean
  DB     run     +OVS    ready   network   stop      DB
```

**Database Tracking**:

```sql
-- Topology knows its container
SELECT container_id, container_name, grpc_port
FROM topologies
WHERE id = '<topology-id>';

-- Container knows its topology
SELECT topology_id, status, ip_address
FROM emulation_containers
WHERE emulation_id = '<emulation-id>';
```

---

**Ready to implement!** Follow the 5 steps above and refer to [DYNAMIC_CONTAINER_IMPLEMENTATION.md](./DYNAMIC_CONTAINER_IMPLEMENTATION.md) for detailed code.
