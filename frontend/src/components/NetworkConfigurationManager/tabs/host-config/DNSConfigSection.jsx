// DNSConfigSection.jsx - DNS server configuration
import React from 'react';
import { Globe, Plus } from 'lucide-react';
import ConfigSection from '../../components/ConfigSection';
import { InputField } from '../../components/FormComponents';

export const DNSConfigSection = ({ 
  local, 
  hostStatus, 
  sections, 
  dispatch, 
  onToggle 
}) => {
  const currentDNS = hostStatus?.dns_config?.nameservers || [];
  const currentSearchDomains = hostStatus?.dns_config?.search_domains || [];

  return (
    <ConfigSection
      title="DNS Configuration"
      icon={Globe}
      expanded={sections.dns}
      onToggle={() => onToggle('dns')}
    >
      {/* Current DNS Status */}
      {(currentDNS.length > 0 || currentSearchDomains.length > 0) && (
        <div className="mb-4 p-3 bg-blue-50 rounded border border-blue-200">
          <p className="text-sm text-blue-800">
            <strong>Current DNS Configuration:</strong>
          </p>
          {currentDNS.length > 0 && (
            <p className="text-sm text-blue-700">
              Nameservers: {currentDNS.join(', ')}
            </p>
          )}
          {currentSearchDomains.length > 0 && (
            <p className="text-sm text-blue-700">
              Search Domains: {currentSearchDomains.join(', ')}
            </p>
          )}
        </div>
      )}

      {/* DNS Servers Configuration */}
      <div className="mb-6">
        <h4 className="font-medium text-gray-900 mb-3">DNS Servers</h4>
        
        {(local.dns_servers || []).map((dns, i) => (
          <div key={i} className="flex gap-4 mb-2">
            <div className="flex-1">
              <InputField
                value={dns}
                onChange={(v) => dispatch({ type: 'DNS_SET', index: i, value: v })}
                placeholder="8.8.8.8"
                helper={i === 0 ? "Primary DNS server" : i === 1 ? "Secondary DNS server" : "Additional DNS server"}
              />
            </div>
            <button
              onClick={() => dispatch({ type: 'DNS_REMOVE', index: i })}
              className="p-2 text-red-600 hover:bg-red-50 rounded"
              title="Remove DNS server"
            >
              ×
            </button>
          </div>
        ))}

        <button
          onClick={() => dispatch({ type: 'DNS_ADD' })}
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <Plus size={16} /> Add DNS Server
        </button>
      </div>

      {/* Search Domains Configuration */}
      <div className="mb-4">
        <h4 className="font-medium text-gray-900 mb-3">Search Domains</h4>
        <p className="text-sm text-gray-600 mb-3">
          Domains to search when resolving unqualified hostnames
        </p>
        
        {(local.search_domains || []).map((domain, i) => (
          <div key={i} className="flex gap-4 mb-2">
            <div className="flex-1">
              <InputField
                value={domain}
                onChange={(v) => dispatch({ type: 'SEARCH_DOMAIN_SET', index: i, value: v })}
                placeholder="example.com"
                helper="Domain to append to unqualified hostnames"
              />
            </div>
            <button
              onClick={() => dispatch({ type: 'SEARCH_DOMAIN_REMOVE', index: i })}
              className="p-2 text-red-600 hover:bg-red-50 rounded"
              title="Remove search domain"
            >
              ×
            </button>
          </div>
        ))}

        <button
          onClick={() => dispatch({ type: 'SEARCH_DOMAIN_ADD' })}
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <Plus size={16} /> Add Search Domain
        </button>
      </div>

      {/* Common DNS Servers */}
      <div className="p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>Common DNS Servers:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>Google:</strong> 8.8.8.8, 8.8.4.4</li>
          <li>• <strong>Cloudflare:</strong> 1.1.1.1, 1.0.0.1</li>
          <li>• <strong>OpenDNS:</strong> 208.67.222.222, 208.67.220.220</li>
          <li>• <strong>Quad9:</strong> 9.9.9.9, 149.112.112.112</li>
        </ul>
      </div>
    </ConfigSection>
  );
};