import React, { useState, useMemo } from 'react';
import {
  BarChart3,
  Clock,
  Filter,
  Search,
  RefreshCw,
  Calendar,
  TrendingUp,
  TrendingDown,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Eye,
  Download,
  Zap,
  Activity,
  Server,
  Gauge,
  Info,
  ExternalLink,
  Copy,
  Settings
} from 'lucide-react';

import { 
  formatMetric, 
  getPerformanceHealth, 
  getHealthStatusColor,
  PERFORMANCE_API_ENDPOINTS 
} from '../utils/performanceUtils';

const PerformanceResults = ({
  apiCall,
  addLog,
  testHistory,
  selectedSession,
  setSelectedSession,
  loading,
  error,
  onRefresh,
  filterOptions,
  setFilterOptions
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('timestamp');
  const [sortOrder, setSortOrder] = useState('desc');
  const [viewMode, setViewMode] = useState('list'); // 'list' or 'cards'

  // Filter and sort test history
  const filteredAndSortedHistory = useMemo(() => {
    let filtered = testHistory.filter(session => {
      const metadata = session.metadata || {};
      
      // Search filter
      const searchMatch = !searchTerm || 
        metadata.test_session_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        metadata.test_type?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (metadata.test_types && metadata.test_types.some(type => 
          type.toLowerCase().includes(searchTerm.toLowerCase())
        ));

      // Test type filter
      const typeMatch = !filterOptions.testType || 
        metadata.test_type === filterOptions.testType ||
        (metadata.test_types && metadata.test_types.includes(filterOptions.testType));

      // Status filter - based on backend response structure
      const summary = session.summary || {};
      const statusMatch = filterOptions.status === 'all' ||
        (filterOptions.status === 'success' && (summary.failed || 0) === 0) ||
        (filterOptions.status === 'failed' && (summary.successful || 0) === 0) ||
        (filterOptions.status === 'partial' && (summary.failed || 0) > 0 && (summary.successful || 0) > 0);

      // Date range filter
      const dateMatch = filterOptions.dateRange === 'all' || (() => {
        const sessionDate = new Date(metadata.timestamp || Date.now());
        const now = new Date();
        const dayInMs = 24 * 60 * 60 * 1000;
        
        switch (filterOptions.dateRange) {
          case 'today':
            return sessionDate.toDateString() === now.toDateString();
          case 'week':
            return now - sessionDate < 7 * dayInMs;
          case 'month':
            return now - sessionDate < 30 * dayInMs;
          default:
            return true;
        }
      })();

      return searchMatch && typeMatch && statusMatch && dateMatch;
    });

    // Sort results
    filtered.sort((a, b) => {
      let aValue, bValue;
      
      switch (sortBy) {
        case 'timestamp':
          aValue = new Date(a.metadata?.timestamp || 0);
          bValue = new Date(b.metadata?.timestamp || 0);
          break;
        case 'duration':
          aValue = a.summary?.duration_seconds || 0;
          bValue = b.summary?.duration_seconds || 0;
          break;
        case 'tests':
          aValue = a.summary?.total_tests || 0;
          bValue = b.summary?.total_tests || 0;
          break;
        case 'success_rate':
          aValue = a.summary?.total_tests > 0 ? (a.summary.successful / a.summary.total_tests) : 0;
          bValue = b.summary?.total_tests > 0 ? (b.summary.successful / b.summary.total_tests) : 0;
          break;
        default:
          aValue = a.metadata?.test_session_id || '';
          bValue = b.metadata?.test_session_id || '';
      }

      if (aValue < bValue) return sortOrder === 'asc' ? -1 : 1;
      if (aValue > bValue) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });

    return filtered;
  }, [testHistory, searchTerm, filterOptions, sortBy, sortOrder]);

  // Get test type icon
  const getTestTypeIcon = (testType) => {
    switch (testType) {
      case 'comprehensive': return BarChart3;
      case 'stress': return Zap;
      case 'custom': return Settings;
      case 'bandwidth': return Activity;
      case 'latency': return Clock;
      case 'jitter': return Gauge;
      case 'packet_loss': return AlertTriangle;
      default: return Activity;
    }
  };

  // Get status color based on session results
  const getStatusColor = (session) => {
    if (!session.summary) return 'gray';
    const { successful, failed } = session.summary;
    if ((failed || 0) === 0) return 'green';
    if ((successful || 0) === 0) return 'red';
    return 'yellow';
  };

  // Format test results for display - matches backend response structure
  const formatTestResult = (result) => {
    const formatted = {
      type: result.test_type,
      success: result.success,
      key_metric: null,
      details: []
    };

    if (result.success) {
      switch (result.test_type) {
        case 'bandwidth':
          formatted.key_metric = `${(result.bandwidth_mbps || 0).toFixed(1)} Mbps`;
          formatted.details = [
            `Throughput: ${(result.throughput_mbps || result.bandwidth_mbps || 0).toFixed(1)} Mbps`,
            `Retransmissions: ${result.retransmissions || 0}`,
            `Protocol: ${result.protocol || 'TCP'}`
          ];
          break;
        case 'latency':
          formatted.key_metric = `${(result.mean_ms || 0).toFixed(2)}ms avg`;
          formatted.details = [
            `Min: ${(result.min_ms || 0).toFixed(2)}ms`,
            `Max: ${(result.max_ms || 0).toFixed(2)}ms`,
            `Std Dev: ${(result.std_ms || 0).toFixed(2)}ms`
          ];
          if (result.packet_loss_percent !== undefined) {
            formatted.details.push(`Packet Loss: ${result.packet_loss_percent.toFixed(1)}%`);
          }
          break;
        case 'jitter':
          formatted.key_metric = `${(result.jitter_ms || 0).toFixed(2)}ms`;
          formatted.details = [
            `Avg Latency: ${(result.avg_latency_ms || 0).toFixed(2)}ms`,
            `Max Jitter: ${(result.max_jitter_ms || 0).toFixed(2)}ms`
          ];
          break;
        case 'packet_loss':
          formatted.key_metric = `${(result.packet_loss_percent || 0).toFixed(1)}%`;
          formatted.details = [
            `Packets Sent: ${result.packets_sent || 0}`,
            `Packets Lost: ${result.packets_lost || 0}`
          ];
          break;
        default:
          formatted.key_metric = 'Completed';
      }
    } else {
      formatted.key_metric = 'Failed';
      formatted.details = [result.error || 'Unknown error'];
    }

    return formatted;
  };

  // Copy session ID to clipboard
  const copySessionId = async (sessionId) => {
    try {
      await navigator.clipboard?.writeText?.(sessionId);
      addLog?.(`📋 Copied session ID: ${sessionId}`, 'info', 'performance');
    } catch {
      // Silently fail if clipboard not available
    }
  };

  // Generate report for session
  const generateReportForSession = async (sessionId) => {
    try {
      const response = await apiCall(PERFORMANCE_API_ENDPOINTS.REPORTS_GENERATE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          format: 'json',
          include_analysis: true
        })
      });

      if (response?.success) {
        addLog?.(`📋 Report generated for session ${sessionId}`, 'success', 'performance');
        // Download the report
        const dataStr = JSON.stringify(response.data, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `performance-report-${sessionId}.json`;
        link.click();
        URL.revokeObjectURL(url);
      } else {
        addLog?.(`❌ Failed to generate report: ${response?.error || 'Unknown error'}`, 'error', 'performance');
      }
    } catch (error) {
      addLog?.(`❌ Error generating report: ${error.message}`, 'error', 'performance');
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="animate-pulse">
          <div className="h-8 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 bg-gray-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-8">
        <AlertTriangle className="w-12 h-12 text-red-500 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Failed to Load Results</h3>
        <p className="text-gray-600 mb-4">{error}</p>
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Test Results</h3>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">
            {filteredAndSortedHistory.length} of {testHistory.length} sessions
          </span>
          <button
            onClick={onRefresh}
            className="flex items-center gap-2 px-3 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Filters and Search */}
      <div className="bg-gray-50 rounded-lg p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Search sessions..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Test Type Filter */}
          <select
            value={filterOptions.testType}
            onChange={(e) => setFilterOptions(prev => ({ ...prev, testType: e.target.value }))}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="">All Test Types</option>
            <option value="comprehensive">Comprehensive</option>
            <option value="stress">Stress Test</option>
            <option value="bandwidth">Bandwidth</option>
            <option value="latency">Latency</option>
            <option value="custom">Custom</option>
          </select>

          {/* Status Filter */}
          <select
            value={filterOptions.status}
            onChange={(e) => setFilterOptions(prev => ({ ...prev, status: e.target.value }))}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Status</option>
            <option value="success">Success Only</option>
            <option value="failed">Failed Only</option>
            <option value="partial">Partial Success</option>
          </select>

          {/* Date Range Filter */}
          <select
            value={filterOptions.dateRange}
            onChange={(e) => setFilterOptions(prev => ({ ...prev, dateRange: e.target.value }))}
            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Time</option>
            <option value="today">Today</option>
            <option value="week">Last Week</option>
            <option value="month">Last Month</option>
          </select>

          {/* Sort Options */}
          <div className="flex gap-2">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="timestamp">Sort by Date</option>
              <option value="duration">Sort by Duration</option>
              <option value="tests">Sort by Test Count</option>
              <option value="success_rate">Sort by Success Rate</option>
            </select>
            <button
              onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
              className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 transition-colors"
              title={`Sort ${sortOrder === 'asc' ? 'Descending' : 'Ascending'}`}
            >
              {sortOrder === 'asc' ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      {testHistory.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-blue-600">{testHistory.length}</div>
                <div className="text-sm text-gray-600">Total Sessions</div>
              </div>
              <BarChart3 className="w-8 h-8 text-blue-500" />
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-green-600">
                  {testHistory.filter(s => (s.summary?.failed || 0) === 0).length}
                </div>
                <div className="text-sm text-gray-600">Successful</div>
              </div>
              <CheckCircle className="w-8 h-8 text-green-500" />
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-red-600">
                  {testHistory.filter(s => (s.summary?.successful || 0) === 0).length}
                </div>
                <div className="text-sm text-gray-600">Failed</div>
              </div>
              <XCircle className="w-8 h-8 text-red-500" />
            </div>
          </div>

          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-2xl font-bold text-purple-600">
                  {testHistory.reduce((sum, s) => sum + (s.summary?.total_tests || 0), 0)}
                </div>
                <div className="text-sm text-gray-600">Total Tests</div>
              </div>
              <Activity className="w-8 h-8 text-purple-500" />
            </div>
          </div>
        </div>
      )}

      {/* Results List */}
      {filteredAndSortedHistory.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg">
          <Info className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h4 className="text-lg font-medium text-gray-900 mb-2">No Test Results</h4>
          <p className="text-gray-600">
            {testHistory.length === 0 ? 
              'No performance tests have been run yet.' : 
              'No sessions match your current filters.'
            }
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredAndSortedHistory.map((session, index) => {
            const metadata = session.metadata || {};
            const summary = session.summary || {};
            const statusColor = getStatusColor(session);
            const TestTypeIcon = getTestTypeIcon(metadata.test_type);
            const sessionId = metadata.test_session_id || `session-${index}`;
            const isSelected = selectedSession?.metadata?.test_session_id === sessionId;

            return (
              <div
                key={sessionId}
                className={`border rounded-lg p-4 cursor-pointer transition-all hover:shadow-md ${
                  isSelected ? 'ring-2 ring-blue-500 border-blue-300' : 'border-gray-200'
                } ${statusColor === 'green' ? 'bg-green-50' : 
                     statusColor === 'red' ? 'bg-red-50' : 
                     statusColor === 'yellow' ? 'bg-yellow-50' : 'bg-white'}`}
                onClick={() => setSelectedSession(isSelected ? null : session)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`p-2 rounded-lg ${
                      statusColor === 'green' ? 'bg-green-100' : 
                      statusColor === 'red' ? 'bg-red-100' : 
                      statusColor === 'yellow' ? 'bg-yellow-100' : 'bg-gray-100'
                    }`}>
                      <TestTypeIcon className={`w-5 h-5 ${
                        statusColor === 'green' ? 'text-green-600' : 
                        statusColor === 'red' ? 'text-red-600' : 
                        statusColor === 'yellow' ? 'text-yellow-600' : 'text-gray-600'
                      }`} />
                    </div>

                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-gray-900 capitalize">
                          {metadata.test_type || 'Unknown Test'}
                        </h4>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            copySessionId(sessionId);
                          }}
                          className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                          title="Copy Session ID"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="flex items-center gap-4 text-sm text-gray-600">
                        <span>{sessionId}</span>
                        <span>
                          {metadata.timestamp ? 
                            new Date(metadata.timestamp).toLocaleString() : 
                            'Unknown time'
                          }
                        </span>
                        {summary.duration_seconds && (
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3" />
                            {summary.duration_seconds.toFixed(1)}s
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-sm font-medium text-gray-900">
                        {summary.successful || 0}/{summary.total_tests || 0} Tests
                      </div>
                      <div className={`text-xs ${
                        statusColor === 'green' ? 'text-green-600' : 
                        statusColor === 'red' ? 'text-red-600' : 
                        statusColor === 'yellow' ? 'text-yellow-600' : 'text-gray-600'
                      }`}>
                        {statusColor === 'green' ? 'All Passed' : 
                         statusColor === 'red' ? 'All Failed' : 
                         statusColor === 'yellow' ? 'Partial' : 'Unknown'}
                      </div>
                    </div>
                    <Eye className="w-4 h-4 text-gray-400" />
                  </div>
                </div>

                {/* Expanded Details */}
                {isSelected && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {/* Test Results */}
                      <div>
                        <h5 className="font-medium text-gray-900 mb-3">Test Results</h5>
                        <div className="space-y-2 max-h-60 overflow-y-auto">
                          {session.results && session.results.length > 0 ? (
                            session.results.map((result, i) => {
                              const formatted = formatTestResult(result);
                              return (
                                <div key={i} className="bg-white rounded p-3 border border-gray-100">
                                  <div className="flex items-center justify-between mb-2">
                                    <div className="flex items-center gap-2">
                                      <span className="font-medium capitalize text-gray-900">
                                        {formatted.type}
                                      </span>
                                      <span className="text-sm text-gray-600">
                                        {result.src_host} → {result.dst_host}
                                      </span>
                                    </div>
                                    {formatted.success ? (
                                      <CheckCircle className="w-4 h-4 text-green-500" />
                                    ) : (
                                      <XCircle className="w-4 h-4 text-red-500" />
                                    )}
                                  </div>
                                  
                                  <div className="text-sm">
                                    <div className={`font-medium mb-1 ${
                                      formatted.success ? 'text-blue-600' : 'text-red-600'
                                    }`}>
                                      {formatted.key_metric}
                                    </div>
                                    {formatted.details.map((detail, j) => (
                                      <div key={j} className="text-gray-600 text-xs">
                                        {detail}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              );
                            })
                          ) : (
                            <p className="text-sm text-gray-500">No detailed results available</p>
                          )}
                        </div>
                      </div>

                      {/* Session Metadata */}
                      <div>
                        <h5 className="font-medium text-gray-900 mb-3">Session Details</h5>
                        <div className="bg-white rounded p-3 border border-gray-100 space-y-2 text-sm">
                          <div className="flex justify-between">
                            <span className="text-gray-600">Session ID:</span>
                            <span className="font-mono text-xs">{sessionId}</span>
                          </div>
                          <div className="flex justify-between">
                            <span className="text-gray-600">Test Type:</span>
                            <span className="capitalize">{metadata.test_type}</span>
                          </div>
                          {metadata.duration && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">Configured Duration:</span>
                              <span>{metadata.duration}s</span>
                            </div>
                          )}
                          {metadata.test_types && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">Test Types:</span>
                              <span className="text-right">
                                {metadata.test_types.join(', ')}
                              </span>
                            </div>
                          )}
                          {summary.duration_seconds && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">Actual Duration:</span>
                              <span>{summary.duration_seconds.toFixed(1)}s</span>
                            </div>
                          )}
                          {summary.success_rate !== undefined && (
                            <div className="flex justify-between">
                              <span className="text-gray-600">Success Rate:</span>
                              <span>{summary.success_rate.toFixed(1)}%</span>
                            </div>
                          )}
                        </div>

                        {/* Quick Actions */}
                        <div className="mt-4 flex flex-wrap gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              copySessionId(sessionId);
                            }}
                            className="px-3 py-1 bg-blue-100 text-blue-700 rounded text-sm hover:bg-blue-200 transition-colors"
                          >
                            Copy ID
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              generateReportForSession(sessionId);
                            }}
                            className="px-3 py-1 bg-green-100 text-green-700 rounded text-sm hover:bg-green-200 transition-colors"
                          >
                            Generate Report
                          </button>
                          <button
                            onClick={(e) => e.stopPropagation()}
                            className="px-3 py-1 bg-purple-100 text-purple-700 rounded text-sm hover:bg-purple-200 transition-colors"
                          >
                            Analyze
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default PerformanceResults;