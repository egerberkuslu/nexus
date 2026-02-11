# Frontend Quick Start: Implementing Button-Triggered Apply

## Overview

The backend is 100% ready! This guide shows how to add the frontend to complete the button-triggered apply feature.

**Time to implement**: 2-3 days
**Complexity**: Medium
**Skills needed**: React, TypeScript, API integration

---

## Step 1: Create Staged Changes Context (30 min)

**File**: `frontend/src/contexts/StagedChangesContext.tsx`

```typescript
import React, { createContext, useContext, useState } from 'react';

export interface StagedDevice {
  id?: string;
  name: string;
  device_type: string;
  x?: number;
  y?: number;
  properties?: Record<string, any>;
}

export interface StagedLink {
  id?: string;
  source_node_id: string;
  target_node_id: string;
  bandwidth?: number;
  delay?: number;
  loss?: number;
  properties?: Record<string, any>;
}

export interface StagedChanges {
  add_devices: StagedDevice[];
  update_devices: StagedDevice[];
  remove_devices: Array<{ id: string }>;
  add_links: StagedLink[];
  update_links: StagedLink[];
  remove_links: Array<{ id: string }>;
}

interface StagedChangesContextType {
  stagedChanges: StagedChanges;
  addDeviceStaged: (device: StagedDevice) => void;
  updateDeviceStaged: (device: StagedDevice) => void;
  removeDeviceStaged: (deviceId: string) => void;
  addLinkStaged: (link: StagedLink) => void;
  updateLinkStaged: (link: StagedLink) => void;
  removeLinkStaged: (linkId: string) => void;
  clearStagedChanges: () => void;
  hasUnappliedChanges: boolean;
  getChangeCount: () => number;
  getSummary: () => Record<string, number>;
}

const StagedChangesContext = createContext<StagedChangesContextType | undefined>(undefined);

export const StagedChangesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [stagedChanges, setStagedChanges] = useState<StagedChanges>({
    add_devices: [],
    update_devices: [],
    remove_devices: [],
    add_links: [],
    update_links: [],
    remove_links: []
  });

  const addDeviceStaged = (device: StagedDevice) => {
    console.log('[Staged] Adding device:', device.name);
    setStagedChanges(prev => ({
      ...prev,
      add_devices: [...prev.add_devices, { id: device.id || undefined, ...device }]
    }));
  };

  const updateDeviceStaged = (device: StagedDevice) => {
    if (!device.id) throw new Error('Device ID required for update');
    console.log('[Staged] Updating device:', device.id);
    setStagedChanges(prev => ({
      ...prev,
      update_devices: [
        ...prev.update_devices.filter(d => d.id !== device.id),
        device
      ]
    }));
  };

  const removeDeviceStaged = (deviceId: string) => {
    console.log('[Staged] Removing device:', deviceId);
    setStagedChanges(prev => ({
      ...prev,
      remove_devices: [...prev.remove_devices, { id: deviceId }]
    }));
  };

  const addLinkStaged = (link: StagedLink) => {
    console.log('[Staged] Adding link:', link.source_node_id, '->', link.target_node_id);
    setStagedChanges(prev => ({
      ...prev,
      add_links: [...prev.add_links, { id: link.id || undefined, ...link }]
    }));
  };

  const updateLinkStaged = (link: StagedLink) => {
    if (!link.id) throw new Error('Link ID required for update');
    console.log('[Staged] Updating link:', link.id);
    setStagedChanges(prev => ({
      ...prev,
      update_links: [
        ...prev.update_links.filter(l => l.id !== link.id),
        link
      ]
    }));
  };

  const removeLinkStaged = (linkId: string) => {
    console.log('[Staged] Removing link:', linkId);
    setStagedChanges(prev => ({
      ...prev,
      remove_links: [...prev.remove_links, { id: linkId }]
    }));
  };

  const clearStagedChanges = () => {
    console.log('[Staged] Clearing all changes');
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

  const getSummary = () => ({
    devices_added: stagedChanges.add_devices.length,
    devices_updated: stagedChanges.update_devices.length,
    devices_removed: stagedChanges.remove_devices.length,
    links_added: stagedChanges.add_links.length,
    links_updated: stagedChanges.update_links.length,
    links_removed: stagedChanges.remove_links.length
  });

  return (
    <StagedChangesContext.Provider
      value={{
        stagedChanges,
        addDeviceStaged,
        updateDeviceStaged,
        removeDeviceStaged,
        addLinkStaged,
        updateLinkStaged,
        removeLinkStaged,
        clearStagedChanges,
        hasUnappliedChanges,
        getChangeCount,
        getSummary
      }}
    >
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

---

## Step 2: Create Apply Button Component (20 min)

**File**: `frontend/src/components/ApplyChangesButton.tsx`

```typescript
import React, { useState } from 'react';
import { useStagedChanges } from '@/contexts/StagedChangesContext';
import { useToast } from '@/hooks/useToast'; // Your toast component
import { Button } from '@/components/ui/Button'; // Your button component

interface ApplyChangesButtonProps {
  topologyId: string;
  onSuccess?: () => void;
  onError?: (error: string) => void;
}

export const ApplyChangesButton: React.FC<ApplyChangesButtonProps> = ({
  topologyId,
  onSuccess,
  onError
}) => {
  const { stagedChanges, clearStagedChanges, hasUnappliedChanges, getChangeCount, getSummary } =
    useStagedChanges();
  const [isApplying, setIsApplying] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  const { toast } = useToast();

  const changeCount = getChangeCount();
  const summary = getSummary();

  const handleApply = async () => {
    setIsApplying(true);

    try {
      const response = await fetch(`/api/topologies/${topologyId}/apply`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify({
          changes: stagedChanges,
          commit: true
        })
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to apply changes');
      }

      const result = await response.json();

      toast({
        title: 'Success',
        description: `Applied ${changeCount} changes successfully`,
        variant: 'success'
      });

      clearStagedChanges();
      onSuccess?.();

      // Reload topology
      window.location.reload();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      toast({
        title: 'Error',
        description: message,
        variant: 'error'
      });
      onError?.(message);
      console.error('Apply failed:', error);
    } finally {
      setIsApplying(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <Button
        onClick={handleApply}
        disabled={!hasUnappliedChanges || isApplying}
        variant={hasUnappliedChanges ? 'primary' : 'secondary'}
        style={{
          minWidth: '200px',
          padding: '10px 20px',
          fontSize: '14px',
          fontWeight: 'bold'
        }}
      >
        {isApplying ? (
          <>
            <span style={{ marginRight: '8px' }}>⏳</span>
            Applying {changeCount} changes...
          </>
        ) : (
          <>
            <span style={{ marginRight: '8px' }}>✓</span>
            Apply Changes ({changeCount})
          </>
        )}
      </Button>

      {hasUnappliedChanges && (
        <details style={{ padding: '10px', backgroundColor: '#f0f0f0', borderRadius: '4px' }}>
          <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>
            Preview changes ({changeCount})
          </summary>
          <div style={{ marginTop: '10px', fontSize: '12px' }}>
            {summary.devices_added > 0 && (
              <div>
                <strong>➕ Devices to add:</strong> {summary.devices_added}
              </div>
            )}
            {summary.devices_updated > 0 && (
              <div>
                <strong>📝 Devices to update:</strong> {summary.devices_updated}
              </div>
            )}
            {summary.devices_removed > 0 && (
              <div>
                <strong>❌ Devices to remove:</strong> {summary.devices_removed}
              </div>
            )}
            {summary.links_added > 0 && (
              <div>
                <strong>➕ Links to add:</strong> {summary.links_added}
              </div>
            )}
            {summary.links_updated > 0 && (
              <div>
                <strong>📝 Links to update:</strong> {summary.links_updated}
              </div>
            )}
            {summary.links_removed > 0 && (
              <div>
                <strong>❌ Links to remove:</strong> {summary.links_removed}
              </div>
            )}
          </div>
        </details>
      )}
    </div>
  );
};
```

---

## Step 3: Integrate Context into App (10 min)

**File**: `frontend/src/App.tsx` (or main layout)

```typescript
import { StagedChangesProvider } from '@/contexts/StagedChangesContext';

export default function App() {
  return (
    <StagedChangesProvider>
      {/* Your existing app content */}
    </StagedChangesProvider>
  );
}
```

---

## Step 4: Update Topology Editor (1-2 hours)

**Replace immediate API calls with staged changes:**

### Before (Old Pattern):
```typescript
const handleAddDevice = async (device: Device) => {
  try {
    await topologyAPI.createNode(topologyId, device);
    // Reload topology
    const updated = await topologyAPI.getTopology(topologyId);
    setTopology(updated);
  } catch (error) {
    toast.error('Failed to add device');
  }
};
```

### After (New Pattern):
```typescript
const { addDeviceStaged } = useStagedChanges();

const handleAddDevice = (device: Device) => {
  // Stage the change
  addDeviceStaged({
    id: device.id,
    name: device.name,
    device_type: device.type,
    x: device.position?.x,
    y: device.position?.y,
    properties: device.properties
  });

  // Update local UI immediately for feedback
  setLocalDevices([...localDevices, device]);
  toast.success(`${device.name} staged for addition`);
};

const handleRemoveDevice = (deviceId: string) => {
  const { removeDeviceStaged } = useStagedChanges();
  removeDeviceStaged(deviceId);
  setLocalDevices(localDevices.filter(d => d.id !== deviceId));
  toast.success('Device staged for removal');
};
```

**Similar changes for:**
- `handleUpdateDevice()` → use `updateDeviceStaged()`
- `handleAddLink()` → use `addLinkStaged()`
- `handleUpdateLink()` → use `updateLinkStaged()`
- `handleRemoveLink()` → use `removeLinkStaged()`

---

## Step 5: Add WiFi Device Configuration UI (1-2 hours)

Update your device form to show WiFi-specific fields:

```typescript
interface DeviceFormProps {
  device: Device;
  onSave: (device: Device) => void;
}

export const DeviceForm: React.FC<DeviceFormProps> = ({ device, onSave }) => {
  const [deviceType, setDeviceType] = useState(device.type);
  const [name, setName] = useState(device.name);
  const [ip, setIp] = useState(device.properties?.ip || '');

  // WiFi specific
  const [ssid, setSsid] = useState(device.properties?.ssid || '');
  const [channel, setChannel] = useState(device.properties?.channel || '6');
  const [mode, setMode] = useState(device.properties?.mode || 'g');
  const [security, setSecurity] = useState(device.properties?.security || 'open');
  const [password, setPassword] = useState(device.properties?.password || '');

  // Docker specific
  const [image, setImage] = useState(device.properties?.image || '');
  const [command, setCommand] = useState(device.properties?.command || '');

  const handleSave = () => {
    onSave({
      ...device,
      name,
      type: deviceType,
      properties: {
        ...device.properties,
        ip: ip || undefined,
        // WiFi properties
        ssid: deviceType === 'ap' || deviceType === 'station' ? ssid : undefined,
        channel: deviceType === 'ap' ? channel : undefined,
        mode: deviceType === 'ap' ? mode : undefined,
        security: deviceType === 'ap' ? security : undefined,
        password: deviceType === 'ap' && security !== 'open' ? password : undefined,
        // Docker properties
        image: deviceType === 'container' ? image : undefined,
        command: deviceType === 'container' ? command : undefined
      }
    });
  };

  return (
    <form onSubmit={(e) => { e.preventDefault(); handleSave(); }}>
      <input
        type="text"
        placeholder="Device Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
        required
      />

      <select value={deviceType} onChange={(e) => setDeviceType(e.target.value)}>
        <option value="host">Host</option>
        <option value="switch">Switch</option>
        <option value="router">Router</option>
        <option value="ap">WiFi Access Point</option>
        <option value="station">WiFi Station</option>
        <option value="container">Docker Container</option>
      </select>

      {/* Common properties */}
      {(deviceType === 'host' || deviceType === 'router' || deviceType === 'station') && (
        <input
          type="text"
          placeholder="IP Address (e.g., 10.0.0.1)"
          value={ip}
          onChange={(e) => setIp(e.target.value)}
        />
      )}

      {/* WiFi AP properties */}
      {deviceType === 'ap' && (
        <>
          <input
            type="text"
            placeholder="SSID"
            value={ssid}
            onChange={(e) => setSsid(e.target.value)}
            required
          />
          <select value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="1">Channel 1 (2.4 GHz)</option>
            <option value="6">Channel 6 (2.4 GHz)</option>
            <option value="11">Channel 11 (2.4 GHz)</option>
            <option value="36">Channel 36 (5 GHz)</option>
            <option value="40">Channel 40 (5 GHz)</option>
            <option value="44">Channel 44 (5 GHz)</option>
          </select>
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="a">802.11a (5 GHz)</option>
            <option value="b">802.11b (2.4 GHz)</option>
            <option value="g">802.11g (2.4 GHz)</option>
            <option value="n">802.11n (2.4/5 GHz)</option>
            <option value="ac">802.11ac (5 GHz)</option>
            <option value="ax">802.11ax (2.4/5 GHz)</option>
          </select>
          <select value={security} onChange={(e) => setSecurity(e.target.value)}>
            <option value="open">Open</option>
            <option value="wpa">WPA</option>
            <option value="wpa2">WPA2</option>
            <option value="wpa3">WPA3</option>
          </select>
          {security !== 'open' && (
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          )}
        </>
      )}

      {/* Docker properties */}
      {deviceType === 'container' && (
        <>
          <input
            type="text"
            placeholder="Docker Image (e.g., ubuntu:22.04)"
            value={image}
            onChange={(e) => setImage(e.target.value)}
            required
          />
          <input
            type="text"
            placeholder="Command (e.g., /bin/bash)"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
          />
        </>
      )}

      <button type="submit">Save Device</button>
    </form>
  );
};
```

---

## Step 6: Add Apply Button to Toolbar (10 min)

**File**: `frontend/src/components/TopologyToolbar.tsx`

```typescript
import { ApplyChangesButton } from './ApplyChangesButton';
import { useStagedChanges } from '@/contexts/StagedChangesContext';

export const TopologyToolbar: React.FC<{ topologyId: string }> = ({ topologyId }) => {
  const { hasUnappliedChanges } = useStagedChanges();

  return (
    <div style={{
      display: 'flex',
      gap: '10px',
      padding: '10px',
      backgroundColor: hasUnappliedChanges ? '#fff3cd' : 'white',
      borderBottom: '1px solid #ddd',
      alignItems: 'center'
    }}>
      <span>Topology Editor</span>
      {hasUnappliedChanges && (
        <span style={{ color: '#856404', fontSize: '12px' }}>
          ⚠️ You have unapplied changes
        </span>
      )}
      <div style={{ marginLeft: 'auto' }}>
        <ApplyChangesButton topologyId={topologyId} />
      </div>
    </div>
  );
};
```

---

## Step 7: Testing (1-2 hours)

### Manual Test Checklist

- [ ] Add device → Check it's staged
- [ ] Add multiple devices → Count should increase
- [ ] Clear staged changes → Count should reset
- [ ] Apply changes → Should call API successfully
- [ ] Check Mininet for new device
- [ ] Check database for persisted device
- [ ] Add WiFi AP → Check SSID/channel options appear
- [ ] Add Station → Check WiFi options appear
- [ ] Apply WiFi changes → Should work in Mininet-WiFi
- [ ] Rollback on failure → Device should not be added if link invalid

### API Test Commands

```bash
# Get topology ID
TOPOLOGY_ID="your-topology-id"

# Test apply endpoint
curl -X POST http://localhost:8002/api/topologies/$TOPOLOGY_ID/apply \
  -H "Content-Type: application/json" \
  -d '{
    "changes": {
      "add_devices": [{
        "id": "node-test",
        "name": "test-host",
        "device_type": "host",
        "properties": {"ip": "10.0.0.99"}
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

## Common Pitfalls & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Changes not staged | Forgot to call staged function | Verify `addDeviceStaged()` is called |
| Apply button disabled | No changes staged | Check `hasUnappliedChanges` state |
| API fails | Missing authorization | Add token to headers |
| Device not in Mininet | Didn't start emulation | Start emulation first |
| WiFi not working | Device type wrong | Use `ap` for AP, `station` for stations |

---

## Performance Tips

1. **Batch operations**: Stage multiple changes before applying
2. **Local UI updates**: Update UI immediately while API processes
3. **Debounce**: For form inputs, debounce 500ms before staging
4. **Cache**: Don't reload entire topology after apply, update locally

---

## Next: Full Integration Checklist

```
✅ Step 1: Context created
✅ Step 2: Button component created
✅ Step 3: Provider added to app
⏳ Step 4: Topology editor updated
⏳ Step 5: WiFi UI added
⏳ Step 6: Toolbar updated
⏳ Step 7: Testing complete
⏳ Step 8: Deploy to production
```

---

## Support & Resources

- **Backend API Docs**: See [IMPLEMENTATION_COMPLETE.md](IMPLEMENTATION_COMPLETE.md)
- **Schema Definitions**: `backend/shared/schemas/topology_schema.py`
- **Example Frontend**: Check other components in `frontend/src/components/`

---

**Ready to implement?** Start with Step 1 and work through sequentially. Each step is independent and testable!
