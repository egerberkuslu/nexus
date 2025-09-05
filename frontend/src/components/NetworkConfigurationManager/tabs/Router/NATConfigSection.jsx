import React from 'react';
import { FiShield, FiPlus } from 'react-icons/fi';
import ConfigSection from '../../components/ConfigSection';
import { CheckboxField, InputField, SelectField } from '../../components/FormComponents';

export function NATConfigSection({ 
  local, 
  sections, 
  dispatch, 
  onToggle, 
  renderNatLines,
  onNatStructuralChange
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

  // Handle NAT rule field changes
  const handleNatRuleFieldChange = (index, field, value) => {
    console.log('NAT rule field change:', { index, field, value });
    dispatch({ type: 'NAT_SET', index, field, value });
  };

  // Handle NAT rule removal with proper tracking
  const handleNatRuleRemove = (index) => {
    console.log('Removing NAT rule at index:', index);
    
    // Call structural change callback BEFORE dispatching the removal
    if (onNatStructuralChange) {
      onNatStructuralChange();
    }
    
    // Instead of immediately removing, mark for deletion if it exists on the router
    const ruleToRemove = local.natRules[index];
    if (ruleToRemove) {
      // Check if this is an existing rule that needs to be deleted on the router
      if (ruleToRemove.id && !ruleToRemove.id.includes('new-')) {
        // Mark existing rule for deletion
        dispatch({ 
          type: 'NAT_SET', 
          index, 
          field: 'operation', 
          value: 'delete' 
        });
        console.log('Marked NAT rule for deletion:', ruleToRemove.type);
      } else {
        // Remove new rule that hasn't been applied yet
        dispatch({ type: 'NAT_RM', index });
        console.log('Removed new NAT rule:', ruleToRemove.type);
      }
    }
  };

  // Handle NAT rule addition with proper tracking
  const handleNatRuleAdd = () => {
    console.log('Adding new NAT rule');
    
    // Call structural change callback BEFORE dispatching the addition
    if (onNatStructuralChange) {
      onNatStructuralChange();
    }
    
    dispatch({ type: 'NAT_ADD' });
  };

  // Filter out NAT rules marked for deletion from display
  const visibleNatRules = (local.natRules || []).filter(rule => rule.operation !== 'delete');

  // Generate preview for NAT rule
  const generateNatRulePreview = (rule) => {
    const parts = [];
    parts.push(`iptables -t nat -A ${rule.chain || 'POSTROUTING'}`);
    
    if (rule.source) parts.push(`-s ${rule.source}`);
    if (rule.destination) parts.push(`-d ${rule.destination}`);
    if (rule.out_interface) parts.push(`-o ${rule.out_interface}`);
    
    if (rule.type === 'snat' && rule.to_source) {
      parts.push(`-j SNAT --to-source ${rule.to_source}`);
    } else if (rule.type === 'dnat' && rule.to_destination) {
      parts.push(`-j DNAT --to-destination ${rule.to_destination}`);
    } else {
      parts.push(`-j ${rule.target || 'MASQUERADE'}`);
    }
    
    return parts.join(' ');
  };

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
        <h4 className="font-medium text-gray-900 mb-3">Configure NAT Rules</h4>
        
        {visibleNatRules.map((rule, i) => {
          // Find original index in the full natRules array
          const originalIndex = local.natRules.findIndex(originalRule => 
            originalRule.id === rule.id || 
            (originalRule.type === rule.type && 
             originalRule.chain === rule.chain && 
             originalRule.source === rule.source && 
             originalRule.operation !== 'delete')
          );
          
          return (
            <div key={rule.id || i} className="space-y-4 mb-6 p-4 border rounded bg-white">
              {/* First row: Basic rule properties */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <SelectField 
                  label="Type" 
                  value={rule.type || 'masquerade'} 
                  onChange={(v) => handleNatRuleFieldChange(originalIndex, 'type', v)} 
                  options={natTypeOptions} 
                />
                
                <SelectField 
                  label="Chain" 
                  value={rule.chain || 'POSTROUTING'} 
                  onChange={(v) => handleNatRuleFieldChange(originalIndex, 'chain', v)} 
                  options={chainOptions} 
                />
                
                <InputField 
                  label="Source" 
                  value={rule.source || ''} 
                  onChange={(v) => handleNatRuleFieldChange(originalIndex, 'source', v)} 
                  placeholder="0.0.0.0/0 or 192.168.1.0/24" 
                />
                
                <InputField 
                  label="Destination" 
                  value={rule.destination || ''} 
                  onChange={(v) => handleNatRuleFieldChange(originalIndex, 'destination', v)} 
                  placeholder="0.0.0.0/0 or specific IP" 
                />
              </div>

              {/* Second row: Interface and type-specific fields */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <InputField 
                  label="Out Interface" 
                  value={rule.out_interface || ''} 
                  onChange={(v) => handleNatRuleFieldChange(originalIndex, 'out_interface', v)} 
                  placeholder="eth0, eth1" 
                />
                
                {/* Type-specific fields */}
                {rule.type === 'snat' && (
                  <InputField 
                    label="To Source" 
                    value={rule.to_source || ''} 
                    onChange={(v) => handleNatRuleFieldChange(originalIndex, 'to_source', v)} 
                    placeholder="192.168.1.1 or range" 
                  />
                )}
                
                {rule.type === 'dnat' && (
                  <InputField 
                    label="To Destination" 
                    value={rule.to_destination || ''} 
                    onChange={(v) => handleNatRuleFieldChange(originalIndex, 'to_destination', v)} 
                    placeholder="192.168.1.100:80" 
                  />
                )}
                
                {rule.type === 'custom' && (
                  <SelectField 
                    label="Target" 
                    value={rule.target || 'MASQUERADE'} 
                    onChange={(v) => handleNatRuleFieldChange(originalIndex, 'target', v)} 
                    options={targetOptions} 
                  />
                )}

                {/* Preview column */}
                <div className="flex flex-col">
                  <label className="text-sm font-medium text-gray-600 mb-1">Preview</label>
                  <div className="p-2 bg-gray-50 rounded text-xs font-mono break-all">
                    {generateNatRulePreview(rule)}
                  </div>
                </div>

                {/* Actions column */}
                <div className="flex flex-col">
                  <label className="text-sm font-medium text-gray-600 mb-1">Actions</label>
                  <button 
                    onClick={() => handleNatRuleRemove(originalIndex)} 
                    className="p-2 text-red-600 hover:bg-red-50 rounded border" 
                    title="Remove NAT rule"
                  >
                    Remove
                  </button>
                </div>
              </div>
            </div>
          );
        })}
        
        <button 
          onClick={handleNatRuleAdd} 
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <FiPlus size={16} /> Add NAT Rule
        </button>
      </div>

      {/* Show pending deletions */}
      {local.natRules?.some(rule => rule.operation === 'delete') && (
        <div className="mb-4 p-3 bg-red-50 rounded border border-red-200">
          <h5 className="font-medium text-red-800 mb-2">Pending NAT Rule Deletions</h5>
          <div className="space-y-1">
            {local.natRules
              .filter(rule => rule.operation === 'delete')
              .map((rule, i) => (
                <div key={i} className="text-sm text-red-700 font-mono">
                  • {rule.type?.toUpperCase()} rule on {rule.chain} chain will be deleted when configuration is applied
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Help Text */}
      <div className="mt-4 p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>NAT Rule Examples:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>MASQUERADE:</strong> Type: masquerade, Source: 192.168.1.0/24, Out Interface: eth0</li>
          <li>• <strong>SNAT:</strong> Type: snat, Source: 10.0.0.0/8, To Source: 203.0.113.1</li>
          <li>• <strong>DNAT:</strong> Type: dnat, Destination: 203.0.113.1:80, To Destination: 192.168.1.100:8080</li>
          <li>• <strong>Port Forward:</strong> Type: dnat, Chain: PREROUTING, Destination: external_ip, To Destination: internal_ip:port</li>
        </ul>
      </div>
    </ConfigSection>
  );
}