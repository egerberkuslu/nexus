import React, { useState, useEffect } from 'react';
import { Database, Camera, Play, Trash2, Download } from 'lucide-react';

const SnapshotsWidget = ({ onOpenSnapshots, topology, networkStatus, controllerStatus, className = '' }) => {
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [latestSnapshot, setLatestSnapshot] = useState(null);

  // Load snapshots summary
  const loadSnapshotsSummary = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/snapshots/?limit=3');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();
      
      if (result.success) {
        setSnapshots(result.snapshots);
        setLatestSnapshot(result.snapshots[0] || null);
        setError(null);
      } else {
        throw new Error(result.error || 'Failed to load snapshots');
      }
    } catch (err) {
      console.error('Error loading snapshots summary:', err);
      
      // Show mock data when API is not available
      if (err.message.includes('fetch') || err.message.includes('NetworkError') || err.message.includes('Failed to fetch')) {
        setError('Backend not available - showing demo data');
        setSnapshots([
          {
            id: 'demo-1',
            name: 'Demo Snapshot 1',
            description: 'Sample snapshot for demonstration',
            snapshot_type: 'full',
            created_at: new Date().toISOString(),
            metadata: { node_count: 4, link_count: 3, controller_running: true }
          },
          {
            id: 'demo-2', 
            name: 'Demo Snapshot 2',
            description: 'Another sample snapshot',
            snapshot_type: 'topology_only',
            created_at: new Date(Date.now() - 86400000).toISOString(),
            metadata: { node_count: 6, link_count: 5, controller_running: false }
          }
        ]);
        setLatestSnapshot({
          id: 'demo-1',
          name: 'Demo Snapshot 1', 
          description: 'Sample snapshot for demonstration',
          snapshot_type: 'full',
          created_at: new Date().toISOString(),
          metadata: { node_count: 4, link_count: 3, controller_running: true }
        });
      } else {
        setError('Failed to load snapshots: ' + err.message);
      }
    }
  };

  // Quick create snapshot
  const quickCreateSnapshot = async () => {
    setLoading(true);
    try {
      // Prepare topology data to send with snapshot
      const topologyData = topology || {};
      
      console.log('Quick creating snapshot with topology data:', {
        nodes: topologyData.nodes?.length || 0,
        links: topologyData.links?.length || 0,
        controllers: topologyData.controllers?.length || 0
      });
      
      const response = await fetch('http://localhost:5000/api/snapshots/create', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: `Quick Snapshot ${new Date().toLocaleString()}`,
          description: 'Quick snapshot created from widget',
          snapshot_type: 'full',
          topology_data: topologyData
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.success) {
        await loadSnapshotsSummary(); // Refresh list
        alert('Snapshot created successfully!');
      } else {
        throw new Error(result.error || 'Failed to create snapshot');
      }
    } catch (err) {
      console.error('Error creating snapshot:', err);
      
      if (err.message.includes('fetch') || err.message.includes('NetworkError') || err.message.includes('Failed to fetch')) {
        alert('Backend not available. Cannot create snapshot.');
      } else {
        alert('Failed to create snapshot: ' + err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  // Load snapshots on mount
  useEffect(() => {
    loadSnapshotsSummary();
  }, []);

  return (
    <div className={`bg-white rounded-lg p-4 border border-gray-200 shadow-sm hover:shadow-md transition-shadow ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-800 flex items-center gap-2">
          <Database className="w-4 h-4 text-orange-600" />
          Simulation Snapshots
        </h3>
        <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded-full">
          {snapshots.length} saved
        </span>
      </div>
      
      <p className="text-sm text-gray-600 mb-3">
        Capture and restore complete simulation states
      </p>

      {/* Error Display */}
      {error && (
        <div className="mb-3 p-2 bg-red-50 text-red-600 text-xs rounded border border-red-200">
          {error}
        </div>
      )}

      {/* Latest Snapshot Info */}
      {latestSnapshot && (
        <div className="mb-3 p-3 bg-gray-50 rounded-lg border">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-gray-700">Latest Snapshot</span>
            <span className="text-xs text-gray-500">
              {new Date(latestSnapshot.created_at).toLocaleDateString()}
            </span>
          </div>
          <div className="text-sm font-medium text-gray-900 truncate">
            {latestSnapshot.name}
          </div>
          {latestSnapshot.metadata && (
            <div className="text-xs text-gray-600 mt-1">
              {latestSnapshot.metadata.node_count || 0} nodes, {latestSnapshot.metadata.link_count || 0} links
            </div>
          )}
        </div>
      )}

      {/* Quick Actions */}
      <div className="space-y-2">
        <button
          onClick={quickCreateSnapshot}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-orange-100 text-orange-700 rounded-lg hover:bg-orange-200 transition-colors disabled:opacity-50"
          disabled={loading}
        >
          <Camera size={16} />
          {loading ? 'Creating...' : 'Quick Snapshot'}
        </button>
        
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={onOpenSnapshots}
            className="flex items-center justify-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs hover:bg-blue-100 transition-colors"
          >
            <Database size={12} />
            Manage
          </button>
          
          {latestSnapshot && (
            <button
              onClick={async () => {
                if (latestSnapshot.id.startsWith('demo-')) {
                  alert('Demo snapshot - Backend not available');
                  return;
                }
                
                try {
                  const response = await fetch(`http://localhost:5000/api/snapshots/${latestSnapshot.id}/restore`, {
                    method: 'POST',
                  });
                  
                  if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                  }
                  
                  const result = await response.json();
                  
                  if (result.success) {
                    alert('Latest snapshot restored!');
                  } else {
                    alert('Error: ' + (result.error || 'Failed to restore'));
                  }
                } catch (err) {
                  if (err.message.includes('fetch') || err.message.includes('NetworkError') || err.message.includes('Failed to fetch')) {
                    alert('Backend not available. Cannot restore snapshot.');
                  } else {
                    alert('Error restoring snapshot: ' + err.message);
                  }
                }
              }}
              className="flex items-center justify-center gap-1 px-2 py-1 bg-green-50 text-green-700 rounded text-xs hover:bg-green-100 transition-colors"
            >
              <Play size={12} />
              Restore
            </button>
          )}
        </div>
      </div>

      {/* Recent Snapshots List */}
      {snapshots.length > 1 && (
        <div className="mt-3 pt-3 border-t border-gray-200">
          <div className="text-xs font-medium text-gray-700 mb-2">Recent Snapshots</div>
          <div className="space-y-1">
            {snapshots.slice(1, 3).map((snapshot) => (
              <div key={snapshot.id} className="flex items-center justify-between text-xs">
                <span className="text-gray-600 truncate flex-1 mr-2">
                  {snapshot.name}
                </span>
                <div className="flex gap-1">
                  <button
                    onClick={async () => {
                      try {
                        const response = await fetch(`http://localhost:5000/api/snapshots/${snapshot.id}/restore`, {
                          method: 'POST',
                        });
                        const result = await response.json();
                        
                        if (result.success) {
                          alert(`Snapshot "${snapshot.name}" restored!`);
                        } else {
                          alert('Error: ' + (result.error || 'Failed to restore'));
                        }
                      } catch (err) {
                        alert('Error restoring snapshot: ' + err.message);
                      }
                    }}
                    className="text-green-600 hover:text-green-800 p-1"
                    title="Restore"
                  >
                    <Play size={10} />
                  </button>
                  <button
                    onClick={async () => {
                      if (window.confirm(`Delete "${snapshot.name}"?`)) {
                        try {
                          const response = await fetch(`http://localhost:5000/api/snapshots/${snapshot.id}`, {
                            method: 'DELETE',
                          });
                          const result = await response.json();
                          
                          if (result.success) {
                            await loadSnapshotsSummary();
                          } else {
                            alert('Error: ' + (result.error || 'Failed to delete'));
                          }
                        } catch (err) {
                          alert('Error deleting snapshot: ' + err.message);
                        }
                      }
                    }}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="Delete"
                  >
                    <Trash2 size={10} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty State */}
      {snapshots.length === 0 && !error && (
        <div className="text-center py-3 text-gray-500">
          <Database className="w-8 h-8 mx-auto mb-2 text-gray-400" />
          <p className="text-xs">No snapshots yet</p>
          <p className="text-xs">Create your first snapshot!</p>
        </div>
      )}
    </div>
  );
};

export default SnapshotsWidget;
