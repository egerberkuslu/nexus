// InterfaceConfigSection.jsx - Network interface configuration
import React from 'react';
import { Wifi, Plus } from 'lucide-react';
import ConfigSection from '../../components/ConfigSection';
import { InputField, SelectField } from '../../components/FormComponents';

export const InterfaceConfigSection = ({ 
  local, 
  hostStatus, 
  sections, 
  dispatch, 
  onToggle 
}) => {
  const currentInterfaces = hostStatus?.interfaces || [];

  const stateOptions = [
    { value: 'up', label: 'Up' },
    { value: 'down', label: 'Down' }
  ];

  return (
    <ConfigSection
      title="Network Interface Configuration"
      icon={Wifi}
      expanded={sections.interfaces}
      onToggle={() => onToggle('interfaces')}
    >
      {/* Current Interfaces Display */}
      {currentInterfaces.length > 0 && (
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-3">Current Interfaces</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {currentInterfaces.map((intf, idx) => (
              <div key={idx} className="p-3 bg-gray-50 rounded border">
                <div className="font-medium text-gray-900">{intf.name}</div>
                <div className="text-sm text-gray-600">
                  IPs: {intf.ip_addresses?.join(', ') || 'None'}
                </div>
                <div className="text-sm text-gray-600">
                  MAC: {intf.mac_address}
                </div>
                <div className="text-sm text-gray-600">
                  MTU: {intf.mtu || 1500}
                </div>
                <div className="text-sm text-gray-600">
                  State: <span className={`font-medium ${intf.state === 'up' ? 'text-green-600' : 'text-red-600'}`}>
                    {intf.state}
                  </span>
                </div>
                {intf.statistics && (
                  <div className="text-xs text-gray-500 mt-1">
                    RX: {(intf.statistics.rx_bytes || 0).toLocaleString()} bytes, 
                    TX: {(intf.statistics.tx_bytes || 0).toLocaleString()} bytes
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Interface Configuration */}
      <div className="mb-4">
        <h4 className="font-medium text-gray-900 mb-3">Interface Configuration</h4>
        
        {(local.interfaces || []).map((intf, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4 p-4 border rounded bg-white">
            <InputField
              label="Interface Name"
              value={intf.name || ''}
              onChange={(v) => dispatch({ type: 'INTERFACE_SET', index: i, field: 'name', value: v })}
              placeholder="eth0"
              helper="Network interface name"
            />
            <InputField
              label="IP Address/CIDR"
              value={intf.ip_address || ''}
              onChange={(v) => dispatch({ type: 'INTERFACE_SET', index: i, field: 'ip_address', value: v })}
              placeholder="192.168.1.100/24"
              helper="IP address with subnet mask"
            />
            <SelectField
              label="State"
              value={intf.state || 'up'}
              onChange={(v) => dispatch({ type: 'INTERFACE_SET', index: i, field: 'state', value: v })}
              options={stateOptions}
              helper="Interface administrative state"
            />
            <InputField
              label="MTU"
              value={intf.mtu || '1500'}
              onChange={(v) => dispatch({ type: 'INTERFACE_SET', index: i, field: 'mtu', value: v })}
              placeholder="1500"
              helper="Maximum transmission unit"
            />
            <div className="flex flex-col justify-end">
              <button
                onClick={() => dispatch({ type: 'INTERFACE_REMOVE', index: i })}
                className="p-2 text-red-600 hover:bg-red-50 rounded border"
                title="Remove interface configuration"
              >
                Remove
              </button>
            </div>
          </div>
        ))}

        <button
          onClick={() => dispatch({ type: 'INTERFACE_ADD' })}
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <Plus size={16} /> Add Interface Configuration
        </button>
      </div>

      {/* Help Text */}
      <div className="p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>Interface Configuration:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>IP Address/CIDR:</strong> Use format like 192.168.1.100/24</li>
          <li>• <strong>State:</strong> Set interface administrative state (up/down)</li>
          <li>• <strong>MTU:</strong> Maximum transmission unit (typically 1500 for Ethernet)</li>
          <li>• Changes will flush existing IP addresses and reconfigure the interface</li>
        </ul>
      </div>
    </ConfigSection>
  );
};