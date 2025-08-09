import React, { useState, useEffect, useCallback } from 'react';
import {
  Settings,
  Router,
  Server,
  Monitor,
  Save,
  Download,
  Upload,
  RefreshCw,
  Activity,
  ChevronDown,
  ChevronRight,
  Plus,
  Trash2,
  Copy,
  Terminal,
  Network,
  Shield,
  Globe,
  Wifi,
  Code,
  FileText,
  CheckCircle,
  XCircle,
  AlertCircle,
  Eye,
  Info,
  Play,
  Square,
  RotateCcw,
  Layers
} from 'lucide-react';

const NetworkConfigurationManager = ({ 
  networkStatus = { running: false },
  controllerStatus = { running: false },
  topology = { nodes: [], links: [], stats: {} },
  selectedNode = null,
  activeTab = 'overview',
  isModal = false,
  compactMode = false,
  hideHeader = false,
  onNetworkChange,
  onClose,
  onNodeSelect,
  onTabChange
}) => {
  // State management
  const [currentTab, setCurrentTab] = useState(activeTab);
  const [currentSelectedNode, setCurrentSelectedNode] = useState(selectedNode);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [expandedSections, setExpandedSections] = useState({
    hostNetwork: true,
    hostDNS: false,
    hostServices: false,
    hostRoutes: false,
    switchOpenFlow: true,
    switchController: false,
    switchFlows: false,
    routerInterfaces: true,
    routerProtocol: false,
    routerStaticRoutes: false,
    routerNAT: false,
    routerFirewall: false,
    controllerType: true,
    controllerAPI: false,
    controllerStatus: false
  });
  
  // Configuration states
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

  // Terminal and command history
  const [commandHistory, setCommandHistory] = useState([]);
  const [commandOutput, setCommandOutput] = useState('');
  const [currentCommand, setCurrentCommand] = useState('');

  // Constants
  const controllerTypes = [
    { id: 'simple_switch_13', name: 'Simple Switch (OpenFlow 1.3)', description: 'Basic L2 learning switch' },
    { id: 'hub', name: 'Hub', description: 'Simple hub that floods all packets' },
    { id: 'rest_router', name: 'REST Router', description: 'L3 router with REST API' },
    { id: 'rest_firewall', name: 'REST Firewall', description: 'Firewall with REST API' },
    { id: 'simple_switch_lacp', name: 'LACP Switch', description: 'Switch with Link Aggregation' },
    { id: 'custom', name: 'Custom', description: 'Custom controller application' }
  ];

  const routingProtocols = [
    { id: 'static', name: 'Static Routing', description: 'Manual route configuration' },
    { id: 'rip', name: 'RIP', description: 'Routing Information Protocol' },
    { id: 'ospf', name: 'OSPF', description: 'Open Shortest Path First' },
    { id: 'bgp', name: 'BGP', description: 'Border Gateway Protocol' }
  ];

  const commonServices = [
    'ssh', 'http', 'https', 'ftp', 'telnet', 'snmp', 'ntp', 'dhcp', 'dns'
  ];

  const bandwidthOptions = [
    '10M', '100M', '1G', '10G', '40G', '100G'
  ];

  // API functions
  const apiCall = useCallback(async (endpoint, options = {}) => {
    try {
      const response = await fetch(`/api${endpoint}`, {
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
  }, []);

  // Utility functions
  const showMessage = useCallback((text, type = 'info') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(''), 5000);
  }, []);

  const toggleSection = useCallback((section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  }, []);

  const handleTabChange = useCallback((tab) => {
    setCurrentTab(tab);
    if (onTabChange) onTabChange(tab);
  }, [onTabChange]);

  const handleNodeSelect = useCallback((node) => {
    setCurrentSelectedNode(node);
    if (onNodeSelect) onNodeSelect(node);
    
    // Auto-switch to appropriate tab based on node type
    if (node) {
      if (node.type === 'host') handleTabChange('host');
      else if (node.type === 'switch') handleTabChange('switch');
      else if (node.type === 'router') handleTabChange('router');
      else if (node.type === 'controller') handleTabChange('controller');
    }
  }, [onNodeSelect, handleTabChange]);

  // Command execution
  const executeCommand = useCallback(async (nodeId, command) => {
    if (!command.trim()) return;
    
    setLoading(true);
    try {
      const result = await apiCall(`/network/hosts/${nodeId}/cmd`, {
        method: 'POST',
        body: JSON.stringify({ command })
      });

      const entry = {
        timestamp: new Date().toISOString(),
        node: nodeId,
        command,
        result: result.result || result.error,
        success: result.success
      };

      setCommandHistory(prev => [entry, ...prev.slice(0, 99)]);
      setCommandOutput(prev => 
        `[${new Date().toLocaleTimeString()}] ${nodeId}$ ${command}\n${result.result || result.error}\n\n${prev}`
      );

      showMessage(
        result.success ? 'Command executed successfully' : result.error,
        result.success ? 'success' : 'error'
      );

      if (onNetworkChange) onNetworkChange();
    } catch (error) {
      showMessage(`Error executing command: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [apiCall, showMessage, onNetworkChange]);

  // Configuration application functions
  const applyHostConfiguration = useCallback(async () => {
    if (!currentSelectedNode || currentSelectedNode.type !== 'host') return;
    
    setLoading(true);
    try {
      const commands = [];

      if (hostConfig.ip) {
        commands.push(`ifconfig ${currentSelectedNode.id}-eth0 ${hostConfig.ip} netmask ${hostConfig.netmask}`);
      }
      if (hostConfig.gateway) {
        commands.push(`route add default gw ${hostConfig.gateway}`);
      }
      if (hostConfig.hostname) {
        commands.push(`hostname ${hostConfig.hostname}`);
      }
      if (hostConfig.dns.length > 0) {
        const dnsConfig = hostConfig.dns.map(dns => `nameserver ${dns}`).join('\\n');
        commands.push(`echo "${dnsConfig}" > /etc/resolv.conf`);
      }

      hostConfig.routes.forEach(route => {
        if (route.network && route.gateway) {
          commands.push(`route add -net ${route.network} gw ${route.gateway}`);
        }
      });

      for (const command of commands) {
        await executeCommand(currentSelectedNode.id, command);
      }

      showMessage('Host configuration applied successfully', 'success');
    } catch (error) {
      showMessage(`Error applying host configuration: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [currentSelectedNode, hostConfig, executeCommand, showMessage]);

  const applySwitchConfiguration = useCallback(async () => {
    if (!currentSelectedNode || currentSelectedNode.type !== 'switch') return;
    
    setLoading(true);
    try {
      const commands = [];

      // Configure OpenFlow version
      commands.push(`ovs-vsctl set bridge ${currentSelectedNode.id} protocols=OpenFlow${switchConfig.openflow_version.replace('.', '')}`);
      
      // Configure controller
      commands.push(`ovs-vsctl set-controller ${currentSelectedNode.id} tcp:${switchConfig.controller_ip}:${switchConfig.controller_port}`);
      
      // Configure fail mode
      commands.push(`ovs-vsctl set-fail-mode ${currentSelectedNode.id} ${switchConfig.fail_mode}`);
      
      // Configure DPID if specified
      if (switchConfig.dpid) {
        commands.push(`ovs-vsctl set bridge ${currentSelectedNode.id} other-config:datapath-id=${switchConfig.dpid}`);
      }

      for (const command of commands) {
        await executeCommand(currentSelectedNode.id, command);
      }

      showMessage('Switch configuration applied successfully', 'success');
    } catch (error) {
      showMessage(`Error applying switch configuration: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [currentSelectedNode, switchConfig, executeCommand, showMessage]);

  const applyRouterConfiguration = useCallback(async () => {
    if (!currentSelectedNode || currentSelectedNode.type !== 'router') return;
    
    setLoading(true);
    try {
      const commands = [];

      // Enable IP forwarding
      commands.push('echo 1 > /proc/sys/net/ipv4/ip_forward');

      // Configure interfaces
      routerConfig.interfaces.forEach((intf, index) => {
        if (intf.ip && intf.netmask) {
          commands.push(`ifconfig ${currentSelectedNode.id}-eth${index} ${intf.ip} netmask ${intf.netmask}`);
        }
      });

      // Add static routes
      routerConfig.static_routes.forEach(route => {
        if (route.network && route.gateway && route.interface) {
          commands.push(`route add -net ${route.network} gw ${route.gateway} dev ${route.interface}`);
        }
      });

      // Configure NAT if enabled
      if (routerConfig.nat_enabled) {
        commands.push('iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE');
        commands.push('iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT');
        commands.push('iptables -A FORWARD -i eth0 -o eth1 -m state --state RELATED,ESTABLISHED -j ACCEPT');
      }

      // Apply firewall rules
      routerConfig.firewall_rules.forEach(rule => {
        if (rule.action && rule.chain && rule.parameters) {
          commands.push(`iptables ${rule.action} ${rule.chain} ${rule.parameters}`);
        }
      });

      for (const command of commands) {
        await executeCommand(currentSelectedNode.id, command);
      }

      showMessage('Router configuration applied successfully', 'success');
    } catch (error) {
      showMessage(`Error applying router configuration: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [currentSelectedNode, routerConfig, executeCommand, showMessage]);

  const applyControllerConfiguration = useCallback(async () => {
    setLoading(true);
    try {
      await apiCall('/controller/config', {
        method: 'POST',
        body: JSON.stringify(controllerConfig)
      });

      showMessage('Controller configuration applied successfully', 'success');
      if (onNetworkChange) onNetworkChange();
    } catch (error) {
      showMessage(`Error applying controller configuration: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [controllerConfig, apiCall, showMessage, onNetworkChange]);

  // Controller management functions
  const startController = useCallback(async () => {
    setLoading(true);
    try {
      await apiCall('/controller/start', {
        method: 'POST',
        body: JSON.stringify({ 
          type: controllerConfig.type, 
          port: controllerConfig.port 
        })
      });

      showMessage('Controller started successfully', 'success');
      if (onNetworkChange) onNetworkChange();
    } catch (error) {
      showMessage(`Error starting controller: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [controllerConfig, apiCall, showMessage, onNetworkChange]);

  const stopController = useCallback(async () => {
    setLoading(true);
    try {
      await apiCall('/controller/stop', { method: 'POST' });
      showMessage('Controller stopped successfully', 'success');
      if (onNetworkChange) onNetworkChange();
    } catch (error) {
      showMessage(`Error stopping controller: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [apiCall, showMessage, onNetworkChange]);

  const restartController = useCallback(async () => {
    setLoading(true);
    try {
      await apiCall('/controller/restart', { method: 'POST' });
      showMessage('Controller restarted successfully', 'success');
      if (onNetworkChange) onNetworkChange();
    } catch (error) {
      showMessage(`Error restarting controller: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [apiCall, showMessage, onNetworkChange]);

  // Export/Import functions
  const exportConfiguration = useCallback(() => {
    const config = {
      host: hostConfig,
      switch: switchConfig,
      router: routerConfig,
      controller: controllerConfig,
      selectedNode: currentSelectedNode?.id,
      timestamp: new Date().toISOString()
    };

    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `network-config-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [hostConfig, switchConfig, routerConfig, controllerConfig, currentSelectedNode]);

  const importConfiguration = useCallback((event) => {
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
  }, [hostConfig, switchConfig, routerConfig, controllerConfig, showMessage]);

  // Effect hooks
  useEffect(() => {
    if (selectedNode !== currentSelectedNode) {
      setCurrentSelectedNode(selectedNode);
    }
  }, [selectedNode, currentSelectedNode]);

  useEffect(() => {
    if (activeTab !== currentTab) {
      setCurrentTab(activeTab);
    }
  }, [activeTab, currentTab]);

  // Load node-specific configuration when node is selected
  useEffect(() => {
    if (currentSelectedNode) {
      // Initialize configurations based on node type and existing data
      if (currentSelectedNode.type === 'host') {
        setHostConfig(prev => ({
          ...prev,
          ip: currentSelectedNode.ip || '',
          hostname: currentSelectedNode.id || ''
        }));
      }
    }
  }, [currentSelectedNode]);

  // Components
  const TabButton = ({ id, label, icon: Icon, active, onClick }) => (
    <button
      onClick={() => onClick(id)}
      className={`flex items-center gap-2 px-4 py-3 font-medium transition-all duration-200 border-b-2 ${
        active 
          ? 'border-blue-600 text-blue-600 bg-blue-50' 
          : 'border-transparent text-gray-600 hover:text-gray-800 hover:border-gray-300'
      }`}
    >
      <Icon size={18} />
      {label}
    </button>
  );

  const StatusBadge = ({ status, label }) => (
    <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${
      status ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
    }`}>
      {status ? <CheckCircle size={16} /> : <AlertCircle size={16} />}
      {label}: {status ? 'Running' : 'Stopped'}
    </div>
  );

  const ConfigSection = ({ title, icon: Icon, children, expanded, onToggle, actions }) => (
    <div className="bg-white rounded-lg border border-gray-200 mb-4">
      <div 
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          <Icon className="text-blue-600" size={20} />
          <h3 className="font-semibold text-gray-800">{title}</h3>
        </div>
        <div className="flex items-center gap-2">
          {actions}
          {expanded ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
        </div>
      </div>
      {expanded && (
        <div className="p-4 border-t border-gray-200">
          {children}
        </div>
      )}
    </div>
  );

  const NodeCard = ({ node, onSelect, selected }) => (
    <div 
      className={`p-4 border rounded-lg cursor-pointer transition-all duration-200 ${
        selected 
          ? 'border-blue-500 bg-blue-50 shadow-md' 
          : 'border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm'
      }`}
      onClick={() => onSelect(node)}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {node.type === 'host' && <Monitor size={20} className="text-blue-600" />}
          {node.type === 'router' && <Router size={20} className="text-green-600" />}
          {node.type === 'switch' && <Server size={20} className="text-purple-600" />}
          {node.type === 'controller' && <Settings size={20} className="text-red-600" />}
          <span className="font-semibold">{node.id}</span>
        </div>
        <span className={`px-2 py-1 rounded text-xs font-medium ${
          node.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
        }`}>
          {node.type}
        </span>
      </div>
      
      {node.ip && (
        <div className="text-sm text-gray-600 mb-1">
          <strong>IP:</strong> {node.ip}
        </div>
      )}
      
      {node.mac && node.mac !== 'N/A' && node.mac !== 'auto' && (
        <div className="text-sm text-gray-600">
          <strong>MAC:</strong> {node.mac}
        </div>
      )}
    </div>
  );

  return (
    <div className={`${isModal ? 'h-full' : 'max-w-7xl mx-auto p-6 bg-gray-50 min-h-screen'}`}>
      {/* Header */}
      {!hideHeader && (
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2 flex items-center gap-3">
            <Settings className="text-blue-600" size={32} />
            Network Configuration Manager
          </h1>
          <p className="text-gray-600">Configure and manage your SDN network components</p>
        </div>
      )}

      {/* Status Bar */}
      <div className={`mb-6 p-4 bg-white rounded-lg shadow-sm border border-gray-200 ${compactMode ? 'text-sm' : ''}`}>
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex gap-4">
            <StatusBadge status={networkStatus.running} label="Network" />
            <StatusBadge status={controllerStatus.running} label="Controller" />
          </div>
          <div className="flex gap-2">
            <button
              onClick={exportConfiguration}
              className="flex items-center gap-2 px-3 py-2 bg-green-100 text-green-700 rounded-lg hover:bg-green-200 transition-colors"
            >
              <Download size={16} />
              Export Config
            </button>
            <label className="flex items-center gap-2 px-3 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors cursor-pointer">
              <Upload size={16} />
              Import Config
              <input
                type="file"
                accept=".json"
                onChange={importConfiguration}
                className="hidden"
              />
            </label>
            <button
              onClick={() => onNetworkChange && onNetworkChange()}
              className="flex items-center gap-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              <RefreshCw size={16} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Message Display */}
      {message && (
        <div className={`mb-4 p-3 rounded-lg ${
          message.type === 'success' ? 'bg-green-100 text-green-800 border border-green-200' :
          message.type === 'error' ? 'bg-red-100 text-red-800 border border-red-200' :
          'bg-blue-100 text-blue-800 border border-blue-200'
        }`}>
          {message.text}
        </div>
      )}

      {/* Tab Navigation */}
      <div className="mb-6">
        <div className="flex border-b border-gray-200 bg-white rounded-t-lg overflow-x-auto">
          <TabButton 
            id="overview" 
            label="Overview" 
            icon={Activity} 
            active={currentTab === 'overview'} 
            onClick={handleTabChange} 
          />
          <TabButton 
            id="host" 
            label="Host Config" 
            icon={Monitor} 
            active={currentTab === 'host'} 
            onClick={handleTabChange} 
          />
          <TabButton 
            id="switch" 
            label="Switch Config" 
            icon={Server} 
            active={currentTab === 'switch'} 
            onClick={handleTabChange} 
          />
          <TabButton 
            id="router" 
            label="Router Config" 
            icon={Router} 
            active={currentTab === 'router'} 
            onClick={handleTabChange} 
          />
          <TabButton 
            id="controller" 
            label="Controller Config" 
            icon={Settings} 
            active={currentTab === 'controller'} 
            onClick={handleTabChange} 
          />
          <TabButton 
            id="terminal" 
            label="Terminal" 
            icon={Terminal} 
            active={currentTab === 'terminal'} 
            onClick={handleTabChange} 
          />
        </div>
      </div>

      {/* Tab Content */}
      <div className="bg-white rounded-b-lg border border-gray-200 min-h-96">
        {/* Overview Tab */}
        {currentTab === 'overview' && (
          <div className="p-6">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Node Selection */}
              <div className="lg:col-span-2">
                <h2 className="text-xl font-semibold mb-4">Select Node to Configure</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {topology.nodes.map(node => (
                    <NodeCard
                      key={node.id}
                      node={node}
                      onSelect={handleNodeSelect}
                      selected={currentSelectedNode?.id === node.id}
                    />
                  ))}
                </div>
              </div>

              {/* Selected Node Info */}
              <div>
                <h2 className="text-xl font-semibold mb-4">Node Information</h2>
                {currentSelectedNode ? (
                  <div className="bg-gray-50 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-3">
                      {currentSelectedNode.type === 'host' && <Monitor className="text-blue-600" />}
                      {currentSelectedNode.type === 'router' && <Router className="text-green-600" />}
                      {currentSelectedNode.type === 'switch' && <Server className="text-purple-600" />}
                      {currentSelectedNode.type === 'controller' && <Settings className="text-red-600" />}
                      <span className="font-semibold text-lg">{currentSelectedNode.id}</span>
                    </div>
                    
                    <div className="space-y-2 text-sm">
                      <div>
                        <strong>Type:</strong> {currentSelectedNode.type}
                      </div>
                      <div>
                        <strong>Status:</strong> 
                        <span className={`ml-2 px-2 py-1 rounded text-xs ${
                          currentSelectedNode.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-600'
                        }`}>
                          {currentSelectedNode.status}
                        </span>
                      </div>
                      {currentSelectedNode.ip && (
                        <div><strong>IP:</strong> {currentSelectedNode.ip}</div>
                      )}
                      {currentSelectedNode.mac && currentSelectedNode.mac !== 'N/A' && currentSelectedNode.mac !== 'auto' && (
                        <div><strong>MAC:</strong> {currentSelectedNode.mac}</div>
                      )}
                      {currentSelectedNode.interfaces && (
                        <div>
                          <strong>Interfaces:</strong>
                          <ul className="mt-1 ml-4">
                            {currentSelectedNode.interfaces.map((intf, index) => (
                              <li key={index} className="text-xs">
                                {intf.name}: {intf.ip}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>

                    <div className="mt-4 pt-4 border-t border-gray-300">
                      <p className="text-xs text-gray-600">
                        Select the appropriate configuration tab to configure this {currentSelectedNode.type}.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="bg-gray-50 rounded-lg p-4 text-center text-gray-500">
                    <Settings className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                    <p>Select a node to view information and configure it</p>
                  </div>
                )}

                {/* Network Summary */}
                <div className="mt-6 bg-gray-50 rounded-lg p-4">
                  <h3 className="font-semibold mb-3">Network Summary</h3>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Hosts:</span>
                      <span className="font-mono">{topology.stats.hosts || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Switches:</span>
                      <span className="font-mono">{topology.stats.switches || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Routers:</span>
                      <span className="font-mono">{topology.stats.routers || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Links:</span>
                      <span className="font-mono">{topology.stats.links || 0}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Host Configuration Tab */}
        {currentTab === 'host' && (
          <div className="p-6">
            {!currentSelectedNode || currentSelectedNode.type !== 'host' ? (
              <div className="text-center text-gray-500 py-12">
                <Monitor className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <h3 className="text-xl font-semibold mb-2">No Host Selected</h3>
                <p>Please select a host from the Overview tab to configure it.</p>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold">Configure Host: {currentSelectedNode.id}</h2>
                  <button
                    onClick={applyHostConfiguration}
                    disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    <Save size={16} />
                    Apply Configuration
                  </button>
                </div>

                {/* Network Interface Configuration */}
                <ConfigSection
                  title="Network Interface"
                  icon={Wifi}
                  expanded={expandedSections.hostNetwork}
                  onToggle={() => toggleSection('hostNetwork')}
                >
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        IP Address
                      </label>
                      <input
                        type="text"
                        value={hostConfig.ip}
                        onChange={(e) => setHostConfig({...hostConfig, ip: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="10.0.0.1"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Netmask
                      </label>
                      <select
                        value={hostConfig.netmask}
                        onChange={(e) => setHostConfig({...hostConfig, netmask: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="255.255.255.0">255.255.255.0 (/24)</option>
                        <option value="255.255.0.0">255.255.0.0 (/16)</option>
                        <option value="255.0.0.0">255.0.0.0 (/8)</option>
                        <option value="255.255.255.128">255.255.255.128 (/25)</option>
                        <option value="255.255.255.192">255.255.255.192 (/26)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Default Gateway
                      </label>
                      <input
                        type="text"
                        value={hostConfig.gateway}
                        onChange={(e) => setHostConfig({...hostConfig, gateway: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="10.0.0.1"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Hostname
                      </label>
                      <input
                        type="text"
                        value={hostConfig.hostname}
                        onChange={(e) => setHostConfig({...hostConfig, hostname: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="host1"
                      />
                    </div>
                  </div>
                </ConfigSection>

                {/* DNS Configuration */}
                <ConfigSection
                  title="DNS Configuration"
                  icon={Globe}
                  expanded={expandedSections.hostDNS}
                  onToggle={() => toggleSection('hostDNS')}
                >
                  <div className="space-y-4">
                    {hostConfig.dns.map((dns, index) => (
                      <div key={index} className="flex items-center gap-2">
                        <input
                          type="text"
                          value={dns}
                          onChange={(e) => {
                            const newDns = [...hostConfig.dns];
                            newDns[index] = e.target.value;
                            setHostConfig({...hostConfig, dns: newDns});
                          }}
                          className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="8.8.8.8"
                        />
                        <button
                          onClick={() => {
                            const newDns = hostConfig.dns.filter((_, i) => i !== index);
                            setHostConfig({...hostConfig, dns: newDns});
                          }}
                          className="text-red-600 hover:text-red-800 transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => setHostConfig({...hostConfig, dns: [...hostConfig.dns, '']})}
                      className="flex items-center gap-2 px-3 py-2 border-2 border-dashed border-gray-300 rounded-md text-gray-600 hover:border-gray-400 transition-colors"
                    >
                      <Plus size={16} />
                      Add DNS Server
                    </button>
                  </div>
                </ConfigSection>

                {/* Services Configuration */}
                <ConfigSection
                  title="Services"
                  icon={Activity}
                  expanded={expandedSections.hostServices}
                  onToggle={() => toggleSection('hostServices')}
                >
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    {commonServices.map(service => (
                      <label key={service} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={hostConfig.services.includes(service)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setHostConfig({...hostConfig, services: [...hostConfig.services, service]});
                            } else {
                              setHostConfig({...hostConfig, services: hostConfig.services.filter(s => s !== service)});
                            }
                          }}
                          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        />
                        <span className="text-sm">{service.toUpperCase()}</span>
                      </label>
                    ))}
                  </div>
                </ConfigSection>

                {/* Static Routes */}
                <ConfigSection
                  title="Static Routes"
                  icon={Network}
                  expanded={expandedSections.hostRoutes}
                  onToggle={() => toggleSection('hostRoutes')}
                >
                  <div className="space-y-4">
                    {hostConfig.routes.map((route, index) => (
                      <div key={index} className="grid grid-cols-1 md:grid-cols-3 gap-3 p-3 border border-gray-200 rounded-lg">
                        <input
                          type="text"
                          value={route.network || ''}
                          onChange={(e) => {
                            const newRoutes = [...hostConfig.routes];
                            newRoutes[index] = {...newRoutes[index], network: e.target.value};
                            setHostConfig({...hostConfig, routes: newRoutes});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="192.168.1.0/24"
                        />
                        <input
                          type="text"
                          value={route.gateway || ''}
                          onChange={(e) => {
                            const newRoutes = [...hostConfig.routes];
                            newRoutes[index] = {...newRoutes[index], gateway: e.target.value};
                            setHostConfig({...hostConfig, routes: newRoutes});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="192.168.1.1"
                        />
                        <button
                          onClick={() => {
                            const newRoutes = hostConfig.routes.filter((_, i) => i !== index);
                            setHostConfig({...hostConfig, routes: newRoutes});
                          }}
                          className="flex items-center justify-center text-red-600 hover:text-red-800 transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => setHostConfig({...hostConfig, routes: [...hostConfig.routes, {network: '', gateway: ''}]})}
                      className="flex items-center gap-2 px-3 py-2 border-2 border-dashed border-gray-300 rounded-md text-gray-600 hover:border-gray-400 transition-colors"
                    >
                      <Plus size={16} />
                      Add Static Route
                    </button>
                  </div>
                </ConfigSection>
              </div>
            )}
          </div>
        )}

        {/* Switch Configuration Tab */}
        {currentTab === 'switch' && (
          <div className="p-6">
            {!currentSelectedNode || currentSelectedNode.type !== 'switch' ? (
              <div className="text-center text-gray-500 py-12">
                <Server className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <h3 className="text-xl font-semibold mb-2">No Switch Selected</h3>
                <p>Please select a switch from the Overview tab to configure it.</p>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold">Configure Switch: {currentSelectedNode.id}</h2>
                  <button
                    onClick={applySwitchConfiguration}
                    disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    <Save size={16} />
                    Apply Configuration
                  </button>
                </div>

                {/* OpenFlow Configuration */}
                <ConfigSection
                  title="OpenFlow Configuration"
                  icon={Network}
                  expanded={expandedSections.switchOpenFlow}
                  onToggle={() => toggleSection('switchOpenFlow')}
                >
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        OpenFlow Version
                      </label>
                      <select
                        value={switchConfig.openflow_version}
                        onChange={(e) => setSwitchConfig({...switchConfig, openflow_version: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="1.0">OpenFlow 1.0</option>
                        <option value="1.1">OpenFlow 1.1</option>
                        <option value="1.2">OpenFlow 1.2</option>
                        <option value="1.3">OpenFlow 1.3</option>
                        <option value="1.4">OpenFlow 1.4</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Fail Mode
                      </label>
                      <select
                        value={switchConfig.fail_mode}
                        onChange={(e) => setSwitchConfig({...switchConfig, fail_mode: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="secure">Secure (Drop packets)</option>
                        <option value="standalone">Standalone (Act as switch)</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        DPID (Optional)
                      </label>
                      <input
                        type="text"
                        value={switchConfig.dpid}
                        onChange={(e) => setSwitchConfig({...switchConfig, dpid: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="0000000000000001"
                      />
                    </div>
                  </div>
                </ConfigSection>

                {/* Controller Configuration */}
                <ConfigSection
                  title="Controller Settings"
                  icon={Settings}
                  expanded={expandedSections.switchController}
                  onToggle={() => toggleSection('switchController')}
                >
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Controller IP
                      </label>
                      <input
                        type="text"
                        value={switchConfig.controller_ip}
                        onChange={(e) => setSwitchConfig({...switchConfig, controller_ip: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="127.0.0.1"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Controller Port
                      </label>
                      <input
                        type="number"
                        value={switchConfig.controller_port}
                        onChange={(e) => setSwitchConfig({...switchConfig, controller_port: parseInt(e.target.value)})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="6633"
                      />
                    </div>
                  </div>
                </ConfigSection>

                {/* Flow Tables */}
                <ConfigSection
                  title="Flow Tables"
                  icon={FileText}
                  expanded={expandedSections.switchFlows}
                  onToggle={() => toggleSection('switchFlows')}
                >
                  <div className="space-y-4">
                    <div className="text-sm text-gray-600">
                      Flow table configuration is managed by the controller. Use the terminal to manually add flows if needed.
                    </div>
                    <button
                      onClick={() => executeCommand(currentSelectedNode.id, `ovs-ofctl dump-flows ${currentSelectedNode.id}`)}
                      className="flex items-center gap-2 px-3 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
                    >
                      <Eye size={16} />
                      View Current Flows
                    </button>
                  </div>
                </ConfigSection>
              </div>
            )}
          </div>
        )}

        {/* Router Configuration Tab */}
        {currentTab === 'router' && (
          <div className="p-6">
            {!currentSelectedNode || currentSelectedNode.type !== 'router' ? (
              <div className="text-center text-gray-500 py-12">
                <Router className="w-16 h-16 mx-auto mb-4 text-gray-300" />
                <h3 className="text-xl font-semibold mb-2">No Router Selected</h3>
                <p>Please select a router from the Overview tab to configure it.</p>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h2 className="text-xl font-semibold">Configure Router: {currentSelectedNode.id}</h2>
                  <button
                    onClick={applyRouterConfiguration}
                    disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    <Save size={16} />
                    Apply Configuration
                  </button>
                </div>

                {/* Interface Configuration */}
                <ConfigSection
                  title="Interface Configuration"
                  icon={Wifi}
                  expanded={expandedSections.routerInterfaces}
                  onToggle={() => toggleSection('routerInterfaces')}
                >
                  <div className="space-y-4">
                    {routerConfig.interfaces.map((intf, index) => (
                      <div key={index} className="grid grid-cols-1 md:grid-cols-4 gap-3 p-3 border border-gray-200 rounded-lg">
                        <input
                          type="text"
                          value={intf.name || `eth${index}`}
                          onChange={(e) => {
                            const newInterfaces = [...routerConfig.interfaces];
                            newInterfaces[index] = {...newInterfaces[index], name: e.target.value};
                            setRouterConfig({...routerConfig, interfaces: newInterfaces});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="eth0"
                        />
                        <input
                          type="text"
                          value={intf.ip || ''}
                          onChange={(e) => {
                            const newInterfaces = [...routerConfig.interfaces];
                            newInterfaces[index] = {...newInterfaces[index], ip: e.target.value};
                            setRouterConfig({...routerConfig, interfaces: newInterfaces});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="10.0.1.1"
                        />
                        <input
                          type="text"
                          value={intf.netmask || ''}
                          onChange={(e) => {
                            const newInterfaces = [...routerConfig.interfaces];
                            newInterfaces[index] = {...newInterfaces[index], netmask: e.target.value};
                            setRouterConfig({...routerConfig, interfaces: newInterfaces});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="255.255.255.0"
                        />
                        <button
                          onClick={() => {
                            const newInterfaces = routerConfig.interfaces.filter((_, i) => i !== index);
                            setRouterConfig({...routerConfig, interfaces: newInterfaces});
                          }}
                          className="flex items-center justify-center text-red-600 hover:text-red-800 transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => setRouterConfig({...routerConfig, interfaces: [...routerConfig.interfaces, {name: '', ip: '', netmask: ''}]})}
                      className="flex items-center gap-2 px-3 py-2 border-2 border-dashed border-gray-300 rounded-md text-gray-600 hover:border-gray-400 transition-colors"
                    >
                      <Plus size={16} />
                      Add Interface
                    </button>
                  </div>
                </ConfigSection>

                {/* Routing Protocol */}
                <ConfigSection
                  title="Routing Protocol"
                  icon={Network}
                  expanded={expandedSections.routerProtocol}
                  onToggle={() => toggleSection('routerProtocol')}
                >
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Routing Protocol
                      </label>
                      <select
                        value={routerConfig.routing_protocol}
                        onChange={(e) => setRouterConfig({...routerConfig, routing_protocol: e.target.value})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        {routingProtocols.map(protocol => (
                          <option key={protocol.id} value={protocol.id}>
                            {protocol.name} - {protocol.description}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </ConfigSection>

                {/* Static Routes */}
                <ConfigSection
                  title="Static Routes"
                  icon={Network}
                  expanded={expandedSections.routerStaticRoutes}
                  onToggle={() => toggleSection('routerStaticRoutes')}
                >
                  <div className="space-y-4">
                    {routerConfig.static_routes.map((route, index) => (
                      <div key={index} className="grid grid-cols-1 md:grid-cols-4 gap-3 p-3 border border-gray-200 rounded-lg">
                        <input
                          type="text"
                          value={route.network || ''}
                          onChange={(e) => {
                            const newRoutes = [...routerConfig.static_routes];
                            newRoutes[index] = {...newRoutes[index], network: e.target.value};
                            setRouterConfig({...routerConfig, static_routes: newRoutes});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="192.168.1.0/24"
                        />
                        <input
                          type="text"
                          value={route.gateway || ''}
                          onChange={(e) => {
                            const newRoutes = [...routerConfig.static_routes];
                            newRoutes[index] = {...newRoutes[index], gateway: e.target.value};
                            setRouterConfig({...routerConfig, static_routes: newRoutes});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="192.168.1.1"
                        />
                        <input
                          type="text"
                          value={route.interface || ''}
                          onChange={(e) => {
                            const newRoutes = [...routerConfig.static_routes];
                            newRoutes[index] = {...newRoutes[index], interface: e.target.value};
                            setRouterConfig({...routerConfig, static_routes: newRoutes});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="eth0"
                        />
                        <button
                          onClick={() => {
                            const newRoutes = routerConfig.static_routes.filter((_, i) => i !== index);
                            setRouterConfig({...routerConfig, static_routes: newRoutes});
                          }}
                          className="flex items-center justify-center text-red-600 hover:text-red-800 transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => setRouterConfig({...routerConfig, static_routes: [...routerConfig.static_routes, {network: '', gateway: '', interface: ''}]})}
                      className="flex items-center gap-2 px-3 py-2 border-2 border-dashed border-gray-300 rounded-md text-gray-600 hover:border-gray-400 transition-colors"
                    >
                      <Plus size={16} />
                      Add Static Route
                    </button>
                  </div>
                </ConfigSection>

                {/* NAT Configuration */}
                <ConfigSection
                  title="NAT Configuration"
                  icon={Shield}
                  expanded={expandedSections.routerNAT}
                  onToggle={() => toggleSection('routerNAT')}
                >
                  <div className="space-y-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={routerConfig.nat_enabled}
                        onChange={(e) => setRouterConfig({...routerConfig, nat_enabled: e.target.checked})}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      <span className="text-sm font-medium">Enable NAT</span>
                    </label>
                    {routerConfig.nat_enabled && (
                      <div className="text-sm text-gray-600 bg-blue-50 p-3 rounded-lg">
                        NAT will be configured automatically with masquerading on eth0 and forwarding rules.
                      </div>
                    )}
                  </div>
                </ConfigSection>

                {/* Firewall Rules */}
                <ConfigSection
                  title="Firewall Rules"
                  icon={Shield}
                  expanded={expandedSections.routerFirewall}
                  onToggle={() => toggleSection('routerFirewall')}
                >
                  <div className="space-y-4">
                    {routerConfig.firewall_rules.map((rule, index) => (
                      <div key={index} className="grid grid-cols-1 md:grid-cols-4 gap-3 p-3 border border-gray-200 rounded-lg">
                        <select
                          value={rule.action || ''}
                          onChange={(e) => {
                            const newRules = [...routerConfig.firewall_rules];
                            newRules[index] = {...newRules[index], action: e.target.value};
                            setRouterConfig({...routerConfig, firewall_rules: newRules});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="">Select Action</option>
                          <option value="-A">Append</option>
                          <option value="-I">Insert</option>
                          <option value="-D">Delete</option>
                        </select>
                        <select
                          value={rule.chain || ''}
                          onChange={(e) => {
                            const newRules = [...routerConfig.firewall_rules];
                            newRules[index] = {...newRules[index], chain: e.target.value};
                            setRouterConfig({...routerConfig, firewall_rules: newRules});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                          <option value="">Select Chain</option>
                          <option value="INPUT">INPUT</option>
                          <option value="OUTPUT">OUTPUT</option>
                          <option value="FORWARD">FORWARD</option>
                        </select>
                        <input
                          type="text"
                          value={rule.parameters || ''}
                          onChange={(e) => {
                            const newRules = [...routerConfig.firewall_rules];
                            newRules[index] = {...newRules[index], parameters: e.target.value};
                            setRouterConfig({...routerConfig, firewall_rules: newRules});
                          }}
                          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                          placeholder="-p tcp --dport 80 -j ACCEPT"
                        />
                        <button
                          onClick={() => {
                            const newRules = routerConfig.firewall_rules.filter((_, i) => i !== index);
                            setRouterConfig({...routerConfig, firewall_rules: newRules});
                          }}
                          className="flex items-center justify-center text-red-600 hover:text-red-800 transition-colors"
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    ))}
                    <button
                      onClick={() => setRouterConfig({...routerConfig, firewall_rules: [...routerConfig.firewall_rules, {action: '', chain: '', parameters: ''}]})}
                      className="flex items-center gap-2 px-3 py-2 border-2 border-dashed border-gray-300 rounded-md text-gray-600 hover:border-gray-400 transition-colors"
                    >
                      <Plus size={16} />
                      Add Firewall Rule
                    </button>
                  </div>
                </ConfigSection>
              </div>
            )}
          </div>
        )}

        {/* Controller Configuration Tab */}
        {currentTab === 'controller' && (
          <div className="p-6">
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Controller Configuration</h2>
                <div className="flex gap-2">
                  <button
                    onClick={applyControllerConfiguration}
                    disabled={loading}
                    className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                  >
                    <Save size={16} />
                    Apply Configuration
                  </button>
                </div>
              </div>

              {/* Controller Type & Settings */}
              <ConfigSection
                title="Controller Type & Settings"
                icon={Settings}
                expanded={expandedSections.controllerType}
                onToggle={() => toggleSection('controllerType')}
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Controller Type
                    </label>
                    <select
                      value={controllerConfig.type}
                      onChange={(e) => setControllerConfig({...controllerConfig, type: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      {controllerTypes.map(type => (
                        <option key={type.id} value={type.id}>
                          {type.name}
                        </option>
                      ))}
                    </select>
                    <p className="text-sm text-gray-500 mt-1">
                      {controllerTypes.find(t => t.id === controllerConfig.type)?.description}
                    </p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Listen Port
                    </label>
                    <input
                      type="number"
                      value={controllerConfig.port}
                      onChange={(e) => setControllerConfig({...controllerConfig, port: parseInt(e.target.value)})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                      min="1024"
                      max="65535"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      IP Address
                    </label>
                    <input
                      type="text"
                      value={controllerConfig.ip}
                      onChange={(e) => setControllerConfig({...controllerConfig, ip: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Log Level
                    </label>
                    <select
                      value={controllerConfig.log_level}
                      onChange={(e) => setControllerConfig({...controllerConfig, log_level: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="DEBUG">DEBUG</option>
                      <option value="INFO">INFO</option>
                      <option value="WARNING">WARNING</option>
                      <option value="ERROR">ERROR</option>
                    </select>
                  </div>
                </div>
              </ConfigSection>

              {/* REST API Configuration */}
              <ConfigSection
                title="REST API Configuration"
                icon={Code}
                expanded={expandedSections.controllerAPI}
                onToggle={() => toggleSection('controllerAPI')}
              >
                <div className="space-y-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={controllerConfig.rest_api_enabled}
                      onChange={(e) => setControllerConfig({...controllerConfig, rest_api_enabled: e.target.checked})}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm font-medium">Enable REST API</span>
                  </label>
                  {controllerConfig.rest_api_enabled && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        REST API Port
                      </label>
                      <input
                        type="number"
                        value={controllerConfig.rest_api_port}
                        onChange={(e) => setControllerConfig({...controllerConfig, rest_api_port: parseInt(e.target.value)})}
                        className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        min="1024"
                        max="65535"
                      />
                    </div>
                  )}
                </div>
              </ConfigSection>

              {/* Controller Status & Management */}
              <ConfigSection
                title="Controller Management"
                icon={Activity}
                expanded={expandedSections.controllerStatus}
                onToggle={() => toggleSection('controllerStatus')}
              >
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-600">Status:</span>
                      <span className={`text-sm font-medium ${controllerStatus.running ? 'text-green-600' : 'text-red-600'}`}>
                        {controllerStatus.running ? 'Running' : 'Stopped'}
                      </span>
                    </div>
                    {controllerStatus.running && (
                      <>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Type:</span>
                          <span className="text-sm font-medium">{controllerStatus.type}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-sm text-gray-600">Port:</span>
                          <span className="text-sm font-medium">{controllerStatus.port}</span>
                        </div>
                        {controllerStatus.pid && (
                          <div className="flex justify-between">
                            <span className="text-sm text-gray-600">PID:</span>
                            <span className="text-sm font-medium">{controllerStatus.pid}</span>
                          </div>
                        )}
                      </>
                    )}
                  </div>
                  <div className="space-y-2">
                    {!controllerStatus.running ? (
                      <button
                        onClick={startController}
                        disabled={loading}
                        className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
                      >
                        <Play size={16} />
                        Start Controller
                      </button>
                    ) : (
                      <div className="space-y-2">
                        <button
                          onClick={stopController}
                          disabled={loading}
                          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
                      >
                          <Square size={16} />
                          Stop Controller
                        </button>
                        <button
                          onClick={restartController}
                          disabled={loading}
                          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 disabled:opacity-50 transition-colors"
                        >
                          <RotateCcw size={16} />
                          Restart Controller
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </ConfigSection>
            </div>
          </div>
        )}

        {/* Terminal Tab */}
        {currentTab === 'terminal' && (
          <div className="p-6">
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold">Network Terminal</h2>
                <div className="flex gap-2">
                  <button
                    onClick={() => setCommandOutput('')}
                    className="flex items-center gap-2 px-3 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors"
                  >
                    <Trash2 size={16} />
                    Clear Output
                  </button>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(commandOutput);
                      showMessage('Output copied to clipboard', 'success');
                    }}
                    className="flex items-center gap-2 px-3 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition-colors"
                  >
                    <Copy size={16} />
                    Copy Output
                  </button>
                </div>
              </div>

              {/* Node Selection for Commands */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-semibold mb-3">Select Target Node</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {topology.nodes.filter(n => n.type !== 'switch').map(node => (
                    <button
                      key={node.id}
                      onClick={() => setCurrentSelectedNode(node)}
                      className={`p-3 rounded-lg border-2 transition-all duration-200 ${
                        currentSelectedNode?.id === node.id
                          ? 'border-blue-500 bg-blue-50 text-blue-700'
                          : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        {node.type === 'host' && <Monitor size={16} />}
                        {node.type === 'router' && <Router size={16} />}
                        {node.type === 'controller' && <Settings size={16} />}
                        <span className="font-medium">{node.id}</span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Command Input */}
              {currentSelectedNode && (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Execute Command on {currentSelectedNode.id}
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={currentCommand}
                        onChange={(e) => setCurrentCommand(e.target.value)}
                        onKeyPress={(e) => {
                          if (e.key === 'Enter' && currentCommand.trim()) {
                            executeCommand(currentSelectedNode.id, currentCommand);
                            setCurrentCommand('');
                          }
                        }}
                        className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                        placeholder="Enter command (e.g., ifconfig, ping, route -n)"
                      />
                      <button
                        onClick={() => {
                          if (currentCommand.trim()) {
                            executeCommand(currentSelectedNode.id, currentCommand);
                            setCurrentCommand('');
                          }
                        }}
                        disabled={loading || !currentCommand.trim()}
                        className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
                      >
                        Execute
                      </button>
                    </div>
                  </div>

                  {/* Quick Commands */}
                  <div>
                    <h4 className="text-sm font-medium text-gray-700 mb-2">Quick Commands</h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                      {[
                        { label: 'Interface Info', cmd: 'ifconfig' },
                        { label: 'Routing Table', cmd: 'route -n' },
                        { label: 'ARP Table', cmd: 'arp -a' },
                        { label: 'Network Stats', cmd: 'netstat -i' },
                        { label: 'Ping Gateway', cmd: 'ping -c 3 $(route -n | grep ^0.0.0.0 | awk \'{print $2}\')' },
                        { label: 'DNS Lookup', cmd: 'nslookup google.com' },
                        { label: 'Process List', cmd: 'ps aux' },
                        { label: 'Disk Usage', cmd: 'df -h' }
                      ].map((quickCmd, index) => (
                        <button
                          key={index}
                          onClick={() => executeCommand(currentSelectedNode.id, quickCmd.cmd)}
                          disabled={loading}
                          className="px-3 py-2 text-sm bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 disabled:opacity-50 transition-colors"
                        >
                          {quickCmd.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Command Output */}
              <div>
                <h3 className="font-semibold mb-3">Command Output</h3>
                <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm h-96 overflow-y-auto">
                  {commandOutput ? (
                    <pre className="whitespace-pre-wrap">{commandOutput}</pre>
                  ) : (
                    <div className="text-gray-500">
                      No commands executed yet. Select a node and run a command to see output here.
                    </div>
                  )}
                </div>
              </div>

              {/* Command History */}
              {commandHistory.length > 0 && (
                <div>
                  <h3 className="font-semibold mb-3">Command History</h3>
                  <div className="bg-white border border-gray-200 rounded-lg max-h-60 overflow-y-auto">
                    {commandHistory.slice(0, 20).map((entry, index) => (
                      <div key={index} className="border-b border-gray-100 p-3 hover:bg-gray-50 transition-colors">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-gray-700">
                            {entry.node}$ {entry.command}
                          </span>
                          <span className="text-xs text-gray-500">
                            {new Date(entry.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <div className={`text-xs ${entry.success ? 'text-green-600' : 'text-red-600'}`}>
                          {entry.success ? '✓ Success' : '✗ Failed'}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Loading Overlay */}
      {loading && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 flex items-center gap-3 shadow-2xl">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
            <span className="text-gray-700 font-medium">Processing Configuration...</span>
          </div>
        </div>
      )}

      {/* Modal Close Button */}
      {isModal && onClose && (
        <button
          onClick={onClose}
          className="fixed top-4 right-4 z-50 bg-white rounded-full p-2 shadow-lg hover:shadow-xl transition-shadow border border-gray-200"
          title="Close Configuration"
        >
          <XCircle size={24} className="text-gray-600" />
        </button>
      )}
    </div>
  );
};

export default NetworkConfigurationManager;