import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Square,
  Monitor,
  Clock,
  Activity,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  CheckCircle,
  Info,
  Settings,
  Refresh,
  Eye,
  EyeOff,
  Wifi,
  WifiOff,
  Server,
  Network,
  Gauge
} from 'lucide-react';

import { 
  PERFORMANCE_API_ENDPOINTS, 
  MONITORING_INTERVALS, 
  normalizeMonitoringData,
  normalizeHostData
} from '../utils/performanceUtils';

const RealTimeMonitoring = ({
  addLog,
  monitoring,
  realTimeMetrics,
  monitoringConfig,
  setMonitoringConfig,
  onStart,
  onStop,
  loading,
  error,
  hosts
}) => {
  const [selectedPairs, setSelectedPairs] = useState([]);
  const [metricsHistory, setMetricsHistory] = useState({});
  const [showSettings, setShowSettings] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const intervalRef = useRef(null);

  // Process hosts with normalization
  const safeHosts = (hosts || []).map(normalizeHostData);
  const readyHosts = safeHosts.filter(h => h.capabilities?.ping);

  // Generate all possible host pairs
  const generateHostPairs = () => {
    const pairs = [];
    for (let i = 0; i < readyHosts.length; i++) {
      for (let j = i + 1; j < readyHosts.length; j++) {
        pairs.push({
          key: `${readyHosts[i].name}->${readyHosts[j].name}`,
          src: readyHosts[i],
          dst: readyHosts[j]
        });
      }
    }
    return pairs;
  };

  const hostPairs = generateHostPairs();

  // Update metrics history when new data arrives
  useEffect(() => {
    if (realTimeMetrics?.metrics) {
      const timestamp = new Date().toISOString();
      setMetricsHistory(prev => {
        const updated = { ...prev };
        Object.entries(realTimeMetrics.metrics).forEach(([pairKey, metrics]) => {
          if (!updated[pairKey]) updated[pairKey] = [];
          updated[pairKey].push({
            timestamp,
            ...metrics
          });
          // Keep only last 50 data points
          if (updated[pairKey].length > 50) {
            updated[pairKey] = updated[pairKey].slice(-50);
          }
        });
        return updated;
      });
    }
  }, [realTimeMetrics]);

  // Handle monitoring start
  const handleStart = async () => {
    try {
      const config = {
        interval: monitoringConfig.interval,
        hosts: monitoringConfig.hosts.length > 0 ? monitoringConfig.hosts : undefined
      };
      await onStart(config);
    } catch (error) {
      addLog?.(`❌ Failed to start monitoring: ${error.message}`, 'error', 'performance');
    }
  };

  // Handle monitoring stop
  const handleStop = async () => {
    try {
      await onStop();
      setMetricsHistory({}); // Clear local history on stop
    } catch (error) {
      addLog?.(`❌ Failed to stop monitoring: ${error.message}`, 'error', 'performance');
    }
  };

  // Format latency with trend indicator
  const formatLatencyWithTrend = (pairKey, currentLatency) => {
    const history = metricsHistory[pairKey];
    if (!history || history.length < 2) {
      return { 
        value: typeof currentLatency === 'number' ? currentLatency.toFixed(2) : 'N/A', 
        trend: 'stable' 
      };
    }

    const previous = history[history.length - 2].latency_ms;
    const current = currentLatency || 0;
    const diff = current - previous;
    const percentChange = previous > 0 ? (diff / previous) * 100 : 0;

    let trend = 'stable';
    if (Math.abs(percentChange) > 5) {
      trend = diff > 0 ? 'up' : 'down';
    }

    return {
      value: current.toFixed(2),
      trend,
      change: diff.toFixed(2)
    };
  };

  // Get connectivity status color
  const getConnectivityColor = (connected) => {
    return connected ? 'text-green-600' : 'text-red-600';
  };

  // Get latency color based on value
  const getLatencyColor = (latency) => {
    if (!latency || latency < 1) return 'text-green-600';
    if (latency < 10) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Real-time Monitoring</h3>
        <div className="flex items-center gap-2">
          <span className={`text-sm px-2 py-1 rounded-full ${
            monitoring?.active 
              ? 'bg-green-100 text-green-800' 
              : 'bg-gray-100 text-gray-600'
          }`}>
            {monitoring?.active ? 'Active' : 'Inactive'}
          </span>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Prerequisites Check */}
      {readyHosts.length < 2 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-yellow-600" />
            <h4 className="font-medium text-yellow-800">Insufficient Hosts</h4>
          </div>
          <p className="text-sm text-yellow-700">
            You need at least 2 hosts with ping capability to start monitoring.
            Currently {readyHosts.length} of {safeHosts.length} hosts are ready.
          </p>
        </div>
      )}

      {/* Monitoring Settings */}
      {showSettings && (
        <div className="bg-gray-50 rounded-lg p-4">
          <h4 className="font-medium text-gray-900 mb-3">Monitoring Configuration</h4>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Monitoring Interval (seconds)
              </label>
              <select
                value={monitoringConfig.interval}
                onChange={(e) => setMonitoringConfig(prev => ({
                  ...prev,
                  interval: parseInt(e.target.value)
                }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                disabled={monitoring?.active}
              >
                <option value={MONITORING_INTERVALS.REALTIME}>10 seconds</option>
                <option value={MONITORING_INTERVALS.FREQUENT}>30 seconds</option>
                <option value={MONITORING_INTERVALS.NORMAL}>1 minute</option>
                <option value={MONITORING_INTERVALS.PERIODIC}>5 minutes</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Auto-refresh Display
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={autoRefresh}
                  onChange={(e) => setAutoRefresh(e.target.checked)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <span className="text-sm text-gray-700">
                  Auto-refresh metrics display
                </span>
              </label>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Hosts to Monitor
            </label>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
              {readyHosts.map(host => (
                <label key={host.name} className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={monitoringConfig.hosts.includes(host.name)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setMonitoringConfig(prev => ({
                          ...prev,
                          hosts: [...prev.hosts, host.name]
                        }));
                      } else {
                        setMonitoringConfig(prev => ({
                          ...prev,
                          hosts: prev.hosts.filter(h => h !== host.name)
                        }));
                      }
                    }}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    disabled={monitoring?.active}
                  />
                  <span className="text-sm text-gray-700">{host.name}</span>
                </label>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              Leave empty to monitor all available hosts
            </p>
          </div>
        </div>
      )}

      {/* Control Buttons */}
      <div className="flex items-center gap-4">
        {!monitoring?.active ? (
          <button
            onClick={handleStart}
            disabled={loading || readyHosts.length < 2}
            className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            <Play className="w-5 h-5" />
            Start Monitoring
          </button>
        ) : (
          <button
            onClick={handleStop}
            disabled={loading}
            className="flex items-center gap-2 px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:bg-gray-300 transition-colors"
          >
            <Square className="w-5 h-5" />
            Stop Monitoring
          </button>
        )}

        {monitoring?.active && (
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <Activity className="w-4 h-4" />
            <span>Monitoring every {monitoring.interval || monitoringConfig.interval}s</span>
          </div>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            <h4 className="font-medium text-red-800">Monitoring Error</h4>
          </div>
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Real-time Metrics Display */}
      {monitoring?.active && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-gray-900">Live Metrics</h4>
            <div className="flex items-center gap-2 text-sm text-gray-600">
              <Clock className="w-4 h-4" />
              <span>
                Last updated: {realTimeMetrics?.timestamp ? 
                  new Date(realTimeMetrics.timestamp).toLocaleTimeString() : 
                  'Never'
                }
              </span>
            </div>
          </div>

          {realTimeMetrics?.metrics && Object.keys(realTimeMetrics.metrics).length > 0 ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {Object.entries(realTimeMetrics.metrics).map(([pairKey, metrics]) => {
                const latencyData = formatLatencyWithTrend(pairKey, metrics.latency_ms);
                const TrendIcon = latencyData.trend === 'up' ? TrendingUp : 
                                latencyData.trend === 'down' ? TrendingDown : Minus;
                
                return (
                  <div key={pairKey} className="bg-white border border-gray-200 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-3">
                      <h5 className="font-medium text-gray-900">{pairKey.replace('->', ' →')}</h5>
                      <div className="flex items-center gap-2">
                        {metrics.connectivity ? (
                          <Wifi className="w-4 h-4 text-green-500" />
                        ) : (
                          <WifiOff className="w-4 h-4 text-red-500" />
                        )}
                        <span className={`text-xs font-medium ${getConnectivityColor(metrics.connectivity)}`}>
                          {metrics.connectivity ? 'Connected' : 'Disconnected'}
                        </span>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <Clock className="w-4 h-4 text-gray-500" />
                          <span className="text-sm text-gray-600">Latency</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xl font-bold ${getLatencyColor(metrics.latency_ms || 0)}`}>
                            {latencyData.value}ms
                          </span>
                          {latencyData.trend !== 'stable' && (
                            <div className="flex items-center gap-1">
                              <TrendIcon className={`w-4 h-4 ${
                                latencyData.trend === 'up' ? 'text-red-500' : 'text-green-500'
                              }`} />
                              <span className={`text-xs ${
                                latencyData.trend === 'up' ? 'text-red-600' : 'text-green-600'
                              }`}>
                                {latencyData.change}ms
                              </span>
                            </div>
                          )}
                        </div>
                      </div>

                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <Activity className="w-4 h-4 text-gray-500" />
                          <span className="text-sm text-gray-600">Status</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {metrics.connectivity ? (
                            <CheckCircle className="w-5 h-5 text-green-500" />
                          ) : (
                            <AlertTriangle className="w-5 h-5 text-red-500" />
                          )}
                          <span className={`text-sm font-medium ${getConnectivityColor(metrics.connectivity)}`}>
                            {metrics.connectivity ? 'Healthy' : 'Issues'}
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Mini trend chart */}
                    {metricsHistory[pairKey] && metricsHistory[pairKey].length > 1 && (
                      <div className="mt-3 pt-3 border-t border-gray-100">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs text-gray-600">Latency Trend (last 10 points)</span>
                          <span className="text-xs text-gray-500">
                            {metricsHistory[pairKey].length} samples
                          </span>
                        </div>
                        <div className="h-8 flex items-end gap-1">
                          {metricsHistory[pairKey].slice(-10).map((point, i) => {
                            const height = Math.max(4, Math.min(32, (point.latency_ms || 0) * 4));
                            return (
                              <div
                                key={i}
                                className="bg-blue-400 rounded-sm"
                                style={{ 
                                  height: `${height}px`, 
                                  width: `${100 / 10}%`,
                                  opacity: 0.5 + (i / 10) * 0.5
                                }}
                                title={`${point.latency_ms?.toFixed(2)}ms at ${new Date(point.timestamp).toLocaleTimeString()}`}
                              />
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="text-center py-8 bg-gray-50 rounded-lg">
              <Monitor className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h4 className="text-lg font-medium text-gray-900 mb-2">No Metrics Available</h4>
              <p className="text-gray-600">
                Waiting for monitoring data... This may take up to {monitoring.interval || monitoringConfig.interval} seconds.
              </p>
            </div>
          )}
        </div>
      )}

      {/* Monitoring Statistics */}
      {monitoring?.active && Object.keys(metricsHistory).length > 0 && (
        <div className="bg-gray-50 rounded-lg p-4">
          <h4 className="font-medium text-gray-900 mb-3">Monitoring Statistics</h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600">
                {Object.keys(realTimeMetrics?.metrics || {}).length}
              </div>
              <div className="text-sm text-gray-600">Active Pairs</div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600">
                {Object.values(realTimeMetrics?.metrics || {}).filter(m => m.connectivity).length}
              </div>
              <div className="text-sm text-gray-600">Healthy Connections</div>
            </div>
            
            <div className="text-center">
              <div className="text-2xl font-bold text-purple-600">
                {Object.values(metricsHistory).reduce((sum, history) => sum + history.length, 0)}
              </div>
              <div className="text-sm text-gray-600">Total Samples</div>
            </div>
          </div>
        </div>
      )}

      {/* Information Panel */}
      {!monitoring?.active && readyHosts.length >= 2 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <Info className="w-5 h-5 text-blue-600" />
            <h4 className="font-medium text-blue-800">Ready to Monitor</h4>
          </div>
          <p className="text-sm text-blue-700 mb-3">
            {hostPairs.length} host pairs available for monitoring. 
            Real-time latency and connectivity monitoring will test network health continuously.
          </p>
          <ul className="text-sm text-blue-700 space-y-1">
            <li>• Monitors ping latency between all host pairs</li>
            <li>• Detects connectivity issues in real-time</li>
            <li>• Tracks performance trends over time</li>
            <li>• Configurable monitoring intervals (10s to 5min)</li>
          </ul>
        </div>
      )}
    </div>
  );
};

export default RealTimeMonitoring;