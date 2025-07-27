import { useState, useCallback } from 'react';

export const useTopologyData = ({ apiCall, addLog, setLoading }) => {
  const [savedTopologies, setSavedTopologies] = useState([]);

  // Load saved topologies from localStorage on initialization
  const loadSavedTopologies = useCallback(() => {
    try {
      const saved = localStorage.getItem('mininet_saved_topologies');
      if (saved) {
        setSavedTopologies(JSON.parse(saved));
      }
    } catch (error) {
      addLog('❌ Error loading saved topologies', 'error', 'topology');
    }
  }, [addLog]);

  // Save topology to localStorage
  const saveTopology = useCallback((topology) => {
    try {
      const newTopology = {
        ...topology,
        id: Date.now().toString(),
        created: new Date().toISOString(),
        version: '1.0'
      };

      const updatedTopologies = [...savedTopologies, newTopology];
      setSavedTopologies(updatedTopologies);
      localStorage.setItem('mininet_saved_topologies', JSON.stringify(updatedTopologies));
      
      addLog(`💾 Topology "${topology.name}" saved successfully`, 'success', 'topology');
      return newTopology;
    } catch (error) {
      addLog('❌ Error saving topology', 'error', 'topology');
      return null;
    }
  }, [savedTopologies, addLog]);

  // Delete saved topology
  const deleteTopology = useCallback((topologyId) => {
    try {
      const updatedTopologies = savedTopologies.filter(t => t.id !== topologyId);
      setSavedTopologies(updatedTopologies);
      localStorage.setItem('mininet_saved_topologies', JSON.stringify(updatedTopologies));
      
      addLog('🗑️ Topology deleted', 'info', 'topology');
    } catch (error) {
      addLog('❌ Error deleting topology', 'error', 'topology');
    }
  }, [savedTopologies, addLog]);

  // Create custom topology using backend API
  const createCustomTopology = useCallback(async (topology) => {
    setLoading(true);
    try {
      const result = await apiCall('/network/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'custom',
          topology: topology
        })
      });

      if (result.success && result.data.success) {
        addLog(`🔧 Custom topology "${topology.name || 'Custom'}" created successfully`, 'success', 'network');
        return true;
      } else {
        addLog(`❌ Failed to create custom topology: ${result.data?.error || result.error}`, 'error', 'network');
        return false;
      }
    } catch (error) {
      addLog('❌ Error creating custom topology', 'error', 'network');
      return false;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading]);

  // Import topology configuration from backend
  const importTopologyConfig = useCallback(async (configFile) => {
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', configFile);

      const result = await apiCall('/topology/import', {
        method: 'POST',
        body: formData
      });

      if (result.success && result.data.success) {
        addLog(`📥 Topology configuration imported successfully`, 'success', 'topology');
        return result.data.imported_config;
      } else {
        addLog(`❌ Failed to import topology: ${result.data?.error || result.error}`, 'error', 'topology');
        return null;
      }
    } catch (error) {
      addLog('❌ Error importing topology configuration', 'error', 'topology');
      return null;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading]);

  // Export current topology configuration
  const exportTopologyConfig = useCallback(async (format = 'json') => {
    try {
      const result = await apiCall(`/topology/export?format=${format}`);

      if (result.success) {
        // Create and download file
        const blob = new Blob([
          format === 'json' ? JSON.stringify(result.data, null, 2) : result.data
        ], { 
          type: format === 'json' ? 'application/json' : 'text/plain' 
        });
        
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `topology_export.${format}`;
        a.click();
        URL.revokeObjectURL(url);

        addLog(`📤 Topology exported as ${format.toUpperCase()}`, 'success', 'topology');
        return true;
      } else {
        addLog(`❌ Failed to export topology`, 'error', 'topology');
        return false;
      }
    } catch (error) {
      addLog('❌ Error exporting topology configuration', 'error', 'topology');
      return false;
    }
  }, [apiCall, addLog]);

  // Get topology visualization data
  const getVisualizationData = useCallback(async () => {
    try {
      const result = await apiCall('/topology/visualize');

      if (result.success) {
        return result.data;
      } else {
        addLog(`❌ Failed to get visualization data`, 'error', 'topology');
        return null;
      }
    } catch (error) {
      addLog('❌ Error getting topology visualization data', 'error', 'topology');
      return null;
    }
  }, [apiCall, addLog]);

  // Validate topology configuration
  const validateTopology = useCallback((topology) => {
    const errors = [];
    const warnings = [];

    // Check if topology has nodes
    if (!topology.nodes || topology.nodes.length === 0) {
      errors.push('Topology must have at least one node');
    }

    // Check for duplicate node IDs
    const nodeIds = topology.nodes?.map(n => n.id) || [];
    const duplicateIds = nodeIds.filter((id, index) => nodeIds.indexOf(id) !== index);
    if (duplicateIds.length > 0) {
      errors.push(`Duplicate node IDs found: ${duplicateIds.join(', ')}`);
    }

    // Check links reference valid nodes
    if (topology.links) {
      topology.links.forEach((link, index) => {
        if (!nodeIds.includes(link.source)) {
          errors.push(`Link ${index + 1}: Source node '${link.source}' does not exist`);
        }
        if (!nodeIds.includes(link.target)) {
          errors.push(`Link ${index + 1}: Target node '${link.target}' does not exist`);
        }
      });
    }

    // Check for isolated nodes (nodes with no links)
    if (topology.links && topology.nodes) {
      const connectedNodes = new Set();
      topology.links.forEach(link => {
        connectedNodes.add(link.source);
        connectedNodes.add(link.target);
      });

      const isolatedNodes = topology.nodes
        .filter(node => !connectedNodes.has(node.id))
        .map(node => node.id);

      if (isolatedNodes.length > 0) {
        warnings.push(`Isolated nodes found: ${isolatedNodes.join(', ')}`);
      }
    }

    // Check for valid IP addresses for hosts
    if (topology.nodes) {
      topology.nodes
        .filter(node => node.type === 'host' && node.ip && node.ip !== 'auto')
        .forEach(host => {
          const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
          if (!ipRegex.test(host.ip)) {
            warnings.push(`Host '${host.id}' has invalid IP address: ${host.ip}`);
          }
        });
    }

    // Check for controller nodes
    if (topology.nodes) {
      const controllers = topology.nodes.filter(node => node.type === 'controller');
      if (controllers.length > 1) {
        warnings.push('Multiple controllers detected - this may cause conflicts');
      }
      
      controllers.forEach(controller => {
        if (controller.port && (controller.port < 1024 || controller.port > 65535)) {
          warnings.push(`Controller '${controller.id}' has invalid port: ${controller.port}`);
        }
      });
    }

    // Check for minimum network requirements
    if (topology.nodes) {
      const hosts = topology.nodes.filter(node => node.type === 'host');
      const switches = topology.nodes.filter(node => node.type === 'switch');
      
      if (hosts.length === 0) {
        warnings.push('No hosts found in topology');
      }
      
      if (switches.length === 0 && hosts.length > 1) {
        warnings.push('No switches found - hosts may not be able to communicate');
      }
    }

    return {
      isValid: errors.length === 0,
      errors,
      warnings
    };
  }, []);

  // Generate topology statistics
  const getTopologyStatistics = useCallback((topology) => {
    if (!topology.nodes) {
      return {};
    }

    const stats = {
      totalNodes: topology.nodes.length,
      hosts: topology.nodes.filter(n => n.type === 'host').length,
      switches: topology.nodes.filter(n => n.type === 'switch').length,
      routers: topology.nodes.filter(n => n.type === 'router').length,
      controllers: topology.nodes.filter(n => n.type === 'controller').length,
      links: topology.links?.length || 0,
      avgDegree: 0,
      maxDegree: 0,
      minDegree: 0
    };

    // Calculate node degrees (number of connections per node)
    if (topology.links && topology.nodes.length > 0) {
      const degrees = {};
      topology.nodes.forEach(node => {
        degrees[node.id] = 0;
      });

      topology.links.forEach(link => {
        if (degrees[link.source] !== undefined) degrees[link.source]++;
        if (degrees[link.target] !== undefined) degrees[link.target]++;
      });

      const degreeValues = Object.values(degrees);
      stats.avgDegree = degreeValues.reduce((sum, deg) => sum + deg, 0) / degreeValues.length;
      stats.maxDegree = Math.max(...degreeValues);
      stats.minDegree = Math.min(...degreeValues);
    }

    return stats;
  }, []);

  return {
    savedTopologies,
    loadSavedTopologies,
    saveTopology,
    deleteTopology,
    createCustomTopology,
    importTopologyConfig,
    exportTopologyConfig,
    getVisualizationData,
    validateTopology,
    getTopologyStatistics
  };
};