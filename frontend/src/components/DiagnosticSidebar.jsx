// components/NetworkDiagnostic/components/DiagnosticSidebar.jsx
import React from 'react';
import { 
  Activity, 
  Wifi, 
  Router, 
  RefreshCw,
  TrendingUp,
  Network,
  Shield
} from 'lucide-react';

const DiagnosticSidebar = ({ 
  selectedTest, 
  setSelectedTest, 
  diagnosticLoading, 
  getDiagnosticSummary,
  onFetchData 
}) => {
  const testTabs = [
    { id: 'health', label: 'Health Check', icon: Activity, color: 'emerald' },
    { id: 'connectivity', label: 'Connectivity', icon: Wifi, color: 'blue' },
    { id: 'ping', label: 'Ping Test', icon: TrendingUp, color: 'purple' },
    { id: 'arp', label: 'ARP Tables', icon: Network, color: 'indigo' },
    { id: 'routing', label: 'Routing', icon: Router, color: 'cyan' },
    { id: 'flows', label: 'Switch Flows', icon: Shield, color: 'orange' }
  ];

  const summary = getDiagnosticSummary();

  return (
    <div className="w-80 bg-gray-50 border-r border-gray-200 p-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Diagnostic Tests</h3>
      <div className="space-y-3">
        {testTabs.map(tab => {
          const Icon = tab.icon;
          const isActive = selectedTest === tab.id;
          const isLoading = diagnosticLoading[tab.id] || (tab.id === 'ping' && diagnosticLoading.ping);
          
          return (
            <button
              key={tab.id}
              onClick={() => {
                setSelectedTest(tab.id);
                onFetchData(tab.id);
              }}
              className={`w-full flex items-center gap-3 p-4 rounded-xl text-left transition-all duration-200 ${
                isActive 
                  ? 'bg-indigo-100 text-indigo-700 border-2 border-indigo-200 shadow-sm' 
                  : 'hover:bg-white hover:shadow-sm text-gray-700 border-2 border-transparent'
              }`}
            >
              <div className={`p-2 rounded-lg ${isActive ? 'bg-indigo-200' : 'bg-gray-200'}`}>
                {isLoading ? (
                  <RefreshCw className="w-4 h-4 animate-spin" />
                ) : (
                  <Icon className="w-4 h-4" />
                )}
              </div>
              <div>
                <div className="font-semibold">{tab.label}</div>
                <div className="text-xs text-gray-500">
                  {isLoading ? 'Loading...' : 'Click to analyze'}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Quick Stats */}
      <div className="mt-6 p-4 bg-white rounded-xl border border-gray-200">
        <h4 className="text-sm font-semibold text-gray-900 mb-3">Quick Stats</h4>
        <div className="space-y-2 text-xs">
          <div className="flex justify-between">
            <span className="text-gray-500">Issues Found:</span>
            <span className={`font-semibold ${summary.issuesCount > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
              {summary.issuesCount}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Components:</span>
            <span className="font-semibold text-gray-700">
              {summary.componentsHealthy}/{summary.totalComponents} healthy
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Last Ping:</span>
            <span className={`font-semibold ${summary.lastPingSuccess ? 'text-emerald-600' : 'text-red-600'}`}>
              {summary.lastPingLoss}% loss
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DiagnosticSidebar;