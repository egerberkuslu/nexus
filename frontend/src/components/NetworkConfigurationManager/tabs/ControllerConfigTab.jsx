// ControllerConfigTab.jsx - Auto-updating with current status
import React, { useState, useEffect } from 'react';
import {
  Network, Settings, ToggleLeft, Power, RefreshCcw, Save, Activity
} from 'lucide-react';
import { InputField, SelectField, CheckboxField } from '../components/FormComponents';
import ActionButton from '../components/ActionButton';
import ConfigSection from '../components/ConfigSection';

export const ControllerConfigTab = ({ 
  config, 
  updateConfig, 
  loading, 
  setLoading, 
  showMessage, 
  apiCall, 
  onNetworkChange 
}) => {
  const [expandedSections, setExpandedSections] = useState({
    controllerType: true,
    restAPI: false,
    status: false,
    apps: false,
    logs: false
  });

  const [currentStatus, setCurrentStatus] = useState({
    running: false,
    controller_type: 'Unknown',
    port: 6633,
    ip: '127.0.0.1',
    python_executable: 'python3',
    connections: 0,
    memory_usage: 0,
    log_level: 'INFO'
  });

  const [realTimeConfig, setRealTimeConfig] = useState({
    type: 'simple_switch_13',
    port: 6633,
    ip: '127.0.0.1',
    log_level: 'INFO',
    rest_api_enabled: false,
    rest_api_port: 8080
  });

  const [availableApps, setAvailableApps] = useState([]);
  const [controllerLogs, setControllerLogs] = useState([]);

  const toggle = section => setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));

  // Auto-refresh data every 3 seconds
  useEffect(() => {
    fetchControllerStatus();
    fetchAvailableApps();
    
    const interval = setInterval(() => {
      fetchControllerStatus();
      if (currentStatus.running) {
        fetchControllerLogs();
      }
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  // Update config when currentStatus changes
  useEffect(() => {
    setRealTimeConfig(prev => ({
      ...prev,
      type: currentStatus.controller_type || prev.type,
      port: currentStatus.port || prev.port,
      ip: currentStatus.ip || prev.ip,
      log_level: currentStatus.log_level || prev.log_level,
      ...config
    }));
  }, [currentStatus, config]);

  const fetchControllerStatus = async () => {
    try {
      const response = await apiCall('/controller/status');
      if (response.success) {
        setCurrentStatus({
          running: response.data.running || false,
          controller_type: response.data.controller_type || 'Unknown',
          port: response.data.port || 6633,
          ip: response.data.ip || '127.0.0.1',
          python_executable: response.data.python_executable || 'python3',
          connections: response.data.connections || 0,
          memory_usage: response.data.memory_usage || 0,
          log_level: response.data.log_level || 'INFO'
        });

        // Update parent config with current values
        updateConfig({
          ...config,
          type: response.data.controller_type || config.type,
          port: response.data.port || config.port,
          ip: response.data.ip || config.ip,
          log_level: response.data.log_level || config.log_level
        });
      }
    } catch (error) {
      console.error('Failed to fetch controller status:', error);
    }
  };

  const fetchAvailableApps = async () => {
    try {
      const response = await apiCall('/controller/apps');
      if (response.success) {
        setAvailableApps(response.data.apps || []);
      }
    } catch (error) {
      console.error('Failed to fetch available apps:', error);
    }
  };

  const fetchControllerLogs = async () => {
    try {
      const response = await apiCall('/controller/logs?lines=20');
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
      const response = await apiCall('/controller/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(realTimeConfig)
      });

      if (response.success) {
        showMessage('✔️ Controller configuration applied successfully', 'success');
        await fetchControllerStatus();
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

  const startController = async () => {
    setLoading(true);
    try {
      const response = await apiCall('/controller/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          type: realTimeConfig.type || 'simple_switch_13', 
          port: realTimeConfig.port || 6633 
        })
      });

      if (response.success) {
        showMessage('✅ Controller started successfully', 'success');
        await fetchControllerStatus();
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

  const stopController = async () => {
    setLoading(true);
    try {
      const response = await apiCall('/controller/stop', { method: 'POST' });
      
      if (response.success) {
        showMessage('🛑 Controller stopped successfully', 'success');
        await fetchControllerStatus();
        setControllerLogs([]); // Clear logs when stopped
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

  const restartController = async () => {
    setLoading(true);
    try {
      const response = await apiCall('/controller/restart', { method: 'POST' });
      
      if (response.success) {
        showMessage('🔁 Controller restarted successfully', 'success');
        await fetchControllerStatus();
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

  const switchControllerApp = async (newApp) => {
    setLoading(true);
    try {
      const response = await apiCall('/controller/switch/app', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app: newApp })
      });

      if (response.success) {
        showMessage(`🔀 Switched to ${newApp} successfully`, 'success');
        handleConfigChange('type', newApp);
        await fetchControllerStatus();
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

  const clearControllerLogs = async () => {
    try {
      const response = await apiCall('/controller/logs/clear', { method: 'POST' });
      if (response.success) {
        showMessage('🧹 Controller logs cleared', 'info');
        setControllerLogs([]);
      }
    } catch (error) {
      showMessage('❌ Error clearing logs', 'error');
    }
  };

  const handleConfigChange = (field, value) => {
    const newConfig = { ...realTimeConfig, [field]: value };
    setRealTimeConfig(newConfig);
    updateConfig(newConfig);
  };

  // Get status color and text
  const getStatusDisplay = () => {
    if (currentStatus.running) {
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

      {/* Controller Status - Always visible with real-time info */}
      <div className={`${statusDisplay.bgColor} rounded-lg p-4`}>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${currentStatus.running ? 'bg-green-500' : 'bg-red-500'}`} />
            <h3 className="font-semibold text-gray-900">Controller Status</h3>
          </div>
          <ActionButton
            onClick={fetchControllerStatus}
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
              {currentStatus.controller_type}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Address</label>
            <p className="font-semibold text-gray-900 font-mono">
              {currentStatus.ip}:{currentStatus.port}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Connections</label>
            <p className="font-semibold text-gray-900">
              {currentStatus.connections}
            </p>
          </div>
        </div>

        {currentStatus.running && (
          <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-600">Memory Usage</label>
              <p className="font-semibold text-gray-900">
                {currentStatus.memory_usage}%
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-600">Log Level</label>
              <p className="font-semibold text-gray-900">
                {currentStatus.log_level}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Controller Configuration - Pre-filled with current values */}
      <ConfigSection
        title="Controller Configuration"
        icon={Settings}
        expanded={expandedSections.controllerType}
        onToggle={() => toggle('controllerType')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <SelectField
            label="Controller Type"
            value={realTimeConfig.type}
            onChange={v => handleConfigChange('type', v)}
            options={availableApps.map(app => ({ value: app.id, label: app.name }))}
            helper={`Current: ${currentStatus.controller_type}`}
          />
          <InputField
            label="Listen Port"
            type="number"
            value={realTimeConfig.port}
            onChange={v => handleConfigChange('port', parseInt(v) || 6633)}
            placeholder="6633"
            helper={`Current: ${currentStatus.port}`}
          />
          <InputField
            label="IP Address"
            value={realTimeConfig.ip}
            onChange={v => handleConfigChange('ip', v)}
            placeholder="127.0.0.1"
            helper={`Current: ${currentStatus.ip}`}
          />
          <SelectField
            label="Log Level"
            value={realTimeConfig.log_level}
            onChange={v => handleConfigChange('log_level', v)}
            options={['DEBUG', 'INFO', 'WARNING', 'ERROR'].map(l => ({ value: l, label: l }))}
            helper={`Current: ${currentStatus.log_level}`}
          />
        </div>
        {realTimeConfig.type && availableApps.length > 0 && (
          <p className="text-sm text-slate-500 mt-3">
            {availableApps.find(app => app.id === realTimeConfig.type)?.description}
          </p>
        )}
      </ConfigSection>

      {/* Available Applications - Shows current and allows switching */}
      <ConfigSection
        title="Available Applications"
        icon={Network}
        expanded={expandedSections.apps}
        onToggle={() => toggle('apps')}
      >
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {availableApps.map((app) => (
            <div 
              key={app.id} 
              className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                currentStatus.controller_type === app.id 
                  ? 'border-green-500 bg-green-50' 
                  : realTimeConfig.type === app.id
                  ? 'border-blue-500 bg-blue-50' 
                  : 'border-gray-200 hover:border-gray-300'
              }`}
              onClick={() => {
                handleConfigChange('type', app.id);
                if (currentStatus.running && currentStatus.controller_type !== app.id) {
                  switchControllerApp(app.id);
                }
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium text-gray-900">{app.name}</h4>
                {currentStatus.controller_type === app.id && (
                  <span className="text-xs bg-green-100 text-green-800 px-2 py-1 rounded">
                    Active
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-600 mb-2">{app.description}</p>
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-1 rounded">
                {app.category}
              </span>
            </div>
          ))}
        </div>
      </ConfigSection>

      {/* REST API Configuration - Pre-filled with current values */}
      <ConfigSection
        title="REST API Configuration"
        icon={ToggleLeft}
        expanded={expandedSections.restAPI}
        onToggle={() => toggle('restAPI')}
      >
        <CheckboxField
          label="Enable REST API"
          checked={realTimeConfig.rest_api_enabled || false}
          onChange={v => handleConfigChange('rest_api_enabled', v)}
        />
        {realTimeConfig.rest_api_enabled && (
          <div className="mt-4">
            <InputField
              label="REST API Port"
              type="number"
              value={realTimeConfig.rest_api_port}
              onChange={v => handleConfigChange('rest_api_port', parseInt(v) || 8080)}
              placeholder="8080"
            />
          </div>
        )}
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
            onClick={startController}
            loading={loading}
            icon={<Power size={16} />}
            label="Start"
            variant="success"
            disabled={currentStatus.running}
          />
          <ActionButton
            onClick={stopController}
            loading={loading}
            icon={<Power size={16} />}
            label="Stop"
            variant="danger"
            disabled={!currentStatus.running}
          />
          <ActionButton
            onClick={restartController}
            loading={loading}
            icon={<RefreshCcw size={16} />}
            label="Restart"
            variant="secondary"
            disabled={!currentStatus.running}
          />
        </div>
      </ConfigSection>

      {/* Controller Logs - Real-time logs when running */}
      {currentStatus.running && (
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
            <span className="ml-2 font-mono">{realTimeConfig.type}</span>
          </div>
          <div>
            <span className="text-gray-700">Listen Address:</span>
            <span className="ml-2 font-mono">{realTimeConfig.ip}:{realTimeConfig.port}</span>
          </div>
          <div>
            <span className="text-gray-700">Log Level:</span>
            <span className="ml-2 font-mono">{realTimeConfig.log_level}</span>
          </div>
          <div>
            <span className="text-gray-700">REST API:</span>
            <span className="ml-2 font-mono">
              {realTimeConfig.rest_api_enabled ? `Enabled (${realTimeConfig.rest_api_port})` : 'Disabled'}
            </span>
          </div>
        </div>
        {!currentStatus.running && (
          <div className="mt-2 p-2 bg-yellow-100 rounded text-yellow-800 text-sm">
            ⚠️ Controller is not running. Start it to enable OpenFlow switch management.
          </div>
        )}
      </div>
    </div>
  );
};

export default ControllerConfigTab;