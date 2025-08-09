// RouterConfigTab.jsx - Auto-updating with current status
import React, { useState, useEffect } from 'react';
import {
  Settings, Map, ShieldCheck, Route, Plus, Save, Network, Activity, RefreshCw
} from 'lucide-react';
import { InputField, SelectField, CheckboxField, EmptyState } from '../components/FormComponents';
import ActionButton from '../components/ActionButton';
import ConfigSection from '../components/ConfigSection';

export const RouterConfigTab = ({ 
  selectedNode, 
  config, 
  updateConfig, 
  loading, 
  setLoading, 
  showMessage, 
  apiCall, 
  onNetworkChange 
}) => {
  const [sections, setSections] = useState({
    interfaces: true,
    protocol: false,
    staticRoutes: false,
    nat: false,
    firewall: false,
    status: false
  });

  const [currentStatus, setCurrentStatus] = useState({
    ipForwarding: false,
    interfaces: [],
    routingTable: '',
    natRules: '',
    firewallRules: '',
    arpTable: ''
  });

  const [realTimeConfig, setRealTimeConfig] = useState({
    interfaces: [],
    protocol: 'static',
    static_routes: [],
    nat_enabled: false,
    firewall_rules: []
  });

  const toggle = (section) => setSections(prev => ({ ...prev, [section]: !prev[section] }));

  // Auto-refresh data every 5 seconds when router is selected
  useEffect(() => {
    if (selectedNode && selectedNode.type === 'router') {
      fetchRouterStatus();
      
      const interval = setInterval(() => {
        fetchRouterStatus();
      }, 5000);
      
      return () => clearInterval(interval);
    }
  }, [selectedNode]);

  // Update config when selectedNode or config changes
  useEffect(() => {
    if (selectedNode && selectedNode.type === 'router') {
      setRealTimeConfig(prev => ({
        ...prev,
        ...config
      }));
    }
  }, [selectedNode, config]);

  const executeCommand = async (command) => {
    if (!selectedNode) return { success: false, error: 'No router selected' };

    try {
      const response = await apiCall(`/network/hosts/${selectedNode.id}/cmd`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
      });

      if (response.success) {
        return response.data;
      } else {
        return { success: false, error: response.error };
      }
    } catch (error) {
      return { success: false, error: error.message };
    }
  };

  const fetchRouterStatus = async () => {
    if (!selectedNode) return;

    try {
      // Get interface information
      const ifconfigResult = await executeCommand('ip addr show');
      let interfaces = [];
      if (ifconfigResult.success) {
        // Parse interface information
        const output = ifconfigResult.result;
        const interfaceBlocks = output.split(/^\d+:/m).slice(1);
        
        interfaceBlocks.forEach(block => {
          const lines = block.split('\n');
          const nameMatch = lines[0].match(/(\w+):/);
          if (nameMatch && nameMatch[1] !== 'lo') {
            const interfaceName = nameMatch[1];
            const ipMatch = block.match(/inet (\d+\.\d+\.\d+\.\d+)\/(\d+)/);
            const macMatch = block.match(/link\/ether ([a-f0-9:]{17})/i);
            
            if (ipMatch) {
              const ip = ipMatch[1];
              const prefix = ipMatch[2];
              const netmask = prefixToNetmask(parseInt(prefix));
              
              interfaces.push({
                name: interfaceName,
                ip: ip,
                netmask: netmask,
                mac: macMatch ? macMatch[1] : ''
              });
            }
          }
        });
      }

      // Check IP forwarding
      const forwardResult = await executeCommand('cat /proc/sys/net/ipv4/ip_forward');
      const ipForwarding = forwardResult.success && forwardResult.result.trim() === '1';

      // Get routing table
      const routeResult = await executeCommand('ip route show');
      const routingTable = routeResult.success ? routeResult.result : '';

      // Get NAT rules
      const natResult = await executeCommand('iptables -t nat -L -n 2>/dev/null || echo "No NAT rules"');
      const natRules = natResult.success ? natResult.result : '';

      // Get firewall rules
      const firewallResult = await executeCommand('iptables -L -n 2>/dev/null || echo "No firewall rules"');
      const firewallRules = firewallResult.success ? firewallResult.result : '';

      // Get ARP table
      const arpResult = await executeCommand('arp -a');
      const arpTable = arpResult.success ? arpResult.result : '';

      // Parse static routes from routing table
      const staticRoutes = [];
      if (routingTable) {
        const routeLines = routingTable.split('\n');
        routeLines.forEach(line => {
          if (line.includes('via') && !line.startsWith('default')) {
            const parts = line.split(/\s+/);
            if (parts.length >= 3) {
              const network = parts[0];
              const gatewayIndex = parts.indexOf('via');
              const devIndex = parts.indexOf('dev');
              
              if (gatewayIndex > -1 && devIndex > -1) {
                staticRoutes.push({
                  network: network,
                  gateway: parts[gatewayIndex + 1],
                  interface: parts[devIndex + 1]
                });
              }
            }
          }
        });
      }

      // Check if NAT is enabled
      const natEnabled = natRules.includes('MASQUERADE') || natRules.includes('SNAT');

      setCurrentStatus({
        ipForwarding,
        interfaces,
        routingTable,
        natRules,
        firewallRules,
        arpTable
      });

      // Update config with current values
      setRealTimeConfig(prev => ({
        ...prev,
        interfaces: interfaces.length > 0 ? interfaces : prev.interfaces,
        static_routes: staticRoutes.length > 0 ? staticRoutes : prev.static_routes,
        nat_enabled: natEnabled
      }));

      // Update parent config
      updateConfig({
        ...config,
        interfaces: interfaces.length > 0 ? interfaces : config.interfaces || [],
        static_routes: staticRoutes.length > 0 ? staticRoutes : config.static_routes || [],
        nat_enabled: natEnabled
      });

    } catch (error) {
      console.error('Error fetching router status:', error);
    }
  };

  // Helper function to convert CIDR prefix to netmask
  const prefixToNetmask = (prefix) => {
    const mask = (0xffffffff << (32 - prefix)) >>> 0;
    return [
      (mask >>> 24) & 0xff,
      (mask >>> 16) & 0xff,
      (mask >>> 8) & 0xff,
      mask & 0xff
    ].join('.');
  };

  const applyConfig = async () => {
    if (!selectedNode || selectedNode.type !== 'router') return;
    setLoading(true);
    
    try {
      const commands = [];
      let configChanged = false;

      // Enable IP forwarding if not already enabled
      if (!currentStatus.ipForwarding) {
        commands.push('echo 1 > /proc/sys/net/ipv4/ip_forward');
        configChanged = true;
      }

      // Configure interfaces
      if (realTimeConfig.interfaces && Array.isArray(realTimeConfig.interfaces)) {
        realTimeConfig.interfaces.forEach((intf, i) => {
          if (intf.ip && intf.netmask) {
            const interfaceName = intf.name || `${selectedNode.id}-eth${i}`;
            // Check if interface needs configuration
            const currentIntf = currentStatus.interfaces.find(ci => ci.name === interfaceName);
            if (!currentIntf || currentIntf.ip !== intf.ip) {
              commands.push(`ifconfig ${interfaceName} ${intf.ip} netmask ${intf.netmask}`);
              commands.push(`ip link set ${interfaceName} up`);
              configChanged = true;
            }
          }
        });
      }

      // Configure static routes
      if (realTimeConfig.static_routes && Array.isArray(realTimeConfig.static_routes)) {
        realTimeConfig.static_routes.forEach(route => {
          if (route.network && route.gateway) {
            // Check if route already exists
            const routeExists = currentStatus.routingTable.includes(route.network) && 
                              currentStatus.routingTable.includes(route.gateway);
            if (!routeExists) {
              if (route.interface) {
                commands.push(`ip route add ${route.network} via ${route.gateway} dev ${route.interface} 2>/dev/null || true`);
              } else {
                commands.push(`ip route add ${route.network} via ${route.gateway} 2>/dev/null || true`);
              }
              configChanged = true;
            }
          }
        });
      }

      // Configure NAT if enabled and not already configured
      if (realTimeConfig.nat_enabled && !currentStatus.natRules.includes('MASQUERADE')) {
        commands.push('iptables -t nat -F POSTROUTING 2>/dev/null || true'); // Clear existing rules
        commands.push('iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE');
        commands.push('iptables -A FORWARD -i eth1 -o eth0 -j ACCEPT 2>/dev/null || true');
        commands.push('iptables -A FORWARD -i eth0 -o eth1 -m state --state RELATED,ESTABLISHED -j ACCEPT 2>/dev/null || true');
        configChanged = true;
      }

      // Configure firewall rules
      if (realTimeConfig.firewall_rules && Array.isArray(realTimeConfig.firewall_rules)) {
        realTimeConfig.firewall_rules.forEach(rule => {
          if (rule.action && rule.chain && rule.parameters) {
            // Check if rule already exists (basic check)
            const ruleExists = currentStatus.firewallRules.includes(rule.parameters);
            if (!ruleExists) {
              commands.push(`iptables ${rule.action} ${rule.chain} ${rule.parameters} 2>/dev/null || true`);
              configChanged = true;
            }
          }
        });
      }

      if (!configChanged) {
        showMessage('No configuration changes to apply', 'info');
        setLoading(false);
        return;
      }

      // Execute all commands
      let successCount = 0;
      let errorMessages = [];
      
      for (const command of commands) {
        const result = await executeCommand(command);
        if (result.success) {
          successCount++;
        } else {
          errorMessages.push(`${command}: ${result.error}`);
        }
      }

      if (successCount === commands.length) {
        showMessage('✅ Router configuration applied successfully', 'success');
        // Refresh status after configuration
        setTimeout(() => {
          fetchRouterStatus();
          onNetworkChange?.();
        }, 2000);
      } else {
        showMessage(`Applied ${successCount}/${commands.length} commands`, 'warning');
        if (errorMessages.length > 0) {
          console.warn('Command errors:', errorMessages);
        }
      }
    } catch (err) {
      showMessage(`❌ ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const testConnectivity = async (target) => {
    if (!selectedNode || !target) return;
    
    setLoading(true);
    try {
      const result = await executeCommand(`ping -c 3 ${target}`);
      if (result.success) {
        if (result.result.includes('3 packets transmitted, 3 received')) {
          showMessage(`Connectivity test to ${target}: Success (0% loss)`, 'success');
        } else if (result.result.includes('received')) {
          const lossMatch = result.result.match(/(\d+)% packet loss/);
          const loss = lossMatch ? lossMatch[1] : 'unknown';
          showMessage(`Connectivity test to ${target}: Partial success (${loss}% loss)`, 'warning');
        } else {
          showMessage(`Connectivity test to ${target}: Failed`, 'error');
        }
      } else {
        showMessage(`Connectivity test to ${target}: Failed`, 'error');
      }
    } catch (error) {
      showMessage(`Connectivity test failed: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleConfigChange = (field, value) => {
    const newConfig = { ...realTimeConfig, [field]: value };
    setRealTimeConfig(newConfig);
    updateConfig(newConfig);
  };

  const handleInterfaceChange = (index, field, value) => {
    const newInterfaces = [...(realTimeConfig.interfaces || [])];
    newInterfaces[index] = { ...newInterfaces[index], [field]: value };
    handleConfigChange('interfaces', newInterfaces);
  };

  const addInterface = () => {
    const newInterfaces = [...(realTimeConfig.interfaces || []), { name: '', ip: '', netmask: '255.255.255.0' }];
    handleConfigChange('interfaces', newInterfaces);
  };

  const removeInterface = (index) => {
    const newInterfaces = (realTimeConfig.interfaces || []).filter((_, i) => i !== index);
    handleConfigChange('interfaces', newInterfaces);
  };

  const handleRouteChange = (index, field, value) => {
    const newRoutes = [...(realTimeConfig.static_routes || [])];
    newRoutes[index] = { ...newRoutes[index], [field]: value };
    handleConfigChange('static_routes', newRoutes);
  };

  const addRoute = () => {
    const newRoutes = [...(realTimeConfig.static_routes || []), { network: '', gateway: '', interface: '' }];
    handleConfigChange('static_routes', newRoutes);
  };

  const removeRoute = (index) => {
    const newRoutes = (realTimeConfig.static_routes || []).filter((_, i) => i !== index);
    handleConfigChange('static_routes', newRoutes);
  };

  const handleFirewallRuleChange = (index, field, value) => {
    const newRules = [...(realTimeConfig.firewall_rules || [])];
    newRules[index] = { ...newRules[index], [field]: value };
    handleConfigChange('firewall_rules', newRules);
  };

  const addFirewallRule = () => {
    const newRules = [...(realTimeConfig.firewall_rules || []), { action: '-A', chain: 'INPUT', parameters: '' }];
    handleConfigChange('firewall_rules', newRules);
  };

  const removeFirewallRule = (index) => {
    const newRules = (realTimeConfig.firewall_rules || []).filter((_, i) => i !== index);
    handleConfigChange('firewall_rules', newRules);
  };

  const routingProtocols = [
    { value: 'static', label: 'Static Routing' },
    { value: 'rip', label: 'RIP' },
    { value: 'ospf', label: 'OSPF' },
    { value: 'bgp', label: 'BGP' }
  ];

  if (!selectedNode || selectedNode.type !== 'router') {
    return (
      <div className="p-8">
        <EmptyState
          title="No Router Selected"
          description="Please select a router from the Overview tab to configure it."
        />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-gradient-to-br from-green-500 to-emerald-500 text-white rounded-xl">
            <Route size={20} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">Configure Router</h2>
            <p className="text-gray-600">{selectedNode.id}</p>
          </div>
        </div>
        <ActionButton
          onClick={applyConfig}
          loading={loading}
          icon={<Save size={16} />}
          label="Apply Configuration"
        />
      </div>

      {/* Router Status - Always visible with current info */}
      <ConfigSection
        title="Current Router Status"
        icon={Activity}
        expanded={sections.status}
        onToggle={() => toggle('status')}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="text-sm font-medium text-gray-600">IP Forwarding</label>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${currentStatus.ipForwarding ? 'bg-green-500' : 'bg-red-500'}`} />
              <p className={`font-semibold ${currentStatus.ipForwarding ? 'text-green-600' : 'text-red-600'}`}>
                {currentStatus.ipForwarding ? 'Enabled' : 'Disabled'}
              </p>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">NAT Status</label>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${realTimeConfig.nat_enabled ? 'bg-green-500' : 'bg-gray-400'}`} />
              <p className="font-semibold text-gray-900">
                {realTimeConfig.nat_enabled ? 'Enabled' : 'Disabled'}
              </p>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Configured Interfaces</label>
            <p className="font-semibold text-gray-900">
              {currentStatus.interfaces.length} interfaces
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Static Routes</label>
            <p className="font-semibold text-gray-900">
              {(realTimeConfig.static_routes || []).length} routes
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Firewall Rules</label>
            <p className="font-semibold text-gray-900">
              {(realTimeConfig.firewall_rules || []).length} rules
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Routing Protocol</label>
            <p className="font-semibold text-gray-900">
              {realTimeConfig.protocol || 'Static'}
            </p>
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <ActionButton
            onClick={fetchRouterStatus}
            loading={loading}
            icon={<RefreshCw size={16} />}
            label="Refresh Status"
            variant="secondary"
            size="sm"
          />
          <ActionButton
            onClick={() => testConnectivity('8.8.8.8')}
            loading={loading}
            icon={<Network size={16} />}
            label="Test Internet"
            variant="secondary"
            size="sm"
          />
        </div>
      </ConfigSection>

      {/* Current Interfaces Display */}
      {currentStatus.interfaces.length > 0 && (
        <ConfigSection
          title="Current Network Interfaces"
          icon={Network}
          expanded={false}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {currentStatus.interfaces.map((intf, index) => (
              <div key={index} className="p-3 bg-gray-50 rounded border">
                <div className="font-medium text-gray-900">{intf.name}</div>
                <div className="text-sm text-gray-600">IP: {intf.ip}</div>
                <div className="text-sm text-gray-600">Netmask: {intf.netmask}</div>
                {intf.mac && <div className="text-sm text-gray-600">MAC: {intf.mac}</div>}
              </div>
            ))}
          </div>
        </ConfigSection>
      )}

      {/* Router Interfaces Configuration */}
      <ConfigSection
        title="Interface Configuration"
        icon={Settings}
        expanded={sections.interfaces}
        onToggle={() => toggle('interfaces')}
      >
        {(realTimeConfig.interfaces || []).map((intf, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4 p-4 border rounded">
            <InputField
              label="Interface Name"
              value={intf.name || `eth${i}`}
              onChange={val => handleInterfaceChange(i, 'name', val)}
              placeholder={`eth${i}`}
            />
            <InputField
              label="IP Address"
              value={intf.ip || ''}
              onChange={val => handleInterfaceChange(i, 'ip', val)}
              placeholder="10.0.0.1"
            />
            <div className="flex gap-2">
              <InputField
                label="Netmask"
                value={intf.netmask || ''}
                onChange={val => handleInterfaceChange(i, 'netmask', val)}
                placeholder="255.255.255.0"
              />
              <button
                onClick={() => removeInterface(i)}
                className="self-end p-2 text-red-600 hover:bg-red-50 rounded"
                title="Remove interface"
              >
                ×
              </button>
            </div>
          </div>
        ))}
        <button
          onClick={addInterface}
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <Plus size={16} />
          Add Interface
        </button>
      </ConfigSection>

      {/* Routing Protocol */}
      <ConfigSection
        title="Routing Protocol"
        icon={Map}
        expanded={sections.protocol}
        onToggle={() => toggle('protocol')}
      >
        <SelectField
          label="Protocol"
          value={realTimeConfig.protocol || 'static'}
          onChange={val => handleConfigChange('protocol', val)}
          options={routingProtocols}
        />
      </ConfigSection>

      {/* Static Routes */}
      <ConfigSection
        title="Static Routes"
        icon={Route}
        expanded={sections.staticRoutes}
        onToggle={() => toggle('staticRoutes')}
      >
        {(realTimeConfig.static_routes || []).map((route, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4 p-4 border rounded">
            <InputField
              label="Network"
              value={route.network || ''}
              onChange={val => handleRouteChange(i, 'network', val)}
              placeholder="192.168.0.0/24"
            />
            <InputField
              label="Gateway"
              value={route.gateway || ''}
              onChange={val => handleRouteChange(i, 'gateway', val)}
              placeholder="192.168.0.1"
            />
            <InputField
              label="Interface"
              value={route.interface || ''}
              onChange={val => handleRouteChange(i, 'interface', val)}
              placeholder="eth0"
            />
            <button
              onClick={() => removeRoute(i)}
              className="self-end p-2 text-red-600 hover:bg-red-50 rounded"
              title="Remove route"
            >
              ×
            </button>
          </div>
        ))}
        <button
          onClick={addRoute}
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <Plus size={16} />
          Add Route
        </button>
      </ConfigSection>

      {/* NAT Configuration */}
      <ConfigSection
        title="NAT Configuration"
        icon={ShieldCheck}
        expanded={sections.nat}
        onToggle={() => toggle('nat')}
      >
        <CheckboxField
          label="Enable NAT"
          checked={realTimeConfig.nat_enabled || false}
          onChange={v => handleConfigChange('nat_enabled', v)}
          helper="Enable Network Address Translation for outbound traffic"
        />
        
        {currentStatus.natRules && realTimeConfig.nat_enabled && (
          <div className="mt-4">
            <label className="text-sm font-medium text-gray-600">Current NAT Rules</label>
            <pre className="bg-gray-100 p-3 rounded text-xs mt-2 overflow-x-auto max-h-32">
              {currentStatus.natRules}
            </pre>
          </div>
        )}
      </ConfigSection>

      {/* Firewall Rules */}
      <ConfigSection
        title="Firewall Rules"
        icon={ShieldCheck}
        expanded={sections.firewall}
        onToggle={() => toggle('firewall')}
      >
        {(realTimeConfig.firewall_rules || []).map((rule, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4 p-4 border rounded">
            <SelectField
              label="Action"
              value={rule.action || '-A'}
              onChange={val => handleFirewallRuleChange(i, 'action', val)}
              options={[
                { value: '-A', label: 'Append' },
                { value: '-I', label: 'Insert' },
                { value: '-D', label: 'Delete' }
              ]}
            />
            <SelectField
              label="Chain"
              value={rule.chain || 'INPUT'}
              onChange={val => handleFirewallRuleChange(i, 'chain', val)}
              options={[
                { value: 'INPUT', label: 'INPUT' },
                { value: 'OUTPUT', label: 'OUTPUT' },
                { value: 'FORWARD', label: 'FORWARD' }
              ]}
            />
            <InputField
              label="Parameters"
              value={rule.parameters || ''}
              onChange={val => handleFirewallRuleChange(i, 'parameters', val)}
              placeholder="-p tcp --dport 80 -j ACCEPT"
            />
            <button
              onClick={() => removeFirewallRule(i)}
              className="self-end p-2 text-red-600 hover:bg-red-50 rounded"
              title="Remove rule"
            >
              ×
            </button>
          </div>
        ))}
        <button
          onClick={addFirewallRule}
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <Plus size={16} />
          Add Rule
        </button>

        {currentStatus.firewallRules && (
          <div className="mt-6">
            <label className="text-sm font-medium text-gray-600">Current Firewall Rules</label>
            <pre className="bg-gray-100 p-3 rounded text-xs mt-2 overflow-x-auto max-h-48">
              {currentStatus.firewallRules}
            </pre>
          </div>
        )}
      </ConfigSection>

      {/* Current Routing Table Display */}
      {currentStatus.routingTable && (
        <ConfigSection
          title="Current Routing Table"
          icon={Network}
          expanded={false}
        >
          <pre className="bg-gray-100 p-3 rounded text-xs overflow-x-auto">
            {currentStatus.routingTable}
          </pre>
        </ConfigSection>
      )}

      {/* ARP Table Display */}
      {currentStatus.arpTable && (
        <ConfigSection
          title="Current ARP Table"
          icon={Network}
          expanded={false}
        >
          <pre className="bg-gray-100 p-3 rounded text-xs overflow-x-auto">
            {currentStatus.arpTable}
          </pre>
        </ConfigSection>
      )}

      {/* Configuration Summary */}
      <div className="bg-green-50 rounded-lg p-4">
        <h4 className="font-medium text-green-900 mb-2">Router Configuration Summary</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
          <div>
            <span className="text-green-700">IP Forwarding:</span>
            <span className="ml-2 font-mono">{currentStatus.ipForwarding ? 'Enabled' : 'Disabled'}</span>
          </div>
          <div>
            <span className="text-green-700">Interfaces:</span>
            <span className="ml-2 font-mono">{currentStatus.interfaces.length} configured</span>
          </div>
          <div>
            <span className="text-green-700">Static Routes:</span>
            <span className="ml-2 font-mono">{(realTimeConfig.static_routes || []).length} routes</span>
          </div>
          <div>
            <span className="text-green-700">NAT:</span>
            <span className="ml-2 font-mono">{realTimeConfig.nat_enabled ? 'Enabled' : 'Disabled'}</span>
          </div>
          <div>
            <span className="text-green-700">Firewall Rules:</span>
            <span className="ml-2 font-mono">{(realTimeConfig.firewall_rules || []).length} rules</span>
          </div>
          <div>
            <span className="text-green-700">Routing Protocol:</span>
            <span className="ml-2 font-mono">{realTimeConfig.protocol || 'Static'}</span>
          </div>
        </div>
        {!currentStatus.ipForwarding && (
          <div className="mt-2 p-2 bg-yellow-100 rounded text-yellow-800 text-sm">
            ⚠️ IP forwarding is disabled. Enable it to allow routing between networks.
          </div>
        )}
      </div>
    </div>
  );
};