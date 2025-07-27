import React from 'react';
import { Activity, Clock } from 'lucide-react';

const ActivityMonitor = ({ logs, setLogs }) => {
  return (
    <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-800 flex items-center gap-3">
            <Activity className="w-5 h-5 text-indigo-500" />
            Activity Monitor
          </h2>
          <div className="flex items-center gap-2">
            <select
              className="text-xs border border-gray-300 rounded px-2 py-1"
              onChange={(e) => {
                const filter = e.target.value;
                // Could implement log filtering here
              }}
            >
              <option value="all">All Logs</option>
              <option value="network">Network</option>
              <option value="controller">Controller</option>
              <option value="terminal">Terminal</option>
              <option value="api">API</option>
            </select>
            <button
              onClick={() => setLogs([])}
              className="px-3 py-1 text-xs bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
            >
              Clear
            </button>
            <div className="text-xs text-gray-500">{logs.length}/50</div>
          </div>
        </div>
      </div>
      <div className="h-96 overflow-y-auto bg-gray-50 custom-scrollbar">
        {logs.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-gray-500 p-6">
            <Clock className="w-12 h-12 text-gray-400 mb-3" />
            <p className="text-center">No activity logged yet...</p>
            <p className="text-sm text-gray-500 mt-1">System events will appear here</p>
          </div>
        ) : (
          <div className="p-4 space-y-2">
            {logs.slice().reverse().map((log) => (
              <div
                key={log.id}
                className={`p-3 rounded-lg border-l-4 shadow-sm text-sm transition-all duration-200 hover:shadow-md ${log.type === 'error'
                  ? 'bg-red-50 border-l-red-500 text-red-700'
                  : log.type === 'success'
                    ? 'bg-emerald-50 border-l-emerald-500 text-emerald-700'
                    : log.type === 'warning'
                      ? 'bg-amber-50 border-l-amber-500 text-amber-700'
                      : log.type === 'command'
                        ? 'bg-purple-50 border-l-purple-500 text-purple-700'
                        : log.type === 'output'
                          ? 'bg-gray-100 border-l-gray-400 text-gray-700'
                          : 'bg-blue-50 border-l-blue-500 text-blue-700'
                  }`}
              >
                <div className="flex items-start gap-3">
                  <span className="text-xs font-mono text-gray-500 min-w-[70px] mt-0.5 flex-shrink-0">
                    [{log.time}]
                  </span>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`text-xs px-2 py-1 rounded-full font-medium ${log.category === 'network'
                          ? 'bg-green-100 text-green-700'
                          : log.category === 'controller'
                            ? 'bg-blue-100 text-blue-700'
                            : log.category === 'terminal'
                              ? 'bg-purple-100 text-purple-700'
                              : log.category === 'test'
                                ? 'bg-orange-100 text-orange-700'
                                : log.category === 'api'
                                  ? 'bg-red-100 text-red-700'
                                  : 'bg-gray-100 text-gray-700'
                          }`}
                      >
                        {log.category}
                      </span>
                    </div>
                    <span className="text-xs leading-relaxed break-words">
                      {log.message}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ActivityMonitor;