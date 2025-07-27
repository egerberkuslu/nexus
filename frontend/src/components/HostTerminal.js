import React from 'react';
import { Terminal, ChevronRight, ArrowRight, RefreshCw, Info, Network, Activity, Database, BarChart3 } from 'lucide-react';

const HostTerminal = ({
  selectedHost,
  setSelectedHost,
  command,
  setCommand,
  executeCommand,
  topology,
  networkStatus,
  loading
}) => {
  return (
    <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
        <h2 className="text-lg font-bold text-gray-800 flex items-center gap-3">
          <Terminal className="w-5 h-5 text-indigo-500" />
          Host Terminal
        </h2>
      </div>
      <div className="p-6 space-y-4">
        <div>
          <label className="block text-sm font-semibold text-gray-600 mb-2">Target Host</label>
          <div className="relative">
            <select
              value={selectedHost}
              onChange={(e) => setSelectedHost(e.target.value)}
              disabled={!networkStatus.running}
              className="block w-full px-4 py-3 text-base border border-gray-300 rounded-xl bg-white text-gray-700 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:bg-gray-100 disabled:text-gray-500 appearance-none transition-all duration-200"
            >
              <option value="">Select host...</option>
              {topology.nodes.filter(n => n.type === 'host').map(host => (
                <option key={host.id} value={host.id}>
                  {host.id} • {host.ip}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-gray-500">
              <ChevronRight className="w-5 h-5 rotate-90" />
            </div>
          </div>
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-600 mb-2">Command</label>
          <div className="flex rounded-xl shadow-sm overflow-hidden border border-gray-300">
            <input
              type="text"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder="ifconfig, ping 10.0.0.2, netstat -i"
              disabled={!networkStatus.running || !selectedHost}
              onKeyPress={(e) => e.key === 'Enter' && executeCommand()}
              className="flex-1 min-w-0 block w-full px-4 py-3 text-sm text-gray-700 bg-white border-0 focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100 placeholder-gray-500"
            />
            <button
              onClick={executeCommand}
              disabled={!selectedHost || !command || loading}
              className="inline-flex items-center px-6 py-3 border-0 text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {selectedHost && (
          <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
            <h3 className="text-sm font-bold text-indigo-600 mb-3 flex items-center gap-2">
              <Info className="w-4 h-4" />
              Host Information
            </h3>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="font-medium text-indigo-500">Hostname:</span>
                <span className="text-indigo-700 font-mono">{selectedHost}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium text-indigo-500">IP Address:</span>
                <span className="text-indigo-700 font-mono">{topology.nodes.find(n => n.id === selectedHost)?.ip || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium text-indigo-500">MAC Address:</span>
                <span className="text-indigo-700 font-mono text-[10px]">{topology.nodes.find(n => n.id === selectedHost)?.mac || 'Auto-generated'}</span>
              </div>
              <div className="flex justify-between">
                <span className="font-medium text-indigo-500">Status:</span>
                <span className={`font-semibold ${networkStatus.running ? 'text-emerald-600' : 'text-red-600'}`}>
                  {networkStatus.running ? 'Online' : 'Offline'}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Enhanced Quick Commands */}
        <div>
          <label className="block text-sm font-semibold text-gray-600 mb-3">Quick Commands</label>
          <div className="grid grid-cols-2 gap-2">
            {[
              { cmd: 'ifconfig', label: 'Network Info', icon: <Network className="w-3 h-3" /> },
              { cmd: 'ping -c 3 10.0.0.1', label: 'Ping Gateway', icon: <Activity className="w-3 h-3" /> },
              { cmd: 'arp -a', label: 'ARP Table', icon: <Database className="w-3 h-3" /> },
              { cmd: 'netstat -i', label: 'Interface Stats', icon: <BarChart3 className="w-3 h-3" /> }
            ].map((item, idx) => (
              <button
                key={idx}
                onClick={() => setCommand(item.cmd)}
                disabled={!selectedHost}
                className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default HostTerminal;