export const DEFAULT_PREFIX = '24';

// -------------------------- Utilities --------------------------
export const parseCidr = (cidr) => {
  if (!cidr || typeof cidr !== 'string') return { ip: '', prefix: DEFAULT_PREFIX };
  const [ip, prefix = DEFAULT_PREFIX] = cidr.split('/');
  return { ip, prefix: String(prefix) };
};

export const normalizeInterfaces = (snapIfs = [], routerId = 'r') =>
  snapIfs.map((it, i) => {
    // Accept {interface,address}, {name, ip, prefix}, or {name, ip:"x/y"}
    if (it.address && !it.ip) {
      const { ip, prefix } = parseCidr(String(it.address));
      return { 
        id: `${routerId}-eth${i}`, 
        name: it.interface || it.name || `${routerId}-eth${i}`, 
        ip, 
        prefix, 
        mac: it.mac,
        operation: 'configure'
      };
    }
    if (it.ip && it.prefix) {
      return { 
        id: `${routerId}-eth${i}`,
        name: it.interface || it.name || `${routerId}-eth${i}`, 
        ip: it.ip, 
        prefix: String(it.prefix), 
        mac: it.mac,
        operation: 'configure'
      };
    }
    if (typeof it.ip === 'string' && it.ip.includes('/')) {
      const { ip, prefix } = parseCidr(String(it.ip));
      return { 
        id: `${routerId}-eth${i}`,
        name: it.interface || it.name || `${routerId}-eth${i}`, 
        ip, 
        prefix, 
        mac: it.mac,
        operation: 'configure'
      };
    }
    return { 
      id: `${routerId}-eth${i}`,
      name: it.interface || it.name || `${routerId}-eth${i}`, 
      ip: '', 
      prefix: DEFAULT_PREFIX, 
      mac: it.mac,
      operation: 'configure'
    };
  });

export const normalizeRoutes = (snapRoutes = []) =>
  snapRoutes.map((r, i) => ({
    id: `route-${i}`,
    action: 'add',
    destination: r.destination || r.dest || '',
    gateway: r.gateway || r.via || '',
    interface: r.interface || r.dev || '',
    metric: r.metric,
    operation: 'configure' // for CRUD tracking
  }));

export const normalizeNatRules = (snapNat = {}) => {
  const rules = [];
  const masquerade = snapNat.masquerade || [];
  const chains = snapNat.chains || {};
  
  masquerade.forEach((rule, i) => {
    rules.push({
      id: `nat-masq-${i}`,
      type: 'masquerade',
      chain: 'POSTROUTING',
      source: rule.source || '',
      destination: rule.destination || '',
      out_interface: rule.out_interface || '',
      target: 'MASQUERADE',
      operation: 'configure'
    });
  });
  
  Object.entries(chains).forEach(([chainName, chainRules]) => {
    (chainRules || []).forEach((rule, i) => {
      rules.push({
        id: `nat-${chainName.toLowerCase()}-${i}`,
        type: 'custom',
        chain: chainName,
        source: rule.source || '',
        destination: rule.destination || '',
        target: rule.target || '',
        operation: 'configure'
      });
    });
  });
  
  return rules;
};

export const normalizeFirewallRules = (snapFirewall = {}) => {
  const rules = snapFirewall.rules || [];
  return rules.map((r, i) => ({
    id: `fw-${i}`,
    chain: r.chain || 'INPUT',
    protocol: r.protocol || '',
    source: r.source || '0.0.0.0/0',
    destination: r.destination || '0.0.0.0/0',
    sport: r.sport || '',
    dport: r.dport || '',
    target: r.target || 'ACCEPT',
    parameters: r.parameters || r.params || '',
    operation: 'configure'
  }));
};

// Legacy functions for backward compatibility
export const buildNatCommands = (enabled, ifNames = []) => {
  if (!enabled) return [];
  const wan = ifNames.find((n) => /eth0|wan/i.test(n)) || 'eth0';
  const lan = ifNames.find((n) => /eth1|lan/i.test(n)) || 'eth1';
  return [
    `iptables -t nat -C POSTROUTING -o ${wan} -j MASQUERADE 2>/dev/null || iptables -t nat -A POSTROUTING -o ${wan} -j MASQUERADE`,
    `iptables -C FORWARD -i ${lan} -o ${wan} -j ACCEPT 2>/dev/null || iptables -A FORWARD -i ${lan} -o ${wan} -j ACCEPT`,
    `iptables -C FORWARD -i ${wan} -o ${lan} -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || iptables -A FORWARD -i ${wan} -o ${lan} -m state --state RELATED,ESTABLISHED -j ACCEPT`,
  ];
};

export const buildFirewallCommands = (rules = []) =>
  rules
    .filter((r) => r?.parameters && String(r.parameters).trim())
    .map((r) => `iptables ${r.action || '-A'} ${r.chain || 'INPUT'} ${r.parameters}`);

// Enhanced configuration spec builder with proper interface CRUD
export const buildConfigurationSpec = (local, selectedNode, validateOnly = false, previousConfig = null) => {
  if (!selectedNode?.id) {
    throw new Error('No router selected');
  }

  const routerId = selectedNode.id;
  console.log('Building config spec for router:', routerId);
  console.log('Current interfaces:', local.interfaces);
  console.log('Previous config:', previousConfig);
  
  // Get previous interfaces for comparison
  const previousInterfaces = previousConfig?.interfaces || [];
  const currentInterfaces = local.interfaces || [];
  
  // Build interfaces with enhanced CRUD operations
  const interfaceConfigs = [];
  
  // 1. Handle interfaces marked for deletion
  const interfacesToDelete = currentInterfaces.filter(intf => intf.operation === 'delete');
  interfacesToDelete.forEach(intf => {
    if (intf.name && intf.name.trim()) {
      interfaceConfigs.push({
        name: String(intf.name).trim(),
        action: 'delete'
      });
      console.log('Marking interface for deletion:', intf.name);
    }
  });
  
  // 2. Handle active interfaces (configure/update)
  const activeInterfaces = currentInterfaces.filter(intf => intf.operation !== 'delete');
  activeInterfaces.forEach(intf => {
    if (intf.name && intf.name.trim()) {
      const interfaceConfig = {
        name: String(intf.name).trim(),
        flush: true,
        state: 'up'
      };
      
      if (intf.ip && intf.ip.trim()) {
        const ip = intf.ip.trim();
        const prefix = intf.prefix || DEFAULT_PREFIX;
        interfaceConfig.addresses = [`${ip}/${prefix}`];
      } else {
        interfaceConfig.addresses = [];
      }
      
      interfaceConfigs.push(interfaceConfig);
      console.log('Configuring interface:', intf.name, interfaceConfig);
    }
  });

  // 3. Find interfaces that were removed (not explicitly marked for deletion)
  if (previousInterfaces.length > 0) {
    const currentInterfaceNames = activeInterfaces.map(intf => intf.name).filter(Boolean);
    const previousInterfaceNames = previousInterfaces.map(intf => intf.name).filter(Boolean);
    
    const removedInterfaceNames = previousInterfaceNames.filter(name => 
      !currentInterfaceNames.includes(name) && 
      !interfacesToDelete.some(intf => intf.name === name)
    );
    
    removedInterfaceNames.forEach(name => {
      interfaceConfigs.push({
        name: name,
        action: 'delete'
      });
      console.log('Auto-detected removed interface:', name);
    });
  }

  // Build static routes with CRUD operations  
  const static_routes = (local.routes || [])
    .filter((r) => r.destination && r.destination.trim())
    .map((r) => {
      const route = {
        // backend expects 'add'|'del' (not 'delete')
        action: r.operation === 'delete' ? 'del' : (r.action || 'add').toLowerCase(),
        destination: r.destination.trim()
      };
      
      if (r.operation === 'delete') {
        route.ignore_error = true;
        return route;
      }
      
      if (r.gateway && r.gateway.trim()) {
        route.via = r.gateway.trim();
      }
      
      if (r.interface && r.interface.trim()) {
        route.dev = r.interface.trim();
      }
      
      if (r.metric !== undefined && r.metric !== '' && !isNaN(Number(r.metric))) {
        route.metric = Number(r.metric);
      }
      
      if (route.action === 'del') {
        route.ignore_error = true;
      }
      
      return route;
    });

  // Build NAT rules with CRUD operations
  const nat_rules = (local.natRules || [])
    .filter(rule => rule.operation !== 'delete')
    .map((rule) => {
      const natRule = {
        action: 'add',
        type: rule.type || 'masquerade',
        chain: rule.chain || 'POSTROUTING'
      };
      
      if (rule.source) natRule.source = rule.source;
      if (rule.destination) natRule.destination = rule.destination;
      if (rule.in_interface) natRule.in_interface = rule.in_interface;
      if (rule.out_interface) natRule.out_interface = rule.out_interface;
      if (rule.protocol) natRule.protocol = rule.protocol;
      if (rule.sport) natRule.sport = rule.sport;
      if (rule.dport) natRule.dport = rule.dport;
      if (rule.target) natRule.target = rule.target;
      if (rule.to_source) natRule.to_source = rule.to_source;
      if (rule.to_destination) natRule.to_destination = rule.to_destination;
      
      return natRule;
    });

  // Build firewall rules with CRUD operations
  const firewall_rules = (local.firewallRules || [])
    .filter(rule => rule.operation !== 'delete')
    .map((rule) => {
      const fwRule = {
        action: 'add',
        chain: rule.chain || 'INPUT'
      };
      
      if (rule.protocol) fwRule.protocol = rule.protocol;
      if (rule.source) fwRule.source = rule.source;
      if (rule.destination) fwRule.destination = rule.destination;
      if (rule.sport) fwRule.sport = rule.sport;
      if (rule.dport) fwRule.dport = rule.dport;
      if (rule.in_interface) fwRule.in_interface = rule.in_interface;
      if (rule.out_interface) fwRule.out_interface = rule.out_interface;
      if (rule.state) fwRule.state = rule.state;
      if (rule.target) fwRule.target = rule.target;
      if (rule.position) fwRule.position = rule.position;
      
      return fwRule;
    });

  // Build routing protocol configuration
  const routing_protocol = {
    protocol: local.protocol || 'static',
    action: 'enable'
  };

  // Add protocol-specific configuration
  if (local.protocol === 'bgp' && local.bgpConfig) {
    routing_protocol.config = {
      ...local.bgpConfig,
      as_number: local.bgpConfig.as_number || '65001'
    };
  } else if (local.protocol === 'ospf' && local.ospfConfig) {
    routing_protocol.config = {
      ...local.ospfConfig,
      area_id: local.ospfConfig.area_id || '0'
    };
  } else if (local.protocol === 'rip' && local.ripConfig) {
    routing_protocol.config = {
      ...local.ripConfig,
      version: local.ripConfig.version || '2'
    };
  }

  console.log('Routing protocol config:', routing_protocol);

  // Build legacy commands for backward compatibility
  const ifNames = activeInterfaces
    .filter(i => i.name && i.name.trim())
    .map((i) => String(i.name).trim());
    
  const legacyNatCmds = buildNatCommands(local.natEnabled, ifNames);
  const legacyFwCmds = buildFirewallCommands(local.legacyFirewallRules || []);
  const commands = [...legacyNatCmds, ...legacyFwCmds];

  // Build the complete spec
  const spec = {
    validate_only: !!validateOnly,
    routers: {
      [routerId]: {
        sysctl: { 
          'net.ipv4.ip_forward': local.ipForwarding ? '1' : '0' 
        },
        routing_protocol,
        interfaces: interfaceConfigs,
        static_routes,
        nat_rules,
        firewall_rules,
        commands,
        auto_cleanup_interfaces: false
      },
    },
  };

  console.log('Generated spec:', JSON.stringify(spec, null, 2));
  return spec;
};

// -------------------------- Enhanced Reducer --------------------------
export const initialLocal = {
  ipForwarding: true,
  interfaces: [],
  routes: [],
  protocol: 'static',
  bgpConfig: { as_number: '65001' },
  ospfConfig: { area_id: '0', router_id: '' },
  ripConfig: { version: '2' },
  natEnabled: false,
  natRules: [],
  firewallRules: [],
  legacyFirewallRules: [], // for backward compatibility
};

export function reducer(state, action) {
  switch (action.type) {
    case 'SET_ALL':
      return { ...state, ...action.payload };
    case 'SET_FIELD':
      return { ...state, [action.field]: action.value };
    
    // Interface operations
    case 'IF_SET': {
      const arr = [...state.interfaces];
      if (arr[action.index]) {
        arr[action.index] = { ...arr[action.index], [action.field]: action.value };
      }
      return { ...state, interfaces: arr };
    }
    case 'IF_ADD': {
      const newInterfaceIndex = state.interfaces.length;
      const newInterface = { 
        id: `new-${Date.now()}`, // Use timestamp for new interfaces
        name: `${action.routerId}-eth${newInterfaceIndex}`, 
        ip: '', 
        prefix: DEFAULT_PREFIX,
        operation: 'configure'
      };
      console.log('Adding new interface:', newInterface);
      return {
        ...state,
        interfaces: [...state.interfaces, newInterface]
      };
    }
    case 'IF_RM': {
      console.log('Removing interface at index:', action.index);
      return { 
        ...state, 
        interfaces: state.interfaces.filter((_, idx) => idx !== action.index)
      };
    }
    
    // Route operations
    case 'ROUTE_SET': {
      const arr = [...state.routes];
      if (arr[action.index]) {
        arr[action.index] = { ...arr[action.index], [action.field]: action.value };
      }
      return { ...state, routes: arr };
    }
    case 'ROUTE_ADD':
      return {
        ...state,
        routes: [
          ...state.routes, 
          { 
            id: `route-${Date.now()}`,
            action: 'add', 
            destination: '', 
            gateway: '', 
            interface: '', 
            metric: '',
            operation: 'configure'
          }
        ],
      };
    case 'ROUTE_RM': {
      return { 
        ...state, 
        routes: state.routes.filter((_, idx) => idx !== action.index)
      };
    }
    
    // NAT rule operations
    case 'NAT_SET': {
      const arr = [...(state.natRules || [])];
      if (arr[action.index]) {
        arr[action.index] = { ...arr[action.index], [action.field]: action.value };
      }
      return { ...state, natRules: arr };
    }
    case 'NAT_ADD':
      return { 
        ...state, 
        natRules: [
          ...(state.natRules || []), 
          { 
            id: `nat-${Date.now()}`,
            type: 'masquerade',
            chain: 'POSTROUTING',
            source: '',
            destination: '',
            out_interface: '',
            target: 'MASQUERADE',
            operation: 'configure'
          }
        ] 
      };
    case 'NAT_RM': {
      return { 
        ...state, 
        natRules: (state.natRules || []).filter((_, idx) => idx !== action.index)
      };
    }
    
    // Firewall rule operations
    case 'FW_SET': {
      const arr = [...(state.firewallRules || [])];
      if (arr[action.index]) {
        arr[action.index] = { ...arr[action.index], [action.field]: action.value };
      }
      return { ...state, firewallRules: arr };
    }
    case 'FW_ADD':
      return { 
        ...state, 
        firewallRules: [
          ...(state.firewallRules || []), 
          { 
            id: `fw-${Date.now()}`,
            chain: 'INPUT',
            protocol: 'tcp',
            source: '0.0.0.0/0',
            destination: '0.0.0.0/0',
            sport: '',
            dport: '',
            target: 'ACCEPT',
            operation: 'configure'
          }
        ] 
      };
    case 'FW_RM': {
      return { 
        ...state, 
        firewallRules: (state.firewallRules || []).filter((_, idx) => idx !== action.index)
      };
    }
    
    // Legacy firewall rule operations (backward compatibility)
    case 'LEGACY_FW_SET': {
      const arr = [...(state.legacyFirewallRules || [])];
      if (arr[action.index]) {
        arr[action.index] = { ...arr[action.index], [action.field]: action.value };
      }
      return { ...state, legacyFirewallRules: arr };
    }
    case 'LEGACY_FW_ADD':
      return { 
        ...state, 
        legacyFirewallRules: [
          ...(state.legacyFirewallRules || []), 
          { 
            action: '-A', 
            chain: 'INPUT', 
            parameters: '' 
          }
        ] 
      };
    case 'LEGACY_FW_RM':
      return { 
        ...state, 
        legacyFirewallRules: (state.legacyFirewallRules || []).filter((_, idx) => idx !== action.index)
      };
    
    default:
      return state;
  }
}

// Validation helpers
export const validateConfiguration = (local, selectedNode) => {
  const errors = [];
  
  if (!selectedNode?.id) {
    errors.push('No router selected');
    return errors;
  }
  
  // Validate interfaces
  const interfaces = local.interfaces || [];
  const activeInterfaces = interfaces.filter(intf => intf.operation !== 'delete');
  
  activeInterfaces.forEach((intf, index) => {
    if (!intf.name || !intf.name.trim()) {
      errors.push(`Interface ${index + 1}: Name is required`);
    }
    
    // Check for duplicate interface names
    const duplicates = activeInterfaces.filter(other => 
      other.name && intf.name && other.name.trim() === intf.name.trim()
    );
    if (duplicates.length > 1) {
      errors.push(`Interface ${index + 1}: Duplicate interface name "${intf.name}"`);
    }
    
    if (intf.ip && intf.ip.trim()) {
      // Basic IP validation
      const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
      if (!ipRegex.test(intf.ip.trim())) {
        errors.push(`Interface ${index + 1}: Invalid IP address format`);
      } else {
        // Check IP address ranges
        const parts = intf.ip.trim().split('.');
        const invalidPart = parts.find(part => {
          const num = parseInt(part, 10);
          return num < 0 || num > 255;
        });
        if (invalidPart) {
          errors.push(`Interface ${index + 1}: IP address octet out of range (0-255)`);
        }
      }
    }
    
    if (intf.prefix) {
      const prefix = Number(intf.prefix);
      if (isNaN(prefix) || prefix < 0 || prefix > 32) {
        errors.push(`Interface ${index + 1}: Invalid prefix length (must be 0-32)`);
      }
    }
  });
  
  // Validate routes
  const routes = local.routes || [];
  routes.forEach((route, index) => {
    if (route.operation === 'delete') return; // Skip validation for deleted routes
    
    if (!route.destination || !route.destination.trim()) {
      errors.push(`Route ${index + 1}: Destination is required`);
    }
    
    if (route.metric !== undefined && route.metric !== '') {
      const metric = Number(route.metric);
      if (isNaN(metric) || metric < 0) {
        errors.push(`Route ${index + 1}: Invalid metric value`);
      }
    }
  });
  
  // Validate NAT rules
  const natRules = local.natRules || [];
  natRules.forEach((rule, index) => {
    if (rule.operation === 'delete') return;
    
    if (!rule.target || !rule.target.trim()) {
      errors.push(`NAT rule ${index + 1}: Target is required`);
    }
  });
  
  // Validate firewall rules
  const firewallRules = local.firewallRules || [];
  firewallRules.forEach((rule, index) => {
    if (rule.operation === 'delete') return;
    
    if (!rule.target || !rule.target.trim()) {
      errors.push(`Firewall rule ${index + 1}: Target is required`);
    }
  });
  
  // Validate legacy firewall rules
  const legacyFirewallRules = local.legacyFirewallRules || [];
  legacyFirewallRules.forEach((rule, index) => {
    if (!rule.parameters || !rule.parameters.trim()) {
      errors.push(`Legacy firewall rule ${index + 1}: Parameters are required`);
    }
  });
  
  return errors;
};