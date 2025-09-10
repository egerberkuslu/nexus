import React, { useState, useEffect, useCallback } from 'react';
import {
  Wifi,
  WifiOff,
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
  Wrench,
  Settings,
  X,
  Monitor,
  Server,
  Layers,
  Play,
  Square,
  Info,
  Database,
  Save,
  FolderOpen
} from 'lucide-react';

// Core Components
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

// Advanced Components
import NetworkConfigurationManager from './components/NetworkConfigurationManager/index';
import PerformanceManager from './components/PerformanceManager';
import PerformanceWidget from './components/PerformanceManager/PerformanceWidget';
import SimulationSnapshots from './components/SimulationSnapshots';
import SnapshotsWidget from './components/SimulationSnapshots/SnapshotsWidget';
import StorageManager from './components/StorageManager';
import LLMConfigurationManager from './components/LLMConfigurationManager';
import ErrorBoundary from './components/ErrorBoundary';

// Hooks
import { useApiCall } from './hooks/useApiCall';
import { useNetworkData } from './hooks/useNetworkData';
import { useControllerData } from './hooks/useControllerData';
import { useTopologyData } from './hooks/useTopologyData';
import { useDiagnostic } from './hooks/useDiagnostic';
import { useSwitchData } from './hooks/useSwitchData';
import { usePerformanceData } from './hooks/usePerformanceData';
import { useSnapshotData } from './hooks/useSnapshotData';
import { useStorageData } from './hooks/useStorageData';

// Utils
import { formatBytes } from './utils/formatters';

// Styles
import './App.css';

const MininetVisualizer = () => {
  // ============================================================================
  // STATE MANAGEMENT
  // ============================================================================

  // Core Network State
  const [networkStatus, setNetworkStatus] = useState({ 
    running: false, 
    network_exists: false 
  });
  
  const [controllerStatus, setControllerStatus] = useState({ 
    running: false, 
    app: null 
  });
  
  const [topology, setTopology] = useState({
    nodes: [],
    links: [],
    controllers: [],
    stats: {}
  });



  // Network Metrics
  const [networkMetrics, setNetworkMetrics] = useState({
    uptime: '00:00:00',
    packets_transferred: 0,
    total_bytes: 0,
    bandwidth_mbps: 0.0,
    latency_ms: 0.0,
    active_flows: 0,
    total_interfaces: 0
  });

  // UI State
  const [loading, setLoading] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState('connected');
  const [refreshRate, setRefreshRate] = useState(3000);

  // Logs and Communication
  const [logs, setLogs] = useState([]);

  // Host Terminal State
  const [selectedHost, setSelectedHost] = useState('');
  const [command, setCommand] = useState('');

  // Controller State
  const [ryuApp, setRyuApp] = useState('simple_switch_13');
  const [controllerType, setControllerType] = useState('ryu');
  const [availableApps, setAvailableApps] = useState([]);
  const [controllerLogs, setControllerLogs] = useState([]);
  const [controllerConfig, setControllerConfig] = useState({});
  const [controllerStats, setControllerStats] = useState({});
  const [autoControllerEnabled, setAutoControllerEnabled] = useState(true);
  const [controllerWarning, setControllerWarning] = useState(false);

  // Network Visualization State
  const [hoveredNode, setHoveredNode] = useState(null);
  const [dragPositions, setDragPositions] = useState({});

  // Advanced Features State
  const [detailedStats, setDetailedStats] = useState({});
  const [interfaceStats, setInterfaceStats] = useState({});
  const [flowStats, setFlowStats] = useState({});
  const [metricsHistory, setMetricsHistory] = useState([]);
  const [pingResults, setPingResults] = useState(null);

  // Modal States
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [configSelectedNode, setConfigSelectedNode] = useState(null);
  const [configActiveTab, setConfigActiveTab] = useState('overview');
  const [showStorageManager, setShowStorageManager] = useState(true);

  const [showPerformanceManager, setShowPerformanceManager] = useState(false);
  const [performanceManagerMinimized, setPerformanceManagerMinimized] = useState(false);

  const [diagnosticOpen, setDiagnosticOpen] = useState(false);
  const [showDiagnosticBadge, setShowDiagnosticBadge] = useState(false);
  const [diagnosticWidgetVisible, setDiagnosticWidgetVisible] = useState(true);

  const [snapshotsOpen, setSnapshotsOpen] = useState(false);
  const [showLLMConfig, setShowLLMConfig] = useState(false);

  // ============================================================================
  // HOOKS
  // ============================================================================

  // API Communication Hook
  const { apiCall, addLog } = useApiCall(setConnectionStatus, setLogs);

  // Network Data Management Hook
  const {
    fetchNetworkMetrics,
    fetchDetailedStats,
    fetchStatus,
    fetchTopology,
    addTopologyNode,
    removeTopologyNode,
    addTopologyLink,
    removeTopologyLink,
    // Property update functions
    updateNodeIP,
    updateLinkBandwidth,
    updateLinkStatus,
    updateControllerPort,
    refreshTopology,
    createNetwork: baseCreateNetwork,
    startNetwork: baseStartNetwork,
    stopNetwork,
    deleteNetwork,
    runPingTest: baseRunPingTest,
    executeCommand,
    createPredefinedTopology
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

  // Controller Management Hook
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
    switchControllerType,
    clearControllerLogs,
    CONTROLLER_TYPES
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

  // Topology Management Hook
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

  // Network Diagnostics Hook
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

  // Switch Management Hook
  const {
    fetchAvailableSwitchTypes,
    fetchSwitchTemplates,
    fetchSwitchStatus,
    createSwitch,
    configureSwitch,
    fetchSwitchStats,
    addSwitchFlow,
    deleteSwitchFlows,
    configureP4Program,
    getSwitchConfigOptions,
    deleteSwitch,
    SWITCH_TYPES
  } = useSwitchData({
    apiCall,
    addLog,
    setLoading
  });

  // Performance Monitoring Hook
  const {
    fetchPerformanceMetrics,
    runPerformanceTest,
    generatePerformanceReport,
    checkNetworkHealth: checkPerformanceHealth,
    getBandwidthUtilization,
    measureLatency
  } = usePerformanceData({
    apiCall,
    addLog,
    setPerformanceMetrics: (metrics) => setNetworkMetrics(prev => ({ ...prev, ...metrics })),
    setPerformanceHistory: (history) => setMetricsHistory(history),
    setLoading
  });

  // Snapshot Management Hook
  const {
    fetchSnapshots,
    createSnapshot,
    restoreSnapshot,
    deleteSnapshot,
    exportSnapshot,
    importSnapshot,
    getSnapshotDetails,
    compareSnapshots
  } = useSnapshotData({
    apiCall,
    addLog,
    setSnapshots: (snapshots) => {
      // Update snapshots in topology data
      setTopology(prev => ({ ...prev, snapshots }));
    },
    setLoading,
    refreshTopology: fetchTopology  // Pass fetchTopology to refresh topology after restoration
  });

  // Storage/Database Management Hook
  const {
    fetchTopologies: fetchStoredTopologies,
    saveTopology: saveTopologyToDB,
    loadTopology: loadTopologyFromDB,
    deleteTopology: deleteTopologyFromDB,
    fetchConfigurations,
    saveConfiguration,
    loadConfiguration,
    deleteConfiguration,
    exportData,
    importData,
    searchData
  } = useStorageData({
    apiCall,
    addLog,
    setTopologies: (topologies) => {
      // Update saved topologies
      setTopology(prev => ({ ...prev, savedTopologies: topologies }));
    },
    setConfigurations: (configs) => {
      // Update saved configurations
      setTopology(prev => ({ ...prev, savedConfigurations: configs }));
    },
    setLoading
  });

  // ============================================================================
  // UI COMPONENT BUILDERS
  // ============================================================================

  // Diagnostic Button with Dynamic Styling
  const DiagnosticButton = useCallback(() => {
    const summary = getDiagnosticSummary();

    return (
      <button
        onClick={() => setDiagnosticOpen(true)}
        className={`relative flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all transform hover:scale-105 ${
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
        title="Open Network Diagnostics (Ctrl+D)"
      >
        <Activity className="w-5 h-5" />
        <span>Diagnostics</span>

        {/* Issue Count Badge */}
        {summary.issuesCount > 0 && (
          <span className="absolute -top-2 -right-2 bg-red-500 text-white text-xs rounded-full w-6 h-6 flex items-center justify-center font-bold animate-bounce">
            {summary.issuesCount > 9 ? '9+' : summary.issuesCount}
          </span>
        )}

        {/* Health Indicator Dot */}
        <div className={`w-2 h-2 rounded-full ${
          summary.overallStatus === 'healthy' ? 'bg-green-500' :
          summary.overallStatus === 'warning' ? 'bg-yellow-500' :
          summary.overallStatus === 'critical' ? 'bg-red-500' : 'bg-gray-400'
        }`} />
      </button>
    );
  }, [getDiagnosticSummary, showDiagnosticBadge]);

  // ============================================================================
  // ENHANCED NETWORK OPERATIONS
  // ============================================================================

  // Enhanced Network Creation with Auto-controller Detection
  const createNetwork = useCallback(async (topologyData = null) => {
    setLoading(true);
    try {
      const result = await baseCreateNetwork(topologyData);
      if (result) {
        await fetchTopology();
        setDiagnosticWidgetVisible(true);
        addLog('🚀 Network created successfully', 'success', 'network');
      }
      return result;
    } catch (error) {
      addLog(`❌ Failed to create network: ${error.message}`, 'error', 'network');
      return false;
    } finally {
      setLoading(false);
    }
  }, [baseCreateNetwork, fetchTopology, addLog]);

  // Enhanced Network Start with Intelligent Controller Management
  const startNetwork = useCallback(async () => {
    setLoading(true);
    setControllerWarning(false);

    try {
      const hasControllerNodes = topology.controllers && topology.controllers.length > 0;

      // Auto-start controller for OpenFlow topologies
      if (hasControllerNodes && !controllerStatus.running && autoControllerEnabled) {
        addLog('🔄 OpenFlow topology detected - starting controller automatically...', 'info', 'controller');

        const controllerStarted = await startController(ryuApp);

        if (controllerStarted) {
          addLog('✅ Controller started successfully', 'success', 'controller');
          await new Promise(resolve => setTimeout(resolve, 3000));
        } else {
          addLog('⚠️ Failed to start controller - network may not function properly', 'warning', 'controller');
          setControllerWarning(true);
        }
      }

      // Start the network
      const result = await baseStartNetwork();

      if (result) {
        addLog('🌐 Network started successfully', 'success', 'network');
        
        if (hasControllerNodes) {
          addLog('🔗 Waiting for switches to connect to controller...', 'info', 'network');
          await new Promise(resolve => setTimeout(resolve, 2000));

          // Verify controller connections
          setTimeout(async () => {
            await fetchControllerStats();
            await fetchTopology();
            setTimeout(quickDiagnosticCheck, 5000);
          }, 3000);
        }
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

  // Enhanced Ping Test with Smart Analysis
  const runPingTest = useCallback(async () => {
    setLoading(true);

    try {
      const hasControllerNodes = topology.controllers && topology.controllers.length > 0;

      if (hasControllerNodes && !controllerStatus.running) {
        addLog('⚠️ Warning: Running ping test without active controller on OpenFlow network', 'warning', 'network');
      }

      const result = await baseRunPingTest();
      setPingResults(result);

      if (result.success) {
        const lossPercent = parseInt(result.packet_loss);
        
        if (lossPercent === 100 && hasControllerNodes && !controllerStatus.running) {
          addLog('💡 100% packet loss detected. Try starting the controller first for OpenFlow networks.', 'info', 'network');
          setControllerWarning(true);
          setTimeout(() => setDiagnosticOpen(true), 1000);
        } else if (lossPercent === 0) {
          addLog('🎉 Perfect connectivity - 0% packet loss!', 'success', 'network');
        } else if (lossPercent < 50) {
          addLog(`✅ Good connectivity - ${lossPercent}% packet loss`, 'success', 'network');
        } else {
          addLog(`⚠️ Poor connectivity - ${lossPercent}% packet loss`, 'warning', 'network');
          setTimeout(() => setDiagnosticOpen(true), 1000);
        }
      }

      return result;
    } catch (error) {
      addLog(`❌ Ping test failed: ${error.message}`, 'error', 'network');
      return null;
    } finally {
      setLoading(false);
    }
  }, [baseRunPingTest, topology.controllers, controllerStatus.running, addLog]);

  // Quick Diagnostic Check
  const quickDiagnosticCheck = useCallback(async () => {
    if (!networkStatus.running) return;

    addLog('🔍 Running quick diagnostic check...', 'info', 'diagnostic');
    const health = await fetchNetworkHealth();

    if (health && health.overall_status !== 'healthy') {
      setShowDiagnosticBadge(true);
      addLog(`⚠️ Network issues detected: ${health.overall_status}`, 'warning', 'diagnostic');
    } else {
      addLog('✅ Network health check passed', 'success', 'diagnostic');
    }
  }, [networkStatus.running, fetchNetworkHealth, addLog]);

  // ============================================================================
  // MODAL HANDLERS
  // ============================================================================

  // Configuration Modal Handlers
  const handleOpenConfigForNode = useCallback((node, tab = 'overview') => {
    setConfigSelectedNode(node);
    setConfigActiveTab(tab);
    setShowConfigModal(true);
  }, []);

  // Storage Manager Handlers
  const handleOpenStorageManager = useCallback(() => {
    setShowStorageManager(true);
  }, []);

  const handleLoadTopology = useCallback((loadedTopology) => {
    // Refresh topology data after loading
    fetchTopology();
    addLog(`Topology "${loadedTopology.name}" loaded successfully`, 'success');
  }, [fetchTopology, addLog]);

  const handleLoadConfiguration = useCallback((config) => {
    // Handle loading configuration into the UI
    addLog(`Configuration "${config.name}" loaded for ${config.device_type}`, 'success');
    // You could open the config modal with the loaded configuration
    setShowConfigModal(true);
    setConfigActiveTab(config.device_type);
  }, [addLog]);

  const handleCloseConfigModal = useCallback(() => {
    setShowConfigModal(false);
    setConfigSelectedNode(null);
    setConfigActiveTab('overview');
    setTimeout(() => {
      fetchStatus();
      fetchTopology();
      fetchControllerStatus();
    }, 1000);
  }, [fetchStatus, fetchTopology, fetchControllerStatus]);

  // Performance Manager Handlers
  const handleOpenPerformanceManager = useCallback(() => {
    setShowPerformanceManager(true);
    setPerformanceManagerMinimized(false);
  }, []);

  const handleClosePerformanceManager = useCallback(() => {
    setShowPerformanceManager(false);
    setPerformanceManagerMinimized(false);
  }, []);

  // ============================================================================
  // TOPOLOGY OPERATIONS
  // ============================================================================

  const handleCreateCustomTopology = useCallback(async (topologyConfig) => {
    const validation = validateTopology(topologyConfig);

    if (!validation.isValid) {
      addLog(`❌ Topology validation failed: ${validation.errors.join(', ')}`, 'error', 'topology');
      return false;
    }

    if (validation.warnings.length > 0) {
      addLog(`⚠️ Topology warnings: ${validation.warnings.join(', ')}`, 'warning', 'topology');
    }

    const success = await createCustomTopology(topologyConfig);

    if (success) {
      await Promise.all([fetchStatus(), fetchTopology()]);

      const hasControllerNodes = topologyConfig.nodes?.some(node => node.type === 'controller');
      if (hasControllerNodes) {
        addLog('ℹ️ OpenFlow topology created. Controller will auto-start when network starts.', 'info', 'topology');
      }
    }

    return success;
  }, [createCustomTopology, validateTopology, addLog, fetchStatus, fetchTopology]);

  const handleSaveTopology = useCallback((topologyConfig) => {
    const validation = validateTopology(topologyConfig);

    if (!validation.isValid) {
      addLog(`❌ Cannot save invalid topology: ${validation.errors.join(', ')}`, 'error', 'topology');
      return null;
    }

    return saveTopology(topologyConfig);
  }, [saveTopology, validateTopology, addLog]);

  // ============================================================================
  // EFFECTS
  // ============================================================================

  // Initialize all data sources
  useEffect(() => {
    const initializeData = async () => {
      try {
        // Load saved topologies from database
        await fetchStoredTopologies();
        await fetchConfigurations();

        // Fetch available switch types from backend
        await fetchAvailableSwitchTypes();

        // Load snapshots
        await fetchSnapshots();

        addLog('📊 All data sources initialized successfully', 'success', 'system');
      } catch (error) {
        addLog(`❌ Error initializing data sources: ${error.message}`, 'error', 'system');
      }
    };

    initializeData();
  }, []);

  // Main data fetching and interval management
  useEffect(() => {
    // Initial data fetch
    Promise.all([
      fetchStatus(),
      fetchTopology(),
      fetchControllerStatus(),
      fetchAvailableApps(),
      fetchControllerConfig()
    ]);

    // Real-time update intervals
    const statusInterval = setInterval(() => {
      fetchStatus();
      fetchControllerStatus();
    }, refreshRate);

    const metricsInterval = setInterval(() => {
      if (networkStatus.running) {
        fetchNetworkMetrics();
        fetchPerformanceMetrics(); // Fetch performance metrics
        // Stop polling topology continuously; it's fetched on init and after updates
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
  }, [networkStatus.running, controllerStatus.running, refreshRate]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'p' && !e.shiftKey) {
        e.preventDefault();
        setShowPerformanceManager(true);
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'C') {
        e.preventDefault();
        setShowConfigModal(true);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
        e.preventDefault();
        setDiagnosticOpen(true);
      }
    };

    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, []);

  // Monitor for controller warnings
  useEffect(() => {
    const hasControllerNodes = topology.controllers && topology.controllers.length > 0;
    const shouldWarn = hasControllerNodes && !controllerStatus.running && networkStatus.running;
    setControllerWarning(shouldWarn);
  }, [topology.controllers, controllerStatus.running, networkStatus.running]);

  // Monitor for diagnostic badges
  useEffect(() => {
    const hasControllerIssues = topology.controllers?.length > 0 && !controllerStatus.running && networkStatus.running;
    const hasPingFailures = pingResults && parseInt(pingResults.packet_loss) > 50;
    const hasNetworkIssues = !networkStatus.running && networkStatus.network_exists;

    setShowDiagnosticBadge(hasControllerIssues || hasPingFailures || hasNetworkIssues);
  }, [topology.controllers, controllerStatus.running, networkStatus, pingResults]);

  // ============================================================================
  // UTILITY FUNCTIONS
  // ============================================================================

  const calculateTrend = (current, history, key) => {
    if (history.length < 2) return 0;
    const previous = history[history.length - 2][key] || 0;
    if (previous === 0) return 0;
    return ((current - previous) / previous) * 100;
  };

  const bandwidthTrend = calculateTrend(networkMetrics.bandwidth_mbps, metricsHistory, 'bandwidth_mbps');
  const latencyTrend = calculateTrend(networkMetrics.latency_ms, metricsHistory, 'latency_ms');
  const packetTrend = calculateTrend(networkMetrics.packets_transferred, metricsHistory, 'packets_transferred');

  // ============================================================================
  // RENDER
  // ============================================================================

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
      {/* Header */}
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
        extraActions={
          <button
            onClick={() => setShowLLMConfig(true)}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg hover:from-purple-700 hover:to-indigo-700 transition-all duration-200 shadow-lg hover:shadow-xl transform hover:scale-105 font-medium text-sm border border-purple-500/20"
            title="Manage LLM configurations and API keys"
          >
            <Zap size={16} className="animate-pulse" />
            <span>LLM Config</span>
          </button>
        }
      />

      {/* Controller Warning Banner */}
      {controllerWarning && (
        <div className="bg-yellow-100 border-l-4 border-yellow-500 p-4 mx-4 mt-2 rounded-lg animate-fade-in">
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
            <div className="flex gap-2">
              <button
                onClick={() => setShowConfigModal(true)}
                className="bg-yellow-200 hover:bg-yellow-300 text-yellow-800 px-3 py-1 rounded text-sm font-medium flex items-center gap-2 transition-colors"
              >
                <Settings className="w-4 h-4" />
                Configure
              </button>
              <button
                onClick={() => setDiagnosticOpen(true)}
                className="bg-yellow-200 hover:bg-yellow-300 text-yellow-800 px-3 py-1 rounded text-sm font-medium flex items-center gap-2 transition-colors"
              >
                <Activity className="w-4 h-4" />
                Diagnose
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className={`${isFullscreen ? 'fixed inset-0 top-0 z-50 bg-white' : 'max-w-[95%] mx-auto px-4 py-6'}`}>
       
        {/* Metrics Dashboard */}
        <MetricsDashboard
          topology={topology}
          networkMetrics={networkMetrics}
          packetTrend={packetTrend}
          bandwidthTrend={bandwidthTrend}
          controllerStatus={controllerStatus}
          pingResults={pingResults}
          diagnosticSummary={getDiagnosticSummary()}
          onOpenDiagnostics={() => setDiagnosticOpen(true)}
          onOpenConfig={() => setShowConfigModal(true)}
          onOpenPerformanceManager={handleOpenPerformanceManager}
        />

        {/* Control Panel and Widgets */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-6">
          <div className="lg:col-span-3">
            <ControlPanel
              createNetwork={createNetwork}
              startNetwork={startNetwork}
              stopNetwork={stopNetwork}
              deleteNetwork={deleteNetwork}
              runPingTest={runPingTest}
              startController={startController}
              stopController={stopController}
              restartController={restartController}
              switchControllerApp={switchControllerApp}
              clearControllerLogs={clearControllerLogs}
              networkStatus={networkStatus}
              controllerStatus={controllerStatus}
              topology={topology}
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
              extraActions={
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowConfigModal(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                  >
                    <Settings size={16} />
                    Configure Nodes
                  </button>
                  <button
                    onClick={handleOpenStorageManager}
                    className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                  >
                    <Database size={16} />
                    Storage
                  </button>
                  <button
                    onClick={handleOpenPerformanceManager}
                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 transition-colors"
                  >
                    <Activity size={16} />
                    Performance
                  </button>
                </div>
              }
              // Live topology handlers for builder
              onAddNode={addTopologyNode}
              onRemoveNode={removeTopologyNode}
              onAddLink={addTopologyLink}
              onRemoveLink={removeTopologyLink}
              // Property update handlers
              onUpdateNodeIP={updateNodeIP}
              onUpdateLinkBandwidth={updateLinkBandwidth}
              onUpdateLinkStatus={updateLinkStatus}
              onUpdateControllerPort={updateControllerPort}
              onRefreshTopology={refreshTopology}
              fetchTopology={fetchTopology}
            />
          </div>

          {/* Sidebar Widgets */}
          <div className="lg:col-span-1">
            {diagnosticWidgetVisible && (
              <div className="space-y-4">
                {/* Diagnostic Widget */}
                <DiagnosticWidget
                  diagnosticSummary={getDiagnosticSummary()}
                  onOpenDiagnostics={() => setDiagnosticOpen(true)}
                  onRunQuickCheck={quickDiagnosticCheck}
                  loading={diagnosticLoading.health}
                />

                {/* Performance Widget */}
                <PerformanceWidget
                  apiCall={apiCall}
                  addLog={addLog}
                  onOpenPerformanceManager={handleOpenPerformanceManager}
                  networkStatus={networkStatus}
                  topology={topology}
                  className="hover:shadow-md transition-shadow"
                />

                {/* Simulation Snapshots Widget */}
                <SnapshotsWidget
                  onOpenSnapshots={() => setSnapshotsOpen(true)}
                  className="hover:shadow-md transition-shadow"
                />

                {/* Quick Configuration Widget */}
                <div className="bg-white rounded-lg p-4 border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
                  <h3 className="font-semibold text-gray-800 mb-2 flex items-center gap-2">
                    <Settings className="w-4 h-4 text-indigo-600" />
                    Quick Configuration
                  </h3>
                  <p className="text-sm text-gray-600 mb-3">
                    Configure network components and settings
                  </p>
                  <div className="space-y-2">
                    <button
                      onClick={() => setShowConfigModal(true)}
                      className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 transition-colors"
                    >
                      <Settings size={16} />
                      Open Configuration
                    </button>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        onClick={() => handleOpenConfigForNode(null, 'host')}
                        className="flex items-center justify-center gap-1 px-2 py-1 bg-blue-50 text-blue-700 rounded text-xs hover:bg-blue-100 transition-colors"
                      >
                        <Monitor size={12} />
                        Hosts
                      </button>
                      <button
                        onClick={() => handleOpenConfigForNode(null, 'switch')}
                        className="flex items-center justify-center gap-1 px-2 py-1 bg-purple-50 text-purple-700 rounded text-xs hover:bg-purple-100 transition-colors"
                      >
                        <Server size={12} />
                        Switches
                      </button>
                      <button
                        onClick={() => handleOpenConfigForNode(null, 'router')}
                        className="flex items-center justify-center gap-1 px-2 py-1 bg-green-50 text-green-700 rounded text-xs hover:bg-green-100 transition-colors"
                      >
                        <Router size={12} />
                        Routers
                      </button>
                      <button
                        onClick={() => handleOpenConfigForNode(null, 'controller')}
                        className="flex items-center justify-center gap-1 px-2 py-1 bg-red-50 text-red-700 rounded text-xs hover:bg-red-100 transition-colors"
                      >
                        <Settings size={12} />
                        Controller
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          {/* Network Visualization */}
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
            controllerType={controllerType}
            setControllerType={setControllerType}
            CONTROLLER_TYPES={CONTROLLER_TYPES}
            SWITCH_TYPES={SWITCH_TYPES}
            createNetwork={createNetwork}
            onAddNode={addTopologyNode}
            onRemoveNode={removeTopologyNode}
            onAddLink={addTopologyLink}
            onRemoveLink={removeTopologyLink}
            pingResults={pingResults}
            onExportTopology={() => exportTopologyConfig('dot')}
            onGetVisualizationData={getVisualizationData}
            diagnosticData={diagnosticData}
            onOpenDiagnostics={() => setDiagnosticOpen(true)}
            onOpenConfig={() => setShowConfigModal(true)}
            onConfigureNode={(node) => handleOpenConfigForNode(node, node.type)}
            onNodeDoubleClick={(node) => handleOpenConfigForNode(node, node.type)}
            onOpenPerformanceManager={handleOpenPerformanceManager}
          />

          {/* Secondary Content Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Host Terminal */}
            <HostTerminal
              selectedHost={selectedHost}
              setSelectedHost={setSelectedHost}
              command={command}
              setCommand={setCommand}
              executeCommand={executeCommand}
              topology={topology}
              networkStatus={networkStatus}
              loading={loading}
              onOpenConfig={() => setShowConfigModal(true)}
              onConfigureHost={(hostId) => {
                const host = topology.nodes.find(n => n.id === hostId && n.type === 'host');
                if (host) handleOpenConfigForNode(host, 'host');
              }}
            />

            {/* Statistics Panel */}
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
              onOpenConfig={() => setShowConfigModal(true)}
              onConfigureController={() => handleOpenConfigForNode(null, 'controller')}
              onOpenPerformanceManager={handleOpenPerformanceManager}
            />

            {/* Activity Monitor */}
            <ActivityMonitor
              logs={logs}
              setLogs={setLogs}
              connectionStatus={connectionStatus}
              autoControllerEnabled={autoControllerEnabled}
              showDiagnosticLogs={true}
              onOpenConfig={() => setShowConfigModal(true)}
              onOpenPerformanceManager={handleOpenPerformanceManager}
            />

            {/* Performance Chart */}
            {metricsHistory.length > 5 && (
              <PerformanceChart
                metricsHistory={metricsHistory}
                controllerStatus={controllerStatus}
                networkMode={topology.controllers?.length > 0 ? 'OpenFlow' : 'Learning Bridge'}
                diagnosticData={diagnosticData.historicalPings || []}
                onOpenConfig={() => setShowConfigModal(true)}
                onOpenPerformanceManager={handleOpenPerformanceManager}
              />
            )}

            
          </div>
        </div>

        {/* Flow Statistics */}
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
          onOpenConfig={() => setShowConfigModal(true)}
          onConfigureController={() => handleOpenConfigForNode(null, 'controller')}
          onConfigureSwitch={(switchId) => {
            const switchNode = topology.nodes.find(n => n.id === switchId && n.type === 'switch');
            if (switchNode) handleOpenConfigForNode(switchNode, 'switch');
          }}
          onOpenPerformanceManager={handleOpenPerformanceManager}
        />
      </main>

      {/* ========================================================================== */}
      {/* MODALS */}
      {/* ========================================================================== */}

      {/* Performance Manager Modal */}
      <PerformanceManager
        isOpen={showPerformanceManager}
        onClose={handleClosePerformanceManager}
        apiCall={apiCall}
        addLog={addLog}
        networkStatus={networkStatus}
        topology={topology}
        minimized={performanceManagerMinimized}
        // Enhanced performance functions
        fetchPerformanceMetrics={fetchPerformanceMetrics}
        runPerformanceTest={runPerformanceTest}
        generatePerformanceReport={generatePerformanceReport}
        checkNetworkHealth={checkPerformanceHealth}
        getBandwidthUtilization={getBandwidthUtilization}
        measureLatency={measureLatency}
      />

      {/* Network Configuration Modal */}
      {showConfigModal && (
        <div className="fixed inset-0 bg-black/30 bg-opacity-50 z-50 flex items-start justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-7xl my-8 flex flex-col max-h-[calc(100vh-4rem)]">
            <NetworkConfigurationManager
              networkStatus={networkStatus}
              controllerStatus={controllerStatus}
              topology={topology}
              selectedNode={configSelectedNode}
              activeTab={configActiveTab}
              apiCall={apiCall}
              addLog={addLog}
              fetchStatus={fetchStatus}
              fetchTopology={fetchTopology}
              fetchControllerStatus={fetchControllerStatus}
              executeCommand={executeCommand}
              startController={startController}
              stopController={stopController}
              restartController={restartController}
              switchControllerApp={switchControllerApp}
              switchControllerType={switchControllerType}
              availableApps={availableApps}
              controllerConfig={controllerConfig}
              controllerType={controllerType}
              setControllerType={setControllerType}
              setControllerApp={setRyuApp}
              CONTROLLER_TYPES={CONTROLLER_TYPES}
              SWITCH_TYPES={SWITCH_TYPES}
              // Switch management functions
              createSwitch={createSwitch}
              configureSwitch={configureSwitch}
              deleteSwitch={deleteSwitch}
              addSwitchFlow={addSwitchFlow}
              deleteSwitchFlows={deleteSwitchFlows}
              configureP4Program={configureP4Program}
              // Performance monitoring functions
              runPerformanceTest={runPerformanceTest}
              generatePerformanceReport={generatePerformanceReport}
              measureLatency={measureLatency}
              // Snapshot management functions
              createSnapshot={createSnapshot}
              restoreSnapshot={restoreSnapshot}
              deleteSnapshot={deleteSnapshot}
              exportSnapshot={exportSnapshot}
              // Storage management functions
              saveTopologyToDB={saveTopologyToDB}
              loadTopologyFromDB={loadTopologyFromDB}
              deleteTopologyFromDB={deleteTopologyFromDB}
              saveConfiguration={saveConfiguration}
              loadConfiguration={loadConfiguration}
              deleteConfiguration={deleteConfiguration}
              onNetworkChange={() => {
                fetchStatus();
                fetchTopology();
                fetchControllerStatus();
                fetchNetworkMetrics();
                addLog('🔄 Network configuration updated - refreshing data...', 'info', 'config');
              }}
              onClose={handleCloseConfigModal}
              onNodeSelect={(node) => setConfigSelectedNode(node)}
              onTabChange={(tab) => setConfigActiveTab(tab)}
              isModal={true}
              compactMode={true}
              hideHeader={true}
              showQuickActions={true}
              // Add incremental topology operation functions
              onAddNode={addTopologyNode}
              onRemoveNode={removeTopologyNode}
              onAddLink={addTopologyLink}
              onRemoveLink={removeTopologyLink}
              // Creation functions
              createNetwork={baseCreateNetwork}
              createCustomTopology={createCustomTopology}
              createPredefinedTopology={createPredefinedTopology}
            />
          </div>
        </div>
      )}

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
        onOpenConfig={() => setShowConfigModal(true)}
        onConfigureNode={(node) => {
          setDiagnosticOpen(false);
          setTimeout(() => handleOpenConfigForNode(node, node.type), 300);
        }}
        onOpenPerformanceManager={() => {
          setDiagnosticOpen(false);
          setTimeout(handleOpenPerformanceManager, 300);
        }}
      />

      {/* ========================================================================== */}
      {/* FOOTER */}
      {/* ========================================================================== */}

      <footer className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-sm border-t border-gray-200 px-4 py-2 z-40">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <div className="flex items-center gap-4">
            {/* API Status */}
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full status-indicator ${
                connectionStatus === 'connected' ? 'bg-green-500 active' :
                connectionStatus === 'connecting' ? 'bg-yellow-500' : 'bg-red-500'
              }`} />
              <span>API {connectionStatus}</span>
            </div>

            {/* Network Status */}
            <div className="flex items-center gap-2">
              {networkStatus.running ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              <span>Network {networkStatus.running ? 'Active' : 'Inactive'}</span>
            </div>

            {/* Controller Status */}
            {topology.controllers?.length > 0 && (
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full status-indicator ${
                  controllerStatus.running ? 'bg-blue-500 active' : 'bg-gray-400'
                }`} />
                <span>Controller {controllerStatus.running ? 'Running' : 'Stopped'}</span>
              </div>
            )}

            {/* Configuration Status */}
            <div className="flex items-center gap-2">
              <Settings className="w-3 h-3" />
              <button
                onClick={() => setShowConfigModal(true)}
                className="hover:text-indigo-600 underline transition-colors"
              >
                Configuration
              </button>
            </div>

            {/* Performance Status */}
            <div className="flex items-center gap-2">
              <Activity className="w-3 h-3" />
              <button
                onClick={handleOpenPerformanceManager}
                className="hover:text-blue-600 underline transition-colors"
              >
                Performance Manager
              </button>
            </div>

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
                      <span className="bg-red-100 text-red-600 px-1 rounded text-xs notification-badge">
                        {summary.issuesCount} issues
                      </span>
                    )}
                  </div>
                );
              }
              return null;
            })()}

            {/* Auto-Controller Indicator */}
            {autoControllerEnabled && (
              <div className="flex items-center gap-1 text-blue-600">
                <span>🤖</span>
                <span>Auto-Controller</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-4">
            <span>Refresh: {refreshRate / 1000}s</span>
            <span>Nodes: {topology.nodes?.length || 0}</span>
            <span>Links: {topology.links?.length || 0}</span>
            {networkStatus.running && (
              <span>Uptime: {networkMetrics.uptime}</span>
            )}

            {/* Quick Access Buttons */}
            <button
              onClick={() => setDiagnosticOpen(true)}
              className="text-blue-600 hover:text-blue-800 underline flex items-center gap-1 transition-colors"
              title="Open Network Diagnostics (Ctrl+D)"
            >
              <Activity className="w-3 h-3" />
              Diagnostics
            </button>

            <button
              onClick={() => setShowConfigModal(true)}
              className="text-indigo-600 hover:text-indigo-800 underline flex items-center gap-1 transition-colors"
              title="Open Network Configuration (Ctrl+Shift+C)"
            >
              <Settings className="w-3 h-3" />
              Configure
            </button>

            <button
              onClick={handleOpenPerformanceManager}
              className="text-purple-600 hover:text-purple-800 underline flex items-center gap-1 transition-colors"
              title="Open Performance Manager (Ctrl+P)"
            >
              <Activity className="w-3 h-3" />
              Performance
            </button>

            <button
              onClick={() => setSnapshotsOpen(true)}
              className="text-orange-600 hover:text-orange-800 underline flex items-center gap-1 transition-colors"
              title="Open Simulation Snapshots (Ctrl+S)"
            >
              <Database className="w-3 h-3" />
              Snapshots
            </button>
            
            <div className={`px-2 py-1 text-xs rounded ml-2 ${snapshotsOpen ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
              Snapshots: {snapshotsOpen ? 'OPEN' : 'CLOSED'}
            </div>
          </div>
        </div>
      </footer>

      {/* Storage Manager Modal */}
      {showStorageManager && (
        <StorageManager
          onClose={() => setShowStorageManager(false)}
          currentTopology={topology}
          currentConfigurations={{}}
          onLoadTopology={handleLoadTopology}
          onLoadConfiguration={handleLoadConfiguration}
          // Enhanced storage functions
          fetchTopologies={fetchStoredTopologies}
          saveTopology={saveTopologyToDB}
          loadTopology={loadTopologyFromDB}
          deleteTopology={deleteTopologyFromDB}
          fetchConfigurations={fetchConfigurations}
          saveConfiguration={saveConfiguration}
          loadConfiguration={loadConfiguration}
          deleteConfiguration={deleteConfiguration}
          exportData={exportData}
          importData={importData}
          searchData={searchData}
        />
      )}



      {/* Simulation Snapshots Panel */}
      <SimulationSnapshots
        isOpen={snapshotsOpen}
        onClose={() => setSnapshotsOpen(false)}
        topology={topology}
        networkStatus={networkStatus}
        controllerStatus={controllerStatus}
        // Enhanced snapshot functions
        fetchSnapshots={fetchSnapshots}
        createSnapshot={createSnapshot}
        restoreSnapshot={restoreSnapshot}
        deleteSnapshot={deleteSnapshot}
        exportSnapshot={exportSnapshot}
        importSnapshot={importSnapshot}
        getSnapshotDetails={getSnapshotDetails}
        compareSnapshots={compareSnapshots}
      />

      {/* LLM Configuration Manager Modal */}
      {showLLMConfig && (
        <div className="fixed inset-0 bg-black/30 bg-opacity-50 z-50 flex items-start justify-center p-4 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-6xl my-8 flex flex-col max-h-[calc(100vh-4rem)]">
            <div className="flex items-center justify-between p-6 border-b border-gray-200">
              <h2 className="text-2xl font-bold text-gray-900">LLM Configuration Manager</h2>
              <button
                onClick={() => setShowLLMConfig(false)}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <X size={24} className="text-gray-500" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <ErrorBoundary>
                <LLMConfigurationManager />
              </ErrorBoundary>
            </div>
          </div>
        </div>
      )}

      {/* Loading Overlay */}
      {loading && (showConfigModal || showPerformanceManager || showStorageManager || snapshotsOpen || showLLMConfig) && (
        <div className="fixed inset-0 bg-black bg-opacity-30 z-60 flex items-center justify-center">
          <div className="bg-white rounded-lg p-6 flex items-center gap-3 shadow-2xl">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-600"></div>
            <span className="text-gray-700 font-medium">
              {showPerformanceManager ? 'Loading Performance Data...' : 
               showStorageManager ? 'Loading Storage Data...' : 
               snapshotsOpen ? 'Loading Snapshots...' : 
               showLLMConfig ? 'Loading LLM Configuration...' : 'Applying Configuration...'}
            </span>
          </div>
        </div>
      )}

      {/* Enhanced Styles */}
      <style jsx>{`
        /* Custom Scrollbar */
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
        
        /* Animations */
        @keyframes fade-in {
          from { opacity: 0; transform: translateY(-10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        
        .animate-fade-in {
          animation: fade-in 0.3s ease-out;
        }
        
        /* Status Indicators */
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
        
        /* Notification Badge */
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
        
        /* Reduced Motion */
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