# Implementation Status: Mininet-WiFi + Containernet with Button-Triggered Apply

## Overview

This document tracks the implementation progress of migrating from plain Mininet with auto-sync to Mininet-WiFi + Containernet with button-triggered apply flow.

---

## ✅ Phase 1: Emulation Container (COMPLETE)

### Status: **100% Complete**

The emulation container already has full support for Mininet-WiFi and Containernet!

### What's Working:
- ✅ Mininet-WiFi installed and integrated
- ✅ Containernet installed and integrated
- ✅ WiFi device types supported:
  - Access Points (`addAccessPoint`)
  - Stations (`addStation`)
  - WiFi propagation models
- ✅ Docker container support (`addDocker`)
- ✅ Hybrid networks (wired + wireless + containers)
- ✅ Device handlers for all types in `device_handler.py`
- ✅ Emulation manager switches between Mininet/Mininet-WiFi based on topology

### Files:
- [emulation-container/Dockerfile](emulation-container/Dockerfile) - Dependencies installed
- [emulation-container/grpc_agent/emulation_manager.py](emulation-container/grpc_agent/emulation_manager.py:148-200) - WiFi detection and initialization
- [emulation-container/grpc_agent/device_handler.py](emulation-container/grpc_agent/device_handler.py:196-304) - Device handlers

---

## 🚧 Phase 2: Orchestrator Service (IN PROGRESS)

### Status: **70% Complete**

### ✅ Completed:
- ✅ Helper functions for device/link operations already exist
- ✅ ApplyChangesHandler class created
- ✅ Rollback logic implemented
- ✅ Database persistence logic implemented

###⏳ Remaining Tasks:

#### 1. Disable Auto-Sync Event Handlers
**File**: `backend/services/orchestrator/main.py`

**Instructions**: See [DISABLE_AUTO_SYNC_INSTRUCTIONS.md](DISABLE_AUTO_SYNC_INSTRUCTIONS.md)

Comment out 6 event handler functions:
- `handle_topology_node_updated()`
- `handle_topology_link_updated()`
- `handle_topology_node_added()`
- `handle_topology_node_deleted()`
- `handle_topology_link_added()`
- `handle_topology_link_deleted()`

Remove RabbitMQ bindings for these handlers in `startup_event()`.

#### 2. Add Apply Changes Endpoint
**File**: `backend/services/orchestrator/main.py`

Add this endpoint after the `/api/emulation/sync/{topology_id}` endpoint:

```python
from apply_changes_handler import ApplyChangesHandler, ApplyException
from pydantic import BaseModel

class ApplyChangesRequest(BaseModel):
    """Request payload for applying staged changes"""
    topology_id: str
    changes: Dict[str, Any]

@app.post("/api/orchestrator/apply-changes")
async def apply_changes_endpoint(request: ApplyChangesRequest):
    """
    Apply staged changes to running emulation, then persist to database.

    This is the button-triggered apply flow:
    1. Apply all changes to Mininet-WiFi/Containernet
    2. If successful, persist to database
    3. If any failure, rollback Mininet changes
    """
    handler = ApplyChangesHandler(
        grpc_client=grpc_client,
        active_emulations=active_emulations,
        rabbitmq_publisher=rabbitmq_publisher
    )

    result = await handler.apply_changes(
        topology_id=request.topology_id,
        changes=request.changes
    )

    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result['message']
        )

    return result
```

---

## ⏳ Phase 3: Topology Service (TODO)

### Status: **0% Complete**

### Tasks:

#### 1. Add Batch Update Endpoint
**File**: `backend/services/topology/main.py`

Add this endpoint:

```python
from pydantic import BaseModel
from typing import List

class BatchUpdateRequest(BaseModel):
    """Batch update request for topology changes"""
    add_devices: List[Dict] = []
    update_devices: List[Dict] = []
    remove_devices: List[Dict] = []
    add_links: List[Dict] = []
    update_links: List[Dict] = []
    remove_links: List[Dict] = []

@app.post("/api/topologies/{topology_id}/batch-update")
async def batch_update_topology(
    topology_id: str,
    changes: BatchUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Apply multiple changes atomically to a topology.
    Called by orchestrator after successful Mininet apply.

    This endpoint does NOT publish events (to prevent auto-sync loops).
    """
    topology = db.query(Topology).filter(Topology.id == topology_id).first()
    if not topology:
        raise HTTPException(404, "Topology not found")

    try:
        # Add new devices
        for device_data in changes.add_devices:
            new_device = Node(
                id=device_data['id'],
                topology_id=topology_id,
                name=device_data['name'],
                type=device_data['type'],
                properties=device_data.get('properties', {}),
                x=device_data.get('x'),
                y=device_data.get('y')
            )
            db.add(new_device)

        # Update devices
        for device_data in changes.update_devices:
            device = db.query(Node).filter(Node.id == device_data['id']).first()
            if device:
                device.name = device_data.get('name', device.name)
                device.properties = device_data.get('properties', device.properties)
                device.x = device_data.get('x', device.x)
                device.y = device_data.get('y', device.y)

        # Remove devices
        for device_data in changes.remove_devices:
            device = db.query(Node).filter(Node.id == device_data['id']).first()
            if device:
                db.delete(device)

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
            link = db.query(Link).filter(Link.id == link_data['id']).first()
            if link:
                link.bandwidth = link_data.get('bandwidth', link.bandwidth)
                link.delay = link_data.get('delay', link.delay)
                link.loss = link_data.get('loss', link.loss)

        # Remove links
        for link_data in changes.remove_links:
            link = db.query(Link).filter(Link.id == link_data['id']).first()
            if link:
                db.delete(link)

        db.commit()

        logger.info(f"Batch update committed for topology {topology_id}")
        return {"success": True, "message": "Changes saved to database"}

    except Exception as e:
        db.rollback()
        logger.error(f"Batch update failed: {e}")
        raise HTTPException(500, f"Database transaction failed: {e}")
```

---

## ⏳ Phase 4: Frontend (TODO)

### Status: **0% Complete**

### Tasks:

#### 1. Add Staged Changes State Management

Create `/frontend/src/contexts/StagedChangesContext.tsx`:

```typescript
import React, { createContext, useState, useContext } from 'react';

interface StagedChanges {
  add_devices: Device[];
  update_devices: Device[];
  remove_devices: Device[];
  add_links: Link[];
  update_links: Link[];
  remove_links: Link[];
}

interface StagedChangesContextType {
  stagedChanges: StagedChanges;
  addDeviceStaged: (device: Device) => void;
  updateDeviceStaged: (device: Device) => void;
  removeDeviceStaged: (device: Device) => void;
  addLinkStaged: (link: Link) => void;
  updateLinkStaged: (link: Link) => void;
  removeLinkStaged: (link: Link) => void;
  clearStagedChanges: () => void;
  hasUnappliedChanges: boolean;
  getChangeCount: () => number;
}

export const StagedChangesContext = createContext<StagedChangesContextType | undefined>(undefined);

export const StagedChangesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [stagedChanges, setStagedChanges] = useState<StagedChanges>({
    add_devices: [],
    update_devices: [],
    remove_devices: [],
    add_links: [],
    update_links: [],
    remove_links: []
  });

  const addDeviceStaged = (device: Device) => {
    setStagedChanges(prev => ({
      ...prev,
      add_devices: [...prev.add_devices, device]
    }));
  };

  const updateDeviceStaged = (device: Device) => {
    setStagedChanges(prev => ({
      ...prev,
      update_devices: [...prev.update_devices, device]
    }));
  };

  // ... implement other methods

  const clearStagedChanges = () => {
    setStagedChanges({
      add_devices: [],
      update_devices: [],
      remove_devices: [],
      add_links: [],
      update_links: [],
      remove_links: []
    });
  };

  const hasUnappliedChanges = Object.values(stagedChanges).some(arr => arr.length > 0);

  const getChangeCount = () => {
    return Object.values(stagedChanges).reduce((sum, arr) => sum + arr.length, 0);
  };

  return (
    <StagedChangesContext.Provider value={{
      stagedChanges,
      addDeviceStaged,
      updateDeviceStaged,
      removeDeviceStaged,
      addLinkStaged,
      updateLinkStaged,
      removeLinkStaged,
      clearStagedChanges,
      hasUnappliedChanges,
      getChangeCount
    }}>
      {children}
    </StagedChangesContext.Provider>
  );
};

export const useStagedChanges = () => {
  const context = useContext(StagedChangesContext);
  if (!context) {
    throw new Error('useStagedChanges must be used within StagedChangesProvider');
  }
  return context;
};
```

#### 2. Create Apply Changes Button Component

Create `/frontend/src/components/ApplyChangesButton.tsx`:

```typescript
import React, { useState } from 'react';
import { Button, Spinner, Alert } from '@/components/ui';
import { useStagedChanges } from '@/contexts/StagedChangesContext';
import { orchestratorAPI } from '@/services/api';
import { useToast } from '@/hooks/useToast';

export const ApplyChangesButton: React.FC<{ topologyId: string }> = ({ topologyId }) => {
  const { stagedChanges, clearStagedChanges, hasUnappliedChanges, getChangeCount } = useStagedChanges();
  const [isApplying, setIsApplying] = useState(false);
  const { toast } = useToast();

  const handleApply = async () => {
    setIsApplying(true);

    try {
      const response = await orchestratorAPI.applyChanges(topologyId, stagedChanges);

      if (response.success) {
        toast({
          title: 'Changes Applied',
          description: `Successfully applied ${response.applied_count} changes`,
          variant: 'success'
        });
        clearStagedChanges();
      } else {
        toast({
          title: 'Apply Failed',
          description: response.message,
          variant: 'error'
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to apply changes',
        variant: 'error'
      });
      console.error(error);
    } finally {
      setIsApplying(false);
    }
  };

  const changeCount = getChangeCount();

  return (
    <Button
      onClick={handleApply}
      disabled={!hasUnappliedChanges || isApplying}
      variant="primary"
      className="flex items-center gap-2"
    >
      {isApplying && <Spinner size="sm" />}
      {isApplying ? 'Applying...' : `Apply Changes (${changeCount})`}
    </Button>
  );
};
```

#### 3. Add API Method

Update `/frontend/src/services/api.ts`:

```typescript
export const orchestratorAPI = {
  // ... existing methods

  applyChanges: async (topologyId: string, changes: StagedChanges) => {
    const response = await fetch('/api/orchestrator/apply-changes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topology_id: topologyId,
        changes
      })
    });

    if (!response.ok) {
      throw new Error('Failed to apply changes');
    }

    return response.json();
  }
};
```

#### 4. Update Topology Editor to Use Staged Changes

Modify device/link creation, update, and delete handlers to stage changes instead of immediate API calls:

```typescript
// OLD (immediate):
const handleAddDevice = async (device) => {
  await topologyAPI.createDevice(topologyId, device);
};

// NEW (staged):
const handleAddDevice = (device) => {
  addDeviceStaged(device);
  // Add to local canvas immediately for preview
  setLocalDevices(prev => [...prev, device]);
};
```

---

## 📊 Overall Progress

| Phase | Component | Status | Completion |
|-------|-----------|--------|------------|
| 1 | Emulation Container | ✅ Complete | 100% |
| 2 | Orchestrator Service | 🚧 In Progress | 70% |
| 3 | Topology Service | ⏳ TODO | 0% |
| 4 | Frontend | ⏳ TODO | 0% |

**Total Progress**: ~42% (1 out of 4 phases complete, 1 partially done)

---

## 🎯 Next Steps

### Immediate (Today):
1. ✅ Disable auto-sync event handlers in orchestrator
2. ✅ Add apply-changes endpoint to orchestrator
3. ⏳ Test apply endpoint with curl/Postman

### Short-term (This Week):
4. ⏳ Add batch-update endpoint to topology service
5. ⏳ Test full flow: orchestrator → topology service → database
6. ⏳ Create frontend staged changes context

### Medium-term (Next Week):
7. ⏳ Implement Apply button component
8. ⏳ Update topology editor to use staged changes
9. ⏳ Add changes preview panel
10. ⏳ End-to-end testing

---

## 🧪 Testing Checklist

### Phase 2 Testing (Orchestrator):
- [ ] Test apply-changes endpoint with sample payload
- [ ] Verify devices are added to Mininet
- [ ] Verify rollback works on failure
- [ ] Verify database persistence

### Phase 3 Testing (Topology Service):
- [ ] Test batch-update endpoint directly
- [ ] Verify database transactions are atomic
- [ ] Verify no events are published (no loops)

### Phase 4 Testing (Frontend):
- [ ] Staged changes accumulate correctly
- [ ] Apply button shows correct count
- [ ] Apply button disabled when no changes
- [ ] Success/failure messages display correctly
- [ ] Staged changes clear after successful apply

### Integration Testing:
- [ ] Add device → Apply → Verify in Mininet + DB
- [ ] Update device → Apply → Verify changes
- [ ] Remove device → Apply → Verify removal
- [ ] Add link → Apply → Verify connectivity
- [ ] Mixed changes → Apply → All succeed
- [ ] Trigger failure mid-apply → Verify rollback
- [ ] WiFi devices (AP, Station) work correctly
- [ ] Docker containers work correctly

---

## 📝 Files Created

1. ✅ `MIGRATION_PLAN.md` - Complete migration guide with code examples
2. ✅ `apply_changes_handler.py` - ApplyChangesHandler class
3. ✅ `DISABLE_AUTO_SYNC_INSTRUCTIONS.md` - Step-by-step disable instructions
4. ✅ `IMPLEMENTATION_STATUS.md` - This file

---

## 🔧 Configuration

No environment variables needed yet. Future consideration:

```env
# Feature flag to enable/disable auto-sync
AUTO_SYNC_ENABLED=false

# Timeout for database persistence after Mininet apply
DATABASE_PERSIST_TIMEOUT=30
```

---

## ❓ Open Questions / Decisions Needed

1. **Rollback Granularity**: Should we snapshot device/link state before updates for perfect rollback?
   - Current: No snapshots, can't rollback updates perfectly
   - Proposal: Add snapshot capability

2. **Database Failure Handling**: If Mininet succeeds but DB fails:
   - Current: Raise error, keep Mininet state (out of sync)
   - Alternative: Force rollback everything
   - Decision: Keep current (safer, admin can manually sync)

3. **Partial Apply**: Allow applying selected changes vs all staged changes?
   - Current: All or nothing
   - Proposal: Add checkbox to select which changes to apply

4. **Auto-Save**: Should topology structure still auto-save (non-emulation state)?
   - Current: Everything requires Apply button
   - Proposal: Auto-save topology metadata, require Apply for devices/links

---

## 📖 Documentation

- [MIGRATION_PLAN.md](MIGRATION_PLAN.md) - Full implementation guide
- [DISABLE_AUTO_SYNC_INSTRUCTIONS.md](DISABLE_AUTO_SYNC_INSTRUCTIONS.md) - Disable auto-sync steps
- Phase 1 is documented in emulation container README
- Frontend changes will be documented in component comments

---

**Last Updated**: 2025-01-23
**Status**: Phase 1 Complete, Phase 2 In Progress
