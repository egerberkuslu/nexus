import { useCallback } from 'react';

export const useControllerData = ({
  apiCall,
  addLog,
  setControllerStatus,
  setAvailableApps,
  setControllerLogs,
  setControllerConfig,
  setControllerStats,
  setLoading,
  ryuApp,
  setRyuApp,
  controllerStatus
}) => {
  // Enhanced status fetching using correct backend endpoints
  const fetchControllerStatus = useCallback(async () => {
    const result = await apiCall('/controller/status');
    if (result.success) {
      setControllerStatus(result.data);
    }
  }, [apiCall, setControllerStatus]);

  // Fetch available controller apps
  const fetchAvailableApps = useCallback(async () => {
    const result = await apiCall('/controller/apps');
    if (result.success) {
      setAvailableApps(result.data.apps || []);
    }
  }, [apiCall, setAvailableApps]);

  // Fetch controller logs
  const fetchControllerLogs = useCallback(async () => {
    if (!controllerStatus.running) return;

    const result = await apiCall('/controller/logs?lines=50');
    if (result.success) {
      setControllerLogs(result.data);
    }
  }, [controllerStatus.running, apiCall, setControllerLogs]);

  // Fetch controller configuration
  const fetchControllerConfig = useCallback(async () => {
    const result = await apiCall('/controller/config');
    if (result.success) {
      setControllerConfig(result.data);
    }
  }, [apiCall, setControllerConfig]);

  // Fetch controller statistics
  const fetchControllerStats = useCallback(async () => {
    if (!controllerStatus.running) return;

    const result = await apiCall('/controller/stats');
    if (result.success) {
      setControllerStats(result.data);
    }
  }, [controllerStatus.running, apiCall, setControllerStats]);

  // Enhanced controller management using correct backend endpoints
  const startController = async () => {
    setLoading(true);
    try {
      const result = await apiCall('/controller/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type: ryuApp })
      });

      if (result.success && result.data.success) {
        addLog(`🚀 Ryu controller started with ${ryuApp}`, 'success', 'controller');
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
        setRyuApp(newApp);
        await Promise.all([fetchControllerStatus(), fetchControllerConfig()]);
      } else {
        addLog(`❌ Failed to switch controller: ${result.data?.error || result.error}`, 'error', 'controller');
      }
    } catch (error) {
      addLog('❌ Error switching controller', 'error', 'controller');
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
    clearControllerLogs
  };
};