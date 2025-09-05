// ServicesConfigSection.jsx - Network services management with API integration
import React from 'react';
import { Activity, Play, Square, RefreshCw } from 'lucide-react';
import ConfigSection from '../../components/ConfigSection';
import { InputField, CheckboxField } from '../../components/FormComponents';
import ActionButton from '../../components/ActionButton';

export const ServicesConfigSection = ({ 
  local, 
  hostStatus, 
  sections, 
  dispatch, 
  onToggle,
  onManageService 
}) => {
  const networkServices = hostStatus?.network_services || {};
  const services = ['ssh', 'http', 'https', 'ftp', 'telnet', 'snmp', 'ntp', 'dhcp', 'dns'];

  const getServiceStatus = (serviceName) => {
    const service = networkServices[serviceName];
    return {
      running: service?.running || false,
      port_listening: service?.port_listening || false,
      processes: service?.processes || [],
      port: service?.port || getDefaultPort(serviceName)
    };
  };

  const getDefaultPort = (serviceName) => {
    const defaultPorts = {
      ssh: 22,
      http: 80,
      https: 443,
      ftp: 21,
      telnet: 23,
      snmp: 161,
      ntp: 123,
      dhcp: 67,
      dns: 53
    };
    return defaultPorts[serviceName] || 'Unknown';
  };

  const getServiceDisplayName = (serviceName) => {
    return serviceName.toUpperCase();
  };

  const getServiceDescription = (serviceName) => {
    const descriptions = {
      ssh: 'Secure Shell - Remote terminal access',
      http: 'HTTP Web Server - Serve web pages',
      https: 'HTTPS Web Server - Secure web pages',
      ftp: 'File Transfer Protocol - File sharing',
      telnet: 'Telnet Server - Insecure remote access',
      snmp: 'SNMP Agent - Network monitoring',
      ntp: 'Network Time Protocol - Time synchronization',
      dhcp: 'DHCP Server - Automatic IP assignment',
      dns: 'DNS Server - Domain name resolution'
    };
    return descriptions[serviceName] || 'Network service';
  };

  const handleServiceToggle = (serviceName, enable) => {
    dispatch({ 
      type: 'TOGGLE_SERVICE', 
      service: serviceName, 
      enabled: enable 
    });
  };

  const isServiceMarkedToStart = (serviceName) => {
    return (local.services_to_start || []).includes(serviceName);
  };

  const isServiceMarkedToStop = (serviceName) => {
    return (local.services_to_stop || []).includes(serviceName);
  };

  const getServiceActionStatus = (serviceName) => {
    const status = getServiceStatus(serviceName);
    const markedToStart = isServiceMarkedToStart(serviceName);
    const markedToStop = isServiceMarkedToStop(serviceName);
    
    if (markedToStart && !status.running) {
      return { action: 'will-start', color: 'text-green-600', label: 'Will Start' };
    }
    if (markedToStop && status.running) {
      return { action: 'will-stop', color: 'text-red-600', label: 'Will Stop' };
    }
    if (status.running) {
      return { action: 'running', color: 'text-green-600', label: 'Running' };
    }
    return { action: 'stopped', color: 'text-gray-400', label: 'Stopped' };
  };

  return (
    <ConfigSection
      title="Network Services"
      icon={Activity}
      expanded={sections.services}
      onToggle={() => onToggle('services')}
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {services.map(serviceName => {
          const status = getServiceStatus(serviceName);
          const actionStatus = getServiceActionStatus(serviceName);
          const markedToStart = isServiceMarkedToStart(serviceName);
          const markedToStop = isServiceMarkedToStop(serviceName);
          
          return (
            <div key={serviceName} className="p-4 border rounded bg-white">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="flex items-center">
                    <span className="font-medium text-gray-900 mr-2">
                      {getServiceDisplayName(serviceName)}
                    </span>
                    <div className={`w-2 h-2 rounded-full ${status.running ? 'bg-green-500' : 'bg-gray-400'}`} />
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <span className={`text-xs font-medium ${actionStatus.color}`}>
                    {actionStatus.label}
                  </span>
                </div>
              </div>
              
              <div className="text-xs text-gray-600 mb-3">
                {getServiceDescription(serviceName)}
              </div>
              
              <div className="text-xs text-gray-600 mb-3">
                Port: {status.port}
                {status.port_listening && (
                  <span className="ml-2 text-green-600 font-medium">● Listening</span>
                )}
                {status.processes.length > 0 && (
                  <span className="ml-2 text-gray-500">
                    (PID: {status.processes[0]?.pid})
                  </span>
                )}
              </div>

              {/* Service Actions */}
              <div className="flex gap-2 mb-3">
                {status.running && !markedToStop && (
                  <button
                    onClick={() => handleServiceToggle(serviceName, false)}
                    className="flex-1 px-3 py-1 text-xs bg-red-50 text-red-600 rounded border border-red-200 hover:bg-red-100"
                  >
                    Mark to Stop
                  </button>
                )}
                {!status.running && !markedToStart && (
                  <button
                    onClick={() => handleServiceToggle(serviceName, true)}
                    className="flex-1 px-3 py-1 text-xs bg-green-50 text-green-600 rounded border border-green-200 hover:bg-green-100"
                  >
                    Mark to Start
                  </button>
                )}
                {markedToStart && (
                  <button
                    onClick={() => handleServiceToggle(serviceName, false)}
                    className="flex-1 px-3 py-1 text-xs bg-gray-50 text-gray-600 rounded border border-gray-200 hover:bg-gray-100"
                  >
                    Cancel Start
                  </button>
                )}
                {markedToStop && (
                  <button
                    onClick={() => handleServiceToggle(serviceName, true)}
                    className="flex-1 px-3 py-1 text-xs bg-gray-50 text-gray-600 rounded border border-gray-200 hover:bg-gray-100"
                  >
                    Cancel Stop
                  </button>
                )}
              </div>

              {/* Immediate Actions (if onManageService is provided) */}
              {onManageService && (
                <div className="flex gap-2 pt-2 border-t">
                  {!status.running ? (
                    <ActionButton
                      onClick={() => onManageService(serviceName, 'start')}
                      icon={<Play size={12} />}
                      label="Start Now"
                      variant="secondary"
                      size="sm"
                      className="flex-1"
                    />
                  ) : (
                    <>
                      <ActionButton
                        onClick={() => onManageService(serviceName, 'stop')}
                        icon={<Square size={12} />}
                        label="Stop Now"
                        variant="secondary"
                        size="sm"
                        className="flex-1"
                      />
                      <ActionButton
                        onClick={() => onManageService(serviceName, 'restart')}
                        icon={<RefreshCw size={12} />}
                        label="Restart"
                        variant="secondary"
                        size="sm"
                        className="flex-1"
                      />
                    </>
                  )}
                </div>
              )}

              {/* Service-specific configuration */}
              {markedToStart && (serviceName === 'http' || serviceName === 'ftp' || serviceName === 'ssh') && (
                <div className="mt-3 pt-2 border-t border-gray-200">
                  <InputField
                    label="Custom Port"
                    value={local.service_configs?.[serviceName]?.port || ''}
                    onChange={(v) => dispatch({ 
                      type: 'SET_SERVICE_CONFIG', 
                      service: serviceName, 
                      field: 'port', 
                      value: v 
                    })}
                    placeholder={getDefaultPort(serviceName).toString()}
                    size="sm"
                    helper="Leave empty for default port"
                  />
                </div>
              )}

              {/* DHCP Server warning */}
              {markedToStart && serviceName === 'dhcp' && (
                <div className="mt-3 pt-2 border-t border-gray-200">
                  <div className="text-xs text-amber-600">
                    ⚠️ Configure DHCP settings in the DHCP section
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Service Management Information */}
      <div className="mt-6 p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>Service Management:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>Green dot:</strong> Service is currently running</li>
          <li>• <strong>Mark to Start/Stop:</strong> Queue service for configuration changes</li>
          <li>• <strong>Start/Stop Now:</strong> Immediately control service without applying full config</li>
          <li>• <strong>Custom ports:</strong> Available for HTTP, FTP, and SSH services</li>
          <li>• <strong>Security note:</strong> Telnet is insecure; use SSH instead</li>
          <li>• <strong>Apply Configuration:</strong> Executes all marked service changes</li>
        </ul>
      </div>

      {/* Pending Changes Summary */}
      {(local.services_to_start?.length > 0 || local.services_to_stop?.length > 0) && (
        <div className="mt-4 p-3 bg-yellow-50 rounded border border-yellow-200">
          <h5 className="font-medium text-yellow-900 mb-2">Pending Service Changes</h5>
          {local.services_to_start?.length > 0 && (
            <div className="text-sm text-yellow-800 mb-1">
              <span className="font-medium">Will Start:</span> {local.services_to_start.map(s => s.toUpperCase()).join(', ')}
            </div>
          )}
          {local.services_to_stop?.length > 0 && (
            <div className="text-sm text-yellow-800">
              <span className="font-medium">Will Stop:</span> {local.services_to_stop.map(s => s.toUpperCase()).join(', ')}
            </div>
          )}
          <div className="text-xs text-yellow-700 mt-2">
            Click "Apply Configuration" to execute these changes
          </div>
        </div>
      )}

      {/* Running Services Summary */}
      {Object.keys(networkServices).some(service => networkServices[service].running) && (
        <div className="mt-4 p-3 bg-green-50 rounded border border-green-200">
          <h5 className="font-medium text-green-900 mb-2">Currently Running Services</h5>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {Object.entries(networkServices)
              .filter(([_, service]) => service.running)
              .map(([serviceName, service]) => (
                <div key={serviceName} className="text-sm text-green-800 bg-white px-2 py-1 rounded">
                  <span className="font-medium">{serviceName.toUpperCase()}</span>
                  <span className="ml-2 text-green-600">:{service.port}</span>
                  {service.processes?.length > 0 && (
                    <span className="ml-1 text-xs text-green-600">
                      (PID {service.processes[0].pid})
                    </span>
                  )}
                </div>
              ))}
          </div>
        </div>
      )}
    </ConfigSection>
  );
};