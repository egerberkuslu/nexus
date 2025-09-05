import React, { useState, useEffect, useCallback } from 'react';

const SimulationSnapshots = ({ isOpen, onClose, topology, networkStatus, controllerStatus }) => {
  // State management
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  // Dialog states
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [snapshotName, setSnapshotName] = useState('');
  const [snapshotDescription, setSnapshotDescription] = useState('');
  const [snapshotType, setSnapshotType] = useState('full');
  
  // Comparison state
  const [compareMode, setCompareMode] = useState(false);
  const [selectedSnapshots, setSelectedSnapshots] = useState([]);
  const [comparisonResult, setComparisonResult] = useState(null);
  const [expandedSnapshot, setExpandedSnapshot] = useState(null);

  // Load snapshots from server
  const loadSnapshots = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch('http://localhost:5000/api/snapshots/');
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const result = await response.json();
      
      if (result.success) {
        setSnapshots(result.snapshots);
      } else {
        throw new Error(result.error || 'Failed to load snapshots');
      }
    } catch (err) {
      console.error('Error loading snapshots:', err);
      
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
            updated_at: new Date().toISOString(),
            metadata: { 
              node_count: 4, 
              link_count: 3, 
              controller_running: true,
              mininet_running: true,
              created_by: 'demo'
            }
          },
          {
            id: 'demo-2', 
            name: 'Demo Snapshot 2',
            description: 'Another sample snapshot',
            snapshot_type: 'topology_only',
            created_at: new Date(Date.now() - 86400000).toISOString(),
            updated_at: new Date(Date.now() - 86400000).toISOString(),
            metadata: { 
              node_count: 6, 
              link_count: 5, 
              controller_running: false,
              mininet_running: false,
              created_by: 'demo'
            }
          },
          {
            id: 'demo-3',
            name: 'Demo Snapshot 3',
            description: 'Third sample snapshot with more nodes',
            snapshot_type: 'runtime_state',
            created_at: new Date(Date.now() - 172800000).toISOString(),
            updated_at: new Date(Date.now() - 172800000).toISOString(),
            metadata: { 
              node_count: 8, 
              link_count: 10, 
              controller_running: true,
              mininet_running: true,
              created_by: 'demo'
            }
          }
        ]);
      } else {
        setError('Failed to load snapshots: ' + err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Create new snapshot
  const createSnapshot = useCallback(async () => {
    if (!snapshotName.trim()) {
      alert('Please enter a snapshot name');
      return;
    }

    setLoading(true);
    
    try {
      // Prepare topology data to send with snapshot
      const topologyData = topology || {};
      
      console.log('Creating snapshot with topology data:', {
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
          name: snapshotName,
          description: snapshotDescription,
          snapshot_type: snapshotType,
          topology_data: topologyData
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.success) {
        alert(`Snapshot "${snapshotName}" created successfully!`);
        setCreateDialogOpen(false);
        setSnapshotName('');
        setSnapshotDescription('');
        setSnapshotType('full');
        loadSnapshots(); // Refresh list
      } else {
        throw new Error(result.error || 'Failed to create snapshot');
      }
    } catch (err) {
      console.error('Error creating snapshot:', err);
      
      if (err.message.includes('fetch') || err.message.includes('NetworkError') || err.message.includes('Failed to fetch')) {
        alert('Backend not available. Cannot create snapshot.');
      } else {
        alert('Error creating snapshot: ' + err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [snapshotName, snapshotDescription, snapshotType, topology, loadSnapshots]);

  // Restore snapshot
  const restoreSnapshot = useCallback(async (snapshotId, snapshotName) => {
    if (snapshotId.startsWith('demo-')) {
      alert('Demo snapshot - Backend not available');
      return;
    }
    
    if (!window.confirm(`Are you sure you want to restore snapshot "${snapshotName}"? This will stop the current network and restore the saved state.`)) {
      return;
    }

    setLoading(true);
    
    try {
      const response = await fetch(`http://localhost:5000/api/snapshots/${snapshotId}/restore`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.success) {
        alert(`Snapshot "${snapshotName}" restored successfully!`);
      } else {
        throw new Error(result.error || 'Failed to restore snapshot');
      }
    } catch (err) {
      console.error('Error restoring snapshot:', err);
      
      if (err.message.includes('fetch') || err.message.includes('NetworkError') || err.message.includes('Failed to fetch')) {
        alert('Backend not available. Cannot restore snapshot.');
      } else {
        alert('Error restoring snapshot: ' + err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Delete snapshot
  const deleteSnapshot = useCallback(async (snapshotId, snapshotName) => {
    if (snapshotId.startsWith('demo-')) {
      alert('Demo snapshot - Backend not available');
      return;
    }
    
    if (!window.confirm(`Are you sure you want to delete snapshot "${snapshotName}"? This action cannot be undone.`)) {
      return;
    }

    setLoading(true);
    
    try {
      const response = await fetch(`http://localhost:5000/api/snapshots/${snapshotId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const result = await response.json();
      
      if (result.success) {
        alert(`Snapshot "${snapshotName}" deleted successfully!`);
        loadSnapshots(); // Refresh list
      } else {
        throw new Error(result.error || 'Failed to delete snapshot');
      }
    } catch (err) {
      console.error('Error deleting snapshot:', err);
      
      if (err.message.includes('fetch') || err.message.includes('NetworkError') || err.message.includes('Failed to fetch')) {
        alert('Backend not available. Cannot delete snapshot.');
      } else {
        alert('Error deleting snapshot: ' + err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [loadSnapshots]);

  // Export snapshot
  const exportSnapshot = useCallback(async (snapshotId, snapshotName) => {
    try {
      const response = await fetch(`http://localhost:5000/api/snapshots/export/${snapshotId}`);
      const result = await response.json();
      
      if (result.success) {
        // Create and download file
        const dataStr = JSON.stringify(result.export_data, null, 2);
        const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr);
        
        const exportFileDefaultName = `snapshot_${snapshotName}_${new Date().toISOString().slice(0, 10)}.json`;
        
        const linkElement = document.createElement('a');
        linkElement.setAttribute('href', dataUri);
        linkElement.setAttribute('download', exportFileDefaultName);
        linkElement.click();
        
        alert(`Snapshot "${snapshotName}" exported successfully!`);
      } else {
        throw new Error(result.error || 'Failed to export snapshot');
      }
    } catch (err) {
      console.error('Error exporting snapshot:', err);
      alert('Error exporting snapshot: ' + err.message);
    }
  }, []);

  // Compare snapshots
  const compareSnapshots = useCallback(async () => {
    if (selectedSnapshots.length !== 2) {
      alert('Please select exactly 2 snapshots to compare');
      return;
    }

    setLoading(true);
    
    try {
      const [snap1, snap2] = selectedSnapshots;
      const response = await fetch(`http://localhost:5000/api/snapshots/compare/${snap1}/${snap2}`);
      const result = await response.json();
      
      if (result.success) {
        setComparisonResult(result.comparison);
      } else {
        throw new Error(result.error || 'Failed to compare snapshots');
      }
    } catch (err) {
      console.error('Error comparing snapshots:', err);
      alert('Error comparing snapshots: ' + err.message);
    } finally {
      setLoading(false);
    }
  }, [selectedSnapshots]);

  // Handle snapshot selection for comparison
  const toggleSnapshotSelection = useCallback((snapshotId) => {
    setSelectedSnapshots(prev => {
      if (prev.includes(snapshotId)) {
        return prev.filter(id => id !== snapshotId);
      } else if (prev.length < 2) {
        return [...prev, snapshotId];
      } else {
        // Replace first selection with new one
        return [prev[1], snapshotId];
      }
    });
  }, []);

  // Load snapshots on component mount
  useEffect(() => {
    loadSnapshots();
  }, [loadSnapshots]);

  // Format date for display
  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  // Get snapshot type badge color
  const getTypeColor = (type) => {
    switch (type) {
      case 'full': return 'bg-green-100 text-green-800';
      case 'topology_only': return 'bg-blue-100 text-blue-800';
      case 'runtime_state': return 'bg-yellow-100 text-yellow-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg w-full max-w-7xl h-[90vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex-shrink-0 bg-white border-b border-gray-200 p-6">
          <div className="flex justify-between items-center mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Simulation Snapshots</h1>
              <p className="text-gray-600 mt-1">Capture and restore complete simulation states</p>
            </div>
            
            <button
              onClick={onClose}
              className="text-gray-500 hover:text-gray-700 p-2 rounded-lg hover:bg-gray-100 transition-colors"
              title="Close Snapshots"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <div className="flex gap-3">
            <button
              onClick={() => setCompareMode(!compareMode)}
              className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                compareMode 
                  ? 'bg-blue-600 text-white hover:bg-blue-700' 
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {compareMode ? 'Exit Compare' : 'Compare Mode'}
            </button>
          
          {compareMode && selectedSnapshots.length === 2 && (
            <button
              onClick={compareSnapshots}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg font-medium hover:bg-purple-700 transition-colors"
              disabled={loading}
            >
              Compare Selected
            </button>
          )}
          
          <button
            onClick={loadSnapshots}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg font-medium hover:bg-gray-200 transition-colors"
            disabled={loading}
          >
            Refresh
          </button>
          
          <button
            onClick={() => setCreateDialogOpen(true)}
            className="px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
            disabled={loading}
          >
            Create Snapshot
          </button>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 overflow-y-auto p-6">
        {/* Error Display */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-300 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {/* Loading Indicator */}
        {loading && (
          <div className="mb-4 p-4 bg-blue-100 border border-blue-300 text-blue-700 rounded-lg">
            Loading...
          </div>
        )}

        {/* Compare Mode Info */}
        {compareMode && (
          <div className="mb-4 p-4 bg-purple-100 border border-purple-300 text-purple-700 rounded-lg">
            <strong>Compare Mode:</strong> Select exactly 2 snapshots to compare. 
            Selected: {selectedSnapshots.length}/2
          </div>
        )}

        {/* Snapshots Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
        {snapshots.map((snapshot) => (
          <div 
            key={snapshot.id} 
            className={`bg-white rounded-lg shadow-md border-2 transition-all ${
              compareMode && selectedSnapshots.includes(snapshot.id)
                ? 'border-purple-500 bg-purple-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            {/* Snapshot Header */}
            <div className="p-4 border-b border-gray-200">
              <div className="flex justify-between items-start mb-2">
                <h3 className="font-semibold text-lg text-gray-900 truncate">
                  {snapshot.name}
                </h3>
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${getTypeColor(snapshot.snapshot_type)}`}>
                  {snapshot.snapshot_type}
                </span>
              </div>
              
              {snapshot.description && (
                <p className="text-gray-600 text-sm mb-2">{snapshot.description}</p>
              )}
              
              <div className="text-xs text-gray-500 space-y-1">
                <div>Created: {formatDate(snapshot.created_at)}</div>
                {snapshot.updated_at !== snapshot.created_at && (
                  <div>Updated: {formatDate(snapshot.updated_at)}</div>
                )}
              </div>
            </div>

            {/* Snapshot Metadata */}
            {snapshot.metadata && (
              <div className="p-4 border-b border-gray-200 bg-gray-50">
                <div className="grid grid-cols-2 gap-2 text-sm">
                  {/* Basic Topology Info */}
                  {snapshot.metadata.node_count !== undefined && (
                    <div>
                      <span className="text-gray-600">Total Nodes:</span>
                      <span className="font-medium ml-1">{snapshot.metadata.node_count}</span>
                    </div>
                  )}
                  {snapshot.metadata.link_count !== undefined && (
                    <div>
                      <span className="text-gray-600">Links:</span>
                      <span className="font-medium ml-1">{snapshot.metadata.link_count}</span>
                    </div>
                  )}
                  
                  {/* Detailed Node Breakdown */}
                  {snapshot.metadata.host_count !== undefined && snapshot.metadata.host_count > 0 && (
                    <div>
                      <span className="text-gray-600">Hosts:</span>
                      <span className="font-medium ml-1">{snapshot.metadata.host_count}</span>
                    </div>
                  )}
                  {snapshot.metadata.switch_count !== undefined && snapshot.metadata.switch_count > 0 && (
                    <div>
                      <span className="text-gray-600">Switches:</span>
                      <span className="font-medium ml-1">{snapshot.metadata.switch_count}</span>
                    </div>
                  )}
                  {snapshot.metadata.router_count !== undefined && snapshot.metadata.router_count > 0 && (
                    <div>
                      <span className="text-gray-600">Routers:</span>
                      <span className="font-medium ml-1">{snapshot.metadata.router_count}</span>
                    </div>
                  )}
                  
                  {/* Status Info */}
                  {snapshot.metadata.mininet_running !== undefined && (
                    <div>
                      <span className="text-gray-600">Network:</span>
                      <span className={`font-medium ml-1 ${
                        snapshot.metadata.mininet_running ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {snapshot.metadata.mininet_running ? 'Running' : 'Stopped'}
                      </span>
                    </div>
                  )}
                  {snapshot.metadata.controller_running !== undefined && (
                    <div>
                      <span className="text-gray-600">Controller:</span>
                      <span className={`font-medium ml-1 ${
                        snapshot.metadata.controller_running ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {snapshot.metadata.controller_running ? 'Running' : 'Stopped'}
                      </span>
                    </div>
                  )}
                  
                  {/* Configuration Info */}
                  {snapshot.metadata.has_live_configs && (
                    <div>
                      <span className="text-gray-600">Live Configs:</span>
                      <span className="font-medium ml-1 text-blue-600">Yes</span>
                    </div>
                  )}
                  {snapshot.metadata.total_routes !== undefined && snapshot.metadata.total_routes > 0 && (
                    <div>
                      <span className="text-gray-600">Routes:</span>
                      <span className="font-medium ml-1">{snapshot.metadata.total_routes}</span>
                    </div>
                  )}
                  {snapshot.metadata.controller_type && snapshot.metadata.controller_type !== 'unknown' && (
                    <div className="col-span-2">
                      <span className="text-gray-600">Controller Type:</span>
                      <span className="font-medium ml-1">{snapshot.metadata.controller_type}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Expandable Details Section */}
            {expandedSnapshot === snapshot.id && (
              <div className="border-t border-gray-200 bg-gray-50 p-4">
                <h4 className="font-medium text-gray-900 mb-3">Snapshot Details</h4>
                
                {/* Configuration Summary */}
                {snapshot.metadata && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                    <div>
                      <h5 className="font-medium text-gray-700 mb-2">Network Components</h5>
                      <ul className="space-y-1 text-gray-600">
                        <li>• Total Nodes: {snapshot.metadata.node_count || 0}</li>
                        <li>• Hosts: {snapshot.metadata.host_count || 0}</li>
                        <li>• Switches: {snapshot.metadata.switch_count || 0}</li>
                        <li>• Routers: {snapshot.metadata.router_count || 0}</li>
                        <li>• Controllers: {snapshot.metadata.controller_count || 0}</li>
                        <li>• Links: {snapshot.metadata.link_count || 0}</li>
                      </ul>
                    </div>
                    
                    <div>
                      <h5 className="font-medium text-gray-700 mb-2">Configuration Status</h5>
                      <ul className="space-y-1 text-gray-600">
                        <li>• Network: <span className={snapshot.metadata.mininet_running ? 'text-green-600' : 'text-red-600'}>
                          {snapshot.metadata.mininet_running ? 'Running' : 'Stopped'}
                        </span></li>
                        <li>• Controller: <span className={snapshot.metadata.controller_running ? 'text-green-600' : 'text-red-600'}>
                          {snapshot.metadata.controller_running ? 'Running' : 'Stopped'}
                        </span></li>
                        {snapshot.metadata.controller_type && (
                          <li>• Controller Type: {snapshot.metadata.controller_type}</li>
                        )}
                        <li>• Live Configurations: <span className={snapshot.metadata.has_live_configs ? 'text-blue-600' : 'text-gray-500'}>
                          {snapshot.metadata.has_live_configs ? 'Captured' : 'None'}
                        </span></li>
                        {snapshot.metadata.total_routes > 0 && (
                          <li>• Total Routes: {snapshot.metadata.total_routes}</li>
                        )}
                        {snapshot.metadata.configured_hosts > 0 && (
                          <li>• Configured Hosts: {snapshot.metadata.configured_hosts}</li>
                        )}
                        {snapshot.metadata.configured_routers > 0 && (
                          <li>• Configured Routers: {snapshot.metadata.configured_routers}</li>
                        )}
                        {snapshot.metadata.tracked_devices > 0 && (
                          <li>• Tracked Devices: {snapshot.metadata.tracked_devices}</li>
                        )}
                        {snapshot.metadata.api_operations > 0 && (
                          <li>• API Operations: {snapshot.metadata.api_operations}</li>
                        )}
                        {snapshot.metadata.terminal_commands > 0 && (
                          <li>• Terminal Commands: {snapshot.metadata.terminal_commands}</li>
                        )}
                      </ul>
                    </div>
                  </div>
                )}
                
                {/* Snapshot Info */}
                <div className="mt-4 pt-3 border-t border-gray-300">
                  <h5 className="font-medium text-gray-700 mb-2">Snapshot Info</h5>
                  <div className="text-sm text-gray-600 space-y-1">
                    <div>• Size: {snapshot.metadata?.snapshot_size ? `${Math.round(snapshot.metadata.snapshot_size / 1024)} KB` : 'Unknown'}</div>
                    <div>• Created: {formatDate(snapshot.created_at)}</div>
                    {snapshot.updated_at !== snapshot.created_at && (
                      <div>• Last Updated: {formatDate(snapshot.updated_at)}</div>
                    )}
                    <div>• Type: {snapshot.snapshot_type}</div>
                    <div>• Created By: {snapshot.metadata?.created_by || 'Unknown'}</div>
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="p-4">
              <div className="flex justify-between items-center mb-3">
                <button
                  onClick={() => setExpandedSnapshot(
                    expandedSnapshot === snapshot.id ? null : snapshot.id
                  )}
                  className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                >
                  {expandedSnapshot === snapshot.id ? 'Hide Details' : 'View Details'}
                </button>
              </div>
              
              {compareMode ? (
                <button
                  onClick={() => toggleSnapshotSelection(snapshot.id)}
                  className={`w-full px-3 py-2 rounded-lg font-medium transition-colors ${
                    selectedSnapshots.includes(snapshot.id)
                      ? 'bg-purple-600 text-white hover:bg-purple-700'
                      : 'bg-purple-100 text-purple-700 hover:bg-purple-200'
                  }`}
                >
                  {selectedSnapshots.includes(snapshot.id) ? 'Selected' : 'Select for Compare'}
                </button>
              ) : (
                <div className="flex gap-2">
                  <button
                    onClick={() => restoreSnapshot(snapshot.id, snapshot.name)}
                    className="flex-1 px-3 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
                    disabled={loading}
                  >
                    Restore
                  </button>
                  
                  <button
                    onClick={() => exportSnapshot(snapshot.id, snapshot.name)}
                    className="px-3 py-2 bg-gray-600 text-white rounded-lg font-medium hover:bg-gray-700 transition-colors"
                    disabled={loading}
                  >
                    Export
                  </button>
                  
                  <button
                    onClick={() => deleteSnapshot(snapshot.id, snapshot.name)}
                    className="px-3 py-2 bg-red-600 text-white rounded-lg font-medium hover:bg-red-700 transition-colors"
                    disabled={loading}
                  >
                    Delete
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        </div>

        {/* Empty State */}
        {snapshots.length === 0 && !loading && (
          <div className="text-center py-12">
            <div className="text-gray-400 text-6xl mb-4">📸</div>
            <h3 className="text-xl font-semibold text-gray-900 mb-2">No snapshots yet</h3>
            <p className="text-gray-600 mb-4">Create your first simulation snapshot to get started</p>
            <button
              onClick={() => setCreateDialogOpen(true)}
              className="px-6 py-3 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
            >
              Create Snapshot
            </button>
          </div>
        )}
        </div>
      </div>

      {/* Create Snapshot Dialog */}
      {createDialogOpen && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md mx-4">
            <h2 className="text-xl font-semibold mb-4">Create Simulation Snapshot</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Snapshot Name *
                </label>
                <input
                  type="text"
                  value={snapshotName}
                  onChange={(e) => setSnapshotName(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  placeholder="Enter snapshot name"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Description
                </label>
                <textarea
                  value={snapshotDescription}
                  onChange={(e) => setSnapshotDescription(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                  rows="3"
                  placeholder="Describe this snapshot..."
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Snapshot Type
                </label>
                <select
                  value={snapshotType}
                  onChange={(e) => setSnapshotType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                >
                  <option value="full">Full Snapshot</option>
                  <option value="topology_only">Topology Only</option>
                  <option value="runtime_state">Runtime State</option>
                </select>
              </div>
              
              <div className="bg-blue-50 p-3 rounded-lg">
                <p className="text-sm text-blue-700">
                  This will capture the complete state of your current simulation, including network topology, 
                  controller state, and runtime statistics.
                </p>
              </div>
            </div>
            
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => {
                  setCreateDialogOpen(false);
                  setSnapshotName('');
                  setSnapshotDescription('');
                  setSnapshotType('full');
                }}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={createSnapshot}
                className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
                disabled={loading || !snapshotName.trim()}
              >
                {loading ? 'Creating...' : 'Create Snapshot'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Comparison Result Dialog */}
      {comparisonResult && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-2xl mx-4 max-h-96 overflow-y-auto">
            <h2 className="text-xl font-semibold mb-4">Snapshot Comparison</h2>
            
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 p-3 rounded-lg">
                  <h3 className="font-medium text-gray-900">{comparisonResult.snapshot1.name}</h3>
                  <p className="text-sm text-gray-600">Created: {formatDate(comparisonResult.snapshot1.created_at)}</p>
                </div>
                <div className="bg-gray-50 p-3 rounded-lg">
                  <h3 className="font-medium text-gray-900">{comparisonResult.snapshot2.name}</h3>
                  <p className="text-sm text-gray-600">Created: {formatDate(comparisonResult.snapshot2.created_at)}</p>
                </div>
              </div>
              
              <div className="border-t pt-4">
                <h4 className="font-medium text-gray-900 mb-2">Differences</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Nodes:</span>
                    <span>
                      {comparisonResult.differences.nodes.snapshot1_count} → {comparisonResult.differences.nodes.snapshot2_count}
                      {comparisonResult.differences.nodes.difference !== 0 && (
                        <span className={comparisonResult.differences.nodes.difference > 0 ? 'text-green-600' : 'text-red-600'}>
                          {' '}({comparisonResult.differences.nodes.difference > 0 ? '+' : ''}{comparisonResult.differences.nodes.difference})
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Links:</span>
                    <span>
                      {comparisonResult.differences.links.snapshot1_count} → {comparisonResult.differences.links.snapshot2_count}
                      {comparisonResult.differences.links.difference !== 0 && (
                        <span className={comparisonResult.differences.links.difference > 0 ? 'text-green-600' : 'text-red-600'}>
                          {' '}({comparisonResult.differences.links.difference > 0 ? '+' : ''}{comparisonResult.differences.links.difference})
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Controller State:</span>
                    <span className={comparisonResult.differences.controller.same_state ? 'text-green-600' : 'text-yellow-600'}>
                      {comparisonResult.differences.controller.same_state ? 'Same' : 'Different'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="flex justify-end mt-6">
              <button
                onClick={() => setComparisonResult(null)}
                className="px-4 py-2 bg-gray-600 text-white rounded-lg font-medium hover:bg-gray-700 transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SimulationSnapshots;
