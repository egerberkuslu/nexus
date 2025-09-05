import { useCallback } from 'react';

// Helper function to enhance topology with controller and switch type information
const enhanceTopologyWithTypeInfo = (topology) => {
  const enhanced = { ...topology };
  
  // Ensure nodes array exists
  if (!enhanced.nodes) {
    enhanced.nodes = [];
  }
  
  // Enhance each node with type-specific attributes
  enhanced.nodes = enhanced.nodes.map(node => {
    const enhancedNode = { ...node };
    
    if (node.type === 'controller') {
      // Add default controller type attributes if missing
      if (!enhancedNode.controller_type) {
        enhancedNode.controller_type = 'ryu';
      }
      if (!enhancedNode.app) {
        enhancedNode.app = 'simple_switch_13';
      }
      if (!enhancedNode.protocol) {
        enhancedNode.protocol = 'OpenFlow';
      }
      if (!enhancedNode.version) {
        enhancedNode.version = '1.3';
      }
      if (!enhancedNode.port) {
        enhancedNode.port = 6633;
      }
    } else if (node.type === 'switch') {
      // Add default switch type attributes if missing
      if (!enhancedNode.switch_type) {
        enhancedNode.switch_type = 'ovs';
      }
      if (!enhancedNode.dpid) {
        enhancedNode.dpid = 'auto';
      }
      if (!enhancedNode.openflow_version) {
        enhancedNode.openflow_version = '1.3';
      }
    }
    
    return enhancedNode;
  });
  
  // Ensure controllers array exists and is populated
  if (!enhanced.controllers) {
    enhanced.controllers = [];
  }
  
  // Add controllers from nodes if not already in controllers list
  const controllerIds = new Set(enhanced.controllers.map(c => c.id));
  enhanced.nodes.forEach(node => {
    if (node.type === 'controller' && !controllerIds.has(node.id)) {
      enhanced.controllers.push(node);
    }
  });
  
  // Add metadata about supported types
  if (!enhanced.metadata) {
    enhanced.metadata = {};
  }
  
  enhanced.metadata.supported_controller_types = ['ryu', 'pox', 'osken', 'opendaylight'];
  enhanced.metadata.supported_switch_types = ['ovs', 'linux_bridge', 'p4'];
  enhanced.metadata.enhanced_with_type_info = true;
  
  return enhanced;
};

export const useStorageData = ({
  apiCall,
  addLog,
  setTopologies,
  setConfigurations,
  setLoading
}) => {
  // Fetch saved topologies
  const fetchTopologies = useCallback(async () => {
    try {
      const result = await apiCall('/storage/topologies');
      if (result.success) {
        if (setTopologies) setTopologies(result.data.topologies || []);
        return result.data.topologies || [];
      }
    } catch (error) {
      addLog(`❌ Failed to fetch topologies: ${error.message}`, 'error', 'storage');
    }
    return [];
  }, [apiCall, addLog, setTopologies]);

  // Save topology with enhanced controller/switch type information
  const saveTopology = useCallback(async (topologyData, name, description = '') => {
    setLoading(true);
    try {
      // Enhance topology data with controller and switch type information
      const enhancedTopologyData = enhanceTopologyWithTypeInfo(topologyData);
      
      const result = await apiCall('/storage/topologies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          description,
          topology_data: enhancedTopologyData
        })
      });

      if (result.success && result.data.success) {
        addLog(`💾 Topology "${name}" saved successfully`, 'success', 'storage');
        await fetchTopologies(); // Refresh topologies list
        return result.data.topology_id;
      } else {
        addLog(`❌ Failed to save topology: ${result.data?.error || result.error}`, 'error', 'storage');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error saving topology: ${error.message}`, 'error', 'storage');
      return null;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading, fetchTopologies]);

  // Load topology
  const loadTopology = useCallback(async (topologyId) => {
    try {
      const result = await apiCall(`/storage/topologies/${topologyId}`);
      if (result.success) {
        addLog(`📂 Topology "${result.data.topology.name}" loaded successfully`, 'success', 'storage');
        return result.data.topology;
      } else {
        addLog(`❌ Failed to load topology: ${result.data?.error || result.error}`, 'error', 'storage');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error loading topology: ${error.message}`, 'error', 'storage');
      return null;
    }
  }, [apiCall, addLog]);

  // Delete topology
  const deleteTopology = useCallback(async (topologyId) => {
    try {
      const result = await apiCall(`/storage/topologies/${topologyId}`, {
        method: 'DELETE'
      });

      if (result.success && result.data.success) {
        addLog(`🗑️ Topology deleted successfully`, 'success', 'storage');
        await fetchTopologies(); // Refresh topologies list
        return true;
      } else {
        addLog(`❌ Failed to delete topology: ${result.data?.error || result.error}`, 'error', 'storage');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error deleting topology: ${error.message}`, 'error', 'storage');
      return false;
    }
  }, [apiCall, addLog, fetchTopologies]);

  // Fetch device configurations
  const fetchConfigurations = useCallback(async (deviceType = null) => {
    try {
      const endpoint = deviceType
        ? `/storage/configurations?device_type=${deviceType}`
        : '/storage/configurations';
      const result = await apiCall(endpoint);
      if (result.success) {
        if (setConfigurations) setConfigurations(result.data.configurations || []);
        return result.data.configurations || [];
      }
    } catch (error) {
      addLog(`❌ Failed to fetch configurations: ${error.message}`, 'error', 'storage');
    }
    return [];
  }, [apiCall, addLog, setConfigurations]);

  // Save device configuration
  const saveConfiguration = useCallback(async (deviceType, deviceId, configData, name, description = '') => {
    setLoading(true);
    try {
      const result = await apiCall('/storage/configurations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_type: deviceType,
          device_id: deviceId,
          name,
          description,
          configuration_data: configData
        })
      });

      if (result.success && result.data.success) {
        addLog(`💾 Configuration "${name}" saved successfully`, 'success', 'storage');
        await fetchConfigurations(deviceType); // Refresh configurations list
        return result.data.configuration_id;
      } else {
        addLog(`❌ Failed to save configuration: ${result.data?.error || result.error}`, 'error', 'storage');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error saving configuration: ${error.message}`, 'error', 'storage');
      return null;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading, fetchConfigurations]);

  // Load device configuration
  const loadConfiguration = useCallback(async (configurationId) => {
    try {
      const result = await apiCall(`/storage/configurations/${configurationId}`);
      if (result.success) {
        addLog(`📂 Configuration "${result.data.configuration.name}" loaded successfully`, 'success', 'storage');
        return result.data.configuration;
      } else {
        addLog(`❌ Failed to load configuration: ${result.data?.error || result.error}`, 'error', 'storage');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error loading configuration: ${error.message}`, 'error', 'storage');
      return null;
    }
  }, [apiCall, addLog]);

  // Delete configuration
  const deleteConfiguration = useCallback(async (configurationId) => {
    try {
      const result = await apiCall(`/storage/configurations/${configurationId}`, {
        method: 'DELETE'
      });

      if (result.success && result.data.success) {
        addLog(`🗑️ Configuration deleted successfully`, 'success', 'storage');
        await fetchConfigurations(); // Refresh configurations list
        return true;
      } else {
        addLog(`❌ Failed to delete configuration: ${result.data?.error || result.error}`, 'error', 'storage');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error deleting configuration: ${error.message}`, 'error', 'storage');
      return false;
    }
  }, [apiCall, addLog, fetchConfigurations]);

  // Export topology/configuration
  const exportData = useCallback(async (type, id, format = 'json') => {
    try {
      const result = await apiCall(`/storage/export/${type}/${id}?format=${format}`);
      if (result.success) {
        // Create download link
        const blob = new Blob([JSON.stringify(result.data, null, 2)], {
          type: 'application/json'
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${type}-${id}.${format}`;
        a.click();
        URL.revokeObjectURL(url);

        addLog(`📤 ${type} exported successfully`, 'success', 'storage');
        return true;
      } else {
        addLog(`❌ Failed to export ${type}: ${result.data?.error || result.error}`, 'error', 'storage');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error exporting ${type}: ${error.message}`, 'error', 'storage');
      return false;
    }
  }, [apiCall, addLog]);

  // Import topology/configuration
  const importData = useCallback(async (type, file) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('type', type);

      const result = await apiCall('/storage/import', {
        method: 'POST',
        body: formData
      });

      if (result.success && result.data.success) {
        addLog(`📥 ${type} imported successfully`, 'success', 'storage');
        if (type === 'topology') {
          await fetchTopologies();
        } else if (type === 'configuration') {
          await fetchConfigurations();
        }
        return result.data.id;
      } else {
        addLog(`❌ Failed to import ${type}: ${result.data?.error || result.error}`, 'error', 'storage');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error importing ${type}: ${error.message}`, 'error', 'storage');
      return null;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading, fetchTopologies, fetchConfigurations]);

  // Search topologies/configurations
  const searchData = useCallback(async (type, query, filters = {}) => {
    try {
      const params = new URLSearchParams({ q: query, ...filters });
      const result = await apiCall(`/storage/search/${type}?${params}`);
      if (result.success) {
        return result.data.results || [];
      }
    } catch (error) {
      addLog(`❌ Failed to search ${type}: ${error.message}`, 'error', 'storage');
    }
    return [];
  }, [apiCall, addLog]);

  return {
    fetchTopologies,
    saveTopology,
    loadTopology,
    deleteTopology,
    fetchConfigurations,
    saveConfiguration,
    loadConfiguration,
    deleteConfiguration,
    exportData,
    importData,
    searchData
  };
};
