import { useCallback } from 'react';

// Switch types from backend documentation
const SWITCH_TYPES = {
  ovs: {
    name: 'Open vSwitch',
    description: 'Full-featured virtual switch with OpenFlow support',
    protocols: ['OpenFlow10', 'OpenFlow11', 'OpenFlow12', 'OpenFlow13', 'OpenFlow14', 'OpenFlow15'],
    features: ['OpenFlow', 'QOS', 'Mirroring', 'NetFlow']
  },
  linux_bridge: {
    name: 'Linux Bridge',
    description: 'Simple Linux bridge without SDN controller',
    protocols: ['N/A'],
    features: ['STP', 'VLAN', 'Bonding']
  },
  p4: {
    name: 'P4 Switch',
    description: 'Programmable data plane switch with P4Runtime',
    protocols: ['P4Runtime'],
    features: ['Runtime Programming', 'Table Entries', 'P4Runtime']
  }
};

export const useSwitchData = ({
  apiCall,
  addLog,
  setSwitchStatus,
  setSwitchConfig,
  setSwitchStats,
  setLoading
}) => {
  // Fetch available switch types from backend
  const fetchAvailableSwitchTypes = useCallback(async () => {
    try {
      const result = await apiCall('/switch/available');
      if (result.success) {
        return result.data.switch_types || [];
      }
    } catch (error) {
      console.error('Failed to fetch switch types:', error);
      addLog('❌ Failed to fetch available switch types', 'error', 'switch');
    }
    return Object.keys(SWITCH_TYPES);
  }, [apiCall, addLog]);

  // Fetch switch templates/P4 programs
  const fetchSwitchTemplates = useCallback(async (switchType) => {
    try {
      if (switchType === 'p4') {
        const result = await apiCall('/switch/p4/templates');
        if (result.success) {
          return result.data.templates || [];
        }
      }
      return [];
    } catch (error) {
      console.error('Failed to fetch switch templates:', error);
      addLog('❌ Failed to fetch switch templates', 'error', 'switch');
      return [];
    }
  }, [apiCall, addLog]);

  // Get switch status
  const fetchSwitchStatus = useCallback(async (switchId) => {
    try {
      const result = await apiCall(`/switch/status/${switchId}`);
      if (result.success) {
        if (setSwitchStatus) setSwitchStatus(result.data);
        return result.data;
      }
    } catch (error) {
      addLog(`❌ Failed to fetch switch status: ${error.message}`, 'error', 'switch');
    }
    return null;
  }, [apiCall, addLog, setSwitchStatus]);

  // Create switch
  const createSwitch = useCallback(async (switchType, switchId, config = {}) => {
    setLoading(true);
    try {
      const result = await apiCall('/switch/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          switch_type: switchType,
          switch_id: switchId,
          config: {
            ...SWITCH_TYPES[switchType]?.defaultConfig,
            ...config
          }
        })
      });

      if (result.success && result.data.success) {
        const switchName = SWITCH_TYPES[switchType]?.name || switchType;
        addLog(`🔧 ${switchName} switch "${switchId}" created successfully`, 'success', 'switch');
        return true;
      } else {
        addLog(`❌ Failed to create switch: ${result.data?.error || result.error}`, 'error', 'switch');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error creating switch: ${error.message}`, 'error', 'switch');
      return false;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading]);

  // Configure switch
  const configureSwitch = useCallback(async (switchId, config) => {
    setLoading(true);
    try {
      const result = await apiCall(`/switch/configure/${switchId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });

      if (result.success && result.data.success) {
        addLog(`⚙️ Switch "${switchId}" configured successfully`, 'success', 'switch');
        if (setSwitchConfig) setSwitchConfig(config);
        return true;
      } else {
        addLog(`❌ Failed to configure switch: ${result.data?.error || result.error}`, 'error', 'switch');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error configuring switch: ${error.message}`, 'error', 'switch');
      return false;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading, setSwitchConfig]);

  // Get switch statistics
  const fetchSwitchStats = useCallback(async (switchId) => {
    try {
      const result = await apiCall(`/switch/stats/${switchId}`);
      if (result.success) {
        if (setSwitchStats) setSwitchStats(result.data);
        return result.data;
      }
    } catch (error) {
      addLog(`❌ Failed to fetch switch stats: ${error.message}`, 'error', 'switch');
    }
    return null;
  }, [apiCall, addLog, setSwitchStats]);

  // Add flow to switch (OVS)
  const addSwitchFlow = useCallback(async (switchId, flowConfig) => {
    try {
      const result = await apiCall(`/switch/flow/${switchId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flowConfig)
      });

      if (result.success && result.data.success) {
        addLog(`🌊 Flow added to switch "${switchId}"`, 'success', 'switch');
        return true;
      } else {
        addLog(`❌ Failed to add flow: ${result.data?.error || result.error}`, 'error', 'switch');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error adding flow: ${error.message}`, 'error', 'switch');
      return false;
    }
  }, [apiCall, addLog]);

  // Delete flows from switch
  const deleteSwitchFlows = useCallback(async (switchId, flowFilter = {}) => {
    try {
      const result = await apiCall(`/switch/flows/${switchId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flowFilter)
      });

      if (result.success && result.data.success) {
        addLog(`🗑️ Flows deleted from switch "${switchId}"`, 'success', 'switch');
        return true;
      } else {
        addLog(`❌ Failed to delete flows: ${result.data?.error || result.error}`, 'error', 'switch');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error deleting flows: ${error.message}`, 'error', 'switch');
      return false;
    }
  }, [apiCall, addLog]);

  // Configure P4 program
  const configureP4Program = useCallback(async (switchId, programName, config = {}) => {
    try {
      const result = await apiCall(`/switch/p4/${switchId}/program`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          program_name: programName,
          ...config
        })
      });

      if (result.success && result.data.success) {
        addLog(`🔧 P4 program "${programName}" configured on switch "${switchId}"`, 'success', 'switch');
        return true;
      } else {
        addLog(`❌ Failed to configure P4 program: ${result.data?.error || result.error}`, 'error', 'switch');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error configuring P4 program: ${error.message}`, 'error', 'switch');
      return false;
    }
  }, [apiCall, addLog]);

  // Get switch configuration options
  const getSwitchConfigOptions = useCallback((switchType) => {
    return SWITCH_TYPES[switchType] || {};
  }, []);

  // Delete switch
  const deleteSwitch = useCallback(async (switchId) => {
    try {
      const result = await apiCall(`/switch/${switchId}`, {
        method: 'DELETE'
      });

      if (result.success && result.data.success) {
        addLog(`🗑️ Switch "${switchId}" deleted successfully`, 'success', 'switch');
        return true;
      } else {
        addLog(`❌ Failed to delete switch: ${result.data?.error || result.error}`, 'error', 'switch');
        return false;
      }
    } catch (error) {
      addLog(`❌ Error deleting switch: ${error.message}`, 'error', 'switch');
      return false;
    }
  }, [apiCall, addLog]);

  return {
    fetchAvailableSwitchTypes,
    fetchSwitchTemplates,
    fetchSwitchStatus,
    createSwitch,
    configureSwitch,
    fetchSwitchStats,
    addSwitchFlow,
    deleteSwitchFlows,
    configureP4Program,
    getSwitchConfigOptions,
    deleteSwitch,
    SWITCH_TYPES
  };
};
