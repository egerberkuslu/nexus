// components/PerformanceWidget.jsx
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { Activity, Zap, Eye, AlertTriangle, BarChart3, Monitor } from 'lucide-react';

import {
  PERFORMANCE_API_ENDPOINTS,
  MONITORING_INTERVALS,
  normalizeHostData,
  normalizeMonitoringData
} from './utils/performanceUtils';

const PerformanceWidget = ({
  apiCall,
  addLog,
  onOpenPerformanceManager,
  networkStatus,        // may be undefined; API also provides network_running
  className = ''
}) => {
  const [performanceMetrics, setPerformanceMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [monitoringActive, setMonitoringActive] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [apiError, setApiError] = useState(null);

  // Helper: pick a sensible "is running" that matches the *data* you have
  const isNetworkRunning = useMemo(() => {
    if (typeof networkStatus?.running === 'boolean') return networkStatus.running;
    if (performanceMetrics?.network_running != null) return performanceMetrics.network_running;
    if (performanceMetrics?.prerequisites?.network_running != null) return performanceMetrics.prerequisites.network_running;
    return true; // default to true so we can fetch status at least once
  }, [networkStatus?.running, performanceMetrics]);

  // Direct API call for status
  const fetchPerformanceStatus = useCallback(async () => {
    // Only skip if the parent explicitly says "not running"
    if (networkStatus?.running === false) {
      addLog?.('ℹ️ Skipping status fetch: parent indicates network not running', 'info', 'performance');
      return;
    }

    setLoading(true);
    setApiError(null);

    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.STATUS, { method: 'GET' });

      if (!response?.success) {
        throw new Error(response?.error || 'API request failed');
      }

      const data = response.data.data || {};

      // Process & normalize
      const processedData = {
        ...data,
        hosts: (data.hosts || []).map(host =>
          normalizeHostData({
            ...host,
            capabilities: {
              iperf3: Boolean(host.capabilities?.iperf3 ?? host.iperf3_available),
              ping: Boolean(host.capabilities?.ping ?? host.ping_available),
              netstat: Boolean(host.capabilities?.netstat ?? host.netstat_available)
            }
          })
        ),
        monitoring: normalizeMonitoringData(data.monitoring || {})
      };

      setPerformanceMetrics(processedData);
      setMonitoringActive(Boolean(processedData.monitoring?.active));

      // Prefer API timestamp; fallback to now
      const ts = processedData.timestamp ? new Date(processedData.timestamp) : new Date();
      setLastUpdate(ts);

      addLog?.(
        `📊 Performance status loaded: ${processedData.total_hosts ?? processedData.hosts?.length ?? 0} hosts, ready: ${processedData.system_ready}`,
        'info',
        'performance'
      );
    } catch (error) {
      setApiError(error.message);
      addLog?.(`❌ Failed to fetch performance status: ${error.message}`, 'error', 'performance');
    } finally {
      setLoading(false);
    }
  }, [apiCall, networkStatus?.running, addLog]);

  // Check monitoring status (optional refinement)
  const checkMonitoringStatus = useCallback(async () => {
    if (networkStatus?.running === false) return;

    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.MONITORING_STATUS, { method: 'GET' });
      if (response?.success) {
        const monitoringData = normalizeMonitoringData(response.data);
        setMonitoringActive(Boolean(monitoringData.active));
      }
    } catch (error) {
      // Non-fatal
      console.warn('Failed to check monitoring status:', error.message);
    }
  }, [apiCall, networkStatus?.running]);

  // Auto-refresh
  useEffect(() => {
    // Always attempt at least one fetch unless parent explicitly says not running
    fetchPerformanceStatus();
    checkMonitoringStatus();

    const refreshSeconds = MONITORING_INTERVALS?.FREQUENT || 30;
    const id = setInterval(() => {
      fetchPerformanceStatus();
      checkMonitoringStatus();
    }, refreshSeconds * 1000);

    return () => clearInterval(id);
  }, [fetchPerformanceStatus, checkMonitoringStatus]);

  // Quick test function
  const runQuickTest = async () => {
    const hosts = performanceMetrics?.hosts || [];
    if (hosts.length < 2) {
      addLog?.('❌ Need at least 2 hosts for performance testing', 'error', 'performance');
      return;
    }

    const readyHosts = hosts.filter(h => h?.capabilities?.iperf3 && h?.capabilities?.ping);
    if (readyHosts.length < 2) {
      addLog?.('❌ Need at least 2 hosts with iperf3 and ping capabilities', 'error', 'performance');
      return;
    }

    try {
      addLog?.('🚀 Starting quick performance test...', 'info', 'performance');

      // Prefer names, fallback to IPs
      const src = readyHosts[0].name || readyHosts[0].ip;
      const dst = readyHosts[1].name || readyHosts[1].ip;

      const payload = {
        src_host: src,
        dst_host: dst,
        duration: 10,
        test_types: ['bandwidth', 'latency']
      };

      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.TEST_COMPREHENSIVE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (response?.success) {
        addLog?.('✅ Quick performance test completed', 'success', 'performance');
        await fetchPerformanceStatus();
      } else {
        const error = response?.error || 'Unknown error';
        addLog?.(`❌ Performance test failed: ${error}`, 'error', 'performance');
      }
    } catch (error) {
      addLog?.(`❌ Performance test error: ${error?.message || error}`, 'error', 'performance');
    }
  };

  // If the parent explicitly says "network not running", show that state
  if (networkStatus?.running === false) {
    return (
      <div className={`bg-gray-50 border border-gray-200 rounded-lg p-4 ${className}`}>
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-semibold text-gray-900 flex items-center gap-2">
            <Activity className="w-5 h-5 text-gray-500" />
            Performance
          </h3>
        </div>
        <p className="text-sm text-gray-600">Network not running</p>
      </div>
    );
  }

  const hostsAvailable = performanceMetrics?.total_hosts ?? performanceMetrics?.hosts?.length ?? 0;
  const systemReady = Boolean(performanceMetrics?.system_ready);
  const showMonitoringDot = Boolean(monitoringActive);

  return (
    <div className={`bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-gray-900 flex items-center gap-2">
          <Activity className="w-5 h-5 text-gray-800" />
          Performance
        </h3>
        <div className="flex items-center gap-2">
          {showMonitoringDot && (
            <div className="w-2 h-2 bg-emerald-500 rounded-full animate-pulse" title="Monitoring Active" />
          )}
          <button
            onClick={onOpenPerformanceManager}
            className="p-1 text-gray-400 hover:text-gray-900 transition-colors"
            title="Open Performance Manager"
          >
            <Eye className="w-4 h-4" />
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-2">
          <div className="animate-pulse">
            <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
            <div className="h-4 bg-gray-200 rounded w-1/2"></div>
          </div>
        </div>
      ) : performanceMetrics ? (
        <div className="space-y-3">
          {/* Status Summary */}
          <div className="grid grid-cols-2 gap-3">
            <div className="text-center">
              <div
                className={`text-xl font-bold ${
                  systemReady ? 'text-emerald-600' : 'text-red-600'
                }`}
              >
                {systemReady ? 'Ready' : 'Not Ready'}
              </div>
              <div className="text-xs text-gray-600">System Status</div>
            </div>

            <div className="text-center">
              <div className="text-xl font-bold text-gray-900">
                {hostsAvailable}
              </div>
              <div className="text-xs text-gray-600">Available Hosts</div>
            </div>
          </div>

          {/* Test History */}
          {performanceMetrics.test_history?.total_sessions > 0 && (
            <div className="bg-gray-50 rounded p-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-600">Test Sessions:</span>
                <span className="font-medium">{performanceMetrics.test_history.total_sessions}</span>
              </div>
              {performanceMetrics.test_history.last_test && (
                <div className="text-xs text-gray-500 mt-1">
                  Last: {performanceMetrics.test_history.last_test}
                </div>
              )}
            </div>
          )}

          {/* Quick Actions */}
          <div className="flex gap-2">
            <button
              onClick={runQuickTest}
              disabled={!systemReady || loading || !isNetworkRunning}
              className="flex-1 flex items-center justify-center gap-1 px-2 py-1 bg-gray-100 text-gray-900 rounded text-xs hover:bg-gray-200 disabled:bg-gray-100 disabled:text-gray-400 transition-colors"
            >
              <Zap className="w-3 h-3" />
              {loading ? 'Testing...' : 'Quick Test'}
            </button>

            <button
              onClick={onOpenPerformanceManager}
              disabled={!systemReady || loading || !isNetworkRunning}
              className="flex-1 flex items-center justify-center gap-1 px-2 py-1 bg-gray-100 text-gray-900 rounded text-xs hover:bg-gray-200 disabled:bg-gray-100 disabled:text-gray-400 transition-colors"
            >
              <Monitor className="w-3 h-3" />
              Monitor
            </button>
          </div>

          {/* API Error */}
          {apiError && (
            <div className="bg-red-50 border border-red-200 rounded p-2">
              <div className="flex items-center gap-2 mb-1">
                <AlertTriangle className="w-4 h-4 text-red-600" />
                <span className="text-xs font-medium text-red-800">API Error</span>
              </div>
              <p className="text-xs text-red-700">{apiError}</p>
            </div>
          )}

          {/* Last Update */}
          {lastUpdate && (
            <div className="text-xs text-gray-500 text-center">
              Updated: {lastUpdate.toLocaleTimeString()}
            </div>
          )}
        </div>
      ) : (
        <div className="text-center py-4">
          <div className="text-gray-400 mb-2">
            <BarChart3 className="w-8 h-8 mx-auto" />
          </div>
          <p className="text-sm text-gray-600 mb-3">
            {apiError ? 'Error loading performance data' : 'Performance data unavailable'}
          </p>
          {apiError && (
            <p className="text-xs text-red-600 mb-3">{apiError}</p>
          )}
          <button
            onClick={fetchPerformanceStatus}
            disabled={loading}
            className="px-3 py-1 bg-gray-100 text-gray-900 rounded text-sm hover:bg-gray-200 disabled:bg-gray-300 transition-colors"
          >
            {loading ? 'Loading...' : 'Reload Data'}
          </button>
        </div>
      )}
    </div>
  );
};

export default PerformanceWidget;
