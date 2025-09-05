// ConnectivityTestSection.jsx - Network connectivity testing tools
import React, { useState } from 'react';
import { Zap, Plus, Target, Globe, Router, Wifi, Activity } from 'lucide-react';
import ConfigSection from '../../components/ConfigSection';
import { InputField, SelectField } from '../../components/FormComponents';
import ActionButton from '../../components/ActionButton';

export const ConnectivityTestSection = ({ 
  selectedNode, 
  sections, 
  loading, 
  onToggle, 
  onTestConnectivity 
}) => {
  const [testTargets, setTestTargets] = useState([
    { target: '8.8.8.8', type: 'ping', label: 'Google DNS', icon: '🌐' },
    { target: '1.1.1.1', type: 'ping', label: 'Cloudflare DNS', icon: '☁️' },
    { target: 'www.google.com', type: 'ping', label: 'Google Website', icon: '🔍' }
  ]);
  const [customTarget, setCustomTarget] = useState('');
  const [customType, setCustomType] = useState('ping');
  const [customLabel, setCustomLabel] = useState('');

  const testTypes = [
    { value: 'ping', label: 'Ping (ICMP)' },
    { value: 'traceroute', label: 'Traceroute' },
    { value: 'telnet', label: 'Telnet (Port Check)' }
  ];

  const addCustomTest = () => {
    if (customTarget.trim()) {
      const newTest = {
        target: customTarget.trim(),
        type: customType,
        label: customLabel.trim() || `Custom ${customType}`,
        icon: '🎯',
        custom: true
      };
      setTestTargets(prev => [...prev, newTest]);
      setCustomTarget('');
      setCustomLabel('');
    }
  };

  const removeTest = (index) => {
    setTestTargets(prev => prev.filter((_, i) => i !== index));
  };

  const getTestTypeIcon = (type) => {
    switch (type) {
      case 'ping': return <Target size={16} className="text-green-600" />;
      case 'traceroute': return <Router size={16} className="text-blue-600" />;
      case 'telnet': return <Wifi size={16} className="text-purple-600" />;
      default: return <Activity size={16} className="text-gray-600" />;
    }
  };

  const getTestTypeDescription = (type) => {
    switch (type) {
      case 'ping': return 'Tests basic connectivity and measures round-trip time';
      case 'traceroute': return 'Shows the network path and hop-by-hop latency';
      case 'telnet': return 'Tests if a specific port is reachable';
      default: return 'Network connectivity test';
    }
  };

  const quickTests = [
    { target: 'localhost', type: 'ping', label: 'Localhost', icon: '🏠', description: 'Test local network stack' },
    { target: '127.0.0.1', type: 'ping', label: 'Loopback', icon: '🔄', description: 'Test loopback interface' }
  ];

  return (
    <ConfigSection
      title="Connectivity Testing"
      icon={Zap}
      expanded={sections.connectivity}
      onToggle={() => onToggle('connectivity')}
    >
      <div className="space-y-6">
        {/* Quick Tests */}
        <div>
          <h5 className="font-medium text-gray-900 mb-3">Quick Tests</h5>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {quickTests.map((test, index) => (
              <div key={index} className="p-3 border rounded bg-white hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{test.icon}</span>
                    <div>
                      <div className="font-medium text-gray-900">{test.label}</div>
                      <div className="text-xs text-gray-500">{test.description}</div>
                    </div>
                  </div>
                  <ActionButton
                    onClick={() => onTestConnectivity(test.target, test.type)}
                    loading={loading}
                    label="Test"
                    variant="secondary"
                    size="sm"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Configured Tests */}
        <div>
          <h5 className="font-medium text-gray-900 mb-3">Configured Tests</h5>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {testTargets.map((test, index) => (
              <div key={index} className="p-4 border rounded bg-white">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">{test.icon}</span>
                    <div>
                      <div className="font-medium text-gray-900">{test.label}</div>
                      <div className="text-sm text-gray-600 font-mono">{test.target}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    {getTestTypeIcon(test.type)}
                    <span className="text-xs text-gray-500 uppercase">{test.type}</span>
                  </div>
                </div>
                
                <div className="text-xs text-gray-600 mb-3">
                  {getTestTypeDescription(test.type)}
                </div>
                
                <div className="flex gap-2">
                  <div className="flex-1">
                    <ActionButton
                      onClick={() => onTestConnectivity(test.target, test.type)}
                      loading={loading}
                      label="Run Test"
                      variant="secondary"
                      size="sm"
                      className="w-full"
                    />
                  </div>
                  {test.custom && (
                    <button
                      onClick={() => removeTest(index)}
                      className="p-2 text-red-600 hover:bg-red-50 rounded border"
                      title="Remove test"
                    >
                      ×
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Add Custom Test */}
        <div className="p-4 bg-gray-50 rounded border">
          <h5 className="font-medium text-gray-900 mb-3">Add Custom Test</h5>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <InputField
              label="Target"
              value={customTarget}
              onChange={setCustomTarget}
              placeholder="Enter IP address or hostname"
              helper="Target to test (IP address, hostname, or URL)"
            />
            
            <SelectField
              label="Test Type"
              value={customType}
              onChange={setCustomType}
              options={testTypes}
              helper="Type of connectivity test"
            />
            
            <InputField
              label="Label (Optional)"
              value={customLabel}
              onChange={setCustomLabel}
              placeholder="My Custom Test"
              helper="Friendly name for this test"
            />
            
            <div className="flex items-end">
              <ActionButton
                onClick={addCustomTest}
                icon={<Plus size={16} />}
                label="Add Test"
                variant="secondary"
                disabled={!customTarget.trim()}
                className="w-full"
              />
            </div>
          </div>
        </div>

        {/* Network Diagnostic Tools */}
        <div className="p-4 bg-blue-50 rounded border border-blue-200">
          <h5 className="font-medium text-blue-900 mb-3">Network Diagnostic Information</h5>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Target size={14} className="text-green-600" />
                <span className="font-medium text-blue-800">Ping (ICMP)</span>
              </div>
              <ul className="text-xs text-blue-700 space-y-1">
                <li>• Tests basic connectivity</li>
                <li>• Measures round-trip time</li>
                <li>• Shows packet loss</li>
                <li>• Works at Layer 3 (IP)</li>
              </ul>
            </div>
            
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Router size={14} className="text-blue-600" />
                <span className="font-medium text-blue-800">Traceroute</span>
              </div>
              <ul className="text-xs text-blue-700 space-y-1">
                <li>• Shows network path</li>
                <li>• Hop-by-hop latency</li>
                <li>• Identifies routing issues</li>
                <li>• May be blocked by firewalls</li>
              </ul>
            </div>
            
            <div>
              <div className="flex items-center gap-2 mb-1">
                <Wifi size={14} className="text-purple-600" />
                <span className="font-medium text-blue-800">Telnet</span>
              </div>
              <ul className="text-xs text-blue-700 space-y-1">
                <li>• Tests port connectivity</li>
                <li>• Checks service availability</li>
                <li>• Works at Layer 4 (TCP)</li>
                <li>• Common ports: 80, 443, 22</li>
              </ul>
            </div>
          </div>
        </div>

        {/* Common Targets */}
        <div className="p-3 bg-gray-100 rounded text-sm text-gray-600">
          <strong>Common Test Targets:</strong>
          <div className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
            <div>
              <span className="font-medium">DNS Servers:</span>
              <ul className="ml-2 space-y-1">
                <li>• 8.8.8.8 (Google)</li>
                <li>• 1.1.1.1 (Cloudflare)</li>
                <li>• 9.9.9.9 (Quad9)</li>
              </ul>
            </div>
            <div>
              <span className="font-medium">Web Services:</span>
              <ul className="ml-2 space-y-1">
                <li>• www.google.com</li>
                <li>• www.cloudflare.com</li>
                <li>• httpbin.org</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </ConfigSection>
  );
};