// RoutesConfigSection.jsx - Static routes configuration with API integration
import React from 'react';
import { Network, Plus, Route, Trash2 } from 'lucide-react';
import ConfigSection from '../../components/ConfigSection';
import { InputField } from '../../components/FormComponents';

export const RoutesConfigSection = ({ 
  local, 
  hostStatus, 
  sections, 
  dispatch, 
  onToggle 
}) => {
  const currentRoutes = hostStatus?.routing_table || [];

  const getRouteType = (route) => {
    if (route.destination === '0.0.0.0/0' || route.destination === 'default') {
      return { type: 'default', color: 'text-blue-600', icon: '🌐' };
    } else if (route.gateway) {
      return { type: 'static', color: 'text-green-600', icon: '🗺️' };
    } else {
      return { type: 'connected', color: 'text-gray-600', icon: '🔗' };
    }
  };

  const markRouteForDeletion = (route) => {
    // Check if already marked for deletion
    const isMarked = (local.routes_to_delete || []).some(r => 
      r.destination === route.destination && r.gateway === route.gateway
    );
    
    if (!isMarked) {
      dispatch({ 
        type: 'SET_FIELD', 
        field: 'routes_to_delete', 
        value: [...(local.routes_to_delete || []), {
          destination: route.destination,
          gateway: route.gateway || ''
        }]
      });
    }
  };

  const unmarkRouteForDeletion = (route) => {
    dispatch({ 
      type: 'SET_FIELD', 
      field: 'routes_to_delete', 
      value: (local.routes_to_delete || []).filter(r => 
        !(r.destination === route.destination && r.gateway === route.gateway)
      )
    });
  };

  const isRouteMarkedForDeletion = (route) => {
    return (local.routes_to_delete || []).some(r => 
      r.destination === route.destination && 
      (r.gateway === route.gateway || (!r.gateway && !route.gateway))
    );
  };

  return (
    <ConfigSection
      title="Static Routes"
      icon={Network}
      expanded={sections.routes}
      onToggle={() => onToggle('routes')}
    >
      {/* Current Routes Display */}
      {currentRoutes.length > 0 && (
        <div className="mb-6">
          <h4 className="font-medium text-gray-900 mb-3">Current Routing Table</h4>
          <div className="bg-gray-50 p-3 rounded border max-h-64 overflow-y-auto">
            {currentRoutes.map((route, idx) => {
              const routeInfo = getRouteType(route);
              const markedForDeletion = isRouteMarkedForDeletion(route);
              
              return (
                <div 
                  key={idx} 
                  className={`flex items-center gap-2 text-sm mb-1 p-2 rounded transition-all ${
                    markedForDeletion 
                      ? 'bg-red-50 border border-red-200' 
                      : 'hover:bg-white'
                  }`}
                >
                  <span className="text-lg">{routeInfo.icon}</span>
                  <div className="flex-1">
                    <div className="font-mono">
                      <span className={`font-medium ${markedForDeletion ? 'text-red-600 line-through' : ''}`}>
                        {route.destination}
                      </span>
                      {route.gateway && (
                        <>
                          <span className="text-gray-500"> via </span>
                          <span className={`text-blue-600 ${markedForDeletion ? 'line-through' : ''}`}>
                            {route.gateway}
                          </span>
                        </>
                      )}
                      {route.interface && (
                        <>
                          <span className="text-gray-500"> dev </span>
                          <span className={`text-green-600 ${markedForDeletion ? 'line-through' : ''}`}>
                            {route.interface}
                          </span>
                        </>
                      )}
                      {route.metric && (
                        <span className="text-gray-500"> metric {route.metric}</span>
                      )}
                    </div>
                    <div className={`text-xs ${routeInfo.color}`}>
                      {routeInfo.type.charAt(0).toUpperCase() + routeInfo.type.slice(1)} route
                      {markedForDeletion && (
                        <span className="ml-2 text-red-600 font-medium">
                          (Marked for deletion)
                        </span>
                      )}
                    </div>
                  </div>
                  {routeInfo.type !== 'connected' && (
                    <div>
                      {!markedForDeletion ? (
                        <button
                          onClick={() => markRouteForDeletion(route)}
                          className="p-1 text-red-600 hover:bg-red-100 rounded"
                          title="Mark for deletion"
                        >
                          <Trash2 size={14} />
                        </button>
                      ) : (
                        <button
                          onClick={() => unmarkRouteForDeletion(route)}
                          className="p-1 text-gray-600 hover:bg-gray-100 rounded"
                          title="Cancel deletion"
                        >
                          ↩️
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Routes to Delete Summary */}
      {local.routes_to_delete?.length > 0 && (
        <div className="mb-6 p-3 bg-red-50 rounded border border-red-200">
          <h5 className="font-medium text-red-900 mb-2">Routes Marked for Deletion</h5>
          <div className="space-y-1">
            {local.routes_to_delete.map((route, idx) => (
              <div key={idx} className="text-sm text-red-700 font-mono">
                {route.destination}
                {route.gateway && ` via ${route.gateway}`}
              </div>
            ))}
          </div>
          <div className="text-xs text-red-600 mt-2">
            These routes will be deleted when you apply the configuration.
          </div>
        </div>
      )}

      {/* Add New Routes */}
      <div className="mb-4">
        <h4 className="font-medium text-gray-900 mb-3">Add Static Routes</h4>
        
        {(local.routes_to_add || []).map((route, i) => (
          <div key={i} className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4 p-4 border rounded bg-white">
            <InputField
              label="Destination"
              value={route.destination || ''}
              onChange={(v) => dispatch({ type: 'ROUTE_SET', index: i, field: 'destination', value: v })}
              placeholder="192.168.2.0/24 or default"
              helper="Network destination (CIDR)"
            />
            <InputField
              label="Gateway"
              value={route.gateway || ''}
              onChange={(v) => dispatch({ type: 'ROUTE_SET', index: i, field: 'gateway', value: v })}
              placeholder="192.168.1.1"
              helper="Next hop IP (optional)"
            />
            <InputField
              label="Interface"
              value={route.interface || ''}
              onChange={(v) => dispatch({ type: 'ROUTE_SET', index: i, field: 'interface', value: v })}
              placeholder="eth0"
              helper="Output interface (optional)"
            />
            <InputField
              label="Metric"
              value={route.metric || ''}
              onChange={(v) => dispatch({ type: 'ROUTE_SET', index: i, field: 'metric', value: v })}
              placeholder="100"
              helper="Priority (lower = higher)"
            />
            <div className="flex flex-col justify-end">
              <button
                onClick={() => dispatch({ type: 'ROUTE_REMOVE', index: i })}
                className="p-2 text-red-600 hover:bg-red-50 rounded border"
                title="Remove route"
              >
                Remove
              </button>
            </div>
          </div>
        ))}

        <button
          onClick={() => dispatch({ type: 'ROUTE_ADD' })}
          className="flex items-center gap-2 text-sm text-blue-600 hover:underline mt-2"
        >
          <Plus size={16} /> Add Static Route
        </button>
      </div>

      {/* Common Route Examples */}
      <div className="mb-4">
        <h5 className="font-medium text-gray-900 mb-2">Common Route Examples</h5>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div className="p-3 bg-blue-50 rounded border border-blue-200">
            <div className="font-medium text-blue-900 text-sm">Default Route</div>
            <div className="text-xs text-blue-700 font-mono mt-1">
              Destination: default<br />
              Gateway: 192.168.1.1
            </div>
          </div>
          <div className="p-3 bg-green-50 rounded border border-green-200">
            <div className="font-medium text-green-900 text-sm">Network Route</div>
            <div className="text-xs text-green-700 font-mono mt-1">
              Destination: 10.0.0.0/8<br />
              Gateway: 192.168.1.254
            </div>
          </div>
          <div className="p-3 bg-purple-50 rounded border border-purple-200">
            <div className="font-medium text-purple-900 text-sm">Host Route</div>
            <div className="text-xs text-purple-700 font-mono mt-1">
              Destination: 8.8.8.8/32<br />
              Gateway: 192.168.1.1
            </div>
          </div>
          <div className="p-3 bg-orange-50 rounded border border-orange-200">
            <div className="font-medium text-orange-900 text-sm">Interface Route</div>
            <div className="text-xs text-orange-700 font-mono mt-1">
              Destination: 169.254.0.0/16<br />
              Interface: eth0 (no gateway)
            </div>
          </div>
        </div>
      </div>

      {/* Pending Changes Summary */}
      {(local.routes_to_add?.length > 0 || local.routes_to_delete?.length > 0) && (
        <div className="mb-4 p-3 bg-yellow-50 rounded border border-yellow-200">
          <h5 className="font-medium text-yellow-900 mb-2">Pending Route Changes</h5>
          {local.routes_to_add?.filter(r => r.destination).length > 0 && (
            <div className="text-sm text-yellow-800 mb-1">
              <span className="font-medium">Routes to Add:</span> {local.routes_to_add.filter(r => r.destination).length}
            </div>
          )}
          {local.routes_to_delete?.length > 0 && (
            <div className="text-sm text-yellow-800">
              <span className="font-medium">Routes to Delete:</span> {local.routes_to_delete.length}
            </div>
          )}
          <div className="text-xs text-yellow-700 mt-2">
            Click "Apply Configuration" to execute these changes
          </div>
        </div>
      )}

      {/* Help Text */}
      <div className="p-3 bg-gray-100 rounded text-sm text-gray-600">
        <strong>Static Route Configuration:</strong>
        <ul className="mt-2 space-y-1 text-xs">
          <li>• <strong>Destination:</strong> Network in CIDR format (e.g., 192.168.1.0/24) or "default"</li>
          <li>• <strong>Gateway:</strong> Next hop IP address (required for remote networks)</li>
          <li>• <strong>Interface:</strong> Outgoing interface (alternative to gateway for direct routes)</li>
          <li>• <strong>Metric:</strong> Route priority (lower numbers have higher priority)</li>
          <li>• Either gateway or interface must be specified for new routes</li>
          <li>• Default route (0.0.0.0/0) can be specified as "default"</li>
          <li>• Connected routes (automatically created) cannot be deleted</li>
        </ul>
      </div>
    </ConfigSection>
  );
};