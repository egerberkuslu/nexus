// SwitchConfigTab.jsx - Enhanced with multi-switch support from backend API
import React, { useState, useEffect } from 'react';
import {
  Wifi, Settings, Server, Activity, Save, Eye, Network, Shield, Layers,
  Cpu, Zap, Globe, Database
} from 'lucide-react';
import { InputField, SelectField, CheckboxField, EmptyState } from '../components/FormComponents';
import ActionButton from '../components/ActionButton';
import ConfigSection from '../components/ConfigSection';

// Switch types from backend API
const SWITCH_TYPES = {
  ovs: {
    name: 'Open vSwitch',
    description: 'Full-featured virtual switch with OpenFlow support',
    icon: Network,
    protocol: 'OpenFlow',
    defaultConfig: {
      protocols: 'OpenFlow13',
      fail_mode: 'secure',
      dpid: ''
    },
    features: ['OpenFlow', 'QOS', 'Mirroring', 'NetFlow'],
    color: 'bg-blue-600'
  },
  linux_bridge: {
    name: 'Linux Bridge',
    description: 'Simple Linux bridge without SDN controller',
    icon: Server,
    protocol: 'N/A',
    defaultConfig: {
      stp: false,
      priority: 32768
    },
    features: ['STP', 'VLAN', 'Bonding'],
    color: 'bg-green-600'
  },
  p4: {
    name: 'P4 Switch',
    description: 'Programmable data plane switch with P4Runtime',
    icon: Cpu,
    protocol: 'P4Runtime',
    defaultConfig: {
      program_name: 'basic_forwarding',
      grpc_port: 50051,
      p4info_path: ''
    },
    features: ['Runtime Programming', 'Table Entries', 'P4Runtime'],
    color: 'bg-purple-600'
  }
};

export const SwitchConfigTab = ({
  selectedNode,
  config,
  updateConfig,
  loading: parentLoading = false,
  setLoading = () => {},
  showMessage = () => {},
  apiCall = () => {},
  onNetworkChange = () => {}
}) => {
  const [sections, setSections] = useState({
    switchType: true,
    ovsConfig: false,
    linuxBridgeConfig: false,
    p4Config: false,
    controller: false,
    flows: false,
    status: false
  });

  const [localConfig, setLocalConfig] = useState({
    switchType: 'ovs',
    ovs: {
      protocols: 'OpenFlow13',
      fail_mode: 'secure',
      dpid: '',
      controller_ip: '127.0.0.1',
      controller_port: 6633
    },
    linux_bridge: {
      stp: false,
      priority: 32768,
      ageing_time: 300
    },
    p4: {
      program_name: 'basic_forwarding',
      grpc_port: 50051,
      p4info_path: '',
      device_id: 1
    }
  });

  // Available switch types from backend
  const [availableSwitchTypes, setAvailableSwitchTypes] = useState([]);
  const [switchTemplates, setSwitchTemplates] = useState({});

  // Default values for hooks that will be replaced with props
  const snapshot = null;
  const snapshotLoading = false;
  const applyLoading = false;
  const refreshSnapshot = () => {};
  const applyConfig = async () => ({ success: false });
  const buildSwitchConfig = () => ({});

  const loading = parentLoading || snapshotLoading || applyLoading;

  const toggleSection = (section) => {
    setSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Fetch available switch types from backend API
  const fetchAvailableSwitchTypes = async () => {
    try {
      const response = await apiCall('/api/switch/available');
      if (response.success && response.data) {
        setAvailableSwitchTypes(response.data.switch_types || []);
        setSwitchTemplates(response.data.templates || {});
      }
    } catch (error) {
      console.error('Failed to fetch available switch types:', error);
    }
  };

  // Fetch P4 templates from backend
  const fetchP4Templates = async () => {
    try {
      const response = await apiCall('/api/switch/p4/templates');
      if (response.success && response.data) {
        setLocalConfig(prev => ({
          ...prev,
          p4: {
            ...prev.p4,
            availablePrograms: response.data.templates || []
          }
        }));
      }
    } catch (error) {
      console.error('Failed to fetch P4 templates:', error);
    }
  };

  // Initialize and fetch data
  useEffect(() => {
    fetchAvailableSwitchTypes();
    fetchP4Templates();
  }, []);

  // Auto-refresh snapshot every 5 seconds
  useEffect(() => {
    if (selectedNode && selectedNode.type === 'switch') {
      const interval = setInterval(() => {
        refreshSnapshot();
      }, 5000);

      return () => clearInterval(interval);
    }
  }, [selectedNode, refreshSnapshot]);

  // Update local config from snapshot
  useEffect(() => {
    if (snapshot && snapshot.type === 'switch') {
      const switchType = snapshot.switch_type || 'ovs';

      // Parse controller from snapshot for Open vSwitch
      let controllerIP = '127.0.0.1';
      let controllerPort = 6633;

      if (snapshot.summary?.controller) {
        const match = snapshot.summary.controller.match(/tcp:([^:]+):(\d+)/);
        if (match) {
          controllerIP = match[1];
          controllerPort = parseInt(match[2]);
        }
      }

      setLocalConfig(prev => ({
        ...prev,
        switchType,
        [switchType]: {
          ...prev[switchType],
          protocols: snapshot.openflow?.version || 'OpenFlow13',
          fail_mode: snapshot.summary?.fail_mode || 'secure',
          controller_ip: controllerIP,
          controller_port: controllerPort,
          dpid: snapshot.openflow?.dpid || '',
          ...config
        }
      }));
    }
  }, [snapshot, config]);

  const applyConfiguration = async () => {
    if (!selectedNode) return;
    setLoading(true);
    
    try {
      // Build configuration spec
      const spec = buildSwitchConfig(selectedNode.id, localConfig);
      
      // Apply configuration
      const result = await applyConfig(spec);
      
      if (result.success) {
        const successCount = result.applied || 0;
        const failCount = result.failed || 0;
        
        if (failCount === 0) {
          showMessage('✅ Switch configuration applied successfully', 'success');
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
      showMessage(`❌ ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const clearFlows = async () => {
    if (!selectedNode) return;
    
    setLoading(true);
    try {
      // Use apply-config to execute ovs-ofctl del-flows command
      const spec = {
        switches: {}
      };
      spec.switches[selectedNode.id] = {
        commands: [`ovs-ofctl del-flows ${selectedNode.id}`]
      };
      
      const result = await applyConfig(spec);
      if (result.success) {
        showMessage('✅ Flow table cleared successfully', 'success');
        await refreshSnapshot();
      } else {
        showMessage('❌ Failed to clear flows', 'error');
      }
    } catch (error) {
      showMessage(`❌ Error clearing flows: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const addTestFlow = async () => {
    if (!selectedNode) return;
    
    setLoading(true);
    try {
      // Add a simple test flow that forwards all traffic normally
      const spec = {
        switches: {}
      };
      spec.switches[selectedNode.id] = {
        commands: [`ovs-ofctl add-flow ${selectedNode.id} "priority=100,actions=NORMAL" -O OpenFlow13`]
      };
      
      const result = await applyConfig(spec);
      if (result.success) {
        showMessage('✅ Test flow added successfully', 'success');
        await refreshSnapshot();
      } else {
        showMessage('❌ Failed to add test flow', 'error');
      }
    } catch (error) {
      showMessage(`❌ Error adding test flow: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleConfigChange = (switchType, field, value) => {
    const newConfig = {
      ...localConfig,
      switchType,
      [switchType]: {
        ...localConfig[switchType],
        [field]: value
      }
    };
    setLocalConfig(newConfig);
    updateConfig(newConfig);
  };

  const handleSwitchTypeChange = (newType) => {
    setLocalConfig(prev => ({ ...prev, switchType: newType }));
    updateConfig({ ...localConfig, switchType: newType });

    // Auto-expand the configuration section for the selected switch type
    setSections(prev => ({
      ...prev,
      ovsConfig: newType === 'ovs',
      linuxBridgeConfig: newType === 'linux_bridge',
      p4Config: newType === 'p4'
    }));
  };

  if (!selectedNode || selectedNode.type !== 'switch') {
    return (
      <div className="p-8">
        <EmptyState
          title="No Switch Selected"
          description="Please select a switch node from the Overview tab to configure."
        />
      </div>
    );
  }

  // Extract current status from snapshot
  const currentStatus = {
    controller: snapshot?.summary?.controller || 'Not configured',
    fail_mode: snapshot?.summary?.fail_mode || 'Unknown',
    dpid: snapshot?.openflow?.dpid || 'Auto-generated',
    openflow_version: snapshot?.openflow?.version || 'Unknown',
    connected: snapshot?.connections?.status === 'connected',
    flowCount: snapshot?.flows?.count || 0,
    flows: snapshot?.flows?.entries || [],
    portStats: snapshot?.port_statistics || {}
  };

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-purple-600 text-white rounded-xl">
            <Wifi size={20} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">Configure Switch</h2>
            <p className="text-gray-600">{selectedNode.id}</p>
          </div>
        </div>
        <ActionButton
          onClick={applyConfiguration}
          loading={loading}
          icon={<Save size={16} />}
          label="Apply Configuration"
        />
      </div>

      {/* Switch Status - From Snapshot */}
      <ConfigSection
        title="Current Switch Status"
        icon={Activity}
        expanded={sections.status}
        onToggle={() => toggleSection('status')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="text-sm font-medium text-gray-600">Controller</label>
            <p className="font-mono text-sm text-gray-900 break-all">
              {currentStatus.controller}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">OpenFlow Version</label>
            <p className="font-mono text-sm text-gray-900">
              {currentStatus.openflow_version}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Fail Mode</label>
            <p className="font-mono text-sm text-gray-900">
              {currentStatus.fail_mode}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Connection Status</label>
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${currentStatus.connected ? 'bg-green-500' : 'bg-red-500'}`} />
              <p className="font-mono text-sm text-gray-900">
                {currentStatus.connected ? 'Connected' : 'Disconnected'}
              </p>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">DPID</label>
            <p className="font-mono text-sm text-gray-900">
              {currentStatus.dpid}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Flow Count</label>
            <p className="font-mono text-sm text-gray-900">
              {currentStatus.flowCount} flows
            </p>
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <ActionButton
            onClick={refreshSnapshot}
            loading={loading}
            icon={<Activity size={16} />}
            label="Refresh Status"
            variant="secondary"
            size="sm"
          />
        </div>
      </ConfigSection>

      {/* Switch Type Selection */}
      <ConfigSection
        title="Switch Type Selection"
        icon={Settings}
        expanded={sections.switchType}
        onToggle={() => toggleSection('switchType')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {availableSwitchTypes.length > 0 ? (
            availableSwitchTypes.map((switchType) => {
              const switchInfo = SWITCH_TYPES[switchType.id] || {
                name: switchType.name,
                description: switchType.description,
                icon: Server,
                protocol: switchType.protocol,
                features: switchType.features || [],
                color: 'bg-gray-600'
              };
              const Icon = switchInfo.icon;

              return (
                <div
                  key={switchType.id}
                  className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${
                    localConfig.switchType === switchType.id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                  onClick={() => handleSwitchTypeChange(switchType.id)}
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className={`p-2 rounded-lg ${switchInfo.color} text-white`}>
                      <Icon size={20} />
                    </div>
                    <div>
                      <h4 className="font-semibold text-gray-900">{switchInfo.name}</h4>
                      <p className="text-sm text-gray-600">{switchInfo.description}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1 mb-2">
                    <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
                      Protocol: {switchInfo.protocol}
                    </span>
                    {switchInfo.features.slice(0, 3).map((feature, i) => (
                      <span key={i} className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">
                        {feature}
                      </span>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500">
                    Status: {switchType.available ? 'Available' : 'Not Available'}
                  </p>
                </div>
              );
            })
          ) : (
            // Fallback to static switch types if API not available
            Object.entries(SWITCH_TYPES).map(([key, switchInfo]) => {
              const Icon = switchInfo.icon;
              return (
                <div
                  key={key}
                  className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${
                    localConfig.switchType === key
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                  }`}
                  onClick={() => handleSwitchTypeChange(key)}
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className={`p-2 rounded-lg ${switchInfo.color} text-white`}>
                      <Icon size={20} />
                    </div>
                    <div>
                      <h4 className="font-semibold text-gray-900">{switchInfo.name}</h4>
                      <p className="text-sm text-gray-600">{switchInfo.description}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1 mb-2">
                    <span className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
                      Protocol: {switchInfo.protocol}
                    </span>
                    {switchInfo.features.slice(0, 3).map((feature, i) => (
                      <span key={i} className="px-2 py-1 bg-blue-100 text-blue-700 text-xs rounded">
                        {feature}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </ConfigSection>

      {/* Open vSwitch Configuration */}
      {localConfig.switchType === 'ovs' && (
        <ConfigSection
          title="Open vSwitch Configuration"
          icon={SWITCH_TYPES.ovs.icon}
          expanded={sections.ovsConfig}
          onToggle={() => toggleSection('ovsConfig')}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <SelectField
              label="OpenFlow Protocol"
              value={localConfig.ovs.protocols}
              onChange={val => handleConfigChange('ovs', 'protocols', val)}
              options={[
                { value: 'OpenFlow10', label: 'OpenFlow 1.0' },
                { value: 'OpenFlow11', label: 'OpenFlow 1.1' },
                { value: 'OpenFlow12', label: 'OpenFlow 1.2' },
                { value: 'OpenFlow13', label: 'OpenFlow 1.3' },
                { value: 'OpenFlow14', label: 'OpenFlow 1.4' },
                { value: 'OpenFlow15', label: 'OpenFlow 1.5' }
              ]}
              helper={`Current: ${currentStatus.openflow_version}`}
            />
            <SelectField
              label="Fail Mode"
              value={localConfig.ovs.fail_mode}
              onChange={val => handleConfigChange('ovs', 'fail_mode', val)}
              options={[
                { value: 'secure', label: 'Secure (Drop packets)' },
                { value: 'standalone', label: 'Standalone (Forward packets)' }
              ]}
              helper={`Current: ${currentStatus.fail_mode}`}
            />
            <InputField
              label="DPID (Datapath ID)"
              value={localConfig.ovs.dpid}
              onChange={val => handleConfigChange('ovs', 'dpid', val)}
              placeholder={currentStatus.dpid || "0000000000000001"}
              helper={`Current: ${currentStatus.dpid}`}
            />
            <InputField
              label="Controller IP"
              value={localConfig.ovs.controller_ip}
              onChange={val => handleConfigChange('ovs', 'controller_ip', val)}
              placeholder="127.0.0.1"
              helper="IP address of the OpenFlow controller"
            />
            <InputField
              label="Controller Port"
              type="number"
              value={localConfig.ovs.controller_port}
              onChange={val => handleConfigChange('ovs', 'controller_port', parseInt(val) || 6633)}
              placeholder="6633"
              helper="Port number for OpenFlow communication"
            />
          </div>
        </ConfigSection>
      )}

      {/* Linux Bridge Configuration */}
      {localConfig.switchType === 'linux_bridge' && (
        <ConfigSection
          title="Linux Bridge Configuration"
          icon={SWITCH_TYPES.linux_bridge.icon}
          expanded={sections.linuxBridgeConfig}
          onToggle={() => toggleSection('linuxBridgeConfig')}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <CheckboxField
              label="Enable Spanning Tree Protocol (STP)"
              checked={localConfig.linux_bridge.stp}
              onChange={val => handleConfigChange('linux_bridge', 'stp', val)}
              helper="Prevents network loops in redundant topologies"
            />
            <InputField
              label="Bridge Priority"
              type="number"
              value={localConfig.linux_bridge.priority}
              onChange={val => handleConfigChange('linux_bridge', 'priority', parseInt(val) || 32768)}
              placeholder="32768"
              helper="Lower values have higher priority (0-65535)"
            />
            <InputField
              label="Ageing Time (seconds)"
              type="number"
              value={localConfig.linux_bridge.ageing_time}
              onChange={val => handleConfigChange('linux_bridge', 'ageing_time', parseInt(val) || 300)}
              placeholder="300"
              helper="Time before MAC address entries expire"
            />
          </div>
        </ConfigSection>
      )}

      {/* P4 Switch Configuration */}
      {localConfig.switchType === 'p4' && (
        <ConfigSection
          title="P4 Switch Configuration"
          icon={SWITCH_TYPES.p4.icon}
          expanded={sections.p4Config}
          onToggle={() => toggleSection('p4Config')}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <SelectField
              label="P4 Program"
              value={localConfig.p4.program_name}
              onChange={val => handleConfigChange('p4', 'program_name', val)}
              options={
                localConfig.p4.availablePrograms?.map(program => ({
                  value: program.name,
                  label: program.name
                })) || [
                  { value: 'basic_forwarding', label: 'Basic Forwarding' },
                  { value: 'firewall', label: 'Firewall' },
                  { value: 'l3_forwarding', label: 'L3 Forwarding' }
                ]
              }
              helper="Select the P4 program to load"
            />
            <InputField
              label="gRPC Port"
              type="number"
              value={localConfig.p4.grpc_port}
              onChange={val => handleConfigChange('p4', 'grpc_port', parseInt(val) || 50051)}
              placeholder="50051"
              helper="Port for P4Runtime gRPC communication"
            />
            <InputField
              label="P4Info Path"
              value={localConfig.p4.p4info_path}
              onChange={val => handleConfigChange('p4', 'p4info_path', val)}
              placeholder="/path/to/program.p4info"
              helper="Path to the P4Info file"
            />
            <InputField
              label="Device ID"
              type="number"
              value={localConfig.p4.device_id}
              onChange={val => handleConfigChange('p4', 'device_id', parseInt(val) || 1)}
              placeholder="1"
              helper="Unique identifier for this P4 device"
            />
          </div>
        </ConfigSection>
      )}

      {/* Controller Connection (for Open vSwitch only) */}
      {localConfig.switchType === 'ovs' && (
        <ConfigSection
          title="Controller Connection"
          icon={Network}
          expanded={sections.controller}
          onToggle={() => toggleSection('controller')}
        >
          <div className="mb-4">
            <p className="text-sm text-gray-600">
              Current controller: {currentStatus.controller}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <InputField
              label="Controller IP"
              value={localConfig.ovs.controller_ip}
              onChange={val => handleConfigChange('ovs', 'controller_ip', val)}
              placeholder="127.0.0.1"
              icon={Network}
              helper="IP address of the OpenFlow controller"
            />
            <InputField
              label="Controller Port"
              type="number"
              value={localConfig.ovs.controller_port}
              onChange={val => handleConfigChange('ovs', 'controller_port', parseInt(val) || 6633)}
              placeholder="6633"
              icon={Server}
              helper="Port number for OpenFlow communication"
            />
          </div>
        </ConfigSection>
      )}

      {/* Flow Table Management */}
      <ConfigSection
        title="Flow Table Management"
        icon={Activity}
        expanded={sections.flows}
        onToggle={() => toggleSection('flows')}
      >
        <div className="space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <p className="text-sm text-gray-600">
                Flow entries are managed by the OpenFlow controller.
              </p>
              <p className="text-sm font-medium text-gray-900">
                Current flows: {currentStatus.flowCount}
              </p>
            </div>
            <div className="flex gap-2">
              <ActionButton
                onClick={refreshSnapshot}
                loading={loading}
                icon={<Eye size={16} />}
                label="Refresh Flows"
                variant="secondary"
                size="sm"
              />
              <ActionButton
                onClick={addTestFlow}
                loading={loading}
                icon={<Activity size={16} />}
                label="Add Test Flow"
                variant="secondary"
                size="sm"
              />
              <ActionButton
                onClick={clearFlows}
                loading={loading}
                icon={<Activity size={16} />}
                label="Clear Flows"
                variant="danger"
                size="sm"
              />
            </div>
          </div>

          {currentStatus.flows.length > 0 ? (
            <div>
              <label className="text-sm font-medium text-gray-600">Current Flow Entries</label>
              <div className="bg-gray-100 p-3 rounded mt-2 max-h-64 overflow-y-auto">
                {currentStatus.flows.map((flow, index) => (
                  <div key={index} className="font-mono text-xs mb-2 p-2 bg-white rounded">
                    {typeof flow === 'object' ? (
                      <div>
                        <div>Priority: {flow.priority || 'N/A'}</div>
                        <div>Match: {JSON.stringify(flow.match || {})}</div>
                        <div>Actions: {JSON.stringify(flow.actions || [])}</div>
                        {flow.packets !== undefined && (
                          <div>Packets: {flow.packets}, Bytes: {flow.bytes || 0}</div>
                        )}
                      </div>
                    ) : (
                      flow
                    )}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="text-center py-4 bg-gray-50 rounded">
              <p className="text-gray-500">No flow entries found</p>
              <p className="text-xs text-gray-400 mt-1">
                Flow entries will appear here when the controller is connected and traffic is processed
              </p>
            </div>
          )}

          {/* Port Statistics */}
          {Object.keys(currentStatus.portStats).length > 0 && (
            <div>
              <label className="text-sm font-medium text-gray-600">Port Statistics</label>
              <div className="bg-gray-100 p-3 rounded mt-2">
                {Object.entries(currentStatus.portStats).map(([port, stats]) => (
                  <div key={port} className="mb-2 text-xs">
                    <div className="font-medium">Port {port}</div>
                    <div className="grid grid-cols-2 gap-2 mt-1">
                      <div>RX Packets: {stats.rx_packets || 0}</div>
                      <div>TX Packets: {stats.tx_packets || 0}</div>
                      <div>RX Bytes: {stats.rx_bytes || 0}</div>
                      <div>TX Bytes: {stats.tx_bytes || 0}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </ConfigSection>

      {/* Configuration Summary */}
      <div className="bg-blue-50 rounded-lg p-4">
        <h4 className="font-medium text-blue-900 mb-2">Configuration Summary</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
          <div>
            <span className="text-blue-700">Switch Type:</span>
            <span className="ml-2 font-mono">{SWITCH_TYPES[localConfig.switchType]?.name || 'Unknown'}</span>
          </div>
          {localConfig.switchType === 'ovs' && (
            <>
              <div>
                <span className="text-blue-700">OpenFlow Protocol:</span>
                <span className="ml-2 font-mono">{localConfig.ovs.protocols}</span>
              </div>
              <div>
                <span className="text-blue-700">Fail Mode:</span>
                <span className="ml-2 font-mono">{localConfig.ovs.fail_mode}</span>
              </div>
              <div>
                <span className="text-blue-700">Controller:</span>
                <span className="ml-2 font-mono">{localConfig.ovs.controller_ip}:{localConfig.ovs.controller_port}</span>
              </div>
              <div>
                <span className="text-blue-700">DPID:</span>
                <span className="ml-2 font-mono">{localConfig.ovs.dpid || 'Auto-generated'}</span>
              </div>
            </>
          )}
          {localConfig.switchType === 'linux_bridge' && (
            <>
              <div>
                <span className="text-blue-700">STP Enabled:</span>
                <span className="ml-2 font-mono">{localConfig.linux_bridge.stp ? 'Yes' : 'No'}</span>
              </div>
              <div>
                <span className="text-blue-700">Priority:</span>
                <span className="ml-2 font-mono">{localConfig.linux_bridge.priority}</span>
              </div>
              <div>
                <span className="text-blue-700">Ageing Time:</span>
                <span className="ml-2 font-mono">{localConfig.linux_bridge.ageing_time}s</span>
              </div>
            </>
          )}
          {localConfig.switchType === 'p4' && (
            <>
              <div>
                <span className="text-blue-700">P4 Program:</span>
                <span className="ml-2 font-mono">{localConfig.p4.program_name}</span>
              </div>
              <div>
                <span className="text-blue-700">gRPC Port:</span>
                <span className="ml-2 font-mono">{localConfig.p4.grpc_port}</span>
              </div>
              <div>
                <span className="text-blue-700">Device ID:</span>
                <span className="ml-2 font-mono">{localConfig.p4.device_id}</span>
              </div>
              <div>
                <span className="text-blue-700">P4Info Path:</span>
                <span className="ml-2 font-mono">{localConfig.p4.p4info_path || 'Default'}</span>
              </div>
            </>
          )}
        </div>

        {/* Switch Features Summary */}
        <div className="mt-3">
          <span className="text-sm text-blue-700">Supported Features:</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {SWITCH_TYPES[localConfig.switchType]?.features.map((feature, i) => (
              <span key={i} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
                {feature}
              </span>
            ))}
          </div>
        </div>

        {localConfig.switchType === 'ovs' && !currentStatus.connected && (
          <div className="mt-3 p-2 bg-yellow-100 rounded text-yellow-800 text-sm">
            ⚠️ Switch is not connected to controller. Check controller status and network connectivity.
          </div>
        )}

        {localConfig.switchType !== 'ovs' && (
          <div className="mt-3 p-2 bg-green-100 rounded text-green-800 text-sm">
            ✅ {SWITCH_TYPES[localConfig.switchType]?.name} is a standalone switch type that doesn't require a controller.
          </div>
        )}
      </div>
    </div>
  );
};