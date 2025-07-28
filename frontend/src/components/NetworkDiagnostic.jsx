// components/NetworkDiagnostic/index.jsx
import React, { useState, useEffect } from 'react';
import {
  Activity,
  XCircle,
  RefreshCw,
  Wrench
} from 'lucide-react';

// Import all components


import StatusBadge from './StatusBadge';
import ActionButton from './ActionButton';
import DiagnosticSidebar from './DiagnosticSidebar';

import NetworkHealthPanel from './panels/NetworkHealthPanel';
import ConnectivityPanel from './panels/ConnectivityPanel';
import PingTestPanel from './panels/PingTestPanel';
import ArpTablesPanel from './panels/ArpTablesPanel';
import RoutingTablesPanel from './panels/RoutingTablesPanel';
import SwitchFlowsPanel from './panels/SwitchFlowsPanel';

import { useDiagnostic } from '../hooks/useDiagnostic';

const NetworkDiagnostic = ({
  apiCall,
  addLog,
  networkStatus,
  controllerStatus,
  topology,
  networkMetrics,
  isOpen,
  onClose,
}) => {
  // Use the diagnostic hook
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
    getDiagnosticSummary
  } = useDiagnostic({ apiCall, addLog });

  const [selectedTest, setSelectedTest] = useState('health');
  const [autoRefresh, setAutoRefresh] = useState(false);

  // Get available hosts for ping tests with null safety
  const availableHosts = topology?.nodes?.filter(node =>
    ['host', 'router'].includes(node.type)
  ).map(node => node.id) || ['h1', 'h2', 'h3', 'h4'];

  // Auto-refresh effect
  useEffect(() => {
    if (!autoRefresh || !isOpen) return;

    const interval = setInterval(() => {
      handleFetchData(selectedTest);
    }, 5000);

    return () => clearInterval(interval);
  }, [autoRefresh, selectedTest, isOpen]);

  // Initial data fetch when component opens
  useEffect(() => {
    if (isOpen) {
      fetchNetworkHealth();
      diagnoseConnectivity();
    }
  }, [isOpen, fetchNetworkHealth, diagnoseConnectivity]);

  // Handle data fetching for different test types
  const handleFetchData = (testId) => {
    switch (testId) {
      case 'health':
        fetchNetworkHealth();
        break;
      case 'connectivity':
        diagnoseConnectivity();
        break;
      case 'arp':
        fetchArpTables();
        break;
      case 'routing':
        fetchRoutingTables();
        break;
      case 'flows':
        fetchSwitchFlows();
        break;
      default:
        break;
    }
  };

  if (!isOpen) return null;

  const summary = getDiagnosticSummary();

  // Render the appropriate panel based on selected test
  const renderCurrentPanel = () => {
    switch (selectedTest) {
      case 'health':
        return (
          <NetworkHealthPanel
            diagnosticData={diagnosticData}
            diagnosticLoading={diagnosticLoading}
            diagnosticErrors={diagnosticErrors}
            fetchNetworkHealth={fetchNetworkHealth}
          />
        );
      case 'connectivity':
        return (
          <ConnectivityPanel
            diagnosticData={diagnosticData}
            diagnosticLoading={diagnosticLoading}
            diagnosticErrors={diagnosticErrors}
            diagnoseConnectivity={diagnoseConnectivity}
          />
        );
      case 'ping':
        return (
          <PingTestPanel
            diagnosticData={diagnosticData}
            diagnosticLoading={diagnosticLoading}
            runDetailedPing={runDetailedPing}
            runTraceRoute={runTraceRoute}
            availableHosts={availableHosts}
          />
        );
      case 'arp':
        return (
          <ArpTablesPanel
            diagnosticData={diagnosticData}
            diagnosticLoading={diagnosticLoading}
            diagnosticErrors={diagnosticErrors}
            fetchArpTables={fetchArpTables}
          />
        );
      case 'routing':
        return (
          <RoutingTablesPanel
            diagnosticData={diagnosticData}
            diagnosticLoading={diagnosticLoading}
            diagnosticErrors={diagnosticErrors}
            fetchRoutingTables={fetchRoutingTables}
          />
        );
      case 'flows':
        return (
          <SwitchFlowsPanel
            diagnosticData={diagnosticData}
            diagnosticLoading={diagnosticLoading}
            diagnosticErrors={diagnosticErrors}
            fetchSwitchFlows={fetchSwitchFlows}
          />
        );
      default:
        return <div>Select a diagnostic test</div>;
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-7xl h-[90vh] overflow-hidden border border-gray-200">

        {/* Simplified White Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Activity className="w-6 h-6 text-gray-600" />
            <div>
              <h2 className="text-xl font-semibold text-gray-800">Network Diagnostics</h2>
              <p className="text-gray-500 text-sm">Real‑time network health overview</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <StatusBadge
              status={summary.overallStatus === 'healthy'}
              text={summary.overallStatus?.toUpperCase() || 'UNKNOWN'}
            />

            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={e => setAutoRefresh(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-indigo-300 rounded-full peer peer-checked:bg-indigo-600 transition-colors" />
              <div className="absolute left-0.5 top-0.5 w-5 h-5 bg-white rounded-full peer-checked:translate-x-5 transition-transform shadow-md" />
              <span className="ml-4 text-sm font-medium text-gray-700">Auto‑refresh</span>
            </label>


            <ActionButton
              onClick={fixCommonIssues}
              loading={diagnosticLoading.fixing}
              icon={<Wrench className="w-4 h-4 text-gray-600" />}
              label="Auto‑Fix"
              color="gray"
              size="sm"
            />

            <button
              onClick={onClose}
              className="p-1 text-gray-600 hover:text-gray-800 rounded"
            >
              <XCircle className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex h-full">
          {/* Sidebar */}
          <DiagnosticSidebar
            selectedTest={selectedTest}
            setSelectedTest={setSelectedTest}
            diagnosticLoading={diagnosticLoading}
            getDiagnosticSummary={getDiagnosticSummary}
            onFetchData={handleFetchData}
          />

          {/* Main Content */}
          <div className="flex-1 p-6 overflow-y-auto bg-white">
            {renderCurrentPanel()}
          </div>
        </div>
      </div>
    </div>
  );

};

export default NetworkDiagnostic;