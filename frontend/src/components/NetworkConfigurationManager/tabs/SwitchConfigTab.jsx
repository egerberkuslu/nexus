// SwitchConfigTab.jsx - Using bulk configuration and snapshots
import React, { useState, useEffect } from 'react';
import {
  Wifi, Settings, Server, Activity, Save, Eye, Network, Shield, Layers
} from 'lucide-react';
import { InputField, SelectField, EmptyState } from '../components/FormComponents';
import ActionButton from '../components/ActionButton';
import ConfigSection from '../components/ConfigSection';
import { useDeviceSnapshot, useApplyConfig } from '../hooks/useNetworkManagement';

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
    openflow: true,
    controller: false,
    flows: false,
    status: false
  });

  const [localConfig, setLocalConfig] = useState({
    openflow_version: '1.3',
    fail_mode: 'secure',
    controller_ip: '127.0.0.1',
    controller_port: 6633,
    dpid: ''
  });

  // Use the new hooks
  const { snapshot, loading: snapshotLoading, refreshSnapshot } = useDeviceSnapshot(selectedNode?.id);
  const { applyConfig, buildSwitchConfig, loading: applyLoading } = useApplyConfig();

  const loading = parentLoading || snapshotLoading || applyLoading;

  const toggleSection = (section) => {
    setSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

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
      // Parse controller from snapshot
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
        openflow_version: snapshot.openflow?.version || '1.3',
        fail_mode: snapshot.summary?.fail_mode || 'secure',
        controller_ip: controllerIP,
        controller_port: controllerPort,
        dpid: snapshot.openflow?.dpid || '',
        ...config
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

  const handleConfigChange = (field, value) => {
    const newConfig = { ...localConfig, [field]: value };
    setLocalConfig(newConfig);
    updateConfig(newConfig);
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

      {/* OpenFlow Settings */}
      <ConfigSection
        title="OpenFlow Configuration"
        icon={Settings}
        expanded={sections.openflow}
        onToggle={() => toggleSection('openflow')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <SelectField
            label="OpenFlow Version"
            value={localConfig.openflow_version}
            onChange={val => handleConfigChange('openflow_version', val)}
            options={[
              { value: '1.0', label: 'OpenFlow 1.0' },
              { value: '1.1', label: 'OpenFlow 1.1' },
              { value: '1.2', label: 'OpenFlow 1.2' },
              { value: '1.3', label: 'OpenFlow 1.3' },
              { value: '1.4', label: 'OpenFlow 1.4' }
            ]}
            icon={Layers}
            helper={`Current: ${currentStatus.openflow_version}`}
          />
          <SelectField
            label="Fail Mode"
            value={localConfig.fail_mode}
            onChange={val => handleConfigChange('fail_mode', val)}
            options={[
              { value: 'secure', label: 'Secure (Drop packets)' },
              { value: 'standalone', label: 'Standalone (Forward packets)' }
            ]}
            icon={Shield}
            helper={`Current: ${currentStatus.fail_mode} - Behavior when controller connection is lost`}
          />
          <InputField
            label="DPID (Datapath ID)"
            value={localConfig.dpid}
            onChange={val => handleConfigChange('dpid', val)}
            placeholder={currentStatus.dpid || "0000000000000001"}
            helper={`Current: ${currentStatus.dpid} - 16-digit hex identifier (optional)`}
          />
        </div>
      </ConfigSection>

      {/* Controller Settings */}
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
            value={localConfig.controller_ip}
            onChange={val => handleConfigChange('controller_ip', val)}
            placeholder="127.0.0.1"
            icon={Network}
            helper="IP address of the OpenFlow controller"
          />
          <InputField
            label="Controller Port"
            type="number"
            value={localConfig.controller_port}
            onChange={val => handleConfigChange('controller_port', parseInt(val) || 6633)}
            placeholder="6633"
            icon={Server}
            helper="Port number for OpenFlow communication"
          />
        </div>
      </ConfigSection>

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
            <span className="text-blue-700">OpenFlow Version:</span>
            <span className="ml-2 font-mono">{localConfig.openflow_version}</span>
          </div>
          <div>
            <span className="text-blue-700">Fail Mode:</span>
            <span className="ml-2 font-mono">{localConfig.fail_mode}</span>
          </div>
          <div>
            <span className="text-blue-700">Controller:</span>
            <span className="ml-2 font-mono">{localConfig.controller_ip}:{localConfig.controller_port}</span>
          </div>
          <div>
            <span className="text-blue-700">DPID:</span>
            <span className="ml-2 font-mono">{localConfig.dpid || 'Auto-generated'}</span>
          </div>
        </div>
        {!currentStatus.connected && (
          <div className="mt-2 p-2 bg-yellow-100 rounded text-yellow-800 text-sm">
            ⚠️ Switch is not connected to controller. Check controller status and network connectivity.
          </div>
        )}
      </div>
    </div>
  );
};