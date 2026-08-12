import React, { useState } from 'react';
import { Network, Server, Play, Square, RefreshCw, Activity, Settings, Layers, Plus } from 'lucide-react';
import ActionButton from './ActionButton';
import TopologyBuilder from './TopologyBuilder';

const ControlPanel = ({
  createNetwork,
  startNetwork,
  stopNetwork,
  deleteNetwork,
  runPingTest,
  startController,
  stopController,
  restartController,
  switchControllerApp,
  clearControllerLogs,
  networkStatus,
  controllerStatus,
  topology,
  ryuApp,
  setRyuApp,
  availableApps,
  controllerConfig,
  controllerStats,
  controllerLogs,
  loading,
  // New props for custom topology
  createCustomTopology,
  savedTopologies = [],
  onSaveTopology,
  // Live topology handlers
  onAddNode,
  onRemoveNode,
  onAddLink,
  onRemoveLink,
  // Property update handlers
  onUpdateNodeIP,
  onUpdateLinkBandwidth,
  onUpdateLinkStatus,
  onUpdateControllerPort,
  onRefreshTopology,
  // optional refresh action after apply
  fetchTopology
}) => {
  const [showTopologyBuilder, setShowTopologyBuilder] = useState(false);

  const handleCreateCustomTopology = (topology) => {
    if (createCustomTopology) {
      createCustomTopology(topology);
    } else {
      // Fallback to basic network creation if custom topology handler not provided
      createNetwork();
    }
  };

  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-6">
        {/* Network Management */}
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm p-6">
          <h2 className="mb-6 flex items-center gap-3 text-xl font-semibold text-gray-700">
            <span className="inline-flex p-2 rounded-lg border border-indigo-100 bg-indigo-50">
              <Network className="w-5 h-5 text-indigo-500" />
            </span>
            Network Management
          </h2>

          {/* Topology Creation Options */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-600 mb-3">Create Topology</label>
            <div className="grid grid-cols-1 gap-3">
              {/* Quick Create Buttons */}
              <div className="grid grid-cols-2 gap-2">
                <ActionButton
                  onClick={createNetwork}
                  icon={<RefreshCw className="w-4 h-4" />}
                  label="Simple Topology"
                  color="pastelIndigo"
                  size="sm"
                />
                <ActionButton
                  onClick={() => setShowTopologyBuilder(true)}
                  icon={<Layers className="w-4 h-4" />}
                  label="Custom Builder"
                  color="pastelIndigo"
                  size="sm"
                />
              </div>
            </div>
          </div>

          {/* Network Control Buttons */}
          <div className="grid grid-cols-2 gap-4">
            <ActionButton
              onClick={startNetwork}
              disabled={networkStatus.running}
              icon={<Play className="w-4 h-4" />}
              label="Start Network"
              color="success"
            />
            <ActionButton
              onClick={stopNetwork}
              disabled={!networkStatus.running}
              icon={<Square className="w-4 h-4" />}
              label="Stop Network"
              color="danger"
            />
          </div>

          {/* Delete Network Button */}
          <div className="mt-4">
            <ActionButton
              onClick={deleteNetwork}
              disabled={networkStatus.running}
              icon={<Square className="w-4 h-4" />}
              label="Delete Network"
              color="danger"
              size="md"
            />
          </div>

          {/* Network Testing */}
          <div className="mt-4">
            <ActionButton
              onClick={runPingTest}
              disabled={!networkStatus.running}
              icon={<Activity className="w-4 h-4" />}
              label="Run Connectivity Test"
              color="pastelIndigo"
              size="md"
            />
          </div>

          {/* Network Status Display */}
          {networkStatus.running && (
            <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-xl">
              <h3 className="text-sm font-bold text-green-600 mb-2 flex items-center gap-2">
                <Network className="w-4 h-4" />
                Network Status
              </h3>
              <div className="space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-green-500">Status:</span>
                  <span className="text-green-700 font-semibold">Running</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-green-500">Uptime:</span>
                  <span className="text-green-700 font-mono">{networkStatus.uptime || '00:00:00'}</span>
                </div>
                {networkStatus.topology_summary && (
                  <>
                    <div className="flex justify-between">
                      <span className="text-green-500">Hosts:</span>
                      <span className="text-green-700">{networkStatus.topology_summary.hosts || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-green-500">Switches:</span>
                      <span className="text-green-700">{networkStatus.topology_summary.switches || 0}</span>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}
        </section>

        {/* SDN Controller */}
        <section className="rounded-2xl border border-gray-200 bg-white shadow-sm p-6">
          <h2 className="mb-6 flex items-center gap-3 text-xl font-semibold text-gray-700">
            <span className="inline-flex p-2 rounded-lg border border-emerald-100 bg-emerald-50">
              <Server className="w-5 h-5 text-emerald-500" />
            </span>
            SDN Controller
          </h2>

          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-600 mb-2">
                Controller Application
              </label>
              <select
                value={ryuApp}
                onChange={(e) => setRyuApp(e.target.value)}
                disabled={controllerStatus.running}
                className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-gray-700 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-200 disabled:bg-gray-100 disabled:text-gray-400 transition"
              >
                {availableApps.length > 0 ? (
                  availableApps.map(app => (
                    <option key={app.id} value={app.id}>
                      {app.name} - {app.description}
                    </option>
                  ))
                ) : (
                  <>
                    <option value="simple_switch_13">Learning Switch (OpenFlow 1.3)</option>
                    <option value="simple_switch">Learning Switch (OpenFlow 1.0)</option>
                    <option value="hub">Hub Controller</option>
                    <option value="rest_router">REST Router</option>
                    <option value="rest_firewall">REST Firewall</option>
                  </>
                )}
              </select>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <ActionButton
                onClick={startController}
                disabled={controllerStatus.running}
                icon={<Play className="w-4 h-4" />}
                label="Start"
                color="success"
                size="sm"
              />
              <ActionButton
                onClick={stopController}
                disabled={!controllerStatus.running}
                icon={<Square className="w-4 h-4" />}
                label="Stop"
                color="danger"
                size="sm"
              />
              <ActionButton
                onClick={restartController}
                disabled={!controllerStatus.running}
                icon={<RefreshCw className="w-4 h-4" />}
                label="Restart"
                color="pastelIndigo"
                size="sm"
              />
            </div>

            {/* Controller Status Display */}
            {controllerStatus.running && (
              <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
                <h3 className="text-sm font-bold text-emerald-600 mb-3 flex items-center gap-2">
                  <Server className="w-4 h-4" />
                  Active Controller
                </h3>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-emerald-500">App:</span>
                    <span className="text-emerald-700 font-mono text-[10px]">{controllerConfig.type || controllerStatus.type || ryuApp}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-emerald-500">Port:</span>
                    <span className="text-emerald-700 font-mono">{controllerConfig.port || '6633'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-emerald-500">PID:</span>
                    <span className="text-emerald-700 font-mono">{controllerStatus.pid || 'N/A'}</span>
                  </div>
                  {controllerStats.controller && (
                    <>
                      <div className="flex justify-between">
                        <span className="text-emerald-500">Connections:</span>
                        <span className="text-emerald-700">{controllerStats.controller.connections || 0}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-emerald-500">Memory:</span>
                        <span className="text-emerald-700">{controllerStats.controller.memory_usage || 'N/A'}</span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Quick App Switcher for Running Controller */}
            {controllerStatus.running && availableApps.length > 0 && (
              <div>
                <label className="block text-sm font-medium text-gray-600 mb-2">
                  Quick Switch App
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {availableApps.slice(0, 4).map(app => (
                    <button
                      key={app.id}
                      onClick={() => switchControllerApp(app.id)}
                      disabled={loading || app.id === (controllerConfig.type || ryuApp)}
                      className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors ${
                        app.id === (controllerConfig.type || ryuApp)
                          ? 'bg-emerald-100 text-emerald-700 border-emerald-300'
                          : 'bg-gray-100 text-gray-700 border-gray-300 hover:bg-gray-200'
                      } disabled:opacity-50 disabled:cursor-not-allowed`}
                    >
                      {app.name.split(' ')[0]} {/* Show short name */}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      </div>

      {/* Topology Builder Modal */}
      <TopologyBuilder
        isOpen={showTopologyBuilder}
        onClose={() => setShowTopologyBuilder(false)}
        onCreateTopology={handleCreateCustomTopology}
        availableTemplates={savedTopologies}
        onSaveTemplate={onSaveTopology}
        // Live mode props
        networkStatus={networkStatus}
        initialTopology={topology}
        onAddNode={onAddNode}
        onRemoveNode={onRemoveNode}
        onAddLink={onAddLink}
        onRemoveLink={onRemoveLink}
        // Property update handlers
        onUpdateNodeIP={onUpdateNodeIP}
        onUpdateLinkBandwidth={onUpdateLinkBandwidth}
        onUpdateLinkStatus={onUpdateLinkStatus}
        onUpdateControllerPort={onUpdateControllerPort}
        onRefreshTopology={onRefreshTopology}
        onAfterApply={fetchTopology}
      />
    </>
  );
};

export default ControlPanel;