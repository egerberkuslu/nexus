import React from 'react';
import { FiGitBranch, FiPlus } from 'react-icons/fi';
import ConfigSection from '../../components/ConfigSection';
import { SelectField, InputField } from '../../components/FormComponents';

export function StaticRoutesSection({ 
  local, 
  status, 
  sections, 
  dispatch, 
  onToggle,
  onRouteStructuralChange
}) {
  const routeActionOptions = [
    { value: 'add', label: 'Add' }, 
    { value: 'del', label: 'Delete' }
  ];

  // Handle route field changes
  const handleRouteFieldChange = (index, field, value) => {
    console.log('Route field change:', { index, field, value });
    dispatch({ type: 'ROUTE_SET', index, field, value });
  };

  // Handle route removal with proper tracking
  const handleRouteRemove = (index) => {
    console.log('Removing route at index:', index);
    
    // Call structural change callback BEFORE dispatching the removal
    if (onRouteStructuralChange) {
      onRouteStructuralChange();
    }
    
    // Instead of immediately removing, mark for deletion if it exists on the router
    const routeToRemove = local.routes[index];
    if (routeToRemove && routeToRemove.destination) {
      // Check if this is an existing route that needs to be deleted on the router
      if (routeToRemove.id && !routeToRemove.id.includes('new-')) {
        // Mark existing route for deletion
        dispatch({ 
          type: 'ROUTE_SET', 
          index, 
          field: 'operation', 
          value: 'delete' 
        });
        console.log('Marked route for deletion:', routeToRemove.destination);
      } else {
        // Remove new route that hasn't been applied yet
        dispatch({ type: 'ROUTE_RM', index });
        console.log('Removed new route:', routeToRemove.destination);
      }
    }
  };

  // Handle route addition with proper tracking
  const handleRouteAdd = () => {
    console.log('Adding new route');
    
    // Call structural change callback BEFORE dispatching the addition
    if (onRouteStructuralChange) {
      onRouteStructuralChange();
    }
    
    dispatch({ type: 'ROUTE_ADD' });
  };

  // Filter out routes marked for deletion from display
  const visibleRoutes = (local.routes || []).filter(route => route.operation !== 'delete');

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
          <div className="bg-gray-50 p-2 rounded mt-2 max-h-32 overflow-y-auto">
            {status.routes.map((r, i) => (
              <div key={i} className="text-xs font-mono mb-1">
                {(r.destination || r.dest) || ''} → {(r.gateway || r.via) || 'direct'} {r.interface ? `(${r.interface})` : ''} {r.metric !== undefined ? `[${r.metric}]` : ''}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mb-4">
        <h4 className="font-medium text-gray-900 mb-3">Configure Static Routes</h4>
        
        {visibleRoutes.map((route, i) => {
          // Find original index in the full routes array
          const originalIndex = local.routes.findIndex(originalRoute => 
            originalRoute.id === route.id || 
            (originalRoute.destination === route.destination && originalRoute.operation !== 'delete')
          );
          
          return (
            <div key={route.id || i} className="grid grid-cols-1 md:grid-cols-7 gap-4 mb-4 p-4 border rounded bg-white">
              <SelectField 
                label="Action" 
                value={route.action || 'add'} 
                onChange={(v) => handleRouteFieldChange(originalIndex, 'action', v)} 
                options={routeActionOptions} 
              />
              <InputField 
                label="Destination" 
                value={route.destination || ''} 
                onChange={(v) => handleRouteFieldChange(originalIndex, 'destination', v)} 
                placeholder="192.168.0.0/24 or default" 
              />
              <InputField 
                label="Gateway" 
                value={route.gateway || ''} 
                onChange={(v) => handleRouteFieldChange(originalIndex, 'gateway', v)} 
                placeholder="192.168.0.1" 
              />
              <InputField 
                label="Interface" 
                value={route.interface || ''} 
                onChange={(v) => handleRouteFieldChange(originalIndex, 'interface', v)} 
                placeholder="eth0, eth1" 
              />
              <InputField 
                label="Metric" 
                value={route.metric || ''} 
                onChange={(v) => handleRouteFieldChange(originalIndex, 'metric', v)} 
                placeholder="100" 
                type="number"
                min="0"
                max="65535"
              />
              <div className="flex flex-col">
                <label className="text-sm font-medium text-gray-600 mb-1">Preview</label>
                <div className="p-2 bg-gray-50 rounded text-xs font-mono">
                  {route.destination ? (
                    `${route.destination} ${route.gateway ? `via ${route.gateway}` : ''} ${route.interface ? `dev ${route.interface}` : ''}`.trim()
                  ) : 'No destination configured'}
                </div>
              </div>
              <div className="flex flex-col">
                <label className="text-sm font-medium text-gray-600 mb-1">Actions</label>
                <button 
                  onClick={() => handleRouteRemove(originalIndex)} 
                  className="p-2 text-red-600 hover:bg-red-50 rounded border" 
                  title="Remove route"
                >
                  Remove
                </button>
              </div>
            </div>
          );
        })}
        
        <button 
          onClick={handleRouteAdd} 
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <FiPlus size={16} /> Add Route
        </button>
      </div>

      {/* Show pending deletions */}
      {local.routes?.some(route => route.operation === 'delete') && (
        <div className="mb-4 p-3 bg-red-50 rounded border border-red-200">
          <h5 className="font-medium text-red-800 mb-2">Pending Route Deletions</h5>
          <div className="space-y-1">
            {local.routes
              .filter(route => route.operation === 'delete')
              .map((route, i) => (
                <div key={i} className="text-sm text-red-700 font-mono">
                  • {route.destination} {route.gateway ? `via ${route.gateway}` : ''} {route.interface ? `dev ${route.interface}` : ''} will be deleted when configuration is applied
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Help Text */}
      <div className="mt-4 p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>Static Route Examples:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>Default Route:</strong> Destination: default, Gateway: 192.168.1.1</li>
          <li>• <strong>Network Route:</strong> Destination: 10.0.0.0/8, Gateway: 192.168.1.254</li>
          <li>• <strong>Host Route:</strong> Destination: 8.8.8.8/32, Interface: eth0</li>
          <li>• <strong>Interface Route:</strong> Destination: 192.168.100.0/24, Interface: eth1</li>
          <li>• <strong>Metric Example:</strong> Destination: 0.0.0.0/0, Gateway: 192.168.1.1, Metric: 100</li>
        </ul>
      </div>
    </ConfigSection>
  );
}