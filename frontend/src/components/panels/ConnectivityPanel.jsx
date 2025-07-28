// components/NetworkDiagnostic/panels/ConnectivityPanel.jsx
import React from 'react';
import { 
  AlertTriangle, 
  CheckCircle, 
  RefreshCw,
  Zap,
  Eye,
  Settings
} from 'lucide-react';
import ActionButton from '../ActionButton.jsx';

const ConnectivityPanel = ({ 
  diagnosticData, 
  diagnosticLoading, 
  diagnosticErrors, 
  diagnoseConnectivity 
}) => {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-2xl font-bold text-gray-900">Connectivity Analysis</h3>
          <p className="text-gray-600">Detailed network connectivity diagnostics</p>
        </div>
        <ActionButton
          onClick={diagnoseConnectivity}
          loading={diagnosticLoading.connectivity}
          icon={<Eye className="w-4 h-4" />}
          label="Analyze"
          color="indigo"
        />
      </div>

      {diagnosticLoading.connectivity && (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-500" />
          <span className="ml-3 text-gray-600">Analyzing connectivity...</span>
        </div>
      )}

      {diagnosticErrors.connectivity && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-red-500" />
            <span className="text-red-700 font-medium">Error: {diagnosticErrors.connectivity}</span>
          </div>
        </div>
      )}

      {diagnosticData.connectivityIssues && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white border-2 border-gray-200 rounded-xl p-6">
            <h4 className="text-lg font-semibold mb-4 flex items-center gap-2 text-red-700">
              <AlertTriangle className="w-5 h-5" />
              Issues ({diagnosticData.connectivityIssues.issues?.length || 0})
            </h4>
            
            {diagnosticData.connectivityIssues.issues?.length > 0 ? (
              <div className="space-y-3">
                {diagnosticData.connectivityIssues.issues.map((issue, index) => (
                  <div key={index} className="bg-red-50 border border-red-200 rounded-lg p-3">
                    <span className="text-sm text-red-700">{issue}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto mb-3" />
                <p className="text-emerald-600 font-medium">No issues detected</p>
              </div>
            )}
          </div>

          <div className="bg-white border-2 border-gray-200 rounded-xl p-6">
            <h4 className="text-lg font-semibold mb-4 flex items-center gap-2 text-blue-700">
              <Zap className="w-5 h-5" />
              Suggestions ({diagnosticData.connectivityIssues.suggestions?.length || 0})
            </h4>
            
            {diagnosticData.connectivityIssues.suggestions?.length > 0 ? (
              <div className="space-y-3">
                {diagnosticData.connectivityIssues.suggestions.map((suggestion, index) => (
                  <div key={index} className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                    <span className="text-sm text-blue-700">{suggestion}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <Settings className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                <p className="text-gray-500 font-medium">No suggestions available</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ConnectivityPanel;