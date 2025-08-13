import React from 'react';
import { FiActivity, FiRefreshCcw, FiGlobe } from 'react-icons/fi';
import ConfigSection from '../../components/ConfigSection';
import ActionButton from '../../components/ActionButton';

export function RouterStatusSection({ 
  status, 
  sections, 
  loading, 
  onToggle, 
  onRefreshStatus, 
  onTestConnectivity 
}) {
  return (
    <ConfigSection 
      title="Current Router Status" 
      icon={FiActivity} 
      expanded={sections.status} 
      onToggle={() => onToggle('status')}
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        <div>
          <label className="text-sm font-medium text-gray-600">IP Forwarding</label>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${status.ipForwarding ? 'bg-green-500' : 'bg-red-500'}`} />
            <p className={`font-semibold ${status.ipForwarding ? 'text-green-600' : 'text-red-600'}`}>
              {status.ipForwarding ? 'Enabled' : 'Disabled'}
            </p>
          </div>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">NAT Status</label>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${status.natEnabled ? 'bg-green-500' : 'bg-gray-400'}`} />
            <p className="font-semibold text-gray-900">{status.natEnabled ? 'Enabled' : 'Disabled'}</p>
          </div>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">Configured Interfaces</label>
          <p className="font-semibold text-gray-900">{status.interfaces.length} interfaces</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">Active Routes</label>
          <p className="font-semibold text-gray-900">{status.routes.length} routes</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">NAT Rules</label>
          <p className="font-semibold text-gray-900">{status.nat?.masquerade?.length || 0} rules</p>
        </div>
        <div>
          <label className="text-sm font-medium text-gray-600">Routing Protocol</label>
          <p className="font-semibold text-gray-900">{status.routingProtocol || 'Static'}</p>
        </div>
      </div>

      <div className="flex gap-2 mt-4">
        <ActionButton 
          onClick={onRefreshStatus} 
          loading={loading} 
          icon={<FiRefreshCcw size={16} />} 
          label="Refresh Status" 
          variant="secondary" 
          size="sm" 
        />
        <ActionButton 
          onClick={() => onTestConnectivity('8.8.8.8')} 
          loading={loading} 
          icon={<FiGlobe size={16} />} 
          label="Test Internet" 
          variant="secondary" 
          size="sm" 
        />
      </div>
    </ConfigSection>
  );
}