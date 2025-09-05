// HostConfigTab.jsx - Main orchestrator component with API-compliant calls
import React, { useState, useEffect, useReducer } from 'react';
import { Monitor } from 'lucide-react';
import { EmptyState } from '../../components/FormComponents';
import { HostConfigHeader } from './HostConfigHeader';
import { HostStatusSection } from './HostStatusSection';
import { InterfaceConfigSection } from './InterfaceConfigSection';
import { DNSConfigSection } from './DNSConfigSection';
import { ServicesConfigSection } from './ServicesConfigSection';
import { RoutesConfigSection } from './RoutesConfigSection';
import { FirewallConfigSection } from './FirewallConfigSection';
import { DHCPConfigSection } from './DHCPConfigSection';
import { SystemConfigSection } from './SystemConfigSection';
import { ConnectivityTestSection } from './ConnectivityTestSection';
import { 
  initialHostConfig, 
  hostConfigReducer, 
  buildAPICallsFromConfig,
  validateHostConfig,
  executeAPICall,
  hostConfigUtils
} from './hostConfigUtils';

export const HostConfigTab = ({ 
  selectedNode, 
  config, 
  updateConfig, 
  loading, 
  setLoading, 
  showMessage, 
  apiCall, 
  onNetworkChange 
}) => {
  const [sections, setSections] = useState({
    status: true,
    interfaces: false,
    dns: false,
    services: false,
    routes: false,
    firewall: false,
    dhcp: false,
    system: false,
    connectivity: false
  });

  const [hostStatus, setHostStatus] = useState(null);
  const [local, dispatch] = useReducer(hostConfigReducer, initialHostConfig);
  const [applyProgress, setApplyProgress] = useState(null);

  const toggleSection = (section) => {
    setSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Fetch host status on mount and every 10 seconds
  useEffect(() => {
    if (selectedNode?.type === 'host') {
      fetchHostStatus();
      const interval = setInterval(fetchHostStatus, 10000);
      return () => clearInterval(interval);
    }
  }, [selectedNode]);

  // Initialize local config when node changes or status updates
  useEffect(() => {
    if (selectedNode?.type === 'host' && hostStatus) {
      // Parse current status to set initial values
      const currentServices = hostStatus.network_services || {};
      const runningServices = Object.entries(currentServices)
        .filter(([, service]) => service.running)
        .map(([name]) => name);

      dispatch({
        type: 'SET_ALL',
        payload: {
          ...config,
          system_hostname: hostStatus.hostname || selectedNode.id,
          dns_servers: hostStatus.dns_config?.nameservers || ['8.8.8.8', '8.8.4.4'],
          search_domains: hostStatus.dns_config?.search_domains || [],
          services_to_start: runningServices,
          services_to_stop: [],
          interfaces: [],
          routes_to_add: [],
          routes_to_delete: [],
          firewall_rules: [],
          test_targets: []
        }
      });
    }
  }, [selectedNode, hostStatus]);

  const fetchHostStatus = async () => {
    if (!selectedNode?.id) return;
    
    try {
      const response = await apiCall(`/host-management/devices/${selectedNode.id}/host/status`);
      if (response?.success) {
        setHostStatus(response.data);
      }
    } catch (error) {
      console.error('Error fetching host status:', error);
    }
  };

  const applyConfiguration = async () => {
    if (!selectedNode) return;
    
    // Validate configuration
    const errors = validateHostConfig(local);
    if (errors.length > 0) {
      showMessage(`Configuration errors: ${errors.join(', ')}`, 'error');
      return;
    }

    setLoading(true);
    setApplyProgress({ current: 0, total: 0, message: 'Preparing configuration...' });
    
    try {
      // Build API calls from configuration
      const apiCalls = buildAPICallsFromConfig(local, selectedNode);
      
      if (apiCalls.length === 0) {
        showMessage('No configuration changes to apply', 'info');
        setLoading(false);
        setApplyProgress(null);
        return;
      }

      setApplyProgress({ 
        current: 0, 
        total: apiCalls.length, 
        message: `Applying ${apiCalls.length} configuration(s)...` 
      });

      // Execute API calls sequentially with progress updates
      const results = [];
      for (let i = 0; i < apiCalls.length; i++) {
        const call = apiCalls[i];
        
        setApplyProgress({
          current: i,
          total: apiCalls.length,
          message: call.description
        });
        
        const result = await executeAPICall(call, apiCall);
        results.push(result);
        
        // Small delay between calls to avoid overwhelming the API
        if (i < apiCalls.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 100));
        }
      }

      // Count successful and failed operations
      const successful = results.filter(r => r.success).length;
      const failed = results.filter(r => !r.success).length;

      if (failed === 0) {
        showMessage(`All ${successful} configurations applied successfully`, 'success');
      } else if (successful > 0) {
        showMessage(`Applied ${successful}/${results.length} configurations (${failed} failed)`, 'warning');
        
        // Show details of failures
        const failures = results.filter(r => !r.success);
        failures.forEach(failure => {
          console.error(`Failed: ${failure.description}`, failure.error);
        });
      } else {
        showMessage('Failed to apply configuration', 'error');
      }

      // Refresh status after applying changes
      setTimeout(() => {
        fetchHostStatus();
        onNetworkChange?.();
      }, 2000);

    } catch (error) {
      showMessage(`Configuration error: ${error.message}`, 'error');
      console.error('Configuration error:', error);
    } finally {
      setLoading(false);
      setApplyProgress(null);
    }
  };

  const testConnectivity = async (target, type = 'ping', port = null) => {
    if (!selectedNode || !target) return;
    
    setLoading(true);
    try {
      const body = {
        targets: [target],
        type: type,
        timeout: 5
      };
      
      if (type === 'telnet' && port) {
        body.port = port;
      }
      
      const response = await apiCall(`/host-management/devices/${selectedNode.id}/host/test-connectivity`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (response?.success && response.connectivity_tests?.length > 0) {
        const test = response.connectivity_tests[0];
        if (test.success) {
          const latency = test.latency_ms ? ` (${test.latency_ms}ms)` : '';
          showMessage(`✓ ${type} to ${target}: Success${latency}`, 'success');
        } else {
          showMessage(`✗ ${type} to ${target}: Failed`, 'error');
        }
      } else {
        showMessage(`${type} test failed: No response`, 'error');
      }
    } catch (error) {
      showMessage(`${type} test error: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const manageService = async (serviceName, action) => {
    if (!selectedNode || !serviceName) return;
    
    setLoading(true);
    try {
      const body = { action };
      
      // Add custom port if configured and starting
      if (action === 'start' && local.service_configs?.[serviceName]?.port) {
        body.port = parseInt(local.service_configs[serviceName].port);
      }
      
      const response = await apiCall(`/host-management/devices/${selectedNode.id}/host/services/${serviceName}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      if (response?.success) {
        showMessage(`Service ${serviceName} ${action}ed successfully`, 'success');
        // Refresh status to show updated service state
        setTimeout(fetchHostStatus, 1000);
      } else {
        showMessage(`Failed to ${action} ${serviceName}`, 'error');
      }
    } catch (error) {
      showMessage(`Service error: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  if (!selectedNode || selectedNode.type !== 'host') {
    return (
      <div className="p-8">
        <EmptyState
          icon={<Monitor className="w-8 h-8 text-gray-400" />}
          title="No Host Selected"
          description="Select a host node from the Overview tab to configure its settings."
        />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      <HostConfigHeader
        selectedNode={selectedNode}
        loading={loading}
        onApplyConfiguration={applyConfiguration}
      />

      {/* Progress indicator */}
      {applyProgress && (
        <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-blue-900">
              {applyProgress.message}
            </span>
            <span className="text-sm text-blue-700">
              {applyProgress.current} / {applyProgress.total}
            </span>
          </div>
          <div className="w-full bg-blue-200 rounded-full h-2">
            <div 
              className="bg-blue-600 h-2 rounded-full transition-all duration-300"
              style={{ 
                width: `${applyProgress.total > 0 ? (applyProgress.current / applyProgress.total) * 100 : 0}%` 
              }}
            />
          </div>
        </div>
      )}

      <HostStatusSection
        hostStatus={hostStatus}
        sections={sections}
        loading={loading}
        onToggle={toggleSection}
        onRefreshStatus={fetchHostStatus}
        onTestConnectivity={testConnectivity}
      />

      <InterfaceConfigSection
        local={local}
        hostStatus={hostStatus}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggleSection}
      />

      <DNSConfigSection
        local={local}
        hostStatus={hostStatus}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggleSection}
      />

      <ServicesConfigSection
        local={local}
        hostStatus={hostStatus}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggleSection}
        onManageService={manageService}
      />

      <RoutesConfigSection
        local={local}
        hostStatus={hostStatus}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggleSection}
      />

      <FirewallConfigSection
        local={local}
        hostStatus={hostStatus}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggleSection}
      />

      <DHCPConfigSection
        local={local}
        hostStatus={hostStatus}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggleSection}
      />

      <SystemConfigSection
        local={local}
        hostStatus={hostStatus}
        sections={sections}
        dispatch={dispatch}
        onToggle={toggleSection}
      />

      <ConnectivityTestSection
        selectedNode={selectedNode}
        sections={sections}
        loading={loading}
        onToggle={toggleSection}
        onTestConnectivity={testConnectivity}
        local={local}
        dispatch={dispatch}
      />

      {/* Configuration Summary */}
      <div className="p-4 bg-gray-50 rounded-lg border">
        <h3 className="text-sm font-medium text-gray-900 mb-2">Configuration Summary</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-gray-600">Interfaces:</span>
            <span className="ml-2 font-medium">{hostConfigUtils.getSummary(local).interfaces}</span>
          </div>
          <div>
            <span className="text-gray-600">Services to Start:</span>
            <span className="ml-2 font-medium">{hostConfigUtils.getSummary(local).services_to_start}</span>
          </div>
          <div>
            <span className="text-gray-600">Routes to Add:</span>
            <span className="ml-2 font-medium">{hostConfigUtils.getSummary(local).routes_to_add}</span>
          </div>
          <div>
            <span className="text-gray-600">Firewall Rules:</span>
            <span className="ml-2 font-medium">{hostConfigUtils.getSummary(local).firewall_rules}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HostConfigTab;