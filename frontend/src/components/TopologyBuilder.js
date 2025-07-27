import React, { useState, useRef, useEffect, useCallback } from 'react';
import { 
  Plus, 
  Trash2, 
  Save, 
  Download, 
  Upload, 
  Network, 
  Monitor, 
  Server, 
  Router,
  Settings,
  Eye,
  EyeOff,
  Copy,
  RotateCcw,
  CheckCircle,
  XCircle,
  Layers,
  Link as LinkIcon,
  Keyboard,
  Info,
  HelpCircle
} from 'lucide-react';
import Draggable from 'react-draggable';

const TopologyBuilder = ({ 
  isOpen, 
  onClose, 
  onCreateTopology, 
  availableTemplates = [],
  onSaveTemplate 
}) => {
  const [nodes, setNodes] = useState([]);
  const [links, setLinks] = useState([]);
  const [selectedNodeType, setSelectedNodeType] = useState('host');
  const [selectedNode, setSelectedNode] = useState(null);
  const [selectedLink, setSelectedLink] = useState(null);
  const [isLinkMode, setIsLinkMode] = useState(false);
  const [linkStart, setLinkStart] = useState(null);
  const [topologyName, setTopologyName] = useState('Custom Topology');
  const [showGrid, setShowGrid] = useState(true);
  const [dragPositions, setDragPositions] = useState({});
  const [showLegend, setShowLegend] = useState(false);
  const [showShortcuts, setShowShortcuts] = useState(false);
  const canvasRef = useRef(null);
  const fileInputRef = useRef(null);

  const nodeTypes = {
    host: { 
      icon: Monitor, 
      color: 'from-indigo-400 to-indigo-600', 
      label: 'Host',
      defaultPrefix: 'h',
      defaultConfig: { ip: 'auto', mac: 'auto' }
    },
    switch: { 
      icon: Network, 
      color: 'from-blue-400 to-blue-600', 
      label: 'Switch',
      defaultPrefix: 's',
      defaultConfig: { openflow_version: '1.3', dpid: 'auto' }
    },
    router: { 
      icon: Router, 
      color: 'from-emerald-400 to-emerald-600', 
      label: 'Router',
      defaultPrefix: 'r',
      defaultConfig: { routing_protocol: 'static' }
    },
    controller: { 
      icon: Server, 
      color: 'from-red-400 to-red-600', 
      label: 'Controller',
      defaultPrefix: 'c',
      defaultConfig: { port: 6633, ip: '127.0.0.1' }
    }
  };

  const bandwidthOptions = [
    '10M', '100M', '1G', '10G', '40G', '100G'
  ];

  const shortcuts = [
    { key: 'H', action: 'Add Host', description: 'Create a new host node' },
    { key: 'S', action: 'Add Switch', description: 'Create a new switch node' },
    { key: 'R', action: 'Add Router', description: 'Create a new router node' },
    { key: 'C', action: 'Add Controller', description: 'Create a new controller node' },
    { key: 'L', action: 'Toggle Link Mode', description: 'Switch between select and link creation mode' },
    { key: 'G', action: 'Toggle Grid', description: 'Show/hide the background grid' },
    { key: 'Del', action: 'Delete', description: 'Delete selected node or link' },
    { key: 'Esc', action: 'Deselect', description: 'Clear selection and exit link mode' },
    { key: '?', action: 'Show Help', description: 'Toggle this shortcuts panel' }
  ];

  const templates = [
    {
      id: 'linear',
      name: 'Linear Topology',
      description: '4 hosts connected in a line through switches',
      preview: '🖥️—🔀—🔀—🖥️',
      topology: {
        nodes: [
          { id: 'h1', type: 'host', x: 100, y: 200, ip: '10.0.0.1' },
          { id: 's1', type: 'switch', x: 200, y: 200 },
          { id: 's2', type: 'switch', x: 300, y: 200 },
          { id: 'h2', type: 'host', x: 400, y: 200, ip: '10.0.0.2' }
        ],
        links: [
          { source: 'h1', target: 's1', bandwidth: '10M' },
          { source: 's1', target: 's2', bandwidth: '1G' },
          { source: 's2', target: 'h2', bandwidth: '10M' }
        ]
      }
    },
    {
      id: 'star',
      name: 'Star Topology',
      description: 'Central switch with 4 connected hosts',
      preview: '🖥️\n ↗🔀↖\n🖥️ ↙ ↘🖥️',
      topology: {
        nodes: [
          { id: 's1', type: 'switch', x: 250, y: 200 },
          { id: 'h1', type: 'host', x: 150, y: 100, ip: '10.0.0.1' },
          { id: 'h2', type: 'host', x: 350, y: 100, ip: '10.0.0.2' },
          { id: 'h3', type: 'host', x: 150, y: 300, ip: '10.0.0.3' },
          { id: 'h4', type: 'host', x: 350, y: 300, ip: '10.0.0.4' }
        ],
        links: [
          { source: 'h1', target: 's1', bandwidth: '10M' },
          { source: 'h2', target: 's1', bandwidth: '10M' },
          { source: 'h3', target: 's1', bandwidth: '10M' },
          { source: 'h4', target: 's1', bandwidth: '10M' }
        ]
      }
    },
    {
      id: 'tree',
      name: 'Tree Topology',
      description: 'Hierarchical tree with core, aggregation, and access layers',
      preview: '🔀\n↙ ↘\n🔀 🔀\n🖥️🖥️',
      topology: {
        nodes: [
          { id: 's1', type: 'switch', x: 250, y: 100 },
          { id: 's2', type: 'switch', x: 150, y: 200 },
          { id: 's3', type: 'switch', x: 350, y: 200 },
          { id: 'h1', type: 'host', x: 100, y: 300, ip: '10.0.0.1' },
          { id: 'h2', type: 'host', x: 200, y: 300, ip: '10.0.0.2' },
          { id: 'h3', type: 'host', x: 300, y: 300, ip: '10.0.0.3' },
          { id: 'h4', type: 'host', x: 400, y: 300, ip: '10.0.0.4' }
        ],
        links: [
          { source: 's1', target: 's2', bandwidth: '1G' },
          { source: 's1', target: 's3', bandwidth: '1G' },
          { source: 's2', target: 'h1', bandwidth: '100M' },
          { source: 's2', target: 'h2', bandwidth: '100M' },
          { source: 's3', target: 'h3', bandwidth: '100M' },
          { source: 's3', target: 'h4', bandwidth: '100M' }
        ]
      }
    },
    {
      id: 'mesh',
      name: 'Mesh Topology',
      description: 'Fully connected mesh of 4 switches with hosts',
      preview: '🔀—🔀\n| × |\n🔀—🔀',
      topology: {
        nodes: [
          { id: 's1', type: 'switch', x: 150, y: 150 },
          { id: 's2', type: 'switch', x: 350, y: 150 },
          { id: 's3', type: 'switch', x: 150, y: 300 },
          { id: 's4', type: 'switch', x: 350, y: 300 },
          { id: 'h1', type: 'host', x: 50, y: 150, ip: '10.0.0.1' },
          { id: 'h2', type: 'host', x: 450, y: 150, ip: '10.0.0.2' },
          { id: 'h3', type: 'host', x: 50, y: 300, ip: '10.0.0.3' },
          { id: 'h4', type: 'host', x: 450, y: 300, ip: '10.0.0.4' }
        ],
        links: [
          { source: 's1', target: 's2', bandwidth: '1G' },
          { source: 's1', target: 's3', bandwidth: '1G' },
          { source: 's1', target: 's4', bandwidth: '1G' },
          { source: 's2', target: 's3', bandwidth: '1G' },
          { source: 's2', target: 's4', bandwidth: '1G' },
          { source: 's3', target: 's4', bandwidth: '1G' },
          { source: 'h1', target: 's1', bandwidth: '100M' },
          { source: 'h2', target: 's2', bandwidth: '100M' },
          { source: 'h3', target: 's3', bandwidth: '100M' },
          { source: 'h4', target: 's4', bandwidth: '100M' }
        ]
      }
    }
  ];

  // Keyboard shortcuts handler
  const handleKeyDown = useCallback((e) => {
    if (!isOpen) return;
    
    // Ignore shortcuts when typing in input fields
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    const key = e.key.toLowerCase();
    
    switch (key) {
      case 'h':
        e.preventDefault();
        addNode('host');
        break;
      case 's':
        e.preventDefault();
        addNode('switch');
        break;
      case 'r':
        e.preventDefault();
        addNode('router');
        break;
      case 'c':
        e.preventDefault();
        addNode('controller');
        break;
      case 'l':
        e.preventDefault();
        toggleLinkMode();
        break;
      case 'g':
        e.preventDefault();
        setShowGrid(prev => !prev);
        break;
      case 'delete':
      case 'backspace':
        e.preventDefault();
        handleDelete();
        break;
      case 'escape':
        e.preventDefault();
        handleEscape();
        break;
      case '?':
        e.preventDefault();
        setShowShortcuts(prev => !prev);
        break;
      default:
        break;
    }
  }, [isOpen, selectedNode, selectedLink]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const addNode = useCallback((type, x = 250, y = 200) => {
    const existingNodes = nodes.filter(n => n.type === type);
    const nodeConfig = nodeTypes[type];
    const nodeId = `${nodeConfig.defaultPrefix}${existingNodes.length + 1}`;
    
    const newNode = {
      id: nodeId,
      type,
      x: x + Math.random() * 50 - 25,
      y: y + Math.random() * 50 - 25,
      ...nodeConfig.defaultConfig
    };

    if (type === 'host') {
      newNode.ip = `10.0.0.${existingNodes.length + 1}`;
    }

    setNodes(prev => [...prev, newNode]);
  }, [nodes]);

  const deleteNode = useCallback((nodeId) => {
    setNodes(prev => prev.filter(n => n.id !== nodeId));
    setLinks(prev => prev.filter(l => l.source !== nodeId && l.target !== nodeId));
    if (selectedNode?.id === nodeId) {
      setSelectedNode(null);
    }
  }, [selectedNode]);

  const toggleLinkMode = useCallback(() => {
    setIsLinkMode(prev => !prev);
    setLinkStart(null);
  }, []);

  const handleDelete = useCallback(() => {
    if (selectedNode) {
      deleteNode(selectedNode.id);
    } else if (selectedLink !== null) {
      deleteLink(selectedLink.index);
    }
  }, [selectedNode, selectedLink, deleteNode]);

  const handleEscape = useCallback(() => {
    setSelectedNode(null);
    setSelectedLink(null);
    setIsLinkMode(false);
    setLinkStart(null);
  }, []);

  const handleNodeClick = useCallback((node) => {
    if (isLinkMode) {
      if (!linkStart) {
        setLinkStart(node);
      } else if (linkStart.id !== node.id) {
        const existingLink = links.find(l => 
          (l.source === linkStart.id && l.target === node.id) ||
          (l.source === node.id && l.target === linkStart.id)
        );
        
        if (!existingLink) {
          const newLink = {
            source: linkStart.id,
            target: node.id,
            bandwidth: node.type === 'host' || linkStart.type === 'host' ? '100M' : '1G',
            status: 'up'
          };
          setLinks(prev => [...prev, newLink]);
        }
        setLinkStart(null);
        setIsLinkMode(false);
      }
    } else {
      setSelectedNode(node);
      setSelectedLink(null);
    }
  }, [isLinkMode, linkStart, links]);

  const updateNodeProperty = useCallback((property, value) => {
    if (!selectedNode) return;
    
    setNodes(prev => prev.map(n => 
      n.id === selectedNode.id 
        ? { ...n, [property]: value }
        : n
    ));
    setSelectedNode(prev => ({ ...prev, [property]: value }));
  }, [selectedNode]);

  const handleLinkClick = useCallback((link, index) => {
    setSelectedLink({ ...link, index });
    setSelectedNode(null);
  }, []);

  const updateLinkProperty = useCallback((property, value) => {
    if (selectedLink === null || selectedLink.index === undefined) return;
    
    setLinks(prev => {
      const updated = [...prev];
      updated[selectedLink.index] = {
        ...updated[selectedLink.index],
        [property]: value
      };
      return updated;
    });
    
    setSelectedLink(prev => ({
      ...prev,
      [property]: value
    }));
  }, [selectedLink]);

  const deleteLink = useCallback((linkIndex) => {
    setLinks(prev => prev.filter((_, index) => index !== linkIndex));
    if (selectedLink && selectedLink.index === linkIndex) {
      setSelectedLink(null);
    }
  }, [selectedLink]);

  const loadTemplate = useCallback((template) => {
    setNodes(template.topology.nodes);
    setLinks(template.topology.links);
    setTopologyName(template.name);
    setDragPositions({});
    setSelectedNode(null);
    setSelectedLink(null);
  }, []);

  const clearTopology = useCallback(() => {
    setNodes([]);
    setLinks([]);
    setSelectedNode(null);
    setSelectedLink(null);
    setLinkStart(null);
    setIsLinkMode(false);
    setDragPositions({});
    setTopologyName('Custom Topology');
  }, []);

  const exportTopology = useCallback(() => {
    const topology = {
      name: topologyName,
      nodes: nodes.map(node => ({
        ...node,
        x: dragPositions[node.id]?.x || node.x,
        y: dragPositions[node.id]?.y || node.y
      })),
      links,
      metadata: {
        created: new Date().toISOString(),
        version: '1.0'
      }
    };

    const blob = new Blob([JSON.stringify(topology, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${topologyName.replace(/\s+/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [topologyName, nodes, links, dragPositions]);

  const importTopology = useCallback((event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const topology = JSON.parse(e.target.result);
        setNodes(topology.nodes || []);
        setLinks(topology.links || []);
        setTopologyName(topology.name || 'Imported Topology');
        setDragPositions({});
        setSelectedNode(null);
        setSelectedLink(null);
      } catch (error) {
        alert('Error loading topology file: ' + error.message);
      }
    };
    reader.readAsText(file);
  }, []);

  const createTopology = useCallback(() => {
    const finalNodes = nodes.map(node => ({
      ...node,
      x: dragPositions[node.id]?.x || node.x,
      y: dragPositions[node.id]?.y || node.y
    }));

    const topology = {
      name: topologyName,
      nodes: finalNodes,
      links
    };

    onCreateTopology(topology);
    onClose();
  }, [nodes, links, dragPositions, topologyName, onCreateTopology, onClose]);

  if (!isOpen) return null;

  return React.createElement('div', {
    className: "fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
  }, 
    React.createElement('div', {
      className: "bg-white rounded-2xl shadow-2xl w-full max-w-7xl h-[90vh] flex flex-col"
    },
      // Header
      React.createElement('div', {
        className: "px-6 py-4 border-b border-gray-200 flex items-center justify-between"
      },
        React.createElement('div', {
          className: "flex items-center gap-4"
        },
          React.createElement('h2', {
            className: "text-2xl font-bold text-gray-800 flex items-center gap-3"
          },
            React.createElement(Layers, { className: "w-7 h-7 text-indigo-500" }),
            "Topology Builder"
          ),
          React.createElement('input', {
            type: "text",
            value: topologyName,
            onChange: (e) => setTopologyName(e.target.value),
            className: "px-3 py-2 border border-gray-300 rounded-lg text-gray-700 bg-white focus:ring-2 focus:ring-indigo-500",
            placeholder: "Topology Name"
          })
        ),
        React.createElement('button', {
          onClick: onClose,
          className: "text-gray-500 hover:text-gray-700 transition-colors"
        },
          React.createElement(XCircle, { className: "w-6 h-6" })
        )
      ),
      
      React.createElement('div', {
        className: "flex flex-1 overflow-hidden"
      },
        // Left Sidebar - Tools
        React.createElement('div', {
          className: "w-80 border-r border-gray-200 bg-gray-50 p-4 overflow-y-auto"
        },
          // Node Types
          React.createElement('div', {
            className: "mb-6"
          },
            React.createElement('h3', {
              className: "text-lg font-semibold text-gray-800 mb-3"
            }, "Add Nodes"),
            React.createElement('div', {
              className: "grid grid-cols-2 gap-2"
            },
              Object.entries(nodeTypes).map(([type, config]) => {
                const IconComponent = config.icon;
                const shortcutKey = type.charAt(0).toUpperCase();
                return React.createElement('button', {
                  key: type,
                  onClick: () => addNode(type),
                  className: `p-3 rounded-xl border-2 transition-all duration-200 hover:scale-105 relative ${
                    selectedNodeType === type
                      ? 'border-indigo-500 bg-indigo-50'
                      : 'border-gray-300 bg-white hover:border-gray-400'
                  }`
                },
                  React.createElement(IconComponent, { className: "w-6 h-6 mx-auto mb-1 text-gray-600" }),
                  React.createElement('div', {
                    className: "text-xs font-medium text-gray-700"
                  }, config.label),
                  React.createElement('kbd', {
                    className: "absolute top-1 right-1 px-1 py-0.5 bg-gray-200 text-gray-600 text-xs rounded"
                  }, shortcutKey)
                );
              })
            )
          ),
          
          // Tools
          React.createElement('div', {
            className: "mb-6"
          },
            React.createElement('h3', {
              className: "text-lg font-semibold text-gray-800 mb-3 flex items-center justify-between"
            },
              "Tools",
              React.createElement('div', {
                className: "flex gap-1"
              },
                React.createElement('button', {
                  onClick: () => setShowShortcuts(!showShortcuts),
                  className: "p-1 text-gray-500 hover:text-gray-700 transition-colors",
                  title: "Keyboard Shortcuts"
                },
                  React.createElement(Keyboard, { className: "w-4 h-4" })
                ),
                React.createElement('button', {
                  onClick: () => setShowLegend(!showLegend),
                  className: "p-1 text-gray-500 hover:text-gray-700 transition-colors",
                  title: "Legend"
                },
                  React.createElement(Info, { className: "w-4 h-4" })
                )
              )
            ),
            
            // Keyboard Shortcuts Panel
            showShortcuts && React.createElement('div', {
              className: "mb-4 p-3 bg-blue-50 border border-blue-200 rounded-xl"
            },
              React.createElement('h4', {
                className: "font-semibold text-blue-800 mb-2 flex items-center gap-2"
              },
                React.createElement(Keyboard, { className: "w-4 h-4" }),
                "Keyboard Shortcuts"
              ),
              React.createElement('div', {
                className: "space-y-1 text-xs"
              },
                shortcuts.map((shortcut, index) =>
                  React.createElement('div', {
                    key: index,
                    className: "flex items-center justify-between"
                  },
                    React.createElement('div', {
                      className: "flex items-center gap-2"
                    },
                      React.createElement('kbd', {
                        className: "px-2 py-1 bg-white border border-blue-300 rounded text-blue-800 font-mono"
                      }, shortcut.key),
                      React.createElement('span', {
                        className: "text-blue-700 font-medium"
                      }, shortcut.action)
                    )
                  )
                )
              ),
              React.createElement('div', {
                className: "mt-2 text-xs text-blue-600"
              },
                "Press ",
                React.createElement('kbd', {
                  className: "px-1 bg-white border border-blue-300 rounded"
                }, "?"),
                " to toggle this panel"
              )
            ),

            // Legend Panel
            showLegend && React.createElement('div', {
              className: "mb-4 p-3 bg-green-50 border border-green-200 rounded-xl"
            },
              React.createElement('h4', {
                className: "font-semibold text-green-800 mb-2 flex items-center gap-2"
              },
                React.createElement(Info, { className: "w-4 h-4" }),
                "Legend"
              ),
              React.createElement('div', {
                className: "space-y-2 text-xs"
              },
                Object.entries(nodeTypes).map(([type, config]) => {
                  const IconComponent = config.icon;
                  return React.createElement('div', {
                    key: type,
                    className: "flex items-center gap-2"
                  },
                    React.createElement('div', {
                      className: `w-6 h-6 bg-gradient-to-br ${config.color} rounded-lg flex items-center justify-center`
                    },
                      React.createElement(IconComponent, { className: "w-4 h-4 text-white" })
                    ),
                    React.createElement('span', {
                      className: "text-green-700 font-medium"
                    }, config.label),
                    React.createElement('span', {
                      className: "text-green-600"
                    }, `(${config.defaultPrefix})`)
                  );
                }),
                React.createElement('div', {
                  className: "border-t border-green-300 pt-2 mt-2"
                },
                  React.createElement('div', {
                    className: "flex items-center gap-2 mb-1"
                  },
                    React.createElement('div', {
                      className: "w-4 h-0.5 bg-blue-500"
                    }),
                    React.createElement('span', {
                      className: "text-green-700"
                    }, "Active Link")
                  ),
                  React.createElement('div', {
                    className: "flex items-center gap-2 mb-1"
                  },
                    React.createElement('div', {
                      className: "w-4 h-0.5 bg-red-500 opacity-50"
                    }),
                    React.createElement('span', {
                      className: "text-green-700"
                    }, "Down Link")
                  ),
                  React.createElement('div', {
                    className: "flex items-center gap-2"
                  },
                    React.createElement('div', {
                      className: "w-4 h-0.5 bg-yellow-500"
                    }),
                    React.createElement('span', {
                      className: "text-green-700"
                    }, "Selected Link")
                  )
                )
              )
            ),

            React.createElement('div', {
              className: "space-y-2"
            },
              React.createElement('button', {
                onClick: toggleLinkMode,
                className: `w-full p-3 rounded-xl border-2 transition-all duration-200 flex items-center gap-2 ${
                  isLinkMode
                    ? 'border-green-500 bg-green-50 text-green-700'
                    : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'
                }`
              },
                React.createElement(Network, { className: "w-5 h-5" }),
                isLinkMode ? 'Link Mode (Active)' : 'Create Links',
                React.createElement('kbd', {
                  className: "ml-auto px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded"
                }, "L")
              ),
              
              React.createElement('button', {
                onClick: () => setShowGrid(!showGrid),
                className: "w-full p-3 rounded-xl border-2 border-gray-300 bg-white text-gray-700 hover:border-gray-400 transition-all duration-200 flex items-center gap-2"
              },
                React.createElement(showGrid ? Eye : EyeOff, { className: "w-5 h-5" }),
                showGrid ? 'Hide Grid' : 'Show Grid',
                React.createElement('kbd', {
                  className: "ml-auto px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded"
                }, "G")
              ),
              
              React.createElement('button', {
                onClick: clearTopology,
                className: "w-full p-3 rounded-xl border-2 border-red-300 bg-red-50 text-red-700 hover:border-red-400 transition-all duration-200 flex items-center gap-2"
              },
                React.createElement(RotateCcw, { className: "w-5 h-5" }),
                "Clear All"
              )
            )
          ),

          // Templates
          React.createElement('div', {
            className: "mb-6"
          },
            React.createElement('h3', {
              className: "text-lg font-semibold text-gray-800 mb-3"
            }, "Templates"),
            React.createElement('div', {
              className: "space-y-2"
            },
              templates.map(template =>
                React.createElement('div', {
                  key: template.id,
                  className: "bg-white rounded-xl p-3 border border-gray-200"
                },
                  React.createElement('div', {
                    className: "flex items-center justify-between mb-2"
                  },
                    React.createElement('h4', {
                      className: "font-medium text-gray-800"
                    }, template.name),
                    React.createElement('button', {
                      onClick: () => loadTemplate(template),
                      className: "px-3 py-1 bg-indigo-100 text-indigo-700 rounded-lg text-xs hover:bg-indigo-200 transition-colors"
                    }, "Load")
                  ),
                  React.createElement('p', {
                    className: "text-xs text-gray-600 mb-2"
                  }, template.description),
                  React.createElement('div', {
                    className: "text-xs font-mono bg-gray-100 p-2 rounded text-center"
                  }, template.preview)
                )
              )
            )
          ),

          // File Operations
          React.createElement('div', {},
            React.createElement('h3', {
              className: "text-lg font-semibold text-gray-800 mb-3"
            }, "File Operations"),
            React.createElement('div', {
              className: "space-y-2"
            },
              React.createElement('button', {
                onClick: exportTopology,
                disabled: nodes.length === 0,
                className: "w-full p-3 rounded-xl border-2 border-green-300 bg-green-50 text-green-700 hover:border-green-400 transition-all duration-200 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              },
                React.createElement(Download, { className: "w-5 h-5" }),
                "Export JSON"
              ),
              
              React.createElement('button', {
                onClick: () => fileInputRef.current?.click(),
                className: "w-full p-3 rounded-xl border-2 border-blue-300 bg-blue-50 text-blue-700 hover:border-blue-400 transition-all duration-200 flex items-center gap-2"
              },
                React.createElement(Upload, { className: "w-5 h-5" }),
                "Import JSON"
              ),
              React.createElement('input', {
                ref: fileInputRef,
                type: "file",
                accept: ".json",
                onChange: importTopology,
                className: "hidden"
              })
            )
          )
        ),
        
        // Center Canvas
        React.createElement('div', {
          className: "flex-1 relative overflow-hidden"
        },
          React.createElement('div', {
            ref: canvasRef,
            className: "w-full h-full relative bg-white overflow-hidden",
            style: {
              backgroundImage: showGrid ? `
                linear-gradient(to right, #f1f5f9 1px, transparent 1px),
                linear-gradient(to bottom, #f1f5f9 1px, transparent 1px)
              ` : 'none',
              backgroundSize: showGrid ? '20px 20px' : 'auto'
            }
          },
            // Links
            links.map((link, index) => {
              const sourceNode = nodes.find(n => n.id === link.source);
              const targetNode = nodes.find(n => n.id === link.target);
              if (!sourceNode || !targetNode) return null;

              const sourcePos = {
                x: dragPositions[sourceNode.id]?.x || sourceNode.x,
                y: dragPositions[sourceNode.id]?.y || sourceNode.y
              };
              const targetPos = {
                x: dragPositions[targetNode.id]?.x || targetNode.x,
                y: dragPositions[targetNode.id]?.y || targetNode.y
              };

              const isSelected = selectedLink?.index === index;
              const isDown = link.status === 'down';

              return React.createElement('svg', {
                key: `link-${index}`,
                className: "absolute top-0 left-0 w-full h-full pointer-events-none"
              },
                React.createElement('line', {
                  x1: sourcePos.x,
                  y1: sourcePos.y,
                  x2: targetPos.x,
                  y2: targetPos.y,
                  stroke: isSelected ? "#f59e0b" : isDown ? "#ef4444" : "#3b82f6",
                  strokeWidth: isSelected ? "4" : "3",
                  strokeOpacity: "0.7",
                  strokeDasharray: isDown ? "5,5" : "0",
                  className: "cursor-pointer pointer-events-auto",
                  onClick: () => handleLinkClick(link, index)
                }),
                React.createElement('text', {
                  x: (sourcePos.x + targetPos.x) / 2,
                  y: (sourcePos.y + targetPos.y) / 2 - 10,
                  textAnchor: "middle",
                  fill: isSelected ? "#d97706" : isDown ? "#dc2626" : "#1d4ed8",
                  fontSize: "11",
                  fontWeight: "600",
                  className: "pointer-events-auto cursor-pointer",
                  onClick: () => handleLinkClick(link, index)
                }, link.bandwidth)
              );
            }),

            // Nodes
            nodes.map(node => {
              const nodeConfig = nodeTypes[node.type];
              const IconComponent = nodeConfig.icon;
              const position = dragPositions[node.id] || { x: node.x, y: node.y };

              return React.createElement(Draggable, {
                key: node.id,
                bounds: "parent",
                position: { x: position.x - 30, y: position.y - 30 },
                onStop: (e, data) => {
                  setDragPositions(prev => ({
                    ...prev,
                    [node.id]: { x: data.x + 30, y: data.y + 30 }
                  }));
                }
              },
                React.createElement('div', {
                  className: `absolute w-16 h-16 bg-gradient-to-br ${nodeConfig.color} rounded-xl shadow-lg border-2 cursor-pointer transition-all duration-200 hover:scale-110 flex items-center justify-center ${
                    selectedNode?.id === node.id ? 'border-yellow-400 ring-4 ring-yellow-200' : 'border-white'
                  } ${isLinkMode && linkStart?.id === node.id ? 'ring-4 ring-green-400' : ''}`,
                  onClick: () => handleNodeClick(node),
                  onDoubleClick: () => deleteNode(node.id)
                },
                  React.createElement(IconComponent, { className: "w-8 h-8 text-white" }),
                  React.createElement('div', {
                    className: "absolute -bottom-6 left-1/2 transform -translate-x-1/2 text-xs font-semibold text-gray-700 bg-white px-2 py-1 rounded shadow whitespace-nowrap"
                  }, node.id)
                )
              );
            }),

            // Instructions
            nodes.length === 0 && React.createElement('div', {
              className: "absolute inset-0 flex items-center justify-center"
            },
              React.createElement('div', {
                className: "text-center text-gray-500 max-w-md"
              },
                React.createElement(Layers, { className: "w-16 h-16 mx-auto mb-4 text-gray-300" }),
                React.createElement('h3', {
                  className: "text-xl font-semibold mb-2"
                }, "Start Building Your Topology"),
                React.createElement('p', {
                  className: "mb-4"
                }, "Add nodes from the left panel or load a template"),
                React.createElement('div', {
                  className: "text-sm bg-gray-100 p-4 rounded-lg"
                },
                  React.createElement('h4', {
                    className: "font-semibold mb-2 flex items-center gap-2"
                  },
                    React.createElement(Keyboard, { className: "w-4 h-4" }),
                    "Quick Actions:"
                  ),
                  React.createElement('div', {
                    className: "space-y-1 text-left"
                  },
                    React.createElement('div', {
                      className: "flex justify-between"
                    },
                      React.createElement('span', {}, "Add Host:"),
                      React.createElement('kbd', {
                        className: "px-2 py-1 bg-white border rounded text-xs"
                      }, "H")
                    ),
                    React.createElement('div', {
                      className: "flex justify-between"
                    },
                      React.createElement('span', {}, "Add Switch:"),
                      React.createElement('kbd', {
                        className: "px-2 py-1 bg-white border rounded text-xs"
                      }, "S")
                    ),
                    React.createElement('div', {
                      className: "flex justify-between"
                    },
                      React.createElement('span', {}, "Link Mode:"),
                      React.createElement('kbd', {
                        className: "px-2 py-1 bg-white border rounded text-xs"
                      }, "L")
                    ),
                    React.createElement('div', {
                      className: "flex justify-between"
                    },
                      React.createElement('span', {}, "Help:"),
                      React.createElement('kbd', {
                        className: "px-2 py-1 bg-white border rounded text-xs"
                      }, "?")
                    )
                  ),
                  React.createElement('div', {
                    className: "mt-3 pt-3 border-t border-gray-300"
                  },
                    React.createElement('p', {
                      className: "text-xs"
                    }, "• Click nodes to select • Double-click to delete • Drag to reposition • Use Link Mode to connect")
                  )
                )
              )
            ),

            // Link Mode Indicator
            isLinkMode && React.createElement('div', {
              className: "absolute top-4 left-4 bg-green-100 border border-green-300 text-green-700 px-4 py-2 rounded-lg flex items-center gap-2"
            },
              React.createElement(Network, { className: "w-4 h-4" }),
              React.createElement('span', {},
                linkStart 
                  ? `Click target node to connect to ${linkStart.id}` 
                  : 'Click first node to start creating a link'
              ),
              React.createElement('kbd', {
                className: "px-2 py-1 bg-green-200 text-green-800 text-xs rounded ml-2"
              }, "ESC to cancel")
            ),

            // Floating Help Button
            React.createElement('button', {
              onClick: () => setShowShortcuts(!showShortcuts),
              className: "absolute bottom-4 right-4 w-12 h-12 bg-indigo-600 text-white rounded-full shadow-lg hover:bg-indigo-700 transition-all duration-200 flex items-center justify-center group",
              title: "Keyboard Shortcuts"
            },
              React.createElement(HelpCircle, { className: "w-6 h-6" }),
              React.createElement('span', {
                className: "absolute bottom-full right-0 mb-2 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap"
              }, "Press ? for shortcuts")
            )
          )
        ),
        
        // Right Sidebar - Properties
        React.createElement('div', {
          className: "w-80 border-l border-gray-200 bg-gray-50 p-4 overflow-y-auto"
        },
          selectedNode ? React.createElement('div', {},
            React.createElement('h3', {
              className: "text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2"
            },
              React.createElement(Settings, { className: "w-5 h-5" }),
              "Node Properties"
            ),
            
            React.createElement('div', {
              className: "space-y-4"
            },
              React.createElement('div', {},
                React.createElement('label', {
                  className: "block text-sm font-medium text-gray-700 mb-1"
                }, "Node ID"),
                React.createElement('input', {
                  type: "text",
                  value: selectedNode.id,
                  onChange: (e) => updateNodeProperty('id', e.target.value),
                  className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                })
              ),

              React.createElement('div', {},
                React.createElement('label', {
                  className: "block text-sm font-medium text-gray-700 mb-1"
                }, "Type"),
                React.createElement('select', {
                  value: selectedNode.type,
                  onChange: (e) => updateNodeProperty('type', e.target.value),
                  className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                },
                  Object.entries(nodeTypes).map(([type, config]) =>
                    React.createElement('option', {
                      key: type,
                      value: type
                    }, config.label)
                  )
                )
              ),

              selectedNode.type === 'host' && React.createElement('div', {},
                React.createElement('label', {
                  className: "block text-sm font-medium text-gray-700 mb-1"
                }, "IP Address"),
                React.createElement('input', {
                  type: "text",
                  value: selectedNode.ip || '',
                  onChange: (e) => updateNodeProperty('ip', e.target.value),
                  className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500",
                  placeholder: "10.0.0.1"
                })
              ),

              selectedNode.type === 'controller' && React.createElement(React.Fragment, {},
                React.createElement('div', {},
                  React.createElement('label', {
                    className: "block text-sm font-medium text-gray-700 mb-1"
                  }, "IP Address"),
                  React.createElement('input', {
                    type: "text",
                    value: selectedNode.ip || '',
                    onChange: (e) => updateNodeProperty('ip', e.target.value),
                    className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500",
                    placeholder: "127.0.0.1"
                  })
                ),
                React.createElement('div', {},
                  React.createElement('label', {
                    className: "block text-sm font-medium text-gray-700 mb-1"
                  }, "Port"),
                  React.createElement('input', {
                    type: "number",
                    value: selectedNode.port || '',
                    onChange: (e) => updateNodeProperty('port', parseInt(e.target.value)),
                    className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500",
                    placeholder: "6633"
                  })
                )
              ),

              React.createElement('div', {
                className: "pt-4 border-t border-gray-300"
              },
                React.createElement('button', {
                  onClick: () => deleteNode(selectedNode.id),
                  className: "w-full p-3 bg-red-50 text-red-700 border border-red-300 rounded-lg hover:bg-red-100 transition-colors flex items-center justify-center gap-2"
                },
                  React.createElement(Trash2, { className: "w-4 h-4" }),
                  "Delete Node"
                )
              )
            )
          ) : selectedLink ? React.createElement('div', {},
            React.createElement('h3', {
              className: "text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2"
            },
              React.createElement(LinkIcon, { className: "w-5 h-5" }),
              "Link Properties"
            ),
            
            React.createElement('div', {
              className: "space-y-4"
            },
              React.createElement('div', {},
                React.createElement('label', {
                  className: "block text-sm font-medium text-gray-700 mb-1"
                }, "Connection"),
                React.createElement('div', {
                  className: "w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-100"
                }, `${selectedLink.source} ↔ ${selectedLink.target}`)
              ),

              React.createElement('div', {},
                React.createElement('label', {
                  className: "block text-sm font-medium text-gray-700 mb-1"
                }, "Bandwidth"),
                React.createElement('select', {
                  value: selectedLink.bandwidth || '100M',
                  onChange: (e) => updateLinkProperty('bandwidth', e.target.value),
                  className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                },
                  bandwidthOptions.map(option =>
                    React.createElement('option', {
                      key: option,
                      value: option
                    }, option)
                  )
                )
              ),

              React.createElement('div', {},
                React.createElement('label', {
                  className: "block text-sm font-medium text-gray-700 mb-1"
                }, "Status"),
                React.createElement('select', {
                  value: selectedLink.status || 'up',
                  onChange: (e) => updateLinkProperty('status', e.target.value),
                  className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                },
                  React.createElement('option', { value: "up" }, "Up (Active)"),
                  React.createElement('option', { value: "down" }, "Down (Inactive)")
                )
              ),

              React.createElement('div', {
                className: "pt-4 border-t border-gray-300"
              },
                React.createElement('button', {
                  onClick: () => deleteLink(selectedLink.index),
                  className: "w-full p-3 bg-red-50 text-red-700 border border-red-300 rounded-lg hover:bg-red-100 transition-colors flex items-center justify-center gap-2"
                },
                  React.createElement(Trash2, { className: "w-4 h-4" }),
                  "Delete Link"
                )
              )
            )
          ) : React.createElement('div', {
            className: "text-center text-gray-500 mt-8"
          },
            React.createElement(Settings, { className: "w-12 h-12 mx-auto mb-3 text-gray-300" }),
            React.createElement('h3', {
              className: "font-semibold mb-2"
            }, "Properties"),
            React.createElement('p', {
              className: "text-sm"
            }, "Select a node or link to edit its properties")
          ),

          // Topology Summary
          React.createElement('div', {
            className: "mt-8 p-4 bg-white rounded-xl border border-gray-200"
          },
            React.createElement('h4', {
              className: "font-semibold text-gray-800 mb-3"
            }, "Topology Summary"),
            React.createElement('div', {
              className: "space-y-2 text-sm"
            },
              React.createElement('div', {
                className: "flex justify-between"
              },
                React.createElement('span', {}, "Hosts:"),
                React.createElement('span', {
                  className: "font-mono"
                }, nodes.filter(n => n.type === 'host').length)
              ),
              React.createElement('div', {
                className: "flex justify-between"
              },
                React.createElement('span', {}, "Switches:"),
                React.createElement('span', {
                  className: "font-mono"
                }, nodes.filter(n => n.type === 'switch').length)
              ),
              React.createElement('div', {
                className: "flex justify-between"
              },
                React.createElement('span', {}, "Routers:"),
                React.createElement('span', {
                  className: "font-mono"
                }, nodes.filter(n => n.type === 'router').length)
              ),
              React.createElement('div', {
                className: "flex justify-between"
              },
                React.createElement('span', {}, "Controllers:"),
                React.createElement('span', {
                  className: "font-mono"
                }, nodes.filter(n => n.type === 'controller').length)
              ),
              React.createElement('div', {
                className: "flex justify-between border-t pt-2"
              },
                React.createElement('span', {}, "Links:"),
                React.createElement('span', {
                  className: "font-mono"
                }, links.length)
              )
            )
          ),

          // Links List
          links.length > 0 && React.createElement('div', {
            className: "mt-4 p-4 bg-white rounded-xl border border-gray-200"
          },
            React.createElement('h4', {
              className: "font-semibold text-gray-800 mb-3"
            }, "Links"),
            React.createElement('div', {
              className: "space-y-2 max-h-60 overflow-y-auto"
            },
              links.map((link, index) =>
                React.createElement('div', {
                  key: index,
                  className: `flex items-center justify-between text-sm p-2 rounded-lg cursor-pointer ${
                    selectedLink?.index === index ? 'bg-indigo-50 border border-indigo-200' : 'hover:bg-gray-50'
                  }`,
                  onClick: () => handleLinkClick(link, index)
                },
                  React.createElement('div', {
                    className: "flex flex-col"
                  },
                    React.createElement('span', {
                      className: "font-mono text-xs"
                    }, `${link.source} ↔ ${link.target}`),
                    React.createElement('div', {
                      className: "flex gap-2 text-xs mt-1"
                    },
                      React.createElement('span', {
                        className: `px-2 py-1 rounded ${
                          link.status === 'down' 
                            ? 'bg-red-100 text-red-800' 
                            : 'bg-green-100 text-green-800'
                        }`
                      }, link.status || 'up'),
                      React.createElement('span', {
                        className: "px-2 py-1 rounded bg-blue-100 text-blue-800"
                      }, link.bandwidth || '100M')
                    )
                  ),
                  React.createElement('button', {
                    onClick: (e) => {
                      e.stopPropagation();
                      deleteLink(index);
                    },
                    className: "text-red-500 hover:text-red-700 transition-colors p-1"
                  },
                    React.createElement(Trash2, { className: "w-4 h-4" })
                  )
                )
              )
            )
          )
        )
      ),
      
      // Footer
      React.createElement('div', {
        className: "px-6 py-4 border-t border-gray-200 flex items-center justify-between bg-gray-50"
      },
        React.createElement('div', {
          className: "flex items-center gap-4 text-sm text-gray-600"
        },
          React.createElement('span', {}, `Nodes: ${nodes.length}`),
          React.createElement('span', {}, `Links: ${links.length}`),
          isLinkMode && React.createElement('span', {
            className: "text-green-600 font-semibold"
          }, "Link Mode Active"),
          React.createElement('button', {
            onClick: () => setShowShortcuts(!showShortcuts),
            className: "text-indigo-600 hover:text-indigo-800 transition-colors flex items-center gap-1"
          },
            React.createElement(Keyboard, { className: "w-3 h-3" }),
            React.createElement('span', {}, "Shortcuts")
          )
        ),
        
        React.createElement('div', {
          className: "flex items-center gap-3"
        },
          React.createElement('button', {
            onClick: onClose,
            className: "px-6 py-2 text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 transition-colors"
          }, "Cancel"),
          React.createElement('button', {
            onClick: () => onSaveTemplate && onSaveTemplate({ 
              name: topologyName, 
              nodes: nodes.map(node => ({
                ...node,
                x: dragPositions[node.id]?.x || node.x,
                y: dragPositions[node.id]?.y || node.y
              })), 
              links 
            }),
            disabled: nodes.length === 0,
            className: "px-6 py-2 text-indigo-700 bg-indigo-100 rounded-lg hover:bg-indigo-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          },
            React.createElement(Save, { className: "w-4 h-4" }),
            "Save Template"
          ),
          React.createElement('button', {
            onClick: createTopology,
            disabled: nodes.length === 0,
            className: "px-6 py-2 text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          },
            React.createElement(CheckCircle, { className: "w-4 h-4" }),
            "Create Topology"
          )
        )
      )
    )
  );
};

export default TopologyBuilder;