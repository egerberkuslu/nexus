// components/NetworkDiagnostic/panels/SwitchFlowsPanel.jsx
import React, { useEffect, useMemo } from 'react';
import { 
  XCircle, 
  RefreshCw,
  Shield,
  BarChart3
} from 'lucide-react';
import StatusBadge from '../StatusBadge';
import ActionButton from '../ActionButton';

// Helper to parse the CLI port_stats string into structured rows
const parsePortStats = raw => {
  const lines = raw.split('\n');
  const entries = [];
  let curr = null;

  lines.forEach(line => {
    let m = line.match(/port\s+(LOCAL|\d+):\s+rx pkts=(\d+), bytes=(\d+), drop=(\d+), errs=(\d+), frame=(\d+), over=(\d+), crc=(\d+)/);
    if (m) {
      if (curr) entries.push(curr);
      curr = {
        port: m[1],
        rx_pkts: m[2],
        rx_bytes: m[3],
        rx_drop: m[4],
        rx_errs: m[5],
        rx_frame: m[6],
        rx_over: m[7],
        rx_crc: m[8]
      };
    }
    m = line.match(/tx pkts=(\d+), bytes=(\d+), drop=(\d+), errs=(\d+), coll=(\d+)/);
    if (m && curr) {
      curr.tx_pkts  = m[1];
      curr.tx_bytes = m[2];
      curr.tx_drop  = m[3];
      curr.tx_errs  = m[4];
      curr.tx_coll  = m[5];
    }
    m = line.match(/duration=(\d+\.\d+)s/);
    if (m && curr) {
      curr.duration = m[1] + 's';
    }
  });
  if (curr) entries.push(curr);
  return entries;
};

const SwitchFlowsPanel = ({
  diagnosticData,
  diagnosticLoading,
  diagnosticErrors,
  fetchSwitchFlows
}) => {
  // Unwrap any { data: … } envelope
  const raw = diagnosticData.switchFlows;
  const switchFlows = raw?.data ?? raw;

  // Fetch once on mount
  useEffect(() => {
    fetchSwitchFlows();
  }, [fetchSwitchFlows]);

  // Memoize parsing all port_stats so we can index by switch ID
  const portStatsMap = useMemo(() => {
    if (!switchFlows) return {};
    return Object.fromEntries(
      Object.entries(switchFlows).map(([id, fd]) => [
        id,
        parsePortStats(fd.port_stats || '')
      ])
    );
  }, [switchFlows]);

  // Loading state
  if (diagnosticLoading.flows && !switchFlows) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-indigo-500" />
        <span className="ml-3 text-gray-600">Loading switch flows…</span>
      </div>
    );
  }

  // Top‑level error
  if (diagnosticErrors.flows) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-4">
        <div className="flex items-center gap-2">
          <XCircle className="w-5 h-5 text-red-500" />
          <span className="text-red-700 font-medium">
            Error loading switch flows: {diagnosticErrors.flows}
          </span>
        </div>
      </div>
    );
  }

  // No data
  if (!switchFlows || Object.keys(switchFlows).length === 0) {
    return (
      <div className="text-center py-12">
        <Shield className="w-16 h-16 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-500 font-medium">No switch flow data available</p>
        <p className="text-gray-400 text-sm">Click “Refresh Flows” to load data</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold text-gray-900">Switch Flow Tables</h3>
          <p className="text-gray-600">OpenFlow switch flow table analysis</p>
        </div>
        <ActionButton
          onClick={fetchSwitchFlows}
          loading={diagnosticLoading.flows}
          icon={<Shield className="w-4 h-4" />}
          label="Refresh Flows"
          color="indigo"
        />
      </div>

      {/* Switch cards */}
      <div className="grid gap-6">
        {Object.entries(switchFlows).map(([switchId, fd]) => {
          const hasError = Boolean(fd.error);
          const flows    = fd.flows || [];
          const count    = fd.flow_count || 0;
          // Lookup parsed stats
          const stats    = portStatsMap[switchId] || [];

          return (
            <div key={switchId} className="bg-white border-2 border-gray-200 rounded-xl p-6">
              {/* Header row */}
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-lg font-semibold text-gray-900">{switchId}</h4>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-3 h-3 rounded-full ${
                        fd.connected ? 'bg-emerald-500' : 'bg-red-500'
                      }`}
                    />
                    <span className="text-sm font-medium text-gray-600">
                      {fd.connected ? 'Connected' : 'Disconnected'}
                    </span>
                  </div>
                  <StatusBadge
                    status={fd.connected}
                    text={`${count} flows`}
                  />
                </div>
              </div>

              {/* Per-switch error */}
              {hasError && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                  <div className="flex items-center gap-2">
                    <XCircle className="w-5 h-5 text-red-500" />
                    <span className="text-red-700 font-medium">{fd.error}</span>
                  </div>
                </div>
              )}

              {/* Flow entries */}
              {!hasError && flows.length > 0 && (
                <div className="space-y-4 mb-4">
                  <div className="bg-gray-50 rounded-xl p-4 border-2 border-gray-200">
                    <h5 className="text-sm font-semibold text-gray-900 mb-3">
                      Flow Entries (first 5):
                    </h5>
                    <div className="space-y-2">
                      {flows.slice(0, 5).map((flow, i) => (
                        <div
                          key={i}
                          className="bg-white border border-gray-200 rounded-lg p-3"
                        >
                          <pre className="text-xs font-mono text-gray-700 whitespace-pre-wrap break-all">
                            {flow}
                          </pre>
                        </div>
                      ))}
                    </div>
                    {flows.length > 5 && (
                      <div className="text-center mt-4">
                        <span className="text-sm text-gray-500 bg-white px-3 py-1 rounded-full border border-gray-200">
                          … and {flows.length - 5} more
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* No flows */}
              {!hasError && flows.length === 0 && (
                <div className="text-center py-8 mb-4">
                  <Shield className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-500 font-medium">No flows found</p>
                  <p className="text-gray-400 text-sm">
                    {fd.connected
                      ? 'Switch is connected but has no flows'
                      : 'Switch is not connected to controller'}
                  </p>
                </div>
              )}

              {/* Port stats table */}
              {stats.length > 0 && (
                <details className="mt-4">
                  <summary className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer hover:text-gray-900 select-none">
                    <BarChart3 className="w-4 h-4" />
                    Show port statistics
                  </summary>
                  <div className="mt-3 overflow-x-auto">
                    <table className="w-full text-xs font-mono text-gray-700 border-collapse">
                      <thead>
                        <tr className="bg-gray-100">
                          <th className="p-2 border">Port</th>
                          <th className="p-2 border">RX pkts</th>
                          <th className="p-2 border">RX bytes</th>
                          <th className="p-2 border">RX drop</th>
                          <th className="p-2 border">TX pkts</th>
                          <th className="p-2 border">TX bytes</th>
                          <th className="p-2 border">TX drop</th>
                          <th className="p-2 border">Duration</th>
                        </tr>
                      </thead>
                      <tbody>
                        {stats.map((row, i) => (
                          <tr key={i} className="odd:bg-white even:bg-gray-50">
                            <td className="p-2 border">{row.port}</td>
                            <td className="p-2 border">{row.rx_pkts}</td>
                            <td className="p-2 border">{row.rx_bytes}</td>
                            <td className="p-2 border">{row.rx_drop}</td>
                            <td className="p-2 border">{row.tx_pkts}</td>
                            <td className="p-2 border">{row.tx_bytes}</td>
                            <td className="p-2 border">{row.tx_drop}</td>
                            <td className="p-2 border">{row.duration}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </details>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SwitchFlowsPanel;
