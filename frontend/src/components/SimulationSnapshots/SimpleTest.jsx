import React, { useState, useEffect } from 'react';

const SimpleSnapshotTest = () => {
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Test API connection
  useEffect(() => {
    const testConnection = async () => {
      setLoading(true);
      try {
        const response = await fetch('http://localhost:5000/api/snapshots/');
        const result = await response.json();
        
        if (result.success) {
          setSnapshots(result.snapshots);
          console.log('Snapshots loaded:', result.snapshots);
        } else {
          throw new Error(result.error || 'Failed to load snapshots');
        }
      } catch (err) {
        console.error('Error loading snapshots:', err);
        setError('Failed to load snapshots: ' + err.message);
      } finally {
        setLoading(false);
      }
    };

    testConnection();
  }, []);

  return (
    <div className="p-4 bg-white min-h-screen">
      <h1 className="text-2xl font-bold mb-4">Simulation Snapshots - Test</h1>
      
      {loading && (
        <div className="p-4 bg-blue-100 text-blue-800 rounded mb-4">
          Loading snapshots...
        </div>
      )}
      
      {error && (
        <div className="p-4 bg-red-100 text-red-800 rounded mb-4">
          Error: {error}
        </div>
      )}
      
      <div className="mb-4">
        <button
          onClick={async () => {
            setLoading(true);
            try {
              const response = await fetch('http://localhost:5000/api/snapshots/create', {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                  name: `Test Snapshot ${Date.now()}`,
                  description: 'Test snapshot created from UI',
                  snapshot_type: 'full'
                }),
              });

              const result = await response.json();
              
              if (result.success) {
                alert('Snapshot created successfully!');
                // Reload snapshots
                window.location.reload();
              } else {
                alert('Error: ' + (result.error || 'Failed to create snapshot'));
              }
            } catch (err) {
              alert('Error creating snapshot: ' + err.message);
            } finally {
              setLoading(false);
            }
          }}
          className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:bg-gray-400"
          disabled={loading}
        >
          Create Test Snapshot
        </button>
      </div>
      
      <div className="space-y-4">
        <h2 className="text-lg font-semibold">Snapshots ({snapshots.length})</h2>
        
        {snapshots.length === 0 ? (
          <div className="p-8 text-center text-gray-500 bg-gray-50 rounded">
            No snapshots found. Create one to get started!
          </div>
        ) : (
          <div className="grid gap-4">
            {snapshots.map((snapshot) => (
              <div key={snapshot.id} className="p-4 border rounded-lg bg-gray-50">
                <h3 className="font-medium">{snapshot.name}</h3>
                <p className="text-sm text-gray-600">{snapshot.description}</p>
                <div className="text-xs text-gray-500 mt-2">
                  <div>Type: {snapshot.snapshot_type}</div>
                  <div>Created: {new Date(snapshot.created_at).toLocaleString()}</div>
                  {snapshot.metadata && (
                    <div>
                      Nodes: {snapshot.metadata.node_count || 0}, 
                      Links: {snapshot.metadata.link_count || 0}
                    </div>
                  )}
                </div>
                
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={async () => {
                      if (window.confirm(`Restore snapshot "${snapshot.name}"?`)) {
                        setLoading(true);
                        try {
                          const response = await fetch(`http://localhost:5000/api/snapshots/${snapshot.id}/restore`, {
                            method: 'POST',
                          });
                          const result = await response.json();
                          
                          if (result.success) {
                            alert('Snapshot restored successfully!');
                          } else {
                            alert('Error: ' + (result.error || 'Failed to restore snapshot'));
                          }
                        } catch (err) {
                          alert('Error restoring snapshot: ' + err.message);
                        } finally {
                          setLoading(false);
                        }
                      }
                    }}
                    className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 disabled:bg-gray-400"
                    disabled={loading}
                  >
                    Restore
                  </button>
                  
                  <button
                    onClick={async () => {
                      if (window.confirm(`Delete snapshot "${snapshot.name}"?`)) {
                        setLoading(true);
                        try {
                          const response = await fetch(`http://localhost:5000/api/snapshots/${snapshot.id}`, {
                            method: 'DELETE',
                          });
                          const result = await response.json();
                          
                          if (result.success) {
                            alert('Snapshot deleted successfully!');
                            window.location.reload();
                          } else {
                            alert('Error: ' + (result.error || 'Failed to delete snapshot'));
                          }
                        } catch (err) {
                          alert('Error deleting snapshot: ' + err.message);
                        } finally {
                          setLoading(false);
                        }
                      }
                    }}
                    className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700 disabled:bg-gray-400"
                    disabled={loading}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default SimpleSnapshotTest;
