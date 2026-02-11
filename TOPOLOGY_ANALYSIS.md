# Caduceus-Flux: Current Topology Creation, Storage, and Emulation Flow Analysis

## Executive Summary

This document provides a detailed analysis of how topologies are created, stored, and emulated in the Caduceus-Flux system. The architecture uses a microservices approach with PostgreSQL for persistent storage, Redis for active emulation tracking, and gRPC for communication with the emulation container.

---

## 1. TOPOLOGY SERVICE (Port 8001)

### Location
- **Main**: `/backend/services/topology/main.py`
- **Schemas**: `/backend/shared/schemas/topology_schema.py`
- **Models**: `/backend/shared/models/topology.py`

### 1.1 Database Models (PostgreSQL)

#### Topology Model
```python
class Topology(Base):
    __tablename__ = "topologies"
    
    id = Column(String(36), primary_key=True)                    # UUID
    project_id = Column(String(36), ForeignKey("projects.id"))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    version = Column(Integer, default=1)
    is_active = Column(Boolean, default=False)                   # <<<< Active emulation flag
    emulation_status = Column(Enum(EmulationStatus), default=EmulationStatus.STOPPED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    topology_metadata = Column('metadata', JSON, default=dict)
```

**Key Fields for Container Tracking:**
- `is_active`: Indicates if topology has an active emulation
- `emulation_status`: Current status (STOPPED, STARTING, RUNNING, PAUSED, STOPPING, ERROR)
- **MISSING**: `emulation_id` field - This is NOT in PostgreSQL topology model
- **MISSING**: `container_id` field - No direct Docker container tracking in database
- **MISSING**: `container_name` field - No container name mapping in database

#### Node Model
```python
class Node(Base):
    __tablename__ = "nodes"
    
    id = Column(String(36), primary_key=True)
    topology_id = Column(String(36), ForeignKey("topologies.id"))
    name = Column(String(255), nullable=False)
    device_type = Column(Enum(DeviceType, values_callable=lambda x: [e.value for e in x]))
    x = Column(Float, default=0)
    y = Column(Float, default=0)
    properties = Column(JSON, default={})                        # Flexible field
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
```

**Important for Container Spawning:**
- `properties` JSON field can store Docker-specific metadata:
  - `image`: Docker image name
  - `command`: Container startup command
  - `environment`: Environment variables (stored as dict/string)
  - `volumes`: Volume mounts
  - `container_id`: Can be stored here after spawning
  - `runtime_name`: Mininet runtime name

#### Link Model
```python
class Link(Base):
    __tablename__ = "links"
    
    id = Column(String(36), primary_key=True)
    topology_id = Column(String(36), ForeignKey("topologies.id"))
    source_node_id = Column(String(36), ForeignKey("nodes.id"))
    target_node_id = Column(String(36), ForeignKey("nodes.id"))
    source_port = Column(String(50))
    target_port = Column(String(50))
    bandwidth = Column(Float)                                     # Mbps
    delay = Column(Float)                                         # ms
    loss = Column(Float)                                          # percentage
    max_queue_size = Column(Integer)
    status = Column(Enum(LinkStatus), default=LinkStatus.UP)
    properties = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
```

### 1.2 Topology Storage Fields

| Field | Type | Purpose | For Container Spawning |
|-------|------|---------|------------------------|
| id | String(36) | Primary key UUID | Parent ID for containers |
| project_id | String(36) | Project reference | Context for emulation |
| name | String(255) | Display name | User-friendly reference |
| version | Integer | Schema version | Track changes |
| is_active | Boolean | Emulation state | Track if running |
| emulation_status | Enum | Status tracking | Current state |
| **MISSING** | **N/A** | **Emulation ID** | **Link to active emulation** |
| **MISSING** | **N/A** | **Container ID** | **Docker container ID** |
| **MISSING** | **N/A** | **Container Name** | **Docker container name** |

### 1.3 Current API Endpoints

#### Create Topology
```
POST /api/topologies
Payload: TopologyCreate {
    project_id: str
    name: str
    description: Optional[str]
    nodes: List[NodeCreate]
    links: List[LinkCreate]
    controllers: List[ControllerCreate]
}
Response: TopologyResponse with full topology structure
```

#### Update Topology
```
PUT /api/topologies/{topology_id}
Payload: dict with nodes/links arrays
Response: TopologyResponse
```

#### Apply Staged Changes
```
POST /api/topologies/{topology_id}/apply
Payload: TopologyApplyRequest {
    changes: TopologyChangeSet {
        add_devices: List[NodeDelta]
        update_devices: List[NodeUpdateDelta]
        remove_devices: List[NodeIdentifier]
        add_links: List[LinkDelta]
        update_links: List[LinkUpdateDelta]
        remove_links: List[LinkIdentifier]
    }
    commit: bool
}
Response: TopologyResponse
```

---

## 2. ORCHESTRATOR SERVICE (Port 8002)

### Location
- **Main**: `/backend/services/orchestrator/main.py`
- **Line Range**: Lines 690-776 (start_emulation_endpoint)
- **Additional**: Lines 1422-1640 (add_device_to_emulation), Lines 1642-1680 (remove_device_from_emulation)

### 2.1 Emulation Start Flow

#### Endpoint: POST /api/emulation/start
```python
async def start_emulation_endpoint(payload: EmulationStartRequest):
    """Start a new emulation for a given topology."""
    # Line 690-776
    
    grpc = require_grpc_client()
    
    # Check if emulation already running (Line 699-731)
    existing = active_emulations.get(payload.topology_id)
    if existing:
        return existing emulation
    
    # Fetch topology definition from topology service (Line 733)
    topology_data = await fetch_topology_definition(payload.topology_id)
    
    # Call gRPC to start emulation (Line 734)
    result = grpc.start_emulation(payload.topology_id, topology_data)
    
    if not result.get('success'):
        raise HTTPException(500, error_message)
    
    # Record in Redis (Line 745-751)
    emulation_id = result.get('emulation_id')
    record = record_active_emulation(
        topology_id=payload.topology_id,
        emulation_id=emulation_id,
        topology_data=topology_data,
        options=payload.options,
        status_value="running"
    )
    
    # Publish event (Line 754-762)
    rabbitmq_publisher.publish("emulation.started", {...})
    
    return EmulationControlResponse(
        success=True,
        emulation_id=emulation_id
    )
```

### 2.2 gRPC StartEmulation Call

#### gRPCClient.start_emulation() - Line 344-393
```python
def start_emulation(self, topology_id: str, topology_data: Dict) -> Dict:
    """Start emulation via gRPC"""
    
    # Build node ID to name mapping (Line 350-360)
    nodes = topology_data.get('nodes', topology_data.get('devices', []))
    self.node_id_to_runtime = {}  # Maps UUID -> runtime name
    for node in nodes:
        node_id = node.get('id')
        node_name = node.get('name')
        runtime_name = _runtime_device_name(node_id, node_name)
        self.node_id_to_runtime[node_id] = runtime_name
        self.node_id_to_runtime[node_name] = runtime_name
    
    # Build protobuf TopologyDefinition (Line 368-376)
    topology_def = emulation_pb2.TopologyDefinition(
        devices=[self._convert_device(d) for d in nodes],
        links=[self._convert_link(l) for l in topology_data.get('links', [])],
        controllers=[self._convert_controller(c) for c in topology_data.get('controllers', [])]
    )
    
    # Create gRPC request (Line 378-385)
    request = emulation_pb2.StartEmulationRequest(
        topology_id=topology_id,
        topology=topology_def
    )
    
    # Call gRPC (Line 387)
    response = self.stub.StartEmulation(request)
    
    return {
        'success': response.success,
        'message': response.message,
        'emulation_id': response.emulation_id  # <<<< emulation_id comes back
    }
```

### 2.3 Active Emulation Tracking

#### Redis Storage (Line 105-145)
```python
class ActiveEmulationStore:
    """Manages active emulation state in Redis"""
    
    def get(self, topology_id: str) -> Optional[Dict[str, Any]]:
        """Get emulation info for topology_id"""
        emulation_data = self.client.hget(ACTIVE_EMULATIONS_KEY, topology_id)
        return json.loads(emulation_data) if emulation_data else None
    
    def set(self, topology_id: str, emulation_info: Dict[str, Any]):
        """Set emulation info"""
        self.client.hset(ACTIVE_EMULATIONS_KEY, topology_id, json.dumps(emulation_info))
    
    def find_by_emulation_id(self, emulation_id: str) -> Optional[str]:
        """Find topology_id by emulation_id"""
        for topology_id, info in self.get_all().items():
            if info.get('emulation_id') == emulation_id:
                return topology_id
        return None
```

#### Emulation Record Structure (Line 244-264)
```python
def record_active_emulation(
    topology_id: str,
    emulation_id: str,
    topology_data: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None,
    status_value: str = "running"
) -> Dict[str, Any]:
    """Persist active emulation metadata in Redis."""
    
    record = {
        'topology_id': topology_id,
        'topology_name': topology_data.get('name'),
        'emulation_id': emulation_id,              # <<<< KEY FIELD
        'status': status_value,
        'started_at': _iso_now(),
        'last_updated': _iso_now(),
        'options': options or {},
        'node_count': len(topology_data.get('nodes', [])),
        'link_count': len(topology_data.get('links', []))
    }
    active_emulations.set(topology_id, record)
    return record
```

**Redis Hash Structure:**
```
Key: "active_emulations"
Field: topology_id (String)
Value: {
    "topology_id": "uuid",
    "topology_name": "name",
    "emulation_id": "uuid",           # <<<< Links to gRPC emulation
    "status": "running|paused|stopped",
    "started_at": "ISO8601",
    "last_updated": "ISO8601",
    "options": {...},
    "node_count": int,
    "link_count": int
}
```

### 2.4 Container Management Functions

#### Add Device to Emulation (Line 1422-1640)
```python
async def add_device_to_emulation(topology_id: str, device_data: Dict):
    """Add a new device to running emulation"""
    
    device_name = device_data.get('name')
    device_type = device_data.get('type', device_data.get('device_type', ''))
    device_properties = device_data.get('properties', {})
    device_id = device_data.get('id') or device_properties.get('node_id')
    
    # Resolve runtime name (Line 1439-1444)
    runtime_name = resolve_runtime_name(node_id_value, device_name)
    
    # Handle Docker Container Type (Line 1568-1608)
    if device_type.lower() in ['docker', 'container']:
        command_value = device_properties.get('command')
        environment = device_properties.get('environment') or {}
        volumes = device_properties.get('volumes') or []
        
        request = emulation_pb2.AddDockerContainerRequest(
            name=runtime_name,
            image=device_properties.get('image') or 'ubuntu:22.04'
        )
        if command_list:
            request.command.extend(command_list)
        for key, value in environment.items():
            request.environment[str(key)] = str(value)
        for volume in volumes:
            request.volumes.append(str(volume))
        for key, value in device_properties.items():
            request.params[key] = str(value)
        attach_common_params(request.params)
        
        response = grpc_client.stub.AddDockerContainer(request)
    
    # Store runtime name mapping (Line 1626-1631)
    if response.success:
        grpc_client.node_id_to_runtime[node_id_value] = runtime_name
        grpc_client.node_id_to_runtime[device_name] = runtime_name
        return True
    else:
        logger.error(f"Failed to add device: {response.message}")
        return False
```

#### Remove Device from Emulation (Line 1642-1680)
```python
async def remove_device_from_emulation(
    topology_id: str,
    device_name: str,
    device_id: Optional[str] = None
):
    """Remove a device from running emulation"""
    
    # Resolve runtime name (Line 1651-1655)
    runtime_name = None
    if device_id and grpc_client:
        runtime_name = grpc_client.node_id_to_runtime.get(device_id)
    if not runtime_name:
        runtime_name = _runtime_device_name(device_id, device_name)
    
    # Call gRPC to remove (Line 1659-1660)
    request = emulation_pb2.RemoveDeviceRequest(name=runtime_name)
    response = grpc_client.stub.RemoveDevice(request)
    
    if response.success:
        # Clean up runtime name mappings (Line 1664-1672)
        if device_id in grpc_client.node_id_to_runtime:
            runtime = grpc_client.node_id_to_runtime.pop(device_id)
            grpc_client.node_id_to_runtime.pop(runtime)
        if device_name:
            runtime = grpc_client.node_id_to_runtime.pop(device_name)
            grpc_client.node_id_to_runtime.pop(runtime)
        return True
    else:
        return False
```

#### Apply Changes with Device Management (Line 779-1148)
```python
async def apply_topology_changes_endpoint(
    topology_id: str,
    payload: TopologyApplyRequest
):
    """Apply staged topology changes: emulate first, then persist."""
    
    # Fetch snapshot of current topology (Line 807-811)
    topology_snapshot = await fetch_topology_definition(topology_id)
    devices_snapshot = copy.deepcopy(topology_snapshot.get('nodes', []))
    links_snapshot = copy.deepcopy(topology_snapshot.get('links', []))
    
    # Remove links first (Line 897-911)
    for link_ref in change_set.remove_links:
        if not await remove_link_from_emulation(topology_id, link_data):
            raise HTTPException(500, "Failed to remove link")
    
    # Remove devices (Line 914-934)
    for device_ref in change_set.remove_devices:
        if not await remove_device_from_emulation(topology_id, device_data.get('name')):
            raise HTTPException(500, "Failed to remove device")
    
    # Add devices (Line 937-974)
    for node_delta in change_set.add_devices:
        device_id = node_delta.id or str(uuid.uuid4())
        device_properties = dict(node_delta.properties or {})
        device_properties.setdefault('node_id', device_id)
        device_properties.setdefault('display_name', node_delta.name)
        
        device_payload = {
            'id': device_id,
            'name': node_delta.name,
            'type': device_type,
            'properties': device_properties,
            'x': node_delta.x,
            'y': node_delta.y
        }
        
        if not await add_device_to_emulation(topology_id, device_payload):
            await rollback_operations()
            raise HTTPException(500, "Failed to add device")
    
    # Persist to topology service (Line 1098-1103)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{TOPOLOGY_SERVICE_URL}/api/topologies/{topology_id}/apply",
            json=payload_dict
        )
    
    # Update emulation metadata (Line 1126-1130)
    update_active_emulation(
        active.get('emulation_id'),
        last_synced=_iso_now(),
        status=active.get('status', 'running')
    )
```

---

## 3. DOCKER & CONTAINER INTEGRATION

### 3.1 Current Docker Support

#### Proto Definition (AddDockerContainerRequest)
```protobuf
message AddDockerContainerRequest {
    string name = 1;
    string image = 2;
    repeated string command = 3;
    map<string, string> environment = 4;
    repeated string volumes = 5;
    map<string, string> params = 6;
}
```

#### Dependencies
**Backend requirements.txt (Line 49):**
```
docker==7.0.0
```

The Docker SDK is already available but NOT currently used in the orchestrator service. It's used by the gRPC emulation container (backend implementation).

### 3.2 Container Property Storage

Containers are defined through Node properties:
```python
Node {
    name: "app-container",
    device_type: "container",
    properties: {
        "image": "ubuntu:22.04",
        "command": "bash -c 'python app.py'",
        "environment": {
            "LOG_LEVEL": "debug",
            "APP_CONFIG": "/etc/config.json"
        },
        "volumes": [
            "/home/user/data:/app/data",
            "/home/user/config:/etc/config.json"
        ],
        "docker_image": "ubuntu:22.04",  # Alternative field name
        "docker_opts": "--cap-add=NET_ADMIN"
    }
}
```

### 3.3 Where Container Tracking is Missing

1. **PostgreSQL Topology Model** - No fields for:
   - `emulation_id` (links topology to active emulation)
   - `container_id` (Docker container ID)
   - `container_name` (Docker container name)
   - `container_host` (Host running container)

2. **Node Model Properties** - Not persisted automatically:
   - Actual Docker container ID returned by Docker API
   - Container status from Docker daemon
   - Container IP address (dynamic)
   - Container exit code (for troubleshooting)

3. **Redis Tracking** - Has `emulation_id` but not:
   - Individual container IDs per device
   - Container host mappings
   - Container port mappings

---

## 4. gRPC COMMUNICATION

### 4.1 StartEmulation Request Flow

**Proto Message:**
```protobuf
message StartEmulationRequest {
    string topology_id = 1;
    TopologyDefinition topology = 2;
    map<string, string> options = 3;
}

message TopologyDefinition {
    repeated Device devices = 1;
    repeated Link links = 2;
    repeated Controller controllers = 3;
    map<string, string> options = 4;
}

message Device {
    string name = 1;           // Runtime name (sanitized)
    string type = 2;           // device_type enum value
    map<string, string> properties = 3;  // node properties
    repeated Interface interfaces = 4;
    string status = 5;
}
```

**Python Implementation:**
```python
def _convert_device(self, device: Dict) -> emulation_pb2.Device:
    """Convert device dict to protobuf Device"""
    device_type = device.get('type', device.get('device_type', ''))
    node_id = device.get('id', device.get('node_id', ''))
    display_name = device.get('name', '')
    runtime_name = _runtime_device_name(node_id, display_name)
    
    pb_device = emulation_pb2.Device(
        name=runtime_name,
        type=device_type
    )
    
    # Add properties as map
    properties = device.get('properties', {})
    for key, value in properties.items():
        pb_device.properties[key] = str(value)
    
    # Add node ID for mapping
    if node_id:
        pb_device.properties['node_id'] = str(node_id)
    
    # Preserve display name
    if display_name:
        pb_device.properties['display_name'] = display_name
        pb_device.properties['original_name'] = display_name
    
    return pb_device
```

### 4.2 Response Handling

The gRPC emulation service returns:
```protobuf
message EmulationResponse {
    bool success = 1;
    string message = 2;
    string emulation_id = 3;
}
```

This `emulation_id` is stored in Redis as the link between:
- PostgreSQL Topology record (topology_id)
- Redis active emulation tracking (emulation_id)
- gRPC emulation container (emulation_id for all subsequent calls)

---

## 5. EMULATION LIFECYCLE

### 5.1 State Transitions

```
TOPOLOGY CREATED (PostgreSQL)
    ↓
Start Emulation Request
    ↓
Fetch Topology → gRPC StartEmulation → Emulation Container Spawned
    ↓
Record in Redis:
  - topology_id → emulation_id mapping
  - emulation_status = "running"
    ↓
Topology in PostgreSQL:
  - is_active = true
  - emulation_status = "running"
    ↓
EMULATION RUNNING
    ↓
Apply Changes (add/remove devices/links)
    ↓
Update gRPC → Update Topology → Update Redis
    ↓
Stop Emulation
    ↓
Remove from Redis
  - Set is_active = false
  - Set emulation_status = "stopped"
```

### 5.2 Current Data Flow

```
PostgreSQL (Topology Storage)
    ↑
    │ read
    ↓
Orchestrator Service (Port 8002)
    ↑
    │ write
    ↓
Redis (Active Emulation Tracking)
    ↑
    │ gRPC calls
    ↓
gRPC Emulation Container (Port 50051)
    ↑
    │ spawns
    ↓
Mininet Emulation + Docker Daemon
```

---

## 6. KEY FINDINGS FOR REDESIGN

### 6.1 Container ID Tracking Gaps

**Current State:**
- Emulation ID is tracked in Redis
- Node-to-runtime-name mapping is in-memory in gRPCClient
- Docker container IDs are NOT tracked anywhere

**Design Issues for Dynamic Spawning:**
1. No way to look up container ID for a running device
2. No persistence of container ID across service restarts
3. No way to correlate PostgreSQL node_id → Docker container_id
4. No host information for containers (which server is running it?)

### 6.2 Node Properties Limitations

**Current:**
```python
Node.properties = {
    "image": "ubuntu:22.04",
    "command": "...",
    # but container_id is NOT stored here
}
```

**Needed for Dynamic Spawning:**
- Store actual docker container ID in properties after creation
- Store container IP address (dynamic)
- Store container exit status/code
- Store container host/server reference

### 6.3 Apply Changes Flow

**Works Well:**
- Staged changes system (add/remove/update)
- Rollback on failure
- Two-phase commit (emulation first, then database)

**Missing for Containers:**
- No way to track what was actually created
- No persistent record of container_id from gRPC response
- No host affinity tracking

### 6.4 gRPC Container Support

**Available (in proto):**
- AddDockerContainerRequest/Response with full Docker parameters
- UpdateDevice capability
- RemoveDevice capability

**NOT Implemented:**
- GetDockerContainerResponse doesn't return container_id
- No way to query created container ID
- No way to update container properties after creation

---

## 7. RECOMMENDED CHANGES FOR DYNAMIC CONTAINER SPAWNING

### 7.1 Database Schema Additions

**Topology Table:**
```sql
ALTER TABLE topologies ADD COLUMN emulation_id VARCHAR(36);  -- Link to active emulation
ALTER TABLE topologies ADD COLUMN container_host VARCHAR(255);  -- Host running emulation
ALTER TABLE topologies ADD COLUMN created_container_count INT DEFAULT 0;
```

**Node Table (properties usage):**
```python
Node.properties should include after creation:
{
    # Input properties
    "image": "ubuntu:22.04",
    "command": "...",
    "environment": {...},
    "volumes": [...],
    
    # Added after container creation
    "container_id": "sha256:abc123...",
    "container_name": "xyz-container-1",
    "container_ip": "172.17.0.2",
    "container_port_mappings": {...},
    "created_at": "2024-11-03T...",
    "last_known_status": "running|exited|..."
}
```

### 7.2 Redis Schema Enhancement

**Emulation Record (in ActiveEmulationStore):**
```python
{
    'topology_id': str,
    'topology_name': str,
    'emulation_id': str,
    'status': str,
    'started_at': str,
    'last_updated': str,
    'container_host': str,  # NEW: Which server
    'device_container_map': {  # NEW: node_id → container_id mapping
        'uuid-1': 'sha256:abc...',
        'uuid-2': 'sha256:def...'
    },
    'node_runtime_map': {  # EXISTING: node_id/name → runtime name
        'uuid-1': 'h1',
        'host1': 'h1'
    },
    'options': {...},
    'node_count': int,
    'link_count': int
}
```

### 7.3 gRPC Response Enhancement

**Need to extend proto:**
```protobuf
message DeviceResponse {
    bool success = 1;
    string message = 2;
    Device device = 3;
    string container_id = 4;  // NEW: Docker container ID
    string container_name = 5;  // NEW: Container name
    string ip_address = 6;  // NEW: Container IP
    map<string, string> metadata = 7;  // NEW: Additional info
}
```

---

## 8. SUMMARY TABLE

| Aspect | Current State | For Container Spawning |
|--------|---------------|------------------------|
| **Topology ID** | PostgreSQL PK | Parent reference |
| **Emulation ID** | Redis only | Need in PostgreSQL + Redis |
| **Container ID** | Not tracked | Need in PostgreSQL + Redis |
| **Container Name** | Not tracked | Need in PostgreSQL |
| **Node.properties** | Flexible JSON | Add post-creation metadata |
| **Runtime Name** | In-memory only | Consistent mapping |
| **Device to Container** | One-to-one (implied) | Need explicit mapping |
| **Container Host** | Not tracked | Need for distributed spawning |
| **Docker SDK** | Installed but not used | Ready to use in orchestrator |
| **gRPC Docker Support** | AddDockerContainer only | Missing response tracking |
| **Apply Changes** | Works for both | Need container ID feedback |

---

## 9. CRITICAL CODE LOCATIONS

| Feature | File | Lines |
|---------|------|-------|
| Topology Model | `/backend/shared/models/topology.py` | 53-72 |
| Node Model | `/backend/shared/models/topology.py` | 74-90 |
| Topology Schema | `/backend/shared/schemas/topology_schema.py` | 127-158 |
| Start Emulation | `/backend/services/orchestrator/main.py` | 689-776 |
| gRPC Client Init | `/backend/services/orchestrator/main.py` | 314-338 |
| Add Container | `/backend/services/orchestrator/main.py` | 1568-1608 |
| Active Emulation Store | `/backend/services/orchestrator/main.py` | 105-145 |
| Record Active | `/backend/services/orchestrator/main.py` | 244-264 |
| Apply Changes | `/backend/services/orchestrator/main.py` | 779-1148 |
| Docker Request | `/backend/proto/emulation.proto` | 174-181 |

