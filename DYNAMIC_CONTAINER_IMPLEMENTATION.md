# Dynamic Emulation Container Implementation Guide

## 🎯 Overview

**NEW ARCHITECTURE**: Each topology gets its own dedicated emulation container that is spawned on-demand and tracked in the database.

### Before (Static)
```
docker-compose.yml
    ↓
1 Static Emulation Container (:50051)
    ↓
Handles ALL topologies
```

### After (Dynamic)
```
User creates topology → Stored in PostgreSQL
    ↓
User starts topology → Orchestrator spawns NEW container
    ↓
Container ID stored in database
    ↓
Each topology has its own isolated container
```

---

## 📊 Architecture Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  1. CREATE TOPOLOGY                                             │
├─────────────────────────────────────────────────────────────────┤
│  POST /api/topologies                                           │
│  → topology-service (:8001)                                     │
│  → Save to PostgreSQL                                           │
│  → Returns topology_id                                          │
│  → Status: "created" (no container yet)                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  2. START EMULATION (Spawn Container)                           │
├─────────────────────────────────────────────────────────────────┤
│  POST /api/emulation/start                                      │
│  → orchestrator-service (:8002)                                 │
│  → docker.containers.run(                                       │
│      image="caduceus-emulation:dynamic",                        │
│      name=f"emulation-{topology_id}",                           │
│      environment={                                              │
│        "TOPOLOGY_ID": topology_id,                              │
│        "EMULATION_ID": emulation_id                             │
│      },                                                         │
│      ports={"50051/tcp": random_port},                          │
│      privileged=True,                                           │
│      network_mode="host"                                        │
│    )                                                            │
│  → Store container_id in database                               │
│  → Store port mapping                                           │
│  → Connect to container's gRPC (localhost:random_port)          │
│  → Send topology definition via gRPC                            │
│  → Container creates Mininet-WiFi network                       │
│  → Returns emulation_id + container_id                          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  3. EXECUTE COMMANDS                                            │
├─────────────────────────────────────────────────────────────────┤
│  POST /api/emulation/execute                                    │
│  → orchestrator looks up container_id from database             │
│  → Connects to container's gRPC port                            │
│  → Sends ExecuteCommand RPC                                     │
│  → Returns output                                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  4. STOP EMULATION (Remove Container)                           │
├─────────────────────────────────────────────────────────────────┤
│  POST /api/emulation/stop/{emulation_id}                        │
│  → orchestrator looks up container_id                           │
│  → docker.containers.get(container_id).stop()                   │
│  → docker.containers.get(container_id).remove()                 │
│  → Update database: status="stopped"                            │
│  → Clean up port mappings                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Schema Changes

### Current Schema (PostgreSQL)

**Table: `topologies`**
```sql
CREATE TABLE topologies (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    description TEXT,
    version VARCHAR(50),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### NEW Schema (Add Container Tracking)

**Table: `topologies`** (Add columns)
```sql
ALTER TABLE topologies ADD COLUMN emulation_id VARCHAR(255);
ALTER TABLE topologies ADD COLUMN container_id VARCHAR(255);
ALTER TABLE topologies ADD COLUMN container_name VARCHAR(255);
ALTER TABLE topologies ADD COLUMN container_port INTEGER;
ALTER TABLE topologies ADD COLUMN status VARCHAR(50) DEFAULT 'created';
ALTER TABLE topologies ADD COLUMN started_at TIMESTAMP;
ALTER TABLE topologies ADD COLUMN stopped_at TIMESTAMP;

-- Status values: 'created', 'starting', 'running', 'stopped', 'failed'
```

**Table: `emulation_containers`** (New table for tracking)
```sql
CREATE TABLE emulation_containers (
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

CREATE INDEX idx_emulation_topology ON emulation_containers(topology_id);
CREATE INDEX idx_emulation_container ON emulation_containers(container_id);
```

---

## 📝 Files to Create/Modify

### A. New Dockerfile

**File**: `/emulation-container/Dockerfile.dynamic`
**Status**: ✅ Created

Key changes:
- Based on your working scripts
- Includes Mininet-WiFi + Containernet
- Includes gRPC server
- Environment variables for topology tracking
- Dynamic entrypoint

### B. New Entrypoint Script

**File**: `/emulation-container/scripts/entrypoint-dynamic.sh`
**Status**: ✅ Created

Features:
- WiFi module setup
- Open vSwitch initialization
- Network namespace support
- Topology-specific environment

### C. Database Migration

**File**: `/backend/shared/models/topology.py`
**Action**: Add new fields

```python
from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

class Topology(Base):
    __tablename__ = 'topologies'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    version = Column(String(50))

    # NEW: Container tracking
    emulation_id = Column(String(255), nullable=True)
    container_id = Column(String(255), nullable=True)
    container_name = Column(String(255), nullable=True)
    container_port = Column(Integer, nullable=True)
    status = Column(String(50), default='created')

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)
```

**File**: `/backend/shared/models/emulation_container.py` (NEW)
**Action**: Create new model

```python
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .base import Base

class EmulationContainer(Base):
    __tablename__ = 'emulation_containers'

    id = Column(Integer, primary_key=True)
    emulation_id = Column(String(255), unique=True, nullable=False)
    topology_id = Column(UUID(as_uuid=True), ForeignKey('topologies.id'), nullable=False)
    container_id = Column(String(255), nullable=False)
    container_name = Column(String(255), nullable=False)
    grpc_port = Column(Integer, nullable=False)
    status = Column(String(50), default='starting')
    ip_address = Column(String(50), nullable=True)
    metadata = Column(JSONB, nullable=True)

    created_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime, nullable=True)
    stopped_at = Column(DateTime, nullable=True)

    # Relationship
    topology = relationship("Topology", backref="emulation_containers")
```

### D. Orchestrator Service Updates

**File**: `/backend/services/orchestrator/main.py`
**Location**: Around line 689 (`start_emulation_endpoint`)

**Current Code**:
```python
@app.post("/api/emulation/start", response_model=EmulationControlResponse)
async def start_emulation_endpoint(payload: EmulationStartRequest):
    # ... existing code ...
    grpc = require_grpc_client()  # Connects to static container
    topology_data = await fetch_topology_definition(payload.topology_id)
    result = grpc.start_emulation(payload.topology_id, topology_data)
    # ...
```

**NEW Code** (Dynamic Container Spawning):
```python
import docker
import random

@app.post("/api/emulation/start", response_model=EmulationControlResponse)
async def start_emulation_endpoint(payload: EmulationStartRequest):
    """
    Start emulation by spawning a NEW container for this topology
    """
    if not payload.topology_id:
        raise HTTPException(status_code=400, detail="topology_id is required")

    # Check if already running
    existing = active_emulations.get(payload.topology_id)
    if existing:
        raise HTTPException(status_code=400, detail="Emulation already running")

    # Fetch topology from database
    topology_data = await fetch_topology_definition(payload.topology_id)

    # Generate emulation ID
    emulation_id = f"emul-{uuid.uuid4().hex[:12]}"

    # ========================================================================
    # SPAWN NEW DOCKER CONTAINER
    # ========================================================================

    docker_client = docker.from_env()

    # Find available port (50051-50151 range)
    grpc_port = find_available_port(50051, 50151)

    container_name = f"emulation-{payload.topology_id[:8]}-{emulation_id[:8]}"

    try:
        # Create container
        container = docker_client.containers.run(
            image="caduceus-emulation:dynamic",
            name=container_name,
            environment={
                "TOPOLOGY_ID": payload.topology_id,
                "TOPOLOGY_NAME": topology_data.get('name', 'Unknown'),
                "EMULATION_ID": emulation_id,
                "EMULATION_SERVER_HOST": "0.0.0.0",
                "EMULATION_SERVER_PORT": "50051",
                "LOG_LEVEL": "INFO"
            },
            ports={"50051/tcp": grpc_port},
            privileged=True,
            network_mode="host",  # Required for Mininet
            volumes={
                "/var/run/docker.sock": {"bind": "/var/run/docker.sock", "mode": "rw"},
                "/lib/modules": {"bind": "/lib/modules", "mode": "ro"},
                "/var/lib/caduceus-flux": {"bind": "/var/lib/caduceus-flux", "mode": "rw"},
                "/run": {"bind": "/run", "mode": "rshared"},
                "/sys": {"bind": "/sys", "mode": "rw"}
            },
            detach=True,
            remove=False,  # Keep container for inspection
            auto_remove=False
        )

        logger.info(f"Container spawned: {container.id} ({container_name}) on port {grpc_port}")

        # Wait for container to be healthy (gRPC server ready)
        await wait_for_container_ready(container.id, grpc_port, timeout=60)

    except docker.errors.APIError as e:
        logger.error(f"Failed to spawn container: {e}")
        raise HTTPException(status_code=500, detail=f"Container spawn failed: {str(e)}")

    # ========================================================================
    # CONNECT TO CONTAINER'S gRPC AND SEND TOPOLOGY
    # ========================================================================

    grpc_address = f"localhost:{grpc_port}"
    grpc_client = EmulationGRPCClient(grpc_address)

    try:
        # Send topology to container's gRPC server
        result = grpc_client.start_emulation(payload.topology_id, topology_data)

        if not result.get('success'):
            # Rollback: stop and remove container
            container.stop(timeout=10)
            container.remove()
            raise HTTPException(status_code=500, detail=result.get('message'))

    except Exception as e:
        # Rollback
        container.stop(timeout=10)
        container.remove()
        raise HTTPException(status_code=500, detail=f"gRPC communication failed: {str(e)}")

    # ========================================================================
    # SAVE TO DATABASE
    # ========================================================================

    # Update topology record
    await update_topology_container_info(
        topology_id=payload.topology_id,
        emulation_id=emulation_id,
        container_id=container.id,
        container_name=container_name,
        container_port=grpc_port,
        status="running"
    )

    # Create emulation_container record
    await create_emulation_container_record(
        emulation_id=emulation_id,
        topology_id=payload.topology_id,
        container_id=container.id,
        container_name=container_name,
        grpc_port=grpc_port,
        status="running",
        ip_address=container.attrs['NetworkSettings'].get('IPAddress', 'N/A')
    )

    # Track in Redis
    record = record_active_emulation(
        topology_id=payload.topology_id,
        emulation_id=emulation_id,
        topology_data=topology_data,
        options=payload.options or {},
        status_value="running",
        container_id=container.id,
        container_name=container_name,
        grpc_port=grpc_port
    )

    # Publish event
    try:
        rabbitmq_publisher.publish("emulation.started", {
            'topology_id': payload.topology_id,
            'emulation_id': emulation_id,
            'container_id': container.id,
            'container_name': container_name,
            'grpc_port': grpc_port,
            'started_at': record.get('started_at')
        })
    except Exception as exc:
        logger.error(f"Failed to publish event: {exc}")

    logger.info(f"Emulation {emulation_id} started in container {container.id}")

    return EmulationControlResponse(
        success=True,
        message=f"Emulation started in container {container_name}",
        emulation_id=emulation_id,
        container_id=container.id,
        container_name=container_name,
        grpc_port=grpc_port
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def find_available_port(start_port: int, end_port: int) -> int:
    """Find an available port in the given range"""
    import socket
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(('localhost', port)) != 0:
                return port
    raise RuntimeError("No available ports in range")


async def wait_for_container_ready(container_id: str, grpc_port: int, timeout: int = 60):
    """Wait for container's gRPC server to be ready"""
    import time
    import grpc

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            channel = grpc.insecure_channel(f'localhost:{grpc_port}')
            grpc.channel_ready_future(channel).result(timeout=5)
            logger.info(f"Container {container_id} is ready")
            return
        except Exception as e:
            logger.debug(f"Waiting for container... ({e})")
            await asyncio.sleep(2)

    raise TimeoutError(f"Container {container_id} did not become ready within {timeout}s")


async def update_topology_container_info(topology_id, emulation_id, container_id,
                                         container_name, container_port, status):
    """Update topology record with container information"""
    async with httpx.AsyncClient() as client:
        await client.put(
            f"{TOPOLOGY_SERVICE_URL}/api/topologies/{topology_id}",
            json={
                "emulation_id": emulation_id,
                "container_id": container_id,
                "container_name": container_name,
                "container_port": container_port,
                "status": status,
                "started_at": datetime.now(timezone.utc).isoformat()
            }
        )


async def create_emulation_container_record(emulation_id, topology_id, container_id,
                                            container_name, grpc_port, status, ip_address):
    """Create emulation_container record in database"""
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{TOPOLOGY_SERVICE_URL}/api/emulation-containers",
            json={
                "emulation_id": emulation_id,
                "topology_id": topology_id,
                "container_id": container_id,
                "container_name": container_name,
                "grpc_port": grpc_port,
                "status": status,
                "ip_address": ip_address,
                "started_at": datetime.now(timezone.utc).isoformat()
            }
        )
```

### E. Stop Emulation Updates

**File**: `/backend/services/orchestrator/main.py`
**Location**: Around line 1151 (`stop_emulation_endpoint`)

**NEW Code**:
```python
@app.post("/api/emulation/stop/{emulation_id}", response_model=EmulationControlResponse)
async def stop_emulation_endpoint(emulation_id: str, payload: EmulationStopRequest):
    """
    Stop emulation and remove its container
    """
    # Get container info from database/Redis
    emulation_info = get_active_emulation_by_id(emulation_id)
    if not emulation_info:
        raise HTTPException(status_code=404, detail="Emulation not found")

    container_id = emulation_info.get('container_id')
    topology_id = emulation_info.get('topology_id')

    if not container_id:
        raise HTTPException(status_code=400, detail="No container associated with this emulation")

    # Stop and remove container
    docker_client = docker.from_env()

    try:
        container = docker_client.containers.get(container_id)

        logger.info(f"Stopping container {container_id}...")
        container.stop(timeout=10)

        if payload.cleanup:
            logger.info(f"Removing container {container_id}...")
            container.remove()

    except docker.errors.NotFound:
        logger.warning(f"Container {container_id} not found (may already be removed)")
    except Exception as e:
        logger.error(f"Error stopping container: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop container: {str(e)}")

    # Update database
    await update_topology_status(topology_id, "stopped")
    await update_emulation_container_status(emulation_id, "stopped")

    # Remove from Redis
    remove_active_emulation_by_id(emulation_id)

    # Publish event
    try:
        rabbitmq_publisher.publish("emulation.stopped", {
            'emulation_id': emulation_id,
            'topology_id': topology_id,
            'container_id': container_id,
            'stopped_at': datetime.now(timezone.utc).isoformat()
        })
    except Exception as exc:
        logger.error(f"Failed to publish event: {exc}")

    return EmulationControlResponse(
        success=True,
        message=f"Emulation stopped and container removed",
        emulation_id=emulation_id
    )
```

---

## 🔨 Build and Deploy

### Step 1: Build Dynamic Image

```bash
cd /home/ege/Desktop/cadeceus-flux-mininet-from-strach/caduceus-flux

# Build the dynamic emulation image
docker build \
  -f emulation-container/Dockerfile.dynamic \
  -t caduceus-emulation:dynamic \
  .
```

### Step 2: Remove Static Container from docker-compose.yml

**File**: `docker-compose.yml`

**Remove** (or comment out) the static emulation-container service we added earlier:
```yaml
# emulation-container:  # REMOVED - now spawned dynamically
#   build: ...
```

### Step 3: Update Dependencies

**File**: `backend/services/orchestrator/requirements.txt`

Add:
```
docker==6.1.3
```

### Step 4: Apply Database Migrations

```bash
# Connect to PostgreSQL
docker exec -it caduceus-postgres psql -U caduceus -d caduceus_flux

# Run migrations
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
```

### Step 5: Rebuild Orchestrator

```bash
# Rebuild orchestrator service with new code
docker compose build orchestrator-service

# Restart
docker compose up -d orchestrator-service
```

---

## 🧪 Testing

### Test 1: Create Topology
```bash
curl -X POST http://localhost:8001/api/topologies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Network",
    "nodes": [
      {"name": "h1", "device_type": "host", "properties": {"ip": "10.0.0.1/24"}},
      {"name": "s1", "device_type": "switch", "properties": {"switch_type": "ovs"}}
    ],
    "links": [{"source_node_id": "h1", "target_node_id": "s1"}]
  }'
```

**Expected**: Returns `topology_id`, status="created"

### Test 2: Start Emulation (Spawn Container)
```bash
TOPO_ID="your-topology-id"

curl -X POST http://localhost:8002/api/emulation/start \
  -H "Content-Type: application/json" \
  -d "{\"topology_id\": \"$TOPO_ID\"}"
```

**Expected**:
- Returns `emulation_id`, `container_id`, `container_name`, `grpc_port`
- New container appears: `docker ps | grep emulation-`
- Database updated with container info

### Test 3: Verify Container
```bash
# List running emulation containers
docker ps | grep emulation-

# Check container logs
docker logs emulation-<id>

# Verify gRPC is running
docker exec emulation-<id> netstat -tlnp | grep 50051
```

### Test 4: Execute Command
```bash
curl -X POST http://localhost:8002/api/emulation/execute \
  -H "Content-Type: application/json" \
  -d '{
    "device_name": "h1",
    "command": "ifconfig"
  }'
```

### Test 5: Stop Emulation (Remove Container)
```bash
EMUL_ID="your-emulation-id"

curl -X POST http://localhost:8002/api/emulation/stop/$EMUL_ID \
  -H "Content-Type: application/json" \
  -d '{"cleanup": true}'
```

**Expected**:
- Container stopped and removed
- Database status updated to "stopped"

### Test 6: Multiple Topologies
```bash
# Start 3 topologies simultaneously
for i in 1 2 3; do
  curl -X POST http://localhost:8002/api/emulation/start \
    -H "Content-Type: application/json" \
    -d "{\"topology_id\": \"topology-$i\"}" &
done

# Verify 3 containers running
docker ps | grep emulation-
```

---

## 📊 Benefits

✅ **Isolation**: Each topology runs in its own container
✅ **Scalability**: Multiple topologies can run concurrently
✅ **Resource Management**: Easy to limit per-topology resources
✅ **State Tracking**: Database knows which container serves which topology
✅ **Clean Shutdown**: Removing topology removes its container
✅ **Port Management**: Each container gets unique gRPC port
✅ **Debugging**: Easy to inspect individual topology containers

---

## ⚠️ Important Notes

1. **Host Setup Required**: WiFi modules still need host-level setup:
   ```bash
   sudo modprobe mac80211_hwsim radios=4
   ```

2. **Privileged Mode**: Containers need `privileged: true` for Mininet

3. **Network Mode**: Must use `network_mode: host` for proper namespace access

4. **Port Range**: Reserve ports 50051-50151 for emulation containers

5. **Resource Limits**: Add CPU/memory limits per container:
   ```python
   container = docker_client.containers.run(
       mem_limit="2g",
       cpu_quota=100000,  # 1 CPU core
       ...
   )
   ```

6. **Cleanup**: Implement cleanup job to remove orphaned containers

---

## 🎯 Next Steps

1. ✅ Dockerfile.dynamic created
2. ✅ Entrypoint script created
3. ⏳ Update orchestrator service (code provided above)
4. ⏳ Apply database migrations
5. ⏳ Build and test

**Start with**: Build the dynamic image and test container spawning manually before integrating with orchestrator.

---

**Files Created**:
- `/emulation-container/Dockerfile.dynamic`
- `/emulation-container/scripts/entrypoint-dynamic.sh`
- `/DYNAMIC_CONTAINER_IMPLEMENTATION.md` (this file)

**Ready for implementation!** 🚀
