// SystemConfigSection.jsx - System configuration management with API integration
import React from 'react';
import { Settings, Plus, Terminal, Clock } from 'lucide-react';
import ConfigSection from '../../components/ConfigSection';
import { InputField, SelectField } from '../../components/FormComponents';

export const SystemConfigSection = ({ 
  local, 
  hostStatus, 
  sections, 
  dispatch, 
  onToggle 
}) => {
  const systemInfo = hostStatus?.system_metrics || {};

  const timezoneOptions = [
    { value: 'UTC', label: 'UTC (Coordinated Universal Time)' },
    { value: 'America/New_York', label: 'Eastern Time (US & Canada)' },
    { value: 'America/Chicago', label: 'Central Time (US & Canada)' },
    { value: 'America/Denver', label: 'Mountain Time (US & Canada)' },
    { value: 'America/Los_Angeles', label: 'Pacific Time (US & Canada)' },
    { value: 'Europe/London', label: 'London (GMT/BST)' },
    { value: 'Europe/Paris', label: 'Paris (CET/CEST)' },
    { value: 'Europe/Berlin', label: 'Berlin (CET/CEST)' },
    { value: 'Asia/Tokyo', label: 'Tokyo (JST)' },
    { value: 'Asia/Shanghai', label: 'Shanghai (CST)' },
    { value: 'Australia/Sydney', label: 'Sydney (AEST/AEDT)' }
  ];

  const formatUptime = (uptime) => {
    if (!uptime) return 'Unknown';
    // Clean up the uptime string
    return uptime.replace('up ', '').trim();
  };

  const hasSystemChanges = () => {
    return (
      (local.system_hostname?.trim() && local.system_hostname.trim() !== hostStatus?.hostname) ||
      (local.timezone && local.timezone !== 'UTC') ||
      (local.custom_commands || []).filter(cmd => cmd?.trim()).length > 0
    );
  };

  return (
    <ConfigSection
      title="System Configuration"
      icon={Settings}
      expanded={sections.system}
      onToggle={() => onToggle('system')}
    >
      {/* Current System Information */}
      <div className="mb-6 p-4 bg-gray-50 rounded border">
        <h4 className="font-medium text-gray-900 mb-3">Current System Information</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="text-sm font-medium text-gray-600">Current Hostname</label>
            <p className="text-sm text-gray-900 font-mono">
              {hostStatus?.hostname || 'Unknown'}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">System Uptime</label>
            <p className="text-sm text-gray-900">
              {formatUptime(systemInfo.uptime)}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Running Processes</label>
            <p className="text-sm text-gray-900">{systemInfo.processes || 0}</p>
          </div>
        </div>
        
        {/* System Metrics */}
        {systemInfo.cpu && (
          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-600">CPU Usage</label>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{ width: `${Math.min(systemInfo.cpu.usage_percent || 0, 100)}%` }}
                  />
                </div>
                <span className="text-sm font-mono">
                  {(systemInfo.cpu.usage_percent || 0).toFixed(1)}%
                </span>
              </div>
              {systemInfo.cpu.load_average?.length > 0 && (
                <div className="text-xs text-gray-500 mt-1">
                  Load: {systemInfo.cpu.load_average.map(l => l.toFixed(2)).join(', ')}
                </div>
              )}
            </div>
            <div>
              <label className="text-sm font-medium text-gray-600">Memory Usage</label>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-green-600 h-2 rounded-full transition-all"
                    style={{ width: `${Math.min(systemInfo.memory?.usage_percent || 0, 100)}%` }}
                  />
                </div>
                <span className="text-sm font-mono">
                  {(systemInfo.memory?.usage_percent || 0).toFixed(1)}%
                </span>
              </div>
              {systemInfo.memory?.total_mb > 0 && (
                <div className="text-xs text-gray-500 mt-1">
                  {systemInfo.memory.used_mb}MB / {systemInfo.memory.total_mb}MB
                </div>
              )}
            </div>
            <div>
              <label className="text-sm font-medium text-gray-600">Disk Usage</label>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-orange-600 h-2 rounded-full transition-all"
                    style={{ width: `${Math.min(systemInfo.disk?.usage_percent || 0, 100)}%` }}
                  />
                </div>
                <span className="text-sm font-mono">
                  {(systemInfo.disk?.usage_percent || 0).toFixed(1)}%
                </span>
              </div>
              {systemInfo.disk?.total_gb > 0 && (
                <div className="text-xs text-gray-500 mt-1">
                  {systemInfo.disk.used_gb}GB / {systemInfo.disk.total_gb}GB
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Basic System Configuration */}
      <div className="space-y-4 mb-6">
        <h4 className="font-medium text-gray-900">Basic System Settings</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <InputField
            label="New Hostname"
            value={local.system_hostname || ''}
            onChange={(v) => dispatch({ type: 'SET_FIELD', field: 'system_hostname', value: v })}
            placeholder={hostStatus?.hostname || 'host1'}
            helper={`Current: ${hostStatus?.hostname || 'Unknown'}`}
            icon={Settings}
          />
          
          <SelectField
            label="Timezone"
            value={local.timezone || 'UTC'}
            onChange={(v) => dispatch({ type: 'SET_FIELD', field: 'timezone', value: v })}
            options={timezoneOptions}
            helper="System timezone setting"
            icon={Clock}
          />
        </div>
        
        {local.system_hostname?.trim() && local.system_hostname.trim() !== hostStatus?.hostname && (
          <div className="p-3 bg-blue-50 rounded text-sm text-blue-800">
            <strong>Note:</strong> Hostname will be changed from "{hostStatus?.hostname}" to "{local.system_hostname.trim()}"
          </div>
        )}
      </div>

      {/* Custom Commands Section */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Terminal size={16} className="text-gray-600" />
          <h5 className="font-medium text-gray-900">Custom Commands</h5>
        </div>
        <p className="text-sm text-gray-600 mb-3">
          Add custom shell commands to execute during system configuration. Commands will be executed in order.
        </p>
        
        {(local.custom_commands || []).map((cmd, i) => (
          <div key={i} className="flex gap-4 mb-2">
            <div className="flex-1">
              <InputField
                value={cmd}
                onChange={(v) => dispatch({ type: 'CUSTOM_COMMAND_SET', index: i, value: v })}
                placeholder="echo 'Custom configuration command'"
                helper={`Command ${i + 1} - Will be executed as root`}
              />
            </div>
            <button
              onClick={() => dispatch({ type: 'CUSTOM_COMMAND_REMOVE', index: i })}
              className="p-2 text-red-600 hover:bg-red-50 rounded border"
              title="Remove command"
            >
              ×
            </button>
          </div>
        ))}

        <button
          onClick={() => dispatch({ type: 'CUSTOM_COMMAND_ADD' })}
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <Plus size={16} /> Add Custom Command
        </button>

        {local.custom_commands?.filter(cmd => cmd?.trim()).length > 0 && (
          <div className="mt-3 p-3 bg-yellow-50 rounded border border-yellow-200">
            <div className="flex items-center gap-2 mb-1">
              <Terminal size={14} className="text-yellow-600" />
              <span className="font-medium text-yellow-900">Security Warning</span>
            </div>
            <p className="text-xs text-yellow-800">
              Custom commands will be executed with root privileges. Ensure commands are safe and tested.
            </p>
          </div>
        )}

        {/* Command Examples */}
        <div className="mt-4 p-3 bg-blue-50 rounded border border-blue-200">
          <h6 className="font-medium text-blue-900 mb-2">Common Command Examples:</h6>
          <ul className="text-xs text-blue-800 space-y-1 font-mono">
            <li>• echo "alias ll='ls -la'"  ~/.bashrc</li>
            <li>• mkdir -p /opt/myapp</li>
            <li>• apt-get update && apt-get install -y curl</li>
            <li>• echo "192.168.1.100 myserver"  /etc/hosts</li>
            <li>• chmod +x /usr/local/bin/myscript.sh</li>
          </ul>
        </div>
      </div>

      {/* Pending Changes Summary */}
      {hasSystemChanges() && (
        <div className="mb-4 p-3 bg-yellow-50 rounded border border-yellow-200">
          <h5 className="font-medium text-yellow-900 mb-2">Pending System Changes</h5>
          <ul className="text-sm text-yellow-800 space-y-1">
            {local.system_hostname?.trim() && local.system_hostname.trim() !== hostStatus?.hostname && (
              <li>• Hostname: {hostStatus?.hostname} → {local.system_hostname.trim()}</li>
            )}
            {local.timezone && local.timezone !== 'UTC' && (
              <li>• Timezone: UTC → {local.timezone}</li>
            )}
            {(local.custom_commands || []).filter(cmd => cmd?.trim()).length > 0 && (
              <li>• Custom commands: {local.custom_commands.filter(cmd => cmd?.trim()).length} command(s)</li>
            )}
          </ul>
          <div className="text-xs text-yellow-700 mt-2">
            Click "Apply Configuration" to execute these changes
          </div>
        </div>
      )}

      {/* System Configuration Help */}
      <div className="p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>System Configuration Notes:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>Hostname:</strong> Sets the system hostname and updates /etc/hostname</li>
          <li>• <strong>Timezone:</strong> Configures system timezone using timedatectl (if available)</li>
          <li>• <strong>Custom Commands:</strong> Execute arbitrary shell commands during configuration</li>
          <li>• <strong>Execution Order:</strong> System settings → Custom commands</li>
          <li>• <strong>Security:</strong> All commands run with system privileges - use caution</li>
          <li>• Changes may require a system restart to take full effect</li>
        </ul>
      </div>
    </ConfigSection>
  );
};