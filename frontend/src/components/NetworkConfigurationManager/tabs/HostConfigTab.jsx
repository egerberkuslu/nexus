// HostConfigTab.jsx - Auto-updating with current status
import React, { useState, useEffect } from 'react';
import { 
  Monitor, Server, Router, Settings, Wifi, Globe, Network, 
  Shield, Activity, Save, Power, RefreshCw, Eye, Layers, 
  Command, Zap, Lock
} from 'lucide-react';
import { 
  ConfigSection, InputField, SelectField, CheckboxField, 
  DynamicList, ActionButton, EmptyState, StatusBadge 
} from '../components/FormComponents';

export const HostConfigTab = ({ 
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
    network: true,
    dns: false,
    services: false,
    routes: false,
    status: false
  });

  const [currentStatus, setCurrentStatus] = useState({
    ip: '',
    mac: '',
    gateway: '',
    interfaces: {},
    arp_table: '',
    routing_table: '',
    dns_servers: [],
    hostname: ''
  });

  const [realTimeConfig, setRealTimeConfig] = useState({
    ip: '',
    netmask: '255.255.255.0',
    gateway: '',
    hostname: '',
    dns: ['8.8.8.8', '8.8.4.4'],
    services: [],
    routes: []
  });

  const toggleSection = (section) => {
    setSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Auto-refresh data every 5 seconds when node is selected
  useEffect(() => {
    if (selectedNode && selectedNode.type === 'host') {
      fetchHostStatus();
      
      const interval = setInterval(() => {
        fetchHostStatus();
      }, 5000);
      
      return () => clearInterval(interval);
    }
  }, [selectedNode]);

  // Update config when selectedNode changes
  useEffect(() => {
    if (selectedNode && selectedNode.type === 'host') {
      setRealTimeConfig(prev => ({
        ...prev,
        ip: selectedNode.ip || '',
        hostname: selectedNode.id || '',
        ...config
      }));
    }
  }, [selectedNode, config]);

  const executeCommand = async (command) => {
    if (!selectedNode) return { success: false, error: 'No host selected' };

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

  const fetchHostStatus = async () => {
    if (!selectedNode) return;
    
    try {
      // Get current IP configuration
      const ifconfigResult = await executeCommand('ifconfig');
      let currentIP = selectedNode.ip || '';
      let currentMAC = selectedNode.mac || '';
      
      if (ifconfigResult.success) {
        // Parse ifconfig output to get current IP and MAC
        const ifconfigOutput = ifconfigResult.result;
        const ipMatch = ifconfigOutput.match(/inet (\d+\.\d+\.\d+\.\d+)/);
        const macMatch = ifconfigOutput.match(/ether ([a-f0-9:]{17})/i);
        
        if (ipMatch) currentIP = ipMatch[1];
        if (macMatch) currentMAC = macMatch[1];
      }

      // Get current hostname
      const hostnameResult = await executeCommand('hostname');
      let currentHostname = selectedNode.id || '';
      if (hostnameResult.success) {
        currentHostname = hostnameResult.result.trim();
      }

      // Get current gateway
      const routeResult = await executeCommand('ip route show default');
      let currentGateway = '';
      if (routeResult.success) {
        const gatewayMatch = routeResult.result.match(/default via (\d+\.\d+\.\d+\.\d+)/);
        if (gatewayMatch) currentGateway = gatewayMatch[1];
      }

      // Get DNS servers
      const dnsResult = await executeCommand('cat /etc/resolv.conf');
      let currentDNS = ['8.8.8.8', '8.8.4.4'];
      if (dnsResult.success) {
        const dnsLines = dnsResult.result.split('\n');
        const dnsServers = dnsLines
          .filter(line => line.startsWith('nameserver'))
          .map(line => line.split(' ')[1])
          .filter(ip => ip);
        if (dnsServers.length > 0) currentDNS = dnsServers;
      }

      // Get ARP table
      const arpResult = await executeCommand('arp -a');
      const arpTable = arpResult.success ? arpResult.result : '';

      // Get routing table
      const routingResult = await executeCommand('ip route show');
      const routingTable = routingResult.success ? routingResult.result : '';

      // Check running services
      const servicesResult = await executeCommand('netstat -tuln');
      let runningServices = [];
      if (servicesResult.success) {
        const output = servicesResult.result;
        if (output.includes(':22 ')) runningServices.push('ssh');
        if (output.includes(':80 ')) runningServices.push('http');
        if (output.includes(':443 ')) runningServices.push('https');
        if (output.includes(':21 ')) runningServices.push('ftp');
        if (output.includes(':23 ')) runningServices.push('telnet');
        if (output.includes(':161 ')) runningServices.push('snmp');
        if (output.includes(':123 ')) runningServices.push('ntp');
        if (output.includes(':67 ')) runningServices.push('dhcp');
        if (output.includes(':53 ')) runningServices.push('dns');
      }

      // Update current status
      setCurrentStatus({
        ip: currentIP,
        mac: currentMAC,
        gateway: currentGateway,
        hostname: currentHostname,
        arp_table: arpTable,
        routing_table: routingTable,
        dns_servers: currentDNS,
        running_services: runningServices
      });

      // Update config with current values
      setRealTimeConfig(prev => ({
        ...prev,
        ip: currentIP,
        gateway: currentGateway,
        hostname: currentHostname,
        dns: currentDNS,
        services: runningServices
      }));

      // Update parent config
      updateConfig({
        ...config,
        ip: currentIP,
        gateway: currentGateway,
        hostname: currentHostname,
        dns: currentDNS,
        services: runningServices
      });

    } catch (error) {
      console.error('Error fetching host status:', error);
    }
  };

  const applyConfiguration = async () => {
    if (!selectedNode) return;
    setLoading(true);
    
    try {
      const commands = [];

      // Configure IP address if changed
      if (realTimeConfig.ip && realTimeConfig.ip !== currentStatus.ip) {
        const netmask = realTimeConfig.netmask || '255.255.255.0';
        commands.push(`ifconfig ${selectedNode.id}-eth0 ${realTimeConfig.ip} netmask ${netmask}`);
      }

      // Configure hostname if changed
      if (realTimeConfig.hostname && realTimeConfig.hostname !== currentStatus.hostname) {
        commands.push(`hostname ${realTimeConfig.hostname}`);
        commands.push(`echo '127.0.0.1 ${realTimeConfig.hostname}' >> /etc/hosts`);
      }

      // Configure default gateway if changed
      if (realTimeConfig.gateway && realTimeConfig.gateway !== currentStatus.gateway) {
        // Remove old default gateway first
        commands.push('route del default 2>/dev/null || true');
        commands.push(`route add default gw ${realTimeConfig.gateway}`);
      }

      // Configure DNS servers if changed
      if (realTimeConfig.dns && JSON.stringify(realTimeConfig.dns) !== JSON.stringify(currentStatus.dns_servers)) {
        commands.push('echo "# Auto-configured DNS servers" > /etc/resolv.conf');
        realTimeConfig.dns.forEach(dnsServer => {
          if (dnsServer.trim()) {
            commands.push(`echo "nameserver ${dnsServer}" >> /etc/resolv.conf`);
          }
        });
      }

      // Configure static routes
      if (realTimeConfig.routes && Array.isArray(realTimeConfig.routes)) {
        realTimeConfig.routes.forEach(route => {
          if (route.network && route.gateway) {
            commands.push(`ip route add ${route.network} via ${route.gateway} 2>/dev/null || true`);
          }
        });
      }

      // Execute all commands
      let successCount = 0;
      for (const command of commands) {
        const result = await executeCommand(command);
        if (result.success) {
          successCount++;
        } else {
          showMessage(`Command failed: ${command}`, 'error');
        }
      }

      if (commands.length === 0) {
        showMessage('No configuration changes to apply', 'info');
      } else if (successCount === commands.length) {
        showMessage('Host configuration applied successfully', 'success');
        // Refresh status after configuration
        setTimeout(() => {
          fetchHostStatus();
          onNetworkChange?.();
        }, 2000);
      } else {
        showMessage(`Applied ${successCount}/${commands.length} configuration commands`, 'warning');
      }
    } catch (error) {
      showMessage(`Failed to apply configuration: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const pingTest = async (target) => {
    if (!selectedNode || !target) return;
    
    setLoading(true);
    try {
      const result = await executeCommand(`ping -c 4 ${target}`);
      if (result.success) {
        const output = result.result;
        if (output.includes('4 packets transmitted, 4 received')) {
          showMessage(`Ping to ${target}: Success (0% loss)`, 'success');
        } else if (output.includes('received')) {
          const lossMatch = output.match(/(\d+)% packet loss/);
          const loss = lossMatch ? lossMatch[1] : 'unknown';
          showMessage(`Ping to ${target}: Partial success (${loss}% loss)`, 'warning');
        } else {
          showMessage(`Ping to ${target}: Failed`, 'error');
        }
      } else {
        showMessage(`Ping to ${target}: Failed`, 'error');
      }
    } catch (error) {
      showMessage(`Ping test failed: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleConfigChange = (field, value) => {
    const newConfig = { ...realTimeConfig, [field]: value };
    setRealTimeConfig(newConfig);
    updateConfig(newConfig);
  };

  if (!selectedNode || selectedNode.type !== 'host') {
    return (
      <EmptyState
        icon={<Monitor className="w-8 h-8 text-gray-400" />}
        title="No Host Selected"
        description="Select a host node from the Overview tab to configure its settings."
      />
    );
  }

  const services = ['SSH', 'HTTP', 'HTTPS', 'FTP', 'Telnet', 'SNMP', 'NTP', 'DHCP', 'DNS'];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Host Configuration</h2>
          <p className="text-sm text-gray-500">Configure network settings for {selectedNode.id}</p>
        </div>
        <ActionButton
          onClick={applyConfiguration}
          loading={loading}
          icon={<Save size={16} />}
          label="Apply Configuration"
          variant="primary"
        />
      </div>

      {/* Host Status - Always visible with current info */}
      <ConfigSection
        title="Current Host Status"
        icon={Activity}
        expanded={sections.status}
        onToggle={() => toggleSection('status')}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="text-sm font-medium text-gray-600">Current IP</label>
            <p className="font-semibold text-gray-900">{currentStatus.ip || 'Not configured'}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">MAC Address</label>
            <p className="font-semibold text-gray-900">{currentStatus.mac || 'Unknown'}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Gateway</label>
            <p className="font-semibold text-gray-900">{currentStatus.gateway || 'None'}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Hostname</label>
            <p className="font-semibold text-gray-900">{currentStatus.hostname || selectedNode.id}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">DNS Servers</label>
            <p className="font-semibold text-gray-900">{currentStatus.dns_servers?.join(', ') || 'None'}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Running Services</label>
            <p className="font-semibold text-gray-900">
              {currentStatus.running_services?.length > 0 ? currentStatus.running_services.join(', ') : 'None'}
            </p>
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <ActionButton
            onClick={fetchHostStatus}
            loading={loading}
            icon={<RefreshCw size={16} />}
            label="Refresh Status"
            variant="secondary"
            size="sm"
          />
          <ActionButton
            onClick={() => pingTest('8.8.8.8')}
            loading={loading}
            icon={<Network size={16} />}
            label="Test Internet"
            variant="secondary"
            size="sm"
          />
          {currentStatus.gateway && (
            <ActionButton
              onClick={() => pingTest(currentStatus.gateway)}
              loading={loading}
              icon={<Router size={16} />}
              label="Test Gateway"
              variant="secondary"
              size="sm"
            />
          )}
        </div>
      </ConfigSection>

      {/* Network Interface Section - Pre-filled with current values */}
      <ConfigSection
        title="Network Interface Configuration"
        icon={Wifi}
        expanded={sections.network}
        onToggle={() => toggleSection('network')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <InputField
            label="IP Address"
            value={realTimeConfig.ip}
            onChange={(value) => handleConfigChange('ip', value)}
            placeholder={currentStatus.ip || "192.168.1.100"}
            icon={Globe}
            helper={`Current: ${currentStatus.ip || 'Not set'}`}
          />
          <SelectField
            label="Netmask"
            value={realTimeConfig.netmask || '255.255.255.0'}
            onChange={(value) => handleConfigChange('netmask', value)}
            options={[
              { value: '255.255.255.0', label: '255.255.255.0 (/24)' },
              { value: '255.255.0.0', label: '255.255.0.0 (/16)' },
              { value: '255.0.0.0', label: '255.0.0.0 (/8)' }
            ]}
            icon={Network}
          />
          <InputField
            label="Gateway"
            value={realTimeConfig.gateway}
            onChange={(value) => handleConfigChange('gateway', value)}
            placeholder={currentStatus.gateway || "192.168.1.1"}
            icon={Router}
            helper={`Current: ${currentStatus.gateway || 'None'}`}
          />
          <InputField
            label="Hostname"
            value={realTimeConfig.hostname}
            onChange={(value) => handleConfigChange('hostname', value)}
            placeholder={currentStatus.hostname || selectedNode.id}
            icon={Monitor}
            helper={`Current: ${currentStatus.hostname || selectedNode.id}`}
          />
        </div>
      </ConfigSection>

      {/* DNS Configuration - Pre-filled with current DNS */}
      <ConfigSection
        title="DNS Servers"
        icon={Globe}
        expanded={sections.dns}
        onToggle={() => toggleSection('dns')}
      >
        <div className="mb-2">
          <p className="text-sm text-gray-600">
            Current DNS: {currentStatus.dns_servers?.join(', ') || 'None configured'}
          </p>
        </div>
        <DynamicList
          items={realTimeConfig.dns || currentStatus.dns_servers || ['8.8.8.8', '8.8.4.4']}
          onChange={(dns) => handleConfigChange('dns', dns)}
          placeholder="DNS Server IP (e.g., 8.8.8.8)"
          addLabel="Add DNS Server"
        />
      </ConfigSection>

      {/* Services Configuration - Shows current running services */}
      <ConfigSection
        title="Network Services"
        icon={Activity}
        expanded={sections.services}
        onToggle={() => toggleSection('services')}
      >
        <div className="mb-4">
          <p className="text-sm text-gray-600">
            Currently running: {currentStatus.running_services?.length > 0 ? 
              currentStatus.running_services.join(', ') : 'No services detected'}
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {services.map((service) => {
            const isRunning = currentStatus.running_services?.includes(service.toLowerCase());
            const isSelected = (realTimeConfig.services || []).includes(service.toLowerCase());
            
            return (
              <div key={service} className="flex items-center space-x-2">
                <CheckboxField
                  label={service}
                  checked={isSelected}
                  onChange={(checked) => {
                    const services = realTimeConfig.services || [];
                    const newServices = checked 
                      ? [...services, service.toLowerCase()]
                      : services.filter(s => s !== service.toLowerCase());
                    handleConfigChange('services', newServices);
                  }}
                />
                {isRunning && (
                  <span className="text-xs text-green-600 font-medium">●</span>
                )}
              </div>
            );
          })}
        </div>
      </ConfigSection>

      {/* Static Routes */}
      <ConfigSection
        title="Static Routes"
        icon={Network}
        expanded={sections.routes}
        onToggle={() => toggleSection('routes')}
      >
        <DynamicList
          items={realTimeConfig.routes || []}
          onChange={(routes) => handleConfigChange('routes', routes)}
          placeholder="Route configuration"
          addLabel="Add Static Route"
          itemComponent={(route, index, update) => (
            <div className="flex-1 grid grid-cols-2 gap-2">
              <InputField
                value={route.network || ''}
                onChange={(value) => update(index, { ...route, network: value })}
                placeholder="Network (e.g., 192.168.2.0/24)"
              />
              <InputField
                value={route.gateway || ''}
                onChange={(value) => update(index, { ...route, gateway: value })}
                placeholder="Gateway (e.g., 192.168.1.1)"
              />
            </div>
          )}
        />
      </ConfigSection>

      {/* Current Routing Table Display */}
      {currentStatus.routing_table && (
        <ConfigSection
          title="Current Routing Table"
          icon={Network}
          expanded={false}
        >
          <pre className="bg-gray-100 p-3 rounded text-xs overflow-x-auto">
            {currentStatus.routing_table}
          </pre>
        </ConfigSection>
      )}

      {/* ARP Table Display */}
      {currentStatus.arp_table && (
        <ConfigSection
          title="Current ARP Table"
          icon={Network}
          expanded={false}
        >
          <pre className="bg-gray-100 p-3 rounded text-xs overflow-x-auto">
            {currentStatus.arp_table}
          </pre>
        </ConfigSection>
      )}
    </div>
  );
};