// SwitchConfigTab.jsx - Auto-updating with current status
import React, { useState, useEffect } from 'react';
import {
  Wifi, Settings, Server, Activity, Save, Eye, Network, Shield, Layers
} from 'lucide-react';
import { InputField, SelectField, EmptyState } from '../components/FormComponents';
import ActionButton from '../components/ActionButton';
import ConfigSection from '../components/ConfigSection';

export const SwitchConfigTab = ({
  selectedNode,
  config,
  updateConfig,
  loading = false,
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

  const [currentStatus, setCurrentStatus] = useState({
    controller: '',
    protocols: '',
    failMode: '',
    dpid: '',
    connected: false,
    flowCount: 0
  });

  const [realTimeConfig, setRealTimeConfig] = useState({
    openflow_version: '1.3',
    fail_mode: 'secure',
    controller_ip: '127.0.0.1',
    controller_port: 6633,
    dpid: ''
  });

  const [flowEntries, setFlowEntries] = useState([]);
  const [portStats, setPortStats] = useState('');

  const toggleSection = (section) => {
    setSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Auto-refresh data every 5 seconds when switch is selected
  useEffect(() => {
    if (selectedNode && selectedNode.type === 'switch') {
      fetchSwitchStatus();
      fetchFlowEntries();
      
      const interval = setInterval(() => {
        fetchSwitchStatus();
        fetchFlowEntries();
      }, 5000);
      
      return () => clearInterval(interval);
    }
  }, [selectedNode]);

  // Update config when selectedNode or config changes
  useEffect(() => {
    if (selectedNode && selectedNode.type === 'switch') {
      setRealTimeConfig(prev => ({
        ...prev,
        ...config
      }));
    }
  }, [selectedNode, config]);

  const executeCommand = async (command) => {
    if (!selectedNode) return { success: false, error: 'No switch selected' };

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

  const fetchSwitchStatus = async () => {
    if (!selectedNode) return;

    try {
      // Get switch controller configuration
      const controllerResult = await executeCommand(`ovs-vsctl get-controller ${selectedNode.id}`);
      let controllerInfo = 'Not configured';
      if (controllerResult.success && controllerResult.result.trim()) {
        controllerInfo = controllerResult.result.trim();
      }

      // Get OpenFlow protocols
      const protocolResult = await executeCommand(`ovs-vsctl get bridge ${selectedNode.id} protocols`);
      let protocols = 'Unknown';
      if (protocolResult.success && protocolResult.result.trim()) {
        protocols = protocolResult.result.trim().replace(/"/g, '');
      }

      // Get fail mode
      const failModeResult = await executeCommand(`ovs-vsctl get-fail-mode ${selectedNode.id}`);
      let failMode = 'Unknown';
      if (failModeResult.success && failModeResult.result.trim()) {
        failMode = failModeResult.result.trim();
      }

      // Get DPID
      const dpidResult = await executeCommand(`ovs-vsctl get bridge ${selectedNode.id} datapath_id`);
      let dpid = '';
      if (dpidResult.success && dpidResult.result.trim()) {
        dpid = dpidResult.result.trim().replace(/"/g, '');
      }

      // Check connection status with ovs-vsctl show
      const showResult = await executeCommand(`ovs-vsctl show`);
      let connected = false;
      if (showResult.success) {
        connected = showResult.result.includes('is_connected: true');
      }

      // Get port statistics
      const portResult = await executeCommand(`ovs-ofctl dump-ports ${selectedNode.id} -O OpenFlow13`);
      if (portResult.success) {
        setPortStats(portResult.result);
      }

      // Parse controller info to update config
      if (controllerInfo.includes('tcp:')) {
        const match = controllerInfo.match(/tcp:([^:]+):(\d+)/);
        if (match) {
          setRealTimeConfig(prev => ({
            ...prev,
            controller_ip: match[1],
            controller_port: parseInt(match[2])
          }));
        }
      }

      // Parse protocols to update config
      if (protocols.includes('OpenFlow')) {
        const versionMatch = protocols.match(/OpenFlow(\d+)/);
        if (versionMatch) {
          const version = versionMatch[1];
          const formattedVersion = version.length === 2 ? `${version[0]}.${version[1]}` : version;
          setRealTimeConfig(prev => ({
            ...prev,
            openflow_version: formattedVersion
          }));
        }
      }

      // Update fail mode
      if (failMode !== 'Unknown') {
        setRealTimeConfig(prev => ({
          ...prev,
          fail_mode: failMode
        }));
      }

      // Update DPID
      if (dpid) {
        setRealTimeConfig(prev => ({
          ...prev,
          dpid: dpid
        }));
      }

      setCurrentStatus({
        controller: controllerInfo,
        protocols: protocols,
        failMode: failMode,
        dpid: dpid,
        connected: connected,
        flowCount: flowEntries.length
      });

      // Update parent config
      updateConfig({
        ...config,
        controller_ip: realTimeConfig.controller_ip,
        controller_port: realTimeConfig.controller_port,
        openflow_version: realTimeConfig.openflow_version,
        fail_mode: realTimeConfig.fail_mode,
        dpid: realTimeConfig.dpid
      });

    } catch (error) {
      console.error('Error fetching switch status:', error);
    }
  };

  const fetchFlowEntries = async () => {
    if (!selectedNode) return;

    try {
      // Try to get flow stats from the stats API first
      const response = await apiCall(`/stats/flows/${selectedNode.id}`);
      if (response.success && response.data.flows) {
        setFlowEntries(response.data.flows.detailed_flows || []);
        setCurrentStatus(prev => ({
          ...prev,
          flowCount: response.data.flows.detailed_flows?.length || 0
        }));
      } else {
        // Fallback to direct command execution
        const result = await executeCommand(`ovs-ofctl dump-flows ${selectedNode.id} -O OpenFlow13`);
        if (result.success) {
          const flows = result.result.split('\n').filter(line => 
            line.trim() && !line.startsWith('NXST_FLOW') && line.includes('cookie=')
          );
          setFlowEntries(flows);
          setCurrentStatus(prev => ({
            ...prev,
            flowCount: flows.length
          }));
        }
      }
    } catch (error) {
      console.error('Error fetching flow entries:', error);
    }
  };

  const applyConfig = async () => {
    if (!selectedNode) return;
    setLoading(true);
    
    try {
      const commands = [];
      let configChanged = false;

      // Set OpenFlow version if changed
      if (realTimeConfig.openflow_version && realTimeConfig.openflow_version !== currentStatus.protocols) {
        const version = realTimeConfig.openflow_version.replace('.', '');
        commands.push(`ovs-vsctl set bridge ${selectedNode.id} protocols=OpenFlow${version}`);
        configChanged = true;
      }

      // Set fail mode if changed
      if (realTimeConfig.fail_mode && realTimeConfig.fail_mode !== currentStatus.failMode) {
        commands.push(`ovs-vsctl set-fail-mode ${selectedNode.id} ${realTimeConfig.fail_mode}`);
        configChanged = true;
      }

      // Set controller if changed
      const newControllerString = `tcp:${realTimeConfig.controller_ip}:${realTimeConfig.controller_port}`;
      if (!currentStatus.controller.includes(newControllerString)) {
        commands.push(`ovs-vsctl set-controller ${selectedNode.id} ${newControllerString}`);
        configChanged = true;
      }

      // Set DPID if specified and different
      if (realTimeConfig.dpid && realTimeConfig.dpid !== 'auto' && realTimeConfig.dpid !== currentStatus.dpid) {
        commands.push(`ovs-vsctl set bridge ${selectedNode.id} other-config:datapath-id=${realTimeConfig.dpid}`);
        configChanged = true;
      }

      if (!configChanged) {
        showMessage('No configuration changes to apply', 'info');
        setLoading(false);
        return;
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

      if (successCount === commands.length) {
        showMessage('✅ Switch configuration applied successfully', 'success');
        // Refresh status after configuration
        setTimeout(() => {
          fetchSwitchStatus();
          onNetworkChange?.();
        }, 2000);
      } else {
        showMessage(`Applied ${successCount}/${commands.length} configuration commands`, 'warning');
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
      const result = await executeCommand(`ovs-ofctl del-flows ${selectedNode.id}`);
      if (result.success) {
        showMessage('Flow table cleared successfully', 'success');
        await fetchFlowEntries();
      } else {
        showMessage('Failed to clear flows', 'error');
      }
    } catch (error) {
      showMessage(`Error clearing flows: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const addTestFlow = async () => {
    if (!selectedNode) return;
    
    setLoading(true);
    try {
      // Add a simple test flow that forwards all traffic normally
      const command = `ovs-ofctl add-flow ${selectedNode.id} "priority=100,actions=NORMAL" -O OpenFlow13`;
      const result = await executeCommand(command);
      if (result.success) {
        showMessage('Test flow added successfully', 'success');
        await fetchFlowEntries();
      } else {
        showMessage('Failed to add test flow', 'error');
      }
    } catch (error) {
      showMessage(`Error adding test flow: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleConfigChange = (field, value) => {
    const newConfig = { ...realTimeConfig, [field]: value };
    setRealTimeConfig(newConfig);
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
          onClick={applyConfig}
          loading={loading}
          icon={<Save size={16} />}
          label="Apply Configuration"
        />
      </div>

      {/* Switch Status - Always visible with current info */}
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
              {currentStatus.controller || 'Not configured'}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">OpenFlow Version</label>
            <p className="font-mono text-sm text-gray-900">
              {currentStatus.protocols || 'Unknown'}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Fail Mode</label>
            <p className="font-mono text-sm text-gray-900">
              {currentStatus.failMode || 'Unknown'}
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
              {currentStatus.dpid || 'Auto-generated'}
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
            onClick={fetchSwitchStatus}
            loading={loading}
            icon={<Activity size={16} />}
            label="Refresh Status"
            variant="secondary"
            size="sm"
          />
          <ActionButton
            onClick={fetchFlowEntries}
            loading={loading}
            icon={<Eye size={16} />}
            label="Refresh Flows"
            variant="secondary"
            size="sm"
          />
        </div>
      </ConfigSection>

      {/* OpenFlow Settings - Pre-filled with current values */}
      <ConfigSection
        title="OpenFlow Configuration"
        icon={Settings}
        expanded={sections.openflow}
        onToggle={() => toggleSection('openflow')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <SelectField
            label="OpenFlow Version"
            value={realTimeConfig.openflow_version}
            onChange={val => handleConfigChange('openflow_version', val)}
            options={[
              { value: '1.0', label: 'OpenFlow 1.0' },
              { value: '1.1', label: 'OpenFlow 1.1' },
              { value: '1.2', label: 'OpenFlow 1.2' },
              { value: '1.3', label: 'OpenFlow 1.3' },
              { value: '1.4', label: 'OpenFlow 1.4' }
            ]}
            icon={Layers}
            helper={`Current: ${currentStatus.protocols || 'Unknown'}`}
          />
          <SelectField
            label="Fail Mode"
            value={realTimeConfig.fail_mode}
            onChange={val => handleConfigChange('fail_mode', val)}
            options={[
              { value: 'secure', label: 'Secure (Drop packets)' },
              { value: 'standalone', label: 'Standalone (Forward packets)' }
            ]}
            icon={Shield}
            helper={`Current: ${currentStatus.failMode || 'Unknown'} - Behavior when controller connection is lost`}
          />
          <InputField
            label="DPID (Datapath ID)"
            value={realTimeConfig.dpid}
            onChange={val => handleConfigChange('dpid', val)}
            placeholder={currentStatus.dpid || "0000000000000001"}
            helper={`Current: ${currentStatus.dpid || 'Auto-generated'} - 16-digit hex identifier (optional)`}
          />
        </div>
      </ConfigSection>

      {/* Controller Settings - Pre-filled with current values */}
      <ConfigSection
        title="Controller Connection"
        icon={Network}
        expanded={sections.controller}
        onToggle={() => toggleSection('controller')}
      >
        <div className="mb-4">
          <p className="text-sm text-gray-600">
            Current controller: {currentStatus.controller || 'None configured'}
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <InputField
            label="Controller IP"
            value={realTimeConfig.controller_ip}
            onChange={val => handleConfigChange('controller_ip', val)}
            placeholder="127.0.0.1"
            icon={Network}
            helper="IP address of the OpenFlow controller"
          />
          <InputField
            label="Controller Port"
            type="number"
            value={realTimeConfig.controller_port}
            onChange={val => handleConfigChange('controller_port', parseInt(val) || 6633)}
            placeholder="6633"
            icon={Server}
            helper="Port number for OpenFlow communication"
          />
        </div>
      </ConfigSection>

      {/* Flow Table Management - Shows current flows */}
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
                onClick={fetchFlowEntries}
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

          {flowEntries.length > 0 ? (
            <div>
              <label className="text-sm font-medium text-gray-600">Current Flow Entries</label>
              <div className="bg-gray-100 p-3 rounded mt-2 max-h-64 overflow-y-auto">
                {flowEntries.map((flow, index) => (
                  <div key={index} className="font-mono text-xs mb-1 p-1 bg-white rounded">
                    {flow}
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

          {portStats && (
            <div>
              <label className="text-sm font-medium text-gray-600">Port Statistics</label>
              <pre className="bg-gray-100 p-3 rounded text-xs mt-2 overflow-x-auto max-h-48">
                {portStats}
              </pre>
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
            <span className="ml-2 font-mono">{realTimeConfig.openflow_version}</span>
          </div>
          <div>
            <span className="text-blue-700">Fail Mode:</span>
            <span className="ml-2 font-mono">{realTimeConfig.fail_mode}</span>
          </div>
          <div>
            <span className="text-blue-700">Controller:</span>
            <span className="ml-2 font-mono">{realTimeConfig.controller_ip}:{realTimeConfig.controller_port}</span>
          </div>
          <div>
            <span className="text-blue-700">DPID:</span>
            <span className="ml-2 font-mono">{realTimeConfig.dpid || 'Auto-generated'}</span>
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