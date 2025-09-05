import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  BarChart3,
  TrendingUp,
  TrendingDown,
  Gauge,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Activity,
  Zap,
  Network,
  Info,
  Settings,
  Eye,
  Loader,
  Copy,
  ExternalLink,
  Calendar,
  Filter,
  Target
} from 'lucide-react';

import { 
  PERFORMANCE_API_ENDPOINTS,
  formatMetric,
  getPerformanceHealth,
  getHealthStatusColor
} from '../utils/performanceUtils';

const PerformanceReports = ({
  apiCall,
  addLog,
  testHistory,
  loading,
  error
}) => {
  const [selectedSessions, setSelectedSessions] = useState([]);
  const [reportConfig, setReportConfig] = useState({
    format: 'json',
    include_analysis: true,
    include_charts: false,
    comparison_baseline: '',
    analysis_type: 'comprehensive'
  });
  const [generatedReports, setGeneratedReports] = useState([]);
  const [currentReport, setCurrentReport] = useState(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('generate');

  // Handle API responses - simplified since backend now returns consistent structure
  const handleApiResponse = (response, operation) => {
    if (response?.success) {
      return response.data;
    } else {
      const errorMsg = response?.error || 'Unknown error occurred';
      addLog?.(`❌ ${operation} failed: ${errorMsg}`, 'error', 'performance');
      throw new Error(errorMsg);
    }
  };

  // Generate comprehensive report
  const handleGenerateReport = async () => {
    if (selectedSessions.length === 0) return;

    setReportLoading(true);
    try {
      const reports = [];
      
      for (const sessionId of selectedSessions) {
        const response = await apiCall(PERFORMANCE_API_ENDPOINTS.REPORTS_GENERATE, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: sessionId,
            format: reportConfig.format,
            include_analysis: reportConfig.include_analysis,
            include_charts: reportConfig.include_charts
          })
        });
        
        const data = handleApiResponse(response, `Generate report for ${sessionId}`);
        
        if (data) {
          reports.push({
            sessionId,
            report: data,
            generatedAt: new Date().toISOString()
          });
        }
      }

      setGeneratedReports(prev => [...reports, ...prev]);
      if (reports.length > 0) {
        setCurrentReport(reports[0]);
        setActiveTab('view');
      }
      
      addLog?.(`📋 Generated ${reports.length} performance reports`, 'success', 'performance');
    } catch (error) {
      addLog?.(`❌ Report generation failed: ${error.message}`, 'error', 'performance');
    } finally {
      setReportLoading(false);
    }
  };

  // Download report
  const downloadReport = (report, filename) => {
    const dataStr = JSON.stringify(report, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || 'performance-report.json';
    link.click();
    URL.revokeObjectURL(url);
  };

  // Get trend indicator
  const getTrendIndicator = (current, baseline) => {
    if (!baseline || !current) return null;
    
    const change = ((current - baseline) / baseline) * 100;
    if (Math.abs(change) < 5) return { icon: null, color: 'gray', text: 'stable' };
    
    return {
      icon: change > 0 ? TrendingUp : TrendingDown,
      color: change > 0 ? 'red' : 'green',
      text: `${Math.abs(change).toFixed(1)}% ${change > 0 ? 'increase' : 'decrease'}`
    };
  };

  // Report summary component
  const ReportSummary = ({ report }) => {
    if (!report || !report.summary) return null;

    const { summary } = report;

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-blue-600">
                {summary.total_tests || 0}
              </div>
              <div className="text-sm text-gray-600">Total Tests</div>
            </div>
            <BarChart3 className="w-8 h-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-green-600">
                {summary.successful_tests || summary.successful || 0}
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
                {summary.failed_tests || summary.failed || 0}
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
                {summary.host_pairs_tested || summary.host_pairs?.length || 0}
              </div>
              <div className="text-sm text-gray-600">Host Pairs</div>
            </div>
            <Network className="w-8 h-8 text-purple-500" />
          </div>
        </div>
      </div>
    );
  };

  // Analysis component
  const AnalysisResults = ({ analysis }) => {
    if (!analysis) return null;

    return (
      <div className="space-y-6">
        {/* Performance Issues */}
        {analysis.performance_issues && analysis.performance_issues.length > 0 && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <h4 className="font-medium text-red-800 mb-3 flex items-center gap-2">
              <AlertTriangle className="w-5 h-5" />
              Performance Issues Detected
            </h4>
            <ul className="space-y-1">
              {analysis.performance_issues.map((issue, i) => (
                <li key={i} className="text-sm text-red-700 flex items-center gap-2">
                  <div className="w-1 h-1 bg-red-500 rounded-full"></div>
                  {issue}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Recommendations */}
        {analysis.recommendations && analysis.recommendations.length > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <h4 className="font-medium text-blue-800 mb-3 flex items-center gap-2">
              <Info className="w-5 h-5" />
              Recommendations
            </h4>
            <ul className="space-y-1">
              {analysis.recommendations.map((rec, i) => (
                <li key={i} className="text-sm text-blue-700 flex items-center gap-2">
                  <div className="w-1 h-1 bg-blue-500 rounded-full"></div>
                  {rec}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Statistics */}
        {analysis.statistics && (
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h4 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5" />
              Performance Statistics
            </h4>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {Object.entries(analysis.statistics).map(([metric, stats]) => (
                <div key={metric} className="space-y-2">
                  <h5 className="font-medium text-gray-800 capitalize">{metric}</h5>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="bg-gray-50 rounded p-2">
                      <div className="text-gray-600">Mean</div>
                      <div className="font-medium">
                        {formatMetric(stats.mean, metric)}
                      </div>
                    </div>
                    <div className="bg-gray-50 rounded p-2">
                      <div className="text-gray-600">Std Dev</div>
                      <div className="font-medium">
                        {formatMetric(stats.std, metric)}
                      </div>
                    </div>
                    <div className="bg-gray-50 rounded p-2">
                      <div className="text-gray-600">Min</div>
                      <div className="font-medium">
                        {formatMetric(stats.min, metric)}
                      </div>
                    </div>
                    <div className="bg-gray-50 rounded p-2">
                      <div className="text-gray-600">Max</div>
                      <div className="font-medium">
                        {formatMetric(stats.max, metric)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Trend Comparison */}
        {analysis.trend_comparison && (
          <div className="bg-white border border-gray-200 rounded-lg p-4">
            <h4 className="font-medium text-gray-900 mb-4 flex items-center gap-2">
              <TrendingUp className="w-5 h-5" />
              Trend Analysis
            </h4>
            
            <div className="space-y-4">
              {analysis.trend_comparison.improvements && analysis.trend_comparison.improvements.length > 0 && (
                <div>
                  <h5 className="font-medium text-green-800 mb-2">Improvements</h5>
                  <ul className="space-y-1">
                    {analysis.trend_comparison.improvements.map((improvement, i) => (
                      <li key={i} className="text-sm text-green-700 flex items-center gap-2">
                        <TrendingUp className="w-4 h-4" />
                        {improvement}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {analysis.trend_comparison.degradations && analysis.trend_comparison.degradations.length > 0 && (
                <div>
                  <h5 className="font-medium text-red-800 mb-2">Performance Degradations</h5>
                  <ul className="space-y-1">
                    {analysis.trend_comparison.degradations.map((degradation, i) => (
                      <li key={i} className="text-sm text-red-700 flex items-center gap-2">
                        <TrendingDown className="w-4 h-4" />
                        {degradation}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  const tabs = [
    { id: 'generate', label: 'Generate Reports', icon: FileText },
    { id: 'view', label: 'View Reports', icon: Eye },
    { id: 'analysis', label: 'Analysis', icon: BarChart3 }
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Performance Reports & Analysis</h3>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">
            {generatedReports.length} reports generated
          </span>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex border-b border-gray-200">
        {tabs.map(tab => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Generate Reports Tab */}
      {activeTab === 'generate' && (
        <div className="space-y-6">
          {/* Session Selection */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="font-medium text-gray-900 mb-3">Select Test Sessions</h4>
            
            {testHistory.length === 0 ? (
              <div className="text-center py-8">
                <Info className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h5 className="text-lg font-medium text-gray-900 mb-2">No Test Sessions Available</h5>
                <p className="text-gray-600">Run some performance tests first to generate reports.</p>
              </div>
            ) : (
              <div className="space-y-2 max-h-60 overflow-y-auto">
                {testHistory.slice(0, 20).map((session, index) => {
                  const metadata = session.metadata || {};
                  const summary = session.summary || {};
                  const sessionId = metadata.test_session_id || `session-${index}`;
                  const isSelected = selectedSessions.includes(sessionId);
                  
                  return (
                    <label
                      key={sessionId}
                      className="flex items-center gap-3 p-3 bg-white border border-gray-200 rounded-lg cursor-pointer hover:bg-gray-50"
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setSelectedSessions(prev => [...prev, sessionId]);
                          } else {
                            setSelectedSessions(prev => prev.filter(id => id !== sessionId));
                          }
                        }}
                        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                      
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900 capitalize">
                            {metadata.test_type || 'Unknown'}
                          </span>
                          <span className="text-sm text-gray-600">
                            {summary.successful || 0}/{summary.total_tests || 0} tests
                          </span>
                        </div>
                        <div className="text-sm text-gray-600">
                          {sessionId} • {
                            metadata.timestamp ? 
                            new Date(metadata.timestamp).toLocaleString() : 
                            'Unknown time'
                          }
                        </div>
                      </div>
                    </label>
                  );
                })}
              </div>
            )}
          </div>

          {/* Report Configuration */}
          <div className="bg-gray-50 rounded-lg p-4">
            <h4 className="font-medium text-gray-900 mb-3">Report Configuration</h4>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Report Format
                </label>
                <select
                  value={reportConfig.format}
                  onChange={(e) => setReportConfig(prev => ({ ...prev, format: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="json">JSON</option>
                  <option value="html">HTML</option>
                  <option value="pdf">PDF</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Analysis Type
                </label>
                <select
                  value={reportConfig.analysis_type}
                  onChange={(e) => setReportConfig(prev => ({ ...prev, analysis_type: e.target.value }))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="comprehensive">Comprehensive</option>
                  <option value="summary">Summary Only</option>
                  <option value="detailed">Detailed Analysis</option>
                </select>
              </div>

              <div className="md:col-span-2">
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={reportConfig.include_analysis}
                      onChange={(e) => setReportConfig(prev => ({ ...prev, include_analysis: e.target.checked }))}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Include Performance Analysis</span>
                  </label>
                  
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={reportConfig.include_charts}
                      onChange={(e) => setReportConfig(prev => ({ ...prev, include_charts: e.target.checked }))}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    <span className="text-sm text-gray-700">Include Charts and Graphs</span>
                  </label>
                </div>
              </div>
            </div>
          </div>

          {/* Generate Button */}
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-600">
              {selectedSessions.length} session{selectedSessions.length !== 1 ? 's' : ''} selected
            </div>
            
            <button
              onClick={handleGenerateReport}
              disabled={selectedSessions.length === 0 || reportLoading}
              className="flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              {reportLoading ? (
                <>
                  <Loader className="w-5 h-5 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <FileText className="w-5 h-5" />
                  Generate Report
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* View Reports Tab */}
      {activeTab === 'view' && (
        <div className="space-y-6">
          {generatedReports.length === 0 ? (
            <div className="text-center py-8 bg-gray-50 rounded-lg">
              <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h4 className="text-lg font-medium text-gray-900 mb-2">No Reports Generated</h4>
              <p className="text-gray-600">Generate some reports first to view them here.</p>
            </div>
          ) : (
            <>
              {/* Report List */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {generatedReports.map((reportItem, index) => (
                  <div
                    key={index}
                    className={`border rounded-lg p-4 cursor-pointer transition-all hover:shadow-md ${
                      currentReport === reportItem ? 'ring-2 ring-blue-500 border-blue-300' : 'border-gray-200'
                    }`}
                    onClick={() => setCurrentReport(reportItem)}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium text-gray-900">Report</h4>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          downloadReport(reportItem.report, `report-${reportItem.sessionId}.json`);
                        }}
                        className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                        title="Download Report"
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    </div>
                    
                    <div className="text-sm text-gray-600 space-y-1">
                      <div>Session: {reportItem.sessionId}</div>
                      <div>Generated: {new Date(reportItem.generatedAt).toLocaleString()}</div>
                      {reportItem.report.summary && (
                        <div>
                          Tests: {reportItem.report.summary.total_tests || 0} 
                          ({reportItem.report.summary.successful_tests || reportItem.report.summary.successful || 0} passed)
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Current Report Display */}
              {currentReport && (
                <div className="bg-white border border-gray-200 rounded-lg p-6">
                  <div className="flex items-center justify-between mb-6">
                    <h4 className="text-lg font-semibold text-gray-900">
                      Report: {currentReport.sessionId}
                    </h4>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => downloadReport(currentReport.report, `report-${currentReport.sessionId}.json`)}
                        className="flex items-center gap-2 px-3 py-2 text-blue-600 border border-blue-600 rounded-lg hover:bg-blue-50 transition-colors"
                      >
                        <Download className="w-4 h-4" />
                        Download
                      </button>
                    </div>
                  </div>

                  <ReportSummary report={currentReport.report} />
                  
                  {currentReport.report.analysis && (
                    <AnalysisResults analysis={currentReport.report.analysis} />
                  )}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Analysis Tab */}
      {activeTab === 'analysis' && (
        <div className="space-y-6">
          <div className="text-center py-8 bg-gray-50 rounded-lg">
            <BarChart3 className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h4 className="text-lg font-medium text-gray-900 mb-2">Advanced Analysis</h4>
            <p className="text-gray-600">
              Advanced analytics and comparison features coming soon.
            </p>
          </div>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-red-600" />
            <h4 className="font-medium text-red-800">Report Generation Error</h4>
          </div>
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}
    </div>
  );
};

export default PerformanceReports;