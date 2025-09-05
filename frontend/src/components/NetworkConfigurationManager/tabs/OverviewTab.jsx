// OverviewTab.jsx - Main overview component with separated Apply Configuration
import React, { useEffect, useState } from 'react';
import { 
  Monitor, Server, Route, Settings, Activity,
  CheckCircle, AlertCircle, Network, RefreshCw, ChevronRight, ChevronDown,
  Plus, Trash2, Link as LinkIcon, Info
} from 'lucide-react';
import ApplyConfigurationPanel from './ApplyConfigurationPanel';

const StatusBadge = ({ status, label }) => {
  const statusClasses = {
    healthy: 'bg-green-100 text-green-800 border-green-200',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-200', 
    error: 'bg-red-100 text-red-800 border-red-200',
    info: 'bg-blue-100 text-blue-800 border-blue-200',
    neutral: 'bg-gray-100 text-gray-800 border-gray-200'
  };
  
  return (
    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${statusClasses[status] || statusClasses.neutral}`}>
      {label}
    </span>
  );
};

const ActionButton = ({ onClick, loading, icon, label, variant = 'primary', size = 'md', disabled = false }) => {
  const baseClasses = 'inline-flex items-center gap-2 font-medium rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-offset-2';
  const variantClasses = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500',
    secondary: 'bg-gray-100 hover:bg-gray-200 text-gray-900 focus:ring-gray-500'
  };
  const sizeClasses = {
    sm: 'px-3 py-2 text-sm',
    md: 'px-4 py-2 text-sm'
  };
  
  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${(disabled || loading) ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      {loading ? <RefreshCw size={16} className="animate-spin" /> : icon}
      {label}
    </button>
  );
};

const ConfigSection = ({ title, subtitle, icon: Icon, expanded = false, actions, children }) => {
  const [isExpanded, setIsExpanded] = useState(expanded);
  
  return (
    <div className="bg-white rounded-2xl border border-gray-200 shadow-sm">
      <div className="p-6 border-b border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gray-100 rounded-lg">
              <Icon size={20} className="text-gray-600" />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-black">{title}</h3>
              {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {actions}
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </button>
          </div>
        </div>
      </div>
      {isExpanded && <div className="p-6">{children}</div>}
    </div>
  );
};

export const OverviewTab = ({
  topology,
  selectedNode,
  onNodeSelect,
  apiCall,
  showMessage,
  loading,
  setLoading,
  // Add new props for incremental operations
  onAddNode,
  onRemoveNode,
  onAddLink,
  onRemoveLink,
  // Creation helpers
  createNetwork,
  createCustomTopology,
  createPredefinedTopology
}) => {
  // ---------------------- STATUS STATES ----------------------
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
    total_bytes: 0,
    packets_transferred: 0
  });

  // ---------------------- LIVE TOPOLOGY EDITOR STATES ----------------------
  const [showAddNodeModal, setShowAddNodeModal] = useState(false);
  const [showAddLinkModal, setShowAddLinkModal] = useState(false);
  const [newNodeType, setNewNodeType] = useState('host');
  const [newNodeId, setNewNodeId] = useState('');
  const [newNodeIP, setNewNodeIP] = useState('');
  const [newLinkSource, setNewLinkSource] = useState('');
  const [newLinkTarget, setNewLinkTarget] = useState('');

  // ---------------------- LIVE TOPOLOGY EDITOR HANDLERS ----------------------
  const handleQuickAddNode = async (type) => {
    if (!onAddNode) {
      showMessage('Add node functionality not available', 'error');
      return;
    }

    try {
      setLoading(true);
      const existingNodes = topology?.nodes?.filter(n => n.type === type) || [];
      const nodeId = `${type === 'host' ? 'h' : type === 'switch' ? 's' : type === 'router' ? 'r' : 'c'}${existingNodes.length + 1}`;
      
      const result = await onAddNode({
        id: nodeId,
        type: type,
        ip: type === 'host' ? `10.0.0.${existingNodes.length + 1}` : undefined
      });

      if (result.success) {
        showMessage(`Added ${type} "${nodeId}" successfully`, 'success');
        setNewNodeId('');
        setNewNodeType('host');
      } else {
        showMessage(`Failed to add ${type}: ${result.error}`, 'error');
      }
    } catch (error) {
      showMessage(`Error adding ${type}: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleAddNode = async () => {
    if (!onAddNode || !newNodeId.trim()) {
      showMessage('Please enter a node ID', 'error');
      return;
    }

    try {
      setLoading(true);
      const nodeData = {
        id: newNodeId.trim(),
        type: newNodeType
      };

      // Add IP address if specified for hosts
      if (newNodeType === 'host') {
        if (newNodeIP.trim()) {
          nodeData.ip = newNodeIP.trim();
        } else {
          nodeData.ip = 'auto'; // Auto-assign IP
        }
      }

      const result = await onAddNode(nodeData);

      if (result.success) {
        showMessage(`Added ${newNodeType} "${newNodeId}" successfully`, 'success');
        setShowAddNodeModal(false);
        setNewNodeId('');
        setNewNodeIP('');
        setNewNodeType('host');
      } else {
        showMessage(`Failed to add ${newNodeType}: ${result.error}`, 'error');
      }
    } catch (error) {
      showMessage(`Error adding ${newNodeType}: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveNode = async (nodeId) => {
    if (!onRemoveNode) {
      showMessage('Remove node functionality not available', 'error');
      return;
    }

    if (!window.confirm(`Are you sure you want to remove ${nodeId}? This will also remove all its connections.`)) {
      return;
    }

    try {
      setLoading(true);
      const result = await onRemoveNode(nodeId);

      if (result.success) {
        showMessage(`Removed ${nodeId} successfully`, 'success');
        onNodeSelect(null); // Clear selection
      } else {
        showMessage(`Failed to remove ${nodeId}: ${result.error}`, 'error');
      }
    } catch (error) {
      showMessage(`Error removing ${nodeId}: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleAddLink = async () => {
    if (!onAddLink || !newLinkSource || !newLinkTarget) {
      showMessage('Please select both source and target nodes', 'error');
      return;
    }

    if (newLinkSource === newLinkTarget) {
      showMessage('Source and target nodes must be different', 'error');
      return;
    }

    try {
      setLoading(true);
      const result = await onAddLink({
        source: newLinkSource,
        target: newLinkTarget,
        bandwidth: '1G'
      });

      if (result.success) {
        showMessage(`Added link between ${newLinkSource} and ${newLinkTarget} successfully`, 'success');
        setShowAddLinkModal(false);
        setNewLinkSource('');
        setNewLinkTarget('');
      } else {
        showMessage(`Failed to add link: ${result.error}`, 'error');
      }
    } catch (error) {
      showMessage(`Error adding link: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };
  
  const [controllerStatus, setControllerStatus] = useState({ 
    running: false, 
    controller_type: 'Unknown', 
    port: 6633, 
    connections: 0,
    memory_usage: 0
  });

  // ---------------------- AUTO REFRESH ----------------------
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

  // ---------------------- FETCHERS ----------------------
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
    } catch (e) {
      console.error('Failed to fetch network status:', e);
    }
  };

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
    } catch (e) {
      console.error('Failed to fetch network metrics:', e);
    }
  };

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
    } catch (e) {
      console.error('Failed to fetch controller status:', e);
    }
  };

  // ---------------------- ACTIONS ----------------------
  const refreshAll = async () => {
    setLoading(true);
    try {
      await Promise.all([
        fetchNetworkStatus(), 
        fetchNetworkMetrics(), 
        fetchControllerStatus()
      ]);
      showMessage('Status refreshed successfully', 'success');
    } catch (e) {
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
        await fetchNetworkMetrics();
      } else {
        showMessage(`Ping test failed: ${response.error}`, 'error');
      }
    } catch (e) {
      showMessage(`Ping test error: ${e.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  // ---------------------- VISUALIZATION HELPERS ----------------------
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
    { type: 'router', icon: Route, label: 'Routers', count: stats.routers, color: 'text-green-600' },
    { type: 'controller', icon: Settings, label: 'Controllers', count: stats.controllers, color: 'text-red-600' }
  ];

  const getNodeIcon = (type) => {
    const icons = { host: Monitor, switch: Server, router: Route, controller: Settings };
    return icons[type] || Monitor;
  };

  const getNodeStatus = (node) => {
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

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  // ---------------------- RENDER ----------------------
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

        {/* Status Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="flex items-center gap-3">
            <StatusBadge 
              status={getOverallNetworkStatus()} 
              label={`Network: ${networkStatus.running ? 'Running' : 'Stopped'}`} 
            />
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge 
              status={controllerStatus.running ? 'healthy' : 'warning'} 
              label={`Controller: ${controllerStatus.running ? 'Running' : 'Stopped'}`} 
            />
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status="info" label={`${stats.totalNodes} Total Nodes`} />
          </div>
          <div className="flex items-center gap-3">
            <StatusBadge status="info" label={`${stats.totalLinks} Links`} />
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

      {/* Apply Configuration Panel - Separated Component */}
      <ApplyConfigurationPanel 
        apiCall={apiCall}
        showMessage={showMessage}
        networkStatus={networkStatus}
        refreshAll={refreshAll}
      />

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
                  className={`relative p-4 rounded-xl border-2 text-left transition-all ${
                    isSelected
                      ? 'border-blue-500 bg-blue-50 shadow-md'
                      : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-sm'
                  }`}
                >
                  <div
                    className={`absolute top-3 right-3 w-2 h-2 rounded-full ${
                      status === 'healthy'
                        ? 'bg-green-500'
                        : status === 'warning'
                        ? 'bg-yellow-500'
                        : status === 'error'
                        ? 'bg-red-500'
                        : 'bg-gray-400'
                    }`}
                  />
                  <div className="flex items-start gap-3">
                    <div className="p-2 bg-gray-100 rounded-lg">
                      <Icon size={20} className="text-black opacity-70" />
                    </div>
                    <div className="flex-1">
                      <h4 className="font-medium text-black">{node.id}</h4>
                      <p className="text-xs text-gray-600 capitalize">{node.type}</p>
                      {node.ip && <p className="text-xs text-black mt-1 font-mono">{node.ip}</p>}
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

      {/* Live Topology Editor or Creation depending on network state */}
      {networkStatus.running ? (
        <>
          {/* Live Topology Editor */}
          <ConfigSection 
            title="Live Topology Editor" 
            icon={Network} 
            expanded={true}
            actions={
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowAddNodeModal(true)}
                  className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                >
                  <Plus size={16} />
                  Add Node
                </button>
                <button
                  onClick={() => setShowAddLinkModal(true)}
                  className="inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors"
                >
                  <LinkIcon size={16} />
                  Add Link
                </button>
              </div>
            }
          >
            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-blue-100 rounded-lg">
                    <Info size={20} className="text-blue-600" />
                  </div>
                  <div className="flex-1">
                    <h4 className="font-medium text-blue-900 mb-1">Real-time Topology Updates</h4>
                    <p className="text-sm text-blue-700">
                      Add or remove network devices and connections while the network is running. 
                      Changes are applied immediately without interrupting network operations.
                    </p>
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <h5 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                    <Plus size={16} className="text-blue-600" />
                    Quick Add Node
                  </h5>
                  <div className="space-y-3">
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        onClick={() => handleQuickAddNode('host')}
                        className="p-3 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors"
                      >
                        + Host
                      </button>
                      <button
                        onClick={() => handleQuickAddNode('switch')}
                        className="p-3 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors"
                      >
                        + Switch
                      </button>
                      <button
                        onClick={() => handleQuickAddNode('router')}
                        className="p-3 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors"
                      >
                        + Router
                      </button>
                      <button
                        onClick={() => handleQuickAddNode('controller')}
                        className="p-3 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-200 rounded-lg hover:bg-gray-100 transition-colors"
                      >
                        + Controller
                      </button>
                    </div>
                  </div>
                </div>

                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <h5 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                    <Trash2 size={16} className="text-red-600" />
                    Remove Elements
                  </h5>
                  <div className="space-y-3">
                    <p className="text-sm text-gray-600">
                      Select a node or link in the topology view above, then click the delete button to remove it.
                    </p>
                    {selectedNode && (
                      <button
                        onClick={() => handleRemoveNode(selectedNode.id)}
                        className="w-full p-3 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition-colors flex items-center justify-center gap-2"
                      >
                        <Trash2 size={16} />
                        Remove {selectedNode.type} "{selectedNode.id}"
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </ConfigSection>
        </>
      ) : (
        <>
          {/* Network Creation Panel when stopped or not created */}
          <ConfigSection 
            title="Create a Network Topology" 
            icon={Network} 
            expanded={true}
          >
            <div className="space-y-4">
              <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                <div className="flex items-start gap-3">
                  <div className="p-2 bg-yellow-100 rounded-lg">
                    <Info size={20} className="text-yellow-700" />
                  </div>
                  <div>
                    <h4 className="font-medium text-yellow-900 mb-1">Network is not running</h4>
                    <p className="text-sm text-yellow-800">Create and start a topology to begin. You can also open the custom builder to design one before creating.</p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <h5 className="font-medium text-gray-900 mb-3">Quick Create</h5>
                  <div className="grid grid-cols-2 gap-2">
                    <button
                      onClick={() => createPredefinedTopology && createPredefinedTopology('simple')}
                      className="p-3 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
                    >Simple</button>
                    <button
                      onClick={() => createPredefinedTopology && createPredefinedTopology('linear')}
                      className="p-3 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
                    >Linear</button>
                    <button
                      onClick={() => createPredefinedTopology && createPredefinedTopology('tree')}
                      className="p-3 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
                    >Tree</button>
                    <button
                      onClick={() => createPredefinedTopology && createPredefinedTopology('star')}
                      className="p-3 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors"
                    >Star</button>
                  </div>
                  <div className="mt-4">
                    <button
                      onClick={() => createNetwork && createNetwork()}
                      className="w-full p-3 text-sm font-medium text-gray-800 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                    >Create Default</button>
                  </div>
                </div>

                <div className="bg-white border border-gray-200 rounded-lg p-4">
                  <h5 className="font-medium text-gray-900 mb-3">Custom Builder</h5>
                  <p className="text-sm text-gray-600 mb-3">Open the custom topology builder to design a network, then create it.</p>
                  <button
                    onClick={() => setShowAddNodeModal(true)}
                    className="w-full p-3 text-sm font-medium text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 transition-colors"
                  >Open Builder</button>
                </div>
              </div>
            </div>
          </ConfigSection>
        </>
      )}

      {/* Add Node Modal */}
      {showAddNodeModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-800">Add New Node</h3>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Node Type</label>
                <select
                  value={newNodeType}
                  onChange={(e) => setNewNodeType(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="host">Host</option>
                  <option value="switch">Switch</option>
                  <option value="router">Router</option>
                  <option value="controller">Controller</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Node ID</label>
                <input
                  type="text"
                  value={newNodeId}
                  onChange={(e) => setNewNodeId(e.target.value)}
                  placeholder="e.g., h5, s3, r2"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
              {/* IP Address input for hosts */}
              {newNodeType === 'host' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">IP Address</label>
                  <input
                    type="text"
                    value={newNodeIP}
                    onChange={(e) => setNewNodeIP(e.target.value)}
                    placeholder="10.0.0.1"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">Leave empty for auto-assignment</p>
                </div>
              )}
              <div className="flex items-center gap-3 pt-4">
                <button
                  onClick={() => setShowAddNodeModal(false)}
                  className="flex-1 px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddNode}
                  disabled={!newNodeId.trim()}
                  className="flex-1 px-4 py-2 text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Add Node
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add Link Modal */}
      {showAddLinkModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-800">Add New Link</h3>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Source Node</label>
                <select
                  value={newLinkSource}
                  onChange={(e) => setNewLinkSource(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">Select source node</option>
                  {topology?.nodes?.map(node => (
                    <option key={node.id} value={node.id}>{node.id} ({node.type})</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Target Node</label>
                <select
                  value={newLinkTarget}
                  onChange={(e) => setNewLinkTarget(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="">Select target node</option>
                  {topology?.nodes?.map(node => (
                    <option key={node.id} value={node.id}>{node.id} ({node.type})</option>
                  ))}
                </select>
              </div>
              <div className="flex items-center gap-3 pt-4">
                <button
                  onClick={() => setShowAddLinkModal(false)}
                  className="flex-1 px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAddLink}
                  disabled={!newLinkSource || !newLinkTarget || newLinkSource === newLinkTarget}
                  className="flex-1 px-4 py-2 text-white bg-green-600 rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Add Link
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Selected Node Details */}
      {selectedNode && (
        <ConfigSection title="Node Information" icon={Activity} expanded={true}>
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
                label={networkStatus.running ? selectedNode.status || 'Active' : 'Inactive'}
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
                <div className="mt-1 space-y-1">
                  {selectedNode.interfaces.map((intf, index) => (
                    <div key={index} className="bg-gray-50 rounded p-2">
                      <p className="text-sm text-black font-mono">
                        <span className="font-semibold">{intf.name}:</span> {intf.ip}
                      </p>
                      {intf.mac && intf.mac !== 'unknown' && (
                        <p className="text-xs text-gray-600 font-mono">MAC: {intf.mac}</p>
                      )}
                    </div>
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
                {controllerStatus.memory_usage > 0 && (
                  <div>
                    <label className="text-xs text-gray-500">Memory Usage</label>
                    <p className="font-medium text-black">{controllerStatus.memory_usage.toFixed(1)} MB</p>
                  </div>
                )}
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

      {/* Bottom Stats Dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Network Issues</p>
              <p className="text-2xl font-bold text-black">{topology?.issues?.length || 0}</p>
              <p className="text-xs text-gray-400 mt-1">
                {topology?.issues?.length === 0 ? 'All systems normal' : 'Issues detected'}
              </p>
            </div>
            <AlertCircle className={`w-8 h-8 ${topology?.issues?.length > 0 ? 'text-red-500' : 'text-green-500'}`} />
          </div>
        </div>
        
        <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Components</p>
              <p className="text-2xl font-bold text-black">{stats.totalNodes}</p>
              <p className="text-xs text-gray-400 mt-1">
                {networkStatus.running ? `${stats.totalNodes} active` : '0 active'}
              </p>
            </div>
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-xl border border-gray-200 p-4 hover:shadow-md transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Data Transfer</p>
              <p className="text-lg font-bold text-black">{formatBytes(networkMetrics.total_bytes)}</p>
              <p className="text-xs text-gray-400 mt-1">
                {networkMetrics.packets_transferred} packets transferred
              </p>
            </div>
            <Activity className="w-8 h-8 text-blue-500" />
          </div>
        </div>
      </div>
    </div>
  );
};

export default OverviewTab;