import React from 'react';
import { BarChart3, Server, AlertTriangle, CheckCircle, Clock, Zap } from 'lucide-react';

const StatisticsPanel = ({
  networkMetrics,
  packetTrend,
  bandwidthTrend,
  latencyTrend,
  controllerStatus,
  controllerConfig,
  controllerStats,
  controllerLogs,
  clearControllerLogs,
  ryuApp,
  formatBytes,
  topology,
  networkStatus
}) => {
  // Calculate controller connection status
  const switchCount = topology.nodes?.filter(node => node.type === 'switch').length || 0;
  const controllerCount = topology.controllers?.length || 0;
  const hasControllerNodes = controllerCount > 0;
  
  // Determine network mode
  const networkMode = hasControllerNodes ? 'OpenFlow' : 'Learning Bridge';
  const isOpenFlowMode = hasControllerNodes && controllerStatus.running;

  return (
    <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
        <h2 className="text-lg font-bold text-gray-800 flex items-center gap-3">
          <BarChart3 className="w-5 h-5 text-indigo-500" />
          Network Statistics
        </h2>
      </div>
      
      <div className="p-6 space-y-6">
        {/* Network Mode Indicator */}
        <div className={`p-4 rounded-xl border-2 ${
          isOpenFlowMode 
            ? 'bg-green-50 border-green-200' 
            : hasControllerNodes && !controllerStatus.running
            ? 'bg-yellow-50 border-yellow-200'
            : 'bg-blue-50 border-blue-200'
        }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {isOpenFlowMode ? (
                <CheckCircle className="w-5 h-5 text-green-600" />
              ) : hasControllerNodes && !controllerStatus.running ? (
                <AlertTriangle className="w-5 h-5 text-yellow-600" />
              ) : (
                <Zap className="w-5 h-5 text-blue-600" />
              )}
              <span className={`font-semibold ${
                isOpenFlowMode 
                  ? 'text-green-700' 
                  : hasControllerNodes && !controllerStatus.running
                  ? 'text-yellow-700'
                  : 'text-blue-700'
              }`}>
                {networkMode} Mode
              </span>
            </div>
            <div className={`text-xs px-2 py-1 rounded-full ${
              isOpenFlowMode 
                ? 'bg-green-100 text-green-700' 
                : hasControllerNodes && !controllerStatus.running
                ? 'bg-yellow-100 text-yellow-700'
                : 'bg-blue-100 text-blue-700'
            }`}>
              {isOpenFlowMode 
                ? 'Controller Active' 
                : hasControllerNodes && !controllerStatus.running
                ? 'Controller Needed'
                : 'No Controller'
              }
            </div>
          </div>
          {hasControllerNodes && !controllerStatus.running && (
            <div className="mt-2 text-xs text-yellow-600">
              OpenFlow switches detected but controller is not running. Start controller for optimal performance.
            </div>
          )}
        </div>

        {/* Core Metrics Grid */}
        <div className="grid grid-cols-2 gap-3">
          <div className="text-center p-4 bg-emerald-50 rounded-xl border border-emerald-200">
            <div className="text-2xl font-bold text-emerald-600">
              {networkMetrics.packets_transferred.toLocaleString()}
            </div>
            <div className="text-xs text-emerald-500 font-medium">Packets Sent</div>
            {packetTrend !== 0 && (
              <div className={`text-xs mt-1 ${packetTrend > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {packetTrend > 0 ? '↗' : '↘'} {Math.abs(packetTrend).toFixed(1)}%
              </div>
            )}
          </div>
          
          <div className="text-center p-4 bg-blue-50 rounded-xl border border-blue-200">
            <div className="text-2xl font-bold text-blue-600">
              {networkMetrics.bandwidth_mbps.toFixed(1)}
            </div>
            <div className="text-xs text-blue-500 font-medium">Mbps</div>
            {bandwidthTrend !== 0 && (
              <div className={`text-xs mt-1 ${bandwidthTrend > 0 ? 'text-green-600' : 'text-red-600'}`}>
                {bandwidthTrend > 0 ? '↗' : '↘'} {Math.abs(bandwidthTrend).toFixed(1)}%
              </div>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="text-center p-4 bg-purple-50 rounded-xl border border-purple-200">
            <div className="text-2xl font-bold text-purple-600">
              {networkMetrics.latency_ms.toFixed(1)}
            </div>
            <div className="text-xs text-purple-500 font-medium">ms Latency</div>
            {latencyTrend !== 0 && (
              <div className={`text-xs mt-1 ${latencyTrend < 0 ? 'text-green-600' : 'text-red-600'}`}>
                {latencyTrend < 0 ? '↗' : '↘'} {Math.abs(latencyTrend).toFixed(1)}%
              </div>
            )}
          </div>
          
          <div className="text-center p-4 bg-orange-50 rounded-xl border border-orange-200">
            <div className="text-2xl font-bold text-orange-600">
              {formatBytes(networkMetrics.total_bytes)}
            </div>
            <div className="text-xs text-orange-500 font-medium">Total Data</div>
          </div>
        </div>

        {/* Network Overview */}
        <div className="grid grid-cols-3 gap-3">
          <div className="text-center p-3 bg-gray-50 rounded-xl border border-gray-200">
            <div className="text-lg font-bold text-gray-600">{switchCount}</div>
            <div className="text-xs text-gray-500 font-medium">Switches</div>
          </div>
          
          <div className="text-center p-3 bg-cyan-50 rounded-xl border border-cyan-200">
            <div className="text-lg font-bold text-cyan-600">{networkMetrics.active_flows}</div>
            <div className="text-xs text-cyan-500 font-medium">Active Flows</div>
          </div>
          
          <div className="text-center p-3 bg-pink-50 rounded-xl border border-pink-200">
            <div className="text-lg font-bold text-pink-600">{networkMetrics.total_interfaces}</div>
            <div className="text-xs text-pink-500 font-medium">Interfaces</div>
          </div>
        </div>

        {/* Uptime Display */}
        {networkStatus.running && (
          <div className="flex items-center justify-center gap-2 p-3 bg-gray-50 rounded-xl border border-gray-200">
            <Clock className="w-4 h-4 text-gray-500" />
            <span className="text-sm text-gray-600">Uptime: </span>
            <span className="text-sm font-mono font-semibold text-gray-700">
              {networkMetrics.uptime}
            </span>
          </div>
        )}

        {/* Controller Status Panel */}
        {(controllerStatus.running || hasControllerNodes) && (
          <div className={`p-4 rounded-xl border-2 ${
            controllerStatus.running 
              ? 'bg-indigo-50 border-indigo-200' 
              : 'bg-red-50 border-red-200'
          }`}>
            <div className="flex items-center justify-between mb-3">
              <h3 className={`text-sm font-bold flex items-center gap-2 ${
                controllerStatus.running ? 'text-indigo-600' : 'text-red-600'
              }`}>
                <Server className="w-4 h-4" />
                Controller {controllerStatus.running ? 'Active' : 'Inactive'}
              </h3>
              {controllerLogs.length > 0 && (
                <button
                  onClick={clearControllerLogs}
                  className={`text-xs transition-colors ${
                    controllerStatus.running 
                      ? 'text-indigo-500 hover:text-indigo-700' 
                      : 'text-red-500 hover:text-red-700'
                  }`}
                >
                  Clear Logs
                </button>
              )}
            </div>
            
            {controllerStatus.running ? (
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-indigo-500">Application:</span>
                  <span className="text-indigo-700 font-mono text-[10px]">
                    {controllerConfig.type || controllerStatus.type || ryuApp}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-indigo-500">Protocol:</span>
                  <span className="text-indigo-700 font-semibold">OpenFlow 1.3</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-indigo-500">Port:</span>
                  <span className="text-indigo-700 font-mono">{controllerConfig.port || '6633'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-indigo-500">PID:</span>
                  <span className="text-indigo-700 font-mono">{controllerStatus.pid || 'N/A'}</span>
                </div>
                
                {controllerStats.controller && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-indigo-500">Connections:</span>
                      <span className="text-indigo-700">{controllerStats.controller.connections || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-indigo-500">Memory Usage:</span>
                      <span className="text-indigo-700">{controllerStats.controller.memory_usage || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-indigo-500">Flow Tables:</span>
                      <span className="text-indigo-700">{Object.keys(controllerStats.flows || {}).length}</span>
                    </div>
                  </>
                )}

                {/* Recent Controller Logs */}
                {controllerLogs.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-indigo-200">
                    <div className="text-xs text-indigo-600 font-medium mb-2">Recent Activity:</div>
                    <div className="max-h-20 overflow-y-auto space-y-1">
                      {controllerLogs.slice(-3).map((log, idx) => (
                        <div key={idx} className="text-[10px] text-indigo-600 font-mono bg-indigo-100 px-2 py-1 rounded">
                          {typeof log === 'string' 
                            ? log.slice(0, 60) + (log.length > 60 ? '...' : '') 
                            : JSON.stringify(log).slice(0, 60)
                          }
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-xs text-red-600">
                Controller is not running. Network switches may not forward traffic properly.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default StatisticsPanel;