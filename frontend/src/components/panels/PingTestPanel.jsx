// components/NetworkDiagnostic/panels/PingTestPanel.jsx
import React, { useState } from 'react';
import { 
  CheckCircle, 
  XCircle, 
  RefreshCw,
  TrendingUp,
  Router,
  BarChart3,
  Clock,
  Network
} from 'lucide-react';
import MetricCard from '../MetricCard';
import ActionButton from '../ActionButton.jsx';


const PingTestPanel = ({ 
  diagnosticData, 
  diagnosticLoading, 
  runDetailedPing,
  runTraceRoute,
  availableHosts = ['h1', 'h2', 'h3', 'h4']
}) => {
  const [pingConfig, setPingConfig] = useState({
    source: 'h1',
    target: 'h2',
    count: 4,
    timeout: 2
  });
  const [traceRouteResult, setTraceRouteResult] = useState(null);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-2xl font-bold text-gray-900">Detailed Ping & Trace Route</h3>
        <p className="text-gray-600">Advanced network connectivity testing</p>
      </div>
      
      {/* Ping Configuration */}
      <div className="bg-white border-2 border-gray-200 rounded-xl p-6">
        <h4 className="text-lg font-semibold text-gray-900 mb-4">Test Configuration</h4>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Source</label>
            <select
              value={pingConfig.source}
              onChange={(e) => setPingConfig(prev => ({ ...prev, source: e.target.value }))}
              className="w-full border-2 border-gray-200 rounded-xl px-4 py-3 text-gray-700 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 transition"
            >
              {availableHosts.map(host => (
                <option key={host} value={host}>{host}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Target</label>
            <select
              value={pingConfig.target}
              onChange={(e) => setPingConfig(prev => ({ ...prev, target: e.target.value }))}
              className="w-full border-2 border-gray-200 rounded-xl px-4 py-3 text-gray-700 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 transition"
            >
              {availableHosts.map(host => (
                <option key={host} value={host}>{host}</option>
              ))}
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Count</label>
            <input
              type="number"
              min="1"
              max="10"
              value={pingConfig.count}
              onChange={(e) => setPingConfig(prev => ({ ...prev, count: parseInt(e.target.value) }))}
              className="w-full border-2 border-gray-200 rounded-xl px-4 py-3 text-gray-700 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 transition"
            />
          </div>
          
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">Timeout</label>
            <input
              type="number"
              min="1"
              max="10"
              value={pingConfig.timeout}
              onChange={(e) => setPingConfig(prev => ({ ...prev, timeout: parseInt(e.target.value) }))}
              className="w-full border-2 border-gray-200 rounded-xl px-4 py-3 text-gray-700 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-300 transition"
            />
          </div>
        </div>
        
        <div className="flex gap-3 mt-6">
          <ActionButton
            onClick={() => runDetailedPing(pingConfig)}
            loading={diagnosticLoading.ping}
            icon={<TrendingUp className="w-4 h-4" />}
            label="Run Ping Test"
            color="green"
          />
          
          <ActionButton
            onClick={() => runTraceRoute(pingConfig.source, pingConfig.target).then(setTraceRouteResult)}
            icon={<Router className="w-4 h-4" />}
            label="Trace Route"
            color="blue"
            variant="outline"
          />
        </div>
      </div>

      {/* Ping Results */}
      {diagnosticData.detailedPing && (
        <div className="bg-white border-2 border-gray-200 rounded-xl p-6">
          <h4 className="text-lg font-semibold text-gray-900 mb-6">Ping Results</h4>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <MetricCard
              label="Packet Loss"
              value={`${diagnosticData.detailedPing.packet_loss}%`}
              icon={<BarChart3 className="w-5 h-5" />}
              color={diagnosticData.detailedPing.packet_loss === '0' ? 'green' : 'red'}
            />
            <MetricCard
              label="Average Time"
              value={`${diagnosticData.detailedPing.average_time_ms}ms`}
              icon={<Clock className="w-5 h-5" />}
              color="blue"
            />
            <MetricCard
              label="Target IP"
              value={diagnosticData.detailedPing.target_ip}
              icon={<Network className="w-5 h-5" />}
              color="purple"
            />
            <MetricCard
              label="Status"
              value={diagnosticData.detailedPing.success ? 'SUCCESS' : 'FAILED'}
              icon={diagnosticData.detailedPing.success ? 
                <CheckCircle className="w-5 h-5" /> : 
                <XCircle className="w-5 h-5" />}
              color={diagnosticData.detailedPing.success ? 'green' : 'red'}
            />
          </div>
          
          <div className="bg-gray-50 border-2 border-gray-200 rounded-xl p-4">
            <h5 className="font-semibold text-gray-900 mb-3">Full Output</h5>
            <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono bg-white rounded-lg p-3 border border-gray-200 overflow-x-auto">
              {diagnosticData.detailedPing.full_result}
            </pre>
          </div>
        </div>
      )}

      {/* Trace Route Results */}
      {traceRouteResult && (
        <div className="bg-white border-2 border-gray-200 rounded-xl p-6">
          <h4 className="text-lg font-semibold text-gray-900 mb-4">Trace Route Results</h4>
          <div className="bg-gray-50 border-2 border-gray-200 rounded-xl p-4">
            <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono bg-white rounded-lg p-3 border border-gray-200 overflow-x-auto">
              {traceRouteResult.traceroute}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};

export default PingTestPanel;