// OverviewTab.jsx - Auto-updating with current status
import React, { useEffect, useState } from 'react';
import { Monitor, Server, Router, Settings, Activity, CheckCircle, AlertCircle, Network, RefreshCw } from 'lucide-react';
import { ConfigSection, StatusBadge, ActionButton } from '../components/FormComponents';

export const OverviewTab = ({ 
  topology, 
  selectedNode, 
  onNodeSelect, 
  apiCall, 
  showMessage, 
  loading, 
  setLoading 
}) => {
  const [networkStatus, setNetworkStatus] = useState({
    running: false,
    network_exists: false,
    uptime: '00:00:00'
  });
  const [networkMetrics, setNetworkMetrics] = useState({
    uptime: '00:00:00',
    bandwidth_mbps: 0,
    latency_ms: 0,
    active_flows: 0,
    packets_transferred: 0,
    total_bytes: 0
  });
  const [controllerStatus, setControllerStatus] = useState({
    running: false,
    controller_type: 'Unknown',
    port: 6633,
    connections: 0
  });

  // Auto-refresh data every 5 seconds
  useEffect(() => {
    const fetchAllData = async () => {
      await Promise.all([
        fetchNetworkStatus(),
        fetchNetworkMetrics(),
        fetchControllerStatus()
      ]);
    };

    fetchAllData();
    const interval = setInterval(fetchAllData, 5000);
    return () => clearInterval(interval);
  }, []);

  // Fetch network status from backend
  const fetchNetworkStatus = async () => {
    try {
      const response = await apiCall('/network/status');
      if (response.success) {
        setNetworkStatus({
          running: response.data.running || false,
          network_exists: response.data.network_exists || false,
          uptime: response.data.uptime || '00:00:00',
          topology_summary: response.data.topology_summary || {}
        });
      }
    } catch (error) {
      console.error('Failed to fetch network status:', error);
    }
  };

  // Fetch real-time network metrics
  const fetchNetworkMetrics = async () => {
    try {
      const response = await apiCall('/stats/metrics');
      if (response.success) {
        setNetworkMetrics({
          uptime: response.data.uptime || '00:00:00',
          bandwidth_mbps: response.data.bandwidth_mbps || 0,
          latency_ms: response.data.latency_ms || 0,
          active_flows: response.data.active_flows || 0,
          packets_transferred: response.data.packets_transferred || 0,
          total_bytes: response.data.total_bytes || 0,
          total_interfaces: response.data.total_interfaces || 0
        });
      }
    } catch (error) {
      console.error('Failed to fetch network metrics:', error);
    }
  };

  // Fetch controller status
  const fetchControllerStatus = async () => {
    try {
      const response = await apiCall('/controller/status');
      if (response.success) {
        setControllerStatus({
          running: response.data.running || false,
          controller_type: response.data.controller_type || 'Unknown',
          port: response.data.port || 6633,
          connections: response.data.connections || 0,
          memory_usage: response.data.memory_usage || 0
        });
      }
    } catch (error) {
      console.error('Failed to fetch controller status:', error);
    }
  };

  const refreshAll = async () => {
    setLoading(true);
    try {
      await Promise.all([
        fetchNetworkStatus(),
        fetchNetworkMetrics(),
        fetchControllerStatus()
      ]);
      showMessage('Status refreshed successfully', 'success');
    } catch (error) {
      showMessage('Failed to refresh status', 'error');
    } finally {
      setLoading(false);
    }
  };

  const runPingTest = async () => {
    setLoading(true);
    try {
      const response = await apiCall('/network/ping', { method: 'POST' });
      if (response.success) {
        showMessage(`Ping test completed: ${response.data.result}`, 'success');
        // Refresh metrics after ping test
        await fetchNetworkMetrics();
      } else {
        showMessage(`Ping test failed: ${response.error}`, 'error');
      }
    } catch (error) {
      showMessage(`Ping test error: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // Calculate statistics from current topology
  const stats = {
    hosts: topology?.nodes?.filter(n => n.type === 'host').length || 0,
    switches: topology?.nodes?.filter(n => n.type === 'switch').length || 0,
    routers: topology?.nodes?.filter(n => n.type === 'router').length || 0,
    controllers: topology?.controllers?.length || topology?.nodes?.filter(n => n.type === 'controller').length || 0,
    totalNodes: topology?.nodes?.length || 0,
    totalLinks: topology?.links?.length || 0
  };

  const nodeTypes = [
    { type: 'host', icon: Monitor, label: 'Hosts', count: stats.hosts, color: 'text-blue-600' },
    { type: 'switch', icon: Server, label: 'Switches', count: stats.switches, color: 'text-purple-600' },
    { type: 'router', icon: Router, label: 'Routers', count: stats.routers, color: 'text-green-600' },
    { type: 'controller', icon: Settings, label: 'Controllers', count: stats.controllers, color: 'text-red-600' }
  ];

  const getNodeIcon = (type) => {
    const icons = { host: Monitor, switch: Server, router: Router, controller: Settings };
    return icons[type] || Monitor;
  };

  const getNodeStatus = (node) => {
    // Use real network status to determine node status
    if (!networkStatus.running) return 'neutral';
    if (node.status === 'active') return 'healthy';
    if (node.status === 'error') return 'error';
    if (node.status === 'warning') return 'warning';
    return networkStatus.running ? 'healthy' : 'neutral';
  };

  const getOverallNetworkStatus = () => {
    if (!networkStatus.running) return 'error';
    if (!controllerStatus.running) return 'warning';
    if (stats.totalNodes === 0) return 'warning';
    return 'healthy';
  };

  // Format bytes to human readable
  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="space-y-6 text-black">
      {/* Network Health Overview */}
      <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-xl font-semibold text-black mb-2">Network Health</h3>
            <p className="text-sm text-gray-500">Real-time system status and metrics</p>
          </div>
          <ActionButton
            onClick={refreshAll}
            loading={loading}
            icon={<RefreshCw size={16} />}
            label="Refresh"
            variant="secondary"
            size="sm"
          />
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="flex items-center gap-3">
            <StatusBadge 
              status={getOverallNetworkStatus()} 
              label={`Network: ${networkStatus.running ? 'Running' : 'Stopped'}`} 
            />
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge 
              status={controllerStatus.running ? "healthy" : "warning"} 
              label={`Controller: ${controllerStatus.running ? 'Running' : 'Stopped'}`} 
            />
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge 
              status="info" 
              label={`${stats.totalNodes} Total Nodes`} 
            />
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge 
              status="info" 
              label={`${stats.totalLinks} Links`} 
            />
          </div>
        </div>

        {/* Real-time Network Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
          <div className="text-center">
            <p className="text-sm text-gray-600">Uptime</p>
            <p className="text-lg font-bold text-black">{networkMetrics.uptime}</p>
          </div>
          <div className="text-center">
            <p className="text-sm text-gray-600">Bandwidth</p>
            <p className="text-lg font-bold text-black">{networkMetrics.bandwidth_mbps.toFixed(2)} Mbps</p>
          </div>
          <div className="text-center">
            <p className="text-sm text-gray-600">Latency</p>
            <p className="text-lg font-bold text-black">{networkMetrics.latency_ms.toFixed(2)} ms</p>
          </div>
          <div className="text-center">
            <p className="text-sm text-gray-600">Active Flows</p>
            <p className="text-lg font-bold text-black">{networkMetrics.active_flows}</p>
          </div>
        </div>

        {/* Additional Metrics */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6 p-4 bg-blue-50 rounded-lg">
          <div className="text-center">
            <p className="text-sm text-gray-600">Packets Transferred</p>
            <p className="text-lg font-bold text-black">{networkMetrics.packets_transferred.toLocaleString()}</p>
          </div>
          <div className="text-center">
            <p className="text-sm text-gray-600">Total Bytes</p>
            <p className="text-lg font-bold text-black">{formatBytes(networkMetrics.total_bytes)}</p>
          </div>
          <div className="text-center">
            <p className="text-sm text-gray-600">Interfaces</p>
            <p className="text-lg font-bold text-black">{networkMetrics.total_interfaces}</p>
          </div>
        </div>

        {/* Node Type Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {nodeTypes.map(({ type, icon: Icon, label, count, color }) => (
            <div 
              key={type} 
              className="bg-gray-50 rounded-xl p-4 border border-gray-100 hover:border-gray-300 hover:shadow-md transition-all"
            >
              <div className="flex items-center justify-between mb-2">
                <Icon className={`w-5 h-5 ${color}`} />
                <span className="text-2xl font-bold text-black">{count}</span>
              </div>
              <p className="text-sm text-black opacity-70">{label}</p>
            </div>
          ))}
        </div>

        {/* Quick Actions */}
        <div className="flex gap-2 mt-6 pt-4 border-t border-gray-200">
          <ActionButton
            onClick={runPingTest}
            loading={loading}
            icon={<Network size={16} />}
            label="Run Ping Test"
            variant="secondary"
            size="sm"
            disabled={!networkStatus.running}
          />
        </div>
      </div>

      {/* Node Selection */}
      <ConfigSection
        title="Select Node to Configure"
        icon={Network}
        expanded={true}
      >
        {topology?.nodes?.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {topology.nodes.map((node) => {
              const Icon = getNodeIcon(node.type);
              const isSelected = selectedNode?.id === node.id;
              const status = getNodeStatus(node);

              return (
                <button
                  key={node.id}
                  onClick={() => onNodeSelect(node)}
                  className={`
                    relative p-4 rounded-xl border-2 text-left transition-all
                    ${isSelected 
                      ? 'border-blue-500 bg-blue-50 shadow-md' 
                      : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-sm'
                    }
                  `}
                >
                  {/* Status indicator */}
                  <div className={`absolute top-3 right-3 w-2 h-2 rounded-full ${
                    status === 'healthy' ? 'bg-green-500' :
                    status === 'warning' ? 'bg-yellow-500' :
                    status === 'error' ? 'bg-red-500' : 'bg-gray-400'
                  }`} />

                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-gray-100 rounded-lg">
                      <Icon size={20} className="text-black opacity-70" />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-medium text-black">{node.id}</h4>
                      <p className="text-xs text-gray-600 capitalize">{node.type}</p>
                      {node.ip && (
                        <p className="text-xs text-black mt-1 font-mono">{node.ip}</p>
                      )}
                      {node.type === 'switch' && node.controller && (
                        <p className="text-xs text-gray-500 mt-1">Controller: {node.controller}</p>
                      )}
                      {node.type === 'controller' && controllerStatus.running && (
                        <p className="text-xs text-gray-500 mt-1">
                          {controllerStatus.controller_type} | Port: {controllerStatus.port}
                        </p>
                      )}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="text-center py-8">
            <Activity className="w-12 h-12 text-gray-400 mx-auto mb-3" />
            <p className="text-black">No nodes available</p>
            <p className="text-sm text-gray-400 mt-1">Create a network topology first</p>
          </div>
        )}
      </ConfigSection>

      {/* Selected Node Details */}
      {selectedNode && (
        <ConfigSection
          title="Node Information"
          icon={Activity}
          expanded={true}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs text-gray-500">Node ID</label>
              <p className="font-medium text-black">{selectedNode.id}</p>
            </div>
            <div>
              <label className="text-xs text-gray-500">Type</label>
              <p className="font-medium text-black capitalize">{selectedNode.type}</p>
            </div>
            {selectedNode.ip && (
              <div>
                <label className="text-xs text-gray-500">IP Address</label>
                <p className="font-mono text-sm text-black">{selectedNode.ip}</p>
              </div>
            )}
            {selectedNode.mac && selectedNode.mac !== 'N/A' && (
              <div>
                <label className="text-xs text-gray-500">MAC Address</label>
                <p className="font-mono text-sm text-black">{selectedNode.mac}</p>
              </div>
            )}
            <div>
              <label className="text-xs text-gray-500">Status</label>
              <StatusBadge 
                status={getNodeStatus(selectedNode)} 
                label={networkStatus.running ? (selectedNode.status || 'Active') : 'Inactive'} 
              />
            </div>
            {selectedNode.type === 'switch' && selectedNode.controller && (
              <div>
                <label className="text-xs text-gray-500">Controller</label>
                <p className="font-medium text-black">{selectedNode.controller}</p>
              </div>
            )}
            {selectedNode.type === 'router' && selectedNode.interfaces && (
              <div className="md:col-span-2">
                <label className="text-xs text-gray-500">Interfaces</label>
                <div className="mt-1">
                  {selectedNode.interfaces.map((intf, index) => (
                    <p key={index} className="text-sm text-black font-mono">
                      {intf.name}: {intf.ip}
                    </p>
                  ))}
                </div>
              </div>
            )}
            {selectedNode.type === 'controller' && (
              <>
                <div>
                  <label className="text-xs text-gray-500">Port</label>
                  <p className="font-medium text-black">{selectedNode.port || controllerStatus.port}</p>
                </div>
                <div>
                  <label className="text-xs text-gray-500">Type</label>
                  <p className="font-medium text-black">{controllerStatus.controller_type}</p>
                </div>
                <div>
                  <label className="text-xs text-gray-500">Connections</label>
                  <p className="font-medium text-black">{controllerStatus.connections}</p>
                </div>
              </>
            )}
          </div>
          <div className="mt-4 pt-4 border-t border-gray-100">
            <p className="text-sm text-black">
              Navigate to the <span className="font-medium">{selectedNode.type}</span> tab to configure this node.
            </p>
          </div>
        </ConfigSection>
      )}

      {/* Network Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Network Issues</p>
              <p className="text-2xl font-bold text-black">
                {topology?.issues?.length || 0}
              </p>
            </div>
            <AlertCircle className="w-8 h-8 text-yellow-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Components</p>
              <p className="text-2xl font-bold text-black">{stats.totalNodes}</p>
              <p className="text-xs text-gray-400">
                {networkStatus.running ? `${stats.totalNodes} active` : '0 active'}
              </p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Packet Loss</p>
              <p className="text-sm font-medium text-black">0%</p>
              <p className="text-xs text-gray-400">Last ping test</p>
            </div>
            <Activity className="w-8 h-8 text-gray-400" />
          </div>
        </div>
      </div>

      {/* Controller Information */}
      {controllerStatus.running && (
        <ConfigSection
          title="Controller Information"
          icon={Settings}
          expanded={false}
        >
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-gray-500">Type</label>
              <p className="font-medium text-black">{controllerStatus.controller_type}</p>
            </div>
            <div>
              <label className="text-xs text-gray-500">Port</label>
              <p className="font-medium text-black">{controllerStatus.port}</p>
            </div>
            <div>
              <label className="text-xs text-gray-500">Connections</label>
              <p className="font-medium text-black">{controllerStatus.connections}</p>
            </div>
            <div>
              <label className="text-xs text-gray-500">Memory Usage</label>
              <p className="font-medium text-black">{controllerStatus.memory_usage}%</p>
            </div>
          </div>
        </ConfigSection>
      )}
    </div>
  );
};