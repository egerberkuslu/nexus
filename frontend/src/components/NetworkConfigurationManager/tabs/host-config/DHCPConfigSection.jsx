// DHCPConfigSection.jsx - DHCP client/server configuration with API integration
import React from 'react';
import { Network, Server, Users, Wifi } from 'lucide-react';
import ConfigSection from '../../components/ConfigSection';
import { InputField, SelectField } from '../../components/FormComponents';

export const DHCPConfigSection = ({ 
  local, 
  hostStatus, 
  sections, 
  dispatch, 
  onToggle 
}) => {
  const dhcpStatus = hostStatus?.dhcp_status || {};
  const interfaces = hostStatus?.interfaces || [];

  const dhcpModeOptions = [
    { value: 'disabled', label: 'Disabled' },
    { value: 'client', label: 'DHCP Client' },
    { value: 'server', label: 'DHCP Server' }
  ];

  const interfaceOptions = [
    { value: '', label: 'Select interface...' },
    ...interfaces.map(intf => ({
      value: intf.name,
      label: `${intf.name} (${intf.ip_addresses?.join(', ') || 'No IP'})`
    }))
  ];

  const getDHCPStatusIcon = (isRunning) => {
    return isRunning ? '🟢' : '🔴';
  };

  const handleDNSServersChange = (value) => {
    // Parse comma-separated DNS servers
    const servers = value.split(',').map(s => s.trim()).filter(s => s);
    dispatch({ 
      type: 'DHCP_SERVER_SET', 
      field: 'dns_servers', 
      value: servers 
    });
  };

  return (
    <ConfigSection
      title="DHCP Configuration"
      icon={Network}
      expanded={sections.dhcp}
      onToggle={() => onToggle('dhcp')}
    >
      {/* Current DHCP Status */}
      <div className="mb-6 p-4 bg-blue-50 rounded border border-blue-200">
        <h4 className="font-medium text-blue-900 mb-3">Current DHCP Status</h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white p-3 rounded border">
            <div className="flex items-center gap-2 mb-2">
              <Wifi size={16} className="text-blue-600" />
              <h5 className="font-medium text-blue-800">Client Status</h5>
            </div>
            <div className="space-y-1 text-sm">
              <div>
                <span className="text-blue-700">Active Leases:</span>
                <span className="ml-2 font-mono">{dhcpStatus.client?.active_leases?.length || 0}</span>
              </div>
              <div>
                <span className="text-blue-700">DHCP Interfaces:</span>
                <span className="ml-2 font-mono">
                  {dhcpStatus.client?.dhcp_enabled_interfaces?.join(', ') || 'None'}
                </span>
              </div>
              {dhcpStatus.client?.active_leases?.length > 0 && (
                <div className="mt-2 p-2 bg-blue-100 rounded text-xs">
                  <div className="font-medium text-blue-800">Active Leases:</div>
                  {dhcpStatus.client.active_leases.map((lease, idx) => (
                    <div key={idx} className="text-blue-700 font-mono">{lease}</div>
                  ))}
                </div>
              )}
              {dhcpStatus.client?.current_servers?.length > 0 && (
                <div className="mt-2">
                  <span className="text-blue-700">DHCP Servers:</span>
                  <span className="ml-2 font-mono text-xs">
                    {dhcpStatus.client.current_servers.join(', ')}
                  </span>
                </div>
              )}
            </div>
          </div>
          
          <div className="bg-white p-3 rounded border">
            <div className="flex items-center gap-2 mb-2">
              <Server size={16} className="text-green-600" />
              <h5 className="font-medium text-green-800">Server Status</h5>
            </div>
            <div className="space-y-1 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-green-700">Server Running:</span>
                <span className="text-lg">{getDHCPStatusIcon(dhcpStatus.server?.running)}</span>
                <span className="font-mono">{dhcpStatus.server?.running ? 'Yes' : 'No'}</span>
              </div>
              <div>
                <span className="text-green-700">Active Leases:</span>
                <span className="ml-2 font-mono">{dhcpStatus.server?.active_leases?.length || 0}</span>
              </div>
              {dhcpStatus.server?.config_file && (
                <div>
                  <span className="text-green-700">Config File:</span>
                  <span className="ml-2 font-mono text-xs">
                    {dhcpStatus.server.config_file}
                  </span>
                </div>
              )}
              {dhcpStatus.server?.configured_pools?.length > 0 && (
                <div className="mt-2 p-2 bg-green-100 rounded text-xs">
                  <div className="font-medium text-green-800">Configured Pools:</div>
                  {dhcpStatus.server.configured_pools.map((pool, idx) => (
                    <div key={idx} className="text-green-700 font-mono break-all">{pool}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* DHCP Mode Selection */}
      <div className="mb-6">
        <SelectField
          label="DHCP Mode"
          value={local.dhcp_mode || 'disabled'}
          onChange={(v) => dispatch({ type: 'SET_FIELD', field: 'dhcp_mode', value: v })}
          options={dhcpModeOptions}
          helper="Choose how this host should handle DHCP"
        />
      </div>

      {/* DHCP Client Configuration */}
      {local.dhcp_mode === 'client' && (
        <div className="mb-6 p-4 border rounded bg-white">
          <div className="flex items-center gap-2 mb-3">
            <Wifi size={16} className="text-blue-600" />
            <h4 className="font-medium text-gray-900">DHCP Client Configuration</h4>
          </div>
          
          <div className="grid grid-cols-1 gap-4">
            <SelectField
              label="Interface"
              value={local.dhcp_client_interface || ''}
              onChange={(v) => dispatch({ type: 'SET_FIELD', field: 'dhcp_client_interface', value: v })}
              options={interfaceOptions}
              helper="Network interface to configure via DHCP"
            />
          </div>

          <div className="mt-4 p-3 bg-blue-50 rounded text-sm text-blue-800">
            <strong>DHCP Client Mode:</strong> This host will request an IP address, gateway, and DNS servers from a DHCP server on the network.
          </div>
          
          {local.dhcp_client_interface && (
            <div className="mt-3 p-3 bg-yellow-50 rounded text-sm text-yellow-800">
              <strong>Note:</strong> The interface "{local.dhcp_client_interface}" will have its current IP configuration replaced by DHCP.
            </div>
          )}
        </div>
      )}

      {/* DHCP Server Configuration */}
      {local.dhcp_mode === 'server' && (
        <div className="mb-6 p-4 border rounded bg-white">
          <div className="flex items-center gap-2 mb-3">
            <Server size={16} className="text-green-600" />
            <h4 className="font-medium text-gray-900">DHCP Server Configuration</h4>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <InputField
              label="Subnet"
              value={local.dhcp_server_config?.subnet || ''}
              onChange={(v) => dispatch({ type: 'DHCP_SERVER_SET', field: 'subnet', value: v })}
              placeholder="192.168.1.0"
              helper="Network subnet (without CIDR)"
            />
            
            <InputField
              label="Netmask"
              value={local.dhcp_server_config?.netmask || '255.255.255.0'}
              onChange={(v) => dispatch({ type: 'DHCP_SERVER_SET', field: 'netmask', value: v })}
              placeholder="255.255.255.0"
              helper="Subnet mask for the network"
            />
            
            <InputField
              label="Range Start"
              value={local.dhcp_server_config?.range_start || ''}
              onChange={(v) => dispatch({ type: 'DHCP_SERVER_SET', field: 'range_start', value: v })}
              placeholder="192.168.1.100"
              helper="First IP address in DHCP pool"
            />
            
            <InputField
              label="Range End"
              value={local.dhcp_server_config?.range_end || ''}
              onChange={(v) => dispatch({ type: 'DHCP_SERVER_SET', field: 'range_end', value: v })}
              placeholder="192.168.1.200"
              helper="Last IP address in DHCP pool"
            />
            
            <InputField
              label="Default Gateway (Optional)"
              value={local.dhcp_server_config?.gateway || ''}
              onChange={(v) => dispatch({ type: 'DHCP_SERVER_SET', field: 'gateway', value: v })}
              placeholder="192.168.1.1"
              helper="Gateway to provide to clients"
            />
            
            <InputField
              label="DNS Servers (Optional)"
              value={local.dhcp_server_config?.dns_servers?.join(', ') || ''}
              onChange={handleDNSServersChange}
              placeholder="8.8.8.8, 8.8.4.4"
              helper="Comma-separated DNS servers"
            />
          </div>

          <div className="mt-4 p-3 bg-green-50 rounded text-sm text-green-800">
            <strong>DHCP Server Mode:</strong> This host will provide IP addresses to other devices on the network.
          </div>
          
          <div className="mt-3 p-3 bg-yellow-50 rounded text-sm text-yellow-800">
            <strong>Important:</strong> Ensure this host has a static IP configuration outside the DHCP range before enabling the DHCP server.
          </div>
        </div>
      )}

      {/* DHCP Server Active Leases */}
      {dhcpStatus.server?.active_leases?.length > 0 && (
        <div className="mb-4 p-4 bg-green-50 rounded border border-green-200">
          <div className="flex items-center gap-2 mb-2">
            <Users size={16} className="text-green-600" />
            <h5 className="font-medium text-green-900">Active DHCP Leases</h5>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {dhcpStatus.server.active_leases.map((lease, idx) => (
              <div key={idx} className="bg-white p-2 rounded border text-sm">
                <div className="font-mono text-green-700">{lease}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Warning for Multiple DHCP Servers */}
      {local.dhcp_mode === 'server' && (
        <div className="mb-4 p-3 bg-red-50 rounded border border-red-200">
          <div className="flex items-center gap-2 mb-1">
            <Server size={16} className="text-red-600" />
            <span className="font-medium text-red-900">Critical Warning</span>
          </div>
          <p className="text-sm text-red-800">
            Only one DHCP server should be active per network segment. Multiple DHCP servers will cause IP address conflicts and severe connectivity issues.
          </p>
        </div>
      )}

      {/* Configuration Summary */}
      {local.dhcp_mode !== 'disabled' && (
        <div className="p-3 bg-gray-100 rounded text-sm text-gray-600">
          <strong>DHCP Configuration will be applied when you click "Apply Configuration"</strong>
          {local.dhcp_mode === 'client' && local.dhcp_client_interface && (
            <div className="mt-2 text-xs">
              • Interface <span className="font-mono">{local.dhcp_client_interface}</span> will request IP via DHCP
            </div>
          )}
          {local.dhcp_mode === 'server' && local.dhcp_server_config?.subnet && (
            <div className="mt-2 text-xs">
              • DHCP server will serve subnet <span className="font-mono">{local.dhcp_server_config.subnet}/{local.dhcp_server_config.netmask}</span>
              <br />• IP range: <span className="font-mono">{local.dhcp_server_config.range_start} - {local.dhcp_server_config.range_end}</span>
            </div>
          )}
        </div>
      )}

      {/* DHCP Help */}
      <div className="p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>DHCP Configuration Guide:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>Client Mode:</strong> Automatically request IP configuration from a DHCP server</li>
          <li>• <strong>Server Mode:</strong> Provide IP addresses to other devices on the network</li>
          <li>• <strong>Network Planning:</strong> Ensure DHCP range doesn't overlap with static IPs</li>
          <li>• <strong>DNS Servers:</strong> Separate multiple DNS servers with commas</li>
          <li>• <strong>Gateway:</strong> Usually the router's IP address on the same subnet</li>
          <li>• DHCP server requires the host to have a static IP outside the DHCP range</li>
        </ul>
      </div>
    </ConfigSection>
  );
};