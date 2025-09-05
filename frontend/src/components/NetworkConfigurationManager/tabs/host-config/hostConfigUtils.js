// hostConfigUtils.js - State management, validation, and API call builders

export const initialHostConfig = {
  // Basic host information
  hostname: '',
  
  // Network interface configuration
  interfaces: [],
  
  // DNS configuration
  dns_servers: ['8.8.8.8', '8.8.4.4'],
  search_domains: [],
  
  // Network services - track services to start/stop
  services_to_start: [],
  services_to_stop: [],
  service_configs: {},
  
  // Static routing
  routes_to_add: [],
  routes_to_delete: [],
  
  // Firewall configuration
  firewall_rules: [],
  firewall_policy: {},
  
  // DHCP configuration
  dhcp_mode: 'disabled', // 'disabled', 'client', 'server'
  dhcp_client_interface: '',
  dhcp_server_config: {
    subnet: '',
    netmask: '255.255.255.0',
    range_start: '',
    range_end: '',
    gateway: '',
    dns_servers: []
  },
  
  // System configuration
  system_hostname: '',
  timezone: 'UTC',
  custom_commands: [],
  
  // Connectivity tests
  test_targets: []
};

export function hostConfigReducer(state, action) {
  switch (action.type) {
    case 'SET_ALL':
      return { ...state, ...action.payload };
    
    case 'SET_FIELD':
      return { ...state, [action.field]: action.value };
    
    case 'SET_SERVICE_CONFIG':
      return {
        ...state,
        service_configs: {
          ...state.service_configs,
          [action.service]: {
            ...state.service_configs[action.service],
            [action.field]: action.value
          }
        }
      };
    
    case 'TOGGLE_SERVICE': {
      const service = action.service;
      const enabled = action.enabled;
      
      let services_to_start = [...state.services_to_start];
      let services_to_stop = [...state.services_to_stop];
      
      if (enabled) {
        // Add to start list, remove from stop list
        if (!services_to_start.includes(service)) {
          services_to_start.push(service);
        }
        services_to_stop = services_to_stop.filter(s => s !== service);
      } else {
        // Add to stop list, remove from start list
        if (!services_to_stop.includes(service)) {
          services_to_stop.push(service);
        }
        services_to_start = services_to_start.filter(s => s !== service);
      }
      
      return { ...state, services_to_start, services_to_stop };
    }

    // Interface operations
    case 'INTERFACE_SET': {
      const interfaces = [...(state.interfaces || [])];
      if (interfaces[action.index]) {
        interfaces[action.index] = { ...interfaces[action.index], [action.field]: action.value };
      }
      return { ...state, interfaces };
    }
    
    case 'INTERFACE_ADD':
      return {
        ...state,
        interfaces: [
          ...(state.interfaces || []),
          { 
            name: '', 
            ip_address: '', 
            state: 'up', 
            mtu: 1500,
            action: 'configure'
          }
        ]
      };
    
    case 'INTERFACE_REMOVE':
      return {
        ...state,
        interfaces: (state.interfaces || []).filter((_, idx) => idx !== action.index)
      };

    // DNS operations
    case 'DNS_SET': {
      const dns_servers = [...(state.dns_servers || [])];
      dns_servers[action.index] = action.value;
      return { ...state, dns_servers };
    }
    
    case 'DNS_ADD':
      return {
        ...state,
        dns_servers: [...(state.dns_servers || []), '']
      };
    
    case 'DNS_REMOVE':
      return {
        ...state,
        dns_servers: (state.dns_servers || []).filter((_, idx) => idx !== action.index)
      };

    // Search domain operations
    case 'SEARCH_DOMAIN_SET': {
      const search_domains = [...(state.search_domains || [])];
      search_domains[action.index] = action.value;
      return { ...state, search_domains };
    }
    
    case 'SEARCH_DOMAIN_ADD':
      return {
        ...state,
        search_domains: [...(state.search_domains || []), '']
      };
    
    case 'SEARCH_DOMAIN_REMOVE':
      return {
        ...state,
        search_domains: (state.search_domains || []).filter((_, idx) => idx !== action.index)
      };

    // Route operations
    case 'ROUTE_SET': {
      const routes_to_add = [...(state.routes_to_add || [])];
      if (routes_to_add[action.index]) {
        routes_to_add[action.index] = { ...routes_to_add[action.index], [action.field]: action.value };
      }
      return { ...state, routes_to_add };
    }
    
    case 'ROUTE_ADD':
      return {
        ...state,
        routes_to_add: [
          ...(state.routes_to_add || []),
          { 
            destination: '', 
            gateway: '', 
            interface: '', 
            metric: null 
          }
        ]
      };
    
    case 'ROUTE_REMOVE':
      return {
        ...state,
        routes_to_add: (state.routes_to_add || []).filter((_, idx) => idx !== action.index)
      };
    
    case 'ROUTE_DELETE_ADD':
      return {
        ...state,
        routes_to_delete: [
          ...(state.routes_to_delete || []),
          { destination: '', gateway: '' }
        ]
      };
    
    case 'ROUTE_DELETE_REMOVE':
      return {
        ...state,
        routes_to_delete: (state.routes_to_delete || []).filter((_, idx) => idx !== action.index)
      };

    // Firewall operations
    case 'FIREWALL_SET': {
      const firewall_rules = [...(state.firewall_rules || [])];
      if (firewall_rules[action.index]) {
        firewall_rules[action.index] = { ...firewall_rules[action.index], [action.field]: action.value };
      }
      return { ...state, firewall_rules };
    }
    
    case 'FIREWALL_ADD':
      return {
        ...state,
        firewall_rules: [
          ...(state.firewall_rules || []),
          { 
            action: 'add',
            chain: 'INPUT', 
            protocol: '', 
            source: '', 
            destination: '',
            port: '', 
            target: 'ACCEPT' 
          }
        ]
      };
    
    case 'FIREWALL_REMOVE':
      return {
        ...state,
        firewall_rules: (state.firewall_rules || []).filter((_, idx) => idx !== action.index)
      };
    
    case 'FIREWALL_SET_POLICY':
      return {
        ...state,
        firewall_policy: {
          ...state.firewall_policy,
          [action.chain]: action.policy
        }
      };

    // DHCP server configuration
    case 'DHCP_SERVER_SET':
      return {
        ...state,
        dhcp_server_config: {
          ...state.dhcp_server_config,
          [action.field]: action.value
        }
      };

    // Custom command operations
    case 'CUSTOM_COMMAND_SET': {
      const custom_commands = [...(state.custom_commands || [])];
      custom_commands[action.index] = action.value;
      return { ...state, custom_commands };
    }
    
    case 'CUSTOM_COMMAND_ADD':
      return {
        ...state,
        custom_commands: [...(state.custom_commands || []), '']
      };
    
    case 'CUSTOM_COMMAND_REMOVE':
      return {
        ...state,
        custom_commands: (state.custom_commands || []).filter((_, idx) => idx !== action.index)
      };

    // Test target operations
    case 'TEST_TARGET_ADD':
      return {
        ...state,
        test_targets: [
          ...(state.test_targets || []),
          { target: '', type: 'ping' }
        ]
      };
    
    case 'TEST_TARGET_REMOVE':
      return {
        ...state,
        test_targets: (state.test_targets || []).filter((_, idx) => idx !== action.index)
      };
    
    case 'TEST_TARGET_SET': {
      const test_targets = [...(state.test_targets || [])];
      if (test_targets[action.index]) {
        test_targets[action.index] = { ...test_targets[action.index], [action.field]: action.value };
      }
      return { ...state, test_targets };
    }

    default:
      return state;
  }
}

// Build individual API calls based on configuration
export function buildAPICallsFromConfig(local, selectedNode) {
  const apiCalls = [];
  const baseUrl = `/host-management/devices/${selectedNode.id}/host`;

  // Interface configurations
  local.interfaces?.forEach(intf => {
    if (intf.name?.trim()) {
      const body = {
        interface: intf.name.trim(),
        action: intf.action || 'configure'
      };
      
      if (intf.ip_address?.trim()) {
        body.ip_address = intf.ip_address.trim();
      }
      if (intf.state) {
        body.state = intf.state;
      }
      if (intf.mtu) {
        body.mtu = parseInt(intf.mtu);
      }
      
      apiCalls.push({
        url: `${baseUrl}/interfaces`,
        method: 'POST',
        body: body,
        description: `Configure interface ${intf.name}`
      });
    }
  });

  // DNS configuration
  const validDnsServers = (local.dns_servers || []).filter(dns => dns?.trim());
  const validSearchDomains = (local.search_domains || []).filter(domain => domain?.trim());
  
  if (validDnsServers.length > 0 || validSearchDomains.length > 0) {
    apiCalls.push({
      url: `${baseUrl}/dns`,
      method: 'POST',
      body: {
        nameservers: validDnsServers.map(dns => dns.trim()),
        search_domains: validSearchDomains.map(domain => domain.trim())
      },
      description: 'Configure DNS'
    });
  }

  // Service management - Start services
  local.services_to_start?.forEach(serviceName => {
    const body = {
      action: 'start'
    };
    
    // Add custom port if configured
    if (local.service_configs?.[serviceName]?.port) {
      body.port = parseInt(local.service_configs[serviceName].port);
    }
    
    apiCalls.push({
      url: `${baseUrl}/services/${serviceName}`,
      method: 'POST',
      body: body,
      description: `Start ${serviceName} service`
    });
  });

  // Service management - Stop services
  local.services_to_stop?.forEach(serviceName => {
    apiCalls.push({
      url: `${baseUrl}/services/${serviceName}`,
      method: 'POST',
      body: { action: 'stop' },
      description: `Stop ${serviceName} service`
    });
  });

  // Add routes
  local.routes_to_add?.forEach(route => {
    if (route.destination?.trim() && (route.gateway?.trim() || route.interface?.trim())) {
      const body = {
        destination: route.destination.trim()
      };
      
      if (route.gateway?.trim()) {
        body.gateway = route.gateway.trim();
      }
      if (route.interface?.trim()) {
        body.interface = route.interface.trim();
      }
      if (route.metric) {
        body.metric = parseInt(route.metric);
      }
      
      apiCalls.push({
        url: `${baseUrl}/routes`,
        method: 'POST',
        body: body,
        description: `Add route to ${route.destination}`
      });
    }
  });

  // Delete routes
  local.routes_to_delete?.forEach(route => {
    if (route.destination?.trim()) {
      const params = new URLSearchParams({
        destination: route.destination.trim()
      });
      
      if (route.gateway?.trim()) {
        params.append('gateway', route.gateway.trim());
      }
      
      apiCalls.push({
        url: `${baseUrl}/routes?${params.toString()}`,
        method: 'DELETE',
        description: `Delete route to ${route.destination}`
      });
    }
  });

  // Firewall rules
  local.firewall_rules?.forEach(rule => {
    if (rule.chain && rule.target) {
      const body = {
        action: rule.action || 'add',
        chain: rule.chain,
        target: rule.target
      };
      
      if (rule.protocol?.trim()) {
        body.protocol = rule.protocol.trim();
      }
      if (rule.source?.trim()) {
        body.source = rule.source.trim();
      }
      if (rule.destination?.trim()) {
        body.destination = rule.destination.trim();
      }
      if (rule.port?.trim()) {
        body.port = parseInt(rule.port.trim());
      }
      
      apiCalls.push({
        url: `${baseUrl}/firewall`,
        method: 'POST',
        body: body,
        description: `Add firewall rule for ${rule.chain}`
      });
    }
  });

  // Firewall policies
  Object.entries(local.firewall_policy || {}).forEach(([chain, policy]) => {
    if (policy) {
      apiCalls.push({
        url: `${baseUrl}/firewall`,
        method: 'POST',
        body: {
          action: 'set_policy',
          chain: chain,
          policy: policy
        },
        description: `Set ${chain} policy to ${policy}`
      });
    }
  });

  // DHCP configuration
  if (local.dhcp_mode === 'client' && local.dhcp_client_interface?.trim()) {
    apiCalls.push({
      url: `${baseUrl}/dhcp`,
      method: 'POST',
      body: {
        action: 'enable_client',
        interface: local.dhcp_client_interface.trim()
      },
      description: 'Enable DHCP client'
    });
  } else if (local.dhcp_mode === 'server') {
    const config = local.dhcp_server_config;
    if (config.subnet?.trim() && config.range_start?.trim() && config.range_end?.trim()) {
      const body = {
        action: 'configure_server',
        subnet: config.subnet.trim(),
        netmask: config.netmask?.trim() || '255.255.255.0',
        range_start: config.range_start.trim(),
        range_end: config.range_end.trim()
      };
      
      if (config.gateway?.trim()) {
        body.gateway = config.gateway.trim();
      }
      if (config.dns_servers?.length > 0) {
        body.dns_servers = config.dns_servers.filter(dns => dns?.trim());
      }
      
      apiCalls.push({
        url: `${baseUrl}/dhcp`,
        method: 'POST',
        body: body,
        description: 'Configure DHCP server'
      });
    }
  }

  // System configuration
  const systemBody = {};
  
  if (local.system_hostname?.trim() && local.system_hostname.trim() !== selectedNode.id) {
    systemBody.hostname = local.system_hostname.trim();
  }
  
  if (local.timezone && local.timezone !== 'UTC') {
    systemBody.timezone = local.timezone;
  }
  
  const validCommands = (local.custom_commands || []).filter(cmd => cmd?.trim());
  if (validCommands.length > 0) {
    systemBody.commands = validCommands.map(cmd => cmd.trim());
  }
  
  if (Object.keys(systemBody).length > 0) {
    apiCalls.push({
      url: `${baseUrl}/system`,
      method: 'POST',
      body: systemBody,
      description: 'Configure system settings'
    });
  }

  // Connectivity tests
  if (local.test_targets?.length > 0) {
    const validTargets = local.test_targets.filter(t => t.target?.trim());
    if (validTargets.length > 0) {
      // Group by test type for efficiency
      const testsByType = {};
      validTargets.forEach(t => {
        const type = t.type || 'ping';
        if (!testsByType[type]) {
          testsByType[type] = [];
        }
        testsByType[type].push(t.target.trim());
      });
      
      Object.entries(testsByType).forEach(([type, targets]) => {
        apiCalls.push({
          url: `${baseUrl}/test-connectivity`,
          method: 'POST',
          body: {
            targets: targets,
            type: type,
            timeout: 5
          },
          description: `Test connectivity using ${type}`
        });
      });
    }
  }

  return apiCalls;
}

export function validateHostConfig(local) {
  const errors = [];

  // Validate hostname
  if (local.system_hostname?.trim()) {
    const hostname = local.system_hostname.trim();
    if (!/^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$/.test(hostname)) {
      errors.push('Invalid hostname format');
    }
  }

  // Validate interfaces
  (local.interfaces || []).forEach((intf, index) => {
    if (intf.name?.trim()) {
      // Interface name validation
      if (!/^[a-zA-Z0-9\-]+$/.test(intf.name.trim())) {
        errors.push(`Interface ${index + 1}: Invalid name format`);
      }
      
      if (intf.ip_address?.trim()) {
        // Validate CIDR format
        if (!/^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/.test(intf.ip_address.trim())) {
          errors.push(`Interface ${index + 1}: Invalid IP/CIDR format`);
        } else {
          // Validate IP octets
          const [ip] = intf.ip_address.trim().split('/');
          const octets = ip.split('.').map(Number);
          if (octets.some(octet => octet < 0 || octet > 255)) {
            errors.push(`Interface ${index + 1}: Invalid IP address`);
          }
        }
      }
      
      if (intf.mtu) {
        const mtu = parseInt(intf.mtu);
        if (isNaN(mtu) || mtu < 68 || mtu > 9000) {
          errors.push(`Interface ${index + 1}: MTU must be 68-9000`);
        }
      }
    }
  });

  // Validate DNS servers
  (local.dns_servers || []).forEach((dns, index) => {
    if (dns?.trim()) {
      if (!/^(\d{1,3}\.){3}\d{1,3}$/.test(dns.trim())) {
        errors.push(`DNS server ${index + 1}: Invalid IP format`);
      } else {
        const octets = dns.trim().split('.').map(Number);
        if (octets.some(octet => octet < 0 || octet > 255)) {
          errors.push(`DNS server ${index + 1}: Invalid IP address`);
        }
      }
    }
  });

  // Validate search domains
  (local.search_domains || []).forEach((domain, index) => {
    if (domain?.trim() && !/^[a-zA-Z0-9]([a-zA-Z0-9\-\.]*[a-zA-Z0-9])?$/.test(domain.trim())) {
      errors.push(`Search domain ${index + 1}: Invalid format`);
    }
  });

  // Validate routes
  (local.routes_to_add || []).forEach((route, index) => {
    if (route.destination?.trim()) {
      const dest = route.destination.trim();
      if (dest !== 'default' && !/^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/.test(dest)) {
        errors.push(`Route ${index + 1}: Invalid destination`);
      }
      
      if (!route.gateway?.trim() && !route.interface?.trim()) {
        errors.push(`Route ${index + 1}: Gateway or interface required`);
      }
      
      if (route.gateway?.trim() && !/^(\d{1,3}\.){3}\d{1,3}$/.test(route.gateway.trim())) {
        errors.push(`Route ${index + 1}: Invalid gateway IP`);
      }
      
      if (route.metric) {
        const metric = parseInt(route.metric);
        if (isNaN(metric) || metric < 0 || metric > 4294967295) {
          errors.push(`Route ${index + 1}: Invalid metric`);
        }
      }
    }
  });

  // Validate firewall rules
  (local.firewall_rules || []).forEach((rule, index) => {
    if (!rule.chain) {
      errors.push(`Firewall rule ${index + 1}: Chain required`);
    }
    
    if (!rule.target) {
      errors.push(`Firewall rule ${index + 1}: Target required`);
    }
    
    if (rule.source?.trim() && !/^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/.test(rule.source.trim())) {
      errors.push(`Firewall rule ${index + 1}: Invalid source`);
    }
    
    if (rule.destination?.trim() && !/^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/.test(rule.destination.trim())) {
      errors.push(`Firewall rule ${index + 1}: Invalid destination`);
    }
    
    if (rule.port?.trim()) {
      const port = parseInt(rule.port.trim());
      if (isNaN(port) || port < 1 || port > 65535) {
        errors.push(`Firewall rule ${index + 1}: Invalid port`);
      }
    }
  });

  // Validate DHCP server configuration
  if (local.dhcp_mode === 'server') {
    const config = local.dhcp_server_config;
    
    if (!config.subnet?.trim()) {
      errors.push('DHCP Server: Subnet required');
    } else if (!/^(\d{1,3}\.){3}\d{1,3}$/.test(config.subnet.trim())) {
      errors.push('DHCP Server: Invalid subnet');
    }
    
    if (!config.range_start?.trim()) {
      errors.push('DHCP Server: Range start required');
    } else if (!/^(\d{1,3}\.){3}\d{1,3}$/.test(config.range_start.trim())) {
      errors.push('DHCP Server: Invalid range start');
    }
    
    if (!config.range_end?.trim()) {
      errors.push('DHCP Server: Range end required');
    } else if (!/^(\d{1,3}\.){3}\d{1,3}$/.test(config.range_end.trim())) {
      errors.push('DHCP Server: Invalid range end');
    }
    
    if (config.gateway?.trim() && !/^(\d{1,3}\.){3}\d{1,3}$/.test(config.gateway.trim())) {
      errors.push('DHCP Server: Invalid gateway');
    }
  }

  // Validate DHCP client configuration
  if (local.dhcp_mode === 'client' && !local.dhcp_client_interface?.trim()) {
    errors.push('DHCP Client: Interface required');
  }

  return errors;
}

// Helper function to execute API calls
export async function executeAPICall(call, apiCall) {
  const options = {
    method: call.method,
    headers: { 'Content-Type': 'application/json' }
  };
  
  if (call.body && call.method !== 'GET' && call.method !== 'DELETE') {
    options.body = JSON.stringify(call.body);
  }
  
  try {
    const response = await apiCall(call.url, options);
    return {
      success: response?.success || false,
      description: call.description,
      response: response
    };
  } catch (error) {
    return {
      success: false,
      description: call.description,
      error: error.message
    };
  }
}

// Utility functions
export const hostConfigUtils = {
  // Check if configuration has changes
  hasChanges: (local, original) => {
    return JSON.stringify(local) !== JSON.stringify(original);
  },

  // Get configuration summary
  getSummary: (local) => {
    const summary = {
      interfaces: (local.interfaces || []).filter(i => i.name?.trim()).length,
      dns_servers: (local.dns_servers || []).filter(dns => dns?.trim()).length,
      services_to_start: (local.services_to_start || []).length,
      services_to_stop: (local.services_to_stop || []).length,
      routes_to_add: (local.routes_to_add || []).filter(r => r.destination?.trim()).length,
      routes_to_delete: (local.routes_to_delete || []).length,
      firewall_rules: (local.firewall_rules || []).filter(r => r.chain?.trim()).length,
      dhcp_mode: local.dhcp_mode || 'disabled',
      custom_commands: (local.custom_commands || []).filter(cmd => cmd?.trim()).length
    };
    return summary;
  },

  // Reset configuration to defaults
  resetToDefaults: () => {
    return { ...initialHostConfig };
  },

  // Parse current status to identify needed changes
  parseStatusForChanges: (hostStatus, local) => {
    const changes = {
      interfaces_to_update: [],
      services_to_toggle: [],
      routes_to_modify: [],
      dns_changed: false,
      firewall_changed: false
    };

    // Check interfaces
    const currentInterfaces = hostStatus?.interfaces || [];
    local.interfaces?.forEach(configIntf => {
      const current = currentInterfaces.find(i => i.name === configIntf.name);
      if (current) {
        const currentIP = current.ip_addresses?.[0] || '';
        if (currentIP !== configIntf.ip_address || current.state !== configIntf.state) {
          changes.interfaces_to_update.push(configIntf.name);
        }
      }
    });

    // Check services
    const networkServices = hostStatus?.network_services || {};
    local.services_to_start?.forEach(service => {
      if (!networkServices[service]?.running) {
        changes.services_to_toggle.push({ service, action: 'start' });
      }
    });
    local.services_to_stop?.forEach(service => {
      if (networkServices[service]?.running) {
        changes.services_to_toggle.push({ service, action: 'stop' });
      }
    });

    // Check DNS
    const currentDNS = hostStatus?.dns_config?.nameservers || [];
    const configuredDNS = local.dns_servers?.filter(dns => dns?.trim()) || [];
    if (JSON.stringify(currentDNS.sort()) !== JSON.stringify(configuredDNS.sort())) {
      changes.dns_changed = true;
    }

    // Check firewall
    const currentRules = hostStatus?.firewall_status?.rule_count || 0;
    const configuredRules = local.firewall_rules?.filter(r => r.chain && r.target).length || 0;
    if (currentRules !== configuredRules) {
      changes.firewall_changed = true;
    }

    return changes;
  }
};