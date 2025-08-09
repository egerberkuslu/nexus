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

// ======================= HOST MANAGEMENT HOOKS =======================

export const useHosts = () => {
  const [hosts, setHosts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchHosts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall('/api/device-management/hosts');
      setHosts(data.hosts || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHosts();
  }, [fetchHosts]);

  const refreshHosts = useCallback(() => {
    fetchHosts();
  }, [fetchHosts]);

  return { hosts, loading, error, refreshHosts };
};

export const useHostDetails = (hostId) => {
  const [hostDetails, setHostDetails] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchHostDetails = useCallback(async () => {
    if (!hostId) return;
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/hosts/${hostId}`);
      setHostDetails(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [hostId]);

  useEffect(() => {
    fetchHostDetails();
  }, [fetchHostDetails]);

  const refreshHostDetails = useCallback(() => {
    fetchHostDetails();
  }, [fetchHostDetails]);

  return { hostDetails, loading, error, refreshHostDetails };
};

export const useHostConfiguration = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const configureHost = useCallback(async (hostId, config) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/hosts/${hostId}/configure`, {
        method: 'POST',
        body: JSON.stringify(config),
      });
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { configureHost, loading, error };
};

export const useHostServices = (hostId) => {
  const [services, setServices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchServices = useCallback(async () => {
    if (!hostId) return;
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/hosts/${hostId}/services`);
      setServices(data.services || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [hostId]);

  const manageService = useCallback(async (action, service, port = 8080) => {
    if (!hostId) throw new Error('Host ID is required');
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/hosts/${hostId}/services`, {
        method: 'POST',
        body: JSON.stringify({ action, service, port }),
      });
      await fetchServices(); // Refresh services list
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [hostId, fetchServices]);

  useEffect(() => {
    fetchServices();
  }, [fetchServices]);

  const startService = useCallback((service, port) => 
    manageService('start', service, port), [manageService]);
  
  const stopService = useCallback((service) => 
    manageService('stop', service), [manageService]);

  const refreshServices = useCallback(() => {
    fetchServices();
  }, [fetchServices]);

  return { 
    services, 
    loading, 
    error, 
    startService, 
    stopService, 
    refreshServices 
  };
};

// ======================= SWITCH MANAGEMENT HOOKS =======================

export const useSwitches = () => {
  const [switches, setSwitches] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchSwitches = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall('/api/device-management/switches');
      setSwitches(data.switches || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSwitches();
  }, [fetchSwitches]);

  const refreshSwitches = useCallback(() => {
    fetchSwitches();
  }, [fetchSwitches]);

  return { switches, loading, error, refreshSwitches };
};

export const useSwitchFlows = (switchId) => {
  const [flows, setFlows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchFlows = useCallback(async () => {
    if (!switchId) return;
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/switches/${switchId}/flows`);
      setFlows(data.flows || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [switchId]);

  const addFlow = useCallback(async (flowConfig) => {
    if (!switchId) throw new Error('Switch ID is required');
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/switches/${switchId}/flows`, {
        method: 'POST',
        body: JSON.stringify(flowConfig),
      });
      await fetchFlows(); // Refresh flows list
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [switchId, fetchFlows]);

  const deleteFlows = useCallback(async (filter = '') => {
    if (!switchId) throw new Error('Switch ID is required');
    
    setLoading(true);
    setError(null);
    try {
      const url = filter ? 
        `/api/device-management/switches/${switchId}/flows?filter=${encodeURIComponent(filter)}` :
        `/api/device-management/switches/${switchId}/flows`;
      
      const data = await apiCall(url, { method: 'DELETE' });
      await fetchFlows(); // Refresh flows list
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [switchId, fetchFlows]);

  useEffect(() => {
    fetchFlows();
  }, [fetchFlows]);

  const refreshFlows = useCallback(() => {
    fetchFlows();
  }, [fetchFlows]);

  return { 
    flows, 
    loading, 
    error, 
    addFlow, 
    deleteFlows, 
    refreshFlows 
  };
};

export const useSwitchPorts = (switchId) => {
  const [ports, setPorts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchPorts = useCallback(async () => {
    if (!switchId) return;
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/switches/${switchId}/ports`);
      setPorts(data.ports || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [switchId]);

  const configurePorts = useCallback(async (portConfig) => {
    if (!switchId) throw new Error('Switch ID is required');
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/switches/${switchId}/ports`, {
        method: 'POST',
        body: JSON.stringify(portConfig),
      });
      await fetchPorts(); // Refresh ports list
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [switchId, fetchPorts]);

  useEffect(() => {
    fetchPorts();
  }, [fetchPorts]);

  const refreshPorts = useCallback(() => {
    fetchPorts();
  }, [fetchPorts]);

  return { 
    ports, 
    loading, 
    error, 
    configurePorts, 
    refreshPorts 
  };
};

// ======================= ROUTER MANAGEMENT HOOKS =======================

export const useRouters = () => {
  const [routers, setRouters] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchRouters = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall('/api/device-management/routers');
      setRouters(data.routers || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRouters();
  }, [fetchRouters]);

  const refreshRouters = useCallback(() => {
    fetchRouters();
  }, [fetchRouters]);

  return { routers, loading, error, refreshRouters };
};

export const useRouterRouting = (routerId) => {
  const [routingInfo, setRoutingInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchRoutingInfo = useCallback(async () => {
    if (!routerId) return;
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/routers/${routerId}/routing`);
      setRoutingInfo(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [routerId]);

  const addRoute = useCallback(async (routeConfig) => {
    if (!routerId) throw new Error('Router ID is required');
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/routers/${routerId}/routing`, {
        method: 'POST',
        body: JSON.stringify(routeConfig),
      });
      await fetchRoutingInfo(); // Refresh routing info
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [routerId, fetchRoutingInfo]);

  const deleteRoute = useCallback(async (destination) => {
    if (!routerId) throw new Error('Router ID is required');
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(
        `/api/device-management/routers/${routerId}/routing?destination=${encodeURIComponent(destination)}`,
        { method: 'DELETE' }
      );
      await fetchRoutingInfo(); // Refresh routing info
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [routerId, fetchRoutingInfo]);

  useEffect(() => {
    fetchRoutingInfo();
  }, [fetchRoutingInfo]);

  const refreshRoutingInfo = useCallback(() => {
    fetchRoutingInfo();
  }, [fetchRoutingInfo]);

  return { 
    routingInfo, 
    loading, 
    error, 
    addRoute, 
    deleteRoute, 
    refreshRoutingInfo 
  };
};

export const useRouterNAT = (routerId) => {
  const [natInfo, setNatInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchNATInfo = useCallback(async () => {
    if (!routerId) return;
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/routers/${routerId}/nat`);
      setNatInfo(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [routerId]);

  const addNATRule = useCallback(async (natConfig) => {
    if (!routerId) throw new Error('Router ID is required');
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/routers/${routerId}/nat`, {
        method: 'POST',
        body: JSON.stringify(natConfig),
      });
      await fetchNATInfo(); // Refresh NAT info
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [routerId, fetchNATInfo]);

  const deleteNATRule = useCallback(async (chain, ruleNumber = null) => {
    if (!routerId) throw new Error('Router ID is required');
    
    setLoading(true);
    setError(null);
    try {
      let url = `/api/device-management/routers/${routerId}/nat?chain=${chain}`;
      if (ruleNumber) {
        url += `&rule_number=${ruleNumber}`;
      }
      
      const data = await apiCall(url, { method: 'DELETE' });
      await fetchNATInfo(); // Refresh NAT info
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [routerId, fetchNATInfo]);

  useEffect(() => {
    fetchNATInfo();
  }, [fetchNATInfo]);

  const refreshNATInfo = useCallback(() => {
    fetchNATInfo();
  }, [fetchNATInfo]);

  return { 
    natInfo, 
    loading, 
    error, 
    addNATRule, 
    deleteNATRule, 
    refreshNATInfo 
  };
};

// ======================= CONTROLLER MANAGEMENT HOOKS =======================

export const useControllers = () => {
  const [controllers, setControllers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchControllers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall('/api/device-management/controllers');
      setControllers(data.controllers || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchControllers();
  }, [fetchControllers]);

  const refreshControllers = useCallback(() => {
    fetchControllers();
  }, [fetchControllers]);

  return { controllers, loading, error, refreshControllers };
};

export const useControllerFlows = (controllerId) => {
  const [controllerFlows, setControllerFlows] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchControllerFlows = useCallback(async () => {
    if (!controllerId) return;
    
    setLoading(true);
    setError(null);
    try {
      const data = await apiCall(`/api/device-management/controllers/${controllerId}/flows`);
      setControllerFlows(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [controllerId]);

  useEffect(() => {
    fetchControllerFlows();
  }, [fetchControllerFlows]);

  const refreshControllerFlows = useCallback(() => {
    fetchControllerFlows();
  }, [fetchControllerFlows]);

  return { controllerFlows, loading, error, refreshControllerFlows };
};

// ======================= COMBINED DEVICE MANAGEMENT HOOK =======================

export const useNetworkDevices = () => {
  const { hosts, loading: hostsLoading, error: hostsError, refreshHosts } = useHosts();
  const { switches, loading: switchesLoading, error: switchesError, refreshSwitches } = useSwitches();
  const { routers, loading: routersLoading, error: routersError, refreshRouters } = useRouters();
  const { controllers, loading: controllersLoading, error: controllersError, refreshControllers } = useControllers();

  const loading = hostsLoading || switchesLoading || routersLoading || controllersLoading;
  const error = hostsError || switchesError || routersError || controllersError;

  const refreshAll = useCallback(() => {
    refreshHosts();
    refreshSwitches();
    refreshRouters();
    refreshControllers();
  }, [refreshHosts, refreshSwitches, refreshRouters, refreshControllers]);

  const getAllDevices = useCallback(() => {
    return [
      ...hosts.map(h => ({ ...h, deviceType: 'host' })),
      ...switches.map(s => ({ ...s, deviceType: 'switch' })),
      ...routers.map(r => ({ ...r, deviceType: 'router' })),
      ...controllers.map(c => ({ ...c, deviceType: 'controller' }))
    ];
  }, [hosts, switches, routers, controllers]);

  const getDeviceById = useCallback((deviceId) => {
    const allDevices = getAllDevices();
    return allDevices.find(device => device.id === deviceId);
  }, [getAllDevices]);

  const getDevicesByType = useCallback((deviceType) => {
    switch (deviceType.toLowerCase()) {
      case 'host':
        return hosts;
      case 'switch':
        return switches;
      case 'router':
        return routers;
      case 'controller':
        return controllers;
      default:
        return [];
    }
  }, [hosts, switches, routers, controllers]);

  return {
    // Individual device types
    hosts,
    switches,
    routers,
    controllers,
    
    // Loading and error states
    loading,
    error,
    
    // Utility functions
    refreshAll,
    getAllDevices,
    getDeviceById,
    getDevicesByType,
    
    // Individual refresh functions
    refreshHosts,
    refreshSwitches,
    refreshRouters,
    refreshControllers,
    
    // Counts
    deviceCounts: {
      hosts: hosts.length,
      switches: switches.length,
      routers: routers.length,
      controllers: controllers.length,
      total: hosts.length + switches.length + routers.length + controllers.length
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
  useHosts,
  useHostDetails,
  useHostConfiguration,
  useHostServices,
  useSwitches,
  useSwitchFlows,
  useSwitchPorts,
  useRouters,
  useRouterRouting,
  useRouterNAT,
  useControllers,
  useControllerFlows,
  useNetworkDevices,
  usePolling,
  useDevicePolling
};