import React from 'react';
import { 
  Activity, 
  AlertTriangle, 
  CheckCircle, 
  XCircle, 
  Zap,
  TrendingUp
} from 'lucide-react';

const DiagnosticWidget = ({ 
  diagnosticSummary, 
  onOpenDiagnostics, 
  onRunQuickCheck,
  loading = false 
}) => {
  const {
    overallStatus,
    issuesCount,
    suggestionsCount,
    lastPingSuccess,
    lastPingLoss,
    componentsHealthy,
    totalComponents,
    hasData
  } = diagnosticSummary;

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'text-green-600 bg-green-50 border-green-200';
      case 'warning': return 'text-yellow-600 bg-yellow-50 border-yellow-200';
      case 'critical': return 'text-red-600 bg-red-50 border-red-200';
      default: return 'text-gray-600 bg-gray-50 border-gray-200';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="w-4 h-4" />;
      case 'warning': return <AlertTriangle className="w-4 h-4" />;
      case 'critical': return <XCircle className="w-4 h-4" />;
      default: return <Activity className="w-4 h-4" />;
    }
  };

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <Activity className="w-4 h-4" />
          Network Health
        </h3>
        
        <div className="flex items-center gap-2">
          <button
            onClick={onRunQuickCheck}
            disabled={loading}
            className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50"
            title="Run quick health check"
          >
            {loading ? 'Checking...' : 'Quick Check'}
          </button>
          
          <button
            onClick={onOpenDiagnostics}
            className="text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 px-2 py-1 rounded"
          >
            Diagnose
          </button>
        </div>
      </div>

      {hasData ? (
        <div className="space-y-3">
          {/* Overall Status */}
          <div className={`flex items-center justify-between p-2 rounded border ${getStatusColor(overallStatus)}`}>
            <div className="flex items-center gap-2">
              {getStatusIcon(overallStatus)}
              <span className="text-sm font-medium capitalize">{overallStatus}</span>
            </div>
            
            {issuesCount > 0 && (
              <span className="text-xs bg-white/70 px-2 py-1 rounded">
                {issuesCount} issues
              </span>
            )}
          </div>

          {/* Quick Stats Grid */}
          <div className="grid grid-cols-2 gap-2 text-xs">
            {/* Components Health */}
            <div className="bg-gray-50 p-2 rounded">
              <div className="text-gray-600">Components</div>
              <div className="font-semibold">
                {componentsHealthy}/{totalComponents} healthy
              </div>
            </div>

            {/* Last Ping */}
            <div className="bg-gray-50 p-2 rounded">
              <div className="text-gray-600">Last Ping</div>
              <div className={`font-semibold ${lastPingSuccess ? 'text-green-600' : 'text-red-600'}`}>
                {lastPingLoss}% loss
              </div>
            </div>
          </div>

          {/* Issues & Suggestions */}
          {(issuesCount > 0 || suggestionsCount > 0) && (
            <div className="flex items-center justify-between text-xs">
              {issuesCount > 0 && (
                <div className="flex items-center gap-1 text-red-600">
                  <AlertTriangle className="w-3 h-3" />
                  <span>{issuesCount} issues</span>
                </div>
              )}
              
              {suggestionsCount > 0 && (
                <div className="flex items-center gap-1 text-blue-600">
                  <Zap className="w-3 h-3" />
                  <span>{suggestionsCount} suggestions</span>
                </div>
              )}
            </div>
          )}

          {/* Quick Actions */}
          {issuesCount > 0 && (
            <button
              onClick={onOpenDiagnostics}
              className="w-full text-xs bg-yellow-100 hover:bg-yellow-200 text-yellow-800 py-2 rounded flex items-center justify-center gap-1"
            >
              <TrendingUp className="w-3 h-3" />
              View Issues & Fixes
            </button>
          )}
        </div>
      ) : (
        <div className="text-center py-4">
          <Activity className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-500 mb-3">No diagnostic data available</p>
          <button
            onClick={onRunQuickCheck}
            disabled={loading}
            className="text-sm bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded disabled:opacity-50"
          >
            {loading ? 'Running...' : 'Run Health Check'}
          </button>
        </div>
      )}
    </div>
  );
};

export default DiagnosticWidget;