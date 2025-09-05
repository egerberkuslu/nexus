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
  HelpCircle,
  AlertCircle,
  Bookmark,
  FolderOpen,
  FolderPlus,
  Brain,
  Sparkles
} from 'lucide-react';
import LLMTopologyGenerator from './LLMTopologyGenerator';
import Draggable from 'react-draggable';

const TopologyBuilder = ({ 
  isOpen, 
  onClose, 
  onCreateTopology, 
  availableTemplates = [],
  onSaveTemplate,
  // Live mode props
  networkStatus,
  initialTopology,
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
  onAfterApply
}) => {
  const [nodes, setNodes] = useState([]);
  const [links, setLinks] = useState([]);
  const [controllers, setControllers] = useState([]);
  // Track existing items at open to avoid re-applying them
  const initialNodeIdsRef = useRef(new Set());
  const initialLinkPairsRef = useRef(new Set());
  const controllerIdsRef = useRef(new Set());
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

  // New state for saved topologies
  const [savedTopologies, setSavedTopologies] = useState([]);
  const [serverTopologies, setServerTopologies] = useState([]);
  const [showSavedTopologies, setShowSavedTopologies] = useState(false);
  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [saveTopologyName, setSaveTopologyName] = useState('');
  const [saveTopologyDescription, setSaveTopologyDescription] = useState('');
  const [saveToServer, setSaveToServer] = useState(true);
  const [loading, setLoading] = useState(false);
  
  // Update topology state
  const [updateDialogOpen, setUpdateDialogOpen] = useState(false);
  const [topologyToUpdate, setTopologyToUpdate] = useState(null);
  const [updateTopologyName, setUpdateTopologyName] = useState('');
  const [updateTopologyDescription, setUpdateTopologyDescription] = useState('');

  // LLM Generator state
  const [llmGeneratorOpen, setLlmGeneratorOpen] = useState(false);

  const isLive = !!(networkStatus && networkStatus.running);

  // When in live mode, we stage local changes and only apply on demand
  const [pendingSummary, setPendingSummary] = useState({ nodes: 0, links: 0 });
  
  // Track changes that happen after opening the builder
  const [stagedChanges, setStagedChanges] = useState({
    addedNodes: [],
    deletedNodes: [],
    addedLinks: [],
    deletedLinks: [],
    modifiedNodes: [], // Track nodes with property changes
    modifiedLinks: []  // Track links with property changes
  });

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
      defaultConfig: { openflow_version: '1.3', dpid: 'auto', switch_type: 'ovs' }
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
      defaultConfig: { port: 6633, ip: '127.0.0.1', controller_type: 'ryu', app: 'simple_switch_13' }
    }
  };

  const bandwidthOptions = [
    '10M', '100M', '500M', '1G'
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
          { id: 's1', type: 'switch', x: 200, y: 200, switch_type: 'ovs' },
          { id: 's2', type: 'switch', x: 300, y: 200, switch_type: 'ovs' },
          { id: 'h2', type: 'host', x: 400, y: 200, ip: '10.0.0.2' }
        ],
        links: [
          { source: 'h1', target: 's1', bandwidth: '100M' },
          { source: 's1', target: 's2', bandwidth: '1G' },
          { source: 's2', target: 'h2', bandwidth: '100M' }
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
          { id: 's1', type: 'switch', x: 250, y: 200, switch_type: 'ovs' },
          { id: 'h1', type: 'host', x: 150, y: 100, ip: '10.0.0.1' },
          { id: 'h2', type: 'host', x: 350, y: 100, ip: '10.0.0.2' },
          { id: 'h3', type: 'host', x: 150, y: 300, ip: '10.0.0.3' },
          { id: 'h4', type: 'host', x: 350, y: 300, ip: '10.0.0.4' }
        ],
        links: [
          { source: 'h1', target: 's1', bandwidth: '100M' },
          { source: 'h2', target: 's1', bandwidth: '100M' },
          { source: 'h3', target: 's1', bandwidth: '100M' },
          { source: 'h4', target: 's1', bandwidth: '100M' }
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
          { id: 's1', type: 'switch', x: 250, y: 100, switch_type: 'ovs' },
          { id: 's2', type: 'switch', x: 150, y: 200, switch_type: 'ovs' },
          { id: 's3', type: 'switch', x: 350, y: 200, switch_type: 'ovs' },
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
          { id: 's1', type: 'switch', x: 150, y: 150, switch_type: 'ovs' },
          { id: 's2', type: 'switch', x: 350, y: 150, switch_type: 'ovs' },
          { id: 's3', type: 'switch', x: 150, y: 300, switch_type: 'ovs' },
          { id: 's4', type: 'switch', x: 350, y: 300, switch_type: 'ovs' },
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
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    const key = e.key.toLowerCase();

    const mapType = (k) => k === 'h' ? 'host' : k === 's' ? 'switch' : k === 'r' ? 'router' : k === 'c' ? 'controller' : null;
    const type = mapType(key);
    if (type) {
      e.preventDefault();
      addNode(type);
      return;
    }

    switch (key) {
      case 'l':
        e.preventDefault();
        setIsLinkMode(prev => !prev);
        setLinkStart(null);
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

  useEffect(() => {
    if (!isOpen) return;
    // Seed from current topology if provided
    if (initialTopology && Array.isArray(initialTopology.nodes)) {
      // Show current topology when opening (both live and create modes)
      const baseNodes = (initialTopology.nodes || []).map(n => ({ ...n }));

      // Merge controllers into nodes for proper rendering in the editor
      let mergedNodes = baseNodes;
      if (Array.isArray(initialTopology.controllers)) {
        const existingIds = new Set(baseNodes.map(n => n.id));
        const controllerNodes = (initialTopology.controllers || []).map(c => ({
          id: c.id,
          type: 'controller',
          x: c.x,
          y: c.y,
          status: c.status,
          ip: c.ip,
          port: c.port,
          controller_type: c.controller_type,
          app: c.app
        })).filter(c => !existingIds.has(c.id));
        mergedNodes = [...baseNodes, ...controllerNodes];
      }

      setNodes(mergedNodes);
      initialNodeIdsRef.current = new Set(mergedNodes.map(n => n.id));
    } else {
      setNodes([]);
      initialNodeIdsRef.current = new Set();
    }
    if (initialTopology && Array.isArray(initialTopology.links)) {
      const incomingLinks = (initialTopology.links || []).map(l => ({ ...l }));
      setLinks(incomingLinks);
      // Track undirected pairs to avoid duplicates regardless of source/target order
      const normalizedPairs = incomingLinks.map(l => {
        const a = String(l.source); const b = String(l.target);
        return a < b ? `${a}__${b}` : `${b}__${a}`;
      });
      initialLinkPairsRef.current = new Set(normalizedPairs);
    } else {
      setLinks([]);
      initialLinkPairsRef.current = new Set();
    }
    // Capture controllers if present
    if (initialTopology && Array.isArray(initialTopology.controllers)) {
      setControllers((initialTopology.controllers || []).map(c => ({ ...c })));
      controllerIdsRef.current = new Set((initialTopology.controllers || []).map(c => c.id));
    } else {
      setControllers([]);
      controllerIdsRef.current = new Set();
    }
    setDragPositions({});
    setSelectedNode(null);
    setSelectedLink(null);
    setIsLinkMode(false);
    setLinkStart(null);
    
    // Clear staged changes when opening
    setStagedChanges({
      addedNodes: [],
      deletedNodes: [],
      addedLinks: [],
      deletedLinks: [],
      modifiedNodes: [],
      modifiedLinks: []
    });
  }, [isOpen, initialTopology]);

  const addNode = useCallback(async (type, x = 250, y = 200) => {
    const existingNodes = nodes.filter(n => n.type === type);
    const nodeConfig = nodeTypes[type];
    const nodeId = `${nodeConfig.defaultPrefix}${existingNodes.length + 1}`;

    // Calculate position to avoid overlapping
    let newX = x;
    let newY = y;
    
    // Check if position is occupied and find a free spot
    let attempts = 0;
    const maxAttempts = 20;
    while (attempts < maxAttempts) {
      const isOccupied = nodes.some(node => 
        Math.abs(node.x - newX) < 80 && Math.abs(node.y - newY) < 80
      );
      
      if (!isOccupied) break;
      
      // Try different positions in a spiral pattern
      newX = x + (attempts * 20) * Math.cos(attempts * 0.5);
      newY = y + (attempts * 20) * Math.sin(attempts * 0.5);
      attempts++;
    }

    // In live mode, stage locally; do not call backend yet
    const newNode = {
      id: nodeId,
      type,
      x: newX,
      y: newY,
      ...nodeConfig.defaultConfig
    };

    if (type === 'host') {
      newNode.ip = `10.0.0.${existingNodes.length + 1}`;
    }

    setNodes(prev => {
      const next = [...prev, newNode];
      if (isLive) {
        const newPending = { ...pendingSummary, nodes: next.length };
        setPendingSummary(newPending);
        // Track this as an added node
        setStagedChanges(prev => ({
          ...prev,
          addedNodes: [...prev.addedNodes, newNode]
        }));
        console.log(`Node ${nodeId} added, pending summary:`, newPending);
      }
      return next;
    });
  }, [nodes, isLive]);

  const deleteNode = useCallback(async (nodeId) => {
    // In live mode, stage the deletion locally instead of calling backend immediately
    if (isLive) {
      // Stage the deletion by removing from local state
      // The actual backend call will happen when user clicks "Apply Updates"
      setNodes(prev => {
        const next = prev.filter(n => n.id !== nodeId);
        const newPending = { ...pendingSummary, nodes: next.length };
        setPendingSummary(newPending);
        // Track this as a deleted node
        setStagedChanges(prev => ({
          ...prev,
          deletedNodes: [...prev.deletedNodes, nodeId]
        }));
        console.log(`Node ${nodeId} staged for deletion, pending summary:`, newPending);
        return next;
      });
      setLinks(prev => prev.filter(l => l.source !== nodeId && l.target !== nodeId));
      if (selectedNode?.id === nodeId) {
        setSelectedNode(null);
      }
      console.log(`Node ${nodeId} staged for deletion - will be applied when you click 'Apply Updates'`);
    } else {
      // In non-live mode, just update local state
      setNodes(prev => {
        const next = prev.filter(n => n.id !== nodeId);
        return next;
      });
      setLinks(prev => prev.filter(l => l.source !== nodeId && l.target !== nodeId));
      if (selectedNode?.id === nodeId) {
        setSelectedNode(null);
      }
    }
  }, [selectedNode, isLive]);

  const toggleLinkMode = useCallback(() => {
    setIsLinkMode(prev => !prev);
    setLinkStart(null);
  }, []);

  const handleEscape = useCallback(() => {
    setSelectedNode(null);
    setSelectedLink(null);
    setIsLinkMode(false);
    setLinkStart(null);
  }, []);

  const handleNodeClick = useCallback(async (node) => {
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
            bandwidth: node.type === 'host' || linkStart.type === 'host' ? '100M' : '500M',
            status: 'up'
          };
          setLinks(prev => {
            const next = [...prev, newLink];
            if (isLive) {
              const newPending = { ...pendingSummary, links: next.length };
              setPendingSummary(newPending);
              console.log(`Link ${linkStart.id}-${node.id} added, pending summary:`, newPending);
            }
            return next;
          });
        }
        setLinkStart(null);
        setIsLinkMode(false);
      }
    } else {
      setSelectedNode(node);
      setSelectedLink(null);
    }
  }, [isLinkMode, linkStart, links, isLive]);

  const updateNodeProperty = useCallback((property, value) => {
    if (!selectedNode) return;
    
    setNodes(prev => prev.map(n => 
      n.id === selectedNode.id 
        ? { ...n, [property]: value }
        : n
    ));
    setSelectedNode(prev => ({ ...prev, [property]: value }));
    
    // Track property changes for live mode
    if (isLive) {
      setStagedChanges(prev => {
        const existingMod = prev.modifiedNodes.find(n => n.id === selectedNode.id);
        if (existingMod) {
          // Update existing modification
          return {
            ...prev,
            modifiedNodes: prev.modifiedNodes.map(n => 
              n.id === selectedNode.id 
                ? { ...n, [property]: value }
                : n
            )
          };
        } else {
          // Add new modification
          return {
            ...prev,
            modifiedNodes: [...prev.modifiedNodes, { 
              id: selectedNode.id, 
              [property]: value,
              originalValue: selectedNode[property]
            }]
          };
        }
      });
      console.log(`Node ${selectedNode.id} property ${property} changed to ${value}`);
    }
  }, [selectedNode, isLive]);

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
    
    // Track property changes for live mode
    if (isLive) {
      const link = links[selectedLink.index];
      setStagedChanges(prev => {
        const existingMod = prev.modifiedLinks.find(l => 
          l.source === link.source && l.target === link.target
        );
        if (existingMod) {
          // Update existing modification
          return {
            ...prev,
            modifiedLinks: prev.modifiedLinks.map(l => 
              (l.source === link.source && l.target === link.target)
                ? { ...l, [property]: value }
                : l
            )
          };
        } else {
          // Add new modification
          return {
            ...prev,
            modifiedLinks: [...prev.modifiedLinks, { 
              source: link.source,
              target: link.target,
              [property]: value,
              originalValue: link[property]
            }]
          };
        }
      });
      console.log(`🔄 Link ${link.source}-${link.target} property ${property} changed to ${value}`);
      console.log(`   Full link object:`, link);
      console.log(`   Staged changes updated:`, stagedChanges);
    }
  }, [selectedLink, links, isLive, stagedChanges]);

  const deleteLink = useCallback(async (linkIndex) => {
    const link = links[linkIndex];
    if (!link) return;
    
    // In live mode, stage the deletion locally instead of calling backend immediately
    if (isLive) {
      // Stage the deletion by removing from local state
      // The actual backend call will happen when user clicks "Apply Updates"
        setLinks(prev => {
          const next = prev.filter((_, index) => index !== linkIndex);
          const newPending = { ...pendingSummary, links: next.length };
          setPendingSummary(newPending);
          console.log(`Link ${link.source}-${link.target} staged for deletion, pending summary:`, newPending);
          return next;
        });
        if (selectedLink && selectedLink.index === linkIndex) {
          setSelectedLink(null);
        }
        console.log(`Link ${link.source}-${link.target} staged for deletion - will be applied when you click 'Apply Updates'`);
    } else {
      // In non-live mode, just update local state
      setLinks(prev => {
        const next = prev.filter((_, index) => index !== linkIndex);
        return next;
      });
      if (selectedLink && selectedLink.index === linkIndex) {
        setSelectedLink(null);
      }
    }
  }, [selectedLink, isLive, links]);

  const handleDelete = useCallback(() => {
    if (selectedNode) {
      deleteNode(selectedNode.id);
    } else if (selectedLink !== null) {
      deleteLink(selectedLink.index);
    }
  }, [selectedNode, selectedLink, deleteNode, deleteLink]);

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
    let topology;
    
    if (isLive && initialTopology) {
      // In live mode, use the current network topology data
      topology = {
        name: topologyName,
        nodes: initialTopology.nodes || [],
        links: initialTopology.links || [],
        controllers: controllers,
        metadata: {
          created: new Date().toISOString(),
          version: '1.0',
          exported_from_live_network: true
        }
      };
    } else {
      // In builder mode, use the current builder state
      topology = {
        name: topologyName,
        nodes: nodes.map(node => ({
          ...node,
          x: dragPositions[node.id]?.x || node.x,
          y: dragPositions[node.id]?.y || node.y
        })),
        links,
        metadata: {
          created: new Date().toISOString(),
          version: '1.0',
          exported_from_builder: true
        }
      };
    }

    const blob = new Blob([JSON.stringify(topology, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${topologyName.replace(/\s+/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [topologyName, nodes, links, dragPositions, isLive, initialTopology]);

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

  // Save topology to server or localStorage
  const saveTopology = useCallback(async () => {
    setLoading(true);
    const name = saveTopologyName || topologyName;
    
    let topologyData;
    
    if (isLive && initialTopology) {
      // In live mode, use the current network topology data
      topologyData = {
        name,
        description: saveTopologyDescription,
        nodes: initialTopology.nodes || [],
        links: initialTopology.links || [],
        controllers: controllers
      };
      
      if (topologyData.nodes.length === 0 && topologyData.links.length === 0) {
        alert('Cannot save empty topology');
        setLoading(false);
        return;
      }
    } else {
      // In builder mode, use the current builder state
      if (nodes.length === 0) {
        alert('Cannot save empty topology');
        setLoading(false);
        return;
      }
      
      topologyData = {
        name,
        description: saveTopologyDescription,
        nodes: nodes.map(node => ({
          ...node,
          x: dragPositions[node.id]?.x || node.x,
          y: dragPositions[node.id]?.y || node.y
        })),
        links,
        controllers: controllers.map(c => ({
          id: c.id,
          ip: c.ip || '127.0.0.1',
          port: c.port || 6633
        }))
      };
    }

    try {
      if (saveToServer) {
        // First, test if the API endpoint exists
        try {
          const testResponse = await fetch('http://localhost:5000/api/test');
          console.log('API test response:', testResponse.status);
        } catch (error) {
          console.error('API test failed:', error);
        }

        // Save to server via API
        console.log('Attempting to save topology to server:', {
          name,
          description: saveTopologyDescription,
          nodeCount: topologyData.nodes.length,
          linkCount: topologyData.links.length
        });

        const response = await fetch('http://localhost:5000/api/storage/topologies', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            name,
            description: saveTopologyDescription,
            topology_data: topologyData,
            topology_type: 'custom',
            metadata: {
              nodeCount: topologyData.nodes.length,
              linkCount: topologyData.links.length,
              controllerCount: topologyData.controllers?.length || topologyData.nodes.filter(n => n.type === 'controller').length,
              created_from_builder: !isLive,
              created_from_live_network: isLive
            }
          }),
        });

        console.log('Server response status:', response.status);
        console.log('Server response headers:', response.headers);

        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
          const textResponse = await response.text();
          console.error('Server returned non-JSON response:', textResponse);
          throw new Error(`Server error: ${response.status} - ${textResponse.substring(0, 200)}...`);
        }

        const result = await response.json();
        console.log('Server response:', result);
        
        if (result.success) {
          alert(`Topology "${name}" saved to server successfully!`);
          loadServerTopologies(); // Refresh server topologies
        } else {
          throw new Error(result.error || 'Failed to save to server');
        }
      } else {
        // Save to localStorage
        const localTopology = {
          id: Date.now().toString(),
          ...topologyData,
          metadata: {
            created: new Date().toISOString(),
            version: '1.0',
            nodeCount: topologyData.nodes.length,
            linkCount: topologyData.links.length,
            controllerCount: topologyData.controllers?.length || topologyData.nodes.filter(n => n.type === 'controller').length,
            source: 'local',
            created_from_builder: !isLive,
            created_from_live_network: isLive
          }
        };

        const existing = JSON.parse(localStorage.getItem('savedTopologies') || '[]');
        const updated = [...existing, localTopology];
        localStorage.setItem('savedTopologies', JSON.stringify(updated));
        setSavedTopologies(updated);
        alert(`Topology "${name}" saved locally successfully!`);
      }
      
      setSaveDialogOpen(false);
      setSaveTopologyName('');
      setSaveTopologyDescription('');
    } catch (error) {
      console.error('Error saving topology:', error);
      
      if (saveToServer) {
        // If server save failed, offer to save locally instead
        const fallbackToLocal = window.confirm(
          `Server save failed: ${error.message}\n\nWould you like to save locally instead?`
        );
        
        if (fallbackToLocal) {
          try {
            const localTopology = {
              id: Date.now().toString(),
              ...topologyData,
              metadata: {
                created: new Date().toISOString(),
                version: '1.0',
                nodeCount: topologyData.nodes.length,
                linkCount: topologyData.links.length,
                controllerCount: topologyData.controllers?.length || topologyData.nodes.filter(n => n.type === 'controller').length,
                source: 'local',
                created_from_builder: !isLive,
                created_from_live_network: isLive,
                fallback_from_server: true
              }
            };

            const existing = JSON.parse(localStorage.getItem('savedTopologies') || '[]');
            const updated = [...existing, localTopology];
            localStorage.setItem('savedTopologies', JSON.stringify(updated));
            setSavedTopologies(updated);
            alert(`Topology "${name}" saved locally as fallback!`);
            
            setSaveDialogOpen(false);
            setSaveTopologyName('');
            setSaveTopologyDescription('');
          } catch (localError) {
            alert('Both server and local save failed: ' + localError.message);
          }
        }
      } else {
        alert('Error saving topology: ' + error.message);
      }
    } finally {
      setLoading(false);
    }
  }, [nodes, links, dragPositions, topologyName, saveTopologyName, saveTopologyDescription, saveToServer, isLive, initialTopology]);

  // Load saved topologies from localStorage
  const loadSavedTopologies = useCallback(() => {
    try {
      const saved = JSON.parse(localStorage.getItem('savedTopologies') || '[]');
      setSavedTopologies(saved);
    } catch (error) {
      console.error('Error loading saved topologies:', error);
      setSavedTopologies([]);
    }
  }, []);

  // Load server topologies via API
  const loadServerTopologies = useCallback(async () => {
    try {
      console.log('Loading server topologies...');
      const response = await fetch('http://localhost:5000/api/storage/topologies');
      console.log('Load topologies response status:', response.status);
      
      // Check if response is JSON
      const contentType = response.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        const textResponse = await response.text();
        console.error('Server returned non-JSON response when loading topologies:', textResponse);
        setServerTopologies([]);
        return;
      }

      const result = await response.json();
      console.log('Load topologies result:', result);
      console.log('Server topologies structure:', result.topologies);
      
      if (result.success) {
        setServerTopologies(result.topologies || []);
      } else {
        console.error('Error loading server topologies:', result.error);
        setServerTopologies([]);
      }
    } catch (error) {
      console.error('Error loading server topologies:', error);
      setServerTopologies([]);
    }
  }, []);

  // Load a specific saved topology
  const loadSavedTopology = useCallback(async (topology) => {
    try {
      let topologyData;
      
      if (topology.source === 'server') {
        // Load from server
        const topologyId = topology.id || topology._id;
        if (!topologyId) {
          throw new Error('No topology ID found');
        }
        const response = await fetch(`http://localhost:5000/api/storage/topologies/${topologyId}`);
        const result = await response.json();
        
        if (result.success) {
          topologyData = result.topology.topology_data;
        } else {
          throw new Error(result.error || 'Failed to load topology from server');
        }
      } else {
        // Load from local storage
        topologyData = topology;
      }
      
      setNodes(topologyData.nodes || []);
      setLinks(topologyData.links || []);
      setTopologyName(topologyData.name);
      setDragPositions({});
      setSelectedNode(null);
      setSelectedLink(null);
      setShowSavedTopologies(false);
      alert(`Topology "${topologyData.name}" loaded successfully!`);
    } catch (error) {
      console.error('Error loading topology:', error);
      alert('Error loading topology: ' + error.message);
    }
  }, []);

  // Delete a saved topology
  const deleteSavedTopology = useCallback(async (topology) => {
    if (window.confirm('Are you sure you want to delete this saved topology? This action cannot be undone.')) {
      try {
        if (topology.source === 'server') {
          // Delete from server
          const topologyId = topology.id || topology._id;
          if (!topologyId) {
            throw new Error('No topology ID found');
          }
          const response = await fetch(`http://localhost:5000/api/storage/topologies/${topologyId}`, {
            method: 'DELETE',
          });
          const result = await response.json();
          
          if (result.success) {
            alert('Topology deleted successfully!');
            loadServerTopologies(); // Refresh server topologies
          } else {
            throw new Error(result.error || 'Failed to delete topology from server');
          }
        } else {
          // Delete from localStorage
          const existing = JSON.parse(localStorage.getItem('savedTopologies') || '[]');
          const updated = existing.filter(t => t.id !== topology.id);
          localStorage.setItem('savedTopologies', JSON.stringify(updated));
          setSavedTopologies(updated);
          alert('Topology deleted successfully!');
        }
      } catch (error) {
        console.error('Error deleting topology:', error);
        alert('Error deleting topology: ' + error.message);
      }
    }
  }, [loadServerTopologies]);

  // Update a saved topology
  const updateSavedTopology = useCallback(async () => {
    if (!topologyToUpdate) return;
    
    setLoading(true);
    
    // Prepare topology data - use current builder state if available, otherwise keep existing data
    let topologyData;
    
    if (isLive && initialTopology) {
      // In live mode, use the current network topology data
      topologyData = {
        name: updateTopologyName,
        description: updateTopologyDescription,
        nodes: initialTopology.nodes || [],
        links: initialTopology.links || [],
        controllers: controllers
      };
    } else if (nodes.length > 0 || links.length > 0) {
      // In builder mode with current topology, use the current builder state
      topologyData = {
        name: updateTopologyName,
        description: updateTopologyDescription,
        nodes: nodes.map(node => ({
          ...node,
          x: dragPositions[node.id]?.x || node.x,
          y: dragPositions[node.id]?.y || node.y
        })),
        links,
        controllers: controllers.map(c => ({
          id: c.id,
          ip: c.ip || '127.0.0.1',
          port: c.port || 6633
        }))
      };
    } else {
      // No current topology data, just update name and description
      topologyData = null;
    }
    
    try {
      if (topologyToUpdate.source === 'server') {
        // Update server topology
        const topologyId = topologyToUpdate.id || topologyToUpdate._id;
        if (!topologyId) {
          throw new Error('No topology ID found');
        }
        
        const updatePayload = {
          name: updateTopologyName,
          description: updateTopologyDescription,
        };
        
        // Include topology data if we have current topology in builder
        if (topologyData) {
          updatePayload.topology_data = topologyData;
          updatePayload.metadata = {
            nodeCount: topologyData.nodes.length,
            linkCount: topologyData.links.length,
            controllerCount: topologyData.controllers?.length || topologyData.nodes.filter(n => n.type === 'controller').length,
            updated_from_builder: !isLive,
            updated_from_live_network: isLive,
            last_updated: new Date().toISOString()
          };
        }
        
        const response = await fetch(`http://localhost:5000/api/storage/topologies/${topologyId}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(updatePayload),
        });

        const result = await response.json();
        
        if (result.success) {
          const updateType = topologyData ? 'topology and metadata' : 'name and description';
          alert(`Topology "${updateTopologyName}" ${updateType} updated successfully!`);
          loadServerTopologies(); // Refresh server topologies
        } else {
          throw new Error(result.error || 'Failed to update topology on server');
        }
      } else {
        // Update local topology
        const existing = JSON.parse(localStorage.getItem('savedTopologies') || '[]');
        const updated = existing.map(t => {
          if (t.id === topologyToUpdate.id) {
            const updatedTopology = { 
              ...t, 
              name: updateTopologyName, 
              description: updateTopologyDescription,
              metadata: {
                ...t.metadata,
                updated: new Date().toISOString()
              }
            };
            
            // Include current topology data if available
            if (topologyData) {
              updatedTopology.nodes = topologyData.nodes;
              updatedTopology.links = topologyData.links;
              updatedTopology.controllers = topologyData.controllers;
              updatedTopology.metadata = {
                ...updatedTopology.metadata,
                nodeCount: topologyData.nodes.length,
                linkCount: topologyData.links.length,
                controllerCount: topologyData.controllers?.length || topologyData.nodes.filter(n => n.type === 'controller').length,
                updated_from_builder: !isLive,
                updated_from_live_network: isLive
              };
            }
            
            return updatedTopology;
          }
          return t;
        });
        localStorage.setItem('savedTopologies', JSON.stringify(updated));
        setSavedTopologies(updated);
        const updateType = topologyData ? 'topology and metadata' : 'name and description';
        alert(`Topology "${updateTopologyName}" ${updateType} updated successfully!`);
      }
      
      setUpdateDialogOpen(false);
      setTopologyToUpdate(null);
      setUpdateTopologyName('');
      setUpdateTopologyDescription('');
    } catch (error) {
      console.error('Error updating topology:', error);
      alert('Error updating topology: ' + error.message);
    } finally {
      setLoading(false);
    }
  }, [topologyToUpdate, updateTopologyName, updateTopologyDescription, loadServerTopologies, isLive, initialTopology, nodes, links, dragPositions]);

  // Open update dialog
  const openUpdateDialog = useCallback((topology) => {
    setTopologyToUpdate(topology);
    setUpdateTopologyName(topology.name);
    setUpdateTopologyDescription(topology.description || '');
    setUpdateDialogOpen(true);
  }, []);

  // Load generated topology from LLM
  const loadGeneratedTopology = useCallback((topologyConfig) => {
    if (topologyConfig && topologyConfig.topology) {
      const { nodes, links } = topologyConfig.topology;
      
      // Convert the generated topology to our format
      const convertedNodes = nodes.map(node => ({
        ...node,
        // Ensure all required fields are present
        x: node.x || 250,
        y: node.y || 200,
        status: node.status || 'active'
      }));
      
      const convertedLinks = links.map(link => ({
        ...link,
        status: link.status || 'up',
        bandwidth: link.bandwidth || '100M'
      }));
      
      setNodes(convertedNodes);
      setLinks(convertedLinks);
      setTopologyName(`AI Generated - ${new Date().toLocaleTimeString()}`);
      setDragPositions({});
      setSelectedNode(null);
      setSelectedLink(null);
      
      // Clear any staged changes
      setStagedChanges({
        addedNodes: [],
        deletedNodes: [],
        addedLinks: [],
        deletedLinks: [],
        modifiedNodes: [],
        modifiedLinks: []
      });
      
      console.log('Loaded AI-generated topology:', { nodes: convertedNodes.length, links: convertedLinks.length });
    }
  }, []);

  // Export saved topology
  const exportSavedTopology = useCallback((topology) => {
    const topologyData = {
      name: topology.name,
      description: topology.description,
      nodes: topology.nodes,
      links: topology.links,
      metadata: topology.metadata
    };

    const blob = new Blob([JSON.stringify(topologyData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${topology.name.replace(/\s+/g, '_')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  // Duplicate a saved topology
  const duplicateSavedTopology = useCallback((topology) => {
    const duplicatedTopology = {
      ...topology,
      id: Date.now().toString(),
      name: `${topology.name} (Copy)`,
      metadata: {
        ...topology.metadata,
        created: new Date().toISOString(),
        duplicated: true
      }
    };

    try {
      const existing = JSON.parse(localStorage.getItem('savedTopologies') || '[]');
      const updated = [...existing, duplicatedTopology];
      localStorage.setItem('savedTopologies', JSON.stringify(updated));
      setSavedTopologies(updated);
      alert(`Topology "${duplicatedTopology.name}" duplicated successfully!`);
    } catch (error) {
      alert('Error duplicating topology: ' + error.message);
    }
  }, []);

  // Load saved topologies on component mount
  useEffect(() => {
    if (isOpen) {
      loadSavedTopologies();
      loadServerTopologies();
    }
  }, [isOpen, loadSavedTopologies, loadServerTopologies]);

  const createTopology = useCallback(() => {
    if (isLive) return; // prevent creating snapshot when live
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
  }, [nodes, links, dragPositions, topologyName, onCreateTopology, onClose, isLive]);

  const applyUpdates = useCallback(async () => {
    if (!isLive) return;
    
    // Get initial state for comparison
    const initialIds = initialNodeIdsRef.current;
    const initialPairs = initialLinkPairsRef.current;
    
    console.log('=== Applying Updates ===');
    console.log('Initial node IDs:', Array.from(initialIds));
    console.log('Initial link pairs:', Array.from(initialPairs));
    console.log('Current nodes:', nodes.map(n => n.id));
    console.log('Current links:', links.map(l => `${l.source}-${l.target}`));
    
    // Calculate what was deleted
    const deletedNodes = Array.from(initialIds).filter(id => !nodes.some(n => n.id === id));
    const deletedLinks = Array.from(initialPairs).filter(pair => {
      const [source, target] = pair.split('__');
      return !links.some(l => 
        (l.source === source && l.target === target) || 
        (l.source === target && l.target === source)
      );
    });

    // Calculate what was added
    const addedNodes = nodes.filter(n => !initialIds.has(n.id));
    const addedLinks = links.filter(l => !initialPairs.has(`${l.source}__${l.target}`));

    // Calculate controller changes
    const currentControllerIds = new Set(controllers.map(c => c.id));
    const initialControllerIds = controllerIdsRef.current;
    const addedControllers = controllers.filter(c => !initialControllerIds.has(c.id));
    const deletedControllers = Array.from(initialControllerIds).filter(id => !currentControllerIds.has(id));

    // Get property changes from staged changes
    const modifiedNodes = stagedChanges.modifiedNodes;
    const modifiedLinks = stagedChanges.modifiedLinks;

    console.log('Deleted nodes:', deletedNodes);
    console.log('Deleted links:', deletedLinks);
    console.log('Added nodes:', addedNodes.map(n => n.id));
    console.log('Added links:', addedLinks.map(l => `${l.source}-${l.target}`));
    console.log('Added controllers:', addedControllers.map(c => c.id));
    console.log('Deleted controllers:', deletedControllers);
    console.log('Modified nodes:', modifiedNodes);
    console.log('Modified links:', modifiedLinks);

    let successCount = 0;
    let errorCount = 0;

    try {
      // First, apply deletions
      if (onRemoveNode && deletedNodes.length > 0) {
        console.log(`Applying ${deletedNodes.length} node deletions:`, deletedNodes);
        for (const nodeId of deletedNodes) {
          try {
            await onRemoveNode(nodeId);
            successCount++;
            console.log(`Successfully deleted node ${nodeId}`);
          } catch (error) {
            console.error(`Failed to delete node ${nodeId}:`, error);
            errorCount++;
            // Continue with other deletions even if one fails
          }
        }
      }
      
      if (onRemoveLink && deletedLinks.length > 0) {
        console.log(`Applying ${deletedLinks.length} link deletions:`, deletedLinks);
        for (const pair of deletedLinks) {
          const [source, target] = pair.split('__');
          try {
            await onRemoveLink(source, target);
            successCount++;
            console.log(`Successfully deleted link ${source}-${target}`);
          } catch (error) {
            console.error(`Failed to delete link ${source}-${target}:`, error);
            errorCount++;
            // Continue with other deletions even if one fails
          }
        }
      }

      // Then, apply additions
      if (onAddNode && addedNodes.length > 0) {
        console.log(`Applying ${addedNodes.length} node additions:`, addedNodes.map(n => n.id));
        for (const node of addedNodes) {
          try {
            await onAddNode({ id: node.id, type: node.type, x: node.x, y: node.y, ip: node.ip }, { refresh: false });
            successCount++;
            console.log(`Successfully added node ${node.id}`);
          } catch (error) {
            console.error(`Failed to add node ${node.id}:`, error);
            errorCount++;
            // Continue with other nodes even if one fails
          }
        }
      }
      
      if (onAddLink && addedLinks.length > 0) {
        console.log(`Applying ${addedLinks.length} link additions:`, addedLinks.map(l => `${l.source}-${l.target}`));
        for (const link of addedLinks) {
          try {
            await onAddLink({ source: link.source, target: link.target, bandwidth: link.bandwidth }, { refresh: false });
            successCount++;
            console.log(`Successfully added link ${link.source}-${link.target}`);
          } catch (error) {
            console.error(`Failed to add link ${link.source}-${link.target}:`, error);
            errorCount++;
            // Continue with other links even if one fails
          }
        }
      }
      
      // Apply property changes
      if (modifiedNodes.length > 0) {
        console.log(`Applying ${modifiedNodes.length} node property changes:`, modifiedNodes);
        for (const nodeMod of modifiedNodes) {
          try {
            // Use the appropriate update function based on the property
            if (nodeMod.ip && nodeMod.ip !== nodeMod.originalValue) {
              try {
                if (onUpdateNodeIP) {
                  await onUpdateNodeIP(nodeMod.id, nodeMod.ip);
                  successCount++;
                  console.log(`Successfully updated IP for node ${nodeMod.id} to ${nodeMod.ip}`);
                } else {
                  errorCount++;
                  console.error(`IP update function not available`);
                }
              } catch (error) {
                errorCount++;
                console.error(`Failed to update IP for node ${nodeMod.id}:`, error);
              }
            }
            // Add more property updates here as needed
          } catch (error) {
            console.error(`Failed to update properties for node ${nodeMod.id}:`, error);
            errorCount++;
          }
        }
      }
      
      if (modifiedLinks.length > 0) {
        console.log(`Applying ${modifiedLinks.length} link property changes:`, modifiedLinks);
        for (const linkMod of modifiedLinks) {
          try {
            // Use the appropriate update function based on the property
            if (linkMod.bandwidth && linkMod.bandwidth !== linkMod.originalValue) {
              try {
                if (onUpdateLinkBandwidth) {
                  console.log(`🔄 Updating bandwidth for link ${linkMod.source}-${linkMod.target}: ${linkMod.originalValue} -> ${linkMod.bandwidth}`);
                  console.log(`   Link object:`, linkMod);
                  
                  await onUpdateLinkBandwidth(linkMod.source, linkMod.target, linkMod.bandwidth);
                  successCount++;
                  console.log(`✅ Successfully updated bandwidth for link ${linkMod.source}-${linkMod.target} to ${linkMod.bandwidth}`);
                } else {
                  errorCount++;
                  console.error(`❌ Bandwidth update function not available`);
                }
              } catch (error) {
                errorCount++;
                console.error(`❌ Failed to update bandwidth for link ${linkMod.source}-${linkMod.target}:`, error);
              }
            }
            if (linkMod.status && linkMod.status !== linkMod.originalValue) {
              try {
                if (onUpdateLinkStatus) {
                  await onUpdateLinkStatus(linkMod.source, linkMod.target, linkMod.status);
                  successCount++;
                  console.log(`Successfully updated status for link ${linkMod.source}-${linkMod.target} to ${linkMod.status}`);
                } else {
                  errorCount++;
                  console.error(`Status update function not available`);
                }
              } catch (error) {
                errorCount++;
                console.error(`Failed to update status for link ${linkMod.source}-${linkMod.target}:`, error);
              }
            }
          } catch (error) {
            console.error(`Failed to update properties for link ${linkMod.source}-${linkMod.target}:`, error);
            errorCount++;
          }
        }
      }
      
      // Show results to user
      const totalOperations = deletedNodes.length + deletedLinks.length + addedNodes.length + addedLinks.length + modifiedNodes.length + modifiedLinks.length;
      
      if (totalOperations === 0) {
        alert('No changes to apply. The topology is already up to date.');
        return;
      }
      
      if (errorCount > 0) {
        alert(`Updates completed with ${successCount} successes and ${errorCount} errors out of ${totalOperations} total operations. Check console for details.`);
      } else if (successCount > 0) {
        alert(`Successfully applied ${successCount} updates out of ${totalOperations} total operations!`);
      }
      
      // Force refresh topology data from Mininet to ensure all changes are reflected
      if (typeof onRefreshTopology === 'function') {
        try {
          await onRefreshTopology();
          console.log('Topology data refreshed from Mininet');
        } catch (error) {
          console.warning('Failed to refresh topology data:', error);
        }
      }
      
      // Fetch final topology once after batch
      if (typeof onAfterApply === 'function') {
        await onAfterApply();
      }
      // Clear staging
      setNodes([]);
      setLinks([]);
      setPendingSummary({ nodes: 0, links: 0 });
      setStagedChanges({
        addedNodes: [],
        deletedNodes: [],
        addedLinks: [],
        deletedLinks: [],
        modifiedNodes: [],
        modifiedLinks: []
      });
      onClose();
    } catch (error) {
      console.error('Error applying updates:', error);
      alert(`Error applying updates: ${error.message || error}`);
      // Don't close on error, let user see what happened
    }
  }, [isLive, nodes, links, onAddNode, onAddLink, onRemoveNode, onRemoveLink, onUpdateNodeIP, onUpdateLinkBandwidth, onUpdateLinkStatus, onUpdateControllerPort, onRefreshTopology, onClose]);

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
            isLive ? "Live Topology Editor" : "Topology Builder"
          ),
          !isLive && React.createElement('input', {
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
      
      // Mininet Limitations Warning
      isLive && React.createElement('div', {
        className: "px-6 py-3 bg-amber-50 border-b border-amber-200"
      },
        React.createElement('div', {
          className: "flex items-center gap-2 text-amber-800"
        },
          React.createElement(AlertCircle, { className: "w-4 h-4" }),
          React.createElement('span', {
            className: "text-sm font-medium"
          }, "Mininet Limitations:"),
          React.createElement('span', {
            className: "text-xs"
          }, "Bandwidth is capped at 1000 Mbps (1 Gbps). Higher values will be automatically reduced.")
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
            }, isLive ? "Add Nodes (Live)" : "Add Nodes"),
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
                onClick: () => setLlmGeneratorOpen(true),
                className: "w-full p-3 rounded-xl border-2 border-purple-300 bg-purple-50 text-purple-700 hover:border-purple-400 transition-all duration-200 flex items-center gap-2"
              },
                React.createElement(Brain, { className: "w-5 h-5" }),
                "AI Generate",
                React.createElement(Sparkles, { className: "w-4 h-4 ml-auto" })
              ),
              
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
              
              !isLive && React.createElement('button', {
                onClick: () => setShowGrid(!showGrid),
                className: "w-full p-3 rounded-xl border-2 border-gray-300 bg-white text-gray-700 hover:border-gray-400 transition-all duration-200 flex items-center gap-2"
              },
                React.createElement(showGrid ? Eye : EyeOff, { className: "w-5 h-5" }),
                showGrid ? 'Hide Grid' : 'Show Grid',
                React.createElement('kbd', {
                  className: "ml-auto px-2 py-1 bg-gray-200 text-gray-600 text-xs rounded"
                }, "G")
              ),
              
              !isLive && React.createElement('button', {
                onClick: clearTopology,
                className: "w-full p-3 rounded-xl border-2 border-red-300 bg-red-50 text-red-700 hover:border-red-400 transition-all duration-200 flex items-center gap-2"
              },
                React.createElement(RotateCcw, { className: "w-5 h-5" }),
                "Clear All"
              )
            )
          ),

          // File Operations (moved up for better visibility)
          React.createElement('div', {
            className: "mb-6"
          },
            React.createElement('h3', {
              className: "text-lg font-semibold text-gray-800 mb-3"
            }, "File Operations"),
            React.createElement('div', {
              className: "space-y-2"
            },
              React.createElement('button', {
                onClick: () => setSaveDialogOpen(true),
                disabled: isLive ? (!initialTopology || (initialTopology.nodes?.length === 0 && initialTopology.links?.length === 0)) : nodes.length === 0,
                className: "w-full p-3 rounded-xl border-2 border-purple-300 bg-purple-50 text-purple-700 hover:border-purple-400 transition-all duration-200 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
              },
                React.createElement(Bookmark, { className: "w-5 h-5" }),
                isLive ? "Save Live Topology" : "Save Topology"
              ),
              
              React.createElement('button', {
                onClick: exportTopology,
                disabled: isLive ? (!initialTopology || (initialTopology.nodes?.length === 0 && initialTopology.links?.length === 0)) : nodes.length === 0,
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
          ),

          // Saved Topologies Section
          React.createElement('div', {
            className: "mb-6"
          },
            React.createElement('h3', {
              className: "text-lg font-semibold text-gray-800 mb-3 flex items-center justify-between"
            },
              "Saved Topologies",
              React.createElement('button', {
                onClick: () => setShowSavedTopologies(!showSavedTopologies),
                className: "p-1 text-gray-500 hover:text-gray-700 transition-colors",
                title: "Toggle Saved Topologies"
              },
                React.createElement(showSavedTopologies ? EyeOff : Eye, { className: "w-4 h-4" })
              )
            ),
            
            showSavedTopologies && React.createElement('div', {
              className: "space-y-3"
            },
              // Server Topologies Section
              React.createElement('div', {},
                React.createElement('h4', {
                  className: "text-sm font-medium text-gray-700 mb-2 flex items-center gap-2"
                },
                  React.createElement(Server, { className: "w-4 h-4 text-blue-500" }),
                  "Server Topologies"
                ),
                serverTopologies.length === 0 ? React.createElement('div', {
                  className: "text-center text-gray-500 py-2"
                },
                  React.createElement('p', {
                    className: "text-xs"
                  }, "No server topologies")
                ) : React.createElement('div', {
                  className: "space-y-2 max-h-40 overflow-y-auto"
                },
                  serverTopologies.map(topology => {
                    const topologyWithSource = { ...topology, source: 'server' };
                    return React.createElement('div', {
                      key: topology.id || topology._id,
                      className: "bg-blue-50 rounded-lg p-2 border border-blue-200"
                    },
                      React.createElement('div', {
                        className: "flex items-center justify-between mb-1"
                      },
                        React.createElement('h5', {
                          className: "font-medium text-gray-800 text-xs truncate"
                        }, topology.name),
                        React.createElement('div', {
                          className: "flex gap-1"
                        },
                          React.createElement('button', {
                            onClick: () => loadSavedTopology(topologyWithSource),
                            className: "p-1 text-blue-600 hover:text-blue-800 transition-colors",
                            title: "Load Topology"
                          },
                            React.createElement(FolderOpen, { className: "w-3 h-3" })
                          ),
                          React.createElement('button', {
                            onClick: () => openUpdateDialog(topologyWithSource),
                            className: "p-1 text-orange-600 hover:text-orange-800 transition-colors",
                            title: "Edit Topology"
                          },
                            React.createElement(Settings, { className: "w-3 h-3" })
                          ),
                          React.createElement('button', {
                            onClick: () => exportSavedTopology(topologyWithSource),
                            className: "p-1 text-indigo-600 hover:text-indigo-800 transition-colors",
                            title: "Export Topology"
                          },
                            React.createElement(Download, { className: "w-3 h-3" })
                          ),
                          React.createElement('button', {
                            onClick: () => deleteSavedTopology(topologyWithSource),
                            className: "p-1 text-red-600 hover:text-red-800 transition-colors",
                            title: "Delete Topology"
                          },
                            React.createElement(Trash2, { className: "w-3 h-3" })
                          )
                        )
                      ),
                      topology.description && React.createElement('p', {
                        className: "text-xs text-gray-600 mb-1"
                      }, topology.description),
                      React.createElement('div', {
                        className: "flex justify-between text-xs text-gray-500"
                      },
                        React.createElement('span', {}, `${topology.metadata?.nodeCount || 0} nodes`),
                        React.createElement('span', {}, `${topology.metadata?.linkCount || 0} links`),
                        React.createElement('span', {}, new Date(topology.created_at).toLocaleDateString())
                      )
                    );
                  })
                )
              ),

              // Local Topologies Section
              React.createElement('div', {},
                React.createElement('h4', {
                  className: "text-sm font-medium text-gray-700 mb-2 flex items-center gap-2"
                },
                  React.createElement(FolderPlus, { className: "w-4 h-4 text-green-500" }),
                  "Local Topologies"
                ),
                savedTopologies.length === 0 ? React.createElement('div', {
                  className: "text-center text-gray-500 py-2"
                },
                  React.createElement('p', {
                    className: "text-xs"
                  }, "No local topologies")
                ) : React.createElement('div', {
                  className: "space-y-2 max-h-40 overflow-y-auto"
                },
                  savedTopologies.map(topology => {
                    const topologyWithSource = { ...topology, source: 'local' };
                    return React.createElement('div', {
                      key: topology.id,
                      className: "bg-green-50 rounded-lg p-2 border border-green-200"
                    },
                      React.createElement('div', {
                        className: "flex items-center justify-between mb-1"
                      },
                        React.createElement('h5', {
                          className: "font-medium text-gray-800 text-xs truncate"
                        }, topology.name),
                        React.createElement('div', {
                          className: "flex gap-1"
                        },
                          React.createElement('button', {
                            onClick: () => loadSavedTopology(topologyWithSource),
                            className: "p-1 text-blue-600 hover:text-blue-800 transition-colors",
                            title: "Load Topology"
                          },
                            React.createElement(FolderOpen, { className: "w-3 h-3" })
                          ),
                          React.createElement('button', {
                            onClick: () => openUpdateDialog(topologyWithSource),
                            className: "p-1 text-orange-600 hover:text-orange-800 transition-colors",
                            title: "Edit Topology"
                          },
                            React.createElement(Settings, { className: "w-3 h-3" })
                          ),
                          React.createElement('button', {
                            onClick: () => duplicateSavedTopology(topology),
                            className: "p-1 text-green-600 hover:text-green-800 transition-colors",
                            title: "Duplicate Topology"
                          },
                            React.createElement(Copy, { className: "w-3 h-3" })
                          ),
                          React.createElement('button', {
                            onClick: () => exportSavedTopology(topology),
                            className: "p-1 text-indigo-600 hover:text-indigo-800 transition-colors",
                            title: "Export Topology"
                          },
                            React.createElement(Download, { className: "w-3 h-3" })
                          ),
                          React.createElement('button', {
                            onClick: () => deleteSavedTopology(topologyWithSource),
                            className: "p-1 text-red-600 hover:text-red-800 transition-colors",
                            title: "Delete Topology"
                          },
                            React.createElement(Trash2, { className: "w-3 h-3" })
                          )
                        )
                      ),
                      topology.description && React.createElement('p', {
                        className: "text-xs text-gray-600 mb-1"
                      }, topology.description),
                      React.createElement('div', {
                        className: "flex justify-between text-xs text-gray-500"
                      },
                        React.createElement('span', {}, `${topology.metadata?.nodeCount || 0} nodes`),
                        React.createElement('span', {}, `${topology.metadata?.linkCount || 0} links`),
                        React.createElement('span', {}, new Date(topology.metadata?.created).toLocaleDateString())
                      )
                    );
                  })
                )
              ),

              (savedTopologies.length === 0 && serverTopologies.length === 0) && React.createElement('div', {
                className: "text-center text-gray-500 py-4"
              },
                React.createElement(Bookmark, { className: "w-8 h-8 mx-auto mb-2 text-gray-300" }),
                React.createElement('p', {
                  className: "text-sm"
                }, "No saved topologies yet")
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

              selectedNode.type === 'switch' && React.createElement('div', {},
                React.createElement('label', {
                  className: "block text-sm font-medium text-gray-700 mb-1"
                }, "Switch Type"),
                React.createElement('select', {
                  value: selectedNode.switch_type || 'ovs',
                  onChange: (e) => updateNodeProperty('switch_type', e.target.value),
                  className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                },
                  React.createElement('option', { value: "ovs" }, "Open vSwitch"),
                  React.createElement('option', { value: "linux_bridge" }, "Linux Bridge"),
                  React.createElement('option', { value: "p4" }, "P4 Switch")
                )
              ),

              selectedNode.type === 'controller' && React.createElement(React.Fragment, {},
                React.createElement('div', {},
                  React.createElement('label', {
                    className: "block text-sm font-medium text-gray-700 mb-1"
                  }, "Controller Type"),
                  React.createElement('select', {
                    value: selectedNode.controller_type || 'ryu',
                    onChange: (e) => updateNodeProperty('controller_type', e.target.value),
                    className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
                  },
                    React.createElement('option', { value: "ryu" }, "Ryu"),
                    React.createElement('option', { value: "pox" }, "POX"),
                    React.createElement('option', { value: "osken" }, "OsKen"),
                    React.createElement('option', { value: "opendaylight" }, "OpenDaylight")
                  )
                ),
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
                ),
                React.createElement('p', {
                  className: "text-xs text-amber-600 mt-1"
                }, "Note: Mininet supports up to 1000 Mbps (1 Gbps). Higher values will be capped.")
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
          }, isLive ? "Cancel" : "Close"),
          isLive && React.createElement('button', {
            onClick: () => { setNodes([]); setLinks([]); setPendingSummary({ nodes: 0, links: 0 }); },
            disabled: (nodes.length === 0 && links.length === 0),
            className: "px-6 py-2 text-red-700 bg-red-100 rounded-lg hover:bg-red-200 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          }, "Clear Staged"),
          isLive && React.createElement('button', {
            onClick: async () => {
              if (typeof onRefreshTopology === 'function') {
                try {
                  await onRefreshTopology();
                  console.log('Manual topology refresh completed');
                } catch (error) {
                  console.error('Manual topology refresh failed:', error);
                }
              }
            },
            className: "px-6 py-2 text-blue-700 bg-blue-100 rounded-lg hover:bg-blue-200 transition-colors"
          }, "🔄 Refresh"),
          isLive && React.createElement('button', {
            onClick: applyUpdates,
            disabled: (nodes.length === 0 && links.length === 0),
            className: "px-6 py-2 text-white bg-emerald-600 rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          },
            React.createElement(CheckCircle, { className: "w-4 h-4" }),
            `Apply Updates (${nodes.length} nodes, ${links.length} links)`
          ),
          !isLive && React.createElement('button', {
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
          !isLive && React.createElement('button', {
            onClick: createTopology,
            disabled: nodes.length === 0,
            className: "px-6 py-2 text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          },
            React.createElement(CheckCircle, { className: "w-4 h-4" }),
            "Create Topology"
          )
        )
      )
    ),

    // Save Topology Dialog
    saveDialogOpen && React.createElement('div', {
      className: "fixed inset-0 bg-black bg-opacity-50 z-[60] flex items-center justify-center p-4"
    },
      React.createElement('div', {
        className: "bg-white rounded-2xl shadow-2xl w-full max-w-md p-6"
      },
        React.createElement('div', {
          className: "flex items-center gap-3 mb-4"
        },
          React.createElement(Bookmark, { className: "w-6 h-6 text-purple-500" }),
          React.createElement('h3', {
            className: "text-xl font-bold text-gray-800"
          }, isLive ? "Save Live Topology" : "Save Topology")
        ),
        
        React.createElement('div', {
          className: "space-y-4"
        },
          React.createElement('div', {},
            React.createElement('label', {
              className: "block text-sm font-medium text-gray-700 mb-1"
            }, "Topology Name"),
            React.createElement('input', {
              type: "text",
              value: saveTopologyName || topologyName,
              onChange: (e) => setSaveTopologyName(e.target.value),
              className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500",
              placeholder: "Enter topology name"
            })
          ),
          
          React.createElement('div', {},
            React.createElement('label', {
              className: "block text-sm font-medium text-gray-700 mb-1"
            }, "Description (Optional)"),
            React.createElement('textarea', {
              value: saveTopologyDescription,
              onChange: (e) => setSaveTopologyDescription(e.target.value),
              className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 resize-none",
              rows: "3",
              placeholder: "Describe your topology..."
            })
          ),

          React.createElement('div', {},
            React.createElement('label', {
              className: "block text-sm font-medium text-gray-700 mb-2"
            }, "Save Location"),
            React.createElement('div', {
              className: "flex gap-4"
            },
              React.createElement('label', {
                className: "flex items-center gap-2 cursor-pointer"
              },
                React.createElement('input', {
                  type: "radio",
                  name: "saveLocation",
                  checked: saveToServer,
                  onChange: () => setSaveToServer(true),
                  className: "text-purple-600 focus:ring-purple-500"
                }),
                React.createElement(Server, { className: "w-4 h-4 text-blue-500" }),
                React.createElement('span', {
                  className: "text-sm text-gray-700"
                }, "Server (Persistent)")
              ),
              React.createElement('label', {
                className: "flex items-center gap-2 cursor-pointer"
              },
                React.createElement('input', {
                  type: "radio",
                  name: "saveLocation",
                  checked: !saveToServer,
                  onChange: () => setSaveToServer(false),
                  className: "text-purple-600 focus:ring-purple-500"
                }),
                React.createElement(FolderPlus, { className: "w-4 h-4 text-green-500" }),
                React.createElement('span', {
                  className: "text-sm text-gray-700"
                }, "Local (Browser)")
              )
            ),
            React.createElement('p', {
              className: "text-xs text-gray-500 mt-1"
            }, saveToServer 
              ? "Saved to server database - accessible from any device"
              : "Saved to browser storage - only available on this device"
            )
          ),
          
          React.createElement('div', {
            className: "bg-gray-50 p-3 rounded-lg"
          },
            React.createElement('div', {
              className: "text-sm text-gray-600"
            },
              React.createElement('div', {
                className: "flex justify-between mb-1"
              },
                React.createElement('span', {}, "Nodes:"),
                React.createElement('span', {
                  className: "font-mono font-medium"
                }, isLive ? (initialTopology?.nodes?.length || 0) : nodes.length)
              ),
              React.createElement('div', {
                className: "flex justify-between"
              },
                React.createElement('span', {}, "Links:"),
                React.createElement('span', {
                  className: "font-mono font-medium"
                }, isLive ? (initialTopology?.links?.length || 0) : links.length)
              )
            )
          )
        ),
        
        React.createElement('div', {
          className: "flex gap-3 mt-6"
        },
          React.createElement('button', {
            onClick: () => setSaveDialogOpen(false),
            className: "flex-1 px-4 py-2 text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 transition-colors"
          }, "Cancel"),
          React.createElement('button', {
            onClick: saveTopology,
            disabled: (!saveTopologyName && !topologyName) || loading,
            className: "flex-1 px-4 py-2 text-white bg-purple-600 rounded-lg hover:bg-purple-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 justify-center"
          },
            loading 
              ? React.createElement('div', {
                  className: "w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"
                })
              : React.createElement(Bookmark, { className: "w-4 h-4" }),
            loading ? "Saving..." : "Save Topology"
          )
        )
      )
    ),

    // Update Topology Dialog
    updateDialogOpen && React.createElement('div', {
      className: "fixed inset-0 bg-black bg-opacity-50 z-[60] flex items-center justify-center p-4"
    },
      React.createElement('div', {
        className: "bg-white rounded-2xl shadow-2xl w-full max-w-md p-6"
      },
        React.createElement('div', {
          className: "flex items-center gap-3 mb-4"
        },
          React.createElement(Settings, { className: "w-6 h-6 text-orange-500" }),
          React.createElement('h3', {
            className: "text-xl font-bold text-gray-800"
          }, "Edit Topology")
        ),
        
        React.createElement('div', {
          className: "space-y-4"
        },
          React.createElement('div', {},
            React.createElement('label', {
              className: "block text-sm font-medium text-gray-700 mb-1"
            }, "Topology Name"),
            React.createElement('input', {
              type: "text",
              value: updateTopologyName,
              onChange: (e) => setUpdateTopologyName(e.target.value),
              className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500",
              placeholder: "Enter topology name"
            })
          ),
          
          React.createElement('div', {},
            React.createElement('label', {
              className: "block text-sm font-medium text-gray-700 mb-1"
            }, "Description (Optional)"),
            React.createElement('textarea', {
              value: updateTopologyDescription,
              onChange: (e) => setUpdateTopologyDescription(e.target.value),
              className: "w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-orange-500 resize-none",
              rows: "3",
              placeholder: "Describe your topology..."
            })
          ),
          
          React.createElement('div', {
            className: "bg-gray-50 p-3 rounded-lg"
          },
            React.createElement('div', {
              className: "text-sm text-gray-600"
            },
              React.createElement('div', {
                className: "flex justify-between mb-1"
              },
                React.createElement('span', {}, "Storage:"),
                React.createElement('span', {
                  className: "font-medium"
                }, topologyToUpdate?.source === 'server' ? 'Server' : 'Local')
              ),
              React.createElement('div', {
                className: "flex justify-between mb-1"
              },
                React.createElement('span', {}, "Original Name:"),
                React.createElement('span', {
                  className: "font-mono text-xs"
                }, topologyToUpdate?.name || '')
              ),
              React.createElement('div', {
                className: "flex justify-between"
              },
                React.createElement('span', {}, "Update Mode:"),
                React.createElement('span', {
                  className: "font-medium text-xs"
                }, (isLive && initialTopology) || (nodes.length > 0 || links.length > 0) 
                  ? 'Full Topology' 
                  : 'Name & Description Only'
                )
              )
            )
          ),
          
          // Show current topology info if available
          ((isLive && initialTopology) || (nodes.length > 0 || links.length > 0)) && React.createElement('div', {
            className: "bg-blue-50 p-3 rounded-lg border border-blue-200"
          },
            React.createElement('h4', {
              className: "font-semibold text-blue-800 mb-2 text-sm"
            }, "Current Topology Will Be Saved:"),
            React.createElement('div', {
              className: "text-sm text-blue-700"
            },
              React.createElement('div', {
                className: "flex justify-between mb-1"
              },
                React.createElement('span', {}, "Nodes:"),
                React.createElement('span', {
                  className: "font-mono font-medium"
                }, isLive ? (initialTopology?.nodes?.length || 0) : nodes.length)
              ),
              React.createElement('div', {
                className: "flex justify-between"
              },
                React.createElement('span', {}, "Links:"),
                React.createElement('span', {
                  className: "font-mono font-medium"
                }, isLive ? (initialTopology?.links?.length || 0) : links.length)
              )
            )
          )
        ),
        
        React.createElement('div', {
          className: "flex gap-3 mt-6"
        },
          React.createElement('button', {
            onClick: () => {
              setUpdateDialogOpen(false);
              setTopologyToUpdate(null);
              setUpdateTopologyName('');
              setUpdateTopologyDescription('');
            },
            className: "flex-1 px-4 py-2 text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300 transition-colors"
          }, "Cancel"),
          React.createElement('button', {
            onClick: updateSavedTopology,
            disabled: !updateTopologyName || loading,
            className: "flex-1 px-4 py-2 text-white bg-orange-600 rounded-lg hover:bg-orange-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 justify-center"
          },
            loading 
              ? React.createElement('div', {
                  className: "w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"
                })
              : React.createElement(Settings, { className: "w-4 h-4" }),
            loading ? "Updating..." : "Update Topology"
          )
        )
      )
    ),

    // LLM Topology Generator
    React.createElement(LLMTopologyGenerator, {
      isOpen: llmGeneratorOpen,
      onClose: () => setLlmGeneratorOpen(false),
      onGenerateTopology: () => {}, // Not used in this context
      onLoadGeneratedTopology: loadGeneratedTopology
    })
  );
};

export default TopologyBuilder;