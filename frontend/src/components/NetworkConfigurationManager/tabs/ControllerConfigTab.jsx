// ControllerConfigTab.jsx - Enhanced with multi-controller support
import React, { useState, useEffect } from 'react';
import {
  Network, Settings, ToggleLeft, Power, RefreshCcw, Save, Activity,
  Cpu, Layers, Globe, Database, Zap
} from 'lucide-react';
import { InputField, SelectField, CheckboxField } from '../components/FormComponents';
import ActionButton from '../components/ActionButton';
import ConfigSection from '../components/ConfigSection';

// Controller configurations based on backend documentation
const CONTROLLER_TYPES = {
  ryu: {
    name: 'Ryu',
    description: 'Full-featured SDN controller with rich ecosystem',
    icon: Cpu,
    defaultPort: 6633,
    defaultApp: 'simple_switch_13',
    features: ['REST API', 'Clustering', 'Monitoring'],
    supportedVersions: ['1.0', '1.3', '1.5'],
    apps: ['simple_switch_13', 'hub', 'l2_learning', 'simple_monitor'],
    color: 'bg-blue-600'
  },
  pox: {
    name: 'POX',
    description: 'Educational SDN controller with scripting support',
    icon: Zap,
    defaultPort: 6633,
    defaultApp: 'l2_learning',
    features: ['Scripting', 'Extensible'],
    supportedVersions: ['1.0'],
    apps: ['l2_learning', 'hub', 'forwarding'],
    color: 'bg-purple-600'
  },
  osken: {
    name: 'OsKen',
    description: 'Lightweight SDN controller for research',
    icon: Layers,
    defaultPort: 6633,
    defaultApp: 'simple_switch',
    features: ['REST API', 'Lightweight'],
    supportedVersions: ['1.0', '1.3'],
    apps: ['simple_switch', 'hub', 'l2_switch'],
    color: 'bg-green-600'
  },
  opendaylight: {
    name: 'OpenDaylight',
    description: 'Enterprise-grade SDN controller with rich features',
    icon: Globe,
    defaultPort: 8181,
    defaultApp: 'default',
    features: ['REST API', 'Clustering', 'Monitoring', 'NetConf'],
    supportedVersions: ['1.0', '1.5'],
    apps: ['default', 'l2switch', 'odl-mdsal-apidocs'],
    color: 'bg-orange-600',
    restApiPort: 8181
  }
};

export const ControllerConfigTab = ({
  config,
  updateConfig,
  loading: parentLoading,
  setLoading,
  showMessage,
  apiCall,
  onNetworkChange,
  fetchStatus = () => {},
  startController = () => {},
  stopController = () => {},
  restartController = () => {},
  switchControllerApp = () => {},
  clearControllerLogs = () => {},
  controllerType = 'ryu',
  setControllerType = () => {},
  setControllerApp = () => {},
  switchControllerType = () => {},
  CONTROLLER_TYPES = {}
}) => {
  const [expandedSections, setExpandedSections] = useState({
    controllerType: true,
    ryuConfig: false,
    poxConfig: false,
    oskenConfig: false,
    opendaylightConfig: false,
    restAPI: false,
    clustering: false,
    status: false,
    apps: false,
    logs: false
  });

  const [localConfig, setLocalConfig] = useState({
    controllerType: 'ryu',
    ryu: {
      app: 'simple_switch_13',
      port: 6633,
      ip: '127.0.0.1',
      log_level: 'INFO',
      rest_api_enabled: true,
      rest_api_port: 8080,
      clustering_enabled: false
    },
    pox: {
      app: 'l2_learning',
      port: 6633,
      ip: '127.0.0.1',
      log_level: 'INFO'
    },
    osken: {
      app: 'simple_switch',
      port: 6633,
      ip: '127.0.0.1',
      log_level: 'INFO',
      rest_api_enabled: false,
      rest_api_port: 8080
    },
    opendaylight: {
      app: 'default',
      port: 8181,
      ip: '127.0.0.1',
      log_level: 'INFO',
      clustering_enabled: true,
      netconf_enabled: true
    }
  });

  const [availableApps, setAvailableApps] = useState([]);
  const [controllerLogs, setControllerLogs] = useState([]);

  // Controller status and functions come from props
  const controllerStatus = { running: false }; // Default status
  const controllerLoading = false;

  const loading = parentLoading || controllerLoading;

  const toggle = section => setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));

  // Auto-refresh data every 3 seconds
  useEffect(() => {
    fetchAvailableApps();
    
    const interval = setInterval(() => {
      fetchStatus();
      if (controllerStatus?.running) {
        fetchControllerLogs();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [fetchStatus, controllerStatus?.running]);

  // Update config when status changes
  useEffect(() => {
    if (controllerStatus) {
      setLocalConfig(prev => ({
        ...prev,
        type: controllerStatus.controller_type || prev.type,
        port: controllerStatus.port || prev.port,
        ip: controllerStatus.ip || prev.ip,
        log_level: controllerStatus.log_level || prev.log_level,
        ...config
      }));
    }
  }, [controllerStatus, config]);

  const fetchAvailableApps = async () => {
    try {
      const response = await apiCall('/api/controller/apps');
      if (response.success) {
        setAvailableApps(response.data.apps || []);
      }
    } catch (error) {
      console.error('Failed to fetch available apps:', error);
    }
  };

  const fetchControllerLogs = async () => {
    try {
      const response = await apiCall('/api/controller/logs?lines=20');
      if (response.success) {
        if (Array.isArray(response.data)) {
          setControllerLogs(response.data);
        } else if (typeof response.data === 'string') {
          setControllerLogs(response.data.split('\n').filter(line => line.trim()));
        } else if (response.data && response.data.logs) {
          setControllerLogs(Array.isArray(response.data.logs) ? response.data.logs : []);
        }
      }
    } catch (error) {
      console.error('Failed to fetch controller logs:', error);
    }
  };

  const applyConfig = async () => {
    setLoading(true);
    try {
      const response = await apiCall('/api/controller/config', {
        method: 'POST',
        body: JSON.stringify(localConfig)
      });

      if (response.success) {
        showMessage('✅ Controller configuration applied successfully', 'success');
        await fetchStatus();
        onNetworkChange?.();
      } else {
        showMessage(`❌ ${response.error}`, 'error');
      }
    } catch (err) {
      showMessage(`❌ ${err.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleStartController = async () => {
    try {
      await startController({ 
        type: localConfig.type, 
        port: localConfig.port 
      });
      showMessage('✅ Controller started successfully', 'success');
      onNetworkChange?.();
    } catch (err) {
      showMessage(`❌ Failed to start controller: ${err.message}`, 'error');
    }
  };

  const handleStopController = async () => {
    try {
      await stopController();
      showMessage('🛑 Controller stopped successfully', 'success');
      setControllerLogs([]);
      onNetworkChange?.();
    } catch (err) {
      showMessage(`❌ Failed to stop controller: ${err.message}`, 'error');
    }
  };

  const handleRestartController = async () => {
    try {
      await restartController();
      showMessage('🔁 Controller restarted successfully', 'success');
      onNetworkChange?.();
    } catch (err) {
      showMessage(`❌ Failed to restart controller: ${err.message}`, 'error');
    }
  };





  const handleConfigChange = (controllerType, field, value) => {
    const newConfig = {
      ...localConfig,
      controllerType,
      [controllerType]: {
        ...localConfig[controllerType],
        [field]: value
      }
    };
    setLocalConfig(newConfig);
    updateConfig(newConfig);
  };

  const handleControllerTypeChange = (newType) => {
    setLocalConfig(prev => ({ ...prev, controllerType: newType }));
    updateConfig({ ...localConfig, controllerType: newType });
  };

  // Get status display
  const getStatusDisplay = () => {
    if (controllerStatus?.running) {
      return {
        color: 'text-green-600',
        text: 'Running',
        bgColor: 'bg-green-100'
      };
    } else {
      return {
        color: 'text-red-600',
        text: 'Stopped',
        bgColor: 'bg-red-100'
      };
    }
  };

  const statusDisplay = getStatusDisplay();
  const currentController = CONTROLLER_TYPES[localConfig.controllerType];

  // Default values for controller snapshot data
  const controllerSnapshot = null;
  const connectedSwitches = [];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-red-600 text-white rounded-xl">
            <Network size={20} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-900">Configure Controller</h2>
            <p className="text-gray-600">Set up your SDN controller node</p>
          </div>
        </div>
        <ActionButton
          onClick={applyConfig}
          loading={loading}
          icon={<Save size={16} />}
          label="Apply Configuration"
        />
      </div>

      {/* Controller Status */}
      <div className={`${statusDisplay.bgColor} rounded-lg p-4`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${controllerStatus?.running ? 'bg-green-500' : 'bg-red-500'}`} />
            <h3 className="font-semibold text-gray-900">Controller Status</h3>
          </div>
          <ActionButton
            onClick={fetchStatus}
            loading={loading}
            icon={<RefreshCcw size={14} />}
            label="Refresh"
            variant="secondary"
            size="sm"
          />
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="text-sm font-medium text-gray-600">Status</label>
            <p className={`font-semibold ${statusDisplay.color}`}>
              {statusDisplay.text}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Type</label>
            <p className="font-semibold text-gray-900">
              {controllerStatus?.controller_type || 'Unknown'}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Address</label>
            <p className="font-semibold text-gray-900 font-mono">
              {controllerStatus?.ip || '127.0.0.1'}:{controllerStatus?.port || 6633}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Connections</label>
            <p className="font-semibold text-gray-900">
              {controllerSnapshot?.summary?.connections || 0} switches
            </p>
          </div>
        </div>

        {controllerStatus?.running && controllerSnapshot && (
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-600">Memory Usage</label>
              <p className="font-semibold text-gray-900">
                {controllerStatus.memory_usage || 0}%
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-600">Log Level</label>
              <p className="font-semibold text-gray-900">
                {controllerStatus.log_level || 'INFO'}
              </p>
            </div>
          </div>
        )}

        {/* Connected Switches */}
        {connectedSwitches.length > 0 && (
          <div className="mt-4">
            <label className="text-sm font-medium text-gray-600">Connected Switches</label>
            <div className="flex flex-wrap gap-2 mt-2">
              {connectedSwitches.map((conn, i) => (
                <span key={i} className="px-2 py-1 bg-white rounded text-xs">
                  {conn.switch_id}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Controller Type Selection */}
      <ConfigSection
        title="Controller Type Selection"
        icon={Settings}
        expanded={expandedSections.controllerType}
        onToggle={() => toggle('controllerType')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Object.entries(CONTROLLER_TYPES).map(([key, controller]) => {
            const Icon = controller.icon;
            return (
              <div
                key={key}
                className={`p-4 border-2 rounded-lg cursor-pointer transition-all ${
                  localConfig.controllerType === key
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
                }`}
                onClick={() => handleControllerTypeChange(key)}
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className={`p-2 rounded-lg ${controller.color} text-white`}>
                    <Icon size={20} />
                  </div>
                  <div>
                    <h4 className="font-semibold text-gray-900">{controller.name}</h4>
                    <p className="text-sm text-gray-600">{controller.description}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1 mb-2">
                  {controller.features.map((feature, i) => (
                    <span key={i} className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
                      {feature}
                    </span>
                  ))}
                </div>
                <p className="text-xs text-gray-500">
                  Supported versions: {controller.supportedVersions.join(', ')}
                </p>
              </div>
            );
          })}
        </div>
      </ConfigSection>

      {/* Ryu Configuration */}
      {localConfig.controllerType === 'ryu' && (
        <ConfigSection
          title="Ryu Controller Configuration"
          icon={CONTROLLER_TYPES.ryu.icon}
          expanded={expandedSections.ryuConfig}
          onToggle={() => toggle('ryuConfig')}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <SelectField
              label="Application"
              value={localConfig.ryu.app}
              onChange={v => handleConfigChange('ryu', 'app', v)}
              options={CONTROLLER_TYPES.ryu.apps.map(app => ({ value: app, label: app }))}
            />
            <InputField
              label="Listen Port"
              type="number"
              value={localConfig.ryu.port}
              onChange={v => handleConfigChange('ryu', 'port', parseInt(v) || 6633)}
              placeholder="6633"
            />
            <InputField
              label="IP Address"
              value={localConfig.ryu.ip}
              onChange={v => handleConfigChange('ryu', 'ip', v)}
              placeholder="127.0.0.1"
            />
            <SelectField
              label="Log Level"
              value={localConfig.ryu.log_level}
              onChange={v => handleConfigChange('ryu', 'log_level', v)}
              options={['DEBUG', 'INFO', 'WARNING', 'ERROR'].map(l => ({ value: l, label: l }))}
            />
            <CheckboxField
              label="Enable REST API"
              checked={localConfig.ryu.rest_api_enabled}
              onChange={v => handleConfigChange('ryu', 'rest_api_enabled', v)}
            />
            {localConfig.ryu.rest_api_enabled && (
              <InputField
                label="REST API Port"
                type="number"
                value={localConfig.ryu.rest_api_port}
                onChange={v => handleConfigChange('ryu', 'rest_api_port', parseInt(v) || 8080)}
                placeholder="8080"
              />
            )}
            <CheckboxField
              label="Enable Clustering"
              checked={localConfig.ryu.clustering_enabled}
              onChange={v => handleConfigChange('ryu', 'clustering_enabled', v)}
            />
          </div>
        </ConfigSection>
      )}

      {/* POX Configuration */}
      {localConfig.controllerType === 'pox' && (
        <ConfigSection
          title="POX Controller Configuration"
          icon={CONTROLLER_TYPES.pox.icon}
          expanded={expandedSections.poxConfig}
          onToggle={() => toggle('poxConfig')}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <SelectField
              label="Application"
              value={localConfig.pox.app}
              onChange={v => handleConfigChange('pox', 'app', v)}
              options={CONTROLLER_TYPES.pox.apps.map(app => ({ value: app, label: app }))}
            />
            <InputField
              label="Listen Port"
              type="number"
              value={localConfig.pox.port}
              onChange={v => handleConfigChange('pox', 'port', parseInt(v) || 6633)}
              placeholder="6633"
            />
            <InputField
              label="IP Address"
              value={localConfig.pox.ip}
              onChange={v => handleConfigChange('pox', 'ip', v)}
              placeholder="127.0.0.1"
            />
            <SelectField
              label="Log Level"
              value={localConfig.pox.log_level}
              onChange={v => handleConfigChange('pox', 'log_level', v)}
              options={['DEBUG', 'INFO', 'WARNING', 'ERROR'].map(l => ({ value: l, label: l }))}
            />
          </div>
        </ConfigSection>
      )}

      {/* OsKen Configuration */}
      {localConfig.controllerType === 'osken' && (
        <ConfigSection
          title="OsKen Controller Configuration"
          icon={CONTROLLER_TYPES.osken.icon}
          expanded={expandedSections.oskenConfig}
          onToggle={() => toggle('oskenConfig')}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <SelectField
              label="Application"
              value={localConfig.osken.app}
              onChange={v => handleConfigChange('osken', 'app', v)}
              options={CONTROLLER_TYPES.osken.apps.map(app => ({ value: app, label: app }))}
            />
            <InputField
              label="Listen Port"
              type="number"
              value={localConfig.osken.port}
              onChange={v => handleConfigChange('osken', 'port', parseInt(v) || 6633)}
              placeholder="6633"
            />
            <InputField
              label="IP Address"
              value={localConfig.osken.ip}
              onChange={v => handleConfigChange('osken', 'ip', v)}
              placeholder="127.0.0.1"
            />
            <SelectField
              label="Log Level"
              value={localConfig.osken.log_level}
              onChange={v => handleConfigChange('osken', 'log_level', v)}
              options={['DEBUG', 'INFO', 'WARNING', 'ERROR'].map(l => ({ value: l, label: l }))}
            />
            <CheckboxField
              label="Enable REST API"
              checked={localConfig.osken.rest_api_enabled}
              onChange={v => handleConfigChange('osken', 'rest_api_enabled', v)}
            />
            {localConfig.osken.rest_api_enabled && (
              <InputField
                label="REST API Port"
                type="number"
                value={localConfig.osken.rest_api_port}
                onChange={v => handleConfigChange('osken', 'rest_api_port', parseInt(v) || 8080)}
                placeholder="8080"
              />
            )}
          </div>
        </ConfigSection>
      )}

      {/* OpenDaylight Configuration */}
      {localConfig.controllerType === 'opendaylight' && (
        <ConfigSection
          title="OpenDaylight Controller Configuration"
          icon={CONTROLLER_TYPES.opendaylight.icon}
          expanded={expandedSections.opendaylightConfig}
          onToggle={() => toggle('opendaylightConfig')}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <SelectField
              label="Application"
              value={localConfig.opendaylight.app}
              onChange={v => handleConfigChange('opendaylight', 'app', v)}
              options={CONTROLLER_TYPES.opendaylight.apps.map(app => ({ value: app, label: app }))}
            />
            <InputField
              label="Listen Port"
              type="number"
              value={localConfig.opendaylight.port}
              onChange={v => handleConfigChange('opendaylight', 'port', parseInt(v) || 8181)}
              placeholder="8181"
            />
            <InputField
              label="IP Address"
              value={localConfig.opendaylight.ip}
              onChange={v => handleConfigChange('opendaylight', 'ip', v)}
              placeholder="127.0.0.1"
            />
            <SelectField
              label="Log Level"
              value={localConfig.opendaylight.log_level}
              onChange={v => handleConfigChange('opendaylight', 'log_level', v)}
              options={['DEBUG', 'INFO', 'WARNING', 'ERROR'].map(l => ({ value: l, label: l }))}
            />
            <CheckboxField
              label="Enable Clustering"
              checked={localConfig.opendaylight.clustering_enabled}
              onChange={v => handleConfigChange('opendaylight', 'clustering_enabled', v)}
            />
            <CheckboxField
              label="Enable NetConf"
              checked={localConfig.opendaylight.netconf_enabled}
              onChange={v => handleConfigChange('opendaylight', 'netconf_enabled', v)}
            />
          </div>
        </ConfigSection>
      )}

      {/* Available Applications for Current Controller */}
      <ConfigSection
        title={`Available ${currentController?.name || 'Controller'} Applications`}
        icon={Network}
        expanded={expandedSections.apps}
        onToggle={() => toggle('apps')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {currentController?.apps.map((app) => (
            <div
              key={app}
              className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                controllerStatus?.running && controllerStatus.controller_type === localConfig.controllerType &&
                localConfig[localConfig.controllerType]?.app === app
                  ? 'border-green-500 bg-green-50'
                  : localConfig[localConfig.controllerType]?.app === app
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
              onClick={() => {
                handleConfigChange(localConfig.controllerType, 'app', app);
                if (controllerStatus?.running && controllerStatus.controller_type === localConfig.controllerType) {
                  switchControllerApp(app);
                }
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-gray-900">{app}</h4>
                {controllerStatus?.running && controllerStatus.controller_type === localConfig.controllerType &&
                 localConfig[localConfig.controllerType]?.app === app && (
                  <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">
                    Active
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-600 mb-2">
                {app === 'simple_switch_13' && 'Basic L2 learning switch implementation'}
                {app === 'hub' && 'Floods all packets to all ports (learning hub)'}
                {app === 'l2_learning' && 'Layer 2 learning switch'}
                {app === 'simple_monitor' && 'Traffic monitoring and statistics'}
                {app === 'forwarding' && 'Basic packet forwarding'}
                {app === 'simple_switch' && 'Basic OpenFlow switch'}
                {app === 'l2_switch' && 'Layer 2 switch with VLAN support'}
                {app === 'default' && 'Default OpenDaylight application'}
                {app === 'l2switch' && 'Layer 2 switching service'}
                {app === 'odl-mdsal-apidocs' && 'REST API documentation'}
              </p>
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                {currentController?.name} App
              </span>
            </div>
          ))}
        </div>
      </ConfigSection>

      {/* Controller Actions */}
      <ConfigSection
        title="Controller Actions"
        icon={Power}
        expanded={expandedSections.status}
        onToggle={() => toggle('status')}
      >
        <div className="flex flex-wrap gap-4 mb-4">
          <ActionButton
            onClick={handleStartController}
            loading={loading}
            icon={<Power size={16} />}
            label="Start"
            variant="success"
            disabled={controllerStatus?.running}
          />
          <ActionButton
            onClick={handleStopController}
            loading={loading}
            icon={<Power size={16} />}
            label="Stop"
            variant="danger"
            disabled={!controllerStatus?.running}
          />
          <ActionButton
            onClick={handleRestartController}
            loading={loading}
            icon={<RefreshCcw size={16} />}
            label="Restart"
            variant="secondary"
            disabled={!controllerStatus?.running}
          />
        </div>
      </ConfigSection>

      {/* Controller Logs */}
      {controllerStatus?.running && (
        <ConfigSection
          title="Controller Logs"
          icon={Activity}
          expanded={expandedSections.logs}
          onToggle={() => toggle('logs')}
          actions={
            <div className="flex gap-2">
              <ActionButton
                onClick={fetchControllerLogs}
                loading={loading}
                icon={<RefreshCcw size={14} />}
                label="Refresh"
                variant="secondary"
                size="sm"
              />
              <ActionButton
                onClick={clearControllerLogs}
                loading={loading}
                icon={<Activity size={14} />}
                label="Clear"
                variant="secondary"
                size="sm"
              />
            </div>
          }
        >
          <div className="bg-gray-900 text-green-400 p-4 rounded-lg font-mono text-sm max-h-64 overflow-y-auto">
            {controllerLogs.length > 0 ? (
              controllerLogs.slice(-20).map((log, index) => (
                <div key={index} className="mb-1">{log}</div>
              ))
            ) : (
              <div className="text-gray-500">No logs available</div>
            )}
          </div>
        </ConfigSection>
      )}

      {/* Configuration Summary */}
      <div className="bg-gray-50 rounded-lg p-4">
        <h4 className="font-medium text-gray-900 mb-2">Configuration Summary</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
          <div>
            <span className="text-gray-700">Controller Type:</span>
            <span className="ml-2 font-mono">{currentController?.name || 'Unknown'}</span>
          </div>
          <div>
            <span className="text-gray-700">Application:</span>
            <span className="ml-2 font-mono">{localConfig[localConfig.controllerType]?.app || 'None'}</span>
          </div>
          <div>
            <span className="text-gray-700">Listen Address:</span>
            <span className="ml-2 font-mono">
              {localConfig[localConfig.controllerType]?.ip || '127.0.0.1'}:
              {localConfig[localConfig.controllerType]?.port || 6633}
            </span>
          </div>
          <div>
            <span className="text-gray-700">Log Level:</span>
            <span className="ml-2 font-mono">{localConfig[localConfig.controllerType]?.log_level || 'INFO'}</span>
          </div>
          {currentController?.features.includes('REST API') && (
            <div>
              <span className="text-gray-700">REST API:</span>
              <span className="ml-2 font-mono">
                {localConfig[localConfig.controllerType]?.rest_api_enabled
                  ? `Enabled (${localConfig[localConfig.controllerType]?.rest_api_port || 8080})`
                  : 'Disabled'}
              </span>
            </div>
          )}
          {currentController?.features.includes('Clustering') && (
            <div>
              <span className="text-gray-700">Clustering:</span>
              <span className="ml-2 font-mono">
                {localConfig[localConfig.controllerType]?.clustering_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          )}
          {localConfig.controllerType === 'opendaylight' && (
            <div>
              <span className="text-gray-700">NetConf:</span>
              <span className="ml-2 font-mono">
                {localConfig.opendaylight.netconf_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          )}
        </div>

        {/* Controller Features Summary */}
        <div className="mt-3">
          <span className="text-sm text-gray-700">Supported Features:</span>
          <div className="flex flex-wrap gap-1 mt-1">
            {currentController?.features.map((feature, i) => (
              <span key={i} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded">
                {feature}
              </span>
            ))}
          </div>
        </div>

        {!controllerStatus?.running && (
          <div className="mt-3 p-2 bg-yellow-100 rounded text-yellow-800 text-sm">
            ⚠️ Controller is not running. Start it to enable OpenFlow switch management.
          </div>
        )}

        {controllerStatus?.running && controllerStatus.controller_type !== localConfig.controllerType && (
          <div className="mt-3 p-2 bg-orange-100 rounded text-orange-800 text-sm">
            ⚠️ Running controller ({controllerStatus.controller_type}) doesn't match selected configuration.
            Restart controller to apply new settings.
          </div>
        )}
      </div>
    </div>
  );
};

export default ControllerConfigTab;