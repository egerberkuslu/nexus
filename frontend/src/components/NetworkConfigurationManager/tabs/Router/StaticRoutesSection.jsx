import React from 'react';
import { FiGitBranch, FiPlus } from 'react-icons/fi';
import ConfigSection from '../../components/ConfigSection';
import { SelectField, InputField } from '../../components/FormComponents';

export function StaticRoutesSection({ 
  local, 
  status, 
  sections, 
  dispatch, 
  onToggle 
}) {
  const routeActionOptions = [
    { value: 'add', label: 'Add' }, 
    { value: 'del', label: 'Delete' }
  ];

  const handleRouteFieldChange = (index, field, value) => {
    console.log('Route field change:', { index, field, value });
    dispatch({ type: 'ROUTE_SET', index, field, value });
  };

  const handleRouteAdd = () => {
    console.log('Adding new route');
    dispatch({ type: 'ROUTE_ADD' });
  };

  const handleRouteRemove = (index) => {
    console.log('Removing route at index:', index);
    dispatch({ type: 'ROUTE_RM', index });
  };

  return (
    <ConfigSection 
      title="Static Routes" 
      icon={FiGitBranch} 
      expanded={sections.staticRoutes} 
      onToggle={() => onToggle('staticRoutes')}
    >
      {status.routes?.length > 0 && (
        <div className="mb-4">
          <label className="text-sm font-medium text-gray-600">Current Routes (Read-only)</label>
          <div className="bg-gray-50 p-2 rounded mt-2">
            {status.routes.map((r, i) => (
              <div key={i} className="text-xs font-mono">
                {(r.destination || r.dest) || ''} → {(r.gateway || r.via) || 'direct'} {r.interface ? `(${r.interface})` : ''} {r.metric !== undefined ? `[${r.metric}]` : ''}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mb-4">
        <h4 className="font-medium text-gray-900 mb-3">Configure Static Routes</h4>
        
        {(local.routes || []).map((route, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-4 p-4 border rounded bg-white">
            <SelectField 
              label="Action" 
              value={route.action || 'add'} 
              onChange={(v) => handleRouteFieldChange(i, 'action', v)} 
              options={routeActionOptions} 
            />
            <InputField 
              label="Destination" 
              value={route.destination || ''} 
              onChange={(v) => handleRouteFieldChange(i, 'destination', v)} 
              placeholder="192.168.0.0/24 or default" 
            />
            <InputField 
              label="Gateway" 
              value={route.gateway || ''} 
              onChange={(v) => handleRouteFieldChange(i, 'gateway', v)} 
              placeholder="192.168.0.1" 
            />
            <InputField 
              label="Interface" 
              value={route.interface || ''} 
              onChange={(v) => handleRouteFieldChange(i, 'interface', v)} 
              placeholder="eth0, eth1" 
            />
            <InputField 
              label="Metric" 
              value={route.metric || ''} 
              onChange={(v) => handleRouteFieldChange(i, 'metric', v)} 
              placeholder="100" 
              type="number"
            />
            <div className="flex flex-col">
              <label className="text-sm font-medium text-gray-600 mb-1">Actions</label>
              <button 
                onClick={() => handleRouteRemove(i)} 
                className="p-2 text-red-600 hover:bg-red-50 rounded border" 
                title="Remove route"
              >
                Remove
              </button>
            </div>
          </div>
        ))}
        
        <button 
          onClick={handleRouteAdd} 
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <FiPlus size={16} /> Add Route
        </button>
      </div>

      {/* Help Text */}
      <div className="mt-4 p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>Static Route Examples:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>Default Route:</strong> Destination: default, Gateway: 192.168.1.1</li>
          <li>• <strong>Network Route:</strong> Destination: 10.0.0.0/8, Gateway: 192.168.1.254</li>
          <li>• <strong>Host Route:</strong> Destination: 8.8.8.8/32, Interface: eth0</li>
          <li>• <strong>Interface Route:</strong> Destination: 192.168.100.0/24, Interface: eth1</li>
        </ul>
      </div>
    </ConfigSection>
  );
}