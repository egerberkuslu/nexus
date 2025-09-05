// components/PerformanceManager/index.jsx
import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Activity,
  Server,
  Zap,
  Monitor,
  BarChart3,
  FileText,
  Maximize2,
  Minimize2,
  X
} from 'lucide-react';

// Sub-components
import PerformanceStatus from './components/PerformanceStatus';
import HostDiscovery from './components/HostDiscovery';
import PerformanceTests from './components/PerformanceTests';
import RealTimeMonitoring from './components/RealTimeMonitoring';
import PerformanceResults from './components/PerformanceResults';
import PerformanceReports from './components/PerformanceReports';

// Hook
import { usePerformanceAPI } from './hooks/usePerformanceAPI';

// Utils
import {
  DEFAULT_PERFORMANCE_CONFIG,
  MONITORING_INTERVALS,
  normalizeHostData
} from './utils/performanceUtils';

const DEFAULT_REALTIME_SECONDS = 10;

const PerformanceManager = ({
  isOpen,
  onClose,
  apiCall,
  addLog,
  networkStatus,
  topology,
  className = '',
  minimized = false
}) => {
  // Window state
  const [activeTab, setActiveTab] = useState('status');
  const [isMinimized, setIsMinimized] = useState(minimized);

  // Configs
  const [testConfig, setTestConfig] = useState({
    ...DEFAULT_PERFORMANCE_CONFIG.testConfig
  });

  const [monitoringConfig, setMonitoringConfig] = useState({
    ...DEFAULT_PERFORMANCE_CONFIG.monitoringConfig
  });

  // UI state
  const [selectedSession, setSelectedSession] = useState(null);
  const [filterOptions, setFilterOptions] = useState({
    testType: '',
    dateRange: 'all',
    status: 'all'
  });

  // Pass-through API (usePerformanceAPI expects apiCall(endpoint, options))
  const pmApiCall = useCallback(
    (endpoint, options) => {
      console.log(`🚀 PerformanceManager API: ${options?.method || 'GET'} ${endpoint}`);
      return apiCall(endpoint, options);
    },
    [apiCall]
  );

  // Initialize API hook
  const {
    performanceData,
    loading,
    errors,
    fetchStatus,
    fetchHosts,
    runTest,
    startMonitoring,
    stopMonitoring,
    fetchTestHistory,
    generateReport,
    refreshData,
    fetchMonitoringMetrics
  } = usePerformanceAPI(pmApiCall, addLog);

  // Defensive getters (support both top-level & nested under .status)
  const systemReady =
    Boolean(performanceData?.status?.system_ready ?? performanceData?.system_ready);
  console.log(performanceData)
  const monitoringState =
    performanceData?.monitoring ?? performanceData?.status?.monitoring ?? { active: false };

  // Normalize hosts once
  const normalizedHosts = useMemo(() => {
    const list = performanceData?.hosts ?? performanceData?.status?.hosts ?? [];
    return list.map((host) =>
      normalizeHostData({
        ...host,
        capabilities: {
          iperf3: Boolean(host.capabilities?.iperf3 ?? host.iperf3_available),
          ping: Boolean(host.capabilities?.ping ?? host.ping_available),
          netstat: Boolean(host.capabilities?.netstat ?? host.netstat_available)
        }
      })
    );
  }, [performanceData?.hosts, performanceData?.status?.hosts]);

  const totalHosts =
    performanceData?.status?.total_hosts ??
    performanceData?.total_hosts ??
    normalizedHosts.length;

  // Initial load when opened (skip only if parent explicitly says network is not running)
  useEffect(() => {
    if (!isOpen) return;
    if (networkStatus?.running === false) {
      addLog?.('ℹ️ Skipping initial load: network not running', 'info', 'performance');
      return;
    }
    console.log('🔄 PerformanceManager: Loading initial data...');
    refreshData?.();
  }, [isOpen, networkStatus?.running, refreshData, addLog]);

  // Auto-refresh real-time monitoring metrics if monitoring is active
  useEffect(() => {
    if (!monitoringState?.active) return;

    const seconds =
      monitoringState?.interval ??
      monitoringConfig?.interval ??
      MONITORING_INTERVALS?.REALTIME ??
      DEFAULT_REALTIME_SECONDS;

    console.log(`🔄 Monitoring refresh every ${seconds}s`);
    const id = setInterval(() => {
      fetchMonitoringMetrics?.();
    }, seconds * 1000);

    return () => {
      console.log('🛑 Cleaning up monitoring refresh');
      clearInterval(id);
    };
  }, [
    monitoringState?.active,
    monitoringState?.interval,
    monitoringConfig?.interval,
    fetchMonitoringMetrics
  ]);

  if (!isOpen) return null;

  const tabs = [
    { id: 'status', label: 'System Status', icon: Activity },
    { id: 'hosts', label: 'Host Discovery', icon: Server },
    { id: 'testing', label: 'Performance Tests', icon: Zap },
    { id: 'monitoring', label: 'Real-time Monitoring', icon: Monitor },
    { id: 'results', label: 'Test Results', icon: BarChart3 },
    { id: 'reports', label: 'Reports & Analysis', icon: FileText }
  ];

  return (
    <div
      className={`fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4 ${className}`}
      role="dialog"
      aria-modal="true"
      aria-label="Performance Manager"
    >
      <div
        className={`bg-white rounded-xl shadow-2xl transition-all duration-300 ${
          isMinimized ? 'w-80 h-60' : 'w-full max-w-7xl h-[90vh]'
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gradient-to-r from-gray-900 to-gray-700 text-white rounded-t-xl">
          <div className="flex items-center gap-3">
            <Activity className="w-6 h-6" />
            <h2 className="text-xl font-bold">Performance Manager</h2>
            <span
              className={`px-2 py-1 rounded-full text-xs ${
                systemReady ? 'bg-emerald-500/20 text-emerald-100' : 'bg-red-500/20 text-red-100'
              }`}
            >
              {systemReady ? 'Ready' : 'Not Ready'}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsMinimized((v) => !v)}
              className="p-2 hover:bg-white/20 rounded-lg transition-colors"
              aria-label={isMinimized ? 'Maximize' : 'Minimize'}
            >
              {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
            </button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-white/20 rounded-lg transition-colors"
              aria-label="Close"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Main */}
        {!isMinimized && (
          <>
            {/* Tabs */}
            <div className="flex border-b border-gray-200 bg-gray-50 overflow-x-auto" role="tablist">
              {tabs.map((tab) => {
                const Icon = tab.icon;
                const selected = activeTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    role="tab"
                    aria-selected={selected}
                    className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors whitespace-nowrap ${
                      selected
                        ? 'text-gray-900 border-b-2 border-gray-900 bg-white'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto" style={{ height: 'calc(90vh - 120px)' }}>
              <div className="p-6">
                {activeTab === 'status' && (
                  <PerformanceStatus
                    status={performanceData?.status ?? performanceData}
                    loading={Boolean(loading?.status)}
                    error={errors?.status}
                    onRefresh={fetchStatus}
                  />
                )}

                {activeTab === 'hosts' && (
                  <HostDiscovery
                    hosts={normalizedHosts}
                    loading={Boolean(loading?.hosts)}
                    error={errors?.hosts}
                    onRefresh={fetchHosts}
                    totalHosts={totalHosts}
                  />
                )}

                {activeTab === 'testing' && (
                  <PerformanceTests
                    hosts={normalizedHosts}
                    testConfig={testConfig}
                    setTestConfig={setTestConfig}
                    onRunTest={runTest}
                    loading={Boolean(loading?.test)}
                    error={errors?.test}
                    currentTest={performanceData?.currentTest}
                    systemReady={systemReady}
                  />
                )}

                {activeTab === 'monitoring' && (
                  <RealTimeMonitoring
                    addLog={addLog}
                    monitoring={monitoringState}
                    realTimeMetrics={performanceData?.realTimeMetrics || { metrics: {} }}
                    monitoringConfig={monitoringConfig}
                    setMonitoringConfig={setMonitoringConfig}
                    onStart={startMonitoring}
                    onStop={stopMonitoring}
                    loading={Boolean(loading?.monitoring)}
                    error={errors?.monitoring}
                    hosts={normalizedHosts}
                  />
                )}

                {activeTab === 'results' && (
                  <PerformanceResults
                    apiCall={pmApiCall}
                    addLog={addLog}
                    testHistory={performanceData?.testHistory || []}
                    selectedSession={selectedSession}
                    setSelectedSession={setSelectedSession}
                    loading={Boolean(loading?.history)}
                    error={errors?.history}
                    onRefresh={fetchTestHistory}
                    filterOptions={filterOptions}
                    setFilterOptions={setFilterOptions}
                  />
                )}

                {activeTab === 'reports' && (
                  <PerformanceReports
                    apiCall={pmApiCall}
                    addLog={addLog}
                    testHistory={performanceData?.testHistory || []}
                    loading={Boolean(loading?.report)}
                    error={errors?.report}
                    onGenerate={generateReport}
                  />
                )}
              </div>
            </div>
          </>
        )}

        {/* Minimized View */}
        {isMinimized && (
          <div className="p-4">
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{totalHosts ?? 0}</div>
                <div className="text-xs text-gray-600">Hosts</div>
              </div>
              <div className="text-center">
                <div
                  className={`text-2xl font-bold ${
                    monitoringState?.active ? 'text-emerald-600' : 'text-gray-400'
                  }`}
                >
                  {monitoringState?.active ? 'ON' : 'OFF'}
                </div>
                <div className="text-xs text-gray-600">Monitoring</div>
              </div>
            </div>

            <div className="space-y-2">
              <button
                onClick={() => {
                  setIsMinimized(false);
                  setActiveTab('testing');
                }}
                className="w-full py-2 bg-gray-900 text-white rounded-lg hover:bg-black transition-colors text-sm"
              >
                Quick Test
              </button>
              <button
                onClick={() => {
                  if (monitoringState?.active) {
                    stopMonitoring?.();
                  } else {
                    startMonitoring?.(monitoringConfig);
                  }
                }}
                className={`w-full py-2 rounded-lg transition-colors text-sm ${
                  monitoringState?.active
                    ? 'bg-red-600 hover:bg-red-700 text-white'
                    : 'bg-emerald-600 hover:bg-emerald-700 text-white'
                }`}
              >
                {monitoringState?.active ? 'Stop Monitor' : 'Start Monitor'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PerformanceManager;
