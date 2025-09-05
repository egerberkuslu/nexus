import React, { useState, useMemo } from 'react';
import {
  Search,
  Filter,
  RefreshCw,
  Server,
  Monitor,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Network,
  Wifi,
  Terminal,
  Copy,
  Info,
  Eye
} from 'lucide-react';

const HostDiscovery = ({ hosts = [], loading, error, onRefresh }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filterCapability, setFilterCapability] = useState('all');
  const [selectedHost, setSelectedHost] = useState(null);

  // Normalize hosts data - simplified since backend now returns consistent structure
  const safeHosts = useMemo(() => {
    // Handle array of hosts directly
    const hostsList = Array.isArray(hosts) ? hosts : [];

    // Normalize host data
    return hostsList.map((host, idx) => ({
      key: host.name ? `${host.name}-${host.ip || idx}` : `host-${idx}`,
      name: host.name || host.ip || 'Unknown',
      ip: host.ip || '—',
      capabilities: {
        iperf3: Boolean(host.capabilities?.iperf3 ?? host.iperf3_available ?? false),
        ping: Boolean(host.capabilities?.ping ?? host.ping_available ?? false),
        netstat: Boolean(host.capabilities?.netstat ?? host.netstat_available ?? false),
      },
      interfaces: Array.isArray(host.interfaces) ? host.interfaces : [],
      system_info: host.system_info && typeof host.system_info === 'object' ? host.system_info : {},
    }));
  }, [hosts]);

  const filteredHosts = useMemo(() => {
    const term = (searchTerm || '').toLowerCase();

    return safeHosts.filter((h) => {
      const name = (h.name || '').toLowerCase();
      const ip = (h.ip || '').toLowerCase();
      const caps = h.capabilities || {};

      const matchesSearch = name.includes(term) || ip.includes(term);

      const matchesCapability =
        filterCapability === 'all' ||
        (filterCapability === 'iperf3' && caps.iperf3) ||
        (filterCapability === 'ping' && caps.ping) ||
        (filterCapability === 'ready' && caps.iperf3 && caps.ping);

      return matchesSearch && matchesCapability;
    });
  }, [safeHosts, searchTerm, filterCapability]);

  const copyToClipboard = async (text) => {
    try {
      await navigator?.clipboard?.writeText?.(String(text ?? ''));
    } catch {
      // Silently ignore if clipboard isn't available
    }
  };

  const getCapabilityStatus = (capability) =>
    capability ? (
      <CheckCircle className="w-4 h-4 text-green-500" />
    ) : (
      <XCircle className="w-4 h-4 text-red-500" />
    );

  const getHostStatusColor = (host) => {
    const caps = host.capabilities || {};
    // For performance testing, we need both iperf3 and ping
    if (caps.iperf3 && caps.ping) return 'green';
    if (caps.iperf3 || caps.ping) return 'yellow';
    return 'red';
  };

  const performanceReadyCount = useMemo(
    () => safeHosts.filter((h) => h.capabilities?.iperf3 && h.capabilities?.ping).length,
    [safeHosts]
  );

  // Generate test pairs from ready hosts
  const readyPairs = useMemo(() => {
    const readyHosts = safeHosts.filter((h) => h.capabilities?.iperf3 && h.capabilities?.ping);
    const pairs = [];

    for (let i = 0; i < readyHosts.length; i++) {
      for (let j = i + 1; j < readyHosts.length; j++) {
        pairs.push({
          key: `${readyHosts[i].name}->${readyHosts[j].name}`,
          src: readyHosts[i],
          dst: readyHosts[j],
          canTestBandwidth: true,
          canTestLatency: true,
        });
      }
    }

    return pairs;
  }, [safeHosts]);

  const totalPairs = readyPairs.length;

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="animate-pulse">
          <div className="h-10 bg-gray-200 rounded mb-4"></div>
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-20 bg-gray-200 rounded"></div>
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
        <h3 className="text-lg font-semibold text-gray-900 mb-2">Host Discovery Failed</h3>
        <p className="text-gray-600 mb-4">{String(error)}</p>
        <button
          onClick={onRefresh}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Retry Discovery
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Host Discovery</h3>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-600">
            {filteredHosts.length} of {safeHosts.length} hosts
          </span>
          <button
            onClick={onRefresh}
            className="flex items-center gap-2 px-3 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4" />
          <input
            type="text"
            placeholder="Search hosts by name or IP..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={filterCapability}
            onChange={(e) => setFilterCapability(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
          >
            <option value="all">All Hosts</option>
            <option value="ready">Performance Ready</option>
            <option value="iperf3">iperf3 Capable</option>
            <option value="ping">Ping Capable</option>
          </select>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-blue-600">{safeHosts.length}</div>
              <div className="text-sm text-gray-600">Total Hosts</div>
            </div>
            <Server className="w-8 h-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-green-600">{performanceReadyCount}</div>
              <div className="text-sm text-gray-600">Performance Ready</div>
            </div>
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-purple-600">
                {safeHosts.filter((h) => h.capabilities?.iperf3).length}
              </div>
              <div className="text-sm text-gray-600">iperf3 Available</div>
            </div>
            <Network className="w-8 h-8 text-purple-500" />
          </div>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-orange-600">{totalPairs}</div>
              <div className="text-sm text-gray-600">Test Pairs (ready)</div>
            </div>
            <Wifi className="w-8 h-8 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Host List */}
      <div className="space-y-3">
        {filteredHosts.length === 0 ? (
          <div className="text-center py-8 bg-gray-50 rounded-lg">
            <Info className="w-8 h-8 text-gray-400 mx-auto mb-2" />
            <p className="text-gray-600">
              {safeHosts.length === 0 ? 'No hosts discovered' : 'No hosts match your search criteria'}
            </p>
          </div>
        ) : (
          filteredHosts.map((host, index) => {
            const caps = host.capabilities || {};
            const name = host.name || 'Unknown';
            const ip = host.ip || '—';
            const statusColor = getHostStatusColor(host);
            const statusColorClasses = {
              green: 'border-green-200 bg-green-50',
              yellow: 'border-yellow-200 bg-yellow-50',
              red: 'border-red-200 bg-red-50',
            };

            return (
              <div
                key={`${host.key}-${index}`}
                className={`border rounded-lg p-4 hover:shadow-md transition-all cursor-pointer ${
                  statusColorClasses[statusColor]
                } ${selectedHost === name ? 'ring-2 ring-blue-500' : ''}`}
                onClick={() => setSelectedHost(selectedHost === name ? null : name)}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div
                      className={`w-3 h-3 rounded-full ${
                        statusColor === 'green'
                          ? 'bg-green-500'
                          : statusColor === 'yellow'
                          ? 'bg-yellow-500'
                          : 'bg-red-500'
                      }`}
                    />

                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="font-medium text-gray-900">{name}</h4>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(name);
                          }}
                          className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                          title="Copy hostname"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="flex items-center gap-2 text-sm text-gray-600">
                        <span>{ip}</span>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            copyToClipboard(ip);
                          }}
                          className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
                          title="Copy IP address"
                        >
                          <Copy className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      {getCapabilityStatus(caps.iperf3)}
                      <span className="text-xs text-gray-600">iperf3</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {getCapabilityStatus(caps.ping)}
                      <span className="text-xs text-gray-600">ping</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {getCapabilityStatus(caps.netstat)}
                      <span className="text-xs text-gray-600">netstat</span>
                    </div>
                    <Eye className="w-4 h-4 text-gray-400" />
                  </div>
                </div>

                {/* Expanded Details */}
                {selectedHost === name && (
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                      {/* Network Interfaces */}
                      <div>
                        <h5 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                          <Network className="w-4 h-4" />
                          Network Interfaces
                        </h5>
                        {Array.isArray(host.interfaces) && host.interfaces.length > 0 ? (
                          <div className="space-y-2">
                            {host.interfaces.map((intf, i) => (
                              <div key={`${host.key}-intf-${i}`} className="bg-white rounded p-2 text-sm">
                                <div className="flex items-center justify-between">
                                  <span className="font-medium">{intf.name || '—'}</span>
                                  <span
                                    className={`px-2 py-1 rounded text-xs ${
                                      (intf.status || 'down') === 'up'
                                        ? 'bg-green-100 text-green-800'
                                        : 'bg-red-100 text-red-800'
                                    }`}
                                  >
                                    {intf.status || 'down'}
                                  </span>
                                </div>
                                <div className="text-gray-600 mt-1">
                                  <div>IP: {intf.ip || '—'}</div>
                                  <div>MAC: {intf.mac || '—'}</div>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500">No interface information</p>
                        )}
                      </div>

                      {/* System Information */}
                      <div>
                        <h5 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                          <Monitor className="w-4 h-4" />
                          System Info
                        </h5>
                        {host.system_info && Object.keys(host.system_info).length > 0 ? (
                          <div className="bg-white rounded p-2 text-sm space-y-1">
                            {host.system_info.kernel && (
                              <div>
                                <span className="text-gray-600">Kernel:</span> {host.system_info.kernel}
                              </div>
                            )}
                            {host.system_info.arch && (
                              <div>
                                <span className="text-gray-600">Arch:</span> {host.system_info.arch}
                              </div>
                            )}
                            {host.system_info.uptime && (
                              <div>
                                <span className="text-gray-600">Uptime:</span> {host.system_info.uptime}
                              </div>
                            )}
                          </div>
                        ) : (
                          <p className="text-sm text-gray-500">No system information</p>
                        )}
                      </div>

                      {/* Capabilities Detail */}
                      <div>
                        <h5 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                          <Terminal className="w-4 h-4" />
                          Tool Capabilities
                        </h5>
                        <div className="bg-white rounded p-2 text-sm space-y-2">
                          {Object.entries(caps).map(([tool, available]) => (
                            <div key={`${host.key}-${tool}`} className="flex items-center justify-between">
                              <span className="capitalize">{tool}</span>
                              <div className="flex items-center gap-1">
                                {available ? (
                                  <>
                                    <CheckCircle className="w-3 h-3 text-green-500" />
                                    <span className="text-green-600 text-xs">Available</span>
                                  </>
                                ) : (
                                  <>
                                    <XCircle className="w-3 h-3 text-red-500" />
                                    <span className="text-red-600 text-xs">Missing</span>
                                  </>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>

                    {/* Quick Actions */}
                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        onClick={(e) => e.stopPropagation()}
                        className="px-3 py-1 bg-blue-100 text-blue-700 rounded text-sm hover:bg-blue-200 transition-colors"
                      >
                        Use as Source
                      </button>
                      <button
                        onClick={(e) => e.stopPropagation()}
                        className="px-3 py-1 bg-green-100 text-green-700 rounded text-sm hover:bg-green-200 transition-colors"
                      >
                        Use as Target
                      </button>
                      {!caps.iperf3 && (
                        <button
                          onClick={(e) => e.stopPropagation()}
                          className="px-3 py-1 bg-orange-100 text-orange-700 rounded text-sm hover:bg-orange-200 transition-colors"
                        >
                          Install iperf3
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Test Pairs Preview */}
      {safeHosts.length > 1 && (
        <div className="bg-gray-50 rounded-lg p-4">
          <h4 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
            <Network className="w-4 h-4" />
            Available Test Pairs
          </h4>
          <div className="text-sm text-gray-600 mb-2">
            With {safeHosts.length} hosts, you can run tests between {totalPairs} ready pairs:
          </div>
          <div className="flex flex-wrap gap-2">
            {readyPairs.slice(0, 12).map((pair) => (
              <span
                key={pair.key}
                className={`px-2 py-1 rounded text-xs ${
                  pair.canTestBandwidth && pair.canTestLatency
                    ? 'bg-green-100 text-green-800'
                    : 'bg-gray-100 text-gray-600'
                }`}
              >
                {pair.src?.name || '—'} → {pair.dst?.name || '—'}
              </span>
            ))}
            {readyPairs.length > 12 && (
              <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs">
                +{readyPairs.length - 12} more pairs
              </span>
            )}
          </div>
          {totalPairs === 0 && (
            <p className="text-sm text-yellow-700 mt-2">
              No test pairs available. Ensure hosts have both iperf3 and ping capabilities.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default HostDiscovery;
