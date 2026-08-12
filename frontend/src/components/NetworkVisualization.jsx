import React, { useRef, useLayoutEffect, useState } from 'react';
import { Network, Globe, Timer, ChevronDown, Cpu, Zap, Layers, Server } from 'lucide-react';
import Draggable from 'react-draggable';
import TopologyRenderer from './TopologyRenderer';
import ActionButton from './ActionButton';

const NetworkVisualization = ({
  topology,
  networkStatus,
  controllerStatus,
  networkMetrics,
  flowStats,
  hoveredNode,
  setHoveredNode,
  dragPositions,
  setDragPositions,
  selectedHost,
  setSelectedHost,
  connectionStatus,
  controllerConfig,
  controllerStats,
  ryuApp,
  formatBytes,
  createNetwork,
  onAddNode,
  onRemoveNode,
  onAddLink,
  onRemoveLink,
  controllerType = 'ryu',
  setControllerType,
  CONTROLLER_TYPES = {},
  SWITCH_TYPES = {}
}) => {
  const vizRef = useRef(null);
  const [canvasWidth, setCanvasWidth] = useState(0);

  // Local state for quick-add selections
  const [selectedControllerType, setSelectedControllerType] = useState('ryu');
  const [selectedSwitchType, setSelectedSwitchType] = useState('ovs');
  const [showControllerDropdown, setShowControllerDropdown] = useState(false);
  const [showSwitchDropdown, setShowSwitchDropdown] = useState(false);

  useLayoutEffect(() => {
    const handle = () => setCanvasWidth(vizRef.current?.clientWidth || 0);
    handle();
    window.addEventListener('resize', handle);
    return () => window.removeEventListener('resize', handle);
  }, []);

  // Close dropdowns when clicking outside
  useLayoutEffect(() => {
    const handleClickOutside = (event) => {
      if (!event.target.closest('.dropdown-container')) {
        setShowControllerDropdown(false);
        setShowSwitchDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Controller type options from props
  const controllerOptions = CONTROLLER_TYPES && Object.keys(CONTROLLER_TYPES).length > 0
    ? Object.entries(CONTROLLER_TYPES).map(([key, controller]) => ({
        value: key,
        label: controller.name || key,
        icon: key === 'ryu' ? Cpu :
              key === 'pox' ? Zap :
              key === 'osken' ? Layers :
              key === 'opendaylight' ? Globe : Cpu
      }))
    : [
        { value: 'ryu', label: 'Ryu', icon: Cpu },
        { value: 'pox', label: 'POX', icon: Zap },
        { value: 'osken', label: 'OsKen', icon: Layers },
        { value: 'opendaylight', label: 'OpenDaylight', icon: Globe }
      ];

  // Debug logging
  console.log('NetworkVisualization - CONTROLLER_TYPES:', CONTROLLER_TYPES);
  console.log('NetworkVisualization - controllerOptions:', controllerOptions);

  // Switch type options from props
  const switchOptions = SWITCH_TYPES && Object.keys(SWITCH_TYPES).length > 0
    ? Object.entries(SWITCH_TYPES).map(([key, switchInfo]) => ({
        value: key,
        label: switchInfo.name || key,
        icon: key === 'ovs' ? Network :
              key === 'linux_bridge' ? Server :
              key === 'p4' ? Cpu : Network
      }))
    : [
        { value: 'ovs', label: 'Open vSwitch', icon: Network },
        { value: 'linux_bridge', label: 'Linux Bridge', icon: Server },
        { value: 'p4', label: 'P4 Switch', icon: Cpu }
      ];

  // Debug logging
  console.log('NetworkVisualization - SWITCH_TYPES:', SWITCH_TYPES);
  console.log('NetworkVisualization - switchOptions:', switchOptions);

  // Get selected controller info
  const getSelectedControllerInfo = () => {
    return controllerOptions.find(opt => opt.value === selectedControllerType) || controllerOptions[0];
  };

  // Get selected switch info
  const getSelectedSwitchInfo = () => {
    return switchOptions.find(opt => opt.value === selectedSwitchType) || switchOptions[0];
  };

  return (
    <div className="bg-white rounded-2xl shadow-lg overflow-hidden border border-gray-200">
      <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-gray-800 flex items-center gap-3">
            <Globe className="w-7 h-7 text-indigo-500" />
            Network Topology Visualization
          </h2>
          <div className="flex items-center gap-6 text-sm text-gray-600">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-emerald-500 rounded-full shadow-sm animate-pulse"></div>
              <span className="font-medium">{topology.stats.links || 0} Active Links</span>
            </div>
            <div className="flex items-center gap-2">
              <Timer className="w-4 h-4 text-blue-500" />
              <span className="font-mono">{networkMetrics.uptime}</span>
            </div>
          </div>
        </div>
      </div>
      
      <div className="h-[700px] relative overflow-hidden">
        {topology && (topology.nodes?.length > 0 || topology.controllers?.length > 0) ? (
          <TopologyRenderer
            ref={vizRef}
            topology={topology}
            networkStatus={networkStatus}
            controllerStatus={controllerStatus}
            networkMetrics={networkMetrics}
            flowStats={flowStats}
            hoveredNode={hoveredNode}
            setHoveredNode={setHoveredNode}
            dragPositions={dragPositions}
            setDragPositions={setDragPositions}
            selectedHost={selectedHost}
            setSelectedHost={setSelectedHost}
            connectionStatus={connectionStatus}
            controllerConfig={controllerConfig}
            controllerStats={controllerStats}
            ryuApp={ryuApp}
            formatBytes={formatBytes}
            canvasWidth={canvasWidth}
            onRemoveNode={onRemoveNode}
            onRemoveLink={onRemoveLink}
          />
        ) : (
          <div className="h-full flex flex-col items-center justify-center bg-gradient-to-br from-gray-50 to-gray-100">
            <div className="bg-gray-100 border-2 border-dashed border-gray-300 rounded-3xl w-32 h-32 flex items-center justify-center mb-8">
              <Network className="w-16 h-16 text-gray-400" />
            </div>
            <h3 className="text-2xl font-semibold text-gray-800 mb-3">No Network Topology</h3>
            <p className="text-gray-600 text-center max-w-md mb-6 leading-relaxed">
              Create and start a network to visualize the SDN topology with real-time data flows and comprehensive network statistics.
            </p>



            <ActionButton
              onClick={createNetwork}
              icon={<Network className="w-5 h-5" />}
              label="Create Network Topology"
              color="indigo"
              size="lg"
            />
          </div>
        )}

        {/* Quick add controls */}
        <div className="absolute top-4 right-4 flex flex-col gap-3 bg-white rounded-lg shadow-lg border border-gray-200 p-3">
          <div className="text-xs font-semibold text-gray-700 mb-1">Quick Add:</div>

          {/* Debug info */}
          <div className="text-[10px] text-gray-500 mb-2 p-2 bg-gray-50 rounded">
            <div>Nodes: {topology?.nodes?.length || 0}</div>
            <div>Controllers: {topology?.controllers?.length || 0}</div>
            <div>Links: {topology?.links?.length || 0}</div>
            <div>Switches: {topology?.nodes?.filter(n => n.type === 'switch').length || 0}</div>
            <div>Routers: {topology?.nodes?.filter(n => n.type === 'router').length || 0}</div>
            <div>Hosts: {topology?.nodes?.filter(n => n.type === 'host').length || 0}</div>
          </div>

          {/* Add Host */}
          <button
            onClick={() => onAddNode && onAddNode({
              id: `h${(topology.nodes.filter(n=>n.type==='host').length||0)+1}`,
              type: 'host',
              x: 120,
              y: 120,
              ip: 'auto',
              mac: 'auto'
            })}
            className="px-3 py-2 bg-indigo-600 text-white text-xs rounded hover:bg-indigo-700 transition-colors"
            title="Add Host"
          >
            + Host
          </button>

          {/* Switch Type Selector */}
          <div className="relative dropdown-container">
            <button
              onClick={() => setShowSwitchDropdown(!showSwitchDropdown)}
              className="px-3 py-2 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors flex items-center gap-1"
              title="Select Switch Type"
            >
              <Network className="w-3 h-3" />
              {getSelectedSwitchInfo().label}
              <ChevronDown className="w-3 h-3" />
            </button>

            {showSwitchDropdown && (
              <div className="absolute top-full right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 min-w-48 dropdown-container">
                {switchOptions.map(option => {
                  const Icon = option.icon;
                  return (
                    <button
                      key={option.value}
                      onClick={() => {
                        setSelectedSwitchType(option.value);
                        setShowSwitchDropdown(false);
                      }}
                      className={`w-full px-3 py-2 text-left text-xs hover:bg-gray-50 flex items-center gap-2 ${
                        selectedSwitchType === option.value ? 'bg-blue-50 text-blue-700' : 'text-gray-700'
                      }`}
                    >
                      <Icon className="w-3 h-3" />
                      {option.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Add Switch */}
          <button
            onClick={() => onAddNode && onAddNode({
              id: `s${(topology.nodes.filter(n=>n.type==='switch').length||0)+1}`,
              type: 'switch',
              x: 220,
              y: 220,
              switch_type: selectedSwitchType
            })}
            className="px-3 py-2 bg-blue-500 text-white text-xs rounded hover:bg-blue-600 transition-colors"
            title={`Add ${getSelectedSwitchInfo().label}`}
          >
            + Switch
          </button>

          {/* Add Router */}
          <button
            onClick={() => onAddNode && onAddNode({
              id: `r${(topology.nodes.filter(n=>n.type==='router').length||0)+1}`,
              type: 'router',
              x: 320,
              y: 320
            })}
            className="px-3 py-2 bg-emerald-600 text-white text-xs rounded hover:bg-emerald-700 transition-colors"
            title="Add Router"
          >
            + Router
          </button>

          {/* Controller Type Selector */}
          <div className="relative dropdown-container">
            <button
              onClick={() => setShowControllerDropdown(!showControllerDropdown)}
              className="px-3 py-2 bg-red-600 text-white text-xs rounded hover:bg-red-700 transition-colors flex items-center gap-1"
              title="Select Controller Type"
            >
              <Cpu className="w-3 h-3" />
              {getSelectedControllerInfo().label}
              <ChevronDown className="w-3 h-3" />
            </button>

            {showControllerDropdown && (
              <div className="absolute top-full right-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 min-w-48 dropdown-container">
                {controllerOptions.map(option => {
                  const Icon = option.icon;
                  return (
                    <button
                      key={option.value}
                      onClick={() => {
                        setSelectedControllerType(option.value);
                        setShowControllerDropdown(false);
                      }}
                      className={`w-full px-3 py-2 text-left text-xs hover:bg-gray-50 flex items-center gap-2 ${
                        selectedControllerType === option.value ? 'bg-red-50 text-red-700' : 'text-gray-700'
                      }`}
                    >
                      <Icon className="w-3 h-3" />
                      {option.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Add Controller */}
          <button
            onClick={() => onAddNode && onAddNode({
              id: `c${((topology.controllers?.length || 0) + (topology.nodes?.filter(n=>n.type==='controller').length || 0))+1}`,
              type: 'controller',
              x: 420,
              y: 420,
              controller_type: selectedControllerType
            })}
            className="px-3 py-2 bg-red-500 text-white text-xs rounded hover:bg-red-600 transition-colors"
            title={`Add ${getSelectedControllerInfo().label} Controller`}
          >
            + Controller
          </button>
          <button
            onClick={() => {
              const hosts = topology.nodes.filter(n=>n.type==='host');
              const switches = topology.nodes.filter(n=>n.type==='switch');
              if (hosts[0] && switches[0]) {
                onAddLink && onAddLink({
                  source: hosts[0].id,
                  target: switches[0].id,
                  bandwidth: '100M',
                  delay: '1ms'
                });
              }
            }}
            className="px-2 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 transition-colors"
            title="Link Host to Switch"
          >
            Link h-s
          </button>
        </div>
      </div>
    </div>
  );
};

export default NetworkVisualization;