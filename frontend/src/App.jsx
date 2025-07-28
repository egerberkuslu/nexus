import React, { useState, useEffect, useCallback } from 'react';
import { 
  Wifi, 
  Maximize2, 
  Minimize2, 
  AlertCircle,
  Activity,
  RefreshCw,
  CheckCircle,
  XCircle,
  Zap,
  TrendingUp,
  Router,
  Network,
  Shield,
  Terminal,
  Eye,
  Clock,
  FileText,
  Wrench
} from 'lucide-react';

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
import NetworkDiagnostic from './components/NetworkDiagnostic';
import DiagnosticWidget from './components/DiagnosticWidget';

// Import hooks and utilities
import { useApiCall } from './hooks/useApiCall';
import { useNetworkData } from './hooks/useNetworkData';
import { useControllerData } from './hooks/useControllerData';
import { useTopologyData } from './hooks/useTopologyData';
import { useDiagnostic } from './hooks/useDiagnostic';
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

  // Diagnostic state - NEW
  const [diagnosticOpen, setDiagnosticOpen] = useState(false);
  const [showDiagnosticBadge, setShowDiagnosticBadge] = useState(false);
  const [diagnosticWidgetVisible, setDiagnosticWidgetVisible] = useState(true);

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

  // DIAGNOSTIC HOOK - NEW
  const {
    diagnosticData,
    diagnosticLoading,
    diagnosticErrors,
    fetchNetworkHealth,
    diagnoseConnectivity,
    fetchArpTables,
    fetchRoutingTables,
    fetchSwitchFlows,
    runDetailedPing,
    runTraceRoute,
    fixCommonIssues,
    runComprehensiveTest,
    resetDiagnosticData,
    getDiagnosticSummary
  } = useDiagnostic({ apiCall, addLog });

  // Enhanced network creation with auto-controller detection
  const createNetwork = useCallback(async (topologyData = null) => {
    setLoading(true);
    try {
      const result = await baseCreateNetwork(topologyData);
      if (result) {
        // Refresh topology data to check for controllers
        await fetchTopology();
        // Show diagnostic widget after network creation
        setDiagnosticWidgetVisible(true);
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
          // Run quick diagnostic check after network starts
          setTimeout(quickDiagnosticCheck, 5000);
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
          // Auto-open diagnostics on complete failure
          setTimeout(() => setDiagnosticOpen(true), 1000);
        } else if (lossPercent === 0) {
          addLog('🎉 Perfect connectivity - 0% packet loss!', 'success', 'network');
        } else if (lossPercent < 50) {
          addLog(`✅ Good connectivity - ${lossPercent}% packet loss`, 'success', 'network');
        } else {
          addLog(`⚠️ Poor connectivity - ${lossPercent}% packet loss`, 'warning', 'network');
          // Auto-open diagnostics on high packet loss
          setTimeout(() => setDiagnosticOpen(true), 1000);
        }
      }
      
      return result;
    } finally {
      setLoading(false);
    }
  }, [baseRunPingTest, topology.controllers, controllerStatus.running, addLog]);

  // Quick diagnostic check function - NEW
  const quickDiagnosticCheck = useCallback(async () => {
    if (!networkStatus.running) return;
    
    addLog('🔍 Running quick diagnostic check...', 'info', 'diagnostic');
    const health = await fetchNetworkHealth();
    
    if (health && health.overall_status !== 'healthy') {
      setShowDiagnosticBadge(true);
      addLog(`⚠️ Network issues detected: ${health.overall_status}`, 'warning', 'diagnostic');
    }
  }, [networkStatus.running, fetchNetworkHealth, addLog]);

  // Diagnostic button component - NEW
  const DiagnosticButton = useCallback(() => {
    const summary = getDiagnosticSummary();
    
    return (
      <button
        onClick={() => setDiagnosticOpen(true)}
        className={`relative flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
          showDiagnosticBadge 
            ? 'bg-red-500 hover:bg-red-600 text-white animate-pulse' 
            : summary.overallStatus === 'healthy'
            ? 'bg-green-100 hover:bg-green-200 text-green-700'
            : summary.overallStatus === 'warning'
            ? 'bg-yellow-100 hover:bg-yellow-200 text-yellow-700'
            : summary.overallStatus === 'critical'
            ? 'bg-red-100 hover:bg-red-200 text-red-700'
            : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
        }`}
        title="Open Network Diagnostics"
      >
        <Activity className="w-5 h-5" />
        <span>Diagnostics</span>
        
        {/* Issue count badge */}
        {summary.issuesCount > 0 && (
          <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full w-6 h-6 flex items-center justify-center font-bold">
            {summary.issuesCount > 9 ? '9+' : summary.issuesCount}
          </span>
        )}
        
        {/* Health indicator dot */}
        <div className={`w-2 h-2 rounded-full ${
          summary.overallStatus === 'healthy' ? 'bg-green-500' :
          summary.overallStatus === 'warning' ? 'bg-yellow-500' :
          summary.overallStatus === 'critical' ? 'bg-red-500' : 'bg-gray-400'
        }`} />
      </button>
    );
  }, [getDiagnosticSummary, showDiagnosticBadge]);

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

  // Monitor for diagnostic badge conditions - NEW
  useEffect(() => {
    // Show diagnostic badge if there are connectivity issues
    const hasControllerIssues = topology.controllers?.length > 0 && !controllerStatus.running && networkStatus.running;
    const hasPingFailures = pingResults && parseInt(pingResults.packet_loss) > 50;
    const hasNetworkIssues = !networkStatus.running && networkStatus.network_exists;
    
    setShowDiagnosticBadge(hasControllerIssues || hasPingFailures || hasNetworkIssues);
  }, [topology.controllers, controllerStatus.running, networkStatus, pingResults]);

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
        DiagnosticButton={DiagnosticButton}
        diagnosticSummary={getDiagnosticSummary()}
      />

      {/* Enhanced Controller Warning Banner with Diagnostic Link */}
      {controllerWarning && (
        <div className="bg-yellow-100 border-l-4 border-yellow-500 p-4 mx-4 mt-2 rounded">
          <div className="flex items-center justify-between">
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
            <button
              onClick={() => setDiagnosticOpen(true)}
              className="bg-yellow-200 hover:bg-yellow-300 text-yellow-800 px-3 py-1 rounded text-sm font-medium flex items-center gap-2"
            >
              <Activity className="w-4 h-4" />
              Diagnose Issues
            </button>
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
          diagnosticSummary={getDiagnosticSummary()}
          onOpenDiagnostics={() => setDiagnosticOpen(true)}
        />

        {/* Control Panel with Diagnostic Widget */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-6">
          <div className="lg:col-span-3">
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
              onOpenDiagnostics={() => setDiagnosticOpen(true)}
              onRunDiagnostics={quickDiagnosticCheck}
              diagnosticSummary={getDiagnosticSummary()}
            />
          </div>
          
          {/* Diagnostic Widget */}
          <div className="lg:col-span-1">
            {diagnosticWidgetVisible && (
              <DiagnosticWidget
                diagnosticSummary={getDiagnosticSummary()}
                onOpenDiagnostics={() => setDiagnosticOpen(true)}
                onRunQuickCheck={quickDiagnosticCheck}
                loading={diagnosticLoading.health}
              />
            )}
          </div>
        </div>

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
            diagnosticData={diagnosticData}
            onOpenDiagnostics={() => setDiagnosticOpen(true)}
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
              diagnosticSummary={getDiagnosticSummary()}
              onOpenDiagnostics={() => setDiagnosticOpen(true)}
            />

            <ActivityMonitor
              logs={logs}
              setLogs={setLogs}
              connectionStatus={connectionStatus}
              autoControllerEnabled={autoControllerEnabled}
              showDiagnosticLogs={true}
            />

            {metricsHistory.length > 5 && (
              <PerformanceChart
                metricsHistory={metricsHistory}
                controllerStatus={controllerStatus}
                networkMode={topology.controllers?.length > 0 ? 'OpenFlow' : 'Learning Bridge'}
                diagnosticData={diagnosticData.historicalPings || []}
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
          diagnosticData={diagnosticData}
          onOpenDiagnostics={() => setDiagnosticOpen(true)}
        />
      </main>

      {/* Network Diagnostic Modal */}
      <NetworkDiagnostic
        isOpen={diagnosticOpen}
        onClose={() => setDiagnosticOpen(false)}
        apiCall={apiCall}
        addLog={addLog}
        networkStatus={networkStatus}
        controllerStatus={controllerStatus}
        topology={topology}
        networkMetrics={networkMetrics}
        diagnosticData={diagnosticData}
        diagnosticLoading={diagnosticLoading}
        diagnosticErrors={diagnosticErrors}
        fetchNetworkHealth={fetchNetworkHealth}
        diagnoseConnectivity={diagnoseConnectivity}
        fetchArpTables={fetchArpTables}
        fetchRoutingTables={fetchRoutingTables}
        fetchSwitchFlows={fetchSwitchFlows}
        runDetailedPing={runDetailedPing}
        runTraceRoute={runTraceRoute}
        fixCommonIssues={fixCommonIssues}
        runComprehensiveTest={runComprehensiveTest}
        resetDiagnosticData={resetDiagnosticData}
      />

      {/* Enhanced Status Footer with Diagnostic Info */}
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
            
            {/* Diagnostic Status */}
            {(() => {
              const summary = getDiagnosticSummary();
              if (summary.hasData) {
                return (
                  <div className="flex items-center gap-2 cursor-pointer" onClick={() => setDiagnosticOpen(true)}>
                    <div className={`w-2 h-2 rounded-full ${
                      summary.overallStatus === 'healthy' ? 'bg-green-500' :
                      summary.overallStatus === 'warning' ? 'bg-yellow-500' : 'bg-red-500'
                    }`} />
                    <span>Health: {summary.overallStatus}</span>
                    {summary.issuesCount > 0 && (
                      <span className="bg-red-100 text-red-600 px-1 rounded text-xs">
                        {summary.issuesCount} issues
                      </span>
                    )}
                  </div>
                );
              }
              return null;
            })()}
            
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
            
            {/* Quick diagnostic button */}
            <button
              onClick={() => setDiagnosticOpen(true)}
              className="text-blue-600 hover:text-blue-800 underline flex items-center gap-1"
              title="Open Network Diagnostics"
            >
              <Activity className="w-3 h-3" />
              Diagnostics
            </button>
          </div>
        </div>
      </footer>

      {/* Enhanced Styles */}
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
        
        /* Diagnostic-specific animations */
        @keyframes diagnostic-pulse {
          0%, 100% { 
            background-color: rgb(239 68 68); 
            transform: scale(1);
          }
          50% { 
            background-color: rgb(220 38 38); 
            transform: scale(1.05);
          }
        }
        
        .diagnostic-alert {
          animation: diagnostic-pulse 2s ease-in-out infinite;
        }
        
        .diagnostic-badge {
          position: relative;
          overflow: visible;
        }
        
        .diagnostic-badge::after {
          content: '';
          position: absolute;
          top: -2px;
          right: -2px;
          width: 8px;
          height: 8px;
          background: rgb(239 68 68);
          border: 2px solid white;
          border-radius: 50%;
          animation: pulse 2s ease-in-out infinite;
        }
        
        /* Diagnostic widget animations */
        .diagnostic-widget {
          transition: all 0.3s ease-in-out;
          transform: translateY(0);
        }
        
        .diagnostic-widget:hover {
          transform: translateY(-2px);
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        
        /* Health status indicators */
        .health-healthy {
          background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
          border-color: #16a34a;
        }
        
        .health-warning {
          background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
          border-color: #d97706;
        }
        
        .health-critical {
          background: linear-gradient(135deg, #fee2e2 0%, #fecaca 100%);
          border-color: #dc2626;
        }
        
        /* Modal animations */
        .diagnostic-modal {
          animation: modalSlideIn 0.3s ease-out;
        }
        
        @keyframes modalSlideIn {
          from {
            opacity: 0;
            transform: scale(0.95) translateY(-10px);
          }
          to {
            opacity: 1;
            transform: scale(1) translateY(0);
          }
        }
        
        /* Button hover effects */
        .diagnostic-button {
          transition: all 0.2s ease-in-out;
          position: relative;
          overflow: hidden;
        }
        
        .diagnostic-button::before {
          content: '';
          position: absolute;
          top: 0;
          left: -100%;
          width: 100%;
          height: 100%;
          background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
          transition: left 0.5s;
        }
        
        .diagnostic-button:hover::before {
          left: 100%;
        }
        
        /* Status indicator animations */
        .status-indicator {
          position: relative;
        }
        
        .status-indicator.active::after {
          content: '';
          position: absolute;
          top: 50%;
          left: 50%;
          width: 100%;
          height: 100%;
          border-radius: 50%;
          background: inherit;
          transform: translate(-50%, -50%);
          animation: statusPulse 2s ease-in-out infinite;
        }
        
        @keyframes statusPulse {
          0% {
            opacity: 1;
            transform: translate(-50%, -50%) scale(1);
          }
          100% {
            opacity: 0;
            transform: translate(-50%, -50%) scale(2);
          }
        }
        
        /* Diagnostic tab animations */
        .diagnostic-tab {
          transition: all 0.2s ease-in-out;
          position: relative;
        }
        
        .diagnostic-tab.active {
          background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
          transform: translateX(4px);
        }
        
        .diagnostic-tab:hover:not(.active) {
          transform: translateX(2px);
          background: rgba(0, 0, 0, 0.02);
        }
        
        /* Progress indicators */
        .diagnostic-progress {
          background: linear-gradient(90deg, #3b82f6 0%, #1d4ed8 100%);
          animation: progressSlide 2s ease-in-out infinite;
        }
        
        @keyframes progressSlide {
          0%, 100% { width: 0%; }
          50% { width: 100%; }
        }
        
        /* Widget glow effect */
        .diagnostic-widget-glow {
          box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
          border: 1px solid rgba(59, 130, 246, 0.5);
        }
        
        /* Notification badges */
        .notification-badge {
          animation: badgeBounce 0.6s ease-in-out;
        }
        
        @keyframes badgeBounce {
          0%, 20%, 50%, 80%, 100% {
            transform: translateY(0);
          }
          40% {
            transform: translateY(-3px);
          }
          60% {
            transform: translateY(-1px);
          }
        }
        
        /* Success/Error animations */
        .success-flash {
          animation: successFlash 1s ease-in-out;
        }
        
        .error-flash {
          animation: errorFlash 1s ease-in-out;
        }
        
        @keyframes successFlash {
          0%, 100% { background-color: transparent; }
          50% { background-color: rgba(34, 197, 94, 0.1); }
        }
        
        @keyframes errorFlash {
          0%, 100% { background-color: transparent; }
          50% { background-color: rgba(239, 68, 68, 0.1); }
        }
        
        /* Loading skeleton */
        .diagnostic-skeleton {
          background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
          background-size: 200% 100%;
          animation: shimmer 1.5s infinite;
        }
        
        /* Responsive adjustments */
        @media (max-width: 768px) {
          .diagnostic-widget {
            margin-bottom: 1rem;
          }
          
          .diagnostic-modal {
            margin: 1rem;
            width: calc(100% - 2rem);
            height: calc(100% - 2rem);
          }
        }
        
        /* Dark mode support (if needed) */
        @media (prefers-color-scheme: dark) {
          .diagnostic-widget {
            background: #1f2937;
            border-color: #374151;
            color: #f9fafb;
          }
          
          .diagnostic-modal {
            background: #1f2937;
            color: #f9fafb;
          }
        }
        
        /* High contrast mode support */
        @media (prefers-contrast: high) {
          .diagnostic-button {
            border: 2px solid currentColor;
          }
          
          .status-indicator {
            border: 2px solid #000;
          }
        }
        
        /* Reduced motion support */
        @media (prefers-reduced-motion: reduce) {
          * {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
          }
        }
      `}</style>
    </div>
  );
};

export default MininetVisualizer;