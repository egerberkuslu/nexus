# Migration Plan: Mininet → Mininet-WiFi + Containernet with Button-Triggered Apply

## Overview

This document outlines the migration from plain Mininet with auto-sync to Mininet-WiFi + Containernet with button-triggered apply logic.

## Current Architecture Issues

1. **Auto-Sync Complexity**: Changes automatically propagate to Mininet, making it hard to batch operations
2. **No Rollback**: Database changes commit before Mininet validation
3. **Limited Device Types**: No support for WiFi stations, access points, or Docker containers
4. **Fragile State**: RabbitMQ events can trigger partial updates if messages arrive out of order

## New Architecture Goals

1. **Staged Changes**: User can make multiple edits before applying
2. **Apply-First**: Validate changes in Mininet-WiFi/Containernet before database commit
3. **Atomic Operations**: All-or-nothing approach (rollback on any failure)
4. **WiFi Support**: Access points, stations, mobility models
5. **Container Support**: Docker nodes via Containernet
6. **Better UX**: Clear feedback on what will be applied

---

## Phase 1: Update Emulation Container (gRPC Server)

### 1.1 Replace Mininet with Containernet + WiFi

**File**: `/emulation-container/grpc_agent/emulation_manager.py`

```python
# OLD
from mininet.net import Mininet
from mininet.node import Host, Switch, Controller

# NEW
from mn_wifi.net import Mininet_wifi
from mn_wifi.node import Station, accessPoint
from mn_wifi.cli import CLI
from containernet.node import Docker
```

### 1.2 Update Device Handler for WiFi Devices

**File**: `/emulation-container/grpc_agent/device_handler.py`

Add methods:
- `add_access_point()` - Create AP with SSID, channel, mode
- `add_station()` - Create WiFi station with mobility
- `add_docker_container()` - Create containerized node
- `configure_wifi()` - Set WiFi parameters (propagation model, etc.)

### 1.3 Update Topology Build Logic

**File**: `/emulation-container/grpc_agent/emulation_manager.py`

```python
def start_emulation(self, topology_def):
    # Initialize Mininet-WiFi (supports both wired and wireless)
    self.net = Mininet_wifi(
        controller=RemoteController if controllers else None,
        link=TCLink,
        accessPoint=UserAccessPoint,
        enable_wmediumd=True,  # Enable wireless medium daemon
        enable_interference=True
    )

    # Add devices based on type
    for device in topology_def.devices:
        if device.type == 'station':
            self._add_station(device)
        elif device.type == 'accesspoint':
            self._add_access_point(device)
        elif device.type == 'docker':
            self._add_docker_node(device)
        elif device.type == 'host':
            self.net.addHost(device.name, ...)
        elif device.type in ['switch', 'ovs']:
            self.net.addSwitch(device.name, ...)

    # IMPORTANT: Configure WiFi nodes BEFORE starting network
    if has_wifi_nodes:
        self.net.configureWifiNodes()
        self.net.setMobilityModel(...)  # If mobility enabled

    # Build network
    self.net.start()
```

---

## Phase 2: Update Orchestrator Service

### 2.1 Remove Auto-Sync Event Handlers

**File**: `/backend/services/orchestrator/main.py`

**Changes**:
1. Comment out RabbitMQ consumer bindings for topology events:
   ```python
   # rabbitmq_consumer.bind_routing_key("topology.node.updated")
   # rabbitmq_consumer.bind_routing_key("topology.link.updated")
   # ... etc
   ```

2. Keep ONLY topology lifecycle events:
   ```python
   rabbitmq_consumer.bind_routing_key("topology.created")  # Keep
   rabbitmq_consumer.bind_routing_key("topology.deleted")  # Keep
   ```

3. Remove event handlers:
   - `handle_topology_node_updated()`
   - `handle_topology_link_updated()`
   - `handle_topology_node_added()`
   - `handle_topology_node_deleted()`
   - `handle_topology_link_added()`
   - `handle_topology_link_deleted()`

### 2.2 Create New Apply Changes Endpoint

**File**: `/backend/services/orchestrator/main.py`

```python
@app.post("/api/orchestrator/apply-changes")
async def apply_changes_endpoint(request: ApplyChangesRequest):
    """
    Apply staged changes to running emulation, then persist to database.

    Flow:
    1. Validate all changes can be applied to Mininet-WiFi
    2. Apply changes to emulation in order:
       - Add new devices
       - Update existing devices
       - Add new links
       - Update existing links
       - Remove links
       - Remove devices
    3. If ALL successful → Save to database via Topology Service
    4. If ANY fails → Rollback changes in Mininet, return error
    5. Return detailed results
    """
    topology_id = request.topology_id
    changes = request.changes

    if topology_id not in active_emulations:
        raise HTTPException(404, "No active emulation for this topology")

    # Track applied changes for rollback
    applied_operations = []
    failed_operations = []

    try:
        # Phase 1: Add new devices
        for device in changes.add_devices:
            success = await add_device_to_emulation(topology_id, device)
            if success:
                applied_operations.append(('add_device', device))
            else:
                failed_operations.append(('add_device', device, "Failed to create"))
                raise ApplyException(f"Failed to add device {device['name']}")

        # Phase 2: Update devices
        for device in changes.update_devices:
            success = await sync_device_to_emulation(topology_id, device)
            if success:
                applied_operations.append(('update_device', device))
            else:
                failed_operations.append(('update_device', device, "Failed to update"))
                raise ApplyException(f"Failed to update device {device['name']}")

        # Phase 3: Add new links
        for link in changes.add_links:
            success = await add_link_to_emulation(topology_id, link)
            if success:
                applied_operations.append(('add_link', link))
            else:
                failed_operations.append(('add_link', link, "Failed to create"))
                raise ApplyException(f"Failed to add link")

        # Phase 4: Update links
        for link in changes.update_links:
            success = await sync_link_to_emulation(topology_id, link)
            if success:
                applied_operations.append(('update_link', link))
            else:
                failed_operations.append(('update_link', link, "Failed to update"))
                raise ApplyException(f"Failed to update link")

        # Phase 5: Remove links (before removing devices)
        for link in changes.remove_links:
            success = await remove_link_from_emulation(topology_id, link)
            if success:
                applied_operations.append(('remove_link', link))
            else:
                # Continue on link removal failures (link might already be gone)
                logger.warning(f"Failed to remove link, continuing: {link}")

        # Phase 6: Remove devices
        for device in changes.remove_devices:
            success = await remove_device_from_emulation(
                topology_id, device['name'], device.get('id')
            )
            if success:
                applied_operations.append(('remove_device', device))
            else:
                failed_operations.append(('remove_device', device, "Failed to remove"))
                raise ApplyException(f"Failed to remove device {device['name']}")

        # ===== ALL MININET OPERATIONS SUCCESSFUL =====
        # Now persist to database via Topology Service

        logger.info(f"All Mininet operations successful. Persisting to database...")

        db_success = await persist_changes_to_database(topology_id, changes)

        if not db_success:
            logger.error("Database persistence failed! Mininet and DB are now out of sync!")
            # TODO: Implement compensation logic or manual sync
            raise HTTPException(500, "Applied to emulation but failed to save to database")

        return {
            "success": True,
            "message": "All changes applied successfully",
            "applied_count": len(applied_operations),
            "results": {
                "devices_added": len(changes.add_devices),
                "devices_updated": len(changes.update_devices),
                "devices_removed": len(changes.remove_devices),
                "links_added": len(changes.add_links),
                "links_updated": len(changes.update_links),
                "links_removed": len(changes.remove_links)
            }
        }

    except ApplyException as e:
        # Rollback applied changes in reverse order
        logger.error(f"Apply failed: {e}. Rolling back {len(applied_operations)} operations")

        rollback_count = await rollback_operations(applied_operations)

        return {
            "success": False,
            "message": str(e),
            "applied_count": len(applied_operations),
            "rolled_back_count": rollback_count,
            "failed_operations": failed_operations
        }


async def persist_changes_to_database(topology_id: str, changes: ChangeSet) -> bool:
    """
    Persist validated changes to database via Topology Service API.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # POST batch update endpoint
            response = await client.post(
                f"{TOPOLOGY_SERVICE_URL}/api/topologies/{topology_id}/batch-update",
                json={
                    "add_devices": changes.add_devices,
                    "update_devices": changes.update_devices,
                    "remove_devices": changes.remove_devices,
                    "add_links": changes.add_links,
                    "update_links": changes.update_links,
                    "remove_links": changes.remove_links
                }
            )

            if response.status_code == 200:
                logger.info(f"Successfully persisted changes to database for {topology_id}")
                return True
            else:
                logger.error(f"Database persistence failed: {response.status_code} {response.text}")
                return False

    except Exception as e:
        logger.error(f"Exception during database persistence: {e}")
        return False


async def rollback_operations(applied_operations: list) -> int:
    """
    Rollback applied operations in reverse order.
    Returns count of successfully rolled back operations.
    """
    rollback_count = 0

    # Reverse order: last applied, first rolled back
    for operation, data in reversed(applied_operations):
        try:
            if operation == 'add_device':
                # Rollback: remove device
                await remove_device_from_emulation(data['topology_id'], data['name'], data.get('id'))
                rollback_count += 1

            elif operation == 'update_device':
                # Rollback: fetch original state and restore
                # (Simplified: just log, full implementation needs state snapshot)
                logger.warning(f"Cannot rollback device update for {data['name']} (no snapshot)")

            elif operation == 'remove_device':
                # Rollback: re-add device
                await add_device_to_emulation(data['topology_id'], data)
                rollback_count += 1

            elif operation == 'add_link':
                # Rollback: remove link
                await remove_link_from_emulation(data['topology_id'], data)
                rollback_count += 1

            elif operation == 'update_link':
                # Rollback: restore original params (need snapshot)
                logger.warning(f"Cannot rollback link update (no snapshot)")

            elif operation == 'remove_link':
                # Rollback: re-add link
                await add_link_to_emulation(data['topology_id'], data)
                rollback_count += 1

        except Exception as e:
            logger.error(f"Rollback failed for operation {operation}: {e}")

    return rollback_count
```

---

## Phase 3: Update Topology Service

### 3.1 Add Batch Update Endpoint

**File**: `/backend/services/topology/main.py`

```python
@app.post("/api/topologies/{topology_id}/batch-update")
async def batch_update_topology(topology_id: str, changes: BatchUpdateRequest):
    """
    Apply multiple changes atomically to a topology.
    Called by orchestrator after successful Mininet apply.

    This endpoint does NOT publish events (to prevent auto-sync loops).
    """
    async with get_db_session() as db:
        topology = await db.get(Topology, topology_id)
        if not topology:
            raise HTTPException(404, "Topology not found")

        # Use database transaction for atomicity
        try:
            # Add new devices
            for device_data in changes.add_devices:
                new_device = Node(
                    id=device_data['id'],
                    topology_id=topology_id,
                    name=device_data['name'],
                    type=device_data['type'],
                    properties=device_data.get('properties', {})
                )
                db.add(new_device)

            # Update devices
            for device_data in changes.update_devices:
                device = await db.get(Node, device_data['id'])
                if device:
                    device.name = device_data.get('name', device.name)
                    device.properties = device_data.get('properties', device.properties)

            # Remove devices
            for device_data in changes.remove_devices:
                device = await db.get(Node, device_data['id'])
                if device:
                    await db.delete(device)

            # Add links
            for link_data in changes.add_links:
                new_link = Link(
                    id=link_data['id'],
                    topology_id=topology_id,
                    source_node_id=link_data['source_node_id'],
                    target_node_id=link_data['target_node_id'],
                    bandwidth=link_data.get('bandwidth'),
                    delay=link_data.get('delay'),
                    loss=link_data.get('loss')
                )
                db.add(new_link)

            # Update links
            for link_data in changes.update_links:
                link = await db.get(Link, link_data['id'])
                if link:
                    link.bandwidth = link_data.get('bandwidth', link.bandwidth)
                    link.delay = link_data.get('delay', link.delay)
                    link.loss = link_data.get('loss', link.loss)

            # Remove links
            for link_data in changes.remove_links:
                link = await db.get(Link, link_data['id'])
                if link:
                    await db.delete(link)

            await db.commit()

            logger.info(f"Batch update committed for topology {topology_id}")
            return {"success": True, "message": "Changes saved to database"}

        except Exception as e:
            await db.rollback()
            logger.error(f"Batch update failed: {e}")
            raise HTTPException(500, f"Database transaction failed: {e}")
```

---

## Phase 4: Update Frontend

### 4.1 Add Staged Changes State Management

**File**: `/frontend/src/contexts/TopologyContext.tsx` (or similar)

```typescript
interface StagedChanges {
  add_devices: Device[];
  update_devices: Device[];
  remove_devices: Device[];
  add_links: Link[];
  update_links: Link[];
  remove_links: Link[];
}

const [stagedChanges, setStagedChanges] = useState<StagedChanges>({
  add_devices: [],
  update_devices: [],
  remove_devices: [],
  add_links: [],
  update_links: [],
  remove_links: []
});

const [hasUnappliedChanges, setHasUnappliedChanges] = useState(false);

// When user adds a device
const addDeviceStaged = (device: Device) => {
  setStagedChanges(prev => ({
    ...prev,
    add_devices: [...prev.add_devices, device]
  }));
  setHasUnappliedChanges(true);
};

// When user edits a device
const updateDeviceStaged = (device: Device) => {
  setStagedChanges(prev => ({
    ...prev,
    update_devices: [...prev.update_devices, device]
  }));
  setHasUnappliedChanges(true);
};
```

### 4.2 Add Apply Button Component

**File**: `/frontend/src/components/ApplyChangesButton.tsx`

```typescript
const ApplyChangesButton: React.FC = () => {
  const { stagedChanges, hasUnappliedChanges, topologyId } = useTopology();
  const [isApplying, setIsApplying] = useState(false);

  const handleApply = async () => {
    setIsApplying(true);

    try {
      const response = await orchestratorAPI.applyChanges(topologyId, stagedChanges);

      if (response.success) {
        toast.success(`Applied ${response.applied_count} changes successfully`);
        clearStagedChanges();
      } else {
        toast.error(`Apply failed: ${response.message}`);
        // Show which operations failed
        displayFailedOperations(response.failed_operations);
      }
    } catch (error) {
      toast.error('Failed to apply changes');
      console.error(error);
    } finally {
      setIsApplying(false);
    }
  };

  const changeCount =
    stagedChanges.add_devices.length +
    stagedChanges.update_devices.length +
    stagedChanges.remove_devices.length +
    stagedChanges.add_links.length +
    stagedChanges.update_links.length +
    stagedChanges.remove_links.length;

  return (
    <Button
      onClick={handleApply}
      disabled={!hasUnappliedChanges || isApplying}
      variant="primary"
      icon={<CheckIcon />}
    >
      {isApplying ? 'Applying...' : `Apply Changes (${changeCount})`}
    </Button>
  );
};
```

### 4.3 Add Changes Preview Panel

Show user what will be applied before they click the button:

```typescript
const ChangesPreviewPanel: React.FC = () => {
  const { stagedChanges } = useTopology();

  return (
    <Panel title="Pending Changes">
      {stagedChanges.add_devices.length > 0 && (
        <Section>
          <h3>New Devices ({stagedChanges.add_devices.length})</h3>
          <ul>
            {stagedChanges.add_devices.map(d => (
              <li key={d.id}>{d.name} ({d.type})</li>
            ))}
          </ul>
        </Section>
      )}

      {stagedChanges.update_devices.length > 0 && (
        <Section>
          <h3>Updated Devices ({stagedChanges.update_devices.length})</h3>
          <ul>
            {stagedChanges.update_devices.map(d => (
              <li key={d.id}>{d.name} - Changed: {getChangedFields(d)}</li>
            ))}
          </ul>
        </Section>
      )}

      {/* Similar for remove_devices, links, etc. */}
    </Panel>
  );
};
```

---

## Phase 5: WiFi-Specific Features

### 5.1 Add WiFi Device Types to Schema

**File**: `/backend/shared/schemas/topology_schema.py`

```python
class DeviceType(str, Enum):
    HOST = "host"
    SWITCH = "switch"
    ROUTER = "router"
    DOCKER = "docker"
    ACCESS_POINT = "accesspoint"  # NEW
    STATION = "station"           # NEW

class WiFiConfig(BaseModel):
    ssid: Optional[str] = ""
    mode: Optional[str] = "g"  # a, b, g, n, ac, ax
    channel: Optional[str] = "1"
    security: Optional[str] = "open"  # open, wpa, wpa2, wpa3
    password: Optional[str] = ""
    range: Optional[int] = 100  # meters
    txpower: Optional[int] = 20  # dBm

class MobilityConfig(BaseModel):
    model: Optional[str] = None  # RandomWalk, RandomDirection, GaussMarkov
    min_v: Optional[float] = 0.5  # m/s
    max_v: Optional[float] = 1.5  # m/s
    min_x: Optional[float] = 0
    max_x: Optional[float] = 100
    min_y: Optional[float] = 0
    max_y: Optional[float] = 100
    position: Optional[Tuple[float, float, float]] = None  # (x, y, z)
```

### 5.2 Update Frontend Device Form

**File**: `/frontend/src/components/DeviceForm.tsx`

Add conditional rendering for WiFi properties:

```typescript
{deviceType === 'accesspoint' && (
  <>
    <Input label="SSID" value={ssid} onChange={setSsid} />
    <Select label="Mode" options={['a', 'b', 'g', 'n', 'ac', 'ax']} />
    <Input label="Channel" type="number" />
    <Select label="Security" options={['open', 'wpa', 'wpa2', 'wpa3']} />
    {security !== 'open' && (
      <Input label="Password" type="password" />
    )}
  </>
)}

{deviceType === 'station' && (
  <>
    <Input label="SSID" value={ssid} />
    <Checkbox label="Enable Mobility" checked={mobilityEnabled} />
    {mobilityEnabled && (
      <>
        <Select label="Mobility Model" options={['RandomWalk', 'RandomDirection']} />
        <Input label="Min Speed (m/s)" type="number" />
        <Input label="Max Speed (m/s)" type="number" />
        <Input label="Initial Position (x, y, z)" />
      </>
    )}
  </>
)}
```

---

## Phase 6: Docker Container Support

### 6.1 Add Docker Device Handling

**File**: `/emulation-container/grpc_agent/device_handler.py`

```python
def add_docker_container(self, request):
    """Add a Docker container node to the network."""
    try:
        # Extract properties
        name = request.name
        image = request.params.get('image', 'ubuntu:22.04')
        dcmd = request.params.get('command', '/bin/bash')

        # Environment variables
        environment = {}
        for key, value in request.params.items():
            if key.startswith('env_'):
                env_var = key.replace('env_', '').upper()
                environment[env_var] = value

        # Add Docker node using Containernet
        docker_node = self.net.addDocker(
            name,
            dimage=image,
            dcmd=dcmd,
            environment=environment,
            ip=request.params.get('ip', None),
            mac=request.params.get('mac', None),
            cpu_period=int(request.params.get('cpu_period', 50000)),
            cpu_quota=int(request.params.get('cpu_quota', 25000)),
            mem_limit=request.params.get('mem_limit', '512m')
        )

        return emulation_pb2.DeviceResponse(
            success=True,
            message=f"Docker container {name} added",
            device=self._device_to_proto(docker_node)
        )

    except Exception as e:
        logger.error(f"Failed to add Docker container: {e}")
        return emulation_pb2.DeviceResponse(
            success=False,
            message=str(e)
        )
```

---

## Testing Plan

### Unit Tests
1. Test staged changes state management
2. Test apply changes endpoint with various change combinations
3. Test rollback logic
4. Test Mininet-WiFi device creation

### Integration Tests
1. Create topology → Add WiFi devices → Apply → Verify in Mininet
2. Update device properties → Apply → Verify changes
3. Trigger failure mid-apply → Verify rollback
4. Test Docker container lifecycle

### E2E Tests
1. Full user workflow: Create topology → Add devices/links → Apply → Start emulation
2. Test mobility: Add station with mobility → Apply → Verify movement
3. Test Docker: Add container → Apply → Execute commands in container

---

## Migration Checklist

### Backend
- [ ] Update emulation container dependencies (mininet-wifi, containernet)
- [ ] Replace Mininet with Mininet_wifi in emulation_manager
- [ ] Add WiFi device handlers (AP, Station)
- [ ] Add Docker container handler
- [ ] Disable auto-sync event handlers in orchestrator
- [ ] Create apply-changes endpoint in orchestrator
- [ ] Add batch-update endpoint in topology service
- [ ] Update gRPC proto for WiFi/Docker support
- [ ] Regenerate Python gRPC stubs

### Frontend
- [ ] Add staged changes state management
- [ ] Create Apply Changes button component
- [ ] Add changes preview panel
- [ ] Update device form for WiFi properties
- [ ] Add Docker container configuration UI
- [ ] Add mobility configuration UI
- [ ] Update topology visualization for WiFi links

### Infrastructure
- [ ] Update emulation-container Dockerfile with WiFi/Containernet deps
- [ ] Test Docker-in-Docker for Containernet
- [ ] Update docker-compose for privileged mode
- [ ] Add WiFi visualization assets

### Documentation
- [ ] Update API documentation
- [ ] Create user guide for Apply button workflow
- [ ] Document WiFi configuration options
- [ ] Document Docker container usage
- [ ] Create troubleshooting guide

---

## Rollback Plan

If migration fails, we can roll back by:

1. Revert orchestrator changes (re-enable auto-sync)
2. Revert frontend changes (remove staged changes logic)
3. Keep database schema (backward compatible)
4. Redeploy previous emulation container image

---

## Timeline Estimate

- **Phase 1** (Emulation Container): 3-4 days
- **Phase 2** (Orchestrator): 2-3 days
- **Phase 3** (Topology Service): 1-2 days
- **Phase 4** (Frontend): 3-4 days
- **Phase 5** (WiFi Features): 2-3 days
- **Phase 6** (Docker Support): 2 days
- **Testing**: 3-4 days

**Total**: ~16-22 days (3-4 weeks)

---

## Questions / Decisions Needed

1. **Rollback Granularity**: Should we snapshot device/link state before updates for perfect rollback?
2. **Database Sync**: If database save fails after Mininet apply, should we:
   - Keep Mininet state and show warning?
   - Force rollback and fail the entire operation?
3. **Partial Apply**: Should we allow users to apply only selected changes, or always apply all staged changes?
4. **Auto-Save**: Should we still auto-save topology structure (non-emulation state) to database?

