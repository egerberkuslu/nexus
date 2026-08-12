// components/NetworkDiagnostic/panels/ArpTablesPanel.jsx
import React, { useEffect } from 'react';
import { 
  XCircle, 
  RefreshCw,
  Network,
  FileText
} from 'lucide-react';
import StatusBadge from '../StatusBadgeLegacy';
import ActionButton from '../ActionButton';

const ArpTablesPanel = ({ 
  diagnosticData, 
  diagnosticLoading, 
  diagnosticErrors, 
  fetchArpTables 
}) => {
  // Unwrap the envelope if present
  const raw = diagnosticData.arpTables;
  const arpTables = raw?.data ?? raw;  

  // auto‑load on mount
  useEffect(() => {
    fetchArpTables();
  }, [fetchArpTables]);

  if (diagnosticLoading.arp && !arpTables) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="w-8 h-8 animate-spin text-indigo-500" />
        <span className="ml-3 text-gray-600">Loading ARP tables…</span>
      </div>
    );
  }

  if (diagnosticErrors.arp) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-4">
        <div className="flex items-center gap-2">
          <XCircle className="w-5 h-5 text-red-500" />
          <span className="text-red-700 font-medium">
            Error loading ARP tables: {diagnosticErrors.arp}
          </span>
        </div>
      </div>
    );
  }

  if (!arpTables || Object.keys(arpTables).length === 0) {
    return (
      <div className="text-center py-12">
        <Network className="w-16 h-16 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-500 font-medium">No ARP data available</p>
        <p className="text-gray-400 text-sm">Click “Refresh ARP” to load data</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold text-gray-900">ARP Tables</h3>
          <p className="text-gray-600">Address Resolution Protocol table analysis</p>
        </div>
        <ActionButton
          onClick={fetchArpTables}
          loading={diagnosticLoading.arp}
          icon={<Network className="w-4 h-4" />}
          label="Refresh ARP"
          color="indigo"
        />
      </div>

      <div className="grid gap-6">
        {Object.entries(arpTables).map(([hostId, arpData]) => {
          const count = arpData.entries?.length || 0;
          const hasError = !!arpData.error;

          return (
            <div key={hostId} className="bg-white border-2 border-gray-200 rounded-xl p-6">
              <div className="flex items-center justify-between mb-4">
                <h4 className="text-lg font-semibold text-gray-900">{hostId}</h4>
                <StatusBadge 
                  status={!hasError && count > 0} 
                  text={`${count} entries`}
                  icon={hasError ? '⚠️' : '📶'}
                />
              </div>

              {hasError && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                  <div className="flex items-center gap-2">
                    <XCircle className="w-5 h-5 text-red-500" />
                    <span className="text-red-700 font-medium">{arpData.error}</span>
                  </div>
                </div>
              )}

              {!hasError && count > 0 && (
                <div className="bg-gray-50 rounded-xl p-4 border-2 border-gray-200">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b-2 border-gray-300">
                          <th className="py-2 px-3 text-left font-semibold text-gray-900">Hostname</th>
                          <th className="py-2 px-3 text-left font-semibold text-gray-900">IP Address</th>
                          <th className="py-2 px-3 text-left font-semibold text-gray-900">MAC Address</th>
                        </tr>
                      </thead>
                      <tbody>
                        {arpData.entries.map((e, i) => (
                          <tr key={i} className="border-b border-gray-200 hover:bg-white transition-colors">
                            <td className="py-2 px-3 font-mono text-sm text-gray-700">{e.hostname}</td>
                            <td className="py-2 px-3 font-mono text-sm text-blue-600">{e.ip}</td>
                            <td className="py-2 px-3 font-mono text-sm text-purple-600">{e.mac}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {!hasError && count === 0 && (
                <div className="text-center py-8">
                  <Network className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                  <p className="text-gray-500 font-medium">No ARP entries found</p>
                  <p className="text-gray-400 text-sm mt-1">
                    This host may not have communicated with other devices
                  </p>
                </div>
              )}

              {arpData.raw && (
                <details className="mt-4">
                  <summary className="flex items-center gap-2 text-sm font-medium text-gray-700 cursor-pointer select-none hover:text-gray-900">
                    <FileText className="w-4 h-4" />
                    Show raw output
                  </summary>
                  <pre className="mt-3 p-3 bg-gray-50 rounded-lg border border-gray-200 font-mono text-xs text-gray-700 whitespace-pre-wrap overflow-x-auto">
                    {arpData.raw}
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

export default ArpTablesPanel;
