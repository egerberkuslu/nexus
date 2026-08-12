// components/NetworkDiagnostic/panels/NetworkHealthPanel.jsx
import React from 'react';
import {
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Zap,
  Monitor
} from 'lucide-react';
import StatusBadge from '../StatusBadgeLegacy.jsx';
import ActionButton from '../ActionButton.jsx';

const NetworkHealthPanel = ({
  diagnosticData,
  diagnosticLoading,
  diagnosticErrors,
  fetchNetworkHealth
}) => {
  const health = diagnosticData.networkHealth;

  if (!health) return null;

  return (
    <section className="flex flex-col h-full bg-white">
      {/* Sticky Header */}
      <header className="sticky top-0 z-10 flex items-center justify-between bg-white px-6 py-4 border-b border-gray-200">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Network Health Overview</h2>
          <p className="text-sm text-gray-500">Full system status & recommendations</p>
        </div>
        <ActionButton
          onClick={fetchNetworkHealth}
          loading={diagnosticLoading.health}
          icon={<Monitor className="w-5 h-5" />}
          label="Refresh"
          color="indigo"
          size="sm"
        />
      </header>

      {/* Scrollable Body */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        {/* Error */}
        {diagnosticErrors.health && (
          <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg">
            <XCircle className="w-5 h-5 text-red-500" />
            <span className="text-red-700">{diagnosticErrors.health}</span>
          </div>
        )}

        {/* Summary Badges */}
        <div className="flex flex-wrap gap-3">
          <StatusBadge
            status={health.overall_status === 'healthy'}
            text={`Overall: ${health.overall_status.toUpperCase()}`}
          />
          <StatusBadge
            status={health.network_running}
            text={`Network Running: ${health.network_running ? 'YES' : 'NO'}`}
          />
          <StatusBadge
            status={health.controller_running}
            text={`Controller Running: ${health.controller_running ? 'YES' : 'NO'}`}
          />
        </div>

        {/* Component Status */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(health.components || {}).map(([name, status]) => (
            <div
              key={name}
              className="p-4 bg-gray-50 border border-gray-200 rounded-lg hover:shadow-sm transition"
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="capitalize font-medium text-gray-800">{name}</h4>
                <StatusBadge status={status === 'healthy'} text={status.toUpperCase()} />
              </div>
              <div className="flex items-center gap-2">
                {status === 'healthy' ? (
                  <CheckCircle className="w-5 h-5 text-green-500" />
                ) : status === 'warning' ? (
                  <AlertTriangle className="w-5 h-5 text-yellow-500" />
                ) : (
                  <XCircle className="w-5 h-5 text-red-500" />
                )}
                <span className="text-sm text-gray-600">
                  {status === 'healthy'
                    ? 'Operating normally'
                    : status === 'warning'
                    ? 'Needs attention'
                    : 'Critical issue'}
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* Connectivity Tests */}
        <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
          <h5 className="mb-3 font-medium text-gray-800">Connectivity Tests</h5>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {Object.entries(health.connectivity_tests || {}).map(([test, res]) => (
              <div
                key={test}
                className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg"
              >
                <span className="capitalize text-gray-700 text-sm">
                  {test.replace(/_/g, ' ')}
                </span>
                <div className="flex items-center gap-1">
                  {res === 'pass' ? (
                    <CheckCircle className="w-4 h-4 text-green-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                  <span className={`text-xs font-semibold ${res === 'pass' ? 'text-green-600' : 'text-red-600'}`}>
                    {res.toUpperCase()}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Issues */}
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
          <h5 className="mb-3 flex items-center gap-2 font-medium text-red-800">
            <AlertTriangle className="w-5 h-5" />
            Issues Found ({health.issues?.length || 0})
          </h5>
          <ul className="space-y-2">
            {(health.issues || []).map((issue, i) => (
              <li key={i} className="flex items-start gap-2 bg-white p-3 border border-red-200 rounded-lg">
                <AlertTriangle className="w-4 h-4 text-red-500 mt-1" />
                <span className="text-sm text-red-700">{issue}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Recommendations */}
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <h5 className="mb-3 flex items-center gap-2 font-medium text-blue-800">
            <Zap className="w-5 h-5" />
            Recommendations ({health.recommendations?.length || 0})
          </h5>
          <ul className="space-y-2">
            {(health.recommendations || []).map((rec, i) => (
              <li key={i} className="flex items-start gap-2 bg-white p-3 border border-blue-200 rounded-lg">
                <Zap className="w-4 h-4 text-blue-500 mt-1" />
                <span className="text-sm text-blue-700">{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
};

export default NetworkHealthPanel;
