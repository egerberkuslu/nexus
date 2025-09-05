import React, { forwardRef } from 'react';
import { Server, Network, Monitor, Activity, Circle, Router, Cpu, Zap, Globe, Database, Layers } from 'lucide-react';
import Draggable from 'react-draggable';

const TopologyRenderer = forwardRef(({
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
  canvasWidth,
  onRemoveNode,
  onRemoveLink
}, ref) => {
  // Extract topology data safely
  const rawNodes = Array.isArray(topology?.nodes) ? topology.nodes : [];
  const rawControllers = Array.isArray(topology?.controllers) ? topology.controllers : [];
  const rawLinks = Array.isArray(topology?.links) ? topology.links : [];

  // Ensure controllers are unique and not duplicated in nodes
  const controllerIdSet = new Set();
  const controllers = rawControllers.filter(c => {
    if (!c || !c.id || controllerIdSet.has(c.id)) return false;
    controllerIdSet.add(c.id);
    return true;
  });

  // Exclude any controller-typed entries from nodes to avoid double rendering
  const nodes = rawNodes.filter(n => n && n.type !== 'controller');

  // Deduplicate links by (source,target,type)
  const linkKeySet = new Set();
  const links = rawLinks.filter(l => {
    if (!l || !l.source || !l.target) return false;
    const key = `${l.source}__${l.target}__${l.type || 'network-link'}`;
    if (linkKeySet.has(key)) return false;
    linkKeySet.add(key);
    return true;
  });

  // Debug logging to help identify issues
  console.log('TopologyRenderer - Topology data:', {
    nodesCount: nodes.length,
    controllersCount: controllers.length,
    linksCount: links.length,
    controllers: controllers.map(c => ({ id: c.id, type: c.type })),
    links: links.map(l => ({ source: l.source, target: l.target, type: l.type }))
  });



  // Group nodes by type (excluding controllers from nodes since they're separate)
  const routers = nodes.filter(n => n.type === 'router');
  const switches = nodes.filter(n => n.type === 'switch');
  const hosts = nodes.filter(n => n.type === 'host');

  // Create position map with drag adjustments
  const nodePositions = {};

  // Add positions for all node types
  const allNodes = [...nodes, ...controllers];

  allNodes.forEach((node, index) => {
    // Use provided coordinates or calculate default positions
    let defaultPos;
    if (node.x !== undefined && node.y !== undefined && node.x !== null && node.y !== null) {
      defaultPos = { x: node.x, y: node.y };
    } else {
      // Calculate grid-based positions
      const cols = 4;
      const spacing = 150;
      const startX = 150;
      const startY = 150;

      // Separate controllers from other nodes for positioning
      const nonControllerNodes = allNodes.filter(n => n.type !== 'controller');
      const controllerNodes = allNodes.filter(n => n.type === 'controller');

      if (node.type === 'controller') {
        // Position controllers at the top
        const controllerIndex = controllerNodes.indexOf(node);
        defaultPos = {
          x: startX + (controllerIndex % cols) * spacing,
          y: startY - 100  // Position controllers above regular nodes
        };
      } else {
        // Position regular nodes below controllers
        const nodeIndex = nonControllerNodes.indexOf(node);
        defaultPos = {
          x: startX + (nodeIndex % cols) * spacing,
          y: startY + Math.floor(nodeIndex / cols) * 120
        };
      }
    }
    nodePositions[node.id] = dragPositions[node.id] || defaultPos;
  });

  // Handle node dragging
  const handleDragStop = (nodeId, offsetX, offsetY, data) => {
    setDragPositions(prev => ({
      ...prev,
      [nodeId]: { 
        x: data.x + offsetX, 
        y: data.y + offsetY 
      }
    }));
  };

    // Render links with proper positions
  // Helper to compute center offset by node type (to keep lines centered)
  const getCenterOffset = (node) => {
    const t = node?.type;
    if (t === 'controller') return 56; // w-28 => 112px
    if (t === 'router') return 48;     // w-24 => 96px
    if (t === 'switch') return 40;     // w-20 => 80px
    if (t === 'host') return 32;       // w-16 => 64px
    return 30;
  };

  const renderLinks = () => {
    return links.map((link, idx) => {
      try {
        // Validate link structure
        if (!link || typeof link !== 'object') return null;
        if (!link.source || !link.target) return null;

        // Look for source and target in both nodes and controllers
        const allNodes = [...nodes, ...controllers];
        const sourceNode = allNodes.find(n => n && n.id === link.source);
        const targetNode = allNodes.find(n => n && n.id === link.target);

        if (!sourceNode || !targetNode) {
          console.warn(`Link ${idx} missing source or target node:`, {
            link,
            availableNodeIds: allNodes.map(n => n.id),
            sourceFound: !!sourceNode,
            targetFound: !!targetNode
          });
          return null;
        }

        // Debug logging for controller links
        if (link.type === 'controller-link') {
          console.log(`Controller link ${idx}:`, {
            link,
            sourceNode: sourceNode ? { id: sourceNode.id, type: sourceNode.type } : null,
            targetNode: targetNode ? { id: targetNode.id, type: targetNode.type } : null,
            sourcePos: nodePositions[sourceNode.id],
            targetPos: nodePositions[targetNode.id]
          });
        }

        const sourcePos = nodePositions[sourceNode.id];
        const targetPos = nodePositions[targetNode.id];

        if (!sourcePos || !targetPos) {
          console.warn(`Link ${idx} missing position data for ${link.source} -> ${link.target}`);
          return null;
        }

      const linkActive = networkStatus.running && link.status !== 'down';
      const isRouterLink = sourceNode.type === 'router' || targetNode.type === 'router';
      const isControllerLink = sourceNode.type === 'controller' || targetNode.type === 'controller';

      // Debug logging for controller link rendering
      if (isControllerLink) {
        console.log(`Rendering controller link ${idx}:`, {
          sourceNode: { id: sourceNode.id, type: sourceNode.type },
          targetNode: { id: targetNode.id, type: targetNode.type },
          sourcePos,
          targetPos,
          linkActive,
          stroke: linkActive ? "url(#controllerLinkGradient)" : "#94a3b8",
          strokeWidth: "6"
        });
      }

      const srcOffset = getCenterOffset(sourceNode);
      const tgtOffset = getCenterOffset(targetNode);

      return (
        <svg
          key={`link-${idx}`}
          className="absolute top-0 left-0 w-full h-full pointer-events-none"
        >
          <defs>
            <linearGradient id="linkGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#6366f1" stopOpacity="0.8" />
            </linearGradient>
            <linearGradient id="routerLinkGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#059669" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.8" />
            </linearGradient>
            <linearGradient id="controllerLinkGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#dc2626" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.8" />
            </linearGradient>
          </defs>
          
          <line
            x1={sourcePos.x + srcOffset}
            y1={sourcePos.y + srcOffset}
            x2={targetPos.x + tgtOffset}
            y2={targetPos.y + tgtOffset}
            stroke={linkActive ? (isControllerLink ? "url(#controllerLinkGradient)" : isRouterLink ? "url(#routerLinkGradient)" : "url(#linkGradient)") : "#94a3b8"}
            strokeWidth={isControllerLink ? "6" : isRouterLink ? "5" : "4"}
            strokeOpacity={linkActive ? "0.8" : "0.4"}
            strokeDasharray={link.status === 'down' ? "10,10" : "0"}
            className="transition-all duration-300 pointer-events-auto cursor-pointer"
            onDoubleClick={() => {
              if (onRemoveLink) onRemoveLink(sourceNode.id, targetNode.id);
            }}
          />

          {/* Data flow animations */}
          {linkActive && (
            <>
              <circle r={isControllerLink ? "6" : isRouterLink ? "5" : "4"} fill={isControllerLink ? "#dc2626" : isRouterLink ? "#059669" : "#3b82f6"} opacity="0.9">
                <animateMotion
                  dur="2s"
                  repeatCount="indefinite"
                  path={`M${sourcePos.x + srcOffset},${sourcePos.y + srcOffset} L${targetPos.x + tgtOffset},${targetPos.y + tgtOffset}`}
                />
              </circle>
              <circle r={isControllerLink ? "5" : isRouterLink ? "4" : "3"} fill={isControllerLink ? "#ef4444" : isRouterLink ? "#10b981" : "#6366f1"} opacity="0.7">
                <animateMotion
                  dur="2.5s"
                  repeatCount="indefinite"
                  begin="0.5s"
                  path={`M${targetPos.x + tgtOffset},${targetPos.y + tgtOffset} L${sourcePos.x + srcOffset},${sourcePos.y + srcOffset}`}
                />
              </circle>
            </>
          )}

          {/* Link info text */}
          <text
            x={(sourcePos.x + srcOffset + targetPos.x + tgtOffset) / 2}
            y={(sourcePos.y + srcOffset + targetPos.y + tgtOffset) / 2 + 20}
            textAnchor="middle"
            fill="#4b5563"
            fontSize="11"
            fontWeight="600"
            className="drop-shadow-lg"
          >
            {link.bandwidth || (isControllerLink ? 'Control' : isRouterLink ? '1G' : '10M')}
          </text>
        </svg>
      );
      } catch (error) {
        console.error(`Error rendering link ${idx}:`, error);
        return null;
      }
    });
  };

  // Get controller type icon and colors
  const getControllerTypeInfo = (controller) => {
    const controllerType = controller.controller_type || controllerStatus?.controller_type || 'ryu';

    // Debug logging
    console.log('TopologyRenderer - Controller:', controller.id, 'Type:', controllerType, 'App:', controller.app, 'Data:', controller);

    switch (controllerType) {
      case 'ryu':
        return {
          icon: Cpu,
          color: isActive => isActive
            ? 'from-blue-400 via-blue-500 to-blue-600 border-blue-300 shadow-blue-200'
            : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300',
          name: 'Ryu'
        };
      case 'pox':
        return {
          icon: Zap,
          color: isActive => isActive
            ? 'from-purple-400 via-purple-500 to-purple-600 border-purple-300 shadow-purple-200'
            : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300',
          name: 'POX'
        };
      case 'osken':
        return {
          icon: Layers,
          color: isActive => isActive
            ? 'from-green-400 via-green-500 to-green-600 border-green-300 shadow-green-200'
            : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300',
          name: 'OsKen'
        };
      case 'opendaylight':
        return {
          icon: Globe,
          color: isActive => isActive
            ? 'from-orange-400 via-orange-500 to-orange-600 border-orange-300 shadow-orange-200'
            : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300',
          name: 'OpenDaylight'
        };
      default:
        return {
          icon: Server,
          color: isActive => isActive
            ? 'from-red-400 via-red-500 to-red-600 border-red-300 shadow-red-200'
            : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300',
          name: 'Controller'
        };
    }
  };

  // Get switch type icon and colors
  const getSwitchTypeInfo = (sw) => {
    const switchType = sw.switch_type || 'ovs';

    // Debug logging
    console.log('TopologyRenderer - Switch:', sw.id, 'Type:', switchType, 'Data:', sw);

    switch (switchType) {
      case 'ovs':
        return {
          icon: Network,
          color: isActive => isActive
            ? 'from-blue-400 via-blue-500 to-blue-600 border-blue-300 shadow-blue-200'
            : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300',
          name: 'Open vSwitch',
          protocol: 'OpenFlow'
        };
      case 'linux_bridge':
        return {
          icon: Server,
          color: isActive => isActive
            ? 'from-green-400 via-green-500 to-green-600 border-green-300 shadow-green-200'
            : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300',
          name: 'Linux Bridge',
          protocol: 'N/A'
        };
      case 'p4':
        return {
          icon: Cpu,
          color: isActive => isActive
            ? 'from-purple-400 via-purple-500 to-purple-600 border-purple-300 shadow-purple-200'
            : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300',
          name: 'P4 Switch',
          protocol: 'P4Runtime'
        };
      default:
        return {
          icon: Network,
          color: isActive => isActive
            ? 'from-blue-400 via-blue-500 to-blue-600 border-blue-300 shadow-blue-200'
            : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300',
          name: 'Switch',
          protocol: 'Unknown'
        };
    }
  };

  // Render controllers
  const renderControllers = () => {
    return controllers.map(controller => {
      try {
        if (!controller || !controller.id) return null;
        const pos = nodePositions[controller.id];
        if (!pos) return null;

      const isActive = controllerStatus?.running === true ||
                       controllerStatus?.status === 'running' ||
                       controller.status === 'running' ||
                       (networkStatus.running && controllerStatus?.running !== false);

      const controllerInfo = getControllerTypeInfo(controller);
      const IconComponent = controllerInfo.icon;

      const offsetX = 50;
      const offsetY = 50;

      return (
        <Draggable
          key={controller.id}
          bounds="parent"
          position={{ x: pos.x - offsetX, y: pos.y - offsetY }}
          onStop={(e, data) => {
            handleDragStop(controller.id, offsetX, offsetY, data);
          }}
        >
          <div
            style={{ position: 'absolute', left: 0, top: 0 }}
            className={`flex flex-col items-center transition-all duration-500 cursor-pointer group ${hoveredNode === controller.id ? 'scale-110 z-30' : 'z-20'
              }`}
            onMouseEnter={() => setHoveredNode(controller.id)}
            onMouseLeave={() => setHoveredNode(null)}
            onDoubleClick={() => onRemoveNode && onRemoveNode(controller.id)}
          >
            <div className="relative">
              <div
                className={`w-28 h-28 bg-gradient-to-br rounded-3xl flex items-center justify-center shadow-xl border-2 backdrop-blur-sm transition-all duration-300 ${controllerInfo.color(isActive)}`}
              >
                <IconComponent className="w-14 h-14 text-white drop-shadow" />
              </div>

              {/* Active indicator */}
              {isActive && (
                <div className="absolute -top-2 -right-2 w-8 h-8 bg-green-500 rounded-full flex items-center justify-center border-2 border-white shadow">
                  <div className="w-5 h-5 bg-white rounded-full animate-pulse"></div>
                </div>
              )}

              {/* Status dot */}
              <div
                className={`absolute -bottom-1 -right-1 w-6 h-6 rounded-full animate-pulse ${isActive ? 'bg-green-500' : 'bg-red-500'
                  }`}
              ></div>
            </div>

            <div className="mt-3 text-center">
              <div className="text-sm font-bold text-gray-800 drop-shadow-sm">{controller.id}</div>
              <div className={`text-xs font-medium ${isActive ? 'text-red-600' : 'text-gray-500'}`}>
                {controllerStatus?.status || controller.status || (isActive ? 'Active' : 'Inactive')}
              </div>

              {/* Tooltip */}
              {hoveredNode === controller.id && (
                <div className="absolute top-full mt-3 left-1/2 transform -translate-x-1/2 bg-white/90 backdrop-blur-sm border border-gray-300 shadow-xl text-gray-800 text-xs px-4 py-3 rounded-xl whitespace-nowrap z-40 min-w-[260px]">
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Controller ID:</span>
                      <span className="font-mono">{controller.id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Type:</span>
                      <span className="font-mono text-[10px]">{controllerInfo.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Application:</span>
                      <span className="font-mono text-[10px]">{controller.app || controllerConfig?.app || controllerStatus?.app || 'default'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Protocol:</span>
                      <span>{controller.protocol || 'OpenFlow'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Port:</span>
                      <span>{controllerConfig?.port || controllerStatus?.port || controller.port || '6633'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">IP:</span>
                      <span className="font-mono">{controller.ip || '127.0.0.1'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">PID:</span>
                      <span className="font-mono">{controllerStatus?.pid || 'N/A'}</span>
                    </div>
                    {controllerStats?.controller && (
                      <>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Connections:</span>
                          <span>{controllerStats.controller.connections || 0}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600">Memory:</span>
                          <span>{controllerStats.controller.memory_usage || 'N/A'}</span>
                        </div>
                      </>
                    )}
                    <div className="flex justify-between">
                      <span className="text-gray-600">Status:</span>
                      <span className={`font-semibold ${isActive ? 'text-green-500' : 'text-red-500'}`}>
                        {isActive ? 'Online' : 'Offline'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Draggable>
      );
      } catch (error) {
        console.error('Error rendering controller:', error);
        return null;
      }
    });
  };

  // Render routers
  const renderRouters = () => {
    return routers.map(router => {
      const pos = nodePositions[router.id];
      if (!pos) return null;

      const isActive = networkStatus.running;
      const hasFlows = flowStats[router.id]?.flows?.length > 0;
      const controllerConnected = controllerStatus?.running === true || controllerStatus?.status === 'running';

      const offsetX = 45;
      const offsetY = 45;

      return (
        <Draggable
          key={router.id}
          bounds="parent"
          position={{ x: pos.x - offsetX, y: pos.y - offsetY }}
          onStop={(e, data) => {
            handleDragStop(router.id, offsetX, offsetY, data);
          }}
        >
          <div
            style={{ position: 'absolute', left: 0, top: 0 }}
            className={`flex flex-col items-center transition-all duration-500 cursor-pointer group ${hoveredNode === router.id ? 'scale-110 z-30' : 'z-20'
              }`}
            onMouseEnter={() => setHoveredNode(router.id)}
            onMouseLeave={() => setHoveredNode(null)}
            onDoubleClick={() => onRemoveNode && onRemoveNode(router.id)}
          >
            <div className="relative">
              <div
                className={`w-24 h-24 bg-gradient-to-br rounded-3xl flex items-center justify-center shadow-xl border-2 backdrop-blur-sm transition-all duration-300 ${isActive
                    ? 'from-emerald-400 via-emerald-500 to-emerald-600 border-emerald-300 shadow-emerald-200'
                    : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300'
                  }`}
              >
                <div className="relative">
                  {/* Router symbol */}
                  <svg
                    className="w-12 h-12 text-white drop-shadow"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <rect x="3" y="11" width="18" height="7" rx="2"
                      fill="currentColor" stroke="currentColor" />
                    <path d="M6 11V5" />
                    <path d="M18 11V5" />
                    <path d="M12 4.5c1.6 0 3 .6 4.2 1.8" opacity=".7" />
                    <path d="M12 6.3c.9 0 1.7.3 2.4 1" opacity=".7" />
                    <circle cx="8" cy="14.5" r=".9" fill="white" opacity=".9" stroke="none" />
                    <circle cx="11" cy="14.5" r=".9" fill="white" opacity=".6" stroke="none" />
                    <circle cx="14" cy="14.5" r=".9" fill="white" opacity=".4" stroke="none" />
                    <rect x="16.5" y="13.2" width="3" height="2.6" rx=".3" fill="white" opacity=".2" stroke="none" />
                  </svg>
                </div>
              </div>

              {/* Controller connection indicator */}
              {controllerConnected && isActive && (
                <div className="absolute -top-2 -right-2 w-7 h-7 bg-emerald-500 rounded-full flex items-center justify-center border-2 border-white shadow">
                  <div className="w-4 h-4 bg-white rounded-full animate-pulse"></div>
                </div>
              )}

              {/* Active flows indicator */}
              {hasFlows && (
                <div className="absolute -bottom-2 -left-2 w-6 h-6 bg-teal-500 rounded-full flex items-center justify-center border-2 border-white">
                  <Activity className="w-4 h-4 text-white" />
                </div>
              )}

              {/* Status dot */}
              <div
                className={`absolute -bottom-1 -right-1 w-5 h-5 rounded-full animate-pulse ${isActive ? 'bg-green-500' : 'bg-red-500'
                  }`}
              ></div>
            </div>

            <div className="mt-3 text-center">
              <div className="text-sm font-bold text-gray-800 drop-shadow-sm">{router.id}</div>
              <div className={`text-xs font-medium ${isActive ? 'text-emerald-600' : 'text-gray-500'}`}>
                {router.status || (isActive ? 'Active' : 'Inactive')}
              </div>

              {/* Tooltip */}
              {hoveredNode === router.id && (
                <div className="absolute top-full mt-3 left-1/2 transform -translate-x-1/2 bg-white/90 backdrop-blur-sm border border-gray-300 shadow-xl text-gray-800 text-xs px-4 py-3 rounded-xl whitespace-nowrap z-40 min-w-[220px]">
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Router ID:</span>
                      <span className="font-mono">{router.id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Type:</span>
                      <span>Layer 3 Router</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Interfaces:</span>
                      <span>{router.interfaces?.length || 4}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Routing Protocol:</span>
                      <span>OSPF/BGP</span>
                    </div>
                    {flowStats[router.id] && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Routes:</span>
                        <span>{flowStats[router.id].flows?.length || 0}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-gray-600">Status:</span>
                      <span className={`font-semibold ${isActive ? 'text-green-500' : 'text-red-500'}`}>
                        {isActive ? 'Online' : 'Offline'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Draggable>
      );
    });
  };

  // Render switches
  const renderSwitches = () => {
    return switches.map(sw => {
      const pos = nodePositions[sw.id];
      if (!pos) return null;

      const isActive = networkStatus.running;
      const hasFlows = flowStats[sw.id]?.flows?.length > 0;
      const controllerConnected = controllerStatus?.running === true || controllerStatus?.status === 'running';
      const switchInfo = getSwitchTypeInfo(sw);
      const IconComponent = switchInfo.icon;

      const offsetX = 40;
      const offsetY = 40;

      return (
        <Draggable
          key={sw.id}
          bounds="parent"
          position={{ x: pos.x - offsetX, y: pos.y - offsetY }}
          onStop={(e, data) => {
            handleDragStop(sw.id, offsetX, offsetY, data);
          }}
        >
          <div
            style={{ position: 'absolute', left: 0, top: 0 }}
            className={`flex flex-col items-center transition-all duration-500 cursor-pointer group ${hoveredNode === sw.id ? 'scale-110 z-30' : 'z-20'
              }`}
            onMouseEnter={() => setHoveredNode(sw.id)}
            onMouseLeave={() => setHoveredNode(null)}
            onDoubleClick={() => onRemoveNode && onRemoveNode(sw.id)}
          >
            <div className="relative">
              <div
                className={`w-20 h-20 bg-gradient-to-br rounded-2xl flex items-center justify-center shadow-lg border-2 backdrop-blur-sm transition-all duration-300 ${switchInfo.color(isActive)}`}
                style={{ border: '2px solid rgba(255,255,255,0.5)' }}
              >
                <IconComponent className="w-10 h-10 text-white drop-shadow" />
                <div className="absolute -bottom-6 text-xs font-bold text-gray-700">
                  {sw.id}
                </div>
              </div>

              {/* Controller connection indicator */}
              {controllerConnected && isActive && (
                <div className="absolute -top-2 -right-2 w-6 h-6 bg-blue-500 rounded-full flex items-center justify-center border-2 border-white shadow">
                  <div className="w-3 h-3 bg-white rounded-full animate-pulse"></div>
                </div>
              )}

              {/* Active flows indicator */}
              {hasFlows && (
                <div className="absolute -bottom-2 -left-2 w-5 h-5 bg-indigo-500 rounded-full flex items-center justify-center border-2 border-white">
                  <Activity className="w-3 h-3 text-white" />
                </div>
              )}

              {/* Status dot */}
              <div
                className={`absolute -bottom-1 -right-1 w-4 h-4 rounded-full animate-pulse ${isActive ? 'bg-green-500' : 'bg-red-500'
                  }`}
              ></div>
            </div>

            <div className="mt-3 text-center">
              <div className="text-sm font-bold text-gray-800 drop-shadow-sm">{sw.id}</div>
              <div className={`text-xs font-medium ${isActive ? 'text-blue-500' : 'text-gray-500'}`}>
                {sw.status || (isActive ? 'Active' : 'Inactive')}
              </div>

              {/* Tooltip */}
              {hoveredNode === sw.id && (
                <div className="absolute top-full mt-3 left-1/2 transform -translate-x-1/2 bg-white/90 backdrop-blur-sm border border-gray-300 shadow-xl text-gray-800 text-xs px-4 py-3 rounded-xl whitespace-nowrap z-40 min-w-[220px]">
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Switch ID:</span>
                      <span className="font-mono">{sw.id}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Type:</span>
                      <span>{switchInfo.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Protocol:</span>
                      <span>{switchInfo.protocol}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Ports:</span>
                      <span>{sw.ports?.length || 3}</span>
                    </div>
                    {switchInfo.protocol === 'OpenFlow' && sw.dpid && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">DPID:</span>
                        <span className="font-mono">{sw.dpid}</span>
                      </div>
                    )}
                    {flowStats[sw.id] && (
                      <div className="flex justify-between">
                        <span className="text-gray-600">Flows:</span>
                        <span>{flowStats[sw.id].flows?.length || 0}</span>
                      </div>
                    )}
                    <div className="flex justify-between">
                      <span className="text-gray-600">Controller:</span>
                      <span className={`font-semibold ${controllerConnected ? 'text-green-500' : 'text-red-500'}`}>
                        {controllerConnected ? 'Connected' : 'Disconnected'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Status:</span>
                      <span className={`font-semibold ${isActive ? 'text-green-500' : 'text-red-500'}`}>
                        {isActive ? 'Online' : 'Offline'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Draggable>
      );
    });
  };

  // Render hosts
  const renderHosts = () => {
    return hosts.map(host => {
      const pos = nodePositions[host.id];
      if (!pos) return null;

      const isActive = networkStatus.running;
      const isSelected = selectedHost === host.id;

      const offsetX = 32;
      const offsetY = 32;

      return (
        <Draggable
          key={host.id}
          bounds="parent"
          position={{ x: pos.x - offsetX, y: pos.y - offsetY }}
          onStop={(e, data) => {
            handleDragStop(host.id, offsetX, offsetY, data);
          }}
        >
          <div
            style={{ position: 'absolute', left: 0, top: 0 }}
            className={`flex flex-col items-center transition-all duration-500 cursor-pointer group ${hoveredNode === host.id ? 'scale-110 z-30' : 'z-20'
              } ${isSelected ? 'ring-4 ring-cyan-400 rounded-3xl p-1' : ''}`}
            onClick={() => setSelectedHost(host.id)}
            onMouseEnter={() => setHoveredNode(host.id)}
            onMouseLeave={() => setHoveredNode(null)}
            onDoubleClick={() => onRemoveNode && onRemoveNode(host.id)}
          >
            <div className="relative">
              <div
                className={`w-16 h-16 bg-gradient-to-br rounded-xl flex items-center justify-center shadow-lg border-2 transition-all duration-300 ${isActive
                    ? 'from-indigo-400 via-indigo-500 to-indigo-600 border-indigo-300 shadow-indigo-200'
                    : 'from-gray-200 via-gray-300 to-gray-400 border-gray-300'
                  }`}
              >
                <Monitor className="w-8 h-8 text-white drop-shadow" />
              </div>

              <div
                className={`absolute -top-1 -right-1 w-4 h-4 rounded-full animate-pulse ${isActive ? 'bg-green-500' : 'bg-red-500'
                  }`}
              ></div>
            </div>

            <div className="mt-2 text-center">
              <div className="text-xs font-bold text-gray-800 drop-shadow-sm">{host.id}</div>
              <div className="text-[10px] text-indigo-500 font-mono">{host.ip}</div>

              {/* Tooltip */}
              {hoveredNode === host.id && (
                <div className="absolute top-full mt-3 left-1/2 transform -translate-x-1/2 bg-white/90 backdrop-blur-sm border border-gray-300 shadow-xl text-gray-800 text-xs px-4 py-3 rounded-xl whitespace-nowrap z-40 min-w-[180px]">
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-gray-600">IP Address:</span>
                      <span className="font-mono">{host.ip}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">MAC Address:</span>
                      <span className="font-mono text-[10px]">{host.mac || 'auto'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Type:</span>
                      <span>Virtual Host</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Status:</span>
                      <span className={`font-semibold ${isActive ? 'text-green-500' : 'text-red-500'}`}>
                        {isActive ? 'Online' : 'Offline'}
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </Draggable>
      );
    });
  };

  return (
    <div
      ref={ref}
      className="relative h-full w-full bg-white overflow-hidden border border-gray-200 shadow-lg"
    >
      {/* Grid Background */}
      <div className="absolute inset-0 opacity-10 pointer-events-none">
        <svg width="100%" height="100%">
          <defs>
            <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
              <path d="M 30 0 L 0 0 0 30" fill="none" stroke="#cbd5e1" strokeWidth="1" />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
        </svg>
      </div>

      {/* Links */}
      {renderLinks()}

      {/* Nodes */}
      {renderControllers()}
      {renderRouters()}
      {renderSwitches()}
      {renderHosts()}

      {/* Live Metrics Overlay */}
      {networkStatus.running && (
        <div className="absolute top-6 left-6 bg-white/90 backdrop-blur-xl rounded-2xl p-4 border border-gray-300 shadow-xl min-w-[280px]">
          <div className="text-gray-800 space-y-3">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
              <span className="font-bold text-lg">Live Network</span>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-gray-600">Uptime</div>
                <div className="font-mono text-green-600">{networkMetrics.uptime}</div>
              </div>
              <div>
                <div className="text-gray-600">Packets</div>
                <div className="font-mono text-blue-600">
                  {networkMetrics.packets_transferred.toLocaleString()}
                </div>
              </div>
              <div>
                <div className="text-gray-600">Bandwidth</div>
                <div className="font-mono text-purple-600">
                  {networkMetrics.bandwidth_mbps.toFixed(1)} Mbps
                </div>
              </div>
              <div>
                <div className="text-gray-600">Latency</div>
                <div className="font-mono text-orange-600">
                  {networkMetrics.latency_ms.toFixed(1)} ms
                </div>
              </div>
              <div>
                <div className="text-gray-600">Data</div>
                <div className="font-mono text-cyan-600">
                  {formatBytes(networkMetrics.total_bytes)}
                </div>
              </div>
              <div>
                <div className="text-gray-600">Flows</div>
                <div className="font-mono text-pink-600">
                  {networkMetrics.active_flows}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Connection Status Badge */}
      <div className="absolute top-6 right-6">
        <div
          className={`flex items-center gap-2 px-3 py-2 rounded-full text-xs font-semibold ${connectionStatus === 'connected'
              ? 'bg-green-100 text-green-700 border border-green-300'
              : connectionStatus === 'connecting'
                ? 'bg-yellow-100 text-yellow-700 border border-yellow-300'
                : 'bg-red-100 text-red-700 border border-red-300'
            }`}
        >
          <Circle className={`w-3 h-3 ${connectionStatus === 'connecting' ? 'animate-pulse' : ''}`} />
          <span className="capitalize">{connectionStatus}</span>
        </div>
      </div>
    </div>
  );
});

TopologyRenderer.displayName = 'TopologyRenderer';

export default TopologyRenderer;