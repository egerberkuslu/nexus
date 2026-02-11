# Topology and Container Spawning Design Guide

## Overview

This guide explains the current architecture of topology creation, storage, and emulation in Caduceus-Flux, with specific focus on how to redesign it for dynamic container spawning.

## Quick Navigation

1. **[TOPOLOGY_ANALYSIS.md](TOPOLOGY_ANALYSIS.md)** - Complete detailed analysis
   - PostgreSQL schema deep dive
   - gRPC communication flow
   - Redis tracking mechanism
   - Missing fields for container tracking
   - 9 sections with code examples

2. **[CONTAINER_SPAWNING_GUIDE.md](CONTAINER_SPAWNING_GUIDE.md)** - Implementation guide
   - Quick reference summary
   - Files to modify
   - Integration points
   - Testing procedures
   - Risk assessment

## Architecture Summary

```
┌─────────────────────┐
│  Frontend (React)   │
└──────────┬──────────┘
           │ HTTP/REST
           ↓
┌─────────────────────────────────────────────┐
│   Topology Service (Port 8001)              │
│   - CRUD for topologies                     │
│   - PostgreSQL: topologies, nodes, links    │
│   - JSON export/import                      │
└──────┬──────────────────────────────────────┘
       │
       │ REST
       ↓
┌─────────────────────────────────────────────┐
│   Orchestrator Service (Port 8002)          │
│   - Emulation lifecycle management          │
│   - Redis: active emulation tracking        │
│   - gRPC client                             │
└──────┬──────────────────────────────────────┘
       │
       │ gRPC
       ↓
┌─────────────────────────────────────────────┐
│   Emulation Container (Port 50051)          │
│   - Mininet network emulation               │
│   - Docker daemon integration               │
│   - Device and link management              │
└─────────────────────────────────────────────┘
```

## Data Storage

### PostgreSQL (Persistent)

**Topology Table**
```sql
- id (UUID, PK)
- project_id (FK)
- name
- description
- version (incremented on changes)
- is_active (current emulation state)
- emulation_status (STOPPED, STARTING, RUNNING, PAUSED, ERROR)
- created_at, updated_at
- metadata (JSON)
-- MISSING: emulation_id, container_host, created_container_count
```

**Node Table**
```sql
- id (UUID, PK)
- topology_id (FK)
- name
- device_type (ENUM: host, switch, router, ap, station, container, p4switch)
- x, y (canvas position)
- properties (JSON) -- FLEXIBLE
  - image: Docker image name
  - command: Startup command
  - environment: Env vars
  - volumes: Volume mounts
  -- MISSING: container_id, container_ip, container_status
```

**Link Table**
```sql
- source_node_id, target_node_id (FK)
- bandwidth (Mbps)
- delay (ms)
- loss (%)
- max_queue_size
- status (UP, DOWN)
- properties (JSON)
```

### Redis (Ephemeral)

**Active Emulations Hash**
```
Key: "active_emulations"
Field: topology_id
Value: {
    topology_id,
    topology_name,
    emulation_id,           # <<<< KEY FIELD
    status,
    started_at,
    last_updated,
    options,
    node_count,
    link_count
    -- MISSING: container_host, device_container_map
}
```

### In-Memory (gRPCClient)

```python
node_id_to_runtime = {
    'topology_node_id': 'sanitized_runtime_name',
    'display_name': 'sanitized_runtime_name'
}
-- MISSING: node_id_to_container_id mapping
```

## API Flow for Container Spawning

### 1. Create Topology with Container
```http
POST /api/topologies
{
    "project_id": "proj-uuid",
    "name": "My Network",
    "nodes": [{
        "name": "web-app",
        "device_type": "container",
        "x": 100, "y": 100,
        "properties": {
            "image": "ubuntu:22.04",
            "command": "sleep 1000",
            "environment": {"LOG_LEVEL": "debug"},
            "volumes": ["/tmp:/tmp"]
        }
    }]
}
```

Response: TopologyResponse with nodes list
- Topology stored in PostgreSQL
- No emulation yet

### 2. Start Emulation
```http
POST /api/emulation/start
{
    "topology_id": "topo-uuid",
    "options": {}
}
```

Flow:
1. Orchestrator fetches topology from Topology Service
2. Orchestrator sends to gRPC: StartEmulationRequest
   - All nodes + links in TopologyDefinition proto format
   - Container nodes converted via AddDockerContainerRequest
3. gRPC container spawns Mininet + Docker containers
4. gRPC returns emulation_id
5. Orchestrator records in Redis

Return: EmulationControlResponse
```json
{
    "success": true,
    "emulation_id": "emulation-uuid"
}
```

**Missing**: No way to get container IDs back

### 3. Apply Dynamic Changes (Add Container)
```http
POST /api/topologies/{topology_id}/apply
{
    "changes": {
        "add_devices": [{
            "name": "db-server",
            "device_type": "container",
            "properties": {
                "image": "postgres:15",
                "command": "postgres",
                "environment": {"POSTGRES_PASSWORD": "secret"}
            }
        }]
    }
}
```

Flow:
1. Fetch active emulation from Redis
2. For each add_devices:
   - Build AddDockerContainerRequest with properties
   - Call gRPC AddDockerContainer
   - **MISSING**: Capture returned container_id
   - Call topology service to persist in Node.properties
3. If any fail, rollback all changes
4. Update Redis active emulation metadata

Return: TopologyResponse with updated nodes

**Missing**: 
- No persistence of container_id from gRPC response
- No way to correlate node_id -> container_id

### 4. List Devices
```http
GET /api/emulation/devices?device_type=container
```

gRPC ListDevices returns all running devices
- Shows runtime_name, type, status, IP
- **Missing**: container_id not in response

**After Enhancement:**
Should include:
- container_id (Docker container ID)
- container_ip (172.17.0.x)
- container_status (running, exited, etc.)
- port_mappings

### 5. Stop Emulation
```http
POST /api/emulation/stop/{emulation_id}
{
    "cleanup": true
}
```

Flow:
1. Call gRPC StopEmulation
2. Remove from Redis active emulations
3. **Missing**: Should clear emulation_id from Topology table
4. **Missing**: Should clean up container metadata from Node.properties

## Critical Gaps for Production

### 1. Container ID Tracking

**Current Problem:**
- Docker spawns containers via gRPC
- Container IDs are not returned to orchestrator
- No way to look up: "Which Docker container corresponds to node X?"
- Service restart loses all in-memory mappings

**Impact on Dynamic Spawning:**
- Can't remove specific containers (don't know container ID)
- Can't monitor container health (don't have container ID)
- Can't restart failed containers (lost the ID)

**Solution:**
1. Extend gRPC proto to return container_id in AddDockerContainerResponse
2. Store container_id in Node.properties after creation
3. Maintain mapping in Redis: node_id -> container_id
4. Query topology service to recover state after restart

### 2. Emulation-Topology Linkage

**Current Problem:**
- Topology has is_active flag but no emulation_id
- Only Redis knows which topology -> emulation_id
- Redis data is ephemeral (lost on restart)

**Impact on Dynamic Spawning:**
- Can't verify which emulation is running for a topology
- Can't properly cleanup on service restart
- Can't persist emulation context

**Solution:**
1. Add emulation_id column to Topology table
2. Update when emulation starts
3. Clear when emulation stops
4. Use for validation in apply_changes

### 3. Container State Persistence

**Current Problem:**
- Node.properties can store container_id but API doesn't populate it
- Container IP addresses are dynamic but not stored
- No last-known status tracking

**Impact on Dynamic Spawning:**
- UI can't show container IPs
- Can't track container history/status
- Can't correlate failures

**Solution:**
1. After AddDockerContainer response, update Node.properties with:
   - container_id
   - container_ip
   - container_status
   - created_timestamp
2. Periodically sync status from gRPC
3. Show in UI for debugging

### 4. gRPC Response Enhancement

**Current Problem:**
- AddDockerContainerResponse doesn't return container_id
- No metadata about spawned container
- No way to query container details later

**Impact on Dynamic Spawning:**
- Orchestrator can't know what was created
- No way to correlate request -> actual container

**Solution:**
1. Extend proto DeviceResponse to include:
   - container_id
   - container_name
   - ip_address
   - metadata (dict)
2. Update gRPC container backend to populate
3. Orchestrator captures and persists

## Implementation Roadmap

### Phase 1: Database & Redis Enhancements (Low Risk)
- Add emulation_id to Topology table (nullable for backward compat)
- Enhance Redis record structure for device_container_map
- No API changes needed

### Phase 2: Container Metadata Capture (Medium Risk)
- Update add_device_to_emulation() to persist container metadata
- Store in Node.properties after gRPC response
- Update topology service with new properties

### Phase 3: gRPC Response Enhancement (Medium Risk)
- Extend proto messages to return container details
- Update emulation container backend to populate
- Handle backward compatibility

### Phase 4: State Synchronization (Low Risk)
- Periodic sync of container status from gRPC
- Recovery of state on service restart
- Health monitoring

## Files You'll Need to Modify

### Must Modify
1. `/backend/shared/models/topology.py` - Add emulation_id column
2. `/backend/services/orchestrator/main.py` - Capture container_id in add_device_to_emulation()
3. `/backend/proto/emulation.proto` - Extend DeviceResponse (if supporting multi-container)

### Should Consider
4. `/backend/shared/schemas/topology_schema.py` - Update TopologyResponse schema
5. `/backend/services/topology/main.py` - Handle emulation_id in endpoints
6. Migration files - For database schema changes

### Optional Enhancement
7. `/backend/proto/emulation.proto` - Extend to return full DeviceResponse

## Testing Checklist

- [ ] Create topology with container node
- [ ] Start emulation
- [ ] Verify container is running (docker ps)
- [ ] Check Node.properties has container_id
- [ ] Add container dynamically via apply
- [ ] Verify new container created
- [ ] Remove container via apply
- [ ] Verify container cleaned up
- [ ] Stop emulation
- [ ] Verify cleanup completed

## References

- Detailed Analysis: See [TOPOLOGY_ANALYSIS.md](TOPOLOGY_ANALYSIS.md)
- Implementation Guide: See [CONTAINER_SPAWNING_GUIDE.md](CONTAINER_SPAWNING_GUIDE.md)
- Emulation Architecture: See [EMULATION_ARCHITECTURE.md](EMULATION_ARCHITECTURE.md)

## Key Code Locations

| Component | File | Lines |
|-----------|------|-------|
| Topology Model | `backend/shared/models/topology.py` | 53-72 |
| Start Emulation | `backend/services/orchestrator/main.py` | 689-776 |
| Add Device | `backend/services/orchestrator/main.py` | 1422-1640 |
| Active Store | `backend/services/orchestrator/main.py` | 105-145 |
| Docker Request | `backend/proto/emulation.proto` | 174-181 |

