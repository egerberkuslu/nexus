// hooks/useConfiguration.js
import { useState, useCallback } from 'react';

/**
 * Custom hook for managing network device configurations
 * Handles state for hosts, switches, routers, and controllers
 */
export const useConfiguration = () => {
  // Host configuration state
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

  // Switch configuration state
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

  // Router configuration state
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

  // Controller configuration state
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

  /**
   * Update host configuration
   * @param {object} updates - Partial host config updates
   */
  const updateHostConfig = useCallback((updates) => {
    setHostConfig(prev => ({ ...prev, ...updates }));
  }, []);

  /**
   * Update switch configuration
   * @param {object} updates - Partial switch config updates
   */
  const updateSwitchConfig = useCallback((updates) => {
    setSwitchConfig(prev => ({ ...prev, ...updates }));
  }, []);

  /**
   * Update router configuration
   * @param {object} updates - Partial router config updates
   */
  const updateRouterConfig = useCallback((updates) => {
    setRouterConfig(prev => ({ ...prev, ...updates }));
  }, []);

  /**
   * Update controller configuration
   * @param {object} updates - Partial controller config updates
   */
  const updateControllerConfig = useCallback((updates) => {
    setControllerConfig(prev => ({ ...prev, ...updates }));
  }, []);

  /**
   * Reset all configurations to default values
   */
  const resetAllConfigurations = useCallback(() => {
    setHostConfig({
      ip: '',
      netmask: '255.255.255.0',
      gateway: '',
      dns: ['8.8.8.8', '8.8.4.4'],
      hostname: '',
      services: [],
      routes: [],
      interfaces: []
    });

    setSwitchConfig({
      openflow_version: '1.3',
      controller_ip: '127.0.0.1',
      controller_port: 6633,
      dpid: '',
      fail_mode: 'secure',
      protocols: ['OpenFlow13'],
      flow_tables: [],
      ports: []
    });

    setRouterConfig({
      interfaces: [],
      routing_protocol: 'static',
      static_routes: [],
      nat_enabled: false,
      firewall_rules: [],
      bgp_config: {},
      ospf_config: {},
      dhcp_pools: []
    });

    setControllerConfig({
      type: 'simple_switch_13',
      port: 6633,
      ip: '127.0.0.1',
      applications: [],
      log_level: 'INFO',
      config_flags: [],
      rest_api_enabled: false,
      rest_api_port: 8080
    });
  }, []);

  /**
   * Load configuration for a specific node
   * @param {object} node - Node object with configuration data
   */
  const loadNodeConfiguration = useCallback((node) => {
    if (!node) return;

    switch (node.type) {
      case 'host':
        updateHostConfig({
          ip: node.ip || '',
          hostname: node.id || '',
          mac: node.mac || ''
        });
        break;
      
      case 'switch':
        updateSwitchConfig({
          dpid: node.dpid || '',
          controller_ip: node.controller_ip || '127.0.0.1',
          controller_port: node.controller_port || 6633
        });
        break;
      
      case 'router':
        updateRouterConfig({
          interfaces: node.interfaces || [],
          routing_protocol: node.routing_protocol || 'static'
        });
        break;
      
      case 'controller':
        updateControllerConfig({
          type: node.controller_type || 'simple_switch_13',
          port: node.port || 6633,
          ip: node.ip || '127.0.0.1'
        });
        break;
    }
  }, [updateHostConfig, updateSwitchConfig, updateRouterConfig, updateControllerConfig]);

  /**
   * Export all configurations to a JSON object
   * @param {object} selectedNode - Currently selected node
   * @returns {object} Complete configuration export
   */
  const exportConfiguration = useCallback((selectedNode) => {
    const config = {
      host: hostConfig,
      switch: switchConfig,
      router: routerConfig,
      controller: controllerConfig,
      selectedNode: selectedNode?.id,
      timestamp: new Date().toISOString(),
      version: '1.0'
    };

    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `network-config-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);

    return config;
  }, [hostConfig, switchConfig, routerConfig, controllerConfig]);

  /**
   * Import configurations from a file
   * @param {Event} event - File input change event
   * @param {Function} showMessage - Message display function
   */
  const importConfiguration = useCallback((event, showMessage) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const config = JSON.parse(e.target.result);
        
        // Validate configuration structure
        if (!config || typeof config !== 'object') {
          throw new Error('Invalid configuration file format');
        }

        // Import configurations with validation
        if (config.host) {
          setHostConfig(prevConfig => ({ ...prevConfig, ...config.host }));
        }
        
        if (config.switch) {
          setSwitchConfig(prevConfig => ({ ...prevConfig, ...config.switch }));
        }
        
        if (config.router) {
          setRouterConfig(prevConfig => ({ ...prevConfig, ...config.router }));
        }
        
        if (config.controller) {
          setControllerConfig(prevConfig => ({ ...prevConfig, ...config.controller }));
        }

        showMessage('Configuration imported successfully', 'success');
      } catch (error) {
        console.error('Configuration import error:', error);
        showMessage(`Error importing configuration: ${error.message}`, 'error');
      }
    };

    reader.onerror = () => {
      showMessage('Error reading configuration file', 'error');
    };

    reader.readAsText(file);
  }, []);

  /**
   * Get configuration for a specific node type
   * @param {string} nodeType - Type of node ('host', 'switch', 'router', 'controller')
   * @returns {object} Configuration object for the specified node type
   */
  const getConfigForNodeType = useCallback((nodeType) => {
    switch (nodeType) {
      case 'host':
        return hostConfig;
      case 'switch':
        return switchConfig;
      case 'router':
        return routerConfig;
      case 'controller':
        return controllerConfig;
      default:
        return {};
    }
  }, [hostConfig, switchConfig, routerConfig, controllerConfig]);

  /**
   * Validate configuration for a specific node type
   * @param {string} nodeType - Type of node to validate
   * @returns {object} Validation result with isValid and errors array
   */
  const validateConfiguration = useCallback((nodeType) => {
    const config = getConfigForNodeType(nodeType);
    const errors = [];

    switch (nodeType) {
      case 'host':
        if (config.ip && !/^(\d{1,3}\.){3}\d{1,3}$/.test(config.ip)) {
          errors.push('Invalid IP address format');
        }
        if (config.gateway && !/^(\d{1,3}\.){3}\d{1,3}$/.test(config.gateway)) {
          errors.push('Invalid gateway address format');
        }
        break;

      case 'switch':
        if (config.controller_port && (config.controller_port < 1 || config.controller_port > 65535)) {
          errors.push('Controller port must be between 1 and 65535');
        }
        if (config.controller_ip && !/^(\d{1,3}\.){3}\d{1,3}$/.test(config.controller_ip)) {
          errors.push('Invalid controller IP address format');
        }
        break;

      case 'controller':
        if (config.port && (config.port < 1 || config.port > 65535)) {
          errors.push('Port must be between 1 and 65535');
        }
        if (config.rest_api_port && (config.rest_api_port < 1 || config.rest_api_port > 65535)) {
          errors.push('REST API port must be between 1 and 65535');
        }
        break;
    }

    return {
      isValid: errors.length === 0,
      errors
    };
  }, [getConfigForNodeType]);

  return {
    // Configuration states
    hostConfig,
    switchConfig,
    routerConfig,
    controllerConfig,
    
    // Update functions
    updateHostConfig,
    updateSwitchConfig,
    updateRouterConfig,
    updateControllerConfig,
    
    // Utility functions
    resetAllConfigurations,
    loadNodeConfiguration,
    exportConfiguration,
    importConfiguration,
    getConfigForNodeType,
    validateConfiguration
  };
};