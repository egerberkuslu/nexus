import { useCallback } from 'react';

export const usePerformanceData = ({
  apiCall,
  addLog,
  setPerformanceMetrics,
  setPerformanceHistory,
  setLoading
}) => {
  // Fetch real-time performance metrics
  const fetchPerformanceMetrics = useCallback(async () => {
    try {
      const result = await apiCall('/performance/metrics');
      if (result.success) {
        const metrics = result.data;
        if (setPerformanceMetrics) {
          setPerformanceMetrics({
            bandwidth_utilization: metrics.bandwidth_utilization || 0,
            packet_loss: metrics.packet_loss || 0,
            latency: metrics.latency || 0,
            throughput: metrics.throughput || 0,
            cpu_usage: metrics.cpu_usage || 0,
            memory_usage: metrics.memory_usage || 0,
            active_flows: metrics.active_flows || 0,
            timestamp: Date.now()
          });
        }

        // Store metrics history
        if (setPerformanceHistory) {
          setPerformanceHistory(prev => {
            const newHistory = [...prev, {
              timestamp: Date.now(),
              ...metrics
            }];
            return newHistory.slice(-50); // Keep last 50 readings
          });
        }

        return metrics;
      }
    } catch (error) {
      addLog(`❌ Failed to fetch performance metrics: ${error.message}`, 'error', 'performance');
    }
    return null;
  }, [apiCall, addLog, setPerformanceMetrics, setPerformanceHistory]);

  // Run performance test
  const runPerformanceTest = useCallback(async (testType, config = {}) => {
    setLoading(true);
    try {
      const result = await apiCall('/performance/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          test_type: testType,
          ...config
        })
      });

      if (result.success && result.data.success) {
        addLog(`🧪 Performance test "${testType}" completed successfully`, 'success', 'performance');
        return result.data.results;
      } else {
        addLog(`❌ Performance test failed: ${result.data?.error || result.error}`, 'error', 'performance');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error running performance test: ${error.message}`, 'error', 'performance');
      return null;
    } finally {
      setLoading(false);
    }
  }, [apiCall, addLog, setLoading]);

  // Get performance report
  const generatePerformanceReport = useCallback(async (timeRange = '1h') => {
    try {
      const result = await apiCall(`/performance/report?range=${timeRange}`);
      if (result.success) {
        addLog(`📊 Performance report generated for ${timeRange}`, 'success', 'performance');
        return result.data.report;
      } else {
        addLog(`❌ Failed to generate report: ${result.data?.error || result.error}`, 'error', 'performance');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error generating report: ${error.message}`, 'error', 'performance');
      return null;
    }
  }, [apiCall, addLog]);

  // Monitor network health
  const checkNetworkHealth = useCallback(async () => {
    try {
      const result = await apiCall('/performance/health');
      if (result.success) {
        return result.data.health_status;
      }
    } catch (error) {
      addLog(`❌ Failed to check network health: ${error.message}`, 'error', 'performance');
    }
    return null;
  }, [apiCall, addLog]);

  // Get bandwidth utilization
  const getBandwidthUtilization = useCallback(async (interfaceName = null) => {
    try {
      const endpoint = interfaceName
        ? `/performance/bandwidth/${interfaceName}`
        : '/performance/bandwidth';
      const result = await apiCall(endpoint);
      if (result.success) {
        return result.data.bandwidth_data;
      }
    } catch (error) {
      addLog(`❌ Failed to get bandwidth data: ${error.message}`, 'error', 'performance');
    }
    return null;
  }, [apiCall, addLog]);

  // Monitor latency
  const measureLatency = useCallback(async (target = null, count = 10) => {
    try {
      const result = await apiCall('/performance/latency', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, count })
      });

      if (result.success && result.data.success) {
        addLog(`📈 Latency measurement completed: ${result.data.average_latency}ms avg`, 'success', 'performance');
        return result.data.latency_data;
      } else {
        addLog(`❌ Latency measurement failed: ${result.data?.error || result.error}`, 'error', 'performance');
        return null;
      }
    } catch (error) {
      addLog(`❌ Error measuring latency: ${error.message}`, 'error', 'performance');
      return null;
    }
  }, [apiCall, addLog]);

  return {
    fetchPerformanceMetrics,
    runPerformanceTest,
    generatePerformanceReport,
    checkNetworkHealth,
    getBandwidthUtilization,
    measureLatency
  };
};
