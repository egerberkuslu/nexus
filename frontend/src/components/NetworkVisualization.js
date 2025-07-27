import React, { useRef, useLayoutEffect, useState } from 'react';
import { Network, Globe, Timer } from 'lucide-react';
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
  createNetwork
}) => {
  const vizRef = useRef(null);
  const [canvasWidth, setCanvasWidth] = useState(0);

  useLayoutEffect(() => {
    const handle = () => setCanvasWidth(vizRef.current?.clientWidth || 0);
    handle();
    window.addEventListener('resize', handle);
    return () => window.removeEventListener('resize', handle);
  }, []);

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
        {topology.nodes.length > 0 ? (
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
      </div>
    </div>
  );
};

export default NetworkVisualization;