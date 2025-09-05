import React, { useState, useEffect, useCallback } from 'react';
import { 
  Save, 
  FolderOpen, 
  Trash2, 
  Download, 
  Upload, 
  Database,
  Network,
  Router,
  Server,
  Monitor,
  Clock,
  FileText,
  Settings,
  AlertCircle,
  CheckCircle,
  X,
  RefreshCw
} from 'lucide-react';

const StorageManager = ({ 
  onClose, 
  currentTopology, 
  currentConfigurations,
  onLoadTopology,
  onLoadConfiguration 
}) => {
  const [activeTab, setActiveTab] = useState('topologies');
  const [topologies, setTopologies] = useState([]);
  const [configurations, setConfigurations] = useState([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveForm, setSaveForm] = useState({
    name: '',
    description: '',
    type: 'topology' // or 'configuration'
  });

  // Fetch saved data
  const fetchTopologies = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:5000'}/api/storage/topologies`);
      const data = await response.json();
      
      if (data.success) {
        setTopologies(data.topologies);
      } else {
        setMessage({ text: 'Failed to fetch topologies', type: 'error' });
      }
    } catch (error) {
      setMessage({ text: `Error fetching topologies: ${error.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchConfigurations = useCallback(async (deviceType = null) => {
    try {
      setLoading(true);
      const url = deviceType 
        ? `/api/storage/configurations?device_type=${deviceType}`
        : '/api/storage/configurations';
      
      const response = await fetch(url);
      const data = await response.json();
      
      if (data.success) {
        setConfigurations(data.configurations);
      } else {
        setMessage({ text: 'Failed to fetch configurations', type: 'error' });
      }
    } catch (error) {
      setMessage({ text: `Error fetching configurations: ${error.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  // Save current topology
  const saveCurrentTopology = async (formData) => {
    try {
      setLoading(true);
      const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:5000'}/api/storage/topologies`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name,
          description: formData.description,
          topology_type: 'custom',
          metadata: {
            saved_from_ui: true,
            node_count: currentTopology?.nodes?.length || 0,
            link_count: currentTopology?.links?.length || 0
          }
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setMessage({ text: `Topology "${formData.name}" saved successfully!`, type: 'success' });
        fetchTopologies();
        setShowSaveModal(false);
        setSaveForm({ name: '', description: '', type: 'topology' });
      } else {
        setMessage({ text: data.error || 'Failed to save topology', type: 'error' });
      }
    } catch (error) {
      setMessage({ text: `Error saving topology: ${error.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // Save configuration
  const saveConfiguration = async (formData, deviceType, configData) => {
    try {
      setLoading(true);
      const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:5000'}/api/storage/configurations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: formData.name,
          description: formData.description,
          device_type: deviceType,
          configuration_data: configData,
          metadata: {
            saved_from_ui: true,
            device_type: deviceType
          }
        })
      });
      
      const data = await response.json();
      
      if (data.success) {
        setMessage({ text: `Configuration "${formData.name}" saved successfully!`, type: 'success' });
        fetchConfigurations();
        setShowSaveModal(false);
        setSaveForm({ name: '', description: '', type: 'configuration' });
      } else {
        setMessage({ text: data.error || 'Failed to save configuration', type: 'error' });
      }
    } catch (error) {
      setMessage({ text: `Error saving configuration: ${error.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // Load topology
  const loadTopology = async (topologyId) => {
    try {
      setLoading(true);
      const response = await fetch(`/api/storage/topologies/${topologyId}/load`, {
        method: 'POST'
      });
      
      const data = await response.json();
      
      if (data.success) {
        setMessage({ text: `Topology "${data.topology.name}" loaded successfully!`, type: 'success' });
        if (onLoadTopology) onLoadTopology(data.topology);
      } else {
        setMessage({ text: data.error || 'Failed to load topology', type: 'error' });
      }
    } catch (error) {
      setMessage({ text: `Error loading topology: ${error.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // Delete item
  const deleteItem = async (id, type) => {
    if (!window.confirm(`Are you sure you want to delete this ${type}?`)) return;
    
    try {
      setLoading(true);
      const endpoint = type === 'topology' ? 'topologies' : 'configurations';
      const response = await fetch(`/api/storage/${endpoint}/${id}`, {
        method: 'DELETE'
      });
      
      const data = await response.json();
      
      if (data.success) {
        setMessage({ text: `${type} deleted successfully!`, type: 'success' });
        if (type === 'topology') {
          fetchTopologies();
        } else {
          fetchConfigurations();
        }
      } else {
        setMessage({ text: data.error || `Failed to delete ${type}`, type: 'error' });
      }
    } catch (error) {
      setMessage({ text: `Error deleting ${type}: ${error.message}`, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  // Export item
  const exportItem = async (id, type, format = 'json') => {
    try {
      const endpoint = type === 'topology' ? 'topologies' : 'configurations';
      const response = await fetch(`/api/storage/export/${endpoint.slice(0, -1)}/${id}?format=${format}`);
      
      if (response.ok) {
        const data = await response.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${data.name || 'export'}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        
        setMessage({ text: `${type} exported successfully!`, type: 'success' });
      } else {
        setMessage({ text: `Failed to export ${type}`, type: 'error' });
      }
    } catch (error) {
      setMessage({ text: `Error exporting ${type}: ${error.message}`, type: 'error' });
    }
  };

  useEffect(() => {
    fetchTopologies();
    fetchConfigurations();
  }, [fetchTopologies, fetchConfigurations]);

  useEffect(() => {
    if (message) {
      const timer = setTimeout(() => setMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [message]);

  const getDeviceIcon = (deviceType) => {
    switch (deviceType) {
      case 'host': return <Monitor className="w-4 h-4" />;
      case 'switch': return <Network className="w-4 h-4" />;
      case 'router': return <Router className="w-4 h-4" />;
      case 'controller': return <Server className="w-4 h-4" />;
      default: return <Settings className="w-4 h-4" />;
    }
  };

  const handleSave = () => {
    if (!saveForm.name.trim()) {
      setMessage({ text: 'Name is required', type: 'error' });
      return;
    }

    if (saveForm.type === 'topology') {
      if (!currentTopology || !currentTopology.nodes || currentTopology.nodes.length === 0) {
        setMessage({ text: 'No topology to save. Create a network first.', type: 'error' });
        return;
      }
      saveCurrentTopology(saveForm);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-6xl h-5/6 flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b">
          <div className="flex items-center space-x-3">
            <Database className="w-6 h-6 text-blue-600" />
            <h2 className="text-2xl font-bold text-gray-800">Storage Manager</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Message */}
        {message && (
          <div className={`mx-6 mt-4 p-4 rounded-lg flex items-center space-x-2 ${
            message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' :
            message.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200' :
            'bg-blue-50 text-blue-700 border border-blue-200'
          }`}>
            {message.type === 'success' ? <CheckCircle className="w-5 h-5" /> :
             message.type === 'error' ? <AlertCircle className="w-5 h-5" /> :
             <AlertCircle className="w-5 h-5" />}
            <span>{message.text}</span>
          </div>
        )}

        {/* Tabs */}
        <div className="flex space-x-1 p-6 pb-0">
          <button
            onClick={() => setActiveTab('topologies')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === 'topologies'
                ? 'bg-blue-100 text-blue-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <Network className="w-4 h-4 inline mr-2" />
            Topologies ({topologies.length})
          </button>
          <button
            onClick={() => setActiveTab('configurations')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === 'configurations'
                ? 'bg-blue-100 text-blue-700'
                : 'text-gray-600 hover:bg-gray-100'
            }`}
          >
            <Settings className="w-4 h-4 inline mr-2" />
            Configurations ({configurations.length})
          </button>
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div className="flex space-x-2">
            <button
              onClick={() => {
                setSaveForm({ name: '', description: '', type: activeTab === 'topologies' ? 'topology' : 'configuration' });
                setShowSaveModal(true);
              }}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              disabled={loading}
            >
              <Save className="w-4 h-4" />
              <span>Save Current</span>
            </button>
            <button
              onClick={() => activeTab === 'topologies' ? fetchTopologies() : fetchConfigurations()}
              className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              disabled={loading}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-hidden p-6">
          {activeTab === 'topologies' && (
            <div className="h-full overflow-y-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {topologies.map((topology) => (
                  <div key={topology.id} className="bg-gray-50 rounded-lg p-4 border">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center space-x-2">
                        <Network className="w-5 h-5 text-blue-600" />
                        <h3 className="font-semibold text-gray-800">{topology.name}</h3>
                      </div>
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        topology.topology_type === 'custom' ? 'bg-purple-100 text-purple-700' :
                        topology.topology_type === 'predefined' ? 'bg-green-100 text-green-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {topology.topology_type}
                      </span>
                    </div>
                    
                    <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                      {topology.description || 'No description'}
                    </p>
                    
                    <div className="flex items-center space-x-4 text-xs text-gray-500 mb-3">
                      <span>Nodes: {topology.metadata?.node_count || 0}</span>
                      <span>Links: {topology.metadata?.link_count || 0}</span>
                      <span className="flex items-center space-x-1">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(topology.updated_at).toLocaleDateString()}</span>
                      </span>
                    </div>
                    
                    <div className="flex space-x-2">
                      <button
                        onClick={() => loadTopology(topology.id)}
                        className="flex-1 flex items-center justify-center space-x-1 px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                        disabled={loading}
                      >
                        <FolderOpen className="w-4 h-4" />
                        <span>Load</span>
                      </button>
                      <button
                        onClick={() => exportItem(topology.id, 'topology')}
                        className="px-3 py-2 border border-gray-300 text-gray-700 text-sm rounded hover:bg-gray-50 transition-colors"
                        disabled={loading}
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteItem(topology.id, 'topology')}
                        className="px-3 py-2 border border-red-300 text-red-600 text-sm rounded hover:bg-red-50 transition-colors"
                        disabled={loading}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              
              {topologies.length === 0 && !loading && (
                <div className="text-center py-12">
                  <Network className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-600 mb-2">No saved topologies</h3>
                  <p className="text-gray-500">Create a network and save it to get started.</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'configurations' && (
            <div className="h-full overflow-y-auto">
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {configurations.map((config) => (
                  <div key={config.id} className="bg-gray-50 rounded-lg p-4 border">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center space-x-2">
                        {getDeviceIcon(config.device_type)}
                        <h3 className="font-semibold text-gray-800">{config.name}</h3>
                      </div>
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        config.device_type === 'host' ? 'bg-blue-100 text-blue-700' :
                        config.device_type === 'switch' ? 'bg-green-100 text-green-700' :
                        config.device_type === 'router' ? 'bg-orange-100 text-orange-700' :
                        config.device_type === 'controller' ? 'bg-purple-100 text-purple-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {config.device_type}
                      </span>
                    </div>
                    
                    <p className="text-sm text-gray-600 mb-3 line-clamp-2">
                      {config.description || 'No description'}
                    </p>
                    
                    <div className="flex items-center space-x-4 text-xs text-gray-500 mb-3">
                      <span className="flex items-center space-x-1">
                        <Clock className="w-3 h-3" />
                        <span>{new Date(config.updated_at).toLocaleDateString()}</span>
                      </span>
                    </div>
                    
                    <div className="flex space-x-2">
                      <button
                        onClick={() => onLoadConfiguration && onLoadConfiguration(config)}
                        className="flex-1 flex items-center justify-center space-x-1 px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                        disabled={loading}
                      >
                        <FolderOpen className="w-4 h-4" />
                        <span>Load</span>
                      </button>
                      <button
                        onClick={() => exportItem(config.id, 'configuration')}
                        className="px-3 py-2 border border-gray-300 text-gray-700 text-sm rounded hover:bg-gray-50 transition-colors"
                        disabled={loading}
                      >
                        <Download className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteItem(config.id, 'configuration')}
                        className="px-3 py-2 border border-red-300 text-red-600 text-sm rounded hover:bg-red-50 transition-colors"
                        disabled={loading}
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
              
              {configurations.length === 0 && !loading && (
                <div className="text-center py-12">
                  <Settings className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-600 mb-2">No saved configurations</h3>
                  <p className="text-gray-500">Save device configurations to reuse them later.</p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Save Modal */}
      {showSaveModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-60">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
            <h3 className="text-lg font-semibold mb-4">
              Save {saveForm.type === 'topology' ? 'Topology' : 'Configuration'}
            </h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name *</label>
                <input
                  type="text"
                  value={saveForm.name}
                  onChange={(e) => setSaveForm(prev => ({ ...prev, name: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Enter a name..."
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  value={saveForm.description}
                  onChange={(e) => setSaveForm(prev => ({ ...prev, description: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  rows={3}
                  placeholder="Enter a description..."
                />
              </div>
            </div>
            
            <div className="flex space-x-3 mt-6">
              <button
                onClick={handleSave}
                className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
                disabled={loading}
              >
                Save
              </button>
              <button
                onClick={() => setShowSaveModal(false)}
                className="flex-1 border border-gray-300 text-gray-700 py-2 px-4 rounded-lg hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default StorageManager;
