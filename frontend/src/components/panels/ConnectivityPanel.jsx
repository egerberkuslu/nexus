import React, { useState } from 'react';
import {
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Zap,
  Eye,
  ChevronDown,
  ChevronRight,
  Clock,
  Activity,
  Wifi,
  WifiOff,
  Server,
  Users,
  Network,
  Router,
  Database,
  Monitor,
  XCircle,
  TrendingUp,
  AlertCircle,
  ChevronUp
} from 'lucide-react';

const ActionButton = ({ onClick, loading, icon, label, color = "indigo", size = "default" }) => {
  const sizeClasses = {
    sm: "px-3 py-1.5 text-sm",
    default: "px-4 py-2",
    lg: "px-6 py-3 text-lg"
  };
  
  const colorClasses = {
    indigo: "bg-indigo-600 hover:bg-indigo-700 border-indigo-600",
    emerald: "bg-emerald-600 hover:bg-emerald-700 border-emerald-600",
    amber: "bg-amber-600 hover:bg-amber-700 border-amber-600",
    red: "bg-red-600 hover:bg-red-700 border-red-600"
  };

  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`${sizeClasses[size]} ${colorClasses[color]} text-white border rounded-lg font-medium transition-all duration-200 flex items-center gap-2 shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed`}
    >
      {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : icon}
      {label}
    </button>
  );
};

const ConnectivityPanel = ({
  diagnosticData,
  diagnosticLoading,
  diagnosticErrors,
  diagnoseConnectivity
}) => {
  const [expandedSections, setExpandedSections] = useState({
    overview: true,
    issues: false,
    recommendations: false,
    controller: false,
    hostConnectivity: false,
    flows: false,
    interfaces: false,
    routing: false
  });

  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  const connectivity = diagnosticData.connectivityIssues;

  const getStatusConfig = (status) => {
    const configs = {
      healthy: {
        color: 'emerald',
        icon: CheckCircle,
        bgClass: 'bg-gradient-to-br from-emerald-50 to-emerald-100',
        borderClass: 'border-emerald-200',
        textClass: 'text-emerald-800'
      },
      issues_found: {
        color: 'amber',
        icon: AlertTriangle,
        bgClass: 'bg-gradient-to-br from-amber-50 to-amber-100',
        borderClass: 'border-amber-200',
        textClass: 'text-amber-800'
      },
      error: {
        color: 'red',
        icon: WifiOff,
        bgClass: 'bg-gradient-to-br from-red-50 to-red-100',
        borderClass: 'border-red-200',
        textClass: 'text-red-800'
      },
      default: {
        color: 'gray',
        icon: Activity,
        bgClass: 'bg-gradient-to-br from-gray-50 to-gray-100',
        borderClass: 'border-gray-200',
        textClass: 'text-gray-800'
      }
    };
    return configs[status] || configs.default;
  };

  const StatCard = ({ icon: Icon, title, value, status, color = "blue" }) => (
    <div className="bg-white rounded-lg border border-gray-200 p-4 shadow-sm hover:shadow-md transition-all duration-200">
      <div className="flex items-center justify-between mb-2">
        <div className={`p-1.5 rounded-md bg-${color}-50`}>
          <Icon className={`w-4 h-4 text-${color}-600`} />
        </div>
        {status && (
          <div className="flex items-center">
            {status === 'healthy' ? (
              <CheckCircle className="w-4 h-4 text-emerald-500" />
            ) : (
              <XCircle className="w-4 h-4 text-red-500" />
            )}
          </div>
        )}
      </div>
      <div className="space-y-1">
        <p className="text-lg font-bold text-gray-900">{value}</p>
        <p className="text-xs text-gray-600">{title}</p>
      </div>
    </div>
  );

  const CollapsibleSection = ({ 
    title, 
    icon: Icon, 
    isExpanded, 
    onToggle, 
    children, 
    badge,
    className = ""
  }) => (
    <div className={`bg-white rounded-lg border border-gray-200 shadow-sm ${className}`}>
      <button
        onClick={onToggle}
        className="w-full p-4 text-left hover:bg-gray-50 transition-colors duration-200 rounded-t-lg"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-gray-100 rounded-md">
              <Icon className="w-4 h-4 text-gray-700" />
            </div>
            <div className="flex items-center gap-2">
              <h4 className="text-base font-semibold text-gray-900">{title}</h4>
              {badge !== undefined && (
                <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs font-medium rounded-full">
                  {badge}
                </span>
              )}
            </div>
          </div>
          {isExpanded ? (
            <ChevronUp className="w-4 h-4 text-gray-500" />
          ) : (
            <ChevronDown className="w-4 h-4 text-gray-500" />
          )}
        </div>
      </button>
      {isExpanded && (
        <div className="px-4 pb-4 border-t border-gray-100">
          <div className="pt-3">
            {children}
          </div>
        </div>
      )}
    </div>
  );

  const PingResultsGrid = ({ pingResults }) => {
    const successCount = Object.values(pingResults).filter(result => result === 'success').length;
    const totalCount = Object.keys(pingResults).length;

    return (
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h5 className="font-medium text-gray-900 text-sm">Connectivity Tests</h5>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${successCount === totalCount ? 'bg-emerald-500' : successCount > 0 ? 'bg-amber-500' : 'bg-red-500'}`}></div>
            <span className="text-xs text-gray-700">
              {successCount}/{totalCount} successful
            </span>
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-48 overflow-y-auto">
          {Object.entries(pingResults).map(([pair, result]) => (
            <div 
              key={pair}
              className={`flex items-center justify-between p-2 rounded border text-xs ${
                result === 'success' 
                  ? 'border-emerald-200 bg-emerald-50' 
                  : 'border-red-200 bg-red-50'
              }`}
            >
              <span className="font-medium text-gray-700 truncate">{pair}</span>
              <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                result === 'success' 
                  ? 'bg-emerald-100 text-emerald-800' 
                  : 'bg-red-100 text-red-800'
              }`}>
                {result}
              </span>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const FlowTable = ({ switchId, flowData }) => (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h5 className="font-medium text-gray-900 text-sm">{switchId}</h5>
        <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs font-medium rounded">
          {flowData.flow_count || 0} flows
        </span>
      </div>
      {flowData.flows && flowData.flows.length > 0 ? (
        <div className="bg-gray-50 rounded border border-gray-200 overflow-hidden">
          <div className="max-h-40 overflow-y-auto">
            <div className="p-2 space-y-1">
              {flowData.flows.slice(0, 5).map((flow, index) => (
                <div key={index} className="text-xs font-mono text-gray-600 bg-white p-1.5 rounded border">
                  {flow.trim()}
                </div>
              ))}
              {flowData.flows.length > 5 && (
                <div className="text-xs text-gray-500 text-center py-1">
                  +{flowData.flows.length - 5} more flows
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="text-center py-4 text-gray-500">
          <Activity className="w-6 h-6 mx-auto mb-1 opacity-50" />
          <p className="text-xs">No flows configured</p>
        </div>
      )}
    </div>
  );

  const RoutingTable = ({ routerId, routingData }) => (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h5 className="font-medium text-gray-900 text-sm">{routerId}</h5>
        <span className="px-2 py-0.5 bg-green-100 text-green-800 text-xs font-medium rounded">
          {routingData.route_count || 0} routes
        </span>
      </div>
      <div className="space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <div className="flex justify-between items-center p-2 bg-gray-50 rounded border border-gray-200 text-xs">
            <span className="text-gray-600">IP Forwarding:</span>
            <span className={routingData.ip_forwarding ? 'text-emerald-600 font-medium' : 'text-red-600 font-medium'}>
              {routingData.ip_forwarding ? 'Enabled' : 'Disabled'}
            </span>
          </div>
          <div className="flex justify-between items-center p-2 bg-gray-50 rounded border border-gray-200 text-xs">
            <span className="text-gray-600">Default Route:</span>
            <span className={routingData.has_default_route ? 'text-emerald-600 font-medium' : 'text-amber-600 font-medium'}>
              {routingData.has_default_route ? 'Present' : 'Missing'}
            </span>
          </div>
        </div>
        {routingData.routes && (
          <div className="bg-gray-50 rounded border border-gray-200 overflow-hidden">
            <div className="max-h-40 overflow-y-auto">
              <div className="p-2 space-y-1">
                {routingData.routes.split('\n').slice(0, 8).map((route, index) => (
                  route.trim() && (
                    <div key={index} className="text-xs font-mono text-gray-600 bg-white p-1.5 rounded border">
                      {route.trim()}
                    </div>
                  )
                ))}
                {routingData.routes.split('\n').filter(r => r.trim()).length > 8 && (
                  <div className="text-xs text-gray-500 text-center py-1">
                    +{routingData.routes.split('\n').filter(r => r.trim()).length - 8} more routes
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  const InterfaceTable = ({ nodeId, interfaces }) => (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h5 className="font-medium text-gray-900 text-sm">{nodeId}</h5>
        <span className="px-2 py-0.5 bg-blue-100 text-blue-800 text-xs font-medium rounded">
          {Object.values(interfaces).filter(intf => intf.up).length}/{Object.keys(interfaces).length} up
        </span>
      </div>
      <div className="bg-gray-50 rounded border border-gray-200 overflow-hidden">
        <div className="max-h-40 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="bg-gray-100 sticky top-0">
              <tr>
                <th className="px-2 py-2 text-left font-medium text-gray-700">Interface</th>
                <th className="px-2 py-2 text-left font-medium text-gray-700">Status</th>
                <th className="px-2 py-2 text-left font-medium text-gray-700">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {Object.entries(interfaces).map(([intfName, intfData]) => (
                <tr key={intfName} className="hover:bg-gray-100 transition-colors">
                  <td className="px-2 py-2 font-medium text-gray-900">{intfData.name}</td>
                  <td className="px-2 py-2">
                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                      intfData.up 
                        ? 'bg-emerald-100 text-emerald-800' 
                        : 'bg-red-100 text-red-800'
                    }`}>
                      {intfData.up ? 'UP' : 'DOWN'}
                    </span>
                  </td>
                  <td className="px-2 py-2 font-mono text-gray-600">{intfData.ip || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  if (diagnosticLoading.connectivity) {
    return (
      <div className="space-y-4">
        <div>
          <h3 className="text-xl font-bold text-gray-900">Connectivity Analysis</h3>
          <p className="text-gray-600 text-sm">Comprehensive network connectivity diagnostics</p>
        </div>
        
        <div className="flex items-center justify-center py-12 bg-white rounded-lg border border-gray-200">
          <div className="text-center">
            <RefreshCw className="w-8 h-8 animate-spin text-indigo-500 mx-auto mb-3" />
            <h4 className="font-semibold text-gray-900 mb-1">Analyzing Network</h4>
            <p className="text-gray-600 text-sm">Running connectivity diagnostics...</p>
          </div>
        </div>
      </div>
    );
  }

  if (diagnosticErrors.connectivity) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-bold text-gray-900">Connectivity Analysis</h3>
            <p className="text-gray-600 text-sm">Comprehensive network connectivity diagnostics</p>
          </div>
          <ActionButton
            onClick={diagnoseConnectivity}
            icon={<RefreshCw className="w-4 h-4" />}
            label="Retry"
            color="indigo"
            size="sm"
          />
        </div>
        
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex items-start gap-2">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="font-semibold text-red-800 mb-1">Analysis Failed</h4>
              <p className="text-red-700 text-sm">{diagnosticErrors.connectivity}</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!connectivity) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-bold text-gray-900">Connectivity Analysis</h3>
            <p className="text-gray-600 text-sm">Comprehensive network connectivity diagnostics</p>
          </div>
          <ActionButton
            onClick={diagnoseConnectivity}
            icon={<Eye className="w-4 h-4" />}
            label="Start Analysis"
            color="indigo"
            size="sm"
          />
        </div>
        
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <Network className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <h4 className="font-semibold text-gray-900 mb-1">Ready to Analyze</h4>
          <p className="text-gray-600 text-sm mb-4">Click "Start Analysis" to begin comprehensive connectivity testing</p>
        </div>
      </div>
    );
  }

  const statusConfig = getStatusConfig(connectivity.status);
  const StatusIcon = statusConfig.icon;

  return (
    <div className="space-y-4">
      {/* Compact Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-xl font-bold text-gray-900">Connectivity Analysis</h3>
          <p className="text-gray-600 text-sm">Network connectivity diagnostics</p>
        </div>
        <ActionButton
          onClick={diagnoseConnectivity}
          icon={<RefreshCw className="w-4 h-4" />}
          label="Re-analyze"
          color="indigo"
          size="sm"
        />
      </div>

      {/* Compact Status Hero */}
      <div className={`rounded-lg border p-4 ${statusConfig.bgClass} ${statusConfig.borderClass}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-white rounded-lg shadow-sm">
              <StatusIcon className={`w-6 h-6 text-${statusConfig.color}-600`} />
            </div>
            <div>
              <h4 className={`text-lg font-bold ${statusConfig.textClass} capitalize`}>
                {connectivity.status?.replace('_', ' ') || 'Unknown Status'}
              </h4>
              <p className="text-gray-700 text-sm">{connectivity.message}</p>
            </div>
          </div>
          {connectivity.timestamp && (
            <div className="flex items-center gap-1 text-gray-600">
              <Clock className="w-4 h-4" />
              <span className="text-xs">
                {new Date(connectivity.timestamp).toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Compact Overview Stats */}
      {connectivity.detailed_results && (
        <CollapsibleSection
          title="System Overview"
          icon={Monitor}
          isExpanded={expandedSections.overview}
          onToggle={() => toggleSection('overview')}
        >
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard
              icon={Server}
              title="Controller"
              value={connectivity.detailed_results.controller?.details?.controller_running ? "Online" : "Offline"}
              status={connectivity.detailed_results.controller?.details?.controller_running ? "healthy" : "error"}
              color="purple"
            />
            <StatCard
              icon={Network}
              title="Switches"
              value={connectivity.detailed_results.switch_controller?.details?.switches_checked || 0}
              color="blue"
            />
            <StatCard
              icon={Users}
              title="Hosts"
              value={connectivity.detailed_results.host_connectivity?.details?.hosts_checked || 0}
              color="emerald"
            />
            <StatCard
              icon={Activity}
              title="Active Flows"
              value={Object.keys(connectivity.detailed_results.flows?.details?.flow_tables || {}).reduce((sum, sw) =>
                sum + (connectivity.detailed_results.flows.details.flow_tables[sw].flow_count || 0), 0
              )}
              color="amber"
            />
          </div>
        </CollapsibleSection>
      )}

      {/* Compact Issues and Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <CollapsibleSection
          title="Issues"
          icon={AlertTriangle}
          badge={connectivity.issues?.length || 0}
          isExpanded={expandedSections.issues}
          onToggle={() => toggleSection('issues')}
        >
          {connectivity.issues?.length > 0 ? (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {connectivity.issues.map((issue, index) => (
                <div key={index} className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded text-sm">
                  <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                  <span className="text-red-700">{issue}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6">
              <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
              <p className="text-emerald-600 font-medium text-sm">No issues detected</p>
            </div>
          )}
        </CollapsibleSection>

        <CollapsibleSection
          title="Recommendations"
          icon={Zap}
          badge={connectivity.recommendations?.length || 0}
          isExpanded={expandedSections.recommendations}
          onToggle={() => toggleSection('recommendations')}
        >
          {connectivity.recommendations?.length > 0 ? (
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {connectivity.recommendations.map((recommendation, index) => (
                <div key={index} className="flex items-start gap-2 p-3 bg-blue-50 border border-blue-200 rounded text-sm">
                  <Zap className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
                  <span className="text-blue-700">{recommendation}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-6">
              <TrendingUp className="w-8 h-8 text-gray-400 mx-auto mb-2" />
              <p className="text-gray-500 font-medium text-sm">No recommendations</p>
            </div>
          )}
        </CollapsibleSection>
      </div>

      {/* Compact Detailed Analysis Sections */}
      {connectivity.detailed_results && (
        <div className="space-y-4">
          {/* Controller Details */}
          {connectivity.detailed_results.controller && (
            <CollapsibleSection
              title="Controller Status"
              icon={Server}
              isExpanded={expandedSections.controller}
              onToggle={() => toggleSection('controller')}
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="space-y-2">
                  <h5 className="font-medium text-gray-900">Connection Status</h5>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center py-1 border-b border-gray-200">
                      <span className="text-gray-600">Controller Running</span>
                      <span className={`font-medium ${connectivity.detailed_results.controller.details?.controller_running ? 'text-emerald-600' : 'text-red-600'}`}>
                        {connectivity.detailed_results.controller.details?.controller_running ? 'Yes' : 'No'}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-1">
                      <span className="text-gray-600">Port Accessible</span>
                      <span className={`font-medium ${connectivity.detailed_results.controller.details?.port_accessible ? 'text-emerald-600' : 'text-red-600'}`}>
                        {connectivity.detailed_results.controller.details?.port_accessible ? 'Yes' : 'No'}
                      </span>
                    </div>
                  </div>
                </div>
                {connectivity.detailed_results.controller.details?.controller_status && (
                  <div className="space-y-2">
                    <h5 className="font-medium text-gray-900">Controller Details</h5>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between items-center py-1 border-b border-gray-200">
                        <span className="text-gray-600">Type</span>
                        <span className="font-mono">{connectivity.detailed_results.controller.details.controller_status.type}</span>
                      </div>
                      <div className="flex justify-between items-center py-1 border-b border-gray-200">
                        <span className="text-gray-600">Port</span>
                        <span className="font-mono">{connectivity.detailed_results.controller.details.controller_status.port}</span>
                      </div>
                      <div className="flex justify-between items-center py-1">
                        <span className="text-gray-600">Uptime</span>
                        <span className="font-mono">{connectivity.detailed_results.controller.details.controller_status.uptime}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </CollapsibleSection>
          )}

          {/* Host Connectivity */}
          {connectivity.detailed_results.host_connectivity && (
            <CollapsibleSection
              title="Host Connectivity"
              icon={Users}
              badge={`${connectivity.detailed_results.host_connectivity.details?.failed_tests || 0} failed`}
              isExpanded={expandedSections.hostConnectivity}
              onToggle={() => toggleSection('hostConnectivity')}
            >
              {connectivity.detailed_results.host_connectivity.details?.ping_results && (
                <PingResultsGrid pingResults={connectivity.detailed_results.host_connectivity.details.ping_results} />
              )}
            </CollapsibleSection>
          )}

          {/* Flow Tables */}
          {connectivity.detailed_results.flows && (
            <CollapsibleSection
              title="OpenFlow Tables"
              icon={Activity}
              isExpanded={expandedSections.flows}
              onToggle={() => toggleSection('flows')}
            >
              <div className="space-y-4">
                {Object.entries(connectivity.detailed_results.flows.details?.flow_tables || {}).map(([switchId, flowData]) => (
                  <FlowTable key={switchId} switchId={switchId} flowData={flowData} />
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Network Interfaces */}
          {connectivity.detailed_results.interfaces && (
            <CollapsibleSection
              title="Network Interfaces"
              icon={Wifi}
              isExpanded={expandedSections.interfaces}
              onToggle={() => toggleSection('interfaces')}
            >
              <div className="space-y-4">
                {Object.entries(connectivity.detailed_results.interfaces.details?.interfaces || {}).map(([nodeId, interfaces]) => (
                  <InterfaceTable key={nodeId} nodeId={nodeId} interfaces={interfaces} />
                ))}
              </div>
            </CollapsibleSection>
          )}

          {/* Routing Tables */}
          {connectivity.detailed_results.routing && (
            <CollapsibleSection
              title="Routing Tables"
              icon={Router}
              isExpanded={expandedSections.routing}
              onToggle={() => toggleSection('routing')}
            >
              <div className="space-y-4">
                {Object.entries(connectivity.detailed_results.routing.details?.routing_tables || {}).map(([routerId, routingData]) => (
                  <RoutingTable key={routerId} routerId={routerId} routingData={routingData} />
                ))}
              </div>
            </CollapsibleSection>
          )}
        </div>
      )}
    </div>
  );
};

export default ConnectivityPanel;