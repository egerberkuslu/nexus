// HostStatusSection.jsx - Current host status display (API Compatible)
import React from 'react';
import { Activity, RefreshCw, Network, Router, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import ConfigSection from '../../components/ConfigSection';
import ActionButton from '../../components/ActionButton';

export const HostStatusSection = ({ 
  hostStatus, 
  sections, 
  loading, 
  onToggle, 
  onRefreshStatus, 
  onTestConnectivity 
}) => {
  const getStatusValue = (value, fallback = 'Not configured') => 
    value || fallback;

  // Extract primary interface information - handle empty interfaces array
  const primaryInterface = hostStatus?.interfaces?.[0] || {};
  const primaryIP = primaryInterface.ip_addresses?.[0] || '';

  // Get running services based on actual API structure
  const getRunningServices = () => {
    if (!hostStatus?.network_services) return 'None';
    
    const runningServices = Object.entries(hostStatus.network_services)
      .filter(([, service]) => service.running || service.port_listening)
      .map(([, service]) => service.service_key?.toUpperCase() || service.name?.toUpperCase())
      .filter(Boolean);
    
    return runningServices.length > 0 ? runningServices.join(', ') : 'None';
  };

  // Get services that are listening on ports (even if not fully running)
  const getListeningServices = () => {
    if (!hostStatus?.network_services) return [];
    
    return Object.entries(hostStatus.network_services)
      .filter(([, service]) => service.port_listening)
      .map(([serviceKey, service]) => ({
        key: serviceKey,
        name: service.name,
        port: service.port,
        running: service.running
      }));
  };

  // Get default gateway from routing table
  const getDefaultGateway = () => {
    if (!hostStatus?.routing_table || hostStatus.routing_table.length === 0) {
      return 'None';
    }
    
    const defaultRoute = hostStatus.routing_table.find(route => 
      route.destination === '0.0.0.0/0' || 
      route.destination === 'default' ||
      (route.raw && route.raw.includes('default'))
    );
    return defaultRoute?.gateway || 'None';
  };

  // Get DHCP status indicator
  const getDHCPStatus = () => {
    const dhcpStatus = hostStatus?.dhcp_status;
    if (!dhcpStatus) return 'Unknown';
    
    const clientActive = dhcpStatus.client?.active_leases?.length > 0;
    const serverRunning = dhcpStatus.server?.running;
    const clientInterfaces = dhcpStatus.client?.dhcp_enabled_interfaces?.length > 0;
    
    if (serverRunning) return 'Server Running';
    if (clientActive) return 'Client Active';
    if (clientInterfaces) return 'Client Enabled';
    return 'Disabled';
  };

  // Get firewall status
  const getFirewallStatus = () => {
    const fwStatus = hostStatus?.firewall_status;
    if (!fwStatus) return 'Unknown';
    
    if (fwStatus.iptables_available && fwStatus.rule_count > 0) {
      return `Active (${fwStatus.rule_count} rules)`;
    } else if (fwStatus.iptables_available) {
      return 'Available (No rules)';
    } else if (fwStatus.ufw_available) {
      return 'UFW Available';
    }
    return 'Not Available';
  };

  // Get DNS status
  const getDNSStatus = () => {
    const dnsConfig = hostStatus?.dns_config;
    if (!dnsConfig) return 'Unknown';
    
    const hasNameservers = dnsConfig.nameservers && dnsConfig.nameservers.length > 0;
    const serviceRunning = dnsConfig.dns_service_running;
    
    if (serviceRunning && hasNameservers) return 'Active';
    if (hasNameservers) return 'Configured';
    if (serviceRunning) return 'Service Running';
    return 'Not Configured';
  };

  const listeningServices = getListeningServices();
  const hasSystemMetricsError = hostStatus?.system_metrics?.error;

  return (
    <ConfigSection
      title="Current Host Status"
      icon={Activity}
      expanded={sections.status}
      onToggle={() => onToggle('status')}
    >
      {/* Basic Status Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <label className="text-sm font-medium text-gray-600">Device ID</label>
          <p className="font-semibold text-gray-900">{hostStatus?.device_id || 'Unknown'}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">Hostname</label>
          <p className="font-semibold text-gray-900">
            {getStatusValue(hostStatus?.hostname, hostStatus?.device_id || 'Not set')}
          </p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">Interface Count</label>
          <p className="font-semibold text-gray-900">{hostStatus?.interfaces?.length || 0}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">Default Gateway</label>
          <p className="font-semibold text-gray-900">{getDefaultGateway()}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">DNS Status</label>
          <p className="font-semibold text-gray-900">{getDNSStatus()}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">Active Services</label>
          <p className="font-semibold text-gray-900">{getRunningServices()}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">DHCP Status</label>
          <p className="font-semibold text-gray-900">{getDHCPStatus()}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">Firewall Status</label>
          <p className="font-semibold text-gray-900">{getFirewallStatus()}</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">Routes</label>
          <p className="font-semibold text-gray-900">{hostStatus?.routing_table?.length || 0} configured</p>
        </div>
      </div>

      {/* System Metrics */}
      {hostStatus?.system_metrics && (
        <div className="mb-4 p-3 bg-gray-50 rounded border">
          <h5 className="font-medium text-gray-900 mb-2">System Metrics</h5>
          {hasSystemMetricsError ? (
            <div className="p-2 bg-yellow-100 rounded text-yellow-800 text-sm flex items-center gap-2">
              <AlertTriangle size={16} />
              System metrics error: {hostStatus.system_metrics.error}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-gray-600">CPU Usage:</span>
                <span className="ml-2 font-mono">
                  {hostStatus.system_metrics.cpu?.usage_percent?.toFixed(1) || 0}%
                </span>
                {hostStatus.system_metrics.cpu?.load_average?.length > 0 && (
                  <div className="text-xs text-gray-500">
                    Load: {hostStatus.system_metrics.cpu.load_average[0]?.toFixed(2) || 'N/A'}
                  </div>
                )}
              </div>
              <div>
                <span className="text-gray-600">Memory:</span>
                <span className="ml-2 font-mono">
                  {hostStatus.system_metrics.memory?.usage_percent?.toFixed(1) || 0}%
                </span>
                {hostStatus.system_metrics.memory?.total_mb > 0 && (
                  <div className="text-xs text-gray-500">
                    {hostStatus.system_metrics.memory.used_mb}MB / {hostStatus.system_metrics.memory.total_mb}MB
                  </div>
                )}
              </div>
              <div>
                <span className="text-gray-600">Disk Usage:</span>
                <span className="ml-2 font-mono">
                  {hostStatus.system_metrics.disk?.usage_percent?.toFixed(1) || 0}%
                </span>
                {hostStatus.system_metrics.disk?.total_gb > 0 && (
                  <div className="text-xs text-gray-500">
                    {hostStatus.system_metrics.disk.used_gb}GB / {hostStatus.system_metrics.disk.total_gb}GB
                  </div>
                )}
              </div>
              <div>
                <span className="text-gray-600">Processes:</span>
                <span className="ml-2 font-mono">
                  {hostStatus.system_metrics.processes || 0}
                </span>
                <div className="text-xs text-gray-500">
                  Uptime: {hostStatus.system_metrics.uptime || 'Unknown'}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Network Services Status */}
      {hostStatus?.network_services && Object.keys(hostStatus.network_services).length > 0 && (
        <div className="mb-4 p-3 bg-gray-50 rounded border">
          <h5 className="font-medium text-gray-900 mb-2">Network Services</h5>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(hostStatus.network_services).map(([serviceName, service]) => (
              <div key={serviceName} className="flex items-center justify-between p-2 bg-white rounded border">
                <div className="flex items-center gap-2">
                  {service.running ? (
                    <CheckCircle size={16} className="text-green-500" />
                  ) : service.port_listening ? (
                    <AlertTriangle size={16} className="text-yellow-500" />
                  ) : (
                    <XCircle size={16} className="text-gray-400" />
                  )}
                  <div>
                    <div className="font-medium text-sm">{service.name}</div>
                    <div className="text-xs text-gray-500">
                      Port: {service.port}
                      {service.port_listening && ' (Listening)'}
                      {service.processes?.length > 0 && ` | ${service.processes.length} proc`}
                    </div>
                  </div>
                </div>
                <div className={`text-xs px-2 py-1 rounded ${
                  service.running 
                    ? 'bg-green-100 text-green-800' 
                    : service.port_listening 
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-gray-100 text-gray-600'
                }`}>
                  {service.running ? 'Running' : service.port_listening ? 'Listening' : 'Stopped'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interface Information - Handle empty interfaces */}
      {hostStatus?.interfaces?.length > 0 ? (
        <div className="mb-4 p-3 bg-gray-50 rounded border">
          <h5 className="font-medium text-gray-900 mb-2">Network Interfaces</h5>
          <div className="space-y-3">
            {hostStatus.interfaces.map((intf, idx) => (
              <div key={idx} className="bg-white p-3 rounded border">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-medium">{intf.name}</div>
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${
                      intf.state === 'up' ? 'bg-green-500' : 'bg-red-500'
                    }`} />
                    <span className="text-sm font-medium">{intf.state}</span>
                  </div>
                </div>
                <div className="text-sm text-gray-600 mb-2">
                  <div>IP: {intf.ip_addresses?.join(', ') || 'Not configured'}</div>
                  <div>MAC: {intf.mac_address || 'Unknown'}</div>
                  <div>MTU: {intf.mtu || 1500}</div>
                </div>
                {intf.statistics && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs text-gray-600">
                    <span>RX: {(intf.statistics.rx_bytes || 0).toLocaleString()} bytes</span>
                    <span>TX: {(intf.statistics.tx_bytes || 0).toLocaleString()} bytes</span>
                    <span>RX Packets: {(intf.statistics.rx_packets || 0).toLocaleString()}</span>
                    <span>TX Packets: {(intf.statistics.tx_packets || 0).toLocaleString()}</span>
                    {intf.statistics.rx_errors > 0 && (
                      <span className="text-red-600">RX Errors: {intf.statistics.rx_errors}</span>
                    )}
                    {intf.statistics.tx_errors > 0 && (
                      <span className="text-red-600">TX Errors: {intf.statistics.tx_errors}</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="mb-4 p-3 bg-yellow-50 rounded border border-yellow-200">
          <div className="flex items-center gap-2 text-yellow-800">
            <AlertTriangle size={16} />
            <span className="font-medium">No interface information available</span>
          </div>
          <p className="text-sm text-yellow-700 mt-1">
            Interface data may not be populated yet. Try refreshing the status.
          </p>
        </div>
      )}

      {/* Listening Services Summary */}
      {listeningServices.length > 0 && (
        <div className="mb-4 p-3 bg-blue-50 rounded border border-blue-200">
          <h5 className="font-medium text-blue-900 mb-2">Services Listening on Ports</h5>
          <div className="flex flex-wrap gap-2">
            {listeningServices.map((service) => (
              <span key={service.key} className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">
                {service.name} ({service.port})
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex gap-2 mt-4">
        <ActionButton
          onClick={onRefreshStatus}
          loading={loading}
          icon={<RefreshCw size={16} />}
          label="Refresh Status"
          variant="secondary"
          size="sm"
        />
        <ActionButton
          onClick={() => onTestConnectivity('8.8.8.8', 'ping')}
          loading={loading}
          icon={<Network size={16} />}
          label="Test Internet"
          variant="secondary"
          size="sm"
        />
        {/* Show gateway test if default route exists */}
        {getDefaultGateway() !== 'None' && (
          <ActionButton
            onClick={() => onTestConnectivity(getDefaultGateway(), 'ping')}
            loading={loading}
            icon={<Router size={16} />}
            label="Test Gateway"
            variant="secondary"
            size="sm"
          />
        )}
      </div>

      {/* Status Warnings */}
      <div className="mt-4 space-y-2">
        {hostStatus?.interfaces?.length === 0 && (
          <div className="p-2 bg-yellow-100 rounded text-yellow-800 text-sm flex items-center gap-2">
            <AlertTriangle size={16} />
            No network interfaces configured or detected
          </div>
        )}
        {getDefaultGateway() === 'None' && (
          <div className="p-2 bg-yellow-100 rounded text-yellow-800 text-sm flex items-center gap-2">
            <AlertTriangle size={16} />
            No default gateway configured
          </div>
        )}
        {(!hostStatus?.dns_config?.nameservers || hostStatus.dns_config.nameservers.length === 0) && (
          <div className="p-2 bg-yellow-100 rounded text-yellow-800 text-sm flex items-center gap-2">
            <AlertTriangle size={16} />
            No DNS servers configured
          </div>
        )}
        {hostStatus?.firewall_status?.iptables_available && hostStatus.firewall_status.rule_count === 0 && (
          <div className="p-2 bg-blue-100 rounded text-blue-800 text-sm flex items-center gap-2">
            <AlertTriangle size={16} />
            Firewall available but no rules configured
          </div>
        )}
      </div>
    </ConfigSection>
  );
};