# QUICK REFERENCE: Container Spawning for Caduceus-Flux

## Current Flow Summary

1. **Topology Created** (PostgreSQL)
   - Nodes stored with device_type and properties
   - Containers defined via: device_type="container", properties={image, command, env, volumes}

2. **Start Emulation** (Orchestrator Port 8002)
   - Fetch topology from Topology Service (Port 8001)
   - Send to gRPC Emulation Container (Port 50051)
   - Get back emulation_id
   - Store emulation_id in Redis (NOT in PostgreSQL)

3. **Container Management**
   - Docker SDK installed but not used in orchestrator
   - Actual container spawning happens in gRPC container backend
   - Node-to-runtime mapping tracked in-memory only
   - No persistent record of container IDs

4. **Apply Dynamic Changes**
   - Use TopologyApplyRequest with add_devices/remove_devices
   - Call gRPC AddDockerContainer/RemoveDevice
   - Update PostgreSQL topology
   - Update Redis active emulation

## What's Missing for Production Container Spawning

### 1. Database Tracking
- PostgreSQL Topology table lacks emulation_id field
- Node properties don't store returned container_id
- No container_host tracking for distributed spawning
- No container_status or container_ip fields

### 2. Redis Tracking
- Only has emulation_id -> topology_id mapping
- Missing node_id -> container_id mapping
- No container host information
- No port mapping tracking

### 3. gRPC Response Enhancement
- AddDockerContainerResponse doesn't return container_id
- No way to query created container metadata
- Missing container_name from response

## Files to Modify for Full Container Tracking

### A. Database Models
File: `/backend/shared/models/topology.py`

Add to Topology class:
```python
emulation_id = Column(String(36), nullable=True)  # Link to active emulation
container_host = Column(String(255))  # Which host running emulation
created_container_count = Column(Integer, default=0)
```

### B. Orchestrator Service
File: `/backend/services/orchestrator/main.py`

Update record_active_emulation() to include:
```python
'device_container_map': {},  # node_id -> container_id
'node_runtime_map': {},      # node_id/name -> runtime_name
'container_host': None       # Host running containers
```

Update add_device_to_emulation() to capture and persist:
```python
# After gRPC response, store container_id in node properties
device_properties['container_id'] = response.container_id
device_properties['container_name'] = response.container_name
device_properties['container_ip'] = response.ip_address
```

### C. Schema Updates
File: `/backend/shared/schemas/topology_schema.py`

The EmulationStartRequest and EmulationControlResponse already work well. No changes needed there.

### D. Proto Extension (Optional)
File: `/backend/proto/emulation.proto`

Extend DeviceResponse message:
```protobuf
message DeviceResponse {
    bool success = 1;
    string message = 2;
    Device device = 3;
    string container_id = 4;      // NEW
    string container_name = 5;    // NEW
    string ip_address = 6;        // NEW
    map<string, string> metadata = 7;  // NEW
}
```

## Key Integration Points

### 1. Start Emulation Flow
- Line 689-776: start_emulation_endpoint()
- Needs to update topology.emulation_id after gRPC success
- Store container_host from environment variable

### 2. Add Device Dynamically
- Line 1422-1640: add_device_to_emulation()
- Currently: Updates node in-memory and Redis only
- Need: Update Node.properties with container_id after creation
- Need: Call topology service to update node properties

### 3. Apply Changes
- Line 779-1148: apply_topology_changes_endpoint()
- Already handles rollback on failure (good!)
- Need: Capture container IDs from AddDockerContainer response
- Need: Persist container IDs back to topology service

### 4. Stop Emulation
- Line 1151-1186: stop_emulation_endpoint()
- Currently: Just stops gRPC emulation
- Need: Clear emulation_id from topology table
- Need: Optionally clean up container metadata from nodes

## Data Flow Diagram

```
User Creates Container Node
    ↓
POST /api/topologies/{topology_id}/apply
    ├─ Send to gRPC: AddDockerContainerRequest
    │   ├─ image, command, env, volumes
    │   └─ Returns: container_id, container_name, ip_address
    │
    ├─ Store in Redis:
    │   └─ device_container_map[node_id] = container_id
    │
    ├─ Store in PostgreSQL:
    │   ├─ Node.properties.container_id = "sha256:..."
    │   ├─ Node.properties.container_ip = "172.17.0.2"
    │   └─ Topology.emulation_id = "emulation-uuid"
    │
    └─ Return: Node with updated properties
        └─ Frontend shows container_id, status, IP
```

## Testing Container Spawning

### 1. Create Container Node
```bash
POST /api/topologies/{topology_id}/apply
{
    "changes": {
        "add_devices": [{
            "name": "app1",
            "device_type": "container",
            "properties": {
                "image": "ubuntu:22.04",
                "command": "sleep 1000",
                "environment": {"DEBUG": "1"},
                "volumes": ["/tmp:/tmp"]
            }
        }]
    }
}
```

### 2. Verify Container Started
```bash
GET /api/emulation/devices?device_type=container
# Should show container_id, container_ip
```

### 3. Query Node Properties
```bash
GET /api/topologies/{topology_id}/nodes/{node_id}
# Should include container_id, container_ip in properties
```

### 4. Remove Container
```bash
POST /api/topologies/{topology_id}/apply
{
    "changes": {
        "remove_devices": [{
            "id": "{node_id}"
        }]
    }
}
```

## Dependencies Already Available

- docker==7.0.0 (in backend/requirements.txt) - NOT used yet in orchestrator
- grpcio & protobuf - Already in use
- Redis - Already in use for tracking
- PostgreSQL - Already in use

## Risk Assessment

**Low Risk Changes:**
- Adding fields to Node.properties (already flexible JSON)
- Adding fields to Redis emulation records
- Using docker SDK in orchestrator (SDK already installed)

**Medium Risk Changes:**
- Adding columns to Topology table (needs migration)
- Extending gRPC proto (backward compatibility)

**Mitigation:**
- Test with container devices first (before commit)
- Use feature flag if possible
- Keep in-memory mappings as fallback
