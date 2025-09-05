// hooks/useMessage.js
import { useState } from 'react';

export const useMessage = () => {
  const [message, setMessage] = useState('');

  const showMessage = (text, type = 'info') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(''), 5000);
  };

  const clearMessage = () => setMessage('');

  return { message, showMessage, clearMessage };
};

// hooks/useNetworkApi.js
export const useNetworkApi = () => {
  const apiCall = async (endpoint, options = {}) => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL || 'http://localhost:5000'}/api${endpoint}`, {
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        },
        ...options
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error(`API call failed for ${endpoint}:`, error);
      throw error;
    }
  };

  return { apiCall };
};

// hooks/useConfiguration.js
import { useState } from 'react';

export const useConfiguration = () => {
  const [hostConfig, setHostConfig] = useState({
    ip: '',
    netmask: '255.255.255.0',
    gateway: '',
    dns: ['8.8.8.8', '8.8.4.4'],
    hostname: '',
    services: [],
    routes: [],
    interfaces: []
  });

  const [switchConfig, setSwitchConfig] = useState({
    openflow_version: '1.3',
    controller_ip: '127.0.0.1',
    controller_port: 6633,
    dpid: '',
    fail_mode: 'secure',
    protocols: ['OpenFlow13'],
    flow_tables: [],
    ports: []
  });

  const [routerConfig, setRouterConfig] = useState({
    interfaces: [],
    routing_protocol: 'static',
    static_routes: [],
    nat_enabled: false,
    firewall_rules: [],
    bgp_config: {},
    ospf_config: {},
    dhcp_pools: []
  });

  const [controllerConfig, setControllerConfig] = useState({
    type: 'simple_switch_13',
    port: 6633,
    ip: '127.0.0.1',
    applications: [],
    log_level: 'INFO',
    config_flags: [],
    rest_api_enabled: false,
    rest_api_port: 8080
  });

  const updateHostConfig = (updates) => {
    setHostConfig(prev => ({ ...prev, ...updates }));
  };

  const updateSwitchConfig = (updates) => {
    setSwitchConfig(prev => ({ ...prev, ...updates }));
  };

  const updateRouterConfig = (updates) => {
    setRouterConfig(prev => ({ ...prev, ...updates }));
  };

  const updateControllerConfig = (updates) => {
    setControllerConfig(prev => ({ ...prev, ...updates }));
  };

  const exportConfiguration = (selectedNode) => {
    const config = {
      host: hostConfig,
      switch: switchConfig,
      router: routerConfig,
      controller: controllerConfig,
      selectedNode: selectedNode?.id,
      timestamp: new Date().toISOString()
    };

    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `network-config-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const importConfiguration = (event, showMessage) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const config = JSON.parse(e.target.result);
        setHostConfig(config.host || hostConfig);
        setSwitchConfig(config.switch || switchConfig);
        setRouterConfig(config.router || routerConfig);
        setControllerConfig(config.controller || controllerConfig);
        showMessage('Configuration imported successfully', 'success');
      } catch (error) {
        showMessage('Error importing configuration: ' + error.message, 'error');
      }
    };
    reader.readAsText(file);
  };

  return {
    hostConfig,
    switchConfig,
    routerConfig,
    controllerConfig,
    updateHostConfig,
    updateSwitchConfig,
    updateRouterConfig,
    updateControllerConfig,
    exportConfiguration,
    importConfiguration
  };
};