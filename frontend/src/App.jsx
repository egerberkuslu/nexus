import React, { useState, useEffect, useCallback } from 'react';
import { Wifi, Maximize2, Minimize2, AlertCircle } from 'lucide-react';

// Import components
import Header from './components/Header';
import MetricsDashboard from './components/MetricsDashboard';
import ControlPanel from './components/ControlPanel';
import NetworkVisualization from './components/NetworkVisualization';
import HostTerminal from './components/HostTerminal';
import StatisticsPanel from './components/StatisticsPanel';
import ActivityMonitor from './components/ActivityMonitor';
import PerformanceChart from './components/PerformanceChart';
import FlowStatistics from './components/FlowStatistics';

// Import hooks and utilities
import { useApiCall } from './hooks/useApiCall';
import { useNetworkData } from './hooks/useNetworkData';
import { useControllerData } from './hooks/useControllerData';
import { useTopologyData } from './hooks/useTopologyData';
import { formatBytes } from './utils/formatters';

import './App.css';

const MininetVisualizer = () => {
  // Core state
  const [networkStatus, setNetworkStatus] = useState({ running: false, network_exists: false });
  const [controllerStatus, setControllerStatus] = useState({ running: false, app: null });
  const [topology, setTopology] = useState({ nodes: [], links: [], controllers: [], stats: {} });
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState([]);
  const [selectedHost, setSelectedHost] = useState('');
  const [command, setCommand] = useState('');
  const [ryuApp, setRyuApp] = useState('simple_switch_13');
  const [hoveredNode, setHoveredNode] = useState(null);
  const [dragPositions, setDragPositions] = useState({});
  const [autoControllerEnabled, setAutoControllerEnabled] = useState(true);

  // Real network metrics from backend
  const [networkMetrics, setNetworkMetrics] = useState({
    uptime: '00:00:00',
    packets_transferred: 0,
    total_bytes: 0,
    bandwidth_mbps: 0.0,
    latency_ms: 0.0,
    active_flows: 0,
    total_interfaces: 0
  });

  // Enhanced state for modern features
  const [detailedStats, setDetailedStats] = useState({});
  const [interfaceStats, setInterfaceStats] = useState({});
  const [flowStats, setFlowStats] = useState({});
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connected');
  const [refreshRate, setRefreshRate] = useState(3000);
  const [metricsHistory, setMetricsHistory] = useState([]);
  const [availableApps, setAvailableApps] = useState([]);
  const [controllerLogs, setControllerLogs] = useState([]);
  const [controllerConfig, setControllerConfig] = useState({});
  const [controllerStats, setControllerStats] = useState({});
  const [pingResults, setPingResults] = useState(null);
  const [controllerWarning, setControllerWarning] = useState(false);

  // Custom hooks
  const { apiCall, addLog } = useApiCall(setConnectionStatus, setLogs);
  
  const {
    fetchNetworkMetrics,
    fetchDetailedStats,
    fetchStatus,
    fetchTopology,
    createNetwork: baseCreateNetwork,
    startNetwork: baseStartNetwork,
    stopNetwork,
    runPingTest: baseRunPingTest,
    executeCommand
  } = useNetworkData({
    apiCall,
    addLog,
    setNetworkStatus,
    setTopology,
    setNetworkMetrics,
    setDetailedStats,
    setFlowStats,
    setInterfaceStats,
    setMetricsHistory,
    setLoading,
    networkStatus,
    selectedHost,
    command,
    setCommand
  });

  const {
    fetchControllerStatus,
    fetchAvailableApps,
    fetchControllerLogs,
    fetchControllerConfig,
    fetchControllerStats,
    startController,
    stopController,
    restartController,
    switchControllerApp,
    clearControllerLogs
  } = useControllerData({
    apiCall,
    addLog,
    setControllerStatus,
    setAvailableApps,
    setControllerLogs,
    setControllerConfig,
    setControllerStats,
    setLoading,
    ryuApp,
    setRyuApp,
    controllerStatus
  });

  // New topology management hook
  const {
    savedTopologies,
    loadSavedTopologies,
    saveTopology,
    deleteTopology,
    createCustomTopology,
    importTopologyConfig,
    exportTopologyConfig,
    getVisualizationData,
    validateTopology
  } = useTopologyData({
    apiCall,
    addLog,
    setLoading
  });

  // Enhanced network creation with auto-controller detection
  const createNetwork = useCallback(async (topologyData = null) => {
    setLoading(true);
    try {
      const result = await baseCreateNetwork(topologyData);
      if (result) {
        // Refresh topology data to check for controllers
        await fetchTopology();
      }
      return result;
    } finally {
      setLoading(false);
    }
  }, [baseCreateNetwork, fetchTopology]);

  // Enhanced network start with auto-controller management
  const startNetwork = useCallback(async () => {
    setLoading(true);
    setControllerWarning(false);
    
    try {
      // Check if topology has controller nodes
      const hasControllerNodes = topology.controllers && topology.controllers.length > 0;
      
      if (hasControllerNodes && !controllerStatus.running && autoControllerEnabled) {
        addLog('🔄 Detected OpenFlow topology - starting controller automatically...', 'info', 'controller');
        
        // Start controller first
        const controllerStarted = await startController(ryuApp);
        
        if (controllerStarted) {
          addLog('✅ Controller started successfully', 'success', 'controller');
          // Wait a moment for controller to initialize
          await new Promise(resolve => setTimeout(resolve, 3000));
        } else {
          addLog('⚠️ Failed to start controller - network may not work properly', 'warning', 'controller');
          setControllerWarning(true);
        }
      }
      
      // Start the network
      const result = await baseStartNetwork();
      
      if (result && hasControllerNodes) {
        // Additional wait for OpenFlow switches to connect
        addLog('🔗 Waiting for switches to connect to controller...', 'info', 'network');
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Verify controller connections
        setTimeout(async () => {
          await fetchControllerStats();
          await fetchTopology();
        }, 3000);
      }
      
      return result;
    } catch (error) {
      addLog(`❌ Error starting network: ${error.message}`, 'error', 'network');
      return false;
    } finally {
      setLoading(false);
    }
  }, [baseStartNetwork, topology.controllers, controllerStatus.running, autoControllerEnabled, 
      startController, ryuApp, addLog, fetchControllerStats, fetchTopology]);

  // Enhanced ping test with controller status checking
  const runPingTest = useCallback(async () => {
    setLoading(true);
    
    try {
      // Check if we need a controller but don't have one
      const hasControllerNodes = topology.controllers && topology.controllers.length > 0;
      
      if (hasControllerNodes && !controllerStatus.running) {
        addLog('⚠️ Warning: Running ping test without active controller on OpenFlow network', 'warning', 'network');
      }
      
      const result = await baseRunPingTest();
      setPingResults(result);
      
      // Analyze ping results
      if (result.success) {
        const lossPercent = parseInt(result.packet_loss);
        if (lossPercent === 100 && hasControllerNodes && !controllerStatus.running) {
          addLog('💡 100% packet loss detected. Try starting the controller first for OpenFlow networks.', 'info', 'network');
          setControllerWarning(true);
        } else if (lossPercent === 0) {
          addLog('🎉 Perfect connectivity - 0% packet loss!', 'success', 'network');
        } else if (lossPercent < 50) {
          addLog(`✅ Good connectivity - ${lossPercent}% packet loss`, 'success', 'network');
        } else {
          addLog(`⚠️ Poor connectivity - ${lossPercent}% packet loss`, 'warning', 'network');
        }
      }
      
      return result;
    } finally {
      setLoading(false);
    }
  }, [baseRunPingTest, topology.controllers, controllerStatus.running, addLog]);

  // Load saved topologies on component mount
  useEffect(() => {
    loadSavedTopologies();
  }, [loadSavedTopologies]);

  // Enhanced main effect with intelligent controller management
  useEffect(() => {
    // Initial fetch
    Promise.all([
      fetchStatus(),
      fetchTopology(),
      fetchControllerStatus(),
      fetchAvailableApps(),
      fetchControllerConfig()
    ]);

    // Set up intervals for real-time updates
    const statusInterval = setInterval(() => {
      fetchStatus();
      fetchControllerStatus();
    }, refreshRate);

    const metricsInterval = setInterval(() => {
      if (networkStatus.running) {
        fetchNetworkMetrics();
        fetchTopology();
      }
    }, refreshRate);

    const detailedStatsInterval = setInterval(() => {
      if (networkStatus.running) {
        fetchDetailedStats();
        if (controllerStatus.running) {
          fetchControllerStats();
        }
      }
    }, refreshRate * 2);

    const controllerLogsInterval = setInterval(() => {
      if (controllerStatus.running) {
        fetchControllerLogs();
      }
    }, refreshRate * 3);

    return () => {
      clearInterval(statusInterval);
      clearInterval(metricsInterval);
      clearInterval(detailedStatsInterval);
      clearInterval(controllerLogsInterval);
    };
  }, [networkStatus.running, controllerStatus.running, refreshRate, fetchStatus, 
      fetchControllerStatus, fetchNetworkMetrics, fetchTopology, fetchDetailedStats, 
      fetchAvailableApps, fetchControllerConfig, fetchControllerLogs, fetchControllerStats]);

  // Monitor for controller warning conditions
  useEffect(() => {
    const hasControllerNodes = topology.controllers && topology.controllers.length > 0;
    const shouldWarn = hasControllerNodes && !controllerStatus.running && networkStatus.running;
    setControllerWarning(shouldWarn);
  }, [topology.controllers, controllerStatus.running, networkStatus.running]);

  // Enhanced topology creation handler
  const handleCreateCustomTopology = useCallback(async (topologyConfig) => {
    // Validate topology first
    const validation = validateTopology(topologyConfig);
    
    if (!validation.isValid) {
      addLog(`❌ Topology validation failed: ${validation.errors.join(', ')}`, 'error', 'topology');
      return false;
    }

    if (validation.warnings.length > 0) {
      addLog(`⚠️ Topology warnings: ${validation.warnings.join(', ')}`, 'warning', 'topology');
    }

    // Create the topology
    const success = await createCustomTopology(topologyConfig);
    
    if (success) {
      // Refresh topology data after creation
      await Promise.all([fetchStatus(), fetchTopology()]);
      
      // Check if this topology needs a controller
      const hasControllerNodes = topologyConfig.nodes?.some(node => node.type === 'controller');
      if (hasControllerNodes) {
        addLog('ℹ️ OpenFlow topology created. Controller will auto-start when network starts.', 'info', 'topology');
      }
    }
    
    return success;
  }, [createCustomTopology, validateTopology, addLog, fetchStatus, fetchTopology]);

  // Enhanced topology save handler
  const handleSaveTopology = useCallback((topologyConfig) => {
    const validation = validateTopology(topologyConfig);
    
    if (!validation.isValid) {
      addLog(`❌ Cannot save invalid topology: ${validation.errors.join(', ')}`, 'error', 'topology');
      return null;
    }

    return saveTopology(topologyConfig);
  }, [saveTopology, validateTopology, addLog]);

  // Calculate trends for metrics
  const calculateTrend = (current, history, key) => {
    if (history.length < 2) return 0;
    const previous = history[history.length - 2][key] || 0;
    if (previous === 0) return 0;
    return ((current - previous) / previous) * 100;
  };

  const bandwidthTrend = calculateTrend(networkMetrics.bandwidth_mbps, metricsHistory, 'bandwidth_mbps');
  const latencyTrend = calculateTrend(networkMetrics.latency_ms, metricsHistory, 'latency_ms');
  const packetTrend = calculateTrend(networkMetrics.packets_transferred, metricsHistory, 'packets_transferred');

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      <Header
        networkStatus={networkStatus}
        controllerStatus={controllerStatus}
        refreshRate={refreshRate}
        setRefreshRate={setRefreshRate}
        isFullscreen={isFullscreen}
        setIsFullscreen={setIsFullscreen}
        autoControllerEnabled={autoControllerEnabled}
        setAutoControllerEnabled={setAutoControllerEnabled}
        controllerWarning={controllerWarning}
        onExportTopology={() => exportTopologyConfig('json')}
        onImportTopology={importTopologyConfig}
      />

      {/* Controller Warning Banner */}
      {controllerWarning && (
        <div className="bg-yellow-100 border-l-4 border-yellow-500 p-4 mx-4 mt-2 rounded">
          <div className="flex items-center">
            <AlertCircle className="w-5 h-5 text-yellow-500 mr-3" />
            <div className="text-sm text-yellow-700">
              <p className="font-medium">Controller Required</p>
              <p>Your topology has OpenFlow switches but no active controller. 
                 <button 
                   onClick={() => startController(ryuApp)}
                   className="ml-1 underline hover:no-underline font-medium"
                 >
                   Start Controller
                 </button> for proper operation.
              </p>
            </div>
          </div>
        </div>
      )}

      <main className={`${isFullscreen ? 'fixed inset-0 top-0 z-50 bg-white' : 'max-w-[95%] mx-auto px-4 py-6'}`}>
        <MetricsDashboard
          topology={topology}
          networkMetrics={networkMetrics}
          packetTrend={packetTrend}
          bandwidthTrend={bandwidthTrend}
          controllerStatus={controllerStatus}
          pingResults={pingResults}
        />

        <ControlPanel
          createNetwork={createNetwork}
          startNetwork={startNetwork}
          stopNetwork={stopNetwork}
          runPingTest={runPingTest}
          startController={startController}
          stopController={stopController}
          restartController={restartController}
          switchControllerApp={switchControllerApp}
          clearControllerLogs={clearControllerLogs}
          networkStatus={networkStatus}
          controllerStatus={controllerStatus}
          ryuApp={ryuApp}
          setRyuApp={setRyuApp}
          availableApps={availableApps}
          controllerConfig={controllerConfig}
          controllerStats={controllerStats}
          controllerLogs={controllerLogs}
          loading={loading}
          autoControllerEnabled={autoControllerEnabled}
          setAutoControllerEnabled={setAutoControllerEnabled}
          createCustomTopology={handleCreateCustomTopology}
          savedTopologies={savedTopologies}
          onSaveTopology={handleSaveTopology}
        />

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <NetworkVisualization
            topology={topology}
            networkStatus={networkStatus}
            controllerStatus={controllerStatus}
            networkMetrics={networkMetrics}
            flowStats={flowStats}
            hoveredNode={hoveredNode}
            setHoveredNode={setHoveredNode}
            dragPositions={dragPositions}
            setDragPositions={setDragPositions}
            selectedHost={selectedHost}
            setSelectedHost={setSelectedHost}
            connectionStatus={connectionStatus}
            controllerConfig={controllerConfig}
            controllerStats={controllerStats}
            ryuApp={ryuApp}
            formatBytes={formatBytes}
            createNetwork={createNetwork}
            pingResults={pingResults}
            onExportTopology={() => exportTopologyConfig('dot')}
            onGetVisualizationData={getVisualizationData}
          />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <HostTerminal
              selectedHost={selectedHost}
              setSelectedHost={setSelectedHost}
              command={command}
              setCommand={setCommand}
              executeCommand={executeCommand}
              topology={topology}
              networkStatus={networkStatus}
              loading={loading}
            />

            <StatisticsPanel
              networkMetrics={networkMetrics}
              packetTrend={packetTrend}
              bandwidthTrend={bandwidthTrend}
              latencyTrend={latencyTrend}
              controllerStatus={controllerStatus}
              controllerConfig={controllerConfig}
              controllerStats={controllerStats}
              controllerLogs={controllerLogs}
              clearControllerLogs={clearControllerLogs}
              ryuApp={ryuApp}
              formatBytes={formatBytes}
              topology={topology}
              networkStatus={networkStatus}
            />

            <ActivityMonitor
              logs={logs}
              setLogs={setLogs}
              connectionStatus={connectionStatus}
              autoControllerEnabled={autoControllerEnabled}
            />

            {metricsHistory.length > 5 && (
              <PerformanceChart
                metricsHistory={metricsHistory}
                controllerStatus={controllerStatus}
                networkMode={topology.controllers?.length > 0 ? 'OpenFlow' : 'Learning Bridge'}
              />
            )}
          </div>
        </div>

        <FlowStatistics
          flowStats={flowStats}
          controllerStats={controllerStats}
          controllerStatus={controllerStatus}
          controllerConfig={controllerConfig}
          controllerLogs={controllerLogs}
          availableApps={availableApps}
          fetchControllerLogs={fetchControllerLogs}
          clearControllerLogs={clearControllerLogs}
          switchControllerApp={switchControllerApp}
          setRyuApp={setRyuApp}
          addLog={addLog}
          loading={loading}
          formatBytes={formatBytes}
          topology={topology}
          networkStatus={networkStatus}
          savedTopologies={savedTopologies}
          onDeleteTopology={deleteTopology}
          autoControllerEnabled={autoControllerEnabled}
        />
      </main>

      {/* Enhanced Status Footer */}
      <footer className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-sm border-t border-gray-200 px-4 py-2">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                connectionStatus === 'connected' ? 'bg-green-500' : 
                connectionStatus === 'connecting' ? 'bg-yellow-500' : 'bg-red-500'
              }`} />
              <span>API {connectionStatus}</span>
            </div>
            
            <div className="flex items-center gap-2">
              <Wifi className="w-3 h-3" />
              <span>Network {networkStatus.running ? 'Active' : 'Inactive'}</span>
            </div>
            
            {topology.controllers?.length > 0 && (
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${
                  controllerStatus.running ? 'bg-blue-500' : 'bg-gray-400'
                }`} />
                <span>Controller {controllerStatus.running ? 'Running' : 'Stopped'}</span>
              </div>
            )}
            
            {autoControllerEnabled && (
              <div className="flex items-center gap-1 text-blue-600">
                <span>🤖</span>
                <span>Auto-Controller</span>
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-4">
            <span>Refresh: {refreshRate/1000}s</span>
            <span>Nodes: {topology.nodes?.length || 0}</span>
            <span>Links: {topology.links?.length || 0}</span>
            {networkStatus.running && (
              <span>Uptime: {networkMetrics.uptime}</span>
            )}
          </div>
        </div>
      </footer>

      <style jsx>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 8px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: #f1f5f9;
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #cbd5e1;
          border-radius: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #94a3b8;
        }
        
        /* Animation for controller warning */
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        
        .controller-warning {
          animation: pulse 2s ease-in-out infinite;
        }
        
        /* Smooth transitions for status changes */
        .status-transition {
          transition: all 0.3s ease-in-out;
        }
        
        /* Enhanced loading states */
        .loading-shimmer {
          background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
          background-size: 200% 100%;
          animation: shimmer 1.5s infinite;
        }
        
        @keyframes shimmer {
          0% { background-position: -200% 0; }
          100% { background-position: 200% 0; }
        }
        
        /* Network mode indicators */
        .openflow-mode {
          border-left: 4px solid #3b82f6;
        }
        
        .bridge-mode {
          border-left: 4px solid #10b981;
        }
        
        .warning-mode {
          border-left: 4px solid #f59e0b;
        }
      `}</style>
    </div>
  );
};

export default MininetVisualizer;