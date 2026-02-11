import { useState, useEffect, useRef, ReactNode } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Node, Edge } from 'reactflow'
import toast from 'react-hot-toast'
import TopologyDesigner from '@components/TopologyDesigner'
import WebShell from '@components/WebShell'
import P4Editor, { DEFAULT_P4_CODE } from '@components/P4Editor'
import ControllerConfig from '@components/ControllerConfig'
import { topologiesAPI, emulationAPI, infrastructureAPI, topologyP4API, p4API, algorithmsAPI, type P4ProgramDraft } from '@services/api'
import { 
  PlayIcon, 
  StopIcon, 
  CommandLineIcon, 
  CogIcon, 
  ChartBarIcon,
  ArrowLeftIcon,
  WifiIcon as WifiIconSolid,
} from '@heroicons/react/24/solid'
import { 
  ExclamationTriangleIcon,
  CheckBadgeIcon,
  ArrowPathIcon as RefreshIcon,
} from '@heroicons/react/24/outline'
import { Button } from '@/components/atoms/Button'
import { Badge } from '@/components/atoms/Badge'
import { cn } from '@/utils/cn'

type SyncStatus = 'synced' | 'syncing' | 'out-of-sync' | 'error'

export default function TopologyEditor() {
  const { t } = useTranslation()
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showWebShell, setShowWebShell] = useState(false)
  const [selectedDevice, setSelectedDevice] = useState<string>('')
  const [showControllerConfig, setShowControllerConfig] = useState(false)
  const [showStopModal, setShowStopModal] = useState(false)
  const [stopAlsoInfra, setStopAlsoInfra] = useState(false)
  const [deleteInfraData, setDeleteInfraData] = useState(false)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [activeTab, setActiveTab] = useState<'designer' | 'p4'>('designer')
  const [currentNodes, setCurrentNodes] = useState<Node[]>([])
  const [currentEdges, setCurrentEdges] = useState<Edge[]>([])
  const [emulationId, setEmulationId] = useState<string | null>(null)
  const [syncStatus, setSyncStatus] = useState<SyncStatus>('synced')
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'connecting' | 'disconnected'>('connecting')
  const ws = useRef<WebSocket | null>(null)

  const [p4DraftId, setP4DraftId] = useState<string | null>(null)
  const [p4DraftName, setP4DraftName] = useState<string>('Untitled')
  const [p4DraftTarget, setP4DraftTarget] = useState<string>('bmv2')
  const [p4DraftArchitecture, setP4DraftArchitecture] = useState<string>('v1model')
  const [p4DraftCode, setP4DraftCode] = useState<string>(DEFAULT_P4_CODE)
  const [p4LastCompiledProgramId, setP4LastCompiledProgramId] = useState<string | null>(null)
  const [algoOverlayById, setAlgoOverlayById] = useState<Record<string, any>>({})

  // Fetch topology
  const { data: topology, isLoading } = useQuery({
    queryKey: ['topology', id],
    queryFn: async () => {
      const response = await topologiesAPI.get(id!)
      return response.data
    },
    enabled: !!id,
  })

  // Fetch active emulations to get emulation_id for this topology
  const { data: activeEmulations } = useQuery({
    queryKey: ['active-emulations'],
    queryFn: async () => {
      try {
        const response = await emulationAPI.active()
        return response.data
      } catch (error) {
        return { emulations: [] }
      }
    },
    refetchInterval: 5000,
    retry: false,
  })

  // Extract emulation_id for current topology
  useEffect(() => {
    if (activeEmulations?.emulations) {
      const currentEmulation = activeEmulations.emulations.find(
        (e: any) => e.topology_id === id && String(e?.status || '').toLowerCase() === 'running'
      )
      setEmulationId(currentEmulation?.emulation_id || null)
    }
  }, [activeEmulations, id])

  // Fetch emulation status
  const { data: emulationStatus } = useQuery({
    queryKey: ['emulation-status', emulationId],
    queryFn: async () => {
      if (!emulationId) return null
      try {
        const response = await emulationAPI.status(emulationId)
        return response.data
      } catch (error) {
        // If emulation status fails (no emulation running), return null
        return null
      }
    },
    enabled: !!emulationId,
    refetchInterval: 5000,
    retry: false, // Don't retry on error
  })

  // Poll algorithm overlay (best-effort; empty when no runs exist).
  const { data: algoOverlayData } = useQuery({
    queryKey: ['algorithm-overlay', id],
    queryFn: async () => {
      if (!id) return { overlays: {} as Record<string, any> }
      const res = await algorithmsAPI.overlay(id)
      return res.data
    },
    enabled: !!id,
    refetchInterval: 1500,
    retry: false,
  })

  useEffect(() => {
    const overlays = algoOverlayData?.overlays && typeof algoOverlayData.overlays === 'object' ? algoOverlayData.overlays : {}
    setAlgoOverlayById(overlays)
  }, [algoOverlayData])

  const { data: shellInfo } = useQuery({
    queryKey: ['emulation-shell', emulationId],
    queryFn: async () => {
      if (!emulationId || syncStatus !== 'synced') return null
      try {
        const response = await emulationAPI.shellInfo(emulationId)
        return response.data
      } catch (error) {
        return null
      }
    },
    enabled: !!emulationId && syncStatus === 'synced',
    refetchInterval: 15000,
    retry: false,
  })

  const shellDevices = shellInfo?.devices || []
  const containerName = shellInfo?.container_name as string | undefined

  const {
    data: p4Drafts,
    isLoading: p4DraftsLoading,
    refetch: refetchP4Drafts,
  } = useQuery<P4ProgramDraft[]>({
    queryKey: ['topology-p4-drafts', id],
    queryFn: async () => {
      const response = await topologyP4API.listDrafts(id!)
      return response.data
    },
    enabled: !!id && activeTab === 'p4',
    retry: false,
  })

  useEffect(() => {
    if (activeTab !== 'p4') return
    if (!p4Drafts || !p4Drafts.length) {
      if (!p4DraftCode) setP4DraftCode(DEFAULT_P4_CODE)
      return
    }
    const selected = p4DraftId
      ? p4Drafts.find((draft) => draft.draft_id === p4DraftId)
      : p4Drafts[0]
    if (!selected) return
    setP4DraftId(selected.draft_id)
    setP4DraftName(selected.name)
    setP4DraftTarget(selected.target || 'bmv2')
    setP4DraftArchitecture(selected.architecture || 'v1model')
    setP4DraftCode(selected.source_code || '')
    setP4LastCompiledProgramId(selected.compiled_program_id || null)
  }, [activeTab, p4Drafts, p4DraftId])

  useEffect(() => {
    if (!shellDevices.length) {
      setSelectedDevice('')
      return
    }
    setSelectedDevice((current) => {
      if (current) return current
      const first = shellDevices[0]
      return first?.runtime_name || first?.name || first?.id || ''
    })
  }, [shellDevices])

  // WebSocket connection for live updates
  useEffect(() => {
    if (!id) return

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/ws/topology/${id}`

    setConnectionStatus('connecting')
    
    ws.current = new WebSocket(wsUrl)

    ws.current.onopen = () => {
      console.log('WebSocket connected')
      setConnectionStatus('connected')
      toast.success('Live updates connected!', {
        icon: <WifiIconSolid className="w-5 h-5 text-green-500" />,
      })
    }

    ws.current.onmessage = (event) => {
      const message = JSON.parse(event.data)
      console.log('WebSocket message received:', message)

      switch (message.type) {
        case 'topology.updated':
          toast.success('Full topology synced!')
          queryClient.invalidateQueries({ queryKey: ['topology', id] })
          setSyncStatus('synced')
          break
        case 'topology.node.updated':
          toast.success(`Device ${message.payload?.name ?? ''} updated.`)
          queryClient.invalidateQueries({ queryKey: ['topology', id] })
          setSyncStatus('synced')
          break
        case 'topology.link.updated':
          toast.success(
            `Link updated: ${message.payload?.source ?? '?'} → ${message.payload?.target ?? '?'}`
          )
          queryClient.invalidateQueries({ queryKey: ['topology', id] })
          setSyncStatus('synced')
          break
        default:
          break
      }
    }

    ws.current.onclose = () => {
      console.log('WebSocket disconnected')
      setConnectionStatus('disconnected')
      toast.error('Live updates disconnected.', {
        icon: <ExclamationTriangleIcon className="w-5 h-5 text-red-500" />,
      })
    }

    ws.current.onerror = () => {
      setConnectionStatus('disconnected')
    }

    return () => {
      ws.current?.close()
    }
  }, [id, queryClient])

  // Start emulation mutation
  const startMutation = useMutation({
    mutationFn: () => emulationAPI.start(id!),
    onSuccess: (response) => {
      const ok = response.data?.success !== false
      const message = response.data?.message

      if (!ok) {
        toast.error(message || 'Failed to start emulation.')
        return
      }

      if (response.data?.emulation_id) {
        setEmulationId(response.data.emulation_id)
      }
      queryClient.invalidateQueries({ queryKey: ['active-emulations'] })
      queryClient.invalidateQueries({ queryKey: ['emulation-status'] })
      toast.success(message || 'Emulation started successfully!')
    },
    onError: async (err: any) => {
      // If the client timed out / navigation aborted, the backend might still have started it.
      try {
        const active = await emulationAPI.active()
        const current = active.data?.emulations?.find((e: any) => e.topology_id === id)
        if (current?.emulation_id && String(current?.status || '').toLowerCase() === 'running') {
          setEmulationId(current.emulation_id)
          queryClient.invalidateQueries({ queryKey: ['active-emulations'] })
          queryClient.invalidateQueries({ queryKey: ['emulation-status'] })
          toast.success('Emulation started (request was interrupted).')
          return
        }
      } catch {
        // ignore
      }

      toast.error(err?.response?.data?.detail || err?.message || 'Failed to start emulation.')
    }
  })

  // Stop emulation mutation
  const stopMutation = useMutation({
    mutationFn: async (opts?: { cleanup?: boolean; stop_infra?: boolean; preserve_infra_data?: boolean }) => {
      let emulationIdToStop = emulationId
      if (!emulationIdToStop && id) {
        try {
          const active = await emulationAPI.active()
          const current = active.data?.emulations?.find((e: any) => e.topology_id === id)
          if (current?.emulation_id) {
            emulationIdToStop = current.emulation_id
            setEmulationId(current.emulation_id)
          }
        } catch {
          // ignore
        }
      }

      if (!emulationIdToStop) {
        throw new Error('No emulation running')
      }
      return emulationAPI.stop(emulationIdToStop, opts)
    },
    onSuccess: async () => {
      setEmulationId(null)
      queryClient.invalidateQueries({ queryKey: ['active-emulations'] })
      queryClient.invalidateQueries({ queryKey: ['emulation-status'] })
      toast.success('Emulation stopped.')

      if (deleteInfraData && id) {
        const toastId = toast.loading('Deleting isolated infrastructure data…')
        try {
          await infrastructureAPI.purgeTopologyInfra(id)
          toast.success('Infrastructure data deleted', { id: toastId })
        } catch (err: any) {
          toast.error(err?.response?.data?.detail || err?.message || 'Failed to delete infrastructure data', { id: toastId })
        }
      }
    },
    onError: async (err: any) => {
      // If stop failed but the emulation is already gone, treat it as stopped.
      try {
        const active = await emulationAPI.active()
        const current = active.data?.emulations?.find((e: any) => e.topology_id === id)
        if (!current || !current.emulation_id) {
          setEmulationId(null)
          queryClient.invalidateQueries({ queryKey: ['active-emulations'] })
          queryClient.invalidateQueries({ queryKey: ['emulation-status'] })
          toast.success('Emulation stopped.')
          return
        }
      } catch {
        // ignore
      }

      toast.error(err?.response?.data?.detail || err?.message || 'Failed to stop emulation.')
    }
  })

  // Manual sync mutation
  const syncMutation = useMutation({
    mutationFn: () => {
      if (!id) {
        throw new Error('Topology ID is not available')
      }
      setSyncStatus('syncing')
      return emulationAPI.sync(id)
    },
    onSuccess: (data) => {
      const { devices_updated, links_updated, devices_failed, links_failed } = data.data.sync_results
      toast.success(
        `Sync complete: ${devices_updated} devices, ${links_updated} links updated.`,
        {
          icon: <CheckBadgeIcon className="w-5 h-5 text-green-500" />,
        }
      )
      if (devices_failed > 0 || links_failed > 0) {
        toast.error(
          `Sync failed for: ${devices_failed} devices, ${links_failed} links.`,
          {
            icon: <ExclamationTriangleIcon className="w-5 h-5 text-red-500" />,
          }
        )
        setSyncStatus('error')
      } else {
        setSyncStatus('synced')
      }
      queryClient.invalidateQueries({ queryKey: ['topology', id] })
    },
    onError: () => {
      toast.error('Manual sync failed.')
      setSyncStatus('error')
    },
  })

  // Helper to format bandwidth for display
  const formatBandwidth = (bw: number | string): string => {
    if (typeof bw === 'string') return bw
    if (bw >= 1000) return `${bw / 1000}Gbps`
    return `${bw}Mbps`
  }

  // Helper to format delay for display
  const formatDelay = (delay: number | string): string => {
    if (typeof delay === 'string') return delay
    return `${delay}ms`
  }

  // Convert topology data to React Flow nodes/edges
  const convertTopologyToReactFlow = (topologyData: any) => {
    const baseNodes: Node[] = (topologyData?.nodes || []).map((node: any) => ({
      id: node.id,
      type: 'device',
      position: node.position || { x: node.x || 0, y: node.y || 0 },
      data: {
        label: node.name,
        deviceType: node.device_type,
        properties: node.properties || {},
      },
    }))

    const controllers = Array.isArray(topologyData?.controllers) ? topologyData.controllers : []
    const minY = baseNodes.length ? Math.min(...baseNodes.map((n) => n.position.y)) : 0
    const avgX = baseNodes.length
      ? baseNodes.reduce((sum, n) => sum + n.position.x, 0) / baseNodes.length
      : 0
    const controllerYOffset = 180
    const controllerSpacing = 220
    const controllerStartX = avgX - ((controllers.length - 1) * controllerSpacing) / 2

    const controllerNodes: Node[] = controllers
      .filter((c: any) => c && typeof c === 'object' && c.id)
      .map((c: any, idx: number) => ({
        id: c.id,
        type: 'device',
        position: {
          x: controllerStartX + idx * controllerSpacing,
          y: minY - controllerYOffset,
        },
        data: {
          label: c.name || `controller-${idx + 1}`,
          deviceType: 'controller',
          controllerType: c.controller_type,
          ip: c.ip,
          port: c.port,
          properties: {
            ...(c.properties || {}),
            controller_type: c.controller_type,
            ip: c.ip,
            port: c.port,
          },
        },
      }))

    const nodes: Node[] = [...baseNodes, ...controllerNodes]

    const edges: Edge[] = (topologyData?.links || []).map((link: any) => ({
      id: link.id,
      source: link.source || link.source_node_id,
      target: link.target || link.target_node_id,
      type: 'smoothstep',
      animated: true,
      style: {
        stroke: '#10b981',
        strokeWidth: 2,
      },
      markerEnd: {
        type: 'arrowclosed',
        color: '#10b981',
        width: 20,
        height: 20,
      },
      data: {
        bandwidth: formatBandwidth(link.bandwidth || 1000),
        delay: formatDelay(link.delay || 0),
        loss: link.loss || 0,
      },
    }))

    return { nodes, edges }
  }

  // Load topology data when fetched
  useEffect(() => {
    if (topology) {
      const { nodes, edges } = convertTopologyToReactFlow(topology)
      setCurrentNodes(nodes)
      setCurrentEdges(edges)
    }
  }, [topology])

  // Helper function to parse bandwidth string to Mbps number
  const parseBandwidth = (bw: string): number => {
    const match = bw.match(/^(\d+(?:\.\d+)?)(Mbps|Gbps|mbps|gbps)?$/i)
    if (!match) return 1000 // default 1000 Mbps
    const value = parseFloat(match[1])
    const unit = (match[2] || 'mbps').toLowerCase()
    return unit === 'gbps' ? value * 1000 : value
  }

  // Helper function to parse delay string to ms number
  const parseDelay = (delay: string): number => {
    const match = delay.match(/^(\d+(?:\.\d+)?)(ms)?$/i)
    return match ? parseFloat(match[1]) : 0
  }

  // Save topology mutation
  const saveMutation = useMutation({
    mutationFn: (data: { nodes: Node[]; edges: Edge[] }) => {
      setSyncStatus('out-of-sync')
      const updatedTopology = {
        ...topology,
        nodes: data.nodes.map((node) => ({
          id: node.id,
          name: node.data.label,
          device_type: node.data.deviceType,
          properties: node.data.properties,
          x: node.position.x,
          y: node.position.y,
        })),
        links: data.edges.map((edge) => ({
          id: edge.id,
          source: edge.source,
          source_node_id: edge.source,
          target: edge.target,
          target_node_id: edge.target,
          bandwidth: parseBandwidth(edge.data?.bandwidth || '1000Mbps'),
          delay: parseDelay(edge.data?.delay || '0ms'),
          loss: edge.data?.loss || 0,
          properties: edge.data || {},
        })),
      }
      return topologiesAPI.update(id!, updatedTopology)
    },
    onSuccess: () => {
      // Invalidate and refetch topology data
      queryClient.invalidateQueries({ queryKey: ['topology', id] })
      toast.success('Topology saved successfully!')
    },
    onError: (error) => {
      console.error('Failed to save topology:', error)
      toast.error('Failed to save topology.')
    },
  })

  const saveP4DraftMutation = useMutation({
    mutationFn: async (payload: {
      draft_id?: string
      name: string
      source_code: string
      target: string
      architecture: string
      compiled_program_id?: string | null
    }) => {
      if (!id) {
        throw new Error('Missing topology id')
      }
      const response = await topologyP4API.saveDraft(id, payload)
      return response.data
    },
    onSuccess: (draft) => {
      setP4DraftId(draft.draft_id)
      setP4DraftName(draft.name)
      setP4DraftTarget(draft.target)
      setP4DraftArchitecture(draft.architecture)
      setP4DraftCode(draft.source_code)
      setP4LastCompiledProgramId(draft.compiled_program_id || null)
      queryClient.invalidateQueries({ queryKey: ['topology-p4-drafts', id] })
      toast.success('P4 program saved')
    },
    onError: (error: any) => {
      toast.error(error?.message || 'Failed to save P4 program')
    },
  })

  const deleteP4DraftMutation = useMutation({
    mutationFn: async (draftId: string) => {
      if (!id) throw new Error('Missing topology id')
      await topologyP4API.deleteDraft(id, draftId)
      return draftId
    },
    onSuccess: async (draftId) => {
      if (p4DraftId === draftId) {
        setP4DraftId(null)
        setP4DraftName('Untitled')
        setP4DraftTarget('bmv2')
        setP4DraftArchitecture('v1model')
        setP4DraftCode('')
        setP4LastCompiledProgramId(null)
      }
      await refetchP4Drafts()
      toast.success('P4 draft deleted')
    },
    onError: (error: any) => {
      toast.error(error?.message || 'Failed to delete P4 draft')
    },
  })

  const handleSaveP4Draft = async (code: string) => {
    saveP4DraftMutation.mutate({
      draft_id: p4DraftId || undefined,
      name: p4DraftName || 'Untitled',
      source_code: code,
      target: p4DraftTarget || 'bmv2',
      architecture: p4DraftArchitecture || 'v1model',
      compiled_program_id: p4LastCompiledProgramId || undefined,
    })
  }

  const handleCompileP4Draft = async (code: string) => {
    setP4DraftCode(code)
    try {
      const res = await p4API.compile({
        name: p4DraftName || 'Untitled',
        source_code: code,
        target: p4DraftTarget || 'bmv2',
        architecture: p4DraftArchitecture || 'v1model',
      })
      const program = res.data
      if (program.status === 'failed') {
        toast.error(program.error || 'P4 compile failed')
        return
      }
      toast.success(`P4 compiled: ${program.program_id}`)
      setP4LastCompiledProgramId(program.program_id)
      saveP4DraftMutation.mutate({
        draft_id: p4DraftId || undefined,
        name: p4DraftName || 'Untitled',
        source_code: code,
        target: p4DraftTarget || 'bmv2',
        architecture: p4DraftArchitecture || 'v1model',
        compiled_program_id: program.program_id,
      })
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'P4 compile failed')
    }
  }

  const handleNodesChange = (nodes: Node[]) => {
    setCurrentNodes(nodes)
    setSyncStatus('out-of-sync')
    const controllerNode = nodes.find(n => n.selected && n.data.deviceType === 'controller')
    if (controllerNode) {
      setSelectedNode(controllerNode)
    }
  }

  const handleEdgesChange = (edges: Edge[]) => {
    setCurrentEdges(edges)
    setSyncStatus('out-of-sync')
  }

  const handleControllerSave = (config: any) => {
    if (selectedNode) {
      const existingProps =
        selectedNode?.data?.properties && typeof selectedNode.data.properties === 'object'
          ? selectedNode.data.properties
          : {}
      const extra =
        config?.config && typeof config.config === 'object' && !Array.isArray(config.config) ? config.config : {}
      const mergedProps = {
        ...existingProps,
        ...extra,
        controller_type: config.controller_type,
        ip: config.ip,
        port: config.port,
      }
      const updatedNode = {
        ...selectedNode,
        data: {
          ...selectedNode.data,
          label: config.name || selectedNode.data.label,
          properties: mergedProps,
        },
      }
      setCurrentNodes(nodes => 
        nodes.map(n => n.id === selectedNode.id ? updatedNode : n)
      )
      setSyncStatus('out-of-sync')
    }
    setShowControllerConfig(false)
    setSelectedNode(null)
  }

  const handleSave = () => {
    saveMutation.mutate({ nodes: currentNodes, edges: currentEdges })
  }

  const handleStartEmulation = () => {
    startMutation.mutate()
  }

  const handleStopEmulation = () => {
    setShowStopModal(true)
  }

  const handleManualSync = () => {
    syncMutation.mutate()
  }

  const isRunning = emulationStatus?.status === 'running'

  const activeShellDevices = shellDevices.length
  const connectionBadgeVariant =
    connectionStatus === 'connected' ? 'success' : connectionStatus === 'connecting' ? 'warning' : 'error'
  const connectionBadgeLabel =
    connectionStatus === 'connected'
      ? 'Live updates connected'
      : connectionStatus === 'connecting'
        ? 'Connecting to live updates'
        : 'Live updates offline'
  const emulationBadgeVariant = isRunning ? 'success' : 'warning'
  const emulationBadgeLabel = isRunning ? 'Emulation running' : 'Emulation stopped'

  const SyncStatusIndicator = () => {
    switch (syncStatus) {
      case 'syncing':
        return (
          <Badge variant="info" size="sm" isLoading>
            Syncing...
          </Badge>
        )
      case 'out-of-sync':
        return (
          <Badge variant="warning" size="sm" withIcon>
            Out of Sync
          </Badge>
        )
      case 'error':
        return (
          <Badge variant="error" size="sm" withIcon>
            Sync Error
          </Badge>
        )
      case 'synced':
      default:
        return (
          <Badge variant="success" size="sm" withIcon>
            In Sync
          </Badge>
        )
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-gray-600 dark:text-gray-400">{t('common.loading')}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="relative min-h-screen bg-gradient-to-b from-gray-50 via-white to-white dark:from-gray-950 dark:via-gray-950 dark:to-gray-950 pb-20 md:pb-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-gradient-to-r from-blue-500/10 via-purple-500/10 to-cyan-500/10 blur-3xl" />

      <div className="relative w-full px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <div className="sticky top-16 z-30">
          <div className="glass-card rounded-3xl border border-white/40 dark:border-gray-800/60 bg-white/80 dark:bg-gray-900/75 px-5 py-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0 space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    leftIcon={<ArrowLeftIcon className="h-4 w-4" />}
                    onClick={() => navigate('/projects')}
                  >
                    Projects
                  </Button>
                  {topology?.id && (
                    <Badge variant="info" size="sm">
                      ID&nbsp;{topology.id}
                    </Badge>
                  )}
                  {emulationId && (
                    <Badge variant="primary" size="sm">
                      Emulation&nbsp;#{emulationId}
                    </Badge>
                  )}
                </div>

                <div className="space-y-1">
                  <h1 className="truncate text-3xl font-bold tracking-tight text-gray-900 dark:text-white">
                    {topology?.name || t('topology.title')}
                  </h1>
                  <p className="max-w-3xl text-sm text-gray-600 dark:text-gray-300">
                    {topology?.description || 'Design, run, and inspect your topology.'}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={emulationBadgeVariant} size="sm" withIcon>
                    {emulationBadgeLabel}
                  </Badge>
                  <Badge variant={connectionBadgeVariant} size="sm" withIcon>
                    {connectionBadgeLabel}
                  </Badge>
                  <SyncStatusIndicator />
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                <Button
                  variant={isRunning ? 'danger' : 'success'}
                  size="sm"
                  leftIcon={isRunning ? <StopIcon className="h-4 w-4" /> : <PlayIcon className="h-4 w-4" />}
                  onClick={isRunning ? handleStopEmulation : handleStartEmulation}
                  isLoading={startMutation.isPending || stopMutation.isPending}
                >
                  {isRunning ? 'Stop' : 'Start'}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  leftIcon={<RefreshIcon className="h-4 w-4" />}
                  onClick={handleManualSync}
                  isLoading={syncMutation.isPending}
                >
                  Sync
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<CommandLineIcon className="h-4 w-4" />}
                  onClick={() => setShowWebShell(true)}
                  disabled={!activeShellDevices}
                >
                  WebShell
                </Button>
                {selectedNode?.data.deviceType === 'controller' && (
                  <Button
                    variant="ghost"
                    size="sm"
                    leftIcon={<CogIcon className="h-4 w-4" />}
                    onClick={() => setShowControllerConfig(true)}
                  >
                    Controller
                  </Button>
                )}
                {isRunning && id && (
                  <Button
                    variant="ghost"
                    size="sm"
                    leftIcon={<ChartBarIcon className="h-4 w-4" />}
                    onClick={() => navigate(`/network-manager?topology=${id}`)}
                  >
                    Network
                  </Button>
                )}
                <Button
                  variant="primary"
                  size="sm"
                  leftIcon={<CheckBadgeIcon className="h-4 w-4" />}
                  onClick={handleSave}
                  isLoading={saveMutation.isPending}
                >
                  Save
                </Button>
              </div>
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-3xl border border-gray-200/70 bg-white/90 shadow-sm backdrop-blur-md dark:border-gray-800/70 dark:bg-gray-900/80">
          <div className="flex flex-col gap-3 border-b border-gray-200/70 bg-white/70 px-4 py-3 dark:border-gray-800/70 dark:bg-gray-900/60 md:flex-row md:items-center md:justify-between">
            <div className="inline-flex rounded-full bg-gray-100 p-1 dark:bg-gray-800">
              <button
                type="button"
                onClick={() => setActiveTab('designer')}
                className={cn(
                  'px-4 py-2 text-sm font-medium rounded-full',
                  activeTab === 'designer'
                    ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-950 dark:text-white'
                    : 'text-gray-600 hover:bg-white/60 dark:text-gray-300 dark:hover:bg-gray-700/60'
                )}
              >
                Canvas
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('p4')}
                className={cn(
                  'px-4 py-2 text-sm font-medium rounded-full',
                  activeTab === 'p4'
                    ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-950 dark:text-white'
                    : 'text-gray-600 hover:bg-white/60 dark:text-gray-300 dark:hover:bg-gray-700/60'
                )}
              >
                P4
              </button>
            </div>

            <div className="text-xs text-gray-500 dark:text-gray-400">
              {currentNodes.length} devices • {currentEdges.length} links
            </div>
          </div>

          {activeTab === 'designer' ? (
            <div className="relative h-[76vh] min-h-[600px] bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.08)_0%,_transparent_55%)] dark:bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.12)_0%,_transparent_55%)]">
              <TopologyDesigner
                key={id}
                initialNodes={currentNodes}
                initialEdges={currentEdges}
                onNodesChange={handleNodesChange}
                onEdgesChange={handleEdgesChange}
                overlayById={algoOverlayById}
              />
            </div>
          ) : (
            <div className="p-6">
              <div className="space-y-4">
                <div className="flex flex-col gap-3 rounded-2xl border border-gray-200/70 bg-white/80 p-4 shadow-sm backdrop-blur-md dark:border-gray-800/70 dark:bg-gray-900/60 md:flex-row md:items-end md:justify-between">
                  <div className="flex flex-col gap-3 md:flex-row md:items-end">
                    <div className="space-y-1">
                      <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Draft</label>
                      <select
                        value={p4DraftId || ''}
                        onChange={(e) => {
                          const nextId = e.target.value || null
                          setP4DraftId(nextId)
                          const selected = (p4Drafts || []).find((d) => d.draft_id === nextId)
                          if (selected) {
                            setP4DraftName(selected.name)
                            setP4DraftTarget(selected.target || 'bmv2')
                            setP4DraftArchitecture(selected.architecture || 'v1model')
                            setP4DraftCode(selected.source_code || '')
                            setP4LastCompiledProgramId(selected.compiled_program_id || null)
                          }
                        }}
                        className="input-field w-64"
                        disabled={p4DraftsLoading}
                      >
                        <option value="">(new)</option>
                        {(p4Drafts || []).map((draft) => (
                          <option key={draft.draft_id} value={draft.draft_id}>
                            {draft.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Name</label>
                      <input
                        value={p4DraftName}
                        onChange={(e) => setP4DraftName(e.target.value)}
                        className="input-field w-64"
                        placeholder="MyP4Program"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Target</label>
                      <select
                        value={p4DraftTarget}
                        onChange={(e) => setP4DraftTarget(e.target.value)}
                        className="input-field w-40"
                      >
                        <option value="bmv2">BMv2</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Architecture</label>
                      <select
                        value={p4DraftArchitecture}
                        onChange={(e) => setP4DraftArchitecture(e.target.value)}
                        className="input-field w-40"
                      >
                        <option value="v1model">v1model</option>
                        <option value="psa">psa</option>
                      </select>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    {p4LastCompiledProgramId && (
                      <span className="text-xs text-gray-600 dark:text-gray-400">
                        Last compiled: <span className="font-mono">{p4LastCompiledProgramId}</span>
                      </span>
                    )}
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void refetchP4Drafts()}
                      disabled={p4DraftsLoading}
                    >
                      Refresh
                    </Button>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => {
                        setP4DraftId(null)
                        setP4DraftName('Untitled')
                        setP4DraftTarget('bmv2')
                        setP4DraftArchitecture('v1model')
                        setP4DraftCode(DEFAULT_P4_CODE)
                        setP4LastCompiledProgramId(null)
                      }}
                    >
                      New
                    </Button>
                    <Button
                      variant="danger"
                      size="sm"
                      disabled={!p4DraftId}
                      onClick={() => {
                        if (!p4DraftId) return
                        deleteP4DraftMutation.mutate(p4DraftId)
                      }}
                    >
                      Delete
                    </Button>
                  </div>
                </div>

                <P4Editor
                  value={p4DraftCode}
                  onChange={(next) => setP4DraftCode(next)}
                  onSave={handleSaveP4Draft}
                  onCompile={handleCompileP4Draft}
                  height="70vh"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {showStopModal && isRunning && (
        <div className="fixed inset-0 bg-black/60 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 p-6 rounded-2xl max-w-md w-full shadow-2xl border border-gray-200 dark:border-gray-700">
            <h2 className="text-xl font-bold mb-4 text-gray-900 dark:text-white">Stop Emulation</h2>
            <div className="space-y-3 text-sm text-gray-700 dark:text-gray-300">
              <label className="flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={stopAlsoInfra}
                  onChange={(e) => {
                    const next = e.target.checked
                    setStopAlsoInfra(next)
                    if (!next) setDeleteInfraData(false)
                  }}
                  className="mt-1 h-4 w-4 rounded border-gray-300 dark:border-gray-600"
                />
                <span>Also stop isolated infrastructure containers (this can break embedded controller UIs until restarted)</span>
              </label>
              <label className="flex items-start gap-2">
                <input
                  type="checkbox"
                  checked={deleteInfraData}
                  onChange={(e) => setDeleteInfraData(e.target.checked)}
                  disabled={!stopAlsoInfra}
                  className="mt-1 h-4 w-4 rounded border-gray-300 dark:border-gray-600"
                />
                <span>Delete isolated infrastructure data (volumes). This cannot be undone.</span>
              </label>
            </div>
            <div className="flex justify-end gap-3 pt-5">
              <Button variant="secondary" onClick={() => setShowStopModal(false)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  setShowStopModal(false)
                  stopMutation.mutate({
                    cleanup: true,
                    stop_infra: stopAlsoInfra,
                    preserve_infra_data: !deleteInfraData,
                  })
                }}
                isLoading={stopMutation.isPending}
              >
                Stop
              </Button>
            </div>
          </div>
        </div>
      )}

      {showWebShell && (
        <div className="modal-backdrop" onClick={() => setShowWebShell(false)}>
          <div
            className="glass-card w-full max-w-4xl h-[75vh] overflow-hidden rounded-3xl border border-white/60 bg-white/95 shadow-2xl backdrop-blur-xl dark:border-gray-800/80 dark:bg-gray-900/95"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-gray-200/70 bg-white/80 px-6 py-4 dark:border-gray-800/70 dark:bg-gray-900/80">
              <div className="space-y-1">
                <p className="text-sm font-medium text-gray-700 dark:text-gray-200">Select device</p>
                <select
                  value={selectedDevice}
                  onChange={(e) => setSelectedDevice(e.target.value)}
                  className="input-field w-64"
                >
                  {shellDevices.map((device: any) => {
                    const value = device.runtime_name || device.name || device.id || ''
                    const label = device.name || device.runtime_name || value
                    return (
                      <option key={value} value={value}>
                        {label}
                      </option>
                    )
                  })}
                </select>
              </div>
              <Button variant="ghost" size="sm" onClick={() => setShowWebShell(false)}>
                Close
              </Button>
            </div>
            {selectedDevice ? (
              <WebShell device={selectedDevice} container={containerName} onClose={() => setShowWebShell(false)} />
            ) : (
              <div className="flex flex-1 items-center justify-center text-gray-500 dark:text-gray-400">
                No devices available
              </div>
            )}
          </div>
        </div>
      )}

      {showControllerConfig && (
        <div className="modal-backdrop" onClick={() => setShowControllerConfig(false)}>
          <div
            className="glass-card max-w-2xl w-full overflow-hidden rounded-3xl border border-white/60 bg-white/95 shadow-2xl backdrop-blur-xl dark:border-gray-800/80 dark:bg-gray-900/95"
            onClick={(e) => e.stopPropagation()}
          >
            <ControllerConfig
              controller={{
                name: selectedNode?.data?.label || '',
                controller_type: selectedNode?.data?.properties?.controller_type || 'osken',
                ip: selectedNode?.data?.properties?.ip || '127.0.0.1',
                port: selectedNode?.data?.properties?.port || 6653,
                config: selectedNode?.data?.properties || {},
              }}
              onSave={handleControllerSave}
              onCancel={() => {
                setShowControllerConfig(false)
                setSelectedNode(null)
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
