import React, { useMemo } from 'react';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Info,
  RefreshCw,
  Server,
  Monitor,
  BarChart3,
  Clock,
  Wifi,
  WifiOff,
  Activity
} from 'lucide-react';

const pick = (obj, path) =>
  path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj);

// Drill through possible nestings: status -> status.data -> status.data.data
const unwrapStatus = (raw) =>
  raw?.system_ready !== undefined ? raw : pick(raw, 'data.data') ?? pick(raw, 'data') ?? raw ?? {};

const normalizeHost = (host) => ({
  ...host,
  name: host?.name || host?.ip || 'unknown',
  capabilities: {
    iperf3: Boolean(host?.capabilities?.iperf3 ?? host?.iperf3_available),
    ping: Boolean(host?.capabilities?.ping ?? host?.ping_available),
    netstat: Boolean(host?.capabilities?.netstat ?? host?.netstat_available),
  },
});

const safeArray = (v) => (Array.isArray(v) ? v : []);

const PerformanceStatus = ({ status: rawStatus, loading, error, onRefresh }) => {
  // 🔧 Hooks must run before any early return
  const status = useMemo(() => unwrapStatus(rawStatus), [rawStatus]);

  // Extract data defensively (these will be ignored if we early-return for loading/error)
  const system_ready = Boolean(status?.system_ready);
  const network_running = Boolean(status?.network_running);
  const total_hosts =
    Number(status?.total_hosts ?? (Array.isArray(status?.hosts) ? status.hosts.length : 0)) || 0;
  const available_host_pairs = Number(status?.available_host_pairs ?? 0) || 0;

  const monitoring = {
    active: Boolean(status?.monitoring?.active),
    interval: Number(status?.monitoring?.interval ?? 0) || undefined,
  };

  const test_history = {
    total_sessions: Number(status?.test_history?.total_sessions ?? 0) || 0,
    last_test: status?.test_history?.last_test || null,
  };

  const capabilities = {
    max_test_duration: Number(status?.capabilities?.max_test_duration ?? 0) || 0,
    max_concurrent_tests: Number(status?.capabilities?.max_concurrent_tests ?? 0) || 0,
    supported_test_types: safeArray(status?.capabilities?.supported_test_types),
  };

  const prerequisites = {
    network_running: Boolean(status?.prerequisites?.network_running),
    hosts_available: Number(status?.prerequisites?.hosts_available ?? 0) || 0,
    iperf3_available: Number(status?.prerequisites?.iperf3_available ?? 0) || 0,
    ping_available: Number(status?.prerequisites?.ping_available ?? 0) || 0,
    issues: safeArray(status?.prerequisites?.issues),
    recommendations: safeArray(status?.prerequisites?.recommendations),
  };

  const hostsRaw = useMemo(() => safeArray(status?.hosts).map(normalizeHost), [status?.hosts]);

  const counts = useMemo(() => {
    const iperf3 = hostsRaw.filter((h) => h.capabilities.iperf3).length;
    const ping = hostsRaw.filter((h) => h.capabilities.ping).length;
    return { iperf3, ping };
  }, [hostsRaw]);

  const timestamp = status?.timestamp ? new Date(status.timestamp) : null;

  // ✅ Early returns AFTER hooks
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="animate-pulse">
          <div className="h-6 bg-gray-200 rounded w-1/4 mb-4"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="h-32 bg-gray-200 rounded-lg"></div>
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
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Status Check Failed</h3>
        <p className="text-gray-600 mb-4">{String(error)}</p>
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-black transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!status || Object.keys(status).length === 0) {
    return (
      <div className="text-center py-8">
        <Info className="w-12 h-12 text-gray-400 mx-auto mb-4" />
        <h3 className="text-lg font-semibold text-gray-900 mb-2">No Status Data</h3>
        <p className="text-gray-600 mb-4">Performance status information is not available.</p>
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-black transition-colors"
        >
          Load Status
        </button>
      </div>
    );
  }

  const statusCards = [
    {
      title: 'System Status',
      value: system_ready ? 'Ready' : 'Not Ready',
      icon: system_ready ? CheckCircle : XCircle,
      color: system_ready ? 'green' : 'red',
      description: system_ready ? 'All systems operational' : 'System not ready for testing',
    },
    {
      title: 'Network',
      value: network_running ? 'Running' : 'Stopped',
      icon: network_running ? Wifi : WifiOff,
      color: network_running ? 'green' : 'red',
      description: network_running ? 'Network is active' : 'Network is stopped',
    },
    {
      title: 'Hosts',
      value: total_hosts,
      icon: Server,
      color: 'blue',
      description: `${available_host_pairs} test pairs available`,
    },
    {
      title: 'Monitoring',
      value: monitoring.active ? 'Active' : 'Inactive',
      icon: Monitor,
      color: monitoring.active ? 'green' : 'gray',
      description:
        monitoring.active && monitoring.interval ? `${monitoring.interval}s interval` : 'Not monitoring',
    },
    {
      title: 'Test History',
      value: test_history.total_sessions || 0,
      icon: BarChart3,
      color: 'purple',
      description: test_history.last_test ? `Last: ${test_history.last_test}` : 'No tests run',
    },
    {
      title: 'Max Duration',
      value: `${capabilities.max_test_duration || 0}s`,
      icon: Clock,
      color: 'orange',
      description: `Up to ${capabilities.max_concurrent_tests || 0} concurrent tests`,
    },
  ];

  const getColorClasses = (color) => {
    const colors = {
      green: { text: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-200', icon: 'text-emerald-500' },
      red:   { text: 'text-red-600',     bg: 'bg-red-50',     border: 'border-red-200',     icon: 'text-red-500' },
      blue:  { text: 'text-gray-900',    bg: 'bg-gray-50',    border: 'border-gray-200',    icon: 'text-gray-600' },
      purple:{ text: 'text-gray-900',    bg: 'bg-gray-50',    border: 'border-gray-200',    icon: 'text-gray-600' },
      orange:{ text: 'text-gray-900',    bg: 'bg-gray-50',    border: 'border-gray-200',    icon: 'text-gray-600' },
      gray:  { text: 'text-gray-600',    bg: 'bg-gray-50',    border: 'border-gray-200',    icon: 'text-gray-500' },
    };
    return colors[color] || colors.gray;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">System Status Overview</h3>
        <div className="flex items-center gap-3">
          {timestamp && <span className="text-xs text-gray-500">Updated: {timestamp.toLocaleString()}</span>}
          <button
            onClick={onRefresh}
            className="flex items-center gap-2 px-3 py-2 text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {statusCards.map((card, index) => {
          const Icon = card.icon;
          const colorClasses = getColorClasses(card.color);
          return (
            <div
              key={index}
              className={`bg-white border rounded-lg p-4 hover:shadow-md transition-shadow ${colorClasses.border}`}
            >
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-medium text-gray-600">{card.title}</h4>
                <Icon className={`w-5 h-5 ${colorClasses.icon}`} />
              </div>
              <div className={`text-2xl font-bold ${colorClasses.text} mb-1`}>{card.value}</div>
              <p className="text-xs text-gray-500">{card.description}</p>
            </div>
          );
        })}
      </div>

      {/* Host List */}
      {hostsRaw.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
            <Server className="w-4 h-4" />
            Available Hosts ({hostsRaw.length})
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {hostsRaw.map((host, i) => (
              <div key={`${host.name}-${i}`} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <div>
                  <div className="font-medium text-sm">{host.name}</div>
                  <div className="text-xs text-gray-600">{host.ip}</div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1" title="iperf3">
                    {host.capabilities.iperf3 ? (
                      <CheckCircle className="w-4 h-4 text-emerald-500" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-500" />
                    )}
                    <span className="text-xs">iperf3</span>
                  </div>
                  <div className="flex items-center gap-1" title="ping">
                    {host.capabilities.ping ? (
                      <CheckCircle className="w-4 h-4 text-emerald-500" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-500" />
                    )}
                    <span className="text-xs">ping</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-3 text-xs text-gray-500">
            Capabilities: iperf3 {counts.iperf3}/{hostsRaw.length}, ping {counts.ping}/{hostsRaw.length}
          </div>
        </div>
      )}

      {/* Prerequisites Issues */}
      {prerequisites.issues.length > 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <h4 className="font-medium text-yellow-800 mb-2 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            Issues Found
          </h4>
          <ul className="text-sm text-yellow-700 space-y-1">
            {prerequisites.issues.map((issue, i) => (
              <li key={i} className="flex items-center gap-2">
                <div className="w-1 h-1 bg-yellow-600 rounded-full"></div>
                {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Prerequisites Recommendations */}
      {prerequisites.recommendations.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="font-medium text-blue-800 mb-2 flex items-center gap-2">
            <Info className="w-4 h-4" />
            Recommendations
          </h4>
          <ul className="text-sm text-blue-700 space-y-1">
            {prerequisites.recommendations.map((rec, i) => (
              <li key={i} className="flex items-center gap-2">
                <div className="w-1 h-1 bg-blue-600 rounded-full"></div>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Prerequisites Status Detail */}
      {Object.keys(prerequisites).length > 0 && (
        <div className="bg-gray-50 rounded-lg p-4">
          <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4" />
            System Prerequisites
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <h5 className="text-sm font-medium text-gray-700 mb-2">Requirements Status</h5>
              <ul className="space-y-1 text-sm">
                <li className="flex items-center gap-2">
                  {prerequisites.network_running ? (
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                  <span className={prerequisites.network_running ? 'text-emerald-700' : 'text-red-700'}>
                    Network Running
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  {prerequisites.hosts_available >= 2 ? (
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                  <span className={prerequisites.hosts_available >= 2 ? 'text-emerald-700' : 'text-red-700'}>
                    Sufficient Hosts ({prerequisites.hosts_available})
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  {prerequisites.iperf3_available > 0 ? (
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                  <span className={prerequisites.iperf3_available > 0 ? 'text-emerald-700' : 'text-red-700'}>
                    iperf3 Available ({prerequisites.iperf3_available})
                  </span>
                </li>
                <li className="flex items-center gap-2">
                  {prerequisites.ping_available > 0 ? (
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-500" />
                  )}
                  <span className={prerequisites.ping_available > 0 ? 'text-emerald-700' : 'text-red-700'}>
                    Ping Available ({prerequisites.ping_available})
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Supported Test Types */}
      {capabilities.supported_test_types.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
            <BarChart3 className="w-4 h-4" />
            Supported Test Types
          </h4>
          <div className="flex flex-wrap gap-2">
            {capabilities.supported_test_types.map((type) => (
              <span key={type} className="px-3 py-1 bg-gray-100 text-gray-900 rounded-full text-sm font-medium">
                {type}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* System Ready Status */}
      <div
        className={`rounded-lg p-4 ${
          system_ready ? 'bg-emerald-50 border border-emerald-200' : 'bg-yellow-50 border border-yellow-200'
        }`}
      >
        <h4
          className={`font-medium mb-2 flex items-center gap-2 ${
            system_ready ? 'text-emerald-800' : 'text-yellow-800'
          }`}
        >
          {system_ready ? (
            <>
              <CheckCircle className="w-4 h-4" />
              System Ready for Testing
            </>
          ) : (
            <>
              <AlertTriangle className="w-4 h-4" />
              System Not Ready
            </>
          )}
        </h4>
        <p className={`text-sm ${system_ready ? 'text-emerald-700' : 'text-yellow-700'}`}>
          {system_ready
            ? 'All prerequisites are met. You can now run performance tests and start monitoring.'
            : 'Your system is not ready for performance testing. Please address the issues above.'}
        </p>
      </div>
    </div>
  );
};

export default PerformanceStatus;
