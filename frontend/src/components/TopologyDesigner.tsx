import { useCallback, useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import ReactFlow, {
  Node,
  Edge,
  addEdge,
  Background,
  Controls,
  MiniMap,
  Connection,
  useNodesState,
  useEdgesState,
  MarkerType,
  NodeTypes,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { DeviceNode } from './nodes/DeviceNode'
import { DeviceType } from '@/types/topology'
import { Button } from '@/components/atoms/Button'
import { Input } from '@/components/atoms/Input'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/atoms/Card'
import { DevicePropertiesPanel } from './DevicePropertiesPanel'
import { 
  Trash2, 
  Save, 
  RefreshCw, 
  XCircle,
  Monitor,
  Network,
  Router,
  Wifi,
  Smartphone,
  Container,
  Zap,
  Server,
  Plus,
} from 'lucide-react'

// Rename Container to avoid conflict
import { Container as ContainerIcon } from 'lucide-react'

const nodeTypes: NodeTypes = {
  device: DeviceNode,
}

interface TopologyDesignerProps {
  initialNodes?: Node[]
  initialEdges?: Edge[]
  onNodesChange?: (nodes: Node[]) => void
  onEdgesChange?: (edges: Edge[]) => void
  overlayById?: Record<string, any>
}


export default function TopologyDesigner({
  initialNodes = [],
  initialEdges = [],
  onNodesChange,
  onEdgesChange,
  overlayById,
}: TopologyDesignerProps) {
  const { t } = useTranslation()
  const [nodes, setNodes, onNodesChangeInternal] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChangeInternal] = useEdgesState(initialEdges)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null)
  const [isInitialized, setIsInitialized] = useState(false)

  // Sync initialNodes to internal state ONCE when loaded from backend
  useEffect(() => {
    if (!isInitialized && initialNodes && initialNodes.length > 0) {
      setNodes(initialNodes)
      setIsInitialized(true)
    }
  }, [initialNodes, setNodes, isInitialized])

  // Sync initialEdges to internal state ONCE when loaded from backend
  useEffect(() => {
    if (!isInitialized && initialEdges && initialEdges.length > 0) {
      setEdges(initialEdges)
    }
  }, [initialEdges, setEdges, isInitialized])

  // Apply algorithm overlays without resetting layout/edits.
  useEffect(() => {
    if (!overlayById) return
    setNodes((prev) =>
      prev.map((n) => {
        const nextOverlay = overlayById[n.id]
        if (nextOverlay === undefined) return n
        return { ...n, data: { ...n.data, overlay: nextOverlay } }
      })
    )
  }, [overlayById, setNodes])

  const onConnect = useCallback(
    (params: Connection) => {
      const newEdge = {
        ...params,
        type: 'smoothstep',
        animated: true,
        style: {
          stroke: '#10b981',
          strokeWidth: 2,
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: '#10b981',
          width: 20,
          height: 20,
        },
        data: {
          bandwidth: '1Gbps',
          delay: '0ms',
          loss: 0,
        },
      }
      setEdges((eds) => {
        const updatedEdges = addEdge(newEdge, eds)
        // Notify parent of change
        if (onEdgesChange) {
          onEdgesChange(updatedEdges)
        }
        return updatedEdges
      })
    },
    [setEdges, onEdgesChange]
  )

  const addNode = useCallback(
    (deviceType: DeviceType) => {
      const newNode: Node = {
        id: `${deviceType}-${Date.now()}`,
        type: 'device',
        position: {
          x: Math.random() * 400 + 100,
          y: Math.random() * 300 + 100,
        },
        data: {
          label: `${deviceType}-${nodes.length + 1}`,
          deviceType,
          properties: {},
        },
      }
      setNodes((nds) => {
        const updatedNodes = [...nds, newNode]
        // Notify parent of change
        if (onNodesChange) {
          onNodesChange(updatedNodes)
        }
        return updatedNodes
      })
    },
    [nodes, setNodes, onNodesChange]
  )

  const deleteSelectedNode = () => {
    if (selectedNode) {
      setNodes((nds) => {
        const updatedNodes = nds.filter((n) => n.id !== selectedNode.id)
        // Notify parent of change
        if (onNodesChange) {
          onNodesChange(updatedNodes)
        }
        return updatedNodes
      })
      setEdges((eds) => {
        const updatedEdges = eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id)
        // Notify parent of change
        if (onEdgesChange) {
          onEdgesChange(updatedEdges)
        }
        return updatedEdges
      })
      setSelectedNode(null)
    }
  }

  const updateNodeProperty = (key: string, value: any) => {
    if (selectedNode) {
      setNodes((nds) => {
        const updatedNodes = nds.map((n) =>
          n.id === selectedNode.id
            ? {
                ...n,
                data: {
                  ...n.data,
                  [key === 'label' ? 'label' : `properties.${key}`]: value,
                  properties: key !== 'label' ? { ...n.data.properties, [key]: value } : n.data.properties,
                },
              }
            : n
        )
        // Notify parent of change
        if (onNodesChange) {
          onNodesChange(updatedNodes)
        }
        return updatedNodes
      })
      setSelectedNode((prev) => prev ? {
        ...prev,
        data: {
          ...prev.data,
          [key === 'label' ? 'label' : `properties.${key}`]: value,
          properties: key !== 'label' ? { ...prev.data.properties, [key]: value } : prev.data.properties,
        },
      } : null)
    }
  }

  const updateEdgeBandwidth = (bandwidth: string) => {
    if (selectedEdge) {
      setEdges((eds) => {
        const updatedEdges = eds.map((e) =>
          e.id === selectedEdge.id
            ? { ...e, data: { ...e.data, bandwidth } }
            : e
        )
        // Notify parent of change
        if (onEdgesChange) {
          onEdgesChange(updatedEdges)
        }
        return updatedEdges
      })
    }
  }


  const clearAll = () => {
    if (confirm(t('topology.clear') + '?')) {
      setNodes([])
      setEdges([])
      setSelectedNode(null)
      setSelectedEdge(null)
      // Notify parent of change
      if (onNodesChange) {
        onNodesChange([])
      }
      if (onEdgesChange) {
        onEdgesChange([])
      }
    }
  }

  const handleNodesChange = useCallback(
    (changes: any) => {
      onNodesChangeInternal(changes)
    },
    [onNodesChangeInternal]
  )

  const handleEdgesChange = useCallback(
    (changes: any) => {
      onEdgesChangeInternal(changes)
    },
    [onEdgesChangeInternal]
  )

  // Notify parent when nodes/edges change (but not during initial load)
  useEffect(() => {
    if (isInitialized && onNodesChange) {
      onNodesChange(nodes)
    }
  }, [nodes, isInitialized]) // Don't include onNodesChange in deps to avoid loops

  useEffect(() => {
    if (isInitialized && onEdgesChange) {
      onEdgesChange(edges)
    }
  }, [edges, isInitialized]) // Don't include onEdgesChange in deps to avoid loops

  const handleNodeClick = useCallback((_event: any, node: Node) => {
    setSelectedNode(node)
    setSelectedEdge(null)
  }, [])

  const handleEdgeClick = useCallback((_event: any, edge: Edge) => {
    setSelectedEdge(edge)
    setSelectedNode(null)
  }, [])

  const deviceTypes: { type: DeviceType; icon: React.ElementType; color: string; bgGradient: string; category?: string; label: string }[] = [
    { type: 'host', icon: Monitor, color: 'text-blue-600', bgGradient: 'bg-gradient-to-br from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700', category: 'network', label: t('topology.devices.host') },
    { type: 'switch', icon: Network, color: 'text-emerald-600', bgGradient: 'bg-gradient-to-br from-emerald-500 to-emerald-600 hover:from-emerald-600 hover:to-emerald-700', category: 'network', label: t('topology.devices.switch') },
    { type: 'router', icon: Router, color: 'text-purple-600', bgGradient: 'bg-gradient-to-br from-purple-500 to-purple-600 hover:from-purple-600 hover:to-purple-700', category: 'network', label: t('topology.devices.router') },
    { type: 'ap', icon: Wifi, color: 'text-orange-600', bgGradient: 'bg-gradient-to-br from-orange-500 to-orange-600 hover:from-orange-600 hover:to-orange-700', category: 'wireless', label: t('topology.devices.ap') },
    { type: 'station', icon: Smartphone, color: 'text-pink-600', bgGradient: 'bg-gradient-to-br from-pink-500 to-pink-600 hover:from-pink-600 hover:to-pink-700', category: 'wireless', label: t('topology.devices.station') },
    { type: 'p4switch', icon: Zap, color: 'text-amber-600', bgGradient: 'bg-gradient-to-br from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700', category: 'sdn', label: t('topology.devices.p4switch') },
    { type: 'controller', icon: Server, color: 'text-indigo-600', bgGradient: 'bg-gradient-to-br from-indigo-500 to-indigo-600 hover:from-indigo-600 hover:to-indigo-700', category: 'sdn', label: t('topology.devices.controller') },
  ]

  return (
    <div className="h-full flex flex-col">
      {/* Mobile Device Palette - Modern Horizontal Scroll */}
      <div className="lg:hidden bg-gradient-to-r from-gray-50 to-white dark:from-gray-900 dark:to-gray-800 border-b-2 border-gray-200 dark:border-gray-700 p-3 overflow-x-auto shadow-sm">
        <div className="flex gap-2 min-w-max">
          {deviceTypes.map((device) => {
            const Icon = device.icon
            return (
              <button
                key={device.type}
                onClick={() => addNode(device.type)}
                className={`group flex-shrink-0 px-4 py-2.5 rounded-xl ${device.bgGradient} text-white text-xs font-semibold shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-105 flex items-center gap-2 border-2 border-white/20`}
              >
                <Icon className="w-5 h-5 group-hover:scale-110 transition-transform" strokeWidth={2.5} />
                <span className="hidden sm:inline">{device.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      <div className="flex-1 flex flex-col lg:flex-row gap-0 lg:gap-4 lg:p-4 bg-gray-50 dark:bg-gray-950 overflow-hidden">
        {/* Left Sidebar - Desktop Only */}
        <div className="hidden lg:block w-72 space-y-4 overflow-y-auto">
          {/* Device Palette - Modern Design */}
          <Card className="bg-gradient-to-br from-white to-gray-50 dark:from-gray-800 dark:to-gray-900 border-2">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-bold flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
                  <Plus className="w-5 h-5 text-white" strokeWidth={2.5} />
                </div>
                {t('topology.devices.title')}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
            {/* Network Devices */}
            <div>
              <h4 className="text-xs text-gray-600 dark:text-gray-300 uppercase font-bold mb-3 flex items-center gap-2">
                <div className="h-1 w-6 rounded-full bg-gradient-to-r from-blue-500 to-emerald-500"></div>
                {t('topology.categories.network')}
              </h4>
              <div className="grid grid-cols-2 gap-2">
                {deviceTypes.filter(d => d.category === 'network').map((device) => {
                  const Icon = device.icon
                  return (
                    <button
                      key={device.type}
                      onClick={() => addNode(device.type)}
                      className={`group p-3 rounded-xl ${device.bgGradient} transition-all duration-200 text-white flex flex-col items-center gap-2 text-xs font-semibold shadow-lg hover:shadow-xl hover:scale-105 border-2 border-white/20`}
                    >
                      <Icon className="w-7 h-7 group-hover:scale-110 transition-transform" strokeWidth={2.5} />
                      <span className="text-center leading-tight">{device.label}</span>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Wireless & SDN & Compute */}
            {['wireless', 'sdn', 'compute'].map((category) => {
              const categoryDevices = deviceTypes.filter(d => d.category === category)
              if (categoryDevices.length === 0) return null
              const gradients = {
                wireless: 'from-orange-500 to-pink-500',
                sdn: 'from-amber-500 to-indigo-500',
                compute: 'from-cyan-500 to-cyan-500'
              }
              return (
                <div key={category}>
                  <h4 className="text-xs text-gray-600 dark:text-gray-300 uppercase font-bold mb-3 flex items-center gap-2">
                    <div className={`h-1 w-6 rounded-full bg-gradient-to-r ${gradients[category as keyof typeof gradients]}`}></div>
                    {t(`topology.categories.${category}`)}
                  </h4>
                  <div className="grid grid-cols-2 gap-2">
                    {categoryDevices.map((device) => {
                      const Icon = device.icon
                      return (
                        <button
                          key={device.type}
                          onClick={() => addNode(device.type)}
                          className={`group p-3 rounded-xl ${device.bgGradient} transition-all duration-200 text-white flex flex-col items-center gap-2 text-xs font-semibold shadow-lg hover:shadow-xl hover:scale-105 border-2 border-white/20`}
                        >
                          <Icon className="w-7 h-7 group-hover:scale-110 transition-transform" strokeWidth={2.5} />
                          <span className="text-center leading-tight">{device.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>

        {/* Stats */}
        <Card className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800 dark:to-gray-900 border-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg font-bold flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <span className="text-white text-sm">📊</span>
              </div>
              {t('topology.stats.title')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-blue-500 to-blue-600 p-4 shadow-lg">
              <div className="absolute top-0 right-0 w-20 h-20 bg-white/10 rounded-full -mr-10 -mt-10"></div>
              <div className="relative flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-white/20 backdrop-blur-sm flex items-center justify-center">
                    <span className="text-2xl">🔷</span>
                  </div>
                  <span className="text-sm font-semibold text-white/90">{t('topology.stats.nodes')}</span>
                </div>
                <span className="text-3xl font-black text-white drop-shadow-lg">{nodes.length}</span>
              </div>
            </div>
            <div className="relative overflow-hidden rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 p-4 shadow-lg">
              <div className="absolute top-0 right-0 w-20 h-20 bg-white/10 rounded-full -mr-10 -mt-10"></div>
              <div className="relative flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-white/20 backdrop-blur-sm flex items-center justify-center">
                    <span className="text-2xl">🔗</span>
                  </div>
                  <span className="text-sm font-semibold text-white/90">{t('topology.stats.links')}</span>
                </div>
                <span className="text-3xl font-black text-white drop-shadow-lg">{edges.length}</span>
              </div>
            </div>
          </CardContent>
        </Card>
        </div>

        {/* Center - Canvas */}
        <div className="flex-1 bg-white dark:bg-gray-900 lg:rounded-2xl border-t lg:border border-gray-200 dark:border-gray-800 lg:shadow-lg overflow-hidden relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={handleNodesChange}
          onEdgesChange={handleEdgesChange}
          onConnect={onConnect}
          onNodeClick={handleNodeClick}
          onEdgeClick={handleEdgeClick}
          nodeTypes={nodeTypes}
          fitView
          className="bg-gray-50 dark:bg-gray-900"
        >
          <Background 
            color="#d1d5db" 
            className="dark:!bg-gray-900" 
            gap={16} 
          />
          <Controls className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg" />
          <MiniMap
            nodeColor={(node) => {
              const deviceType = node.data.deviceType as DeviceType
              const colorMap: Record<DeviceType, string> = {
                host: '#2563eb',
                switch: '#10b981',
                router: '#9333ea',
                ap: '#ea580c',
                station: '#db2777',
                p4switch: '#f59e0b',
                controller: '#4f46e5',
              }
              return colorMap[deviceType] || '#6366f1'
            }}
            className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg"
          />
        </ReactFlow>
        </div>

        {/* Right Sidebar - Properties - Desktop */}
        {(selectedNode || selectedEdge) && (
          <div className="hidden lg:block w-80 overflow-y-auto">
          {selectedNode && (
            <DevicePropertiesPanel
              node={selectedNode}
              onUpdate={updateNodeProperty}
              onDelete={deleteSelectedNode}
            />
          )}
              
          {selectedEdge && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Link Properties</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                    Bandwidth
                  </label>
                  <select
                    value={selectedEdge.data?.bandwidth || '1Gbps'}
                    onChange={(e) => updateEdgeBandwidth(e.target.value)}
                    className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  >
                    <option value="10Mbps">10 Mbps</option>
                    <option value="100Mbps">100 Mbps</option>
                    <option value="1Gbps">1 Gbps</option>
                    <option value="10Gbps">10 Gbps</option>
                    <option value="100Gbps">100 Gbps</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                    Delay (ms)
                  </label>
                  <input
                    type="number"
                    value={selectedEdge.data?.delay?.replace('ms', '') || ''}
                    onChange={(e) => setEdges((eds) =>
                      eds.map((edge) =>
                        edge.id === selectedEdge.id
                          ? { ...edge, data: { ...edge.data, delay: `${e.target.value}ms` } }
                          : edge
                      )
                    )}
                    className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                    placeholder="0"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                    Packet Loss (%)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={selectedEdge.data?.loss || ''}
                    onChange={(e) => setEdges((eds) =>
                      eds.map((edge) =>
                        edge.id === selectedEdge.id
                          ? { ...edge, data: { ...edge.data, loss: parseFloat(e.target.value) } }
                          : edge
                      )
                    )}
                    className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                    placeholder="0"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                    Jitter (ms)
                  </label>
                  <input
                    type="number"
                    value={selectedEdge.data?.jitter?.replace('ms', '') || ''}
                    onChange={(e) => setEdges((eds) =>
                      eds.map((edge) =>
                        edge.id === selectedEdge.id
                          ? { ...edge, data: { ...edge.data, jitter: `${e.target.value}ms` } }
                          : edge
                      )
                    )}
                    className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                    placeholder="0"
                  />
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400 pt-4 border-t border-gray-200 dark:border-gray-700">
                  <p className="mb-1"><strong>Source:</strong> {selectedEdge.source}</p>
                  <p><strong>Target:</strong> {selectedEdge.target}</p>
                </div>
              </CardContent>
            </Card>
          )}
          </div>
        )}
      </div>

      {/* Mobile Properties Modal */}
      {(selectedNode || selectedEdge) && (
        <div className="lg:hidden fixed inset-x-0 bottom-0 z-50 bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 rounded-t-3xl shadow-2xl max-h-[70vh] overflow-y-auto animate-slide-up">
          <div className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 p-4 flex items-center justify-between">
            <h3 className="font-semibold text-gray-900 dark:text-white">
              {selectedNode ? t('topology.properties') : 'Link Properties'}
            </h3>
            <button
              onClick={() => {
                setSelectedNode(null)
                setSelectedEdge(null)
              }}
              className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800"
            >
              <XCircle className="w-5 h-5" />
            </button>
          </div>
          <div className="p-4">
            {selectedNode && (
              <DevicePropertiesPanel
                node={selectedNode}
                onUpdate={updateNodeProperty}
                onDelete={deleteSelectedNode}
              />
            )}
            {selectedEdge && (
              <Card>
                <CardContent className="space-y-4 pt-6">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Bandwidth
                    </label>
                    <select
                      value={selectedEdge.data?.bandwidth || '1Gbps'}
                      onChange={(e) => updateEdgeBandwidth(e.target.value)}
                      className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                    >
                      <option value="10Mbps">10 Mbps</option>
                      <option value="100Mbps">100 Mbps</option>
                      <option value="1Gbps">1 Gbps</option>
                      <option value="10Gbps">10 Gbps</option>
                      <option value="100Gbps">100 Gbps</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Delay (ms)
                    </label>
                    <input
                      type="number"
                      value={selectedEdge.data?.delay?.replace('ms', '') || ''}
                      onChange={(e) => setEdges((eds) =>
                        eds.map((edge) =>
                          edge.id === selectedEdge.id
                            ? { ...edge, data: { ...edge.data, delay: `${e.target.value}ms` } }
                            : edge
                        )
                      )}
                      className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                      placeholder="0"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Packet Loss (%)
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="100"
                      value={selectedEdge.data?.loss || ''}
                      onChange={(e) => setEdges((eds) =>
                        eds.map((edge) =>
                          edge.id === selectedEdge.id
                            ? { ...edge, data: { ...edge.data, loss: parseFloat(e.target.value) } }
                            : edge
                        )
                      )}
                      className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                      placeholder="0"
                    />
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

    
    </div>
  )
}
