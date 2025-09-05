import { useCallback } from 'react';

// Controller types from backend documentation
const CONTROLLER_TYPES = {
  ryu: {
    name: 'Ryu',
    description: 'Full-featured SDN controller with rich ecosystem',
    defaultPort: 6633,
    features: ['REST API', 'Clustering', 'Monitoring'],
    supportedVersions: ['1.0', '1.3', '1.5']
  },
  pox: {
    name: 'POX',
    description: 'Educational SDN controller with scripting support',
    defaultPort: 6633,
    features: ['Scripting', 'Extensible'],
    supportedVersions: ['1.0']
  },
  osken: {
    name: 'OsKen',
    description: 'Lightweight SDN controller for research',
    defaultPort: 6633,
    features: ['REST API', 'Lightweight'],
    supportedVersions: ['1.0', '1.3']
  },
  opendaylight: {
    name: 'OpenDaylight',
    description: 'Enterprise-grade SDN controller with rich features',
    defaultPort: 8181,
    features: ['REST API', 'Web UI', 'Clustering'],
    supportedVersions: ['latest']
  }
};

export const useControllerData = ({
  apiCall,
  addLog,
  setControllerStatus,
  setAvailableApps,
  setControllerLogs,
  setControllerConfig,
  setControllerStats,
  setLoading,
  controllerType = 'ryu',
  controllerApp,
  setControllerType,
  setControllerApp,
  controllerStatus
}) => {
  // Enhanced status fetching using correct backend endpoints
  const fetchControllerStatus = useCallback(async () => {
    const result = await apiCall('/controller/status');
    if (result.success) {
      setControllerStatus(prevStatus => {
        // Only update if data actually changed to prevent unnecessary re-renders
        if (JSON.stringify(prevStatus) !== JSON.stringify(result.data)) {
          return result.data;
        }
        return prevStatus;
      });
    }
  }, [apiCall]);

  // Fetch available controller apps
  const fetchAvailableApps = useCallback(async () => {
    const result = await apiCall('/controller/apps');
    if (result.success) {
      setAvailableApps(result.data.apps || []);
    }
  }, [apiCall]);

  // Fetch controller logs
  const fetchControllerLogs = useCallback(async () => {
    if (!controllerStatus.running) return;

    const result = await apiCall('/controller/logs?lines=50');
    if (result.success) {
      setControllerLogs(result.data);
    }
  }, [controllerStatus.running, apiCall]);

  // Fetch controller configuration
  const fetchControllerConfig = useCallback(async () => {
    const result = await apiCall('/controller/config');
    if (result.success) {
      setControllerConfig(result.data);
    }
  }, [apiCall]);

  // Fetch controller statistics
  const fetchControllerStats = useCallback(async () => {
    if (!controllerStatus.running) return;

    const result = await apiCall('/controller/stats');
    if (result.success) {
      setControllerStats(result.data);
    }
  }, [controllerStatus.running, apiCall]);

  // Enhanced controller management using correct backend endpoints
  const startController = async (config = {}) => {
    setLoading(true);
    try {
      const controllerConfig = {
        type: controllerType,
        app: controllerApp,
        ...CONTROLLER_TYPES[controllerType],
        ...config
      };

      const result = await apiCall('/controller/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(controllerConfig)
      });

      if (result.success && result.data.success) {
        const controllerName = CONTROLLER_TYPES[controllerType]?.name || controllerType;
        addLog(`🚀 ${controllerName} controller started with ${controllerApp}`, 'success', 'controller');
        await Promise.all([fetchControllerStatus(), fetchControllerConfig()]);
      } else {
        addLog(`❌ Failed to start controller: ${result.data?.error || result.error}`, 'error', 'controller');
      }
    } catch (error) {
      addLog('❌ Error starting controller', 'error', 'controller');
    }
    setLoading(false);
  };

  const stopController = async () => {
    setLoading(true);
    try {
      const result = await apiCall('/controller/stop', { method: 'POST' });
      if (result.success && result.data.success) {
        addLog('⏹️ Ryu controller stopped', 'warning', 'controller');
        await Promise.all([fetchControllerStatus(), fetchControllerConfig()]);
      } else {
        addLog(`❌ Failed to stop controller: ${result.data?.error || result.error}`, 'error', 'controller');
      }
    } catch (error) {
      addLog('❌ Error stopping controller', 'error', 'controller');
    }
    setLoading(false);
  };

  const restartController = async () => {
    setLoading(true);
    try {
      const result = await apiCall('/controller/restart', { method: 'POST' });
      if (result.success && result.data.success) {
        addLog('🔄 Ryu controller restarted', 'success', 'controller');
        await Promise.all([fetchControllerStatus(), fetchControllerConfig()]);
      } else {
        addLog(`❌ Failed to restart controller: ${result.data?.error || result.error}`, 'error', 'controller');
      }
    } catch (error) {
      addLog('❌ Error restarting controller', 'error', 'controller');
    }
    setLoading(false);
  };

  const switchControllerApp = async (newApp) => {
    setLoading(true);
    try {
      const result = await apiCall('/controller/switch/app', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app: newApp })
      });

      if (result.success && result.data.success) {
        addLog(`🔀 Switched controller to ${newApp}`, 'success', 'controller');
        if (setControllerApp) setControllerApp(newApp);
        await Promise.all([fetchControllerStatus(), fetchControllerConfig()]);
      } else {
        addLog(`❌ Failed to switch controller: ${result.data?.error || result.error}`, 'error', 'controller');
      }
    } catch (error) {
      addLog('❌ Error switching controller', 'error', 'controller');
    }
    setLoading(false);
  };

  // Switch controller type
  const switchControllerType = async (newType, newApp = null) => {
    setLoading(true);
    try {
      const result = await apiCall('/api/controller/switch/type', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: newType,
          app: newApp || CONTROLLER_TYPES[newType]?.defaultApp
        })
      });

      if (result.success) {
        const newControllerName = CONTROLLER_TYPES[newType]?.name || newType;
        const newAppName = newApp || CONTROLLER_TYPES[newType]?.defaultApp;
        addLog(`🔄 Switched to ${newControllerName} controller with ${newAppName}`, 'success', 'controller');
        if (setControllerType) setControllerType(newType);
        if (setControllerApp) setControllerApp(newAppName);
        await Promise.all([fetchControllerStatus(), fetchControllerConfig()]);
      } else {
        addLog(`❌ Failed to switch controller type: ${result.error || 'Unknown error'}`, 'error', 'controller');
      }
    } catch (error) {
      addLog('❌ Error switching controller type', 'error', 'controller');
    }
    setLoading(false);
  };

  // Get available controller types from backend
  const fetchAvailableControllerTypes = useCallback(async () => {
    try {
      const result = await apiCall('/api/controller/types');
      if (result.success && result.data) {
        return result.data.types || Object.keys(CONTROLLER_TYPES);
      }
    } catch (error) {
      console.error('Failed to fetch controller types:', error);
    }
    return Object.keys(CONTROLLER_TYPES);
  }, [apiCall]);

  // Get controller-specific configuration options
  const getControllerConfigOptions = useCallback((type) => {
    return CONTROLLER_TYPES[type] || {};
  }, []);

  // Advanced controller operations
  const configureControllerClustering = async (enabled, config = {}) => {
    setLoading(true);
    try {
      const result = await apiCall('/controller/clustering', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled, ...config })
      });

      if (result.success && result.data.success) {
        addLog(`🔗 Controller clustering ${enabled ? 'enabled' : 'disabled'}`, 'success', 'controller');
        await fetchControllerConfig();
      } else {
        addLog(`❌ Failed to configure clustering: ${result.data?.error || result.error}`, 'error', 'controller');
      }
    } catch (error) {
      addLog('❌ Error configuring clustering', 'error', 'controller');
    }
    setLoading(false);
  };

  const updateControllerConfig = async (configUpdates) => {
    setLoading(true);
    try {
      const result = await apiCall('/controller/config', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          type: controllerType,
          ...configUpdates
        })
      });

      if (result.success && result.data.success) {
        addLog('⚙️ Controller configuration updated', 'success', 'controller');
        await fetchControllerConfig();
      } else {
        addLog(`❌ Failed to update config: ${result.data?.error || result.error}`, 'error', 'controller');
      }
    } catch (error) {
      addLog('❌ Error updating controller config', 'error', 'controller');
    }
    setLoading(false);
  };

  const clearControllerLogs = async () => {
    try {
      const result = await apiCall('/controller/logs/clear', { method: 'POST' });
      if (result.success && result.data.success) {
        addLog('🧹 Controller logs cleared', 'info', 'controller');
        setControllerLogs([]);
      }
    } catch (error) {
      addLog('❌ Error clearing controller logs', 'error', 'controller');
    }
  };

  return {
    fetchControllerStatus,
    fetchAvailableApps,
    fetchControllerLogs,
    fetchControllerConfig,
    fetchControllerStats,
    startController,
    stopController,
    restartController,
    switchControllerApp,
    switchControllerType,
    fetchAvailableControllerTypes,
    getControllerConfigOptions,
    configureControllerClustering,
    updateControllerConfig,
    clearControllerLogs,
    CONTROLLER_TYPES
  };
};