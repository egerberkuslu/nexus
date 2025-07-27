import React from 'react';
import { Router, Server, Network, Terminal, Settings } from 'lucide-react';

const FlowStatistics = ({
  flowStats,
  controllerStats,
  controllerStatus,
  controllerConfig,
  controllerLogs,
  availableApps,
  fetchControllerLogs,
  clearControllerLogs,
  switchControllerApp,
  setRyuApp,
  addLog,
  loading,
  formatBytes
}) => {
  if (Object.keys(flowStats).length === 0 && Object.keys(controllerStats).length === 0) {
    return null;
  }

  return (
    <div className="mt-6 bg-white rounded-2xl shadow-lg border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
        <h2 className="text-xl font-bold text-gray-800 flex items-center gap-3">
          <Router className="w-6 h-6 text-indigo-500" />
          OpenFlow & Controller Statistics
        </h2>
      </div>
      <div className="p-6">
        {/* Controller Statistics Section */}
        {controllerStatus.running && controllerStats.controller && (
          <div className="mb-6 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-200">
            <h3 className="text-lg font-semibold text-blue-800 mb-4 flex items-center gap-2">
              <Server className="w-5 h-5" />
              Controller Statistics
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="text-center p-4 bg-white rounded-lg border border-blue-200">
                <div className="text-2xl font-bold text-blue-600">{controllerStats.controller.connections || 0}</div>
                <div className="text-sm text-blue-500">Active Connections</div>
              </div>
              <div className="text-center p-4 bg-white rounded-lg border border-blue-200">
                <div className="text-2xl font-bold text-blue-600">{Object.keys(controllerStats.flows || {}).length}</div>
                <div className="text-sm text-blue-500">Total Flow Tables</div>
              </div>
              <div className="text-center p-4 bg-white rounded-lg border border-blue-200">
                <div className="text-2xl font-bold text-blue-600">{controllerStats.controller.memory_usage || 'N/A'}</div>
                <div className="text-sm text-blue-500">Memory Usage</div>
              </div>
            </div>
            
            {/* Controller Configuration Panel */}
            <div className="mt-4 bg-white rounded-lg p-4 border border-blue-200">
              <h4 className="text-sm font-semibold text-blue-700 mb-3">Configuration</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-blue-500">Application:</span>
                  <div className="font-mono text-blue-700">{controllerConfig.type || 'N/A'}</div>
                </div>
                <div>
                  <span className="text-blue-500">Port:</span>
                  <div className="font-mono text-blue-700">{controllerConfig.port || '6633'}</div>
                </div>
                <div>
                  <span className="text-blue-500">PID:</span>
                  <div className="font-mono text-blue-700">{controllerStatus.pid || 'N/A'}</div>
                </div>
                <div>
                  <span className="text-blue-500">Python:</span>
                  <div className="font-mono text-blue-700 truncate">{controllerConfig.python_executable || 'default'}</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Switch Flow Statistics */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {Object.entries(flowStats).map(([switchId, stats]) => (
            <div key={switchId} className="bg-gray-50 rounded-xl p-4 border border-gray-200">
              <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
                <Network className="w-5 h-5 text-emerald-500" />
                {switchId}
              </h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Active Flows:</span>
                  <span className="text-gray-800 font-mono">{stats.flows?.length || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Total Packets:</span>
                  <span className="text-gray-800 font-mono">{stats.total_packets?.toLocaleString() || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Total Bytes:</span>
                  <span className="text-gray-800 font-mono">{formatBytes(stats.total_bytes || 0)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Drop Count:</span>
                  <span className="text-gray-800 font-mono">{stats.drop_count || 0}</span>
                </div>
                {stats.error && (
                  <div className="text-red-500 text-xs">Error: {stats.error}</div>
                )}
                
                {/* Flow Details Button */}
                <button
                  onClick={() => {
                    addLog(`📊 Viewing flow details for ${switchId}`, 'info', 'controller');
                    // Could expand to show detailed flow table
                  }}
                  className="w-full mt-3 px-3 py-2 text-xs bg-emerald-100 text-emerald-700 rounded-lg hover:bg-emerald-200 transition-colors"
                >
                  View Flow Details
                </button>
              </div>
            </div>
          ))}
        </div>

        {/* Controller Logs Section */}
        {controllerLogs.length > 0 && (
          <div className="mt-6 bg-gray-50 rounded-xl p-4 border border-gray-200">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                <Terminal className="w-5 h-5 text-purple-500" />
                Controller Logs
              </h3>
              <div className="flex gap-2">
                <button
                  onClick={fetchControllerLogs}
                  className="px-3 py-1 text-xs bg-purple-100 text-purple-700 rounded-lg hover:bg-purple-200 transition-colors"
                >
                  Refresh
                </button>
                <button
                  onClick={clearControllerLogs}
                  className="px-3 py-1 text-xs bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors"
                >
                  Clear
                </button>
              </div>
            </div>
            <div className="max-h-40 overflow-y-auto space-y-1 custom-scrollbar">
              {controllerLogs.slice(-10).map((log, idx) => (
                <div key={idx} className="text-xs font-mono bg-white p-2 rounded border border-gray-300">
                  {typeof log === 'string' ? log : JSON.stringify(log)}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Available Controller Apps */}
        {availableApps.length > 0 && (
          <div className="mt-6 bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl p-4 border border-indigo-200">
            <h3 className="text-lg font-semibold text-indigo-800 mb-3 flex items-center gap-2">
              <Settings className="w-5 h-5" />
              Available Controller Applications
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {availableApps.map(app => (
                <div key={app.id} className="bg-white rounded-lg p-3 border border-indigo-200">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-indigo-700 text-sm">{app.name}</h4>
                    <span className={`text-xs px-2 py-1 rounded-full ${
                      app.category === 'switching' ? 'bg-green-100 text-green-700' :
                      app.category === 'routing' ? 'bg-blue-100 text-blue-700' :
                      app.category === 'security' ? 'bg-red-100 text-red-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {app.category}
                    </span>
                  </div>
                  <p className="text-xs text-indigo-600 mb-2">{app.description}</p>
                  <button
                    onClick={() => {
                      if (controllerStatus.running) {
                        switchControllerApp(app.id);
                      } else {
                        setRyuApp(app.id);
                        addLog(`Selected ${app.name} for next controller start`, 'info', 'controller');
                      }
                    }}
                    disabled={loading || (controllerConfig.type === app.id && controllerStatus.running)}
                    className={`w-full px-3 py-1 text-xs rounded-lg transition-colors ${
                      controllerConfig.type === app.id && controllerStatus.running
                        ? 'bg-emerald-100 text-emerald-700 cursor-default'
                        : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200'
                    } disabled:opacity-50`}
                  >
                    {controllerConfig.type === app.id && controllerStatus.running ? 'Active' : 
                     controllerStatus.running ? 'Switch To' : 'Select'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default FlowStatistics;