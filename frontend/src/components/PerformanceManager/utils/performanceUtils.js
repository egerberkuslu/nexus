// Performance Manager Utility Functions and Constants
// Updated to match backend API structure

// Performance test types and their configurations
export const PERFORMANCE_TEST_TYPES = {
  COMPREHENSIVE: 'comprehensive',
  STRESS: 'stress',
  CUSTOM: 'custom',
  BANDWIDTH: 'bandwidth',
  LATENCY: 'latency',
  JITTER: 'jitter',
  PACKET_LOSS: 'packet_loss'
};

// Test type metadata
export const TEST_TYPE_CONFIG = {
  [PERFORMANCE_TEST_TYPES.COMPREHENSIVE]: {
    name: 'Comprehensive Test',
    description: 'Run all performance tests (bandwidth, latency, jitter, packet loss)',
    icon: 'BarChart3',
    color: 'blue',
    defaultDuration: 30,
    requiresHosts: 2,
    supportedTypes: ['bandwidth', 'latency', 'jitter', 'packet_loss']
  },
  [PERFORMANCE_TEST_TYPES.STRESS]: {
    name: 'Stress Test',
    description: 'Test network limits with multiple concurrent flows',
    icon: 'Zap',
    color: 'red',
    defaultDuration: 300,
    requiresHosts: 2,
    maxConcurrentFlows: 50
  },
  [PERFORMANCE_TEST_TYPES.CUSTOM]: {
    name: 'Custom Test',
    description: 'Run a specific test type with custom parameters',
    icon: 'Settings',
    color: 'purple',
    defaultDuration: 30,
    requiresHosts: 2
  },
  [PERFORMANCE_TEST_TYPES.BANDWIDTH]: {
    name: 'Bandwidth Test',
    description: 'Measure throughput capacity',
    icon: 'Activity',
    color: 'green',
    defaultDuration: 30,
    requiresHosts: 2,
    unit: 'Mbps'
  },
  [PERFORMANCE_TEST_TYPES.LATENCY]: {
    name: 'Latency Test',
    description: 'Measure round-trip time',
    icon: 'Clock',
    color: 'yellow',
    defaultDuration: 10,
    requiresHosts: 2,
    unit: 'ms'
  },
  [PERFORMANCE_TEST_TYPES.JITTER]: {
    name: 'Jitter Test',
    description: 'Measure latency variation',
    icon: 'Gauge',
    color: 'orange',
    defaultDuration: 30,
    requiresHosts: 2,
    unit: 'ms'
  },
  [PERFORMANCE_TEST_TYPES.PACKET_LOSS]: {
    name: 'Packet Loss Test',
    description: 'Measure packet loss percentage',
    icon: 'Target',
    color: 'red',
    defaultDuration: 20,
    requiresHosts: 2,
    unit: '%'
  }
};

// Performance thresholds for health assessment
export const PERFORMANCE_THRESHOLDS = {
  bandwidth: {
    excellent: 900, // Mbps
    good: 500,
    fair: 100,
    poor: 10
  },
  latency: {
    excellent: 1, // ms
    good: 10,
    fair: 50,
    poor: 100
  },
  jitter: {
    excellent: 1, // ms
    good: 5,
    fair: 20,
    poor: 50
  },
  packetLoss: {
    excellent: 0, // %
    good: 0.1,
    fair: 1,
    poor: 5
  }
};

// Monitoring intervals (seconds)
export const MONITORING_INTERVALS = {
  REALTIME: 10,
  FREQUENT: 30,
  NORMAL: 60,
  PERIODIC: 300
};

// API endpoints - Updated to match backend structure
export const PERFORMANCE_API_ENDPOINTS = {
  // Base endpoints
  STATUS: '/performance-management/performance/status',
  PREREQUISITES: '/performance-management/performance/prerequisites',
  HOSTS: '/performance-management/performance/hosts',
  
  // Testing endpoints
  TEST_COMPREHENSIVE: '/performance-management/performance/test/comprehensive',
  TEST_STRESS: '/performance-management/performance/test/stress',
  TEST_CUSTOM: '/performance-management/performance/test/custom',
  
  // Monitoring endpoints
  MONITORING_START: '/performance-management/performance/monitoring/start',
  MONITORING_STOP: '/performance-management/performance/monitoring/stop',
  MONITORING_STATUS: '/performance-management/performance/monitoring/status',
  MONITORING_HISTORY: '/performance-management/performance/monitoring/history',
  
  // Results and reporting
  RESULTS_HISTORY: '/performance-management/performance/results/history',
  RESULTS_SESSION: '/performance-management/performance/results/session',
  REPORTS_GENERATE: '/performance-management/performance/reports/generate',
  REPORTS_ANALYZE: '/performance-management/performance/reports/analyze',
  
  // Utility endpoints
  CLEANUP: '/performance-management/performance/cleanup',
  TOOLS_INSTALL: '/performance-management/performance/tools/install'
};

// Format performance metrics for display
export const formatMetric = (value, type, decimals = 2) => {
  if (typeof value !== 'number' || isNaN(value)) return 'N/A';
  
  const config = TEST_TYPE_CONFIG[type];
  const unit = config?.unit || '';
  
  switch (type) {
    case PERFORMANCE_TEST_TYPES.BANDWIDTH:
      if (value >= 1000) {
        return `${(value / 1000).toFixed(decimals)} Gbps`;
      }
      return `${value.toFixed(decimals)} Mbps`;
    
    case PERFORMANCE_TEST_TYPES.LATENCY:
    case PERFORMANCE_TEST_TYPES.JITTER:
      if (value >= 1000) {
        return `${(value / 1000).toFixed(decimals)}s`;
      }
      return `${value.toFixed(decimals)}ms`;
    
    case PERFORMANCE_TEST_TYPES.PACKET_LOSS:
      return `${value.toFixed(decimals)}%`;
    
    default:
      return `${value.toFixed(decimals)}${unit ? ` ${unit}` : ''}`;
  }
};

// Get performance health status based on thresholds
export const getPerformanceHealth = (value, type) => {
  const thresholds = PERFORMANCE_THRESHOLDS[type];
  if (!thresholds || typeof value !== 'number') return 'unknown';
  
  // For packet loss, lower is better (reverse logic)
  if (type === 'packetLoss') {
    if (value <= thresholds.excellent) return 'excellent';
    if (value <= thresholds.good) return 'good';
    if (value <= thresholds.fair) return 'fair';
    return 'poor';
  }
  
  // For latency and jitter, lower is better (reverse logic)
  if (type === 'latency' || type === 'jitter') {
    if (value <= thresholds.excellent) return 'excellent';
    if (value <= thresholds.good) return 'good';
    if (value <= thresholds.fair) return 'fair';
    return 'poor';
  }
  
  // For bandwidth, higher is better
  if (value >= thresholds.excellent) return 'excellent';
  if (value >= thresholds.good) return 'good';
  if (value >= thresholds.fair) return 'fair';
  return 'poor';
};

// Get health status color classes
export const getHealthStatusColor = (status) => {
  const colors = {
    excellent: {
      bg: 'bg-green-50',
      border: 'border-green-200',
      text: 'text-green-800',
      icon: 'text-green-500'
    },
    good: {
      bg: 'bg-blue-50',
      border: 'border-blue-200',
      text: 'text-blue-800',
      icon: 'text-blue-500'
    },
    fair: {
      bg: 'bg-yellow-50',
      border: 'border-yellow-200',
      text: 'text-yellow-800',
      icon: 'text-yellow-500'
    },
    poor: {
      bg: 'bg-red-50',
      border: 'border-red-200',
      text: 'text-red-800',
      icon: 'text-red-500'
    },
    unknown: {
      bg: 'bg-gray-50',
      border: 'border-gray-200',
      text: 'text-gray-800',
      icon: 'text-gray-500'
    }
  };
  
  return colors[status] || colors.unknown;
};

// Calculate trend between two values
export const calculateTrend = (current, previous, type = 'absolute') => {
  if (typeof current !== 'number' || typeof previous !== 'number' || previous === 0) {
    return { change: 0, percentage: 0, direction: 'stable' };
  }
  
  const change = current - previous;
  const percentage = (change / Math.abs(previous)) * 100;
  
  let direction = 'stable';
  if (Math.abs(percentage) > 5) {
    direction = change > 0 ? 'up' : 'down';
  }
  
  return {
    change: Math.abs(change),
    percentage: Math.abs(percentage),
    direction,
    isImprovement: type === 'reverse' ? change < 0 : change > 0
  };
};

// Validate test configuration
export const validateTestConfig = (config) => {
  const errors = [];
  const warnings = [];
  
  // Check required fields
  if (!config.testType) {
    errors.push('Test type is required');
  }
  
  if (!config.src_host) {
    errors.push('Source host is required');
  }
  
  if (!config.dst_host) {
    errors.push('Destination host is required');
  }
  
  if (config.src_host === config.dst_host) {
    errors.push('Source and destination hosts must be different');
  }
  
  // Check duration
  if (config.duration < 1 || config.duration > 3600) {
    errors.push('Duration must be between 1 and 3600 seconds');
  }
  
  // Test type specific validations
  const testConfig = TEST_TYPE_CONFIG[config.testType];
  if (testConfig) {
    if (config.duration > testConfig.defaultDuration * 10) {
      warnings.push(`Duration is much longer than recommended (${testConfig.defaultDuration}s)`);
    }
  }
  
  // Stress test specific validations
  if (config.testType === PERFORMANCE_TEST_TYPES.STRESS) {
    if (config.concurrent_flows < 1 || config.concurrent_flows > 50) {
      errors.push('Concurrent flows must be between 1 and 50');
    }
    
    if (config.concurrent_flows > 20) {
      warnings.push('High concurrent flows may impact system performance');
    }
  }
  
  // Comprehensive test validations
  if (config.testType === PERFORMANCE_TEST_TYPES.COMPREHENSIVE) {
    if (!config.test_types || config.test_types.length === 0) {
      errors.push('At least one test type must be selected for comprehensive testing');
    }
  }
  
  return {
    isValid: errors.length === 0,
    errors,
    warnings
  };
};

// Generate host pairs for testing - matches backend structure
export const generateHostPairs = (hosts) => {
  const pairs = [];
  const readyHosts = hosts.filter(h => 
    h.capabilities?.iperf3 && h.capabilities?.ping
  );
  
  for (let i = 0; i < readyHosts.length; i++) {
    for (let j = i + 1; j < readyHosts.length; j++) {
      pairs.push({
        key: `${readyHosts[i].name}->${readyHosts[j].name}`,
        src: readyHosts[i],
        dst: readyHosts[j],
        canTestBandwidth: readyHosts[i].capabilities.iperf3 && readyHosts[j].capabilities.iperf3,
        canTestLatency: readyHosts[i].capabilities.ping && readyHosts[j].capabilities.ping
      });
    }
  }
  
  return pairs;
};

// Create test session summary - matches backend response format
export const createTestSummary = (results) => {
  const summary = {
    total_tests: results.length,
    successful: results.filter(r => r.success).length,
    failed: results.filter(r => !r.success).length,
    duration_seconds: 0,
    test_types: [...new Set(results.map(r => r.test_type))],
    host_pairs: [...new Set(results.map(r => `${r.src_host}->${r.dst_host}`))]
  };
  
  summary.success_rate = summary.total_tests > 0 ? (summary.successful / summary.total_tests) * 100 : 0;
  
  return summary;
};

// Parse performance results for analysis
export const parsePerformanceResults = (results) => {
  const parsed = {
    bandwidth: [],
    latency: [],
    jitter: [],
    packetLoss: []
  };
  
  results.forEach(result => {
    if (!result.success) return;
    
    switch (result.test_type) {
      case 'bandwidth':
        if (result.bandwidth_mbps !== undefined) {
          parsed.bandwidth.push(result.bandwidth_mbps);
        }
        break;
      case 'latency':
        if (result.mean_ms !== undefined) {
          parsed.latency.push(result.mean_ms);
        }
        break;
      case 'jitter':
        if (result.jitter_ms !== undefined) {
          parsed.jitter.push(result.jitter_ms);
        }
        break;
      case 'packet_loss':
        if (result.packet_loss_percent !== undefined) {
          parsed.packetLoss.push(result.packet_loss_percent);
        }
        break;
    }
  });
  
  return parsed;
};

// Calculate statistics for metric array
export const calculateStatistics = (values) => {
  if (!Array.isArray(values) || values.length === 0) {
    return { mean: 0, min: 0, max: 0, std: 0 };
  }
  
  const mean = values.reduce((sum, val) => sum + val, 0) / values.length;
  const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
  const std = Math.sqrt(variance);
  
  return {
    mean,
    min: Math.min(...values),
    max: Math.max(...values),
    std
  };
};

// Normalize host data from backend response
export const normalizeHostData = (host) => {
  return {
    name: host.name || 'Unknown',
    ip: host.ip || 'Unknown',
    interfaces: host.interfaces || [],
    capabilities: {
      iperf3: Boolean(host.capabilities?.iperf3),
      ping: Boolean(host.capabilities?.ping),
      netstat: Boolean(host.capabilities?.netstat)
    },
    system_info: host.system_info || {}
  };
};

// Normalize monitoring data from backend response
export const normalizeMonitoringData = (data) => {
  return {
    active: Boolean(data.monitoring_active || data.active),
    interval: data.monitor_interval || data.interval || null,
    metrics: data.metrics || {},
    timestamp: data.timestamp || new Date().toISOString()
  };
};

// Export default configuration - updated for backend compatibility
export const DEFAULT_PERFORMANCE_CONFIG = {
  testConfig: {
    testType: PERFORMANCE_TEST_TYPES.COMPREHENSIVE,
    src_host: '',
    dst_host: '',
    duration: 30,
    test_types: ['bandwidth', 'latency'],
    parallel_streams: 1,
    concurrent_flows: 10,
    flow_size: '100M'
  },
  monitoringConfig: {
    interval: MONITORING_INTERVALS.FREQUENT,
    hosts: [],
    autoStart: false
  },
  reportConfig: {
    format: 'json',
    include_analysis: true,
    include_charts: false,
    analysis_type: 'comprehensive'
  }
};