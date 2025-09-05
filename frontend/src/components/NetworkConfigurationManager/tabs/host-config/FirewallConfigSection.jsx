// FirewallConfigSection.jsx - Firewall rules management
import React from 'react';
import { Shield, Plus, Lock, AlertTriangle } from 'lucide-react';
import ConfigSection from '../../components/ConfigSection';
import { InputField, SelectField } from '../../components/FormComponents';

export const FirewallConfigSection = ({ 
  local, 
  hostStatus, 
  sections, 
  dispatch, 
  onToggle 
}) => {
  const firewallStatus = hostStatus?.firewall_status || {};

  const chainOptions = [
    { value: 'INPUT', label: 'INPUT (Incoming traffic)' },
    { value: 'OUTPUT', label: 'OUTPUT (Outgoing traffic)' },
    { value: 'FORWARD', label: 'FORWARD (Forwarded traffic)' }
  ];

  const targetOptions = [
    { value: 'ACCEPT', label: 'ACCEPT (Allow)' },
    { value: 'DROP', label: 'DROP (Silently deny)' },
    { value: 'REJECT', label: 'REJECT (Deny with response)' }
  ];

  const protocolOptions = [
    { value: '', label: 'Any protocol' },
    { value: 'tcp', label: 'TCP' },
    { value: 'udp', label: 'UDP' },
    { value: 'icmp', label: 'ICMP' }
  ];

  const getFirewallStatusColor = () => {
    if (!firewallStatus.iptables_available) return 'text-gray-500';
    if (firewallStatus.rule_count > 0) return 'text-green-600';
    return 'text-yellow-600';
  };

  const getFirewallStatusText = () => {
    if (!firewallStatus.iptables_available) return 'Not Available';
    if (firewallStatus.rule_count > 0) return 'Active';
    return 'Inactive';
  };

  return (
    <ConfigSection
      title="Firewall Configuration"
      icon={Shield}
      expanded={sections.firewall}
      onToggle={() => onToggle('firewall')}
    >
      {/* Current Firewall Status */}
      <div className="mb-6">
        <h4 className="font-medium text-gray-900 mb-3">Current Firewall Status</h4>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
          <div className="flex items-center gap-2">
            <Shield size={16} className={getFirewallStatusColor()} />
            <div>
              <label className="text-sm font-medium text-gray-600">Status</label>
              <p className={`font-semibold ${getFirewallStatusColor()}`}>
                {getFirewallStatusText()}
              </p>
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Active Rules</label>
            <p className="font-semibold text-gray-900">{firewallStatus.rule_count || 0}</p>
          </div>
          <div>
            <label className="text-sm font-medium text-gray-600">Default Policy</label>
            <div className="flex gap-2">
              <span className="text-xs bg-gray-100 px-2 py-1 rounded">
                INPUT: {firewallStatus.policy?.INPUT || 'ACCEPT'}
              </span>
            </div>
          </div>
        </div>

        {/* Current Rules Display */}
        {firewallStatus.active_rules?.length > 0 && (
          <div className="bg-gray-50 p-3 rounded border max-h-32 overflow-y-auto">
            <div className="text-xs font-medium text-gray-600 mb-2">Active Firewall Rules:</div>
            {firewallStatus.active_rules.slice(0, 10).map((rule, idx) => (
              <div key={idx} className="text-xs font-mono text-gray-700 mb-1 p-1 hover:bg-white rounded">
                <span className="text-blue-600">{rule.chain}</span>
                <span className="mx-2">→</span>
                <span className="text-green-600">{rule.target}</span>
                {rule.protocol && (
                  <span className="text-purple-600 ml-2">{rule.protocol}</span>
                )}
                {rule.source && rule.source !== '0.0.0.0/0' && (
                  <span className="text-orange-600 ml-2">from {rule.source}</span>
                )}
              </div>
            ))}
            {firewallStatus.active_rules.length > 10 && (
              <div className="text-xs text-gray-500">
                ... and {firewallStatus.active_rules.length - 10} more rules
              </div>
            )}
          </div>
        )}
      </div>

      {/* Firewall Rules Configuration */}
      <div className="mb-4">
        <h4 className="font-medium text-gray-900 mb-3">Firewall Rules Configuration</h4>
        
        {(local.firewall_rules || []).map((rule, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-4 p-4 border rounded bg-white">
            <SelectField
              label="Chain"
              value={rule.chain || 'INPUT'}
              onChange={(v) => dispatch({ type: 'FIREWALL_SET', index: i, field: 'chain', value: v })}
              options={chainOptions}
              size="sm"
            />
            
            <SelectField
              label="Protocol"
              value={rule.protocol || ''}
              onChange={(v) => dispatch({ type: 'FIREWALL_SET', index: i, field: 'protocol', value: v })}
              options={protocolOptions}
              size="sm"
            />
            
            <InputField
              label="Source"
              value={rule.source || ''}
              onChange={(v) => dispatch({ type: 'FIREWALL_SET', index: i, field: 'source', value: v })}
              placeholder="0.0.0.0/0"
              helper="Source IP/network"
              size="sm"
            />
            
            <InputField
              label="Port"
              value={rule.port || ''}
              onChange={(v) => dispatch({ type: 'FIREWALL_SET', index: i, field: 'port', value: v })}
              placeholder="22, 80, 443"
              helper="Port number(s)"
              size="sm"
            />
            
            <SelectField
              label="Action"
              value={rule.target || 'ACCEPT'}
              onChange={(v) => dispatch({ type: 'FIREWALL_SET', index: i, field: 'target', value: v })}
              options={targetOptions}
              size="sm"
            />
            
            <div className="flex flex-col justify-end">
              <button
                onClick={() => dispatch({ type: 'FIREWALL_REMOVE', index: i })}
                className="p-2 text-red-600 hover:bg-red-50 rounded border text-sm"
                title="Remove firewall rule"
              >
                Remove
              </button>
            </div>
          </div>
        ))}

        <button
          onClick={() => dispatch({ type: 'FIREWALL_ADD' })}
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <Plus size={16} /> Add Firewall Rule
        </button>
      </div>

      {/* Common Firewall Rules Templates */}
      <div className="mb-4">
        <h5 className="font-medium text-gray-900 mb-2">Common Firewall Rules</h5>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="p-3 bg-green-50 rounded border border-green-200">
            <div className="flex items-center gap-2 mb-1">
              <Lock size={14} className="text-green-600" />
              <span className="font-medium text-green-900 text-sm">Allow SSH</span>
            </div>
            <div className="text-xs text-green-700 font-mono">
              Chain: INPUT, Protocol: tcp, Port: 22, Action: ACCEPT
            </div>
          </div>
          
          <div className="p-3 bg-blue-50 rounded border border-blue-200">
            <div className="flex items-center gap-2 mb-1">
              <Shield size={14} className="text-blue-600" />
              <span className="font-medium text-blue-900 text-sm">Allow HTTP/HTTPS</span>
            </div>
            <div className="text-xs text-blue-700 font-mono">
              Chain: INPUT, Protocol: tcp, Port: 80,443, Action: ACCEPT
            </div>
          </div>
          
          <div className="p-3 bg-red-50 rounded border border-red-200">
            <div className="flex items-center gap-2 mb-1">
              <AlertTriangle size={14} className="text-red-600" />
              <span className="font-medium text-red-900 text-sm">Block IP Range</span>
            </div>
            <div className="text-xs text-red-700 font-mono">
              Chain: INPUT, Source: 192.168.1.0/24, Action: DROP
            </div>
          </div>
          
          <div className="p-3 bg-purple-50 rounded border border-purple-200">
            <div className="flex items-center gap-2 mb-1">
              <Shield size={14} className="text-purple-600" />
              <span className="font-medium text-purple-900 text-sm">Allow Ping</span>
            </div>
            <div className="text-xs text-purple-700 font-mono">
              Chain: INPUT, Protocol: icmp, Action: ACCEPT
            </div>
          </div>
        </div>
      </div>

      {/* Security Warning */}
      {(!firewallStatus.iptables_available || firewallStatus.rule_count === 0) && (
        <div className="mb-4 p-3 bg-yellow-50 rounded border border-yellow-200">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={16} className="text-yellow-600" />
            <span className="font-medium text-yellow-900">Security Notice</span>
          </div>
          <p className="text-sm text-yellow-800">
            {!firewallStatus.iptables_available 
              ? "Firewall (iptables) is not available on this system."
              : "No firewall rules are currently active. All traffic is allowed."
            }
          </p>
        </div>
      )}

      {/* Help Text */}
      <div className="p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>Firewall Rule Configuration:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>INPUT:</strong> Controls incoming traffic to this host</li>
          <li>• <strong>OUTPUT:</strong> Controls outgoing traffic from this host</li>
          <li>• <strong>FORWARD:</strong> Controls traffic passing through this host</li>
          <li>• <strong>Source:</strong> Use CIDR notation (e.g., 192.168.1.0/24) or leave empty for any</li>
          <li>• <strong>Port:</strong> Single port (22) or range (1024:65535) or list (80,443)</li>
          <li>• <strong>ACCEPT:</strong> Allow traffic, <strong>DROP:</strong> Silently deny, <strong>REJECT:</strong> Deny with response</li>
          <li>• Rules are processed in order; first match wins</li>
        </ul>
      </div>
    </ConfigSection>
  );
};