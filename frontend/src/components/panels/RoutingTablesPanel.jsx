// components/NetworkDiagnostic/panels/RoutingTablesPanel.jsx
import React, { useEffect } from 'react';
import { 
  XCircle, 
  RefreshCw,
  Router as RouterIcon,
  FileText
} from 'lucide-react';
import StatusBadge from '../StatusBadgeLegacy';
import ActionButton from '../ActionButton';

const RoutingTablesPanel = ({ 
  diagnosticData, 
  diagnosticLoading, 
  diagnosticErrors, 
  fetchRoutingTables 
}) => {
  // Unwrap any envelope (e.g. { success, data, error })
  const raw = diagnosticData.routingTables;
  const routingTables = raw?.data ?? raw;

  // Auto‑fetch on mount
  useEffect(() => {
    fetchRoutingTables();
  }, [fetchRoutingTables]);

  // Loading before we have any real table
  if (diagnosticLoading.routing && !routingTables) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-indigo-500" />
        <span className="ml-3 text-gray-600">Loading routing tables…</span>
      </div>
    );
  }

  // API‑level error
  if (diagnosticErrors.routing) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-4">
        <div className="flex items-center gap-2">
          <XCircle className="w-5 h-5 text-red-500" />
          <span className="text-red-700 font-medium">
            Error loading routing tables: {diagnosticErrors.routing}
          </span>
        </div>
      </div>
    );
  }

  // No hosts at all
  if (!routingTables || Object.keys(routingTables).length === 0) {
    return (
      <div className="text-center py-12">
        <RouterIcon className="w-16 h-16 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-500 font-medium">No routing data available</p>
        <p className="text-gray-400 text-sm">Click “Refresh Routes” to load data</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold text-gray-900">Routing Tables</h3>
          <p className="text-gray-600">Network routing configuration analysis</p>
        </div>
        <ActionButton
          onClick={fetchRoutingTables}
          loading={diagnosticLoading.routing}
          icon={<RouterIcon className="w-4 h-4" />}
          label="Refresh Routes"
          color="indigo"
        />
      </div>

      {/* Per‑host cards */}
      <div className="grid gap-6">
        {Object.entries(routingTables).map(([hostId, rd]) => {
          const hasError = !!rd.error;
          const routes = rd.routes ?? [];
          const gw = rd.default_route;

          return (
            <div key={hostId} className="bg-white border-2 border-gray-200 rounded-xl p-6">
              {/* Host header */}
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-lg font-semibold text-gray-900">{hostId}</h4>
                <StatusBadge
                  status={!!gw}
                  text={gw ? `Gateway: ${gw}` : 'No default gateway'}
                />
              </div>

              {/* Error in this host’s data */}
              {hasError && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                  <div className="flex items-center gap-2">
                    <XCircle className="w-5 h-5 text-red-500" />
                    <span className="text-red-700 font-medium">{rd.error}</span>
                  </div>
                </div>
              )}

              {/* Routes list */}
              {!hasError && routes.length > 0 && (
                <div className="space-y-3 mb-4">
                  <h5 className="text-sm font-semibold text-gray-900">Route Entries:</h5>
                  {routes.map((r, i) => (
                    <div
                      key={i}
                      className="bg-gray-50 border border-gray-200 rounded-lg p-3 font-mono text-sm text-gray-700"
                    >
                      {r}
                    </div>
                  ))}
                </div>
              )}

              {/* No routes for this host */}
              {!hasError && routes.length === 0 && (
                <div className="text-center py-8 mb-4">
                  <RouterIcon className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-500 font-medium">No routes found</p>
                </div>
              )}

              {/* Raw CLI output */}
              {rd.raw && (
                <details className="mt-4">
                  <summary className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer hover:text-gray-900 select-none">
                    <FileText className="w-4 h-4" />
                    Show raw output
                  </summary>
                  <pre className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200 font-mono text-xs text-gray-700 whitespace-pre-wrap overflow-x-auto">
                    {rd.raw}
                  </pre>
                </details>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default RoutingTablesPanel;
