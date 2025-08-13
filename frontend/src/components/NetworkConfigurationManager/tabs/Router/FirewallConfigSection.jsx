import React from 'react';
import { FiShield, FiPlus } from 'react-icons/fi';
import ConfigSection from '../../components/ConfigSection';
import { SelectField, InputField } from '../../components/FormComponents';

export function FirewallConfigSection({ 
   local, 
  sections, 
  dispatch, 
  onToggle, 
  renderFirewallLines 
}) {
  const firewallLines = renderFirewallLines();
  
  const chainOptions = [
    { value: 'INPUT', label: 'INPUT' },
    { value: 'OUTPUT', label: 'OUTPUT' },
    { value: 'FORWARD', label: 'FORWARD' },
    { value: 'PREROUTING', label: 'PREROUTING' },
    { value: 'POSTROUTING', label: 'POSTROUTING' }
  ];

  const protocolOptions = [
    { value: '', label: 'Any' },
    { value: 'tcp', label: 'TCP' },
    { value: 'udp', label: 'UDP' },
    { value: 'icmp', label: 'ICMP' },
    { value: 'all', label: 'All' }
  ];

  const targetOptions = [
    { value: 'ACCEPT', label: 'ACCEPT' },
    { value: 'DROP', label: 'DROP' },
    { value: 'REJECT', label: 'REJECT' },
    { value: 'LOG', label: 'LOG' },
    { value: 'RETURN', label: 'RETURN' }
  ];

  const stateOptions = [
    { value: '', label: 'No state matching' },
    { value: 'NEW', label: 'NEW' },
    { value: 'ESTABLISHED', label: 'ESTABLISHED' },
    { value: 'RELATED', label: 'RELATED' },
    { value: 'ESTABLISHED,RELATED', label: 'ESTABLISHED,RELATED' },
    { value: 'NEW,ESTABLISHED,RELATED', label: 'ALL' }
  ];

  return (
    <ConfigSection 
      title="Firewall Rules" 
      icon={FiShield} 
      expanded={sections.firewall} 
      onToggle={() => onToggle('firewall')}
    >
      {/* Current Firewall Rules from snapshot */}
      {firewallLines.length > 0 && (
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-2">Current Firewall Rules (Read-only)</h4>
          <div className="bg-gray-50 p-3 rounded border max-h-40 overflow-y-auto">
            {firewallLines.map((line, i) => (
              <div key={i} className="text-xs font-mono text-gray-700 mb-1">
                {line}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Advanced Firewall Rules CRUD */}
      <div className="mb-4">
        <h4 className="font-medium text-gray-900 mb-3">Firewall Rules</h4>
        
        {(local.firewallRules || []).map((rule, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4 p-4 border rounded bg-white">
            {/* Row 1: Basic rule properties */}
            <SelectField 
              label="Chain" 
              value={rule.chain || 'INPUT'} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'chain', value: v })} 
              options={chainOptions} 
            />
            
            <SelectField 
              label="Protocol" 
              value={rule.protocol || ''} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'protocol', value: v })} 
              options={protocolOptions} 
            />
            
            <SelectField 
              label="Target" 
              value={rule.target || 'ACCEPT'} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'target', value: v })} 
              options={targetOptions} 
            />
            
            <div className="flex flex-col">
              <label className="text-sm font-medium text-gray-600 mb-1">Actions</label>
              <button 
                onClick={() => dispatch({ type: 'FW_RM', index: i })} 
                className="p-2 text-red-600 hover:bg-red-50 rounded border" 
                title="Remove firewall rule"
              >
                Remove
              </button>
            </div>
            
            {/* Row 2: Source and Destination */}
            <InputField 
              label="Source" 
              value={rule.source || ''} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'source', value: v })} 
              placeholder="0.0.0.0/0 or 192.168.1.0/24" 
            />
            
            <InputField 
              label="Destination" 
              value={rule.destination || ''} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'destination', value: v })} 
              placeholder="0.0.0.0/0 or specific IP" 
            />
            
            <InputField 
              label="Source Port" 
              value={rule.sport || ''} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'sport', value: v })} 
              placeholder="80, 443, 1024:65535" 
            />
            
            <InputField 
              label="Dest Port" 
              value={rule.dport || ''} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'dport', value: v })} 
              placeholder="22, 80, 443" 
            />
            
            {/* Row 3: Advanced options */}
            <InputField 
              label="In Interface" 
              value={rule.in_interface || ''} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'in_interface', value: v })} 
              placeholder="eth0, eth1" 
            />
            
            <InputField 
              label="Out Interface" 
              value={rule.out_interface || ''} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'out_interface', value: v })} 
              placeholder="eth0, eth1" 
            />
            
            <SelectField 
              label="Connection State" 
              value={rule.state || ''} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'state', value: v })} 
              options={stateOptions} 
            />
            
            <InputField 
              label="Position" 
              value={rule.position || ''} 
              onChange={(v) => dispatch({ type: 'FW_SET', index: i, field: 'position', value: v })} 
              placeholder="1, 2, 3..." 
              helper="Rule position for INSERT" 
            />
          </div>
        ))}
        
        <button 
          onClick={() => dispatch({ type: 'FW_ADD' })} 
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <FiPlus size={16} /> Add Firewall Rule
        </button>
      </div>

      {/* Legacy Firewall Rules (backward compatibility) */}
      <div className="mb-4">
        <h4 className="font-medium text-gray-900 mb-3">Legacy Firewall Rules (Raw iptables)</h4>
        
        {(local.legacyFirewallRules || []).map((r, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-4 p-4 border rounded bg-gray-50">
            <SelectField 
              label="Action" 
              value={r.action || '-A'} 
              onChange={(v) => dispatch({ type: 'LEGACY_FW_SET', index: i, field: 'action', value: v })} 
              options={[
                { value: '-A', label: 'Append (-A)' }, 
                { value: '-I', label: 'Insert (-I)' }, 
                { value: '-D', label: 'Delete (-D)' }
              ]} 
            />
            
            <InputField 
              label="Chain" 
              value={r.chain || 'INPUT'} 
              onChange={(v) => dispatch({ type: 'LEGACY_FW_SET', index: i, field: 'chain', value: v })} 
              placeholder="INPUT" 
            />
            
            <InputField 
              label="Parameters" 
              value={r.parameters || ''} 
              onChange={(v) => dispatch({ type: 'LEGACY_FW_SET', index: i, field: 'parameters', value: v })} 
              placeholder="-p tcp --dport 22 -j ACCEPT" 
            />
            
            <button 
              onClick={() => dispatch({ type: 'LEGACY_FW_RM', index: i })} 
              className="self-end p-2 text-red-600 hover:bg-red-50 rounded" 
              title="Remove rule"
            >
              ×
            </button>
          </div>
        ))}
        
        <button 
          onClick={() => dispatch({ type: 'LEGACY_FW_ADD' })} 
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <FiPlus size={16} /> Add Legacy Rule
        </button>
      </div>

      {/* Help Text */}
      <div className="mt-4 p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>Firewall Rule Examples:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>Allow SSH:</strong> Chain: INPUT, Protocol: tcp, Dest Port: 22, Target: ACCEPT</li>
          <li>• <strong>Block IP:</strong> Chain: INPUT, Source: 192.168.1.100, Target: DROP</li>
          <li>• <strong>Allow Established:</strong> Chain: INPUT, State: ESTABLISHED,RELATED, Target: ACCEPT</li>
          <li>• <strong>Port Forward:</strong> Chain: FORWARD, In Interface: eth0, Out Interface: eth1, Target: ACCEPT</li>
        </ul>
      </div>
    </ConfigSection>
  );
}