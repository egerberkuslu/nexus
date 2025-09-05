import { useState, useCallback } from 'react';
import {
  PERFORMANCE_API_ENDPOINTS,
  PERFORMANCE_TEST_TYPES,
  normalizeHostData,
  normalizeMonitoringData
} from '../utils/performanceUtils';

export const usePerformanceAPI = (apiCall, addLog) => {
  // Main performance data state
  const [performanceData, setPerformanceData] = useState({
    status: null,
    hosts: [],
    monitoring: { active: false },
    testHistory: [],
    currentTest: null,
    realTimeMetrics: {}
  });

  // Loading states
  const [loading, setLoading] = useState({
    status: false,
    hosts: false,
    test: false,
    monitoring: false,
    history: false,
    report: false
  });

  // Error states
  const [errors, setErrors] = useState({
    status: null,
    hosts: null,
    test: null,
    monitoring: null,
    history: null,
    report: null
  });

  // Helpers
  const setLoadingState = useCallback((key, value) => {
    setLoading(prev => ({ ...prev, [key]: value }));
  }, []);

  const setErrorState = useCallback((key, value) => {
    setErrors(prev => ({ ...prev, [key]: value }));
  }, []);

  // Safely unwrap API responses that may be {data} or {data: {data}}
  const handleApiResponse = useCallback((response, operation) => {
    if (response?.success) {
      // ✅ tolerate both shapes
      return (response.data && (response.data.data ?? response.data)) || null;
    } else {
      const error = response?.error || 'Unknown error occurred';
      addLog?.(`❌ ${operation} failed: ${error}`, 'error', 'performance');
      throw new Error(error);
    }
  }, [addLog]);

  /** -------- Core API Calls -------- **/

  // Fetch system status
  const fetchStatus = useCallback(async () => {
    setLoadingState('status', true);
    setErrorState('status', null);
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.STATUS, { method: 'GET' });
      const data = handleApiResponse(response, 'Status fetch');

      setPerformanceData(prev => ({ ...prev, status: data }));
      addLog?.('📊 Performance status updated', 'info', 'performance');
      return data;
    } catch (error) {
      setErrorState('status', error.message);
      throw error;
    } finally {
      setLoadingState('status', false);
    }
  }, [apiCall, addLog, handleApiResponse, setLoadingState, setErrorState]);

  // Fetch available hosts
  const fetchHosts = useCallback(async () => {
    setLoadingState('hosts', true);
    setErrorState('hosts', null);
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.HOSTS, { method: 'GET' });
      const data = handleApiResponse(response, 'Host discovery');

      const normalizedHosts = (data?.hosts || []).map(normalizeHostData);
      setPerformanceData(prev => ({ ...prev, hosts: normalizedHosts }));
      addLog?.(`🖥️ Discovered ${normalizedHosts.length} hosts`, 'info', 'performance');
      return data;
    } catch (error) {
      setErrorState('hosts', error.message);
      throw error;
    } finally {
      setLoadingState('hosts', false);
    }
  }, [apiCall, addLog, handleApiResponse, setLoadingState, setErrorState]);

  /**
   * Run performance test
   * Accepts a READY payload in snake_case (from UI builder), or a legacy config with `testType`.
   * - For validate_only requests, we DO NOT mutate currentTest/testHistory.
   */
  const runTest = useCallback(async (config) => {
    setLoadingState('test', true);
    setErrorState('test', null);

    try {
      // Determine endpoint:
      // 1) Prefer explicit `test_type` from payload ('comprehensive' | 'stress_test' | 'bandwidth' etc.)
      // 2) Fallback to legacy `testType` from UI state.
      const kindFromPayload = config?.test_type;
      const kindFromLegacy = config?.testType;

      let endpoint = PERFORMANCE_API_ENDPOINTS.TEST_COMPREHENSIVE;

      if (kindFromPayload === 'stress_test' || kindFromLegacy === PERFORMANCE_TEST_TYPES.STRESS) {
        endpoint = PERFORMANCE_API_ENDPOINTS.TEST_STRESS;
      } else if (
        // Single custom test
        (kindFromPayload && !['comprehensive', 'stress_test'].includes(kindFromPayload)) ||
        kindFromLegacy === PERFORMANCE_TEST_TYPES.CUSTOM
      ) {
        endpoint = PERFORMANCE_API_ENDPOINTS.TEST_CUSTOM;
      }

      // Decide body:
      // If caller passed a prebuilt snake_case payload, forward as-is.
      // Else, remove UI-only fields and send snake_case subset.
      const {
        testType, // legacy UI field (drop)
        ...body
      } = config || {};

      addLog?.(`🚀 Starting ${kindFromPayload || kindFromLegacy || 'comprehensive'} test...`, 'info', 'performance');

      const response = await apiCall(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      const data = handleApiResponse(response, 'Performance test');

      const isValidate = !!body.validate_only;
      if (!isValidate) {
        // Only persist real executions
        setPerformanceData(prev => ({
          ...prev,
          currentTest: data,
          testHistory: [data, ...prev.testHistory.slice(0, 9)]
        }));
        addLog?.('✅ Test completed successfully', 'success', 'performance');
      } else {
        addLog?.('✅ Validation successful', 'success', 'performance');
      }

      return data;
    } catch (error) {
      setErrorState('test', error.message);
      throw error;
    } finally {
      setLoadingState('test', false);
    }
  }, [apiCall, addLog, handleApiResponse, setLoadingState, setErrorState]);

  // Start monitoring
  const startMonitoring = useCallback(async (config) => {
    setLoadingState('monitoring', true);
    setErrorState('monitoring', null);
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.MONITORING_START, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });

      const data = handleApiResponse(response, 'Start monitoring');

      setPerformanceData(prev => ({
        ...prev,
        monitoring: { active: true, ...data }
      }));

      addLog?.('📈 Real-time monitoring started', 'success', 'performance');
      return data;
    } catch (error) {
      setErrorState('monitoring', error.message);
      throw error;
    } finally {
      setLoadingState('monitoring', false);
    }
  }, [apiCall, addLog, handleApiResponse, setLoadingState, setErrorState]);

  // Stop monitoring
  const stopMonitoring = useCallback(async () => {
    setLoadingState('monitoring', true);
    setErrorState('monitoring', null);
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.MONITORING_STOP, {
        method: 'POST'
      });

      handleApiResponse(response, 'Stop monitoring');

      setPerformanceData(prev => ({
        ...prev,
        monitoring: { active: false },
        realTimeMetrics: {}
      }));

      addLog?.('📉 Real-time monitoring stopped', 'info', 'performance');
    } catch (error) {
      setErrorState('monitoring', error.message);
      throw error;
    } finally {
      setLoadingState('monitoring', false);
    }
  }, [apiCall, addLog, handleApiResponse, setLoadingState]);

  // Fetch test history
  const fetchTestHistory = useCallback(async (filters = {}) => {
    setLoadingState('history', true);
    setErrorState('history', null);
    try {
      const params = new URLSearchParams();
      if (filters.limit) params.append('limit', filters.limit);
      if (filters.test_type) params.append('test_type', filters.test_type);

      const url = `${PERFORMANCE_API_ENDPOINTS.RESULTS_HISTORY}${params.toString() ? '?' + params.toString() : ''}`;
      const response = await apiCall(url, { method: 'GET' });

      const data = handleApiResponse(response, 'Fetch test history');

      setPerformanceData(prev => ({ ...prev, testHistory: data?.history || [] }));
      addLog?.(`📊 Loaded ${(data?.history || []).length} test sessions`, 'info', 'performance');
      return data;
    } catch (error) {
      setErrorState('history', error.message);
      throw error;
    } finally {
      setLoadingState('history', false);
    }
  }, [apiCall, addLog, handleApiResponse, setLoadingState, setErrorState]);

  // Fetch session results
  const fetchSessionResults = useCallback(async (sessionId) => {
    try {
      const response = await apiCall(`${PERFORMANCE_API_ENDPOINTS.RESULTS_SESSION}/${sessionId}`, {
        method: 'GET'
      });

      const data = handleApiResponse(response, `Fetch session ${sessionId}`);
      return data?.session;
    } catch (error) {
      addLog?.(`❌ Failed to fetch session ${sessionId}: ${error.message}`, 'error', 'performance');
      throw error;
    }
  }, [apiCall, addLog, handleApiResponse]);

  // Generate report
  const generateReport = useCallback(async (sessionId, options = {}) => {
    setLoadingState('report', true);
    setErrorState('report', null);
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.REPORTS_GENERATE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          format: options.format || 'json',
          include_analysis: options.includeAnalysis !== false,
          include_charts: options.includeCharts || false
        })
      });

      const data = handleApiResponse(response, 'Generate report');

      addLog?.('📋 Performance report generated', 'success', 'performance');
      return data;
    } catch (error) {
      setErrorState('report', error.message);
      throw error;
    } finally {
      setLoadingState('report', false);
    }
  }, [apiCall, addLog, handleApiResponse, setLoadingState, setErrorState]);

  // Analyze performance
  const analyzePerformance = useCallback(async (sessionId, options = {}) => {
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.REPORTS_ANALYZE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          analysis_type: options.analysisType || 'comprehensive',
          comparison_baseline: options.comparisonBaseline
        })
      });

      const data = handleApiResponse(response, 'Analyze performance');

      addLog?.('🔍 Performance analysis completed', 'success', 'performance');
      return data;
    } catch (error) {
      addLog?.(`❌ Analysis failed: ${error.message}`, 'error', 'performance');
      throw error;
    }
  }, [apiCall, addLog, handleApiResponse]);

  // Fetch monitoring metrics
  const fetchMonitoringMetrics = useCallback(async () => {
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.MONITORING_STATUS, {
        method: 'GET'
      });

      const data = handleApiResponse(response, 'Fetch monitoring status');
      const normalizedData = normalizeMonitoringData(data);
      setPerformanceData(prev => ({
        ...prev,
        realTimeMetrics: normalizedData
      }));
      return normalizedData;
    } catch (error) {
      console.warn('Failed to fetch monitoring metrics:', error.message);
    }
  }, [apiCall, handleApiResponse]);

  // Fetch monitoring history
  const fetchMonitoringHistory = useCallback(async (pairKey, limit) => {
    try {
      const params = new URLSearchParams();
      if (pairKey) params.append('pair_key', pairKey);
      if (limit) params.append('limit', limit);

      const url = `${PERFORMANCE_API_ENDPOINTS.MONITORING_HISTORY}${params.toString() ? '?' + params.toString() : ''}`;
      const response = await apiCall(url, { method: 'GET' });

      const data = handleApiResponse(response, 'Fetch monitoring history');
      return data?.history;
    } catch (error) {
      addLog?.(`❌ Failed to fetch monitoring history: ${error.message}`, 'error', 'performance');
      throw error;
    }
  }, [apiCall, addLog, handleApiResponse]);

  // Check prerequisites
  const checkPrerequisites = useCallback(async () => {
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.PREREQUISITES, {
        method: 'GET'
      });

      return handleApiResponse(response, 'Check prerequisites');
    } catch (error) {
      addLog?.(`❌ Prerequisites check failed: ${error.message}`, 'error', 'performance');
      throw error;
    }
  }, [apiCall, addLog, handleApiResponse]);

  // Cleanup
  const cleanup = useCallback(async (options = {}) => {
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.CLEANUP, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cleanup_type: options.cleanupType || 'all',
          keep_recent_sessions: options.keepRecentSessions || 5
        })
      });

      const data = handleApiResponse(response, 'Cleanup');

      addLog?.('🧹 Performance resources cleaned up', 'success', 'performance');

      // Refresh data after cleanup
      await Promise.allSettled([fetchStatus(), fetchTestHistory()]);

      return data;
    } catch (error) {
      addLog?.(`❌ Cleanup failed: ${error.message}`, 'error', 'performance');
      throw error;
    }
  }, [apiCall, addLog, handleApiResponse, fetchStatus, fetchTestHistory]);

  // Install tools
  const installTools = useCallback(async (tools, hosts) => {
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.TOOLS_INSTALL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tools: tools || ['iperf3'],
          hosts: hosts
        })
      });

      const data = handleApiResponse(response, 'Install tools');

      addLog?.(`🔧 Tools installation completed`, 'success', 'performance');

      // Refresh hosts after installation
      await fetchHosts();

      return data;
    } catch (error) {
      addLog?.(`❌ Tool installation failed: ${error.message}`, 'error', 'performance');
      throw error;
    }
  }, [apiCall, addLog, handleApiResponse, fetchHosts]);

  // Refresh all data
  const refreshData = useCallback(async () => {
    try {
      await Promise.allSettled([fetchStatus(), fetchHosts(), fetchTestHistory()]);
    } catch (error) {
      console.warn('Some data refresh operations failed:', error);
    }
  }, [fetchStatus, fetchHosts, fetchTestHistory]);

  return {
    performanceData,
    loading,
    errors,

    // Core operations
    fetchStatus,
    fetchHosts,
    runTest,
    startMonitoring,
    stopMonitoring,
    fetchTestHistory,
    fetchSessionResults,
    generateReport,
    analyzePerformance,

    // Monitoring operations
    fetchMonitoringMetrics,
    fetchMonitoringHistory,

    // Utility operations
    checkPrerequisites,
    cleanup,
    installTools,
    refreshData,

    // State setters
    setPerformanceData,
    setLoadingState,
    setErrorState
  };
};
