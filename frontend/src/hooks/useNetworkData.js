import { useCallback } from 'react';

export const useNetworkData = ({
  apiCall,
  addLog,
  setNetworkStatus,
  setTopology,
  setNetworkMetrics,
  setDetailedStats,
  setFlowStats,
  setInterfaceStats,
  setMetricsHistory,
  setLoading,
  networkStatus,
  selectedHost,
  command,
  setCommand
}) => {
  // Fetch real network metrics using correct backend endpoint
  const fetchNetworkMetrics = useCallback(async () => {
    if (!networkStatus.running) return;

    const result = await apiCall('/stats/metrics');
    if (result.success) {
      const metrics = result.data;
      setNetworkMetrics({
        uptime: metrics.uptime || '00:00:00',
        packets_transferred: metrics.packets_transferred || 0,
        total_bytes: metrics.total_bytes || 0,
        bandwidth_mbps: metrics.bandwidth_mbps || 0.0,
        latency_ms: metrics.latency_ms || 0.0,
        active_flows: metrics.active_flows || 0,
        total_interfaces: metrics.total_interfaces || 0
      });

      // Store metrics history for trends
      setMetricsHistory(prev => {
        const newHistory = [...prev, {
          timestamp: Date.now(),
          bandwidth: metrics.bandwidth_mbps || 0,
          latency: metrics.latency_ms || 0,
          packets: metrics.packets_transferred || 0
        }];
        return newHistory.slice(-20); // Keep last 20 readings
      });
    }
  }, [networkStatus.running, apiCall, setNetworkMetrics, setMetricsHistory]);

  // Fetch detailed network statistics
  const fetchDetailedStats = useCallback(async () => {
    if (!networkStatus.running) return;

    const result = await apiCall('/stats/detailed');
    if (result.success) {
      setDetailedStats(result.data);
      if (result.data.flow_stats) {
        setFlowStats(result.data.flow_stats);
      }
    }
  }, [networkStatus.running, apiCall, setDetailedStats, setFlowStats]);

  const fetchStatus = useCallback(async () => {
    const result = await apiCall('/network/status');
    if (result.success) {
      setNetworkStatus(result.data);
    }
  }, [apiCall, setNetworkStatus]);

  const fetchTopology = useCallback(async () => {
    const result = await apiCall('/topology/full');
    if (result.success) {
      setTopology(result.data);
    }
  }, [apiCall, setTopology]);

  // Enhanced network management using correct backend endpoints
  const createNetwork = async () => {
    setLoading(true);
    try {
      const result = await apiCall('/network/create', { method: 'POST' });
      if (result.success && result.data.success) {
        addLog('🔧 Network topology created successfully', 'success', 'network');
        await Promise.all([fetchStatus(), fetchTopology()]);
      } else {
        addLog(`❌ Failed to create network: ${result.data?.error || result.error}`, 'error', 'network');
      }
    } catch (error) {
      addLog('❌ Error creating network', 'error', 'network');
    }
    setLoading(false);
  };

  // Enhanced custom topology creation
  const createCustomTopology = async (topologyConfig) => {
    setLoading(true);
    try {
      // Format topology for backend
      const backendTopology = formatTopologyForBackend(topologyConfig);
      
      const result = await apiCall('/network/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'custom',
          topology: backendTopology
        })
      });

      if (result.success && result.data.success) {
        addLog(`🔧 Custom topology "${topologyConfig.name || 'Custom'}" created successfully`, 'success', 'network');
        await Promise.all([fetchStatus(), fetchTopology()]);
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
  };

  // Format topology from frontend builder to backend format
  const formatTopologyForBackend = (frontendTopology) => {
    try {
      // Handle predefined topology types
      if (frontendTopology.type && typeof frontendTopology.type === 'string') {
        return {
          type: frontendTopology.type,
          ...frontendTopology
        };
      }

      // Handle custom topology from builder
      const formattedTopology = {
        name: frontendTopology.name || 'Custom Topology',
        nodes: frontendTopology.nodes || [],
        links: (frontendTopology.links || []).map(link => ({
          source: link.source,
          target: link.target,
          bandwidth: link.bandwidth || '10M',
          delay: link.delay || '1ms',
          loss: link.loss || 0
        }))
      };

      return formattedTopology;
    } catch (error) {
      addLog(`❌ Error formatting topology: ${error.message}`, 'error', 'network');
      throw error;
    }
  };

  // Handle predefined topology creation
  const createPredefinedTopology = async (topologyType) => {
    setLoading(true);
    try {
      let topologyConfig;

      switch (topologyType) {
        case 'simple':
          topologyConfig = {
            type: 'simple',
            hosts: 2,
            switches: 1
          };
          break;
        case 'linear':
          topologyConfig = {
            type: 'linear',
            hosts: 4,
            switches: 4
          };
          break;
        case 'tree':
          topologyConfig = {
            type: 'tree',
            depth: 3,
            fanout: 2
          };
          break;
        case 'star':
          topologyConfig = {
            type: 'star',
            hosts: 6
          };
          break;
        default:
          throw new Error(`Unknown topology type: ${topologyType}`);
      }

      const result = await apiCall('/network/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: 'predefined',
          topology: topologyConfig
        })
      });

      if (result.success && result.data.success) {
        addLog(`🔧 ${topologyType} topology created successfully`, 'success', 'network');
        await Promise.all([fetchStatus(), fetchTopology()]);
        return true;
      } else {
        addLog(`❌ Failed to create ${topologyType} topology: ${result.data?.error || result.error}`, 'error', 'network');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error creating ${topologyType} topology`, 'error', 'network');
      return false;
    } finally {
      setLoading(false);
    }
  };

  const startNetwork = async () => {
    setLoading(true);
    try {
      const result = await apiCall('/network/start', { method: 'POST' });
      if (result.success && result.data.success) {
        addLog('✅ Network started successfully', 'success', 'network');
        await Promise.all([fetchStatus(), fetchTopology()]);
      } else {
        addLog(`❌ Failed to start network: ${result.data?.error || result.error}`, 'error', 'network');
      }
    } catch (error) {
      addLog('❌ Error starting network', 'error', 'network');
    }
    setLoading(false);
  };

  const stopNetwork = async () => {
    setLoading(true);
    try {
      const result = await apiCall('/network/stop', { method: 'POST' });
      if (result.success && result.data.success) {
        addLog('⏹️ Network stopped', 'warning', 'network');
        await Promise.all([fetchStatus(), fetchTopology()]);
        // Reset metrics when network stops
        setNetworkMetrics({
          uptime: '00:00:00',
          packets_transferred: 0,
          total_bytes: 0,
          bandwidth_mbps: 0.0,
          latency_ms: 0.0,
          active_flows: 0,
          total_interfaces: 0
        });
        setMetricsHistory([]);
      } else {
        addLog(`❌ Failed to stop network: ${result.data?.error || result.error}`, 'error', 'network');
      }
    } catch (error) {
      addLog('❌ Error stopping network', 'error', 'network');
    }
    setLoading(false);
  };

  const runPingTest = async () => {
    setLoading(true);
    try {
      const result = await apiCall('/network/ping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });

      if (result.success && result.data.result) {
        addLog(`🏓 Ping test: ${result.data.result}`, 'info', 'test');
      } else {
        addLog(`❌ Ping failed: ${result.data?.error || result.error}`, 'error', 'test');
      }
    } catch (error) {
      addLog('❌ Error running ping test', 'error', 'test');
    }
    setLoading(false);
  };

  const executeCommand = async () => {
    if (!selectedHost || !command) return;

    setLoading(true);
    try {
      const result = await apiCall(`/network/hosts/${selectedHost}/cmd`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
      });

      if (result.success && result.data.result) {
        addLog(`💻 ${selectedHost}> ${command}`, 'command', 'terminal');
        addLog(`📤 ${result.data.result.slice(0, 200)}${result.data.result.length > 200 ? '...' : ''}`, 'output', 'terminal');
        setCommand('');
      } else {
        addLog(`❌ Command failed: ${result.data?.error || result.error}`, 'error', 'terminal');
      }
    } catch (error) {
      addLog('❌ Error executing command', 'error', 'terminal');
    }
    setLoading(false);
  };

  return {
    fetchNetworkMetrics,
    fetchDetailedStats,
    fetchStatus,
    fetchTopology,
    createNetwork,
    createCustomTopology,
    createPredefinedTopology,
    startNetwork,
    stopNetwork,
    runPingTest,
    executeCommand
  };
};