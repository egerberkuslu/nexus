// protocolTestUtils.js - Helper functions for testing routing protocol changes

/**
 * Test if routing protocol changes are working properly
 */
export const testProtocolChange = async (apiCall, routerId, fromProtocol, toProtocol) => {
  console.log(`Testing protocol change from ${fromProtocol} to ${toProtocol} on ${routerId}`);
  
  try {
    // 1. Get current router snapshot
    const snapshot = await apiCall(`/device-management/devices/${routerId}/snapshot?detail=full`);
    const currentProtocol = snapshot?.device?.summary?.routing_protocol || 'static';
    
    console.log('Current protocol:', currentProtocol);
    
    // 2. Build configuration spec for protocol change
    const spec = {
      validate_only: false,
      routers: {
        [routerId]: {
          routing_protocol: {
            protocol: toProtocol,
            action: 'enable',
            config: getDefaultProtocolConfig(toProtocol)
          }
        }
      }
    };
    
    // 3. Apply the configuration
    const applyResult = await apiCall('/device-management/apply-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(spec)
    });
    
    console.log('Apply result:', applyResult);
    
    // 4. Wait a moment for changes to take effect
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // 5. Verify the change by checking processes
    const verifyResult = await apiCall(`/network/hosts/${routerId}/cmd`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: 'ps aux | grep -E "(ripd|ospfd|bgpd)" | grep -v grep' })
    });
    
    console.log('Verification result:', verifyResult);
    
    return {
      success: applyResult?.success || false,
      fromProtocol,
      toProtocol,
      processCheck: verifyResult?.result || verifyResult?.stdout || '',
      details: applyResult
    };
    
  } catch (error) {
    console.error('Protocol test error:', error);
    return {
      success: false,
      error: error.message,
      fromProtocol,
      toProtocol
    };
  }
};

/**
 * Get default configuration for each protocol type
 */
export const getDefaultProtocolConfig = (protocol) => {
  switch (protocol.toLowerCase()) {
    case 'bgp':
      return { as_number: '65001', router_id: '' };
    case 'ospf':
      return { area_id: '0', router_id: '' };
    case 'rip':
      return { version: '2' };
    case 'static':
    default:
      return {};
  }
};

/**
 * Check if routing daemons are available on the system
 */
export const checkRoutingDaemonAvailability = async (apiCall, routerId) => {
  const daemons = ['ripd', 'ospfd', 'bgpd', 'zebra'];
  const results = {};
  
  for (const daemon of daemons) {
    try {
      const result = await apiCall(`/network/hosts/${routerId}/cmd`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: `which ${daemon}` })
      });
      
      results[daemon] = {
        available: !!(result?.result || result?.stdout || '').trim(),
        path: (result?.result || result?.stdout || '').trim()
      };
    } catch (error) {
      results[daemon] = {
        available: false,
        error: error.message
      };
    }
  }
  
  return results;
};

/**
 * Get current routing protocol status
 */
export const getCurrentProtocolStatus = async (apiCall, routerId) => {
  try {
    // Check running processes
    const processResult = await apiCall(`/network/hosts/${routerId}/cmd`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: 'ps aux | grep -E "(ripd|ospfd|bgpd)" | grep -v grep' })
    });
    
    const processes = (processResult?.result || processResult?.stdout || '').trim();
    
    // Check routing table
    const routeResult = await apiCall(`/network/hosts/${routerId}/cmd`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command: 'ip route show' })
    });
    
    const routes = (routeResult?.result || routeResult?.stdout || '').trim();
    
    // Determine active protocol
    let activeProtocol = 'static';
    if (processes.includes('ripd')) activeProtocol = 'rip';
    else if (processes.includes('ospfd')) activeProtocol = 'ospf';
    else if (processes.includes('bgpd')) activeProtocol = 'bgp';
    
    return {
      activeProtocol,
      runningProcesses: processes.split('\n').filter(line => line.trim()),
      routingTable: routes.split('\n').filter(line => line.trim()),
      timestamp: new Date().toISOString()
    };
    
  } catch (error) {
    return {
      error: error.message,
      activeProtocol: 'unknown'
    };
  }
};

/**
 * Comprehensive protocol functionality test
 */
export const runProtocolDiagnostics = async (apiCall, routerId) => {
  console.log('Running comprehensive protocol diagnostics...');
  
  const diagnostics = {
    routerId,
    timestamp: new Date().toISOString(),
    daemonAvailability: await checkRoutingDaemonAvailability(apiCall, routerId),
    currentStatus: await getCurrentProtocolStatus(apiCall, routerId),
    testResults: {}
  };
  
  // Test each protocol if daemons are available
  const protocols = ['static', 'rip', 'ospf', 'bgp'];
  
  for (const protocol of protocols) {
    if (protocol === 'static' || diagnostics.daemonAvailability[`${protocol}d`]?.available) {
      console.log(`Testing ${protocol} protocol...`);
      diagnostics.testResults[protocol] = await testProtocolChange(
        apiCall, 
        routerId, 
        diagnostics.currentStatus.activeProtocol, 
        protocol
      );
      
      // Wait between tests
      await new Promise(resolve => setTimeout(resolve, 3000));
    } else {
      diagnostics.testResults[protocol] = {
        skipped: true,
        reason: `${protocol}d daemon not available`
      };
    }
  }
  
  return diagnostics;
};