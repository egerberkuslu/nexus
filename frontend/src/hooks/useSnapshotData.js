import { useCallback } from 'react';

export const useSnapshotData = ({
  apiCall,
  addLog,
  setSnapshots,
  setLoading,
  refreshTopology = null
}) => {
  // Fetch all snapshots
  const fetchSnapshots = useCallback(async () => {
    try {
      const result = await apiCall('/snapshots/list');
      if (result.success) {
        if (setSnapshots) setSnapshots(result.data.snapshots || []);
        return result.data.snapshots || [];
      }
    } catch (error) {
      addLog(`❌ Failed to fetch snapshots: ${error.message}`, 'error', 'snapshot');
    }
    return [];
  }, [apiCall, addLog, setSnapshots]);

  // Create snapshot
  const createSnapshot = useCallback(async (name, description = '', snapshotType = 'full') => {
    setLoading(true);
    try {
      const result = await apiCall('/snapshots/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          type: snapshotType
        })
      });

      if (result.success && result.data.success) {
        addLog(`📸 Snapshot "${name}" created successfully`, 'success', 'snapshot');
        await fetchSnapshots(); // Refresh snapshots list
        return result.data.snapshot_id;
      } else {
        addLog(`❌ Failed to create snapshot: ${result.data?.error || result.error}`, 'error', 'snapshot');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error creating snapshot: ${error.message}`, 'error', 'snapshot');
      return null;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading, fetchSnapshots]);

  // Restore snapshot
  const restoreSnapshot = useCallback(async (snapshotId) => {
    setLoading(true);
    try {
      const result = await apiCall(`/snapshots/restore/${snapshotId}`, {
        method: 'POST'
      });

      if (result.success && result.data.success) {
        addLog(`🔄 Snapshot restored successfully`, 'success', 'snapshot');
        
        // Refresh topology data to show the restored network in UI
        if (refreshTopology && typeof refreshTopology === 'function') {
          try {
            await refreshTopology();
            addLog(`🔄 Topology visualization updated`, 'success', 'snapshot');
          } catch (error) {
            addLog(`⚠️ Snapshot restored but failed to refresh topology: ${error.message}`, 'warning', 'snapshot');
          }
        }
        
        return true;
      } else {
        addLog(`❌ Failed to restore snapshot: ${result.data?.error || result.error}`, 'error', 'snapshot');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error restoring snapshot: ${error.message}`, 'error', 'snapshot');
      return false;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading, refreshTopology]);

  // Delete snapshot
  const deleteSnapshot = useCallback(async (snapshotId) => {
    try {
      const result = await apiCall(`/snapshots/${snapshotId}`, {
        method: 'DELETE'
      });

      if (result.success && result.data.success) {
        addLog(`🗑️ Snapshot deleted successfully`, 'success', 'snapshot');
        await fetchSnapshots(); // Refresh snapshots list
        return true;
      } else {
        addLog(`❌ Failed to delete snapshot: ${result.data?.error || result.error}`, 'error', 'snapshot');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error deleting snapshot: ${error.message}`, 'error', 'snapshot');
      return false;
    }
  }, [apiCall, addLog, fetchSnapshots]);

  // Export snapshot
  const exportSnapshot = useCallback(async (snapshotId, format = 'json') => {
    try {
      const result = await apiCall(`/snapshots/${snapshotId}/export?format=${format}`);
      if (result.success) {
        // Create download link
        const blob = new Blob([JSON.stringify(result.data, null, 2)], {
          type: 'application/json'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `snapshot-${snapshotId}.${format}`;
        a.click();
        URL.revokeObjectURL(url);

        addLog(`📤 Snapshot exported successfully`, 'success', 'snapshot');
        return true;
      } else {
        addLog(`❌ Failed to export snapshot: ${result.data?.error || result.error}`, 'error', 'snapshot');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error exporting snapshot: ${error.message}`, 'error', 'snapshot');
      return false;
    }
  }, [apiCall, addLog]);

  // Import snapshot
  const importSnapshot = useCallback(async (file) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('snapshot', file);

      const result = await apiCall('/snapshots/import', {
        method: 'POST',
        body: formData
      });

      if (result.success && result.data.success) {
        addLog(`📥 Snapshot imported successfully`, 'success', 'snapshot');
        await fetchSnapshots(); // Refresh snapshots list
        return result.data.snapshot_id;
      } else {
        addLog(`❌ Failed to import snapshot: ${result.data?.error || result.error}`, 'error', 'snapshot');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error importing snapshot: ${error.message}`, 'error', 'snapshot');
      return null;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading, fetchSnapshots]);

  // Get snapshot details
  const getSnapshotDetails = useCallback(async (snapshotId) => {
    try {
      const result = await apiCall(`/snapshots/${snapshotId}`);
      if (result.success) {
        return result.data.snapshot;
      } else {
        addLog(`❌ Failed to get snapshot details: ${result.data?.error || result.error}`, 'error', 'snapshot');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error getting snapshot details: ${error.message}`, 'error', 'snapshot');
      return null;
    }
  }, [apiCall, addLog]);

  // Get snapshot comparison
  const compareSnapshots = useCallback(async (snapshotId1, snapshotId2) => {
    try {
      const result = await apiCall(`/snapshots/compare/${snapshotId1}/${snapshotId2}`);
      if (result.success) {
        addLog(`📊 Snapshot comparison completed`, 'success', 'snapshot');
        return result.data.comparison;
      } else {
        addLog(`❌ Failed to compare snapshots: ${result.data?.error || result.error}`, 'error', 'snapshot');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error comparing snapshots: ${error.message}`, 'error', 'snapshot');
      return null;
    }
  }, [apiCall, addLog]);

  return {
    fetchSnapshots,
    createSnapshot,
    restoreSnapshot,
    deleteSnapshot,
    exportSnapshot,
    importSnapshot,
    getSnapshotDetails,
    compareSnapshots
  };
};
