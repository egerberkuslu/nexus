import { useState, useEffect, useCallback } from 'react';

const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:5000';

// Utility function for API calls
const apiCall = async (endpoint, options = {}) => {
  const url = `${API_BASE_URL}${endpoint}`;
  const config = {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  };

  try {
    const response = await fetch(url, config);
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || `HTTP error! status: ${response.status}`);
    }
    
    return data;
  } catch (error) {
    console.error(`API call failed for ${endpoint}:`, error);
    throw error;
  }
};

// ======================= BULK CONFIGURATION HOOK =======================

/**
 * useApplyConfig - Apply bulk configuration to multiple devices at once
 * Uses the new /apply-config endpoint with enhanced JSON spec
 */
export const useApplyConfig = () => {
  const [plan, setPlan] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const previewConfig = useCallback(async (spec) => {
    setLoading(true);
    setError(null);
    setPlan(null);
    try {
      const data = await apiCall('/api/device-management/apply-config', {
        method: 'POST',
        body: JSON.stringify({ ...spec, validate_only: true }),
      });
      setPlan(data.plan || []);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const applyConfig = useCallback(async (spec) => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await apiCall('/api/device-management/apply-config', {
        method: 'POST',
        body: JSON.stringify({ ...spec, validate_only: false }),
      });
      setResult(data);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const buildRouterConfig = useCallback((routerId, config) => {
    const spec = { routers: {} };
    spec.routers[routerId] = {
      sysctl: {},
      interfaces: [],
      routes: [],
      commands: []
    };

    // IP forwarding
    if (config.ipForwarding !== undefined) {
      spec.routers[routerId].sysctl['net.ipv4.ip_forward'] = config.ipForwarding ? '1' : '0';
    }

    // Interfaces
    if (config.interfaces?.length > 0) {
      spec.routers[routerId].interfaces = config.interfaces.map(intf => ({
        name: intf.name,
        flush: true,
        addresses: intf.ip ? [`${intf.ip}/${intf.prefix || '24'}`] : [],
        state: 'up'
      }));
    }

    // Routes
    if (config.routes?.length > 0) {
      spec.routers[routerId].routes = config.routes.map(route => ({
        action: route.action || 'add',
        destination: route.destination,
        via: route.gateway,
        dev: route.interface
      }));
    }

    // NAT
    if (config.nat_enabled) {
      spec.routers[routerId].commands.push(
        'iptables -t nat -F POSTROUTING 2>/dev/null || true',
        'iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE'
      );
    }

    // Firewall rules
    if (config.firewall_rules?.length > 0) {
      config.firewall_rules.forEach(rule => {
        spec.routers[routerId].commands.push(
          `iptables ${rule.action} ${rule.chain} ${rule.parameters}`
        );
      });
    }

    return spec;
  }, []);

  const buildHostConfig = useCallback((hostId, config) => {
    const spec = { hosts: {} };
    spec.hosts[hostId] = {
      interfaces: [],
      routes: [],
      commands: []
    };

    // Primary interface configuration
    if (config.ip) {
      const prefix = config.netmask ? netmaskToPrefix(config.netmask) : '24';
      spec.hosts[hostId].interfaces.push({
        name: `${hostId}-eth0`,
        addresses: [`${config.ip}/${prefix}`]
      });
    }

    // Default gateway
    if (config.gateway) {
      spec.hosts[hostId].routes.push(
        { action: 'del', destination: 'default', ignore_error: true },
        { action: 'add', destination: 'default', via: config.gateway }
      );
    }

    // DNS servers
    if (config.dns?.length > 0) {
      spec.hosts[hostId].commands.push('echo "# Auto-configured DNS" > /etc/resolv.conf');
      config.dns.forEach(dns => {
        spec.hosts[hostId].commands.push(`echo "nameserver ${dns}" >> /etc/resolv.conf`);
      });
    }

    // Hostname
    if (config.hostname) {
      spec.hosts[hostId].commands.push(
        `hostname ${config.hostname}`,
        `echo "127.0.0.1 ${config.hostname}" >> /etc/hosts`
      );
    }

    // Static routes
    if (config.routes?.length > 0) {
      config.routes.forEach(route => {
        if (route.network && route.gateway) {
          spec.hosts[hostId].routes.push({
            action: 'add',
            destination: route.network,
            via: route.gateway
          });
        }
      });
    }

    return spec;
  }, []);

  const buildSwitchConfig = useCallback((switchId, config) => {
    const spec = { switches: {} };
    spec.switches[switchId] = {
      ovs: {},
      commands: []
    };

    // Controller configuration
    if (config.controller_ip && config.controller_port) {
      spec.switches[switchId].ovs['set-controller'] = 
        `tcp:${config.controller_ip}:${config.controller_port}`;
    }

    // Fail mode
    if (config.fail_mode) {
      spec.switches[switchId].ovs['fail-mode'] = config.fail_mode;
    }

    // OpenFlow version
    if (config.openflow_version) {
      const version = config.openflow_version.replace('.', '');
      spec.switches[switchId].ovs.other_cfg = [
        `ovs-vsctl set bridge ${switchId} protocols=OpenFlow${version}`
      ];
    }

    // DPID
    if (config.dpid && config.dpid !== 'auto') {
      spec.switches[switchId].ovs.other_cfg = spec.switches[switchId].ovs.other_cfg || [];
      spec.switches[switchId].ovs.other_cfg.push(
        `ovs-vsctl set bridge ${switchId} other-config:datapath-id=${config.dpid}`
      );
    }

    return spec;
  }, []);

  const netmaskToPrefix = (netmask) => {
    const parts = netmask.split('.');
    let bits = 0;
    parts.forEach(part => {
      const num = parseInt(part);
      for (let i = 7; i >= 0; i--) {
        if ((num >> i) & 1) bits++;
      }
    });
    return bits.toString();
  };

  return { 
    plan, 
    result, 
    loading, 
    error, 
    previewConfig, 
    applyConfig,
    buildRouterConfig,
    buildHostConfig,
    buildSwitchConfig
  };
};

// ======================= DEVICE SNAPSHOT HOOKS =======================

/**
 * useDeviceSnapshots - Get current state of all devices
 */
export const useDeviceSnapshots = () => {
  const [snapshots, setSnapshots] = useState({
    routers: [],
    hosts: [],
    switches: [],
    controllers: []
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchSnapshots = useCallback(async (detail = 'full') => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/devices/snapshots?detail=${detail}`);
      if (data.success && data.devices) {
        setSnapshots(data.devices);
      }
      return data.devices;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshSnapshots = useCallback(() => {
    return fetchSnapshots('full');
  }, [fetchSnapshots]);

  useEffect(() => {
    fetchSnapshots('summary');
  }, [fetchSnapshots]);

  return { snapshots, loading, error, refreshSnapshots, fetchSnapshots };
};

/**
 * useDeviceSnapshot - Get current state of a single device
 */
export const useDeviceSnapshot = (deviceId) => {
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchSnapshot = useCallback(async (detail = 'full') => {
    if (!deviceId) return null;
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(
        `/api/device-management/devices/${deviceId}/snapshot?detail=${detail}`
      );
      if (data.success && data.device) {
        setSnapshot(data.device);
      }
      return data.device;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [deviceId]);

  const refreshSnapshot = useCallback(() => {
    return fetchSnapshot('full');
  }, [fetchSnapshot]);

  useEffect(() => {
    if (deviceId) {
      fetchSnapshot('full');
    }
  }, [deviceId, fetchSnapshot]);

  return { snapshot, loading, error, refreshSnapshot };
};

// ======================= COMMAND EXECUTION HOOK =======================

/**
 * useCommandExecution - Execute commands on nodes
 */
export const useCommandExecution = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const executeCommand = useCallback(async (nodeId, command) => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiCall(`/api/network/hosts/${nodeId}/cmd`, {
        method: 'POST',
        body: JSON.stringify({ command })
      });
      
      if (response.success && response.data) {
        return response.data;
      } else {
        throw new Error(response.error || 'Command execution failed');
      }
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { executeCommand, loading, error };
};

// ======================= CONTROLLER MANAGEMENT HOOKS =======================

export const useControllerManagement = () => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchStatus = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiCall('/api/controller/status');
      if (response.success) {
        setStatus(response.data);
      }
      return response.data;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const startController = useCallback(async (config) => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiCall('/api/controller/start', {
        method: 'POST',
        body: JSON.stringify(config)
      });
      await fetchStatus();
      return response;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [fetchStatus]);

  const stopController = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiCall('/api/controller/stop', { method: 'POST' });
      await fetchStatus();
      return response;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [fetchStatus]);

  const restartController = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiCall('/api/controller/restart', { method: 'POST' });
      await fetchStatus();
      return response;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [fetchStatus]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return {
    status,
    loading,
    error,
    fetchStatus,
    startController,
    stopController,
    restartController
  };
};

// ======================= COMBINED DEVICE MANAGEMENT HOOK =======================

export const useNetworkDevices = () => {
  const { snapshots, loading: snapshotsLoading, error: snapshotsError, refreshSnapshots } = useDeviceSnapshots();
  const { applyConfig, buildRouterConfig, buildHostConfig, buildSwitchConfig } = useApplyConfig();

  const loading = snapshotsLoading;
  const error = snapshotsError;

  const refreshAll = useCallback(() => {
    return refreshSnapshots();
  }, [refreshSnapshots]);

  const getAllDevices = useCallback(() => {
    return [
      ...snapshots.hosts.map(h => ({ ...h, deviceType: 'host' })),
      ...snapshots.switches.map(s => ({ ...s, deviceType: 'switch' })),
      ...snapshots.routers.map(r => ({ ...r, deviceType: 'router' })),
      ...snapshots.controllers.map(c => ({ ...c, deviceType: 'controller' }))
    ];
  }, [snapshots]);

  const getDeviceById = useCallback((deviceId) => {
    const allDevices = getAllDevices();
    return allDevices.find(device => device.id === deviceId);
  }, [getAllDevices]);

  const configureDevice = useCallback(async (deviceId, deviceType, config) => {
    let spec = {};
    
    switch (deviceType) {
      case 'router':
        spec = buildRouterConfig(deviceId, config);
        break;
      case 'host':
        spec = buildHostConfig(deviceId, config);
        break;
      case 'switch':
        spec = buildSwitchConfig(deviceId, config);
        break;
      default:
        throw new Error(`Unknown device type: ${deviceType}`);
    }
    
    return applyConfig(spec);
  }, [applyConfig, buildRouterConfig, buildHostConfig, buildSwitchConfig]);

  return {
    hosts: snapshots.hosts,
    switches: snapshots.switches,
    routers: snapshots.routers,
    controllers: snapshots.controllers,
    loading,
    error,
    refreshAll,
    getAllDevices,
    getDeviceById,
    configureDevice,
    applyConfig,
    buildRouterConfig,
    buildHostConfig,
    buildSwitchConfig,
    deviceCounts: {
      hosts: snapshots.hosts.length,
      switches: snapshots.switches.length,
      routers: snapshots.routers.length,
      controllers: snapshots.controllers.length,
      total: snapshots.hosts.length + snapshots.switches.length + 
             snapshots.routers.length + snapshots.controllers.length
    }
  };
};

// ======================= UTILITY HOOKS =======================

export const usePolling = (callback, interval = 5000, enabled = true) => {
  useEffect(() => {
    if (!enabled) return;
    
    const intervalId = setInterval(callback, interval);
    return () => clearInterval(intervalId);
  }, [callback, interval, enabled]);
};

export const useDevicePolling = (interval = 10000) => {
  const { refreshAll } = useNetworkDevices();
  
  usePolling(refreshAll, interval, true);
  
  return { refreshAll };
};

// Export default for easy importing
export default {
  useApplyConfig,
  useDeviceSnapshots,
  useDeviceSnapshot,
  useCommandExecution,
  useControllerManagement,
  useNetworkDevices,
  usePolling,
  useDevicePolling
};