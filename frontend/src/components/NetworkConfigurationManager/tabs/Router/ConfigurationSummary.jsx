import React from 'react';

export function ConfigurationSummary({ local, status }) {
  // Get protocol-specific details
  const getProtocolDetails = () => {
    const protocol = local.protocol || 'static';
    switch (protocol) {
      case 'bgp':
        return `BGP (AS: ${local.bgpConfig?.as_number || '65001'})`;
      case 'ospf':
        return `OSPF (Area: ${local.ospfConfig?.area_id || '0'})`;
      case 'rip':
        return `RIP v${local.ripConfig?.version || '2'}`;
      case 'static':
      default:
        return 'Static Routing';
    }
  };

  const protocolChanged = status.routingProtocol !== local.protocol;

  return (
    <div className="bg-gray-50 rounded-lg p-4">
      <h4 className="font-medium text-gray-900 mb-2">Router Configuration Summary</h4>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
        <div>
          <span className="text-gray-700">IP Forwarding:</span>
          <span className="ml-2 font-mono">{local.ipForwarding ? 'Enabled' : 'Disabled'}</span>
        </div>
        <div>
          <span className="text-gray-700">Routing Protocol:</span>
          <span className="ml-2 font-mono">{getProtocolDetails()}</span>
          {protocolChanged && (
            <span className="ml-2 text-xs text-orange-600">(Changed from {status.routingProtocol})</span>
          )}
        </div>
        <div>
          <span className="text-gray-700">Interfaces:</span>
          <span className="ml-2 font-mono">
            {(local.interfaces || []).filter(i => i.operation !== 'delete').length} configured
          </span>
          {(local.interfaces || []).some(i => i.operation === 'delete') && (
            <span className="ml-2 text-xs text-red-600">
              ({(local.interfaces || []).filter(i => i.operation === 'delete').length} pending deletion)
            </span>
          )}
        </div>
        <div>
          <span className="text-gray-700">Static Routes:</span>
          <span className="ml-2 font-mono">{(local.routes || []).filter(r => r.operation !== 'delete').length} routes</span>
        </div>
        <div>
          <span className="text-gray-700">Basic NAT:</span>
          <span className="ml-2 font-mono">{local.natEnabled ? 'Enabled' : 'Disabled'}</span>
        </div>
        <div>
          <span className="text-gray-700">NAT Rules:</span>
          <span className="ml-2 font-mono">{(local.natRules || []).filter(r => r.operation !== 'delete').length} rules</span>
        </div>
        <div>
          <span className="text-gray-700">Firewall Rules:</span>
          <span className="ml-2 font-mono">{(local.firewallRules || []).filter(r => r.operation !== 'delete').length} rules</span>
        </div>
        <div>
          <span className="text-gray-700">Legacy FW Rules:</span>
          <span className="ml-2 font-mono">{(local.legacyFirewallRules || []).length} rules</span>
        </div>
      </div>
      
      {/* Protocol Configuration Details */}
      {local.protocol !== 'static' && (
        <div className="mt-4 p-3 bg-blue-50 rounded border border-blue-200">
          <h5 className="font-medium text-blue-900 mb-2">Protocol Configuration</h5>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm">
            {local.protocol === 'bgp' && (
              <>
                <div>
                  <span className="text-blue-700">AS Number:</span>
                  <span className="ml-2 font-mono">{local.bgpConfig?.as_number || '65001'}</span>
                </div>
                {local.bgpConfig?.router_id && (
                  <div>
                    <span className="text-blue-700">Router ID:</span>
                    <span className="ml-2 font-mono">{local.bgpConfig.router_id}</span>
                  </div>
                )}
              </>
            )}
            {local.protocol === 'ospf' && (
              <>
                <div>
                  <span className="text-blue-700">Area ID:</span>
                  <span className="ml-2 font-mono">{local.ospfConfig?.area_id || '0'}</span>
                </div>
                {local.ospfConfig?.router_id && (
                  <div>
                    <span className="text-blue-700">Router ID:</span>
                    <span className="ml-2 font-mono">{local.ospfConfig.router_id}</span>
                  </div>
                )}
              </>
            )}
            {local.protocol === 'rip' && (
              <div>
                <span className="text-blue-700">Version:</span>
                <span className="ml-2 font-mono">v{local.ripConfig?.version || '2'}</span>
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* Debug Information */}
      <div className="mt-4 p-2 bg-gray-100 rounded text-xs">
        <strong>Debug Info:</strong>
        <div>Interfaces: {JSON.stringify(local.interfaces?.map(i => ({name: i.name, ip: i.ip, op: i.operation})) || [])}</div>
        <div>Routes: {JSON.stringify(local.routes?.map(r => ({dest: r.destination, gw: r.gateway, op: r.operation})) || [])}</div>
        <div>Protocol: {local.protocol} {protocolChanged ? `(was: ${status.routingProtocol})` : ''}</div>
      </div>
      
      {!status.ipForwarding && (
        <div className="mt-2 p-2 bg-yellow-100 rounded text-yellow-800 text-sm">
          ⚠️ IP forwarding is disabled. Enable it to allow routing between networks.
        </div>
      )}
      
      {/* Protocol-specific warnings */}
      {local.protocol !== 'static' && (
        <div className="mt-2 p-2 bg-blue-100 rounded text-blue-800 text-sm">
          ℹ️ Dynamic routing protocol ({local.protocol.toUpperCase()}) is configured. 
          Note that routing daemons may not be available in basic Mininet environments.
        </div>
      )}
      
      {/* Additional helpful warnings */}
      {local.natEnabled && (local.natRules || []).length > 0 && (
        <div className="mt-2 p-2 bg-blue-100 rounded text-blue-800 text-sm">
          ℹ️ Both basic NAT and advanced NAT rules are configured. Consider using one approach for clarity.
        </div>
      )}
      
      {(local.firewallRules || []).length > 0 && (local.legacyFirewallRules || []).length > 0 && (
        <div className="mt-2 p-2 bg-blue-100 rounded text-blue-800 text-sm">
          ℹ️ Both structured and legacy firewall rules are configured. Structured rules are applied first.
        </div>
      )}

      {/* Pending changes warning */}
      {(protocolChanged || 
        (local.interfaces || []).some(i => i.operation === 'delete') || 
        (local.routes || []).some(r => r.operation === 'delete')) && (
        <div className="mt-2 p-2 bg-orange-100 rounded text-orange-800 text-sm">
          ⚠️ You have pending configuration changes. Click "Apply Configuration" to apply them to the router.
        </div>
      )}
    </div>
  );
}