import React from 'react';
import { FiShield, FiPlus } from 'react-icons/fi';
import ConfigSection from '../../components/ConfigSection';
import { CheckboxField, InputField, SelectField } from '../../components/FormComponents';

export function NATConfigSection({ 
  local, 
  sections, 
  dispatch, 
  onToggle, 
  renderNatLines 
}) {
  const natLines = renderNatLines();

  const natTypeOptions = [
    { value: 'masquerade', label: 'MASQUERADE' },
    { value: 'snat', label: 'SNAT' },
    { value: 'dnat', label: 'DNAT' },
    { value: 'custom', label: 'Custom' }
  ];

  const chainOptions = [
    { value: 'PREROUTING', label: 'PREROUTING' },
    { value: 'POSTROUTING', label: 'POSTROUTING' },
    { value: 'OUTPUT', label: 'OUTPUT' }
  ];

  const targetOptions = [
    { value: 'MASQUERADE', label: 'MASQUERADE' },
    { value: 'SNAT', label: 'SNAT' },
    { value: 'DNAT', label: 'DNAT' },
    { value: 'ACCEPT', label: 'ACCEPT' },
    { value: 'DROP', label: 'DROP' }
  ];

  return (
    <ConfigSection 
      title="NAT Configuration" 
      icon={FiShield} 
      expanded={sections.nat} 
      onToggle={() => onToggle('nat')}
    >
      {/* Legacy NAT Enable/Disable */}
      <div className="mb-6 p-4 bg-blue-50 rounded-lg border border-blue-200">
        <h4 className="font-medium text-blue-900 mb-2">Quick NAT Setup</h4>
        <CheckboxField 
          label="Enable Basic NAT (Legacy)" 
          checked={local.natEnabled || false} 
          onChange={(v) => dispatch({ type: 'SET_FIELD', field: 'natEnabled', value: v })} 
          helper="Enables basic masquerading for WAN interface (backward compatibility)" 
        />
      </div>

      {/* Current NAT Rules from snapshot */}
      {natLines.length > 0 && (
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-2">Current NAT Rules (Read-only)</h4>
          <div className="bg-gray-50 p-3 rounded border max-h-40 overflow-y-auto">
            {natLines.map((line, i) => (
              <div key={i} className="text-xs font-mono text-gray-700 mb-1">
                {line}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Advanced NAT Rules CRUD */}
      <div className="mb-4">
        <h4 className="font-medium text-gray-900 mb-3">Advanced NAT Rules</h4>
        
        {(local.natRules || []).map((rule, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-4 p-4 border rounded bg-white">
            <SelectField 
              label="Type" 
              value={rule.type || 'masquerade'} 
              onChange={(v) => dispatch({ type: 'NAT_SET', index: i, field: 'type', value: v })} 
              options={natTypeOptions} 
            />
            
            <SelectField 
              label="Chain" 
              value={rule.chain || 'POSTROUTING'} 
              onChange={(v) => dispatch({ type: 'NAT_SET', index: i, field: 'chain', value: v })} 
              options={chainOptions} 
            />
            
            <InputField 
              label="Source" 
              value={rule.source || ''} 
              onChange={(v) => dispatch({ type: 'NAT_SET', index: i, field: 'source', value: v })} 
              placeholder="0.0.0.0/0 or 192.168.1.0/24" 
            />
            
            <InputField 
              label="Destination" 
              value={rule.destination || ''} 
              onChange={(v) => dispatch({ type: 'NAT_SET', index: i, field: 'destination', value: v })} 
              placeholder="0.0.0.0/0 or specific IP" 
            />
            
            <InputField 
              label="Out Interface" 
              value={rule.out_interface || ''} 
              onChange={(v) => dispatch({ type: 'NAT_SET', index: i, field: 'out_interface', value: v })} 
              placeholder="eth0, eth1" 
            />
            
            <div className="flex flex-col">
              <label className="text-sm font-medium text-gray-600 mb-1">Actions</label>
              <button 
                onClick={() => dispatch({ type: 'NAT_RM', index: i })} 
                className="p-2 text-red-600 hover:bg-red-50 rounded border" 
                title="Remove NAT rule"
              >
                Remove
              </button>
            </div>
            
            {/* Additional fields for SNAT/DNAT */}
            {rule.type === 'snat' && (
              <div className="md:col-span-2">
                <InputField 
                  label="To Source" 
                  value={rule.to_source || ''} 
                  onChange={(v) => dispatch({ type: 'NAT_SET', index: i, field: 'to_source', value: v })} 
                  placeholder="192.168.1.1 or range" 
                />
              </div>
            )}
            
            {rule.type === 'dnat' && (
              <div className="md:col-span-2">
                <InputField 
                  label="To Destination" 
                  value={rule.to_destination || ''} 
                  onChange={(v) => dispatch({ type: 'NAT_SET', index: i, field: 'to_destination', value: v })} 
                  placeholder="192.168.1.100:80" 
                />
              </div>
            )}
            
            {rule.type === 'custom' && (
              <div className="md:col-span-2">
                <SelectField 
                  label="Target" 
                  value={rule.target || 'MASQUERADE'} 
                  onChange={(v) => dispatch({ type: 'NAT_SET', index: i, field: 'target', value: v })} 
                  options={targetOptions} 
                />
              </div>
            )}
          </div>
        ))}
        
        <button 
          onClick={() => dispatch({ type: 'NAT_ADD' })} 
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <FiPlus size={16} /> Add NAT Rule
        </button>
      </div>

      {/* Help Text */}
      <div className="mt-4 p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>NAT Rule Examples:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>MASQUERADE:</strong> Source: 192.168.1.0/24, Out Interface: eth0</li>
          <li>• <strong>SNAT:</strong> Source: 10.0.0.0/8, To Source: 203.0.113.1</li>
          <li>• <strong>DNAT:</strong> Destination: 203.0.113.1:80, To Destination: 192.168.1.100:8080</li>
        </ul>
      </div>
    </ConfigSection>
  );
}