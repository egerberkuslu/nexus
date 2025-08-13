// HostConfigTab.jsx - Using bulk configuration and snapshots
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
import { useDeviceSnapshot, useApplyConfig, useCommandExecution } from '../hooks/useNetworkManagement';

export const HostConfigTab = ({ 
  selectedNode, 
  config, 
  updateConfig, 
  loading: parentLoading, 
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

  const [localConfig, setLocalConfig] = useState({
    ip: '',
    netmask: '255.255.255.0',
    gateway: '',
    hostname: '',
    dns: ['8.8.8.8', '8.8.4.4'],
    services: [],
    routes: []
  });

  // Use the new hooks
  const { snapshot, loading: snapshotLoading, refreshSnapshot } = useDeviceSnapshot(selectedNode?.id);
  const { applyConfig, buildHostConfig, loading: applyLoading } = useApplyConfig();
  const { executeCommand, loading: cmdLoading } = useCommandExecution();

  const loading = parentLoading || snapshotLoading || applyLoading || cmdLoading;

  const toggleSection = (section) => {
    setSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Auto-refresh snapshot every 5 seconds
  useEffect(() => {
    if (selectedNode && selectedNode.type === 'host') {
      const interval = setInterval(() => {
        refreshSnapshot();
      }, 5000);
      
      return () => clearInterval(interval);
    }
  }, [selectedNode, refreshSnapshot]);

  // Update local config from snapshot
  useEffect(() => {
    if (snapshot && snapshot.type === 'host') {
      const currentIP = snapshot.summary?.current_ip?.split('/')[0] || '';
      const currentGateway = snapshot.summary?.gateway || '';
      const currentDNS = snapshot.summary?.dns || ['8.8.8.8', '8.8.4.4'];
      
      setLocalConfig(prev => ({
        ...prev,
        ip: currentIP,
        gateway: currentGateway,
        dns: currentDNS,
        hostname: snapshot.id || '',
        ...config
      }));
    }
  }, [snapshot, config]);

  const applyConfiguration = async () => {
    if (!selectedNode) return;
    setLoading(true);
    
    try {
      // Build configuration spec
      const spec = buildHostConfig(selectedNode.id, localConfig);
      
      // Apply configuration
      const result = await applyConfig(spec);
      
      if (result.success) {
        const successCount = result.applied || 0;
        const failCount = result.failed || 0;
        
        if (failCount === 0) {
          showMessage('✅ Host configuration applied successfully', 'success');
        } else {
          showMessage(`⚠️ Applied ${successCount} commands, ${failCount} failed`, 'warning');
        }
        
        // Refresh snapshot after configuration
        setTimeout(() => {
          refreshSnapshot();
          onNetworkChange?.();
        }, 2000);
      } else {
        showMessage('❌ Failed to apply configuration', 'error');
      }
    } catch (error) {
      showMessage(`❌ Error: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const pingTest = async (target) => {
    if (!selectedNode || !target) return;
    
    setLoading(true);
    try {
      const result = await executeCommand(selectedNode.id, `ping -c 4 ${target}`);
      if (result.success) {
        const output = result.result;
        if (output.includes('4 packets transmitted, 4 received')) {
          showMessage(`✅ Ping to ${target}: Success (0% loss)`, 'success');
        } else if (output.includes('received')) {
          const lossMatch = output.match(/(\d+)% packet loss/);
          const loss = lossMatch ? lossMatch[1] : 'unknown';
          showMessage(`⚠️ Ping to ${target}: Partial success (${loss}% loss)`, 'warning');
        } else {
          showMessage(`❌ Ping to ${target}: Failed`, 'error');
        }
      } else {
        showMessage(`❌ Ping to ${target}: Failed`, 'error');
      }
    } catch (error) {
      showMessage(`❌ Ping test failed: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleConfigChange = (field, value) => {
    const newConfig = { ...localConfig, [field]: value };
    setLocalConfig(newConfig);
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

  // Extract current status from snapshot
  const currentStatus = {
    ip: snapshot?.summary?.current_ip || 'Not configured',
    mac: snapshot?.summary?.mac || 'Unknown',
    gateway: snapshot?.summary?.gateway || 'None',
    dns: snapshot?.summary?.dns || [],
    services: snapshot?.services || [],
    openPorts: snapshot?.open_ports || [],
    routes: snapshot?.routes || [],
    interfaces: snapshot?.interfaces || []
  };

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

      {/* Host Status - From Snapshot */}
      <ConfigSection
        title="Current Host Status"
        icon={Activity}
        expanded={sections.status}
        onToggle={() => toggleSection('status')}
      >
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="text-sm font-medium text-gray-600">Current IP</label>
            <p className="font-semibold text-gray-900">{currentStatus.ip}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">MAC Address</label>
            <p className="font-semibold text-gray-900">{currentStatus.mac}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Gateway</label>
            <p className="font-semibold text-gray-900">{currentStatus.gateway}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Hostname</label>
            <p className="font-semibold text-gray-900">{snapshot?.id || selectedNode.id}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">DNS Servers</label>
            <p className="font-semibold text-gray-900">{currentStatus.dns.join(', ') || 'None'}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Open Ports</label>
            <p className="font-semibold text-gray-900">
              {currentStatus.openPorts.length > 0 ? 
                currentStatus.openPorts.map(p => p.port).join(', ') : 'None'}
            </p>
          </div>
        </div>

        {/* Current Interfaces */}
        {currentStatus.interfaces.length > 0 && (
          <div className="mt-4">
            <label className="text-sm font-medium text-gray-600">Network Interfaces</label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
              {currentStatus.interfaces.map((intf, i) => (
                <div key={i} className="bg-gray-50 p-2 rounded text-sm">
                  <span className="font-medium">{intf.interface}:</span> {intf.address}
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2 mt-4">
          <ActionButton
            onClick={refreshSnapshot}
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
          {currentStatus.gateway !== 'None' && (
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

      {/* Network Interface Configuration */}
      <ConfigSection
        title="Network Interface Configuration"
        icon={Wifi}
        expanded={sections.network}
        onToggle={() => toggleSection('network')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <InputField
            label="IP Address"
            value={localConfig.ip}
            onChange={(value) => handleConfigChange('ip', value)}
            placeholder={currentStatus.ip || "192.168.1.100"}
            icon={Globe}
            helper={`Current: ${currentStatus.ip}`}
          />
          <SelectField
            label="Netmask"
            value={localConfig.netmask || '255.255.255.0'}
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
            value={localConfig.gateway}
            onChange={(value) => handleConfigChange('gateway', value)}
            placeholder={currentStatus.gateway || "192.168.1.1"}
            icon={Router}
            helper={`Current: ${currentStatus.gateway}`}
          />
          <InputField
            label="Hostname"
            value={localConfig.hostname}
            onChange={(value) => handleConfigChange('hostname', value)}
            placeholder={snapshot?.id || selectedNode.id}
            icon={Monitor}
            helper={`Current: ${snapshot?.id || selectedNode.id}`}
          />
        </div>
      </ConfigSection>

      {/* DNS Configuration */}
      <ConfigSection
        title="DNS Servers"
        icon={Globe}
        expanded={sections.dns}
        onToggle={() => toggleSection('dns')}
      >
        <div className="mb-2">
          <p className="text-sm text-gray-600">
            Current DNS: {currentStatus.dns.join(', ') || 'None configured'}
          </p>
        </div>
        <DynamicList
          items={localConfig.dns || ['8.8.8.8', '8.8.4.4']}
          onChange={(dns) => handleConfigChange('dns', dns)}
          placeholder="DNS Server IP (e.g., 8.8.8.8)"
          addLabel="Add DNS Server"
        />
      </ConfigSection>

      {/* Services Configuration */}
      <ConfigSection
        title="Network Services"
        icon={Activity}
        expanded={sections.services}
        onToggle={() => toggleSection('services')}
      >
        <div className="mb-4">
          <p className="text-sm text-gray-600">
            Open ports: {currentStatus.openPorts.length > 0 ? 
              currentStatus.openPorts.map(p => `${p.port}/${p.protocol}`).join(', ') : 
              'No services detected'}
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          {services.map((service) => {
            const servicePort = {
              'SSH': 22, 'HTTP': 80, 'HTTPS': 443, 'FTP': 21,
              'Telnet': 23, 'SNMP': 161, 'NTP': 123, 'DHCP': 67, 'DNS': 53
            }[service];
            
            const isRunning = currentStatus.openPorts.some(p => p.port === servicePort);
            const isSelected = (localConfig.services || []).includes(service.toLowerCase());
            
            return (
              <div key={service} className="flex items-center space-x-2">
                <CheckboxField
                  label={service}
                  checked={isSelected}
                  onChange={(checked) => {
                    const services = localConfig.services || [];
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
        {currentStatus.routes.length > 0 && (
          <div className="mb-4">
            <label className="text-sm font-medium text-gray-600">Current Routes</label>
            <div className="bg-gray-50 p-2 rounded mt-2">
              {currentStatus.routes.map((route, i) => (
                <div key={i} className="text-xs font-mono">
                  {route.destination} → {route.gateway || 'direct'} 
                  {route.interface && ` (${route.interface})`}
                </div>
              ))}
            </div>
          </div>
        )}
        
        <DynamicList
          items={localConfig.routes || []}
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

      {/* Firewall Status */}
      {snapshot?.firewall && (
        <ConfigSection
          title="Firewall Status"
          icon={Shield}
          expanded={false}
        >
          <div className="text-sm">
            <div className="mb-2">
              <span className="font-medium">Status:</span> {snapshot.firewall.enabled ? 'Enabled' : 'Disabled'}
            </div>
            {snapshot.firewall.rules?.length > 0 && (
              <div>
                <span className="font-medium">Rules:</span> {snapshot.firewall.rules.length} configured
              </div>
            )}
          </div>
        </ConfigSection>
      )}

      {/* Interface Statistics */}
      {snapshot?.ifstats?.length > 0 && (
        <ConfigSection
          title="Interface Statistics"
          icon={Activity}
          expanded={false}
        >
          <div className="space-y-2">
            {snapshot.ifstats.map((stat, i) => (
              <div key={i} className="bg-gray-50 p-2 rounded text-sm">
                <div className="font-medium">{stat.interface}</div>
                <div className="grid grid-cols-2 gap-2 text-xs mt-1">
                  <div>RX: {stat.stats?.rx_bytes || 0} bytes</div>
                  <div>TX: {stat.stats?.tx_bytes || 0} bytes</div>
                  <div>RX Packets: {stat.stats?.rx_packets || 0}</div>
                  <div>TX Packets: {stat.stats?.tx_packets || 0}</div>
                </div>
              </div>
            ))}
          </div>
        </ConfigSection>
      )}
    </div>
  );
};