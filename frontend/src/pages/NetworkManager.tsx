import { useState, useEffect, useMemo, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useQueries } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import Editor from '@monaco-editor/react'
import ReactFlow, { Background, Controls, MiniMap, MarkerType, type Node, type Edge, type NodeTypes } from 'reactflow'
import 'reactflow/dist/style.css'
import {
  ArrowLeftIcon,
  ArrowDownTrayIcon,
  CpuChipIcon,
  ServerIcon,
  WifiIcon,
  ChartBarIcon,
  ChatBubbleLeftRightIcon,
  CodeBracketIcon,
  ClockIcon,
  CommandLineIcon,
  Cog6ToothIcon,
  WrenchScrewdriverIcon,
  PlayIcon,
} from '@heroicons/react/24/outline'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
} from 'recharts'
import { Button } from '@/components/atoms/Button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'
import { Select } from '@/components/atoms/Select'
import { MetricCard } from '@/components/molecules/MetricCard'
import WSNDashboard from '@/components/wsn/WSNDashboard'
import AlgorithmRunsCompare, { type AlgorithmRunCompareItem } from '@/components/algorithms/AlgorithmRunsCompare'
import AlgoMessageTimelineChart from '@/components/algorithms/AlgoMessageTimelineChart'
import AlgoNodeStatsCharts from '@/components/algorithms/AlgoNodeStatsCharts'
import AlgoMessageTypesChart from '@/components/algorithms/AlgoMessageTypesChart'
import WebShell from '@components/WebShell'
import MininetCLI from '@components/MininetCLI'
import ContainerUI from '@components/ContainerUI'
import ControlConfigPanel from '@components/ControlConfigPanel'
import AiConsole from '@components/ai/AiConsole'
import TopologyTests from '@components/TopologyTests'
import TopologyDiagnostics from '@components/TopologyDiagnostics'
import MlModelsPanel from '@/components/ml/MlModelsPanel'
import DataLabPanel from '@/components/ml/DataLabPanel'
import ControllersTab from './network-manager/ControllersTab'
import ManoTab from './network-manager/ManoTab'
import { KvTableEditor, kvObjectToRows, kvRowsToObject, newKvRow, type KvRow } from './network-manager/kv'
import { topologiesAPI, emulationAPI, devicesAPI, monitoringAPI, aiAPI, networkConfigsAPI, infrastructureAPI, algorithmsAPI, manoAPI, osmAPI } from '@services/api'
import { Input } from '@/components/atoms/Input'
import JsonViewer from '@/components/JsonViewer'
import MarkdownViewer from '@/components/MarkdownViewer'
import { useTheme } from '@/contexts/ThemeContext'
import { cn } from '@/utils/cn'
import type { AlgorithmTemplate } from '@/examples/algorithmTemplates'
import { ALGORITHM_TEMPLATES, getAlgorithmTemplate } from '@/examples/algorithmTemplates'
import { DeviceNode } from '@components/nodes/DeviceNode'
import type { DeviceType } from '@/types/topology'

type RouteRow = {
  dst: string
  via?: string
  dev?: string
  metric?: string
}

const splitLines = (value: string): string[] =>
  (value || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)

const parseStaticRoutes = (value: string): RouteRow[] => {
  const lines = splitLines(value)
  const rows: RouteRow[] = []
  for (const line of lines) {
    const tokens = line.split(/\s+/).filter(Boolean)
    if (!tokens.length) continue
    const dst = tokens[0]
    const viaIndex = tokens.indexOf('via')
    const devIndex = tokens.indexOf('dev')
    const metricIndex = tokens.indexOf('metric')
    const via = viaIndex >= 0 ? tokens[viaIndex + 1] : undefined
    const dev = devIndex >= 0 ? tokens[devIndex + 1] : undefined
    const metric = metricIndex >= 0 ? tokens[metricIndex + 1] : undefined
    rows.push({ dst, via, dev, metric })
  }
  return rows
}

const serializeStaticRoutes = (rows: RouteRow[]): string => {
  return rows
    .map((r) => {
      const dst = (r.dst || '').trim()
      if (!dst) return ''
      const parts = [dst]
      const via = (r.via || '').trim()
      const dev = (r.dev || '').trim()
      const metric = (r.metric || '').trim()
      if (via) parts.push('via', via)
      if (dev) parts.push('dev', dev)
      if (metric) parts.push('metric', metric)
      return parts.join(' ')
    })
    .filter(Boolean)
    .join('\n')
}

const algorithmPreviewNodeTypes: NodeTypes = {
  device: DeviceNode,
}

const guessDeviceTypeFromNodeId = (nodeId: string): DeviceType => {
  const v = String(nodeId || '').toLowerCase()
  if (v.includes('p4') && v.includes('switch')) return 'p4switch'
  if (v.includes('switch')) return 'switch'
  if (v.includes('router')) return 'router'
  if (v.includes('station')) return 'station'
  if (v.includes('ap')) return 'ap'
  if (v.includes('controller')) return 'controller'
  return 'host'
}

const formatAlgoTs = (ts: any): string => {
  const n = Number(ts)
  if (!Number.isFinite(n) || n <= 0) return '—'
  return new Date(n * 1000).toLocaleTimeString()
}

const normalizeGateway = (value: string): string => {
  const trimmed = (value || '').trim()
  if (!trimmed) return ''
  const viaMatch = trimmed.match(/via\\s+([^\\s]+)/i)
  if (viaMatch?.[1]) return viaMatch[1]
  return trimmed.split(/\s+/)[0] || ''
}

export default function NetworkManager() {
  const { t } = useTranslation()
  const { theme } = useTheme()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const topologyId = searchParams.get('topology')
  const [activeTab, setActiveTab] = useState<
    | 'overview'
    | 'metrics'
    | 'hosts'
    | 'switches'
    | 'routers'
    | 'controllers'
    | 'mano'
    | 'tests'
    | 'config'
    | 'algorithms'
    | 'topology-export'
    | 'terminal'
    | 'mininet-cli'
    | 'diagnostics'
    | 'container-ui'
    | 'ai-console'
    | 'ml-models'
    | 'data-lab'
  >('overview')
  const tabParam = (searchParams.get('tab') || '').toLowerCase()
  const [topologyPickerId, setTopologyPickerId] = useState<string>('')
  const configPaneParam = (searchParams.get('config') || '').toLowerCase()

  useEffect(() => {
    if (activeTab !== 'overview') return
    const allowed = new Set([
      'overview',
      'metrics',
      'mano',
      'hosts',
      'switches',
      'routers',
      'controllers',
      'mininet-cli',
      'tests',
      'config',
      'algorithms',
      'topology-export',
      'terminal',
      'diagnostics',
      'container-ui',
      'ai-console',
      'ml-models',
      'data-lab',
    ])
    if (allowed.has(tabParam)) setActiveTab(tabParam as any)
  }, [tabParam, activeTab])
  const [emulationId, setEmulationId] = useState<string | null>(null)
  const [selectedDevice, setSelectedDevice] = useState<string>('')
  const [networkConfigText, setNetworkConfigText] = useState<string>('')
  const [networkConfigName, setNetworkConfigName] = useState<string>('')
  const [networkConfigDescription, setNetworkConfigDescription] = useState<string>('')
  const [networkConfigDryRun, setNetworkConfigDryRun] = useState<boolean>(false)
  const networkConfigFileInputRef = useRef<HTMLInputElement | null>(null)
  const [configPane, setConfigPane] = useState<'control' | 'device' | 'network'>('control')
  const [topologyExportFormat, setTopologyExportFormat] = useState<'mininet' | 'mininet-wifi' | 'containernet'>(
    'mininet'
  )
  const [algoTransport, setAlgoTransport] = useState<'udp' | 'tcp'>('udp')
  const [algoListenPort, setAlgoListenPort] = useState<number>(50000)
  const [algoTemplateId, setAlgoTemplateId] = useState<AlgorithmTemplate['id']>('distributed-mis')
  const [algoLiveUpdatesEnabled, setAlgoLiveUpdatesEnabled] = useState<boolean>(true)
  const [algoTraceMessagesEnabled, setAlgoTraceMessagesEnabled] = useState<boolean>(true)
  const [algoTracePayloadEnabled, setAlgoTracePayloadEnabled] = useState<boolean>(false)
  const [algoManifestText, setAlgoManifestText] = useState<string>(() => {
    const tpl = getAlgorithmTemplate('distributed-mis')
    return JSON.stringify(tpl.manifest, null, 2)
  })
  const [algoSourceCode, setAlgoSourceCode] = useState<string>(() => {
    const tpl = getAlgorithmTemplate('distributed-mis')
    return tpl.code
  })
  const [algoParamsText, setAlgoParamsText] = useState<string>('{}')
  const [algoRunId, setAlgoRunId] = useState<string | null>(null)
  const [algoOverlayById, setAlgoOverlayById] = useState<Record<string, any>>({})
  const [algoMetricsBaseline, setAlgoMetricsBaseline] = useState<{
    total_rx_packets: number
    total_tx_packets: number
    total_rx_bytes: number
    total_tx_bytes: number
  } | null>(null)
  const [algoUiTab, setAlgoUiTab] = useState<'graph' | 'metrics' | 'events' | 'editors' | 'history'>('metrics')
  const [algoEventsTab, setAlgoEventsTab] = useState<'table' | 'raw'>('table')
  const [algoEventsView, setAlgoEventsView] = useState<'messages' | 'system'>('messages')
  const [algoEventNodeFilter, setAlgoEventNodeFilter] = useState<string>('all')
  const [algoEventTypeFilter, setAlgoEventTypeFilter] = useState<string>('all')
  const [algoSelectedEventKey, setAlgoSelectedEventKey] = useState<string>('')
  const [algoMsgDirFilter, setAlgoMsgDirFilter] = useState<'all' | 'tx' | 'rx' | 'bcast'>('all')
  const [algoMsgLocalNodeFilter, setAlgoMsgLocalNodeFilter] = useState<string>('all')
  const [algoMsgPeerFilter, setAlgoMsgPeerFilter] = useState<string>('all')
  const [algoMsgTypeFilter, setAlgoMsgTypeFilter] = useState<string>('all')
  const [algoNodeSearch, setAlgoNodeSearch] = useState<string>('')
  const [algoHistoryWindowMinutes, setAlgoHistoryWindowMinutes] = useState<number>(24 * 60)
  const [algoHistoryAlgorithmFilter, setAlgoHistoryAlgorithmFilter] = useState<string>('')
  const [algoHistorySelectedRunId, setAlgoHistorySelectedRunId] = useState<string>('')
  const [algoHistoryMode, setAlgoHistoryMode] = useState<'inspect' | 'compare'>('inspect')
  const [algoHistoryCompareRunIds, setAlgoHistoryCompareRunIds] = useState<string[]>([])
  const [algoNetSeries, setAlgoNetSeries] = useState<
    { ts: string; packetsDelta: number; bytesDelta: number; rxPacketsDelta: number; txPacketsDelta: number }[]
  >([])
  const [metricsHistory, setMetricsHistory] = useState<
    { ts: string; rx: number; tx: number; cpu: number; mem: number }[]
  >([])
  const [aiDiagnosis, setAiDiagnosis] = useState<string>('')
  const [aiDiagnosisHeuristics, setAiDiagnosisHeuristics] = useState<any>(null)
  const [aiDiagnosing, setAiDiagnosing] = useState<boolean>(false)

  const networkConfigPreview = useMemo(() => {
    const trimmed = (networkConfigText || '').trim()
    if (!trimmed) return { data: null as any, error: '' }
    try {
      return { data: JSON.parse(trimmed), error: '' }
    } catch (e: any) {
      return { data: null as any, error: e?.message || 'Invalid JSON' }
    }
  }, [networkConfigText])

  const getDeviceKey = (device: any) =>
    device?.properties?.node_id || device?.runtime_name || device?.name

  const getRuntimeName = (device: any) =>
    device?.runtime_name || device?.properties?.node_id || device?.name

  const getDeviceType = (device: any) => (device?.device_type || device?.type || '').toLowerCase()
  const queryClient = useQueryClient()

	  const tabs = [
	    { id: 'overview', label: t('nav.overview'), icon: ChartBarIcon },
	    { id: 'metrics', label: t('monitoring.title', 'Metrics'), icon: ChartBarIcon },
	    { id: 'mano', label: 'MANO', icon: Cog6ToothIcon },
	    { id: 'hosts', label: t('nodes.hosts'), icon: CpuChipIcon },
	    { id: 'switches', label: t('nodes.switches'), icon: ServerIcon },
	    { id: 'routers', label: t('nodes.routers'), icon: WifiIcon },
	    { id: 'controllers', label: t('nodes.controllers', 'Controllers'), icon: CpuChipIcon },
	    { id: 'mininet-cli', label: 'Mininet CLI', icon: CommandLineIcon },
	    { id: 'tests', label: 'Test Network Topology', icon: PlayIcon },
	    { id: 'config', label: t('network.configuration', 'Configuration'), icon: Cog6ToothIcon },
	    { id: 'algorithms', label: 'Algorithms', icon: CpuChipIcon },
	    { id: 'topology-export', label: t('topology.export', 'Export Script'), icon: ArrowDownTrayIcon },
	    { id: 'terminal', label: t('webshell.title'), icon: CommandLineIcon },
	    { id: 'diagnostics', label: t('nav.diagnostics'), icon: WrenchScrewdriverIcon },
	    { id: 'container-ui', label: t('container.ui', 'Container UI'), icon: ServerIcon },
	    { id: 'ai-console', label: 'AI Console', icon: CommandLineIcon },
	    { id: 'ml-models', label: t('nav.mlModels', 'ML Models'), icon: CpuChipIcon },
	    { id: 'data-lab', label: t('nav.dataLab', 'Data Lab'), icon: CodeBracketIcon },
	  ]

  const [configDraft, setConfigDraft] = useState<{ [key: string]: string }>({
    ip: '',
    ip6: '',
    mac: '',
    default_route: '',
    mtu: '',
    static_routes: '',
    dns_servers: '',
    startup_commands: '',
    controller: '',
    openflow_version: '',
    router_daemon: '',
    protocols: '',
  })
  const [configFeedback, setConfigFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [routeRows, setRouteRows] = useState<RouteRow[]>([])
  const [dnsRows, setDnsRows] = useState<string[]>([])
  const [commandRows, setCommandRows] = useState<string[]>([])
  const [ifaceSelection, setIfaceSelection] = useState<string>('')
  const [isApplyingDemoConfig, setIsApplyingDemoConfig] = useState<boolean>(false)

  const [selectedControllerId, setSelectedControllerId] = useState<string>('')
  const [controllerCommand, setControllerCommand] = useState<string>('ls -la')
  const [controllerOutput, setControllerOutput] = useState<string>('')
  const [controllerConsole, setControllerConsole] = useState<string[]>([])
  const [controllerSearch, setControllerSearch] = useState<string>('')
  const [controllerPane, setControllerPane] = useState<'overview' | 'terminal' | 'quick' | 'ui'>('overview')

  const [manoPane, setManoPane] = useState<'overview' | 'local' | 'osm'>('overview')

  const [manoCatalogTab, setManoCatalogTab] = useState<'nsd' | 'vnfd'>('nsd')

  const [manoNsdName, setManoNsdName] = useState<string>('demo-nsd')
  const [manoNsdTopologyId, setManoNsdTopologyId] = useState<string>(topologyId || '')
  const [manoNsdOptionRows, setManoNsdOptionRows] = useState<KvRow[]>(() => [newKvRow()])
  const [manoSelectedNsdId, setManoSelectedNsdId] = useState<string>('')

  const [manoVnfdName, setManoVnfdName] = useState<string>('demo-vnfd')
  const [manoVnfdDeviceType, setManoVnfdDeviceType] = useState<string>('container')
  const [manoVnfdDefaultsRows, setManoVnfdDefaultsRows] = useState<KvRow[]>(() => [newKvRow()])
  const [manoSelectedVnfdId, setManoSelectedVnfdId] = useState<string>('')

  const [manoNsName, setManoNsName] = useState<string>('demo-ns')
  const [manoNsDryRun, setManoNsDryRun] = useState<boolean>(true)
  const [manoNsBackend, setManoNsBackend] = useState<'local' | 'osm'>('local')
  const [manoOsmNsdId, setManoOsmNsdId] = useState<string>('')
  const [manoOsmVimAccountId, setManoOsmVimAccountId] = useState<string>('')

  const [osmTab, setOsmTab] = useState<'overview' | 'packages' | 'ns' | 'mirror' | 'ui'>('overview')
  const [osmUiKind, setOsmUiKind] = useState<'ng' | 'light'>('ng')
  const [osmCreateNsName, setOsmCreateNsName] = useState<string>('osm-ns-1')
  const [osmCreateNsDescription, setOsmCreateNsDescription] = useState<string>('')
  const [osmSelectedNsdPkgId, setOsmSelectedNsdPkgId] = useState<string>('')
  const [osmSelectedVimAccountId, setOsmSelectedVimAccountId] = useState<string>('')
  const [osmInstantiateJson, setOsmInstantiateJson] = useState<string>('{}')
  const [osmSelectedNsInstanceId, setOsmSelectedNsInstanceId] = useState<string>('')
  const [osmMirrorResourceType, setOsmMirrorResourceType] = useState<string>('')
  const [osmMirrorIncludeDeleted, setOsmMirrorIncludeDeleted] = useState<boolean>(false)
  const [osmMirrorSelectedId, setOsmMirrorSelectedId] = useState<string>('')
  const [manoVnfName, setManoVnfName] = useState<string>('vnf-1')
  const [manoVnfDeviceType, setManoVnfDeviceType] = useState<string>('container')
  const [manoVnfPropsRows, setManoVnfPropsRows] = useState<KvRow[]>(() => [newKvRow()])
  const [manoVnfDryRun, setManoVnfDryRun] = useState<boolean>(false)
  const [manoVnfDeleteForce, setManoVnfDeleteForce] = useState<boolean>(false)
  const [manoSelectedNsId, setManoSelectedNsId] = useState<string>('')
  const [manoExecCommand, setManoExecCommand] = useState<string>('uname -a')
  const [manoSelectedVnfId, setManoSelectedVnfId] = useState<string>('')

  useEffect(() => {
    if (activeTab !== 'config') return
    if (configPaneParam === 'device' || configPaneParam === 'network' || configPaneParam === 'control') {
      setConfigPane(configPaneParam as any)
    }
  }, [activeTab, configPaneParam])

  useEffect(() => {
    if (!topologyId) return
    setManoNsdTopologyId((prev) => prev || topologyId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topologyId])

  const manoNsdDescriptor = useMemo(() => {
    const parsed = kvRowsToObject(manoNsdOptionRows)
    return { descriptor: { topology_id: (manoNsdTopologyId || '').trim(), options: parsed.obj }, errors: parsed.errors }
  }, [manoNsdOptionRows, manoNsdTopologyId])

  const manoVnfdDescriptor = useMemo(() => {
    const parsed = kvRowsToObject(manoVnfdDefaultsRows)
    return {
      descriptor: { device_type: (manoVnfdDeviceType || '').trim(), default_properties: parsed.obj },
      errors: parsed.errors,
    }
  }, [manoVnfdDefaultsRows, manoVnfdDeviceType])

  const manoVnfProperties = useMemo(() => {
    const parsed = kvRowsToObject(manoVnfPropsRows)
    return { properties: parsed.obj, errors: parsed.errors }
  }, [manoVnfPropsRows])

  const manoInfoQuery = useQuery({
    queryKey: ['mano', 'info'],
    queryFn: async () => (await manoAPI.info()).data as any,
    enabled: activeTab === 'mano',
    retry: false,
  })

  const osmAutoEnsureAttemptsRef = useRef<Record<string, number>>({})
  const osmAutoMirrorAttemptsRef = useRef<Record<string, number>>({})

  const osmInfraStatusQuery = useQuery({
    queryKey: ['infra', 'osm', 'status', topologyId],
    queryFn: async () => {
      if (!topologyId) return null as any
      return (await infrastructureAPI.topologyOsmStatus(topologyId)).data as any
    },
    enabled: activeTab === 'mano' && !!topologyId,
    retry: false,
    refetchInterval: 8000,
  })

  const osmEnsureInfraMutation = useMutation({
    mutationFn: async () => {
      if (!topologyId) throw new Error('No topology selected')
      return (await infrastructureAPI.ensureTopologyOsm(topologyId)).data as any
    },
    onSuccess: () => {
      toast.success('OSM stack ensured')
      osmInfraStatusQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Failed to ensure OSM stack'),
  })

  const osmStopInfraMutation = useMutation({
    mutationFn: async (preserveData: boolean) => {
      if (!topologyId) throw new Error('No topology selected')
      return (await infrastructureAPI.stopTopologyOsm(topologyId, preserveData)).data as any
    },
    onSuccess: () => {
      toast.success('OSM stack stopped')
      osmInfraStatusQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Failed to stop OSM stack'),
  })

  const osmPurgeInfraMutation = useMutation({
    mutationFn: async () => {
      if (!topologyId) throw new Error('No topology selected')
      return (await infrastructureAPI.purgeTopologyOsm(topologyId, true)).data as any
    },
    onSuccess: () => {
      toast.success('OSM stack purged')
      osmInfraStatusQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Failed to purge OSM stack'),
  })

  const osmConnectorRunning = useMemo(() => {
    const items = osmInfraStatusQuery.data?.containers || []
    if (!topologyId) return false
    const short = String(topologyId).slice(0, 8)
    return items.some((c: any) => {
      const name = String(c?.name || '')
      const st = String(c?.status || '').toLowerCase()
      return name.includes(`caduceus-osm-topo-${short}-connector`) && (st === 'running' || st === 'restarting')
    })
  }, [osmInfraStatusQuery.data, topologyId])

  useEffect(() => {
    if (activeTab !== 'mano') return
    if (!topologyId) return
    const tid = String(topologyId)
    const attempts = osmAutoEnsureAttemptsRef.current[tid] || 0
    if (attempts >= 3) return
    if (osmConnectorRunning) return
    if (osmEnsureInfraMutation.isPending) return
    // Auto-ensure per-topology OSM (isolated) so each topology can have its own MANO stack.
    if (!osmInfraStatusQuery.isLoading && !osmInfraStatusQuery.isFetching && !osmConnectorRunning) {
      osmAutoEnsureAttemptsRef.current[tid] = attempts + 1
      osmEnsureInfraMutation.mutate()
    }
  }, [
    activeTab,
    topologyId,
    osmInfraStatusQuery.isLoading,
    osmInfraStatusQuery.isFetching,
    osmConnectorRunning,
    osmEnsureInfraMutation.isPending,
    osmEnsureInfraMutation,
  ])

  const osmInfoQuery = useQuery({
    queryKey: ['osm', 'info', topologyId],
    queryFn: async () => (await osmAPI.info(topologyId || undefined)).data as any,
    enabled: activeTab === 'mano' && !!topologyId && osmConnectorRunning,
    retry: false,
  })

  const osmProjectsQuery = useQuery({
    queryKey: ['osm', 'projects', topologyId],
    queryFn: async () => (await osmAPI.listProjects(topologyId || undefined)).data as any,
    enabled: activeTab === 'mano' && osmTab === 'overview' && !!topologyId && osmConnectorRunning,
    retry: false,
  })

  const osmVimAccountsQuery = useQuery({
    queryKey: ['osm', 'vim-accounts', topologyId],
    queryFn: async () => (await osmAPI.listVimAccounts(topologyId || undefined)).data as any,
    enabled: activeTab === 'mano' && !!topologyId && osmConnectorRunning,
    retry: false,
  })

  const osmWimAccountsQuery = useQuery({
    queryKey: ['osm', 'wim-accounts', topologyId],
    queryFn: async () => (await osmAPI.listWimAccounts(topologyId || undefined)).data as any,
    enabled: activeTab === 'mano' && !!topologyId && osmConnectorRunning,
    retry: false,
  })

  const osmSdnControllersQuery = useQuery({
    queryKey: ['osm', 'sdns', topologyId],
    queryFn: async () => (await osmAPI.proxy('GET', 'admin/v1/sdns', undefined, undefined, topologyId || undefined)).data as any,
    enabled: activeTab === 'mano' && osmTab === 'overview' && !!topologyId && osmConnectorRunning,
    retry: false,
  })

  const osmNsdPackagesQuery = useQuery({
    queryKey: ['osm', 'nsd-packages', topologyId],
    queryFn: async () => (await osmAPI.listNsdPackages(topologyId || undefined)).data as any,
    enabled: activeTab === 'mano' && (osmTab === 'packages' || osmTab === 'ns') && !!topologyId && osmConnectorRunning,
    retry: false,
  })

  const osmVnfdPackagesQuery = useQuery({
    queryKey: ['osm', 'vnfd-packages', topologyId],
    queryFn: async () => (await osmAPI.listVnfdPackages(topologyId || undefined)).data as any,
    enabled: activeTab === 'mano' && osmTab === 'packages' && !!topologyId && osmConnectorRunning,
    retry: false,
  })

  const osmNsInstancesQuery = useQuery({
    queryKey: ['osm', 'ns-instances', topologyId],
    queryFn: async () => (await osmAPI.listNsInstances(topologyId || undefined)).data as any,
    enabled: activeTab === 'mano' && osmTab === 'ns' && !!topologyId && osmConnectorRunning,
    retry: false,
    refetchInterval: 5000,
  })

  const osmMirrorStatsQuery = useQuery({
    queryKey: ['mano', 'osm-mirror', 'stats', topologyId],
    queryFn: async () => {
      if (!topologyId) return null as any
      return (await manoAPI.osmMirrorStats({ topology_id: topologyId })).data as any
    },
    enabled: activeTab === 'mano' && !!topologyId,
    retry: false,
    refetchInterval: 15000,
  })

  const osmMirrorResourcesQuery = useQuery({
    queryKey: ['mano', 'osm-mirror', 'resources', topologyId, osmMirrorResourceType, osmMirrorIncludeDeleted],
    queryFn: async () => {
      if (!topologyId) return null as any
      return (
        await manoAPI.osmMirrorResources({
          topology_id: topologyId,
          resource_type: (osmMirrorResourceType || '').trim() || undefined,
          include_deleted: osmMirrorIncludeDeleted,
          limit: 200,
          offset: 0,
        })
      ).data as any
    },
    enabled: activeTab === 'mano' && osmTab === 'mirror' && !!topologyId,
    retry: false,
  })

  useEffect(() => {
    if (activeTab !== 'mano') return
    if (!topologyId) return
    if (!osmConnectorRunning) return
    const tid = String(topologyId)
    const attempts = osmAutoMirrorAttemptsRef.current[tid] || 0
    if (attempts >= 2) return
    osmAutoMirrorAttemptsRef.current[tid] = attempts + 1
    // Auto-sync OSM → DB once when the connector comes up so the Mirror/Inventory views are populated.
    ;(async () => {
      try {
        await manoAPI.osmMirrorSync({ topology_id: tid, resources: [], mark_deleted: true })
        osmMirrorStatsQuery.refetch()
        osmMirrorResourcesQuery.refetch()
      } catch (err) {
        console.warn('Auto OSM mirror sync failed', err)
      }
    })()
  }, [activeTab, topologyId, osmConnectorRunning, osmMirrorStatsQuery, osmMirrorResourcesQuery])

  const osmMirrorSyncMutation = useMutation({
    mutationFn: async () => {
      if (!topologyId) throw new Error('No topology selected')
      return (await manoAPI.osmMirrorSync({ topology_id: topologyId, resources: [], mark_deleted: true })).data as any
    },
    onSuccess: () => {
      toast.success('OSM mirror sync completed')
      osmMirrorStatsQuery.refetch()
      osmMirrorResourcesQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Mirror sync failed'),
  })

  const osmReconcileMutation = useMutation({
    mutationFn: async () => {
      if (!topologyId) throw new Error('No topology selected')
      return (await manoAPI.osmReconcile({ topology_id: topologyId, ensure_osm_stack: true, sync_after: true })).data as any
    },
    onSuccess: () => {
      toast.success('OSM reconcile completed')
      osmInfraStatusQuery.refetch()
      osmInfoQuery.refetch()
      osmProjectsQuery.refetch()
      osmVimAccountsQuery.refetch()
      osmWimAccountsQuery.refetch()
      osmSdnControllersQuery.refetch()
      osmNsdPackagesQuery.refetch()
      osmVnfdPackagesQuery.refetch()
      osmNsInstancesQuery.refetch()
      osmMirrorStatsQuery.refetch()
      osmMirrorResourcesQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Reconcile failed'),
  })

  const uploadOsmNsdMutation = useMutation({
    mutationFn: async (file: File) => (await osmAPI.uploadNsdPackage(file, topologyId || undefined)).data,
    onSuccess: () => {
      toast.success('NSD uploaded')
      osmNsdPackagesQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Upload failed'),
  })

  const uploadOsmVnfdMutation = useMutation({
    mutationFn: async (file: File) => (await osmAPI.uploadVnfdPackage(file, topologyId || undefined)).data,
    onSuccess: () => {
      toast.success('VNFD uploaded')
      osmVnfdPackagesQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Upload failed'),
  })

  const deleteOsmNsdMutation = useMutation({
    mutationFn: async (id: string) => (await osmAPI.deleteNsdPackage(id, topologyId || undefined)).data,
    onSuccess: () => {
      toast.success('NSD deleted')
      osmNsdPackagesQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Delete failed'),
  })

  const deleteOsmVnfdMutation = useMutation({
    mutationFn: async (id: string) => (await osmAPI.deleteVnfdPackage(id, topologyId || undefined)).data,
    onSuccess: () => {
      toast.success('VNFD deleted')
      osmVnfdPackagesQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Delete failed'),
  })

	  const osmCreateNsMutation = useMutation({
	    mutationFn: async () => {
	      const res = await osmAPI.createNsInstance({
	        nsd_id: (osmSelectedNsdPkgId || '').trim(),
	        name: osmCreateNsName,
	        description: osmCreateNsDescription,
	        vim_account_id: (osmSelectedVimAccountId || '').trim(),
	      }, topologyId || undefined)
	      return res.data as any
	    },
    onSuccess: (data) => {
      toast.success('OSM NS instance created')
      const id = String(data?.id || data?._id || '')
      if (id) setOsmSelectedNsInstanceId(id)
      osmNsInstancesQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Create failed'),
  })

  const osmInstantiateNsMutation = useMutation({
    mutationFn: async () => {
      let params: any = {}
      try {
        params = JSON.parse(osmInstantiateJson || '{}')
      } catch {
        params = {}
      }
      const selected = (osmNsInstancesQuery.data || []).find((x: any) => {
        const id = String(x?._id || x?.id || '')
        return id && id === String(osmSelectedNsInstanceId)
      })
      const nsNameGuess = String(selected?.name || selected?.nsName || selected?.['name-ref'] || '').trim()
      const nsdIdGuess = String(
        selected?.nsd?._id || selected?.['nsd-ref'] || selected?.nsdId || osmSelectedNsdPkgId || ''
      ).trim()
      if (osmSelectedVimAccountId && !params.vimAccountId) params.vimAccountId = osmSelectedVimAccountId
      if (nsNameGuess && !params.nsName) params.nsName = nsNameGuess
      if (nsdIdGuess && !params.nsdId) params.nsdId = nsdIdGuess
      const res = await osmAPI.instantiateNsInstance(osmSelectedNsInstanceId, params, topologyId || undefined)
      return res.data as any
    },
    onSuccess: () => {
      toast.success('Instantiate requested')
      osmNsInstancesQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Instantiate failed'),
  })

  const osmTerminateNsMutation = useMutation({
    mutationFn: async (id: string) => (await osmAPI.terminateNsInstance(id, {}, topologyId || undefined)).data,
    onSuccess: () => {
      toast.success('Terminate requested')
      osmNsInstancesQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Terminate failed'),
  })

  const osmDeleteNsMutation = useMutation({
    mutationFn: async (id: string) => (await osmAPI.deleteNsInstance(id, topologyId || undefined)).data,
    onSuccess: () => {
      toast.success('Deleted')
      osmNsInstancesQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Delete failed'),
  })

  const manoNsdsQuery = useQuery({
    queryKey: ['mano', 'nsds'],
    queryFn: async () => (await manoAPI.listNsds()).data as any[],
    enabled: activeTab === 'mano',
    retry: false,
  })

  const manoVnfdsQuery = useQuery({
    queryKey: ['mano', 'vnfds'],
    queryFn: async () => (await manoAPI.listVnfds()).data as any[],
    enabled: activeTab === 'mano',
    retry: false,
  })

  const manoSelectedNsd = useMemo(() => {
    return (manoNsdsQuery.data || []).find((x: any) => String(x?.id) === String(manoSelectedNsdId)) || null
  }, [manoNsdsQuery.data, manoSelectedNsdId])

  const manoSelectedVnfd = useMemo(() => {
    return (manoVnfdsQuery.data || []).find((x: any) => String(x?.id) === String(manoSelectedVnfdId)) || null
  }, [manoVnfdsQuery.data, manoSelectedVnfdId])

  const manoNsInstancesQuery = useQuery({
    queryKey: ['mano', 'ns-instances', topologyId],
    queryFn: async () => (await manoAPI.listNsInstances(topologyId ? { topology_id: topologyId } : undefined)).data as any[],
    enabled: activeTab === 'mano',
    retry: false,
    refetchInterval: 5000,
  })

  const manoAllVnfsQuery = useQuery({
    queryKey: ['mano', 'vnfs', 'all'],
    queryFn: async () => (await manoAPI.listVnfs()).data as any[],
    enabled: activeTab === 'mano',
    retry: false,
    refetchInterval: 5000,
  })

  const manoVnfsQuery = useQuery({
    queryKey: ['mano', 'vnfs', manoSelectedNsId],
    queryFn: async () => (await manoAPI.listVnfs(manoSelectedNsId ? { ns_instance_id: manoSelectedNsId } : undefined)).data as any[],
    enabled: activeTab === 'mano',
    retry: false,
    refetchInterval: 5000,
  })

  const manoOpsQuery = useQuery({
    queryKey: ['mano', 'ops', manoSelectedNsId],
    queryFn: async () => (await manoAPI.listOperations(manoSelectedNsId ? { ns_instance_id: manoSelectedNsId, limit: 50 } : { limit: 50 })).data as any,
    enabled: activeTab === 'mano',
    retry: false,
    refetchInterval: 5000,
  })

  const manoInventoryQuery = useQuery({
    queryKey: ['mano', 'vim-inventory', manoSelectedNsId],
    queryFn: async () => (await manoAPI.vimInventory(manoSelectedNsId ? { ns_instance_id: manoSelectedNsId } : undefined)).data as any,
    enabled: activeTab === 'mano',
    retry: false,
    refetchInterval: 5000,
  })

  const upsertNsdMutation = useMutation({
    mutationFn: async () => {
      const parsed = kvRowsToObject(manoNsdOptionRows)
      if (parsed.errors.length) throw new Error(parsed.errors.join('; '))
      const descriptor = { topology_id: (manoNsdTopologyId || '').trim(), options: parsed.obj }
      const res = await manoAPI.upsertNsd({ id: manoSelectedNsdId || undefined, name: manoNsdName, version: '1.0', descriptor })
      return res.data as any
    },
    onSuccess: () => {
      toast.success('NSD saved')
      manoNsdsQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Failed'),
  })

  const upsertVnfdMutation = useMutation({
    mutationFn: async () => {
      const parsed = kvRowsToObject(manoVnfdDefaultsRows)
      if (parsed.errors.length) throw new Error(parsed.errors.join('; '))
      const descriptor = { device_type: (manoVnfdDeviceType || '').trim(), default_properties: parsed.obj }
      const res = await manoAPI.upsertVnfd({ id: manoSelectedVnfdId || undefined, name: manoVnfdName, version: '1.0', descriptor })
      return res.data as any
    },
    onSuccess: () => {
      toast.success('VNFD saved')
      manoVnfdsQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Failed'),
  })

  const createNsMutation = useMutation({
    mutationFn: async () => {
      const payload: any = {
        name: manoNsName,
        dry_run: manoNsDryRun,
        backend: manoNsBackend,
      }
      if (manoNsBackend === 'osm') {
        payload.topology_id = topologyId || null
        payload.nsd_id = (manoOsmNsdId || '').trim() || null
        payload.options = { vim_account_id: (manoOsmVimAccountId || '').trim() || undefined }
      } else {
        payload.topology_id = topologyId || null
        payload.nsd_id = manoSelectedNsdId || null
      }
      const res = await manoAPI.createNsInstance(payload)
      return res.data as any
    },
    onSuccess: (data) => {
      toast.success('NS instance created')
      manoNsInstancesQuery.refetch()
      if (data?.id) setManoSelectedNsId(String(data.id))
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Failed'),
  })

  const terminateNsMutation = useMutation({
    mutationFn: async (nsId: string) => (await manoAPI.terminateNsInstance(nsId, { reason: 'terminated from UI' })).data,
    onSuccess: () => {
      toast.success('Terminate requested')
      manoNsInstancesQuery.refetch()
      manoOpsQuery.refetch()
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Failed'),
  })

  const createVnfMutation = useMutation({
    mutationFn: async () => {
      const parsed = kvRowsToObject(manoVnfPropsRows)
      if (parsed.errors.length) throw new Error(parsed.errors.join('; '))
      const properties = parsed.obj
      const res = await manoAPI.createVnf({
        ns_instance_id: manoSelectedNsId,
        name: manoVnfName,
        device_type: manoVnfDeviceType,
        vnfd_id: manoSelectedVnfdId || null,
        properties,
        dry_run: manoVnfDryRun,
      })
      return res.data as any
    },
    onSuccess: (data) => {
      toast.success('VNF created')
      manoVnfsQuery.refetch()
      if (data?.id) setManoSelectedVnfId(String(data.id))
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Failed'),
  })

  const execVnfMutation = useMutation({
    mutationFn: async () => (await manoAPI.execVnf(manoSelectedVnfId, { command: manoExecCommand })).data,
    onSuccess: () => toast.success('Command executed'),
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Failed'),
  })

  const deleteVnfMutation = useMutation({
    mutationFn: async ({ vnfId, force }: { vnfId: string; force?: boolean }) =>
      (await manoAPI.deleteVnf(vnfId, { force: !!force })).data as any,
    onSuccess: (_data, vars) => {
      toast.success('VNF deleted')
      manoVnfsQuery.refetch()
      if (String(manoSelectedVnfId) === String(vars.vnfId)) setManoSelectedVnfId('')
    },
    onError: (e: any) => toast.error(e?.response?.data?.detail || e?.message || 'Delete failed'),
  })

  const appendControllerConsole = (lines: string[]) => {
    setControllerConsole((prev) => {
      const next = [...prev, ...lines]
      return next.length > 500 ? next.slice(next.length - 500) : next
    })
  }

  const { data: infraCredentials } = useQuery({
    queryKey: ['infra-credentials', topologyId],
    queryFn: async () => {
      if (!topologyId) throw new Error('No topology ID')
      const res = await infrastructureAPI.topologyInfraCredentials(topologyId)
      return res.data
    },
    enabled: !!topologyId,
    retry: false,
    refetchInterval: 15000,
  })

  const { data: infraStatus } = useQuery({
    queryKey: ['infra-status', topologyId],
    queryFn: async () => {
      if (!topologyId) throw new Error('No topology ID')
      const res = await infrastructureAPI.topologyInfraStatus(topologyId)
      return res.data
    },
    enabled: activeTab === 'controllers' && !!topologyId,
    retry: false,
    refetchInterval: 5000,
  })

  const topologyExportQuery = useQuery({
    queryKey: ['topology-export-script', topologyId, topologyExportFormat],
    queryFn: async () => {
      if (!topologyId) throw new Error('No topology ID')
      const res = await topologiesAPI.export(topologyId, topologyExportFormat)
      return res.data as { content: string; filename: string; format: string; timestamp?: string }
    },
    enabled: activeTab === 'topology-export' && !!topologyId,
    retry: false,
  })

  const algoParamsPreview = useMemo(() => {
    const trimmed = (algoParamsText || '').trim()
    if (!trimmed) return { data: {} as any, error: '' }
    try {
      return { data: JSON.parse(trimmed), error: '' }
    } catch (e: any) {
      return { data: null as any, error: e?.message || 'Invalid JSON' }
    }
  }, [algoParamsText])

  const startAlgoMutation = useMutation({
    mutationFn: async () => {
      if (!topologyId) throw new Error('No topology ID')
      if (!isRunning) throw new Error('Start the emulation first')
      const manifest = (algoManifestText || '').trim()
      if (!manifest) throw new Error('Manifest JSON required')
      if (algoParamsPreview.error) throw new Error(`Params JSON invalid: ${algoParamsPreview.error}`)
      const mergedParams: any = { ...(algoParamsPreview.data || {}) }
      mergedParams.trace_messages = !!algoTraceMessagesEnabled
      mergedParams.trace_payload = !!algoTracePayloadEnabled
      return algorithmsAPI.startRun({
        topology_id: topologyId,
        transport: algoTransport,
        listen_port: algoListenPort,
        params: mergedParams,
        manifest_json: manifest,
        source_code: algoSourceCode || '',
      })
    },
    onSuccess: (res: any) => {
      const runId = res?.data?.run_id
      if (runId) {
        setAlgoRunId(runId)
        setAlgoMetricsBaseline(null)
        if (topologyId) {
          void (async () => {
            try {
              const m = await monitoringAPI.topologyMetrics(topologyId)
              const d: any = m.data
              setAlgoMetricsBaseline({
                total_rx_packets: Number(d?.total_rx_packets || 0),
                total_tx_packets: Number(d?.total_tx_packets || 0),
                total_rx_bytes: Number(d?.total_rx_bytes || 0),
                total_tx_bytes: Number(d?.total_tx_bytes || 0),
              })
            } catch {
              // best-effort
            }
          })()
        }
        toast.success(`Algorithm started: ${runId.slice(0, 8)}`)
      } else {
        toast.success('Algorithm started')
      }
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to start algorithm')
    },
  })

  const stopAlgoMutation = useMutation({
    mutationFn: async () => {
      if (!algoRunId) throw new Error('No run')
      return algorithmsAPI.stopRun(algoRunId)
    },
    onSuccess: () => {
      toast.success('Algorithm stopped')
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to stop algorithm')
    },
  })

  const algoRunQuery = useQuery({
    queryKey: ['algorithm-run', algoRunId],
    queryFn: async () => {
      if (!algoRunId) return null
      const res = await algorithmsAPI.getRun(algoRunId)
      return res.data
    },
    enabled: !!algoRunId,
    refetchInterval: (data: any) => (String(data?.status || '').toLowerCase() === 'stopped' ? false : 2000),
  })

  const algoRunStatus = String(algoRunQuery.data?.status || '').toLowerCase()
  const algoRunIsStopped = algoRunStatus === 'stopped'
  const algoRunDurationLabel = useMemo(() => {
    const created = Number((algoRunQuery.data as any)?.created_at)
    if (!Number.isFinite(created) || created <= 0) return ''
    const stopped = Number((algoRunQuery.data as any)?.stopped_at)
    const end = Number.isFinite(stopped) && stopped > 0 ? stopped : Date.now() / 1000
    const seconds = Math.max(0, end - created)
    if (!Number.isFinite(seconds)) return ''
    if (seconds < 60) return `${seconds.toFixed(1)}s`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
  }, [algoRunQuery.data])

  const algoIdToNodeIdMap = useMemo(() => {
    const rec: any = algoRunQuery.data
    const raw = rec?.algo_id_to_node_id && typeof rec.algo_id_to_node_id === 'object' ? rec.algo_id_to_node_id : {}
    const out = new Map<number, string>()
    for (const [k, v] of Object.entries(raw)) {
      const aid = Number(k)
      if (!Number.isFinite(aid)) continue
      const nodeId = String(v || '')
      if (nodeId) out.set(aid, nodeId)
    }
    return out
  }, [algoRunQuery.data])

  const formatAlgoNodeLabel = (algoId: any) => {
    const idNum = Number(algoId)
    if (!Number.isFinite(idNum)) return String(algoId ?? '—')
    const nodeId = algoIdToNodeIdMap.get(idNum) || ''
    const short = nodeId ? nodeId.slice(0, 8) : ''
    return short ? `#${idNum} • ${short}` : `#${idNum}`
  }

  const algoEventsQuery = useQuery({
    queryKey: ['algorithm-events', algoRunId],
    queryFn: async () => {
      if (!algoRunId) return { events: [] as any[] }
      const res = await algorithmsAPI.events(algoRunId, { tail: 200 })
      return res.data
    },
    enabled: !!algoRunId,
    refetchInterval: algoRunIsStopped || !algoLiveUpdatesEnabled ? false : 2000,
  })

  const { data: algoOverlayData } = useQuery({
    queryKey: ['network-manager-algorithm-overlay', topologyId, algoRunId],
    queryFn: async () => {
      if (!topologyId || !algoRunId) return { overlays: {} as Record<string, any> }
      const res = await algorithmsAPI.overlay(topologyId, { run_id: algoRunId })
      return res.data as any
    },
    enabled: activeTab === 'algorithms' && !!topologyId && !!algoRunId,
    refetchInterval: algoRunIsStopped || !algoLiveUpdatesEnabled ? false : 1500,
    retry: false,
  })

  useEffect(() => {
    const overlays = algoOverlayData?.overlays && typeof algoOverlayData.overlays === 'object' ? algoOverlayData.overlays : {}
    setAlgoOverlayById(overlays)
  }, [algoOverlayData])

  const algoValidateQuery = useQuery({
    queryKey: ['network-manager-algorithm-validate', algoRunId],
    queryFn: async () => {
      if (!algoRunId) return null
      const res = await algorithmsAPI.validate(algoRunId)
      return res.data as any
    },
    enabled: !!algoRunId && String(algoRunQuery.data?.status || '').toLowerCase() === 'stopped',
    refetchInterval: false,
    retry: false,
  })

  const algoTopologyMetricsQuery = useQuery({
    queryKey: ['network-manager-algorithm-topology-metrics', topologyId, algoRunId],
    queryFn: async () => {
      if (!topologyId) return null
      const res = await monitoringAPI.topologyMetrics(topologyId)
      return res.data as any
    },
    enabled: activeTab === 'algorithms' && !!topologyId && !!algoRunId,
    refetchInterval: algoRunIsStopped || !algoLiveUpdatesEnabled ? false : 2000,
    retry: false,
  })

  const algoTopologyMetrics = algoTopologyMetricsQuery.data as any

  useEffect(() => {
    if (activeTab !== 'algorithms') return
    if (!topologyId || !algoRunId) return
    if (!algoRunIsStopped) return
    void algoTopologyMetricsQuery.refetch()
  }, [activeTab, topologyId, algoRunId, algoRunIsStopped, algoTopologyMetricsQuery])

  useEffect(() => {
    if (!algoRunId) return
    if (!algoTopologyMetrics) return
    if (algoMetricsBaseline) return
    setAlgoMetricsBaseline({
      total_rx_packets: Number(algoTopologyMetrics?.total_rx_packets || 0),
      total_tx_packets: Number(algoTopologyMetrics?.total_tx_packets || 0),
      total_rx_bytes: Number(algoTopologyMetrics?.total_rx_bytes || 0),
      total_tx_bytes: Number(algoTopologyMetrics?.total_tx_bytes || 0),
    })
  }, [algoRunId, algoTopologyMetrics, algoMetricsBaseline])

  const algoMetricsDelta = useMemo(() => {
    if (!algoTopologyMetrics || !algoMetricsBaseline) return null
    const rxP = Number(algoTopologyMetrics?.total_rx_packets || 0) - Number(algoMetricsBaseline.total_rx_packets || 0)
    const txP = Number(algoTopologyMetrics?.total_tx_packets || 0) - Number(algoMetricsBaseline.total_tx_packets || 0)
    const rxB = Number(algoTopologyMetrics?.total_rx_bytes || 0) - Number(algoMetricsBaseline.total_rx_bytes || 0)
    const txB = Number(algoTopologyMetrics?.total_tx_bytes || 0) - Number(algoMetricsBaseline.total_tx_bytes || 0)
    return { rxP, txP, rxB, txB, totalPackets: rxP + txP, totalBytes: rxB + txB }
  }, [algoTopologyMetrics, algoMetricsBaseline])

  useEffect(() => {
    setAlgoNetSeries([])
    setAlgoEventsTab('table')
    setAlgoEventsView('messages')
    setAlgoEventNodeFilter('all')
    setAlgoEventTypeFilter('all')
    setAlgoSelectedEventKey('')
    setAlgoMsgDirFilter('all')
    setAlgoMsgLocalNodeFilter('all')
    setAlgoMsgPeerFilter('all')
    setAlgoMsgTypeFilter('all')
    setAlgoNodeSearch('')
  }, [algoRunId])

  useEffect(() => {
    if (activeTab !== 'algorithms') return
    if (!algoRunId) return
    if (algoRunIsStopped) return
    if (!algoMetricsDelta) return
    setAlgoNetSeries((prev) => {
      const next = [
        ...prev,
        {
          ts: new Date().toLocaleTimeString(),
          packetsDelta: Number(algoMetricsDelta.totalPackets || 0),
          bytesDelta: Number(algoMetricsDelta.totalBytes || 0),
          rxPacketsDelta: Number(algoMetricsDelta.rxP || 0),
          txPacketsDelta: Number(algoMetricsDelta.txP || 0),
        },
      ]
      return next.length > 90 ? next.slice(next.length - 90) : next
    })
  }, [activeTab, algoRunId, algoRunIsStopped, algoMetricsDelta])

  const algoEvents = useMemo(() => {
    const ev = (algoEventsQuery.data as any)?.events
    return Array.isArray(ev) ? ev : []
  }, [algoEventsQuery.data])

  const algoNetEvents = useMemo(() => {
    return algoEvents.filter((e: any) => {
      const t = String(e?.type || '').toLowerCase()
      return t === 'net_tx' || t === 'net_rx' || t === 'net_bcast'
    })
  }, [algoEvents])

  const algoSystemEvents = useMemo(() => {
    return algoEvents.filter((e: any) => {
      const t = String(e?.type || '').toLowerCase()
      return !(t === 'net_tx' || t === 'net_rx' || t === 'net_bcast')
    })
  }, [algoEvents])

  const algoEventTypeCounts = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const e of algoEvents) {
      const t = String(e?.type || 'unknown')
      counts[t] = (counts[t] || 0) + 1
    }
    return counts
  }, [algoEvents])

  const algoHasWsnMetrics = useMemo(() => {
    return !!(
      algoEventTypeCounts['round_metrics'] ||
      algoEventTypeCounts['simulation_complete'] ||
      algoEventTypeCounts['fnd'] ||
      algoEventTypeCounts['hnd'] ||
      algoEventTypeCounts['lnd']
    )
  }, [algoEventTypeCounts])

  const algoMsgPeers = useMemo(() => {
    const peers = new Set<number>()
    for (const e of algoNetEvents as any[]) {
      const t = String(e?.type || '').toLowerCase()
      if (t === 'net_tx' && Number.isFinite(Number(e?.to))) peers.add(Number(e.to))
      if (t === 'net_rx' && Number.isFinite(Number(e?.from))) peers.add(Number(e.from))
    }
    return Array.from(peers.values()).sort((a, b) => a - b)
  }, [algoNetEvents])

  const algoMsgCounts = useMemo(() => {
    let tx = 0
    let rx = 0
    let bcast = 0
    for (const e of algoNetEvents as any[]) {
      const t = String(e?.type || '').toLowerCase()
      if (t === 'net_tx') tx += 1
      else if (t === 'net_rx') rx += 1
      else if (t === 'net_bcast') bcast += 1
    }
    return { tx, rx, bcast, total: tx + rx + bcast }
  }, [algoNetEvents])

  const algoMsgTypes = useMemo(() => {
    const types = new Set<string>()
    for (const e of algoNetEvents as any[]) {
      const mt = String(e?.msg_type || '').trim()
      if (mt) types.add(mt)
    }
    return Array.from(types.values()).sort()
  }, [algoNetEvents])

  const algoFilteredMessageEvents = useMemo(() => {
    const dir = (algoMsgDirFilter || 'all').trim().toLowerCase()
    const local = (algoMsgLocalNodeFilter || 'all').trim().toLowerCase()
    const peer = (algoMsgPeerFilter || 'all').trim().toLowerCase()
    const typ = (algoMsgTypeFilter || 'all').trim().toLowerCase()
    return (algoNetEvents as any[]).filter((e) => {
      const t = String(e?.type || '').toLowerCase()
      if (dir !== 'all') {
        if (dir === 'tx' && t !== 'net_tx') return false
        if (dir === 'rx' && t !== 'net_rx') return false
        if (dir === 'bcast' && t !== 'net_bcast') return false
      }
      if (local !== 'all' && String(e?.node ?? '').toLowerCase() !== local) return false

      const other = t === 'net_tx' ? e?.to : t === 'net_rx' ? e?.from : null
      if (peer !== 'all' && String(other ?? '').toLowerCase() !== peer) return false

      if (typ !== 'all' && String(e?.msg_type ?? '').toLowerCase() !== typ) return false
      return true
    })
  }, [algoNetEvents, algoMsgDirFilter, algoMsgLocalNodeFilter, algoMsgPeerFilter, algoMsgTypeFilter])

  const algoMessageRows = useMemo(() => {
    const tail = (algoFilteredMessageEvents as any[]).slice(-400)
    const createdAt = Number((algoRunQuery.data as any)?.created_at)
    return tail.map((e, idx) => {
      const t = String(e?.type || '').toLowerCase()
      const localNode = formatAlgoNodeLabel(e?.node)
      const msgType = String(e?.msg_type || 'msg')
      const bytes = e?.bytes != null ? Number(e.bytes) : null
      const payload = e?.payload && typeof e.payload === 'object' ? e.payload : null
      const color = payload?.color ?? payload?.overlay?.badge ?? null

      const other = t === 'net_tx' ? e?.to : t === 'net_rx' ? e?.from : null
      const otherLabel = other == null ? (t === 'net_bcast' ? 'BROADCAST' : '—') : formatAlgoNodeLabel(other)
      const endpoint =
        t === 'net_tx'
          ? `${String(e?.dst_ip || '—')}:${String(e?.dst_port ?? '—')}`
          : t === 'net_rx'
            ? `${String(e?.src_ip || '—')}:${String(e?.src_port ?? '—')}`
            : `:${String(e?.dst_port ?? '—')}`

      const rawTs = Number(e?.ts)
      const elapsed = Number.isFinite(createdAt) && Number.isFinite(rawTs) ? rawTs - createdAt : null
      return {
        key: `${String(e?.ts ?? idx)}-${t}-${String(e?.node ?? '')}-${String(e?.msg_type ?? '')}-${String(other ?? '')}-${String(bytes ?? '')}`,
        ts: formatAlgoTs(e?.ts),
        elapsed: elapsed == null ? '' : `+${elapsed.toFixed(3)}s`,
        type: t,
        node: e?.node ?? '—',
        localNode,
        other: other ?? null,
        otherLabel,
        msgType,
        bytes,
        color: color ? String(color).toUpperCase() : '',
        endpoint,
        raw: e,
      }
    })
  }, [algoFilteredMessageEvents, algoRunQuery.data, algoIdToNodeIdMap])

  const algoFilteredEvents = useMemo(() => {
    const nodeFilter = (algoEventNodeFilter || 'all').trim().toLowerCase()
    const typeFilter = (algoEventTypeFilter || 'all').trim().toLowerCase()
    return algoSystemEvents.filter((e: any) => {
      if (nodeFilter !== 'all' && String(e?.node ?? '').toLowerCase() !== nodeFilter) return false
      if (typeFilter !== 'all' && String(e?.type ?? '').toLowerCase() !== typeFilter) return false
      return true
    })
  }, [algoSystemEvents, algoEventNodeFilter, algoEventTypeFilter])

  const algoEventRows = useMemo(() => {
    const tail = algoFilteredEvents.slice(-200)
    return tail.map((e: any, idx: number) => {
      const typ = String(e?.type || 'unknown')
      const node = e?.node
      const msgId = e?.msg_id ? String(e.msg_id) : ''
      let summary = ''
      if (typ === 'neighbors') summary = `neighbors=${e?.count ?? (Array.isArray(e?.neighbors) ? e.neighbors.length : '—')}`
      else if (typ === 'overlay') summary = `color=${String(e?.color || e?.overlay?.badge || '').toUpperCase() || '—'}`
      else if (typ === 'started') summary = `${String(e?.manifest?.name || '').trim() || 'algorithm'} • ${String(e?.transport || '').toUpperCase() || '—'}:${String(e?.listen_port ?? '') || '—'}`
      else if (typ === 'done') {
        const s = e?.stats && typeof e.stats === 'object' ? e.stats : null
        const parts: string[] = []
        if (e?.reason) parts.push(`reason=${e.reason}`)
        if (s?.sent_msgs != null) parts.push(`sent=${s.sent_msgs}`)
        if (s?.recv_msgs != null) parts.push(`recv=${s.recv_msgs}`)
        summary = parts.length ? parts.join(' • ') : 'done'
      }
      else if (typ === 'error') summary = String(e?.error || '')
      else if (typ === 'net_tx') {
        const to = e?.to == null ? 'addr' : formatAlgoNodeLabel(e.to)
        const mt = String(e?.msg_type || 'msg')
        const b = e?.bytes != null ? `${e.bytes}B` : ''
        const payload = e?.payload && typeof e.payload === 'object' ? e.payload : null
        const c = payload?.color ?? payload?.overlay?.badge
        const ep = e?.dst_ip ? `${String(e.dst_ip)}:${String(e?.dst_port ?? '—')}` : ''
        summary = `TX → ${to} • ${mt}${c ? ` • color=${String(c).toUpperCase()}` : ''}${b ? ` • ${b}` : ''}${ep ? ` • ${ep}` : ''}`
      }
      else if (typ === 'net_rx') {
        const from = e?.from != null ? formatAlgoNodeLabel(e.from) : 'unknown'
        const mt = String(e?.msg_type || 'msg')
        const b = e?.bytes != null ? `${e.bytes}B` : ''
        const payload = e?.payload && typeof e.payload === 'object' ? e.payload : null
        const c = payload?.color ?? payload?.overlay?.badge
        const ep = e?.src_ip ? `${String(e.src_ip)}:${String(e?.src_port ?? '—')}` : ''
        summary = `RX ← ${from} • ${mt}${c ? ` • color=${String(c).toUpperCase()}` : ''}${b ? ` • ${b}` : ''}${ep ? ` • ${ep}` : ''}`
      }
      else if (typ === 'net_bcast') {
        const mt = String(e?.msg_type || 'msg')
        const b = e?.bytes != null ? `${e.bytes}B` : ''
        const ep = e?.dst_port != null ? `:${String(e.dst_port)}` : ''
        summary = `BCAST • ${mt}${b ? ` • ${b}` : ''}${ep ? ` • ${ep}` : ''}`
      }
      else if (typ === 'result') {
        const parts: string[] = []
        if (e?.nodes_seen != null) parts.push(`nodes=${e.nodes_seen}`)
        if (e?.edges != null) parts.push(`edges=${e.edges}`)
        if (e?.cover_size != null) parts.push(`cover=${e.cover_size}`)
        if (e?.connected != null) parts.push(`connected=${String(e.connected)}`)
        summary = parts.join(' • ')
      }
      else if (typ === 'connectivity') {
        const parts: string[] = []
        if (e?.final_connected != null) parts.push(`connected=${String(e.final_connected)}`)
        if (e?.unassigned_edges != null) parts.push(`unassigned=${e.unassigned_edges}`)
        if (e?.assigned_edges != null) parts.push(`assigned=${e.assigned_edges}`)
        summary = parts.join(' • ')
      }
      else if (typ === 'leader') summary = `leader=${String(e?.leader_id ?? '—')}`
      else if (typ === 'tree') summary = `leader=${String(e?.leader_id ?? '—')} • dist=${String(e?.dist ?? '—')} • parent=${String(e?.parent ?? '—')}`
      else if (typ === 'req_info') summary = `k=${String(e?.k ?? '—')} • seed=${String(e?.seed ?? '—')}`
      else if (typ === 'sent_info') summary = `to=${String(e?.to ?? '—')}`
      else if (typ === 'history') {
        const parts: string[] = []
        if (e?.iteration != null) parts.push(`iter=${e.iteration}`)
        if (e?.selected_black != null) parts.push(`black=${e.selected_black}`)
        if (e?.node_type) parts.push(`type=${String(e.node_type)}`)
        if (e?.edges_covered_this_iteration != null) parts.push(`+edges=${e.edges_covered_this_iteration}`)
        if (e?.remaining_uncovered_edges != null) parts.push(`left=${e.remaining_uncovered_edges}`)
        summary = parts.join(' • ')
      }

      if (!summary) {
        // Generic fallback: surface a few small fields so the table stays informative
        const maybePairs: Array<[string, any]> = [
          ['color', e?.color ?? e?.overlay?.badge],
          ['msg', e?.msg_id],
          ['reason', e?.reason],
          ['k', e?.k],
          ['seed', e?.seed],
          ['round', e?.round_no ?? e?.round],
          ['priority', e?.priority],
          ['leader', e?.leader_id],
          ['dist', e?.dist],
          ['parent', e?.parent],
          ['to', e?.to],
        ]
        const parts = maybePairs
          .filter(([, v]) => v != null && String(v) !== '')
          .slice(0, 4)
          .map(([k, v]) => `${k}=${String(v)}`)

        const s = e?.stats && typeof e.stats === 'object' ? e.stats : null
        if (s && parts.length < 4) {
          if (s?.sent_msgs != null) parts.push(`sent=${s.sent_msgs}`)
          if (s?.broadcast_msgs != null) parts.push(`bcast=${s.broadcast_msgs}`)
          if (s?.recv_msgs != null) parts.push(`recv=${s.recv_msgs}`)
        }
        summary = parts.join(' • ')
      }

      const runCreatedAt = Number((algoRunQuery.data as any)?.created_at)
      const t = Number(e?.ts)
      const elapsed = Number.isFinite(runCreatedAt) && Number.isFinite(t) ? t - runCreatedAt : null
      return {
        key: `${String(e?.ts ?? idx)}-${typ}-${String(node ?? '')}-${msgId}`,
        ts: formatAlgoTs(e?.ts),
        elapsed: elapsed == null ? '' : `+${elapsed.toFixed(3)}s`,
        type: typ,
        node: node ?? '—',
        summary,
        raw: e,
      }
    })
  }, [algoFilteredEvents, algoRunQuery.data])

  const algoVisibleRows = useMemo(() => {
    return algoEventsView === 'messages' ? algoMessageRows : algoEventRows
  }, [algoEventsView, algoMessageRows, algoEventRows])

  const algoSelectedEventRow = useMemo(() => {
    if (!algoSelectedEventKey) return algoVisibleRows.length ? algoVisibleRows[algoVisibleRows.length - 1] : null
    return algoVisibleRows.find((r) => r.key === algoSelectedEventKey) || null
  }, [algoVisibleRows, algoSelectedEventKey])

  const handleCopySelectedAlgoEvent = async () => {
    if (!algoSelectedEventRow?.raw) {
      toast.error('No event selected')
      return
    }
    try {
      await navigator.clipboard.writeText(JSON.stringify(algoSelectedEventRow.raw, null, 2))
      toast.success('Copied')
    } catch (e: any) {
      toast.error(e?.message || 'Copy failed')
    }
  }

  const algoEventsText = useMemo(() => {
    const base = algoEventsView === 'messages' ? (algoFilteredMessageEvents as any[]) : (algoFilteredEvents as any[])
    return JSON.stringify((base || []).slice(-200), null, 2)
  }, [algoEventsView, algoFilteredMessageEvents, algoFilteredEvents])

  const algoGraphNodes: Node[] = useMemo(() => {
    const rec: any = algoRunQuery.data
    const rawMap = rec?.algo_id_to_node_id && typeof rec.algo_id_to_node_id === 'object' ? rec.algo_id_to_node_id : {}
    const ids = Object.keys(rawMap)
      .map((k) => Number(k))
      .filter((n) => Number.isFinite(n))
      .sort((a, b) => a - b)
    if (!ids.length) return []

    const n = ids.length
    const radius = Math.max(180, Math.min(340, 60 * n))
    return ids.map((algoId, idx) => {
      const nodeId = String(rawMap[String(algoId)] ?? rawMap[algoId] ?? '')
      const overlay = nodeId ? algoOverlayById[nodeId] : undefined
      const started = Array.isArray(rec?.started_nodes) && rec.started_nodes.includes(algoId)
      const skipped = Array.isArray(rec?.skipped_nodes) && rec.skipped_nodes.includes(algoId)
      const angle = (Math.PI * 2 * idx) / n
      const label = nodeId ? `#${algoId} • ${nodeId}` : `#${algoId}`
      return {
        id: String(algoId),
        type: 'device',
        position: { x: Math.cos(angle) * radius, y: Math.sin(angle) * radius },
        data: {
          label,
          deviceType: guessDeviceTypeFromNodeId(nodeId),
          properties: {},
          overlay,
          algoStarted: started,
          algoSkipped: skipped,
        },
      }
    })
  }, [algoRunQuery.data, algoOverlayById])

  const algoGraphEdges: Edge[] = useMemo(() => {
    const rec: any = algoRunQuery.data
    const rawMap = rec?.algo_id_to_node_id && typeof rec.algo_id_to_node_id === 'object' ? rec.algo_id_to_node_id : {}
    const ids = new Set(
      Object.keys(rawMap)
        .map((k) => Number(k))
        .filter((n) => Number.isFinite(n))
    )
    const edges = new Map<string, Edge>()
    for (const e of algoEvents) {
      if (String(e?.type || '').toLowerCase() !== 'neighbors') continue
      const src = Number(e?.node)
      if (!Number.isFinite(src) || !ids.has(src)) continue
      const neighbors = Array.isArray(e?.neighbors) ? e.neighbors : []
      for (const nb of neighbors) {
        const dst = Number(nb)
        if (!Number.isFinite(dst) || !ids.has(dst) || dst === src) continue
        const a = Math.min(src, dst)
        const b = Math.max(src, dst)
        const id = `${a}-${b}`
        if (edges.has(id)) continue
        edges.set(id, {
          id,
          source: String(a),
          target: String(b),
          type: 'smoothstep',
          animated: false,
          style: { stroke: '#94a3b8', strokeWidth: 2 },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#94a3b8', width: 16, height: 16 },
        })
      }
    }
    return Array.from(edges.values())
  }, [algoRunQuery.data, algoEvents])

  const algoNodeTableRows = useMemo(() => {
    const rec: any = algoRunQuery.data
    const rawMap = rec?.algo_id_to_node_id && typeof rec.algo_id_to_node_id === 'object' ? rec.algo_id_to_node_id : {}
    const started = new Set<number>(Array.isArray(rec?.started_nodes) ? rec.started_nodes : [])
    const skipped = new Set<number>(Array.isArray(rec?.skipped_nodes) ? rec.skipped_nodes : [])

    const lastNeighbors: Record<number, number> = {}
    const lastDoneStats: Record<number, any> = {}
    for (const e of algoEvents) {
      const typ = String(e?.type || '').toLowerCase()
      const src = Number(e?.node)
      if (!Number.isFinite(src)) continue
      if (typ === 'neighbors') {
        const c = Number(e?.count ?? (Array.isArray(e?.neighbors) ? e.neighbors.length : 0))
        lastNeighbors[src] = Number.isFinite(c) ? c : 0
      }
      if (typ === 'done' && e?.stats && typeof e.stats === 'object') {
        lastDoneStats[src] = e.stats
      }
    }

    const ids = Object.keys(rawMap)
      .map((k) => Number(k))
      .filter((n) => Number.isFinite(n))
      .sort((a, b) => a - b)

    return ids.map((algoId) => {
      const nodeId = String(rawMap[String(algoId)] ?? rawMap[algoId] ?? '')
      const overlay = nodeId ? (algoOverlayById[nodeId] as any) : null
      const color = String(overlay?.badge || '').toUpperCase() || '—'
      const stats = lastDoneStats[algoId] || {}
      const outMsgs = Number(stats?.sent_msgs || 0) + Number(stats?.broadcast_msgs || 0)
      const inMsgs = Number(stats?.recv_msgs || 0)
      return {
        algoId,
        nodeId: nodeId || '—',
        status: skipped.has(algoId) ? 'skipped' : started.has(algoId) ? 'started' : '—',
        color,
        neighbors: lastNeighbors[algoId] ?? '—',
        outMsgs: Number.isFinite(outMsgs) ? outMsgs : '—',
        inMsgs: Number.isFinite(inMsgs) ? inMsgs : '—',
      }
    })
  }, [algoRunQuery.data, algoOverlayById, algoEvents])

  const algoNodeTableRowsFiltered = useMemo(() => {
    const q = String(algoNodeSearch || '').trim().toLowerCase()
    if (!q) return algoNodeTableRows
    return algoNodeTableRows.filter((r: any) => {
      const algoId = String(r?.algoId ?? '').toLowerCase()
      const nodeId = String(r?.nodeId ?? '').toLowerCase()
      const status = String(r?.status ?? '').toLowerCase()
      const color = String(r?.color ?? '').toLowerCase()
      return algoId.includes(q) || nodeId.includes(q) || status.includes(q) || color.includes(q)
    })
  }, [algoNodeTableRows, algoNodeSearch])

  const algoMessageTotals = useMemo(() => {
    let out = 0
    let inn = 0
    for (const r of algoNodeTableRows as any[]) {
      const o = Number(r?.outMsgs)
      const i = Number(r?.inMsgs)
      if (Number.isFinite(o)) out += o
      if (Number.isFinite(i)) inn += i
    }
    return { out, in: inn }
  }, [algoNodeTableRows])

  const { data: algoHistoryRuns } = useQuery({
    queryKey: ['algorithm-history-runs', topologyId, algoHistoryWindowMinutes, algoHistoryAlgorithmFilter],
    queryFn: async () => {
      if (!topologyId) return { runs: [] as any[] }
      const alg = (algoHistoryAlgorithmFilter || '').trim()
      const res = await monitoringAPI.algorithmRuns(topologyId, {
        window_minutes: algoHistoryWindowMinutes,
        algorithm: alg ? alg : undefined,
      })
      return res.data as any
    },
    enabled: activeTab === 'algorithms' && algoUiTab === 'history' && !!topologyId,
    refetchInterval: 15000,
    retry: false,
  })

  useEffect(() => {
    if (activeTab !== 'algorithms' || algoUiTab !== 'history') return
    const runs = (algoHistoryRuns as any)?.runs
    if (!Array.isArray(runs) || !runs.length) return
    if (algoHistorySelectedRunId) return
    setAlgoHistorySelectedRunId(String(runs[0].run_id || ''))
  }, [activeTab, algoUiTab, algoHistoryRuns, algoHistorySelectedRunId])

  const { data: algoHistoryNodes } = useQuery({
    queryKey: ['algorithm-history-nodes', topologyId, algoHistorySelectedRunId],
    queryFn: async () => {
      if (!topologyId || !algoHistorySelectedRunId) return { nodes: [] as any[] }
      const res = await monitoringAPI.algorithmRunNodes(topologyId, algoHistorySelectedRunId, { window_minutes: 14 * 24 * 60 })
      return res.data as any
    },
    enabled: activeTab === 'algorithms' && algoUiTab === 'history' && !!topologyId && !!algoHistorySelectedRunId,
    refetchInterval: 15000,
    retry: false,
  })

  const { data: algoHistorySummary } = useQuery({
    queryKey: ['algorithm-history-summary', topologyId, algoHistorySelectedRunId],
    queryFn: async () => {
      if (!topologyId || !algoHistorySelectedRunId) return null
      const res = await monitoringAPI.algorithmRunSummary(topologyId, algoHistorySelectedRunId, { window_minutes: 90 * 24 * 60 })
      return res.data as any
    },
    enabled: activeTab === 'algorithms' && algoUiTab === 'history' && !!topologyId && !!algoHistorySelectedRunId,
    refetchInterval: 15000,
    retry: false,
  })

  const algoHistoryRunsList = useMemo(() => {
    const runs = (algoHistoryRuns as any)?.runs
    return Array.isArray(runs) ? (runs as any[]) : []
  }, [algoHistoryRuns])

  const algoHistoryRunById = useMemo(() => {
    const m = new Map<string, any>()
    for (const r of algoHistoryRunsList) {
      const rid = String(r?.run_id || '').trim()
      if (rid) m.set(rid, r)
    }
    return m
  }, [algoHistoryRunsList])

  const algoHistoryCompareRunIdsNormalized = useMemo(() => {
    const uniq = Array.from(new Set((algoHistoryCompareRunIds || []).map((r) => String(r || '').trim()).filter(Boolean)))
    uniq.sort((a, b) => (a < b ? -1 : a > b ? 1 : 0))
    return uniq.slice(0, 8)
  }, [algoHistoryCompareRunIds])

  const toggleAlgoHistoryCompareRun = (runIdRaw: string) => {
    const rid = String(runIdRaw || '').trim()
    if (!rid) return
    setAlgoHistoryCompareRunIds((prev) => {
      const set = new Set((prev || []).map((x) => String(x || '').trim()).filter(Boolean))
      if (set.has(rid)) {
        set.delete(rid)
        return Array.from(set.values())
      }
      if (set.size >= 8) {
        toast.error('Select at most 8 runs to compare')
        return Array.from(set.values())
      }
      set.add(rid)
      return Array.from(set.values())
    })
  }

  const { data: algoHistoryCompareSummaries, isFetching: algoHistoryCompareSummariesLoading } = useQuery({
    queryKey: ['algorithm-history-compare-summaries', topologyId, algoHistoryCompareRunIdsNormalized.join(',')],
    queryFn: async () => {
      if (!topologyId || !algoHistoryCompareRunIdsNormalized.length) return { items: [] as any[] }
      const windowMinutes = 90 * 24 * 60
      const results = await Promise.all(
        algoHistoryCompareRunIdsNormalized.map(async (rid) => {
          try {
            const res = await monitoringAPI.algorithmRunSummary(topologyId, rid, { window_minutes: windowMinutes })
            return { run_id: rid, summary: res.data }
          } catch {
            return { run_id: rid, summary: null }
          }
        })
      )
      return { items: results }
    },
    enabled: activeTab === 'algorithms' && algoUiTab === 'history' && algoHistoryMode === 'compare' && !!topologyId && !!algoHistoryCompareRunIdsNormalized.length,
    refetchInterval: false,
    retry: false,
  })

  const algoHistoryCompareItems: AlgorithmRunCompareItem[] = useMemo(() => {
    const items = ((algoHistoryCompareSummaries as any)?.items || []) as any[]
    const byId = new Map<string, any>()
    for (const it of items) {
      const rid = String(it?.run_id || '').trim()
      if (rid) byId.set(rid, it?.summary)
    }
    return algoHistoryCompareRunIdsNormalized.map((rid) => {
      const run = algoHistoryRunById.get(rid) || {}
      const summary = byId.get(rid) || {}
      const tags = summary?.tags && typeof summary.tags === 'object' ? summary.tags : {}
      const fields = summary?.fields && typeof summary.fields === 'object' ? summary.fields : {}
      return {
        run_id: rid,
        algorithm: String(run?.algorithm || tags?.algorithm || ''),
        time: String(run?.time || summary?.time || ''),
        fields,
      }
    })
  }, [algoHistoryCompareSummaries, algoHistoryCompareRunIdsNormalized, algoHistoryRunById])

  useEffect(() => {
    const tpl = getAlgorithmTemplate(algoTemplateId)
    setAlgoManifestText(JSON.stringify(tpl.manifest, null, 2))
    setAlgoSourceCode(tpl.code)
    const transport = String(tpl.manifest?.transport || 'udp') as any
    if (transport === 'tcp' || transport === 'udp') setAlgoTransport(transport)
    const port = Number(tpl.manifest?.listen_port || 50000)
    if (Number.isFinite(port) && port > 0) setAlgoListenPort(port)
  }, [algoTemplateId])

  const controllerContainerStatusByName = useMemo(() => {
    const containers = (infraStatus as any)?.containers
    if (!Array.isArray(containers)) return {}
    const out: Record<string, string> = {}
    for (const c of containers) {
      const name = String(c?.name || '')
      const status = String(c?.status || '')
      if (name) out[name] = status
    }
    return out
  }, [infraStatus])

  const controllersMap = useMemo(() => {
    const raw = infraCredentials?.credentials?.controllers
    return raw && typeof raw === 'object' ? raw : {}
  }, [infraCredentials])

  const controllersList = useMemo(() => {
    const list = Object.entries(controllersMap || {}).map(([id, info]: any) => ({ id, ...(info || {}) }))
    const q = (controllerSearch || '').trim().toLowerCase()
    const filtered = q
      ? list.filter((c: any) => {
          const name = String(c?.node_name || c?.id || '').toLowerCase()
          const type = String(c?.controller_type || '').toLowerCase()
          const cname = String(c?.container_name || '').toLowerCase()
          return name.includes(q) || type.includes(q) || cname.includes(q)
        })
      : list
    return filtered.map((c: any) => {
      const cname = String(c?.container_name || '')
      const container_status = controllerContainerStatusByName[cname] || ''
      return { ...c, container_status }
    })
  }, [controllersMap, controllerSearch, controllerContainerStatusByName])

  const controllersSummary = useMemo(() => {
    const total = controllersList.length
    const isRunning = (statusRaw: any) => {
      const s = String(statusRaw || '').toLowerCase()
      return s.includes('running') || s.startsWith('up') || s.includes(' up ')
    }
    const isHealthy = (statusRaw: any) => String(statusRaw || '').toLowerCase().includes('healthy')
    const running = controllersList.filter((c: any) => isRunning(c?.container_status)).length
    const healthy = controllersList.filter((c: any) => isHealthy(c?.container_status)).length
    const withUi = controllersList.filter((c: any) => !!(c?.ui && (c.ui.container_port || c.ui.port))).length
    const withCreds = controllersList.filter((c: any) => !!(c?.credentials?.user || c?.credentials?.password)).length
    return { total, running, healthy, withUi, withCreds }
  }, [controllersList])

  useEffect(() => {
    if (activeTab !== 'controllers') return
    if (selectedControllerId) return
    if (controllersList.length) setSelectedControllerId(String(controllersList[0].id))
  }, [activeTab, controllersList, selectedControllerId])

  useEffect(() => {
    if (activeTab !== 'controllers') return
    setControllerPane('overview')
  }, [activeTab, selectedControllerId])

  const selectedController = useMemo(() => {
    return controllersList.find((c) => String(c.id) === String(selectedControllerId)) || null
  }, [controllersList, selectedControllerId])

  const controllerUiUrl = useMemo(() => {
    if (!topologyId || !selectedController?.ui) return ''
    const id8 = topologyId.slice(0, 8)
    const port = selectedController.ui.container_port || selectedController.ui.port
    const rawPath = String(selectedController.ui.path || '/')
    const path = rawPath.startsWith('/') ? rawPath.slice(1) : rawPath
    if (!port) return ''
    return `/infra-proxy/controllers/${id8}/${selectedControllerId}/${port}/${path}`
  }, [selectedController, selectedControllerId, topologyId])

  const execControllerMutation = useMutation({
    mutationFn: async () => {
      if (!topologyId || !selectedControllerId) throw new Error('Select a controller')
      const payload = { command: controllerCommand, timeout_seconds: 20 }
      const res = await infrastructureAPI.execTopologyController(topologyId, selectedControllerId, payload)
      return res.data
    },
    onSuccess: (data: any) => {
      const out = (data?.stdout || '') + (data?.stderr ? `\n${data.stderr}` : '')
      const trimmed = out.trim() ? out : '(no output)'
      setControllerOutput(trimmed)
      appendControllerConsole([`$ ${controllerCommand.trim()}`, trimmed])
      setControllerCommand('')
      toast.success('Controller command executed')
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to execute controller command')
    },
  })

  const controllerLifecycleMutation = useMutation({
    mutationFn: async (action: 'start' | 'stop' | 'restart') => {
      if (!topologyId || !selectedControllerId) throw new Error('Select a controller')
      const payload = { timeout_seconds: 15 }
      if (action === 'start') return (await infrastructureAPI.startTopologyController(topologyId, selectedControllerId, payload)).data
      if (action === 'stop') return (await infrastructureAPI.stopTopologyController(topologyId, selectedControllerId, payload)).data
      return (await infrastructureAPI.restartTopologyController(topologyId, selectedControllerId, payload)).data
    },
    onSuccess: (data: any) => {
      const status = String(data?.status || '').toLowerCase()
      toast.success(`Controller is now ${status || 'updated'}`)
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Controller action failed')
    },
  })

  useEffect(() => {
    if (!configFeedback) {
      return
    }
    const timer = window.setTimeout(() => setConfigFeedback(null), 4000)
    return () => window.clearTimeout(timer)
  }, [configFeedback])

  // Fetch topology data
  const { data: topology, isLoading: topologyLoading } = useQuery({
    queryKey: ['topology', topologyId],
    queryFn: async () => {
      if (!topologyId) throw new Error('No topology ID')
      const response = await topologiesAPI.get(topologyId)
      return response.data
    },
    enabled: !!topologyId,
  })

  const { data: availableTopologies } = useQuery({
    queryKey: ['topologies', 'available-for-network-manager'],
    queryFn: async () => {
      const response = await topologiesAPI.list()
      return response.data || []
    },
    enabled: !topologyId,
    staleTime: 30_000,
    retry: 1,
  })

  // Fetch active emulations to get emulation_id
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
        (e: any) => e.topology_id === topologyId && String(e?.status || '').toLowerCase() === 'running'
      )
      setEmulationId(currentEmulation?.emulation_id || null)
    }
  }, [activeEmulations, topologyId])

  // Fetch emulation status
  const { data: emulationStatus } = useQuery({
    queryKey: ['emulation-status', emulationId],
    queryFn: async () => {
      if (!emulationId) return null
      try {
        const response = await emulationAPI.status(emulationId)
        return response.data
      } catch (error) {
        return null
      }
    },
    enabled: !!emulationId,
    refetchInterval: 3000,
    retry: false,
  })

  // Fetch shell metadata (container + devices)
  const { data: shellInfo, isLoading: shellInfoLoading } = useQuery({
    queryKey: ['emulation-shell', emulationId],
    queryFn: async () => {
      if (!emulationId) return null
      try {
        const response = await emulationAPI.shellInfo(emulationId)
        return response.data
      } catch (error) {
        return null
      }
    },
    enabled: !!emulationId,
    refetchInterval: 15000,
    retry: false,
  })

  // Shell metadata can temporarily fail (e.g., orchestrator restart). Fallback to the
  // deterministic per-topology container name so Mininet CLI + WebShell still work.
  const containerName = (shellInfo?.container_name as string | undefined) || (topologyId ? `caduceus-emu-${topologyId.slice(0, 8)}` : undefined)
  const devices = shellInfo?.devices || []
  const devicesLoading = shellInfoLoading
  const runtimeDevices = useMemo(
    () => (devices || []).filter((d: any) => getDeviceType(d) !== 'controller'),
    [devices]
  )

  const selectedRuntimeDevice = useMemo(() => {
    if (!runtimeDevices?.length) return ''
    const match =
      runtimeDevices.find((device: any) => getDeviceKey(device) === selectedDevice) || runtimeDevices[0]
    return getRuntimeName(match) || ''
  }, [runtimeDevices, selectedDevice])

  const { data: topologyMetrics } = useQuery({
    queryKey: ['network-manager-topology-metrics', topologyId],
    queryFn: async () => {
      if (!topologyId) return null
      const res = await monitoringAPI.topologyMetrics(topologyId)
      return res.data as any
    },
    enabled: activeTab === 'metrics' && !!topologyId,
    refetchInterval: 10000,
    retry: false,
  })

  const { data: selectedDeviceMetrics } = useQuery({
    queryKey: ['network-manager-device-metrics', selectedRuntimeDevice],
    queryFn: async () => {
      if (!selectedRuntimeDevice) return null
      const res = await monitoringAPI.deviceMetrics(selectedRuntimeDevice, topologyId || undefined)
      return res.data as any
    },
    enabled: activeTab === 'metrics' && !!selectedRuntimeDevice && !!emulationId,
    refetchInterval: 5000,
    retry: false,
  })

  const { data: selectedDeviceInterfaces } = useQuery({
    queryKey: ['network-manager-device-interfaces', selectedRuntimeDevice, topologyId],
    queryFn: async () => {
      if (!selectedRuntimeDevice || !topologyId) return null
      const res = await monitoringAPI.deviceInterfaces(selectedRuntimeDevice, topologyId)
      return res.data as any
    },
    enabled: ['metrics', 'config', 'terminal'].includes(activeTab) && !!selectedRuntimeDevice && !!emulationId && !!topologyId,
    refetchInterval: 5000,
    retry: false,
  })

  const selectedDeviceTypeForMetrics = useMemo(() => {
    if (!runtimeDevices?.length) return ''
    const match =
      runtimeDevices.find((device: any) => getDeviceKey(device) === selectedDevice) || runtimeDevices[0]
    return String(getDeviceType(match) || '')
  }, [runtimeDevices, selectedDevice])

  const isSelectedSwitchForMetrics = useMemo(() => {
    const dt = (selectedDeviceTypeForMetrics || '').toLowerCase()
    return dt.includes('switch')
  }, [selectedDeviceTypeForMetrics])

  const { data: selectedDeviceRoutes } = useQuery({
    queryKey: ['network-manager-device-routes', selectedRuntimeDevice, topologyId],
    queryFn: async () => {
      if (!selectedRuntimeDevice || !topologyId) return null
      const res = await monitoringAPI.deviceRoutes(selectedRuntimeDevice, topologyId)
      return res.data as any
    },
    enabled: activeTab === 'metrics' && !!selectedRuntimeDevice && !!emulationId && !!topologyId,
    refetchInterval: 10000,
    retry: false,
  })

  const { data: selectedDeviceArp } = useQuery({
    queryKey: ['network-manager-device-arp', selectedRuntimeDevice, topologyId],
    queryFn: async () => {
      if (!selectedRuntimeDevice || !topologyId) return null
      const res = await monitoringAPI.deviceArp(selectedRuntimeDevice, topologyId)
      return res.data as any
    },
    enabled: activeTab === 'metrics' && !!selectedRuntimeDevice && !!emulationId && !!topologyId,
    refetchInterval: 10000,
    retry: false,
  })

  const { data: selectedSwitchFlows } = useQuery({
    queryKey: ['network-manager-switch-flows', selectedRuntimeDevice, topologyId],
    queryFn: async () => {
      if (!selectedRuntimeDevice || !topologyId) return null
      const res = await monitoringAPI.switchFlows(selectedRuntimeDevice, topologyId)
      return res.data as any
    },
    enabled: activeTab === 'metrics' && !!selectedRuntimeDevice && isSelectedSwitchForMetrics && !!emulationId && !!topologyId,
    refetchInterval: 15000,
    retry: false,
  })

  useEffect(() => {
    if (activeTab !== 'metrics') return
    if (!selectedRuntimeDevice) return
    setMetricsHistory([])
    setAiDiagnosis('')
  }, [activeTab, selectedRuntimeDevice])

  useEffect(() => {
    if (activeTab !== 'metrics') return
    if (!selectedDeviceMetrics) return
    const stats = selectedDeviceMetrics?.stats || {}
    const rx = Number(stats?.rx_bytes || 0)
    const tx = Number(stats?.tx_bytes || 0)
    const cpu = Number(selectedDeviceMetrics?.cpu?.total_cpu_percent || 0)
    const memUsed = Number(selectedDeviceMetrics?.memory?.used_mb || 0)
    const memTotal = Number(selectedDeviceMetrics?.memory?.total_mb || 0)
    const mem = memTotal > 0 ? (memUsed / memTotal) * 100 : 0
    setMetricsHistory((prev) => [...prev, { ts: new Date().toLocaleTimeString(), rx, tx, cpu, mem }].slice(-30))
  }, [activeTab, selectedDeviceMetrics])

  useEffect(() => {
    if (!topologyId) return
    let cancelled = false
    ;(async () => {
      try {
        const res = await networkConfigsAPI.getLatest(topologyId)
        if (cancelled) return
        const cfg = res.data?.config ?? res.data
        setNetworkConfigText(JSON.stringify(cfg, null, 2))
        setNetworkConfigName(res.data?.name || cfg?.name || '')
        setNetworkConfigDescription(res.data?.description || cfg?.description || '')
      } catch {
        try {
          const tpl = await networkConfigsAPI.template(topologyId)
          if (cancelled) return
          setNetworkConfigText(JSON.stringify(tpl.data, null, 2))
          setNetworkConfigName(tpl.data?.name || '')
          setNetworkConfigDescription(tpl.data?.description || '')
        } catch {
          // ignore
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [topologyId])

  const deviceNamesForMetrics = useMemo(() => {
    const list = (runtimeDevices || [])
      .map((d: any) => getRuntimeName(d))
      .filter((v): v is string => typeof v === 'string' && Boolean(v.trim()))
    return Array.from(new Set<string>(list)).slice(0, 25)
  }, [runtimeDevices])

  const deviceMetricQueries = useQueries({
    queries: deviceNamesForMetrics.map((name) => ({
      queryKey: ['network-manager-device-metrics-table', name],
      queryFn: async () => {
        const res = await monitoringAPI.deviceMetrics(name, topologyId || undefined)
        return res.data as any
      },
      enabled: activeTab === 'metrics' && !!emulationId,
      refetchInterval: 8000,
      retry: false,
    })),
  })

  const deviceMetricRows = useMemo(() => {
    return deviceNamesForMetrics.map((name, idx) => {
      const q = deviceMetricQueries[idx]
      const data = q?.data
      const cpu = Number(data?.cpu?.total_cpu_percent || 0)
      const memUsed = Number(data?.memory?.used_mb || 0)
      const memTotal = Number(data?.memory?.total_mb || 0)
      const mem = memTotal > 0 ? (memUsed / memTotal) * 100 : 0
      const rx = Number(data?.stats?.rx_bytes || 0)
      const tx = Number(data?.stats?.tx_bytes || 0)
      let errors = 0
      if (data?.interfaces && typeof data.interfaces === 'object') {
        Object.values(data.interfaces).forEach((v: any) => {
          errors += Number(v?.rx_errors || 0) + Number(v?.tx_errors || 0)
        })
      }
      const status =
        q?.isError ? 'down' : cpu >= 85 || mem >= 85 || errors > 0 ? 'warning' : 'ok'
      return { name, cpu, mem, rx, tx, errors, status }
    })
  }, [deviceMetricQueries, deviceNamesForMetrics])

  const formatBytes = (bytes: number) => {
    if (!bytes) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.min(sizes.length - 1, Math.floor(Math.log(bytes) / Math.log(k)))
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`
  }

  const runAiDiagnosis = async () => {
    if (!topologyId) return
    try {
      setAiDiagnosing(true)
      const res = await aiAPI.network.diagnose({ topology_id: topologyId })
      setAiDiagnosis(String((res.data as any)?.content || '').trim())
      setAiDiagnosisHeuristics((res.data as any)?.heuristics ?? null)
      toast.success('Network diagnosis ready')
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || 'Failed to diagnose network'
      setAiDiagnosisHeuristics(null)
      toast.error(msg)
    } finally {
      setAiDiagnosing(false)
    }
  }

  useEffect(() => {
    if (!runtimeDevices.length) {
      if (selectedDevice) {
        setSelectedDevice('')
      }
      return
    }

    const deviceKeys = runtimeDevices.map((device: any) => getDeviceKey(device))
    if (!selectedDevice || !deviceKeys.includes(selectedDevice)) {
      setSelectedDevice(deviceKeys[0])
    }
  }, [runtimeDevices, selectedDevice])

  const selectedDeviceData = useMemo(() => {
    if (!runtimeDevices.length) {
      return null
    }
    return (
      runtimeDevices.find((device: any) => getDeviceKey(device) === selectedDevice) || runtimeDevices[0]
    )
  }, [runtimeDevices, selectedDevice])

  useEffect(() => {
    if (!selectedDeviceData) {
      return
    }
    const props = selectedDeviceData.properties || {}
    const stringifyList = (value: any) => {
      if (Array.isArray(value)) {
        return value.join('\n')
      }
      return value || ''
    }

    setConfigDraft((draft) => ({
      ...draft,
      ip: props.ip || '',
      ip6: props.ip6 || '',
      mac: props.mac || '',
      default_route: props.default_route || props.defaultRoute || '',
      mtu: props.mtu ? String(props.mtu) : '',
      static_routes: stringifyList(props.static_routes),
      dns_servers: stringifyList(props.dns_servers),
      startup_commands: stringifyList(props.startup_commands),
      controller: props.controller || '',
      openflow_version: props.openflow_version || '',
      router_daemon: props.router_daemon || '',
      protocols: stringifyList(props.protocols),
    }))
  }, [selectedDeviceData])

  useEffect(() => {
    setRouteRows(parseStaticRoutes(configDraft.static_routes))
    setDnsRows(splitLines(configDraft.dns_servers))
    setCommandRows(splitLines(configDraft.startup_commands))
  }, [configDraft.static_routes, configDraft.dns_servers, configDraft.startup_commands])

  const selectedDeviceType = (selectedDeviceData?.device_type || selectedDeviceData?.type || '').toLowerCase()
  const selectedTopologyNode = useMemo(() => {
    if (!topology || !selectedDeviceData) return null
    const displayName = selectedDeviceData.name
    const runtimeName = getRuntimeName(selectedDeviceData)
    return (
      (topology.nodes as any[])?.find((n) => n?.name === displayName) ||
      (topology.nodes as any[])?.find((n) => n?.name === runtimeName) ||
      null
    )
  }, [selectedDeviceData, topology])
  const selectedTopologyNodeProps = (selectedTopologyNode as any)?.properties || {}
  const ifaceOptions = useMemo(() => {
    const all = Object.keys(selectedDeviceInterfaces?.interfaces || {}).filter((name) => name && name !== 'lo')
    const hint = selectedRuntimeDevice || (selectedDeviceData ? getRuntimeName(selectedDeviceData) : '')
    if (!hint) return all
    const filtered = all.filter((name) => name.startsWith(`${hint}-`))
    return filtered.length ? filtered : all
  }, [selectedDeviceInterfaces?.interfaces, selectedRuntimeDevice, selectedDeviceData])

  useEffect(() => {
    const preferred = ifaceOptions[0] || ''
    setIfaceSelection((current) => current || preferred)
  }, [ifaceOptions])

  const updateDeviceMutation = useMutation({
    mutationFn: ({ deviceName, properties }: { deviceName: string; properties: Record<string, any> }) =>
      devicesAPI.update(deviceName, { properties }),
    onSuccess: () => {
      setConfigFeedback({ type: 'success', message: t('network.configurationApplied', 'Configuration applied successfully') })
      queryClient.invalidateQueries({ queryKey: ['emulation-devices', emulationId] })
    },
    onError: (error: any) => {
      const message = error?.response?.data?.detail || error?.message || t('network.configurationFailed', 'Failed to apply configuration')
      setConfigFeedback({ type: 'error', message })
    },
  })

  const handleConfigChange = (key: string, value: string) => {
    setConfigFeedback(null)
    setConfigDraft((prev) => ({ ...prev, [key]: value }))
  }

  const applyRuntimeConfig = async (runtimeName: string) => {
    if (!topologyId) return
    if (!isRunning) return

    const addresses: string[] = []
    if (configDraft.ip.trim()) addresses.push(configDraft.ip.trim())
    if (configDraft.ip6.trim()) addresses.push(configDraft.ip6.trim())

    const iface: any = {}
    if (ifaceSelection) iface.name = ifaceSelection
    if (configDraft.mac.trim()) iface.mac = configDraft.mac.trim()
    if (configDraft.mtu.trim() && Number(configDraft.mtu.trim())) iface.mtu = Number(configDraft.mtu.trim())
    iface.addresses = addresses

    const routes = routeRows
      .map((row) => ({
        dst: row.dst.trim(),
        via: (row.via || '').trim() || undefined,
        dev: (row.dev || '').trim() || undefined,
        metric: (row.metric || '').trim() ? Number(row.metric) : undefined,
      }))
      .filter((row) => row.dst)

    const payload: any = {
      schema: 'caduceus.network-config.v1',
      topology_id: topologyId,
      name: 'Runtime config (single device)',
      devices: [
        {
          name: runtimeName,
          kind: selectedDeviceType,
          interfaces: addresses.length || iface.name || iface.mac || iface.mtu ? [iface] : [],
          default_gateway: normalizeGateway(configDraft.default_route),
          routes,
          dns_servers: dnsRows,
          commands: commandRows,
          sysctls:
            selectedDeviceType === 'router'
              ? { 'net.ipv4.ip_forward': '1', 'net.ipv6.conf.all.forwarding': '1' }
              : {},
        },
      ],
    }

    const res = await emulationAPI.applyNetworkConfig({
      topology_id: topologyId,
      config: payload,
      dry_run: false,
    })
    if (res.data?.success) {
      toast.success('Applied to running network')
    } else {
      toast.error(res.data?.message || 'Applied with errors')
    }
  }

  const buildPayloadForType = (type: string): Record<string, any> => {
    const trimmed = (value: string) => (typeof value === 'string' ? value.trim() : value)
    switch (type) {
      case 'host':
      case 'router':
      case 'container':
        return {
          ip: trimmed(configDraft.ip),
          ip6: trimmed(configDraft.ip6),
          mac: trimmed(configDraft.mac),
          default_route: trimmed(configDraft.default_route),
          mtu: trimmed(configDraft.mtu),
          static_routes: serializeStaticRoutes(routeRows),
          dns_servers: dnsRows.join('\n'),
          startup_commands: commandRows.join('\n'),
          ...(type === 'router'
            ? {
                router_daemon: trimmed(configDraft.router_daemon),
                protocols: configDraft.protocols,
              }
            : {}),
        }
      case 'switch':
      case 'p4switch':
        return {
          controller: trimmed(configDraft.controller),
          openflow_version: trimmed(configDraft.openflow_version),
        }
      default:
        return {}
    }
  }

  const handleApplyConfig = () => {
    if (!selectedDeviceData) {
      return
    }
    const payload = buildPayloadForType(selectedDeviceType)
    if (Object.keys(payload).length === 0) {
      setConfigFeedback({ type: 'error', message: t('network.configurationUnsupported', 'Configuration updates are not supported for this device type yet.') })
      return
    }
    const runtimeName = getRuntimeName(selectedDeviceData)
    updateDeviceMutation.mutate(
      { deviceName: runtimeName, properties: payload },
      {
        onSuccess: async () => {
          try {
            if (isRunning && ['host', 'router', 'container'].includes(selectedDeviceType)) {
              await applyRuntimeConfig(runtimeName)
            }
          } catch (e: any) {
            toast.error(e?.response?.data?.detail || e?.message || 'Failed to apply runtime configuration')
          }
        },
      }
    )
  }

  const isApplyingConfig = updateDeviceMutation.isPending
  const DEMO_TOPOLOGY_ID = 'c9d930f0-1608-4fb4-8f38-e3f209e8626a'

  const applyDemoConfig = async () => {
    if (!topologyId || topologyId !== DEMO_TOPOLOGY_ID) return
    if (!isRunning) {
      toast.error('Start the emulation first')
      return
    }
    try {
      setIsApplyingDemoConfig(true)
      const hostNode = (topology?.nodes as any[])?.find((n) => String(n?.device_type).toLowerCase() === 'host')
      const routerNode = (topology?.nodes as any[])?.find((n) => String(n?.device_type).toLowerCase() === 'router')
      const hostName = hostNode?.name || 'host-1'
      const routerName = routerNode?.name || 'router-3'
      const demo = {
        schema: 'caduceus.network-config.v1',
        topology_id: topologyId,
        name: 'Demo: basic connectivity (10.0.0.0/24)',
        description: 'Sets host/router IPs + default route for quick testing.',
        defaults: {
          dns_servers: ['8.8.8.8', '1.1.1.1'],
          sysctls: {},
          commands: [],
        },
        devices: [
          {
            name: hostName,
            kind: 'host',
            interfaces: [
              { name: `${hostName}-eth1`, addresses: ['10.0.0.1/30'] },
              { name: `${hostName}-eth0`, addresses: ['10.0.1.1/24'] },
            ],
            default_gateway: '10.0.0.2',
          },
          {
            name: routerName,
            kind: 'router',
            interfaces: [{ name: `${routerName}-eth0`, addresses: ['10.0.0.2/30'] }],
            sysctls: { 'net.ipv4.ip_forward': '1' },
          },
        ],
      }

      const applyRes = await emulationAPI.applyNetworkConfig({
        topology_id: topologyId,
        config: demo,
        dry_run: false,
      })
      if (!applyRes.data?.success) {
        toast.error(applyRes.data?.message || 'Demo config applied with errors')
      } else {
        toast.success('Demo config applied')
      }

      try {
        await networkConfigsAPI.create(topologyId, { name: demo.name, description: demo.description, config: demo })
      } catch {
        // Best-effort persistence.
      }

      setNetworkConfigText(JSON.stringify(demo, null, 2))
      setNetworkConfigName(demo.name)
      setNetworkConfigDescription(demo.description)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to apply demo configuration')
    } finally {
      setIsApplyingDemoConfig(false)
    }
  }

  const infraControllerCount =
    infraCredentials?.credentials?.controllers && typeof infraCredentials.credentials.controllers === 'object'
      ? Object.keys(infraCredentials.credentials.controllers as any).length
      : 0

  const controllerCount =
    infraControllerCount ||
    (topology?.nodes || []).filter((n: any) => String(n?.device_type || '').toLowerCase() === 'controller').length ||
    topology?.controllers?.length ||
    0

  // Calculate network statistics from real data
  const networkStats = {
    totalHosts: runtimeDevices?.filter((d: any) => ['host', 'container'].includes(getDeviceType(d))).length || 0,
    totalSwitches: runtimeDevices?.filter((d: any) => ['switch', 'p4switch'].includes(getDeviceType(d))).length || 0,
    totalRouters: runtimeDevices?.filter((d: any) => getDeviceType(d) === 'router').length || 0,
    totalControllers: controllerCount,
    activeConnections:
      (emulationStatus?.status === 'running' ? emulationStatus?.link_count : topology?.links?.length) || 0,
    deviceCount:
      emulationStatus?.status === 'running'
        ? (runtimeDevices?.length || 0) + controllerCount
        : (topology?.nodes || []).length || 0,
    linkCount: emulationStatus?.link_count || 0,
    uptime: emulationStatus?.uptime_seconds || 0,
  }

  const hostDevices = runtimeDevices?.filter((d: any) => ['host', 'container'].includes(getDeviceType(d))) || []
  const switchDevices = runtimeDevices?.filter((d: any) => ['switch', 'p4switch'].includes(getDeviceType(d))) || []
  const routerDevices = runtimeDevices?.filter((d: any) => getDeviceType(d) === 'router') || []

  // Format uptime
  const formatUptime = (seconds: number): string => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    const secs = seconds % 60
    return `${hours}h ${minutes}m ${secs}s`
  }

  if (topologyLoading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <div className="text-center space-y-4">
          <div className="w-16 h-16 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-gray-600 dark:text-gray-400">{t('common.loading')}</p>
        </div>
      </div>
    )
  }

  if (!topologyId || !topology) {
    const firstId = String((availableTopologies || [])[0]?.id || '')
    const effectiveId = topologyPickerId || firstId
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-950 flex items-center justify-center">
        <div className="w-full max-w-lg text-center space-y-4">
          <p className="text-gray-600 dark:text-gray-400">No topology selected</p>

          <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-3 text-left">
            <div className="text-sm font-medium text-gray-800 dark:text-gray-200">
              Select a topology to open Network Manager (MANO → OSM is inside).
            </div>
            <select
              value={effectiveId}
              onChange={(e) => setTopologyPickerId(e.target.value)}
              className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
            >
              {(availableTopologies || []).map((tp: any) => (
                <option key={String(tp.id)} value={String(tp.id)}>
                  {String(tp.name || tp.id)}
                </option>
              ))}
            </select>

            <div className="flex flex-wrap items-center justify-center gap-2">
              <Button
                variant="secondary"
                onClick={() => navigate('/projects')}
              >
                Go to Projects
              </Button>
              <Button
                disabled={!effectiveId}
                onClick={() => navigate(`/network-manager?topology=${encodeURIComponent(effectiveId)}`)}
              >
                Open Network Manager
              </Button>
              <Button
                variant="primary"
                disabled={!effectiveId}
                onClick={() => navigate(`/network-manager?topology=${encodeURIComponent(effectiveId)}&tab=mano`)}
              >
                Open MANO (OSM)
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const isRunning = emulationStatus?.status === 'running'

  const parseNetworkConfig = (): any | null => {
    if (!topologyId) {
      toast.error('No topology selected')
      return null
    }
    try {
      const obj = JSON.parse(networkConfigText || '{}')
      if (!obj || typeof obj !== 'object') {
        throw new Error('Config must be a JSON object')
      }
      obj.schema = obj.schema || 'caduceus.network-config.v1'
      obj.topology_id = topologyId
      if (!obj.name && networkConfigName) obj.name = networkConfigName
      if (!obj.description && networkConfigDescription) obj.description = networkConfigDescription
      if (!Array.isArray(obj.devices)) obj.devices = []
      return obj
    } catch (e: any) {
      toast.error(e?.message || 'Invalid JSON configuration')
      return null
    }
  }

  const handleLoadConfigTemplate = async () => {
    if (!topologyId) return
    try {
      const res = await networkConfigsAPI.template(topologyId)
      setNetworkConfigText(JSON.stringify(res.data, null, 2))
      setNetworkConfigName(res.data?.name || '')
      setNetworkConfigDescription(res.data?.description || '')
      toast.success('Template loaded')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to load template')
    }
  }

  const handleLoadSavedConfig = async () => {
    if (!topologyId) return
    try {
      const res = await networkConfigsAPI.getLatest(topologyId)
      const cfg = res.data?.config ?? res.data
      setNetworkConfigText(JSON.stringify(cfg, null, 2))
      setNetworkConfigName(res.data?.name || cfg?.name || '')
      setNetworkConfigDescription(res.data?.description || cfg?.description || '')
      toast.success('Saved configuration loaded')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'No saved configuration found')
    }
  }

  const handleSaveNetworkConfig = async () => {
    if (!topologyId) return
    const cfg = parseNetworkConfig()
    if (!cfg) return
    try {
      await networkConfigsAPI.create(topologyId, {
        name: networkConfigName || cfg?.name,
        description: networkConfigDescription || cfg?.description,
        config: cfg,
      })
      toast.success('Network configuration saved')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to save configuration')
    }
  }

  const handleApplyNetworkConfig = async () => {
    if (!topologyId) return
    const cfg = parseNetworkConfig()
    if (!cfg) return
    if (!isRunning) {
      toast.error('Start the emulation first')
      return
    }
    try {
      const res = await emulationAPI.applyNetworkConfig({
        topology_id: topologyId,
        config: cfg,
        dry_run: networkConfigDryRun,
      })
      const ok = !!res.data?.success
      if (ok) toast.success(networkConfigDryRun ? 'Dry-run OK' : 'Configuration applied')
      else toast.error(res.data?.message || 'Applied with errors')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to apply configuration')
    }
  }

  const handleExportNetworkConfig = async () => {
    if (!topologyId) return
    try {
      const res = await networkConfigsAPI.exportLatest(topologyId)
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `network-config-${topologyId}.json`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      toast.success('Exported')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to export')
    }
  }

  const downloadTextFile = (filename: string, content: string, mime: string) => {
    const blob = new Blob([content], { type: mime })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  const handleRefreshTopologyExport = async () => {
    if (!topologyId) return
    try {
      await topologyExportQuery.refetch()
      toast.success('Script refreshed')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to refresh script')
    }
  }

  const handleCopyTopologyExport = async () => {
    const content = topologyExportQuery.data?.content || ''
    if (!content) {
      toast.error('No script loaded yet')
      return
    }
    try {
      await navigator.clipboard.writeText(content)
      toast.success('Copied')
    } catch {
      try {
        const textarea = document.createElement('textarea')
        textarea.value = content
        textarea.style.position = 'fixed'
        textarea.style.left = '-9999px'
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        textarea.remove()
        toast.success('Copied')
      } catch (e: any) {
        toast.error(e?.message || 'Copy failed')
      }
    }
  }

  const handleDownloadTopologyExport = async () => {
    if (!topologyId) return
    const toastId = toast.loading('Exporting…')
    try {
      let payload = topologyExportQuery.data
      if (!payload) {
        const res = await topologyExportQuery.refetch()
        payload = res.data
      }
      if (!payload?.content) throw new Error('No script content')
      const filename =
        payload.filename || `topology-${topologyId}-${topologyExportFormat.replace(/[^a-z0-9-]+/gi, '_')}.py`
      downloadTextFile(filename, payload.content, 'text/x-python')
      toast.success('Downloaded', { id: toastId })
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Export failed', { id: toastId })
    }
  }

  const handleImportNetworkConfigFile = async (file: File | null) => {
    if (!file) return
    try {
      const text = await file.text()
      setNetworkConfigText(text)
      toast.success('Imported')
    } catch (e: any) {
      toast.error(e?.message || 'Failed to read file')
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 pb-20 md:pb-8">
      {/* Header */}
      <div className="sticky top-16 z-30 bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl border-b border-gray-200 dark:border-gray-800">
        <div className="container-network py-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate(`/topology/${topologyId}`)}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-xl transition-colors"
              >
                <ArrowLeftIcon className="w-5 h-5 text-gray-600 dark:text-gray-400" />
              </button>
              
              <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {t('nav.networkManager')}
                </h1>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  {t('network.manageRunning')}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant={isRunning ? 'success' : 'default'} withIcon size="sm">
                <PlayIcon className="w-3 h-3" />
                {isRunning ? t('network.running') : 'Stopped'}
              </Badge>
              {isRunning && networkStats.uptime > 0 && (
                <Badge variant="default" size="sm">
                  Uptime: {formatUptime(networkStats.uptime)}
                </Badge>
              )}
            </div>
          </div>
        </div>
      </div>

	      {/* Tabs */}
	      <div className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
	        <div className="container-network">
            <div className="flex items-center gap-3">
              <div className="flex overflow-x-auto flex-1">
                {tabs.map((tab) => {
                  const Icon = tab.icon
                  const isActive = activeTab === tab.id
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id as any)}
                      className={`
                        flex items-center gap-2 px-6 py-4 border-b-2 transition-all whitespace-nowrap
                        ${
                          isActive
                            ? 'border-blue-600 dark:border-blue-400 text-blue-600 dark:text-blue-400'
                            : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                        }
                      `}
                    >
                      <Icon className="w-5 h-5" />
                      <span className="font-medium">{tab.label}</span>
                    </button>
                  )
                })}
              </div>

              <div className="shrink-0">
                <label className="sr-only">Jump to tab</label>
                <select
                  value={activeTab}
                  onChange={(e) => setActiveTab(e.target.value as any)}
                  className="w-44 sm:w-auto px-3 py-2 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-sm text-gray-900 dark:text-gray-100"
                >
                  {tabs.map((tab) => (
                    <option key={tab.id} value={tab.id}>
                      {tab.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
	        </div>
	      </div>

      {/* Content */}
      <div className="container-network py-8">
        {activeTab === 'overview' && (
          <div className="space-y-6 animate-fade-in">
            {/* Stats Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                title={t('nodes.hosts')}
                value={networkStats.totalHosts}
                icon={<CpuChipIcon className="w-5 h-5" />}
                variant="primary"
              />
              <MetricCard
                title={t('nodes.switches')}
                value={networkStats.totalSwitches}
                icon={<ServerIcon className="w-5 h-5" />}
                variant="success"
              />
              <MetricCard
                title={t('nodes.routers')}
                value={networkStats.totalRouters}
                icon={<WifiIcon className="w-5 h-5" />}
                variant="warning"
              />
              <MetricCard
                title={t('nodes.controllers')}
                value={networkStats.totalControllers}
                icon={<CpuChipIcon className="w-5 h-5" />}
                variant="error"
              />
            </div>

            {/* Performance Metrics */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <MetricCard
                title="Active Links"
                value={networkStats.linkCount}
                variant="success"
              />
              <MetricCard
                title="Total Devices"
                value={networkStats.deviceCount}
                variant="primary"
              />
              <MetricCard
                title="Active Connections"
                value={networkStats.activeConnections}
                variant="default"
              />
            </div>

            {/* Topology Visualization */}
            <Card>
              <CardHeader>
                <CardTitle>{t('topology.title')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-96 bg-gray-50 dark:bg-gray-800 rounded-xl flex items-center justify-center">
                  <div className="text-center text-gray-500 dark:text-gray-400">
                    <ChartBarIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                    <p>{t('network.visualizationPlaceholder')}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Devices Table */}
            <Card>
              <CardHeader>
                <CardTitle>{t('network.connectedDevices')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-800">
                        <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">{t('network.device')}</th>
                        <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">{t('network.type')}</th>
                        <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">{t('network.ipAddress')}</th>
                        <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">{t('network.status')}</th>
                        <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">{t('common.actions')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {devicesLoading ? (
                        <tr>
                          <td colSpan={5} className="py-8 text-center text-gray-500 dark:text-gray-400">
                            Loading devices...
                          </td>
                        </tr>
                      ) : runtimeDevices && runtimeDevices.length > 0 ? (
                        runtimeDevices.map((device: any) => (
                          <tr
                            key={getDeviceKey(device)}
                            className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                          >
                            <td className="py-3 px-4 text-sm font-medium text-gray-900 dark:text-white">{device.name}</td>
                            <td className="py-3 px-4 text-sm text-gray-600 dark:text-gray-400 capitalize">{device.device_type}</td>
                            <td className="py-3 px-4 text-sm text-gray-600 dark:text-gray-400 font-mono">{device.ip || 'N/A'}</td>
                            <td className="py-3 px-4">
                              <Badge variant={device.status === 'active' ? 'success' : 'default'} size="sm">
                                {device.status || 'active'}
                              </Badge>
                            </td>
                            <td className="py-3 px-4 text-right">
                              <Button
                                variant="ghost"
                                size="xs"
                                onClick={() => {
                                  setSelectedDevice(getDeviceKey(device))
                                  setActiveTab('terminal')
                                }}
                              >
                                Terminal
                              </Button>
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={5} className="py-8 text-center text-gray-500 dark:text-gray-400">
                            {isRunning ? 'No devices found' : 'Start the emulation to see devices'}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {activeTab === 'metrics' && (
          <div className="space-y-6">
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                title={t('monitoring.bandwidth', 'Bandwidth')}
                value={topologyMetrics?.bandwidth || '—'}
                icon={<ChartBarIcon className="w-5 h-5" />}
                variant="primary"
              />
              <MetricCard
                title={t('monitoring.latency', 'Latency')}
                value={topologyMetrics?.latency || '—'}
                icon={<WifiIcon className="w-5 h-5" />}
                variant="success"
              />
              <MetricCard
                title={t('monitoring.packets', 'Packets')}
                value={topologyMetrics?.packets || '—'}
                icon={<CpuChipIcon className="w-5 h-5" />}
                variant="warning"
              />
              <MetricCard
                title={t('status.status', 'Status')}
                value={isRunning ? t('status.running') : t('status.stopped')}
                icon={<ServerIcon className="w-5 h-5" />}
                variant={isRunning ? 'success' : 'default'}
              />
            </div>

            {!isRunning && (
              <Card>
                <CardContent>
                  <div className="py-6 text-sm text-gray-600 dark:text-gray-400">
                    Start the emulation to see live device telemetry.
                  </div>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle>Device Telemetry</CardTitle>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-gray-600 dark:text-gray-400">Device</span>
                  <select
                    value={selectedDevice}
                    onChange={(e) => setSelectedDevice(e.target.value)}
                    className="px-3 py-2 rounded-xl border bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                    disabled={!runtimeDevices?.length}
                  >
                      {(runtimeDevices || []).map((d: any) => {
                      const key = getDeviceKey(d)
                      const label = `${d?.name || key}${getRuntimeName(d) ? ` · ${getRuntimeName(d)}` : ''}`
                      return (
                        <option key={key} value={key}>
                          {label}
                        </option>
                      )
                    })}
                  </select>
                </div>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                  <MetricCard
                    title="CPU"
                    value={selectedDeviceMetrics?.cpu?.total_cpu_percent !== undefined ? `${Number(selectedDeviceMetrics.cpu.total_cpu_percent).toFixed(1)}%` : '—'}
                    variant="primary"
                  />
                  <MetricCard
                    title="Memory"
                    value={
                      selectedDeviceMetrics?.memory?.total_mb
                        ? `${((Number(selectedDeviceMetrics.memory.used_mb) / Number(selectedDeviceMetrics.memory.total_mb)) * 100).toFixed(1)}%`
                        : '—'
                    }
                    variant="success"
                  />
                  <MetricCard
                    title="RX"
                    value={selectedDeviceMetrics?.stats ? formatBytes(Number(selectedDeviceMetrics.stats.rx_bytes || 0)) : '—'}
                    variant="warning"
                  />
                  <MetricCard
                    title="TX"
                    value={selectedDeviceMetrics?.stats ? formatBytes(Number(selectedDeviceMetrics.stats.tx_bytes || 0)) : '—'}
                    variant="default"
                  />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Live Charts</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
                    <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Traffic (bytes)</div>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={metricsHistory}>
                          <defs>
                            <linearGradient id="nmRx" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35} />
                              <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                            </linearGradient>
                            <linearGradient id="nmTx" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor="#22c55e" stopOpacity={0.35} />
                              <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,.35)" />
                          <XAxis dataKey="ts" tick={{ fontSize: 12 }} />
                          <YAxis tick={{ fontSize: 12 }} />
                          <Tooltip />
                          <Area type="monotone" dataKey="rx" stroke="#3b82f6" fillOpacity={1} fill="url(#nmRx)" />
                          <Area type="monotone" dataKey="tx" stroke="#22c55e" fillOpacity={1} fill="url(#nmTx)" />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
                    <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-3">Load (%)</div>
                    <div className="h-64">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={metricsHistory}>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,.35)" />
                          <XAxis dataKey="ts" tick={{ fontSize: 12 }} />
                          <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} />
                          <Tooltip />
                          <Line type="monotone" dataKey="cpu" stroke="#7c3aed" strokeWidth={2} dot={false} />
                          <Line type="monotone" dataKey="mem" stroke="#f59e0b" strokeWidth={2} dot={false} />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="mt-2 text-xs text-gray-600 dark:text-gray-400">
                      CPU (purple) · Memory (amber)
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle>Interface Details</CardTitle>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {selectedRuntimeDevice ? selectedRuntimeDevice : '—'}
                </div>
              </CardHeader>
              <CardContent>
                {!selectedDeviceInterfaces?.interfaces ? (
                  <div className="py-4 text-sm text-gray-600 dark:text-gray-400">
                    {isRunning ? 'No interface stats available yet.' : 'Start the emulation to see interface stats.'}
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-200 dark:border-gray-800">
                          <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Interface</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">RX</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">TX</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Packets</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Errors</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Drops</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(selectedDeviceInterfaces.interfaces).map(([iface, s]: any) => {
                          const rx = Number(s?.rx_bytes || 0)
                          const tx = Number(s?.tx_bytes || 0)
                          const pkts = Number(s?.rx_packets || 0) + Number(s?.tx_packets || 0)
                          const errs = Number(s?.rx_errors || 0) + Number(s?.tx_errors || 0)
                          const drops = Number(s?.rx_dropped || 0) + Number(s?.tx_dropped || 0)
                          return (
                            <tr
                              key={iface}
                              className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                            >
                              <td className="py-3 px-4 text-sm font-medium text-gray-900 dark:text-white">{iface}</td>
                              <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{formatBytes(rx)}</td>
                              <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{formatBytes(tx)}</td>
                              <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{pkts}</td>
                              <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{errs}</td>
                              <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{drops}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>Routing Table</CardTitle>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    {selectedRuntimeDevice ? selectedRuntimeDevice : '—'}
                  </div>
                </CardHeader>
                <CardContent>
                  {!selectedDeviceRoutes?.routes ? (
                    <div className="py-4 text-sm text-gray-600 dark:text-gray-400">
                      {isRunning ? 'No routing table available yet.' : 'Start the emulation to see routes.'}
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-gray-200 dark:border-gray-800">
                            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Destination</th>
                            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Gateway</th>
                            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Interface</th>
                            <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Metric</th>
                            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Protocol</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(selectedDeviceRoutes.routes as any[]).map((r, idx) => (
                            <tr
                              key={`${r?.destination || 'dst'}-${idx}`}
                              className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                            >
                              <td className="py-3 px-4 text-sm font-medium text-gray-900 dark:text-white font-mono">{r?.destination || '—'}</td>
                              <td className="py-3 px-4 text-sm text-gray-700 dark:text-gray-300 font-mono">{r?.gateway || '—'}</td>
                              <td className="py-3 px-4 text-sm text-gray-700 dark:text-gray-300 font-mono">{r?.interface || '—'}</td>
                              <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{r?.metric ?? '—'}</td>
                              <td className="py-3 px-4 text-sm text-gray-700 dark:text-gray-300">{r?.protocol || '—'}</td>
                            </tr>
                          ))}
                          {!(selectedDeviceRoutes.routes as any[]).length && (
                            <tr>
                              <td colSpan={5} className="py-8 text-center text-gray-500 dark:text-gray-400">
                                No routes
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>ARP / Neighbors</CardTitle>
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    {selectedRuntimeDevice ? selectedRuntimeDevice : '—'}
                  </div>
                </CardHeader>
                <CardContent>
                  {!selectedDeviceArp?.entries ? (
                    <div className="py-4 text-sm text-gray-600 dark:text-gray-400">
                      {isRunning ? 'No ARP entries available yet.' : 'Start the emulation to see ARP entries.'}
                    </div>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-gray-200 dark:border-gray-800">
                            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">IP</th>
                            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">MAC</th>
                            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Interface</th>
                            <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">State</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(selectedDeviceArp.entries as any[]).map((e, idx) => (
                            <tr
                              key={`${e?.ip || 'ip'}-${idx}`}
                              className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                            >
                              <td className="py-3 px-4 text-sm font-medium text-gray-900 dark:text-white font-mono">{e?.ip || '—'}</td>
                              <td className="py-3 px-4 text-sm text-gray-700 dark:text-gray-300 font-mono">{e?.mac || '—'}</td>
                              <td className="py-3 px-4 text-sm text-gray-700 dark:text-gray-300 font-mono">{e?.interface || '—'}</td>
                              <td className="py-3 px-4 text-sm text-gray-700 dark:text-gray-300">{e?.state || '—'}</td>
                            </tr>
                          ))}
                          {!(selectedDeviceArp.entries as any[]).length && (
                            <tr>
                              <td colSpan={4} className="py-8 text-center text-gray-500 dark:text-gray-400">
                                No entries
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle>Switch Flow Table</CardTitle>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {isSelectedSwitchForMetrics ? `${selectedRuntimeDevice}` : 'Select a switch'}
                </div>
              </CardHeader>
              <CardContent>
                {!isSelectedSwitchForMetrics ? (
                  <div className="py-4 text-sm text-gray-600 dark:text-gray-400">
                    Flow tables are available for switch devices.
                  </div>
                ) : !selectedSwitchFlows?.flows ? (
                  <div className="py-4 text-sm text-gray-600 dark:text-gray-400">
                    {isRunning ? 'No flow data available yet.' : 'Start the emulation to see flow entries.'}
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-200 dark:border-gray-800">
                          <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Priority</th>
                          <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Match</th>
                          <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Actions</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Packets</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Bytes</th>
                          <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Duration</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(selectedSwitchFlows.flows as any[]).map((f, idx) => (
                          <tr
                            key={`${f?.priority ?? 'p'}-${idx}`}
                            className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                          >
                            <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{f?.priority ?? '—'}</td>
                            <td className="py-3 px-4 text-sm text-gray-700 dark:text-gray-300 font-mono">{f?.match || '—'}</td>
                            <td className="py-3 px-4 text-sm text-gray-700 dark:text-gray-300 font-mono">{f?.actions || '—'}</td>
                            <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{f?.packet_count ?? '—'}</td>
                            <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{f?.byte_count ?? '—'}</td>
                            <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{f?.duration ?? '—'}</td>
                          </tr>
                        ))}
                        {!(selectedSwitchFlows.flows as any[]).length && (
                          <tr>
                            <td colSpan={6} className="py-8 text-center text-gray-500 dark:text-gray-400">
                              No flow entries
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex items-center justify-between">
                <CardTitle>Device Status</CardTitle>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  {deviceMetricRows.length} devices
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-800">
                        <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Device</th>
                        <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">CPU</th>
                        <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Memory</th>
                        <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">RX</th>
                        <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">TX</th>
                        <th className="text-right py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Errors</th>
                        <th className="text-left py-3 px-4 text-sm font-semibold text-gray-900 dark:text-white">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {deviceMetricRows.map((r) => (
                        <tr
                          key={r.name}
                          className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50"
                        >
                          <td className="py-3 px-4 text-sm font-medium text-gray-900 dark:text-white">{r.name}</td>
                          <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{r.cpu.toFixed(1)}%</td>
                          <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{r.mem.toFixed(1)}%</td>
                          <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{formatBytes(r.rx)}</td>
                          <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{formatBytes(r.tx)}</td>
                          <td className="py-3 px-4 text-sm text-right text-gray-700 dark:text-gray-300">{r.errors}</td>
                          <td className="py-3 px-4">
                            <Badge
                              variant={r.status === 'down' ? 'error' : r.status === 'warning' ? 'warning' : 'success'}
                              size="sm"
                            >
                              {r.status}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                      {!deviceMetricRows.length && (
                        <tr>
                          <td colSpan={7} className="py-8 text-center text-gray-500 dark:text-gray-400">
                            {isRunning ? 'Collecting metrics…' : 'Start the emulation to see metrics'}
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle>AI Network Health</CardTitle>
                <Button variant="primary" size="sm" onClick={runAiDiagnosis} isLoading={aiDiagnosing} disabled={!topologyId}>
                  Analyze
                </Button>
              </CardHeader>
              <CardContent>
                {!aiDiagnosis ? (
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    Generates a health summary (down devices, errors, bottlenecks) using live telemetry.
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div
                      className={cn(
                        'rounded-2xl border border-gray-200 dark:border-gray-800',
                        'bg-gradient-to-b from-white to-gray-50 dark:from-gray-950/50 dark:to-gray-900',
                        'px-4 py-4 space-y-4'
                      )}
                    >
                      <div className="flex justify-end">
                        <div className="max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-relaxed bg-blue-600 text-white whitespace-pre-wrap break-words">
                          Analyze network health
                        </div>
                      </div>
                      <div className="flex justify-start">
                        <div className="max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-relaxed bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100">
                          <MarkdownViewer value={aiDiagnosis} variant="plain" />
                        </div>
                      </div>
                      {aiDiagnosing && (
                        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/30 px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                          <div className="font-semibold">Thinking…</div>
                          <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                            Gathering telemetry and generating a diagnosis.
                          </div>
                        </div>
                      )}
                    </div>

                    {aiDiagnosisHeuristics && (
                      <details className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/40 px-4 py-3">
                        <summary className="cursor-pointer select-none text-sm font-semibold text-gray-800 dark:text-gray-200">
                          Diagnosis context
                        </summary>
                        <div className="mt-3">
                          <JsonViewer data={aiDiagnosisHeuristics} collapsed={2} />
                        </div>
                      </details>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {activeTab === 'hosts' && (
          <div className="animate-fade-in space-y-4">
            {hostDevices.length > 0 ? (
              hostDevices.map((device: any) => (
                <Card key={getDeviceKey(device)}>
                  <CardHeader>
                    <CardTitle>{device.name}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">IP Address</p>
                        <p className="font-mono text-gray-900 dark:text-white">{device.ip || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Status</p>
                        <Badge variant={device.status === 'active' ? 'success' : 'default'} size="sm">
                          {device.status || 'active'}
                        </Badge>
                      </div>
                      <div className="col-span-2">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            setSelectedDevice(getDeviceKey(device))
                            setActiveTab('terminal')
                          }}
                        >
                          Open Terminal
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            ) : (
              <Card>
                <CardContent>
                  <p className="text-center text-gray-600 dark:text-gray-400 py-8">
                    {isRunning ? 'No hosts found' : 'Start the emulation to see hosts'}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {activeTab === 'switches' && (
          <div className="animate-fade-in space-y-4">
            {switchDevices.length > 0 ? (
              switchDevices.map((device: any) => (
                <Card key={getDeviceKey(device)}>
                  <CardHeader>
                    <CardTitle>{device.name}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Type</p>
                        <p className="font-medium text-gray-900 dark:text-white capitalize">{device.device_type}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Status</p>
                        <Badge variant={device.status === 'active' ? 'success' : 'default'} size="sm">
                          {device.status || 'active'}
                        </Badge>
                      </div>
                      <div className="col-span-2">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            setSelectedDevice(getDeviceKey(device))
                            setActiveTab('terminal')
                          }}
                        >
                          Configure Switch
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            ) : (
              <Card>
                <CardContent>
                  <p className="text-center text-gray-600 dark:text-gray-400 py-8">
                    {isRunning ? 'No switches found' : 'Start the emulation to see switches'}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {activeTab === 'routers' && (
          <div className="animate-fade-in space-y-4">
            {routerDevices.length > 0 ? (
              routerDevices.map((device: any) => (
                <Card key={getDeviceKey(device)}>
                  <CardHeader>
                    <CardTitle>{device.name}</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">IP Address</p>
                        <p className="font-mono text-gray-900 dark:text-white">{device.ip || 'N/A'}</p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">Status</p>
                        <Badge variant={device.status === 'active' ? 'success' : 'default'} size="sm">
                          {device.status || 'active'}
                        </Badge>
                      </div>
                      <div className="col-span-2">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            setSelectedDevice(getDeviceKey(device))
                            setActiveTab('terminal')
                          }}
                        >
                          Open Terminal
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            ) : (
              <Card>
                <CardContent>
                  <p className="text-center text-gray-600 dark:text-gray-400 py-8">
                    {isRunning ? 'No routers found' : 'Start the emulation to see routers'}
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {activeTab === 'controllers' && (
          <ControllersTab
            controllersList={controllersList}
            controllersSummary={controllersSummary}
            controllerSearch={controllerSearch}
            setControllerSearch={setControllerSearch}
            setControllerConsole={setControllerConsole}
            setControllerOutput={setControllerOutput}
            selectedControllerId={selectedControllerId}
            setSelectedControllerId={setSelectedControllerId}
            selectedController={selectedController}
            controllerUiUrl={controllerUiUrl}
            controllerPane={controllerPane}
            setControllerPane={setControllerPane}
            controllerLifecycleMutation={controllerLifecycleMutation}
            controllerCommand={controllerCommand}
            setControllerCommand={setControllerCommand}
            controllerConsole={controllerConsole}
            execControllerMutation={execControllerMutation}
          />
        )}

        {activeTab === 'tests' && (
          <TopologyTests topologyId={topologyId} devices={runtimeDevices} isRunning={isRunning} />
        )}

		        {activeTab === 'config' && (
		          <div className="space-y-6">
                <Card>
                  <CardHeader>
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div>
                        <CardTitle>{t('network.configuration', 'Configuration')}</CardTitle>
	                        <p className="text-sm text-gray-600 dark:text-gray-400">
	                          Device tweaks, bulk network JSON, or cross-service control actions (MANO + SDN + Network).
	                        </p>
	                      </div>
	                    </div>
                      <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <button
                          type="button"
                          onClick={() => setConfigPane('control')}
                          className={cn(
                            'rounded-2xl border p-4 text-left transition-all',
                            'bg-gradient-to-br from-blue-50/70 via-white to-cyan-50/60 dark:from-blue-950/25 dark:via-gray-950 dark:to-cyan-950/20',
                            configPane === 'control'
                              ? 'border-blue-500/60 shadow-sm'
                              : 'border-gray-200 dark:border-gray-800 hover:border-blue-300/60 dark:hover:border-blue-800/50'
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-3">
                              <div className="h-10 w-10 rounded-xl bg-blue-600/10 dark:bg-blue-400/10 text-blue-700 dark:text-blue-300 flex items-center justify-center">
                                <Cog6ToothIcon className="h-5 w-5" />
                              </div>
                              <div>
                                <div className="text-sm font-semibold text-gray-900 dark:text-white">
                                  Control Config
                                </div>
                                <div className="text-xs text-gray-600 dark:text-gray-400">
                                  Guided actions (MANO + SDN + Network) + JSON mode.
                                </div>
                              </div>
                            </div>
                            {configPane === 'control' ? (
                              <Badge variant="primary" size="sm">
                                Active
                              </Badge>
                            ) : (
                              <Badge variant="info" size="sm">
                                Recommended
                              </Badge>
                            )}
                          </div>
                        </button>

                        <button
                          type="button"
                          onClick={() => setConfigPane('device')}
                          className={cn(
                            'rounded-2xl border p-4 text-left transition-all',
                            'bg-gradient-to-br from-purple-50/70 via-white to-indigo-50/60 dark:from-purple-950/25 dark:via-gray-950 dark:to-indigo-950/20',
                            configPane === 'device'
                              ? 'border-purple-500/60 shadow-sm'
                              : 'border-gray-200 dark:border-gray-800 hover:border-purple-300/60 dark:hover:border-purple-800/50'
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-3">
                              <div className="h-10 w-10 rounded-xl bg-purple-600/10 dark:bg-purple-400/10 text-purple-700 dark:text-purple-300 flex items-center justify-center">
                                <CpuChipIcon className="h-5 w-5" />
                              </div>
                              <div>
                                <div className="text-sm font-semibold text-gray-900 dark:text-white">Device</div>
                                <div className="text-xs text-gray-600 dark:text-gray-400">
                                  Per-device settings: IPs, routes, DNS, sysctls, startup commands.
                                </div>
                              </div>
                            </div>
                            {configPane === 'device' ? (
                              <Badge variant="primary" size="sm">
                                Active
                              </Badge>
                            ) : null}
                          </div>
                        </button>

                        <button
                          type="button"
                          onClick={() => setConfigPane('network')}
                          className={cn(
                            'rounded-2xl border p-4 text-left transition-all',
                            'bg-gradient-to-br from-emerald-50/70 via-white to-teal-50/60 dark:from-emerald-950/25 dark:via-gray-950 dark:to-teal-950/20',
                            configPane === 'network'
                              ? 'border-emerald-500/60 shadow-sm'
                              : 'border-gray-200 dark:border-gray-800 hover:border-emerald-300/60 dark:hover:border-emerald-800/50'
                          )}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-3">
                              <div className="h-10 w-10 rounded-xl bg-emerald-600/10 dark:bg-emerald-400/10 text-emerald-700 dark:text-emerald-300 flex items-center justify-center">
                                <ArrowDownTrayIcon className="h-5 w-5" />
                              </div>
                              <div>
                                <div className="text-sm font-semibold text-gray-900 dark:text-white">Network JSON</div>
                                <div className="text-xs text-gray-600 dark:text-gray-400">
                                  Full topology config as JSON (import/export + dry-run).
                                </div>
                              </div>
                            </div>
                            {configPane === 'network' ? (
                              <Badge variant="primary" size="sm">
                                Active
                              </Badge>
                            ) : null}
                          </div>
                        </button>
                      </div>
	                  </CardHeader>
	                  <CardContent>
	                    <div className="flex flex-wrap items-center gap-2">
	                      {topologyId ? (
                        <Badge variant="info" size="sm">
                          Topology: <span className="font-mono">{String(topologyId).slice(0, 8)}</span>
                        </Badge>
                      ) : (
                        <Badge variant="default" size="sm">
                          Select a topology
                        </Badge>
                      )}
                      <Badge variant={isRunning ? 'success' : 'default'} size="sm">
                        Emulation: {isRunning ? 'running' : 'stopped'}
                      </Badge>
                    </div>
                  </CardContent>
                </Card>

                {configPane === 'control' && (
                  <ControlConfigPanel
                    topologyId={topologyId}
                    emulationId={emulationId}
                    deviceNames={(runtimeDevices || []).map((d: any) => String(getRuntimeName(d) || '')).filter(Boolean)}
                    controllerIds={(controllersList || []).map((c: any) => String(c?.id || '')).filter(Boolean)}
                  />
                )}

                {configPane === 'device' && (
	            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{t('network.runtimeConfiguration', 'Runtime Configuration')}</CardTitle>
                  {selectedDeviceData && (
                    <Badge variant="primary" size="sm">
                      {selectedDeviceData.name}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                {runtimeDevices.length === 0 ? (
                  <p className="text-gray-600 dark:text-gray-400">
                    {isRunning
                      ? t('network.noDevices', 'No devices available to configure yet.')
                      : t('network.startEmulationForConfig', 'Start the emulation to configure devices.')}
                  </p>
                ) : (
                  <>
                    <div className="grid gap-4 md:grid-cols-2">
                      <div className="md:col-span-2">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                          {t('network.selectDevice', 'Select Device')}
                        </label>
                        <select
                          value={selectedDevice || ''}
                          onChange={(e) => setSelectedDevice(e.target.value)}
                          className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                        >
                          {runtimeDevices.map((device: any) => (
                            <option key={getDeviceKey(device)} value={getDeviceKey(device)}>
                              {device.name} ({getDeviceType(device)})
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          {t('network.deviceType', 'Device Type')}
                        </p>
                        <p className="font-medium text-gray-900 dark:text-white capitalize">
                          {selectedDeviceType || 'n/a'}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                          {t('network.status', 'Status')}
                        </p>
                        <Badge variant={isRunning ? 'success' : 'default'} size="sm">
                          {isRunning ? t('network.running') : t('network.stopped')}
                        </Badge>
                      </div>
                    </div>

                    {topologyId === DEMO_TOPOLOGY_ID && (
                      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-blue-50/60 dark:bg-blue-900/20 p-4">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <div>
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">
                              Demo config for this topology
                            </p>
                            <p className="text-xs text-gray-600 dark:text-gray-400">
                              Assigns `10.0.0.1/30` to `host-1-eth1`, `10.0.0.2/30` to `router-3-eth0`, plus `10.0.1.1/24` on `host-1-eth0`.
                            </p>
                          </div>
                          <Button
                            variant="primary"
                            size="sm"
                            onClick={applyDemoConfig}
                            isLoading={isApplyingDemoConfig}
                            disabled={!isRunning || isApplyingDemoConfig}
                          >
                            Apply Demo Config
                          </Button>
                        </div>
                        <div className="mt-3 text-xs text-gray-700 dark:text-gray-300 font-mono">
                          Test in Terminal: `ping -c 2 10.0.0.2` (from host) · `ping -c 2 10.0.0.1` (from router)
                        </div>
                      </div>
                    )}

                    {['host', 'router', 'container'].includes(selectedDeviceType) && (
                      <div className="space-y-4">
                        <div className="grid md:grid-cols-2 gap-4">
                          <div className="md:col-span-2">
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                              Interface (for runtime apply)
                            </label>
                            <select
                              value={ifaceSelection}
                              onChange={(e) => setIfaceSelection(e.target.value)}
                              className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                            >
                              <option value="">Auto-select</option>
                              {ifaceOptions.map((iface) => (
                                <option key={iface} value={iface}>
                                  {iface}
                                </option>
                              ))}
                            </select>
                            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                              Used for applying IP/MAC/MTU/gateway/routes to the running emulation.
                            </p>
                          </div>
                        </div>
                        <div className="grid md:grid-cols-2 gap-4">
                          <Input
                            label={t('topology.ipv4', 'IPv4 Address')}
                            value={configDraft.ip}
                            onChange={(e) => handleConfigChange('ip', e.target.value)}
                            placeholder="10.0.0.1/24"
                          />
                          <Input
                            label={t('topology.ipv6', 'IPv6 Address')}
                            value={configDraft.ip6}
                            onChange={(e) => handleConfigChange('ip6', e.target.value)}
                            placeholder="fd00::1/64"
                          />
                          <Input
                            label={t('topology.mac', 'MAC Address')}
                            value={configDraft.mac}
                            onChange={(e) => handleConfigChange('mac', e.target.value)}
                            placeholder="00:00:00:00:00:01"
                          />
                          <Input
                            label={t('topology.mtu', 'MTU')}
                            value={configDraft.mtu}
                            onChange={(e) => handleConfigChange('mtu', e.target.value)}
                            placeholder="1500"
                          />
                        </div>
                        <Input
                          label={t('topology.defaultGateway', 'Default Gateway')}
                          value={configDraft.default_route}
                          onChange={(e) => handleConfigChange('default_route', e.target.value)}
                          placeholder="10.0.0.254"
                        />
                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                              {t('topology.staticRoutes', 'Static Routes')}
                            </label>
                            <Button
                              variant="secondary"
                              size="sm"
                              type="button"
                              onClick={() => setRouteRows((prev) => [...prev, { dst: '', via: '', dev: '', metric: '' }])}
                            >
                              Add Route
                            </Button>
                          </div>
                          <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-800">
                            <table className="w-full">
                              <thead>
                                <tr className="border-b border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900">
                                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">
                                    Destination
                                  </th>
                                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">
                                    Gateway (via)
                                  </th>
                                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">
                                    Interface
                                  </th>
                                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">
                                    Metric
                                  </th>
                                  <th className="py-2 px-3" />
                                </tr>
                              </thead>
                              <tbody>
                                {routeRows.length ? (
                                  routeRows.map((row, idx) => (
                                    <tr key={idx} className="border-b border-gray-100 dark:border-gray-800">
                                      <td className="py-2 px-3">
                                        <input
                                          value={row.dst}
                                          onChange={(e) =>
                                            setRouteRows((prev) =>
                                              prev.map((r, i) => (i === idx ? { ...r, dst: e.target.value } : r))
                                            )
                                          }
                                          className="input w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800"
                                          placeholder="10.0.1.0/24 or default"
                                        />
                                      </td>
                                      <td className="py-2 px-3">
                                        <input
                                          value={row.via || ''}
                                          onChange={(e) =>
                                            setRouteRows((prev) =>
                                              prev.map((r, i) => (i === idx ? { ...r, via: e.target.value } : r))
                                            )
                                          }
                                          className="input w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800"
                                          placeholder="10.0.0.254"
                                        />
                                      </td>
                                      <td className="py-2 px-3">
                                        <select
                                          value={row.dev || ''}
                                          onChange={(e) =>
                                            setRouteRows((prev) =>
                                              prev.map((r, i) => (i === idx ? { ...r, dev: e.target.value } : r))
                                            )
                                          }
                                          className="input w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800"
                                        >
                                          <option value="">(auto)</option>
                                          {ifaceOptions.map((iface) => (
                                            <option key={iface} value={iface}>
                                              {iface}
                                            </option>
                                          ))}
                                        </select>
                                      </td>
                                      <td className="py-2 px-3">
                                        <input
                                          value={row.metric || ''}
                                          onChange={(e) =>
                                            setRouteRows((prev) =>
                                              prev.map((r, i) => (i === idx ? { ...r, metric: e.target.value } : r))
                                            )
                                          }
                                          className="input w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-800"
                                          placeholder="100"
                                        />
                                      </td>
                                      <td className="py-2 px-3 text-right">
                                        <Button
                                          variant="danger"
                                          size="sm"
                                          type="button"
                                          onClick={() => setRouteRows((prev) => prev.filter((_, i) => i !== idx))}
                                        >
                                          Remove
                                        </Button>
                                      </td>
                                    </tr>
                                  ))
                                ) : (
                                  <tr>
                                    <td colSpan={5} className="py-6 text-center text-sm text-gray-500 dark:text-gray-400">
                                      No routes configured
                                    </td>
                                  </tr>
                                )}
                              </tbody>
                            </table>
                          </div>
                        </div>

                        <div className="space-y-2">
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t('topology.dnsServers', 'DNS Servers')}
                          </label>
                          <div className="flex flex-wrap gap-2">
                            {dnsRows.map((dns, idx) => (
                              <span
                                key={`${dns}-${idx}`}
                                className="inline-flex items-center gap-2 rounded-full bg-gray-100 px-3 py-1 text-xs text-gray-700 dark:bg-gray-800 dark:text-gray-200"
                              >
                                <span className="font-mono">{dns}</span>
                                <button
                                  type="button"
                                  className="text-gray-500 hover:text-gray-900 dark:hover:text-white"
                                  onClick={() => setDnsRows((prev) => prev.filter((_, i) => i !== idx))}
                                >
                                  ×
                                </button>
                              </span>
                            ))}
                          </div>
                          <input
                            className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                            placeholder="8.8.8.8 (press Enter)"
                            onKeyDown={(e) => {
                              if (e.key !== 'Enter') return
                              const value = (e.currentTarget.value || '').trim()
                              if (!value) return
                              e.currentTarget.value = ''
                              setDnsRows((prev) => (prev.includes(value) ? prev : [...prev, value]))
                            }}
                          />
                        </div>

                        <div className="space-y-2">
                          <div className="flex items-center justify-between">
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                              {t('topology.startupCommands', 'Startup Commands')}
                            </label>
                            <Button
                              variant="secondary"
                              size="sm"
                              type="button"
                              onClick={() => setCommandRows((prev) => [...prev, ''])}
                            >
                              Add Command
                            </Button>
                          </div>
                          <div className="space-y-2">
                            {commandRows.length ? (
                              commandRows.map((cmd, idx) => (
                                <div key={idx} className="flex items-center gap-2">
                                  <input
                                    value={cmd}
                                    onChange={(e) =>
                                      setCommandRows((prev) =>
                                        prev.map((c, i) => (i === idx ? e.target.value : c))
                                      )
                                    }
                                    className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 font-mono text-sm"
                                    placeholder="ip addr show"
                                  />
                                  <Button
                                    variant="danger"
                                    size="sm"
                                    type="button"
                                    onClick={() => setCommandRows((prev) => prev.filter((_, i) => i !== idx))}
                                  >
                                    Remove
                                  </Button>
                                </div>
                              ))
                            ) : (
                              <div className="text-sm text-gray-500 dark:text-gray-400">No commands</div>
                            )}
                          </div>
                        </div>
                        {selectedDeviceType === 'router' && (
                          <div className="grid md:grid-cols-2 gap-4">
                            <div className="space-y-2">
                              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                {t('topology.routingDaemon', 'Routing Daemon')}
                              </label>
                              <select
                                value={configDraft.router_daemon || 'frr'}
                                onChange={(e) => handleConfigChange('router_daemon', e.target.value)}
                                className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                              >
                                <option value="frr">FRR</option>
                                <option value="bird">BIRD</option>
                                <option value="quagga">Quagga</option>
                              </select>
                            </div>
                            <div className="md:col-span-2 space-y-2">
                              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                {t('topology.routingProtocols', 'Routing Protocols')}
                              </label>
                              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                                {['ospf', 'bgp', 'rip', 'isis', 'static'].map((proto) => {
                                  const current = splitLines(configDraft.protocols)
                                  const checked = current.includes(proto)
                                  return (
                                    <label key={proto} className="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                                      <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) => {
                                          const next = e.target.checked
                                            ? Array.from(new Set([...current, proto]))
                                            : current.filter((p) => p !== proto)
                                          handleConfigChange('protocols', next.join('\n'))
                                        }}
                                        className="h-4 w-4 rounded border-gray-300 dark:border-gray-600"
                                      />
                                      <span className="uppercase">{proto}</span>
                                    </label>
                                  )
                                })}
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {['switch', 'p4switch'].includes(selectedDeviceType) && (
                      <div className="grid md:grid-cols-2 gap-4">
                        <Input
                          label={t('topology.controllerEndpoint', 'Controller Endpoint')}
                          value={configDraft.controller}
                          onChange={(e) => handleConfigChange('controller', e.target.value)}
                          placeholder="127.0.0.1:6653"
                        />
                        <div className="space-y-2">
                          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                            {t('topology.openflowVersion', 'OpenFlow Version')}
                          </label>
                          <select
                            value={configDraft.openflow_version || '1.3'}
                            onChange={(e) => handleConfigChange('openflow_version', e.target.value)}
                            className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                          >
                            <option value="1.0">1.0</option>
                            <option value="1.3">1.3</option>
                            <option value="1.5">1.5</option>
                          </select>
                        </div>
                      </div>
                    )}

                    {selectedDeviceType === 'p4switch' && (
                      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 p-4 space-y-3">
                        <div className="flex items-center justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">P4 Switch</p>
                            <p className="text-xs text-gray-600 dark:text-gray-400">
                              Values come from the topology node properties.
                            </p>
                          </div>
                          <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => navigate(`/topology/${topologyId}`)}
                          >
                            Open P4 Editor
                          </Button>
                        </div>

                        <div className="grid gap-3 sm:grid-cols-2">
                          <div>
                            <p className="text-xs text-gray-600 dark:text-gray-400">p4_program_id</p>
                            <p className="font-mono text-sm text-gray-900 dark:text-white">
                              {selectedTopologyNodeProps.p4_program_id || '—'}
                            </p>
                          </div>
                          <div>
                            <p className="text-xs text-gray-600 dark:text-gray-400">runtime_address</p>
                            <p className="font-mono text-sm text-gray-900 dark:text-white">
                              {selectedTopologyNodeProps.runtime_address || '—'}
                            </p>
                          </div>
                          <div className="sm:col-span-2">
                            <p className="text-xs text-gray-600 dark:text-gray-400">device_config_path</p>
                            <p className="font-mono text-sm text-gray-900 dark:text-white break-all">
                              {selectedTopologyNodeProps.device_config_path || '—'}
                            </p>
                          </div>
                          <div className="sm:col-span-2">
                            <p className="text-xs text-gray-600 dark:text-gray-400">p4info_path</p>
                            <p className="font-mono text-sm text-gray-900 dark:text-white break-all">
                              {selectedTopologyNodeProps.p4info_path || '—'}
                            </p>
                          </div>
                        </div>

                        {selectedTopologyNodeProps.p4_program_id && (
                          <a
                            className="text-sm text-blue-600 dark:text-blue-400 hover:underline font-mono"
                            href={`/api/p4/programs/${selectedTopologyNodeProps.p4_program_id}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            /api/p4/programs/{selectedTopologyNodeProps.p4_program_id}
                          </a>
                        )}
                      </div>
                    )}

                    {!['host', 'router', 'container', 'switch', 'p4switch'].includes(selectedDeviceType) && (
                      <p className="text-sm text-gray-600 dark:text-gray-400">
                        {t('network.configurationUnsupported', 'Configuration updates are not available for this device type yet.')}
                      </p>
                    )}

                    {configFeedback && (
                      <div
                        className={`text-sm ${
                          configFeedback.type === 'success' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                        }`}
                      >
                        {configFeedback.message}
                      </div>
                    )}

                    <div className="flex items-center justify-end gap-3 pt-4 border-t border-gray-200 dark:border-gray-800">
                      {!isRunning && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {t('network.startEmulationForConfig', 'Start the emulation to apply configuration changes.')}
                        </span>
                      )}
                      <Button
                        variant="primary"
                        onClick={handleApplyConfig}
                        isLoading={isApplyingConfig}
                        disabled={!isRunning || isApplyingConfig || !selectedDeviceData}
                      >
                        {t('network.applyConfiguration', 'Apply Configuration')}
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          )}

            {configPane === 'network' && (
            <Card>
              <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <CardTitle>{t('network.jsonConfiguration', 'Network Configuration (JSON)')}</CardTitle>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Import/export a reusable configuration and apply it to the running emulation.
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button variant="secondary" size="sm" onClick={handleLoadConfigTemplate} disabled={!topologyId}>
                    Load Template
                  </Button>
                  <Button variant="secondary" size="sm" onClick={handleLoadSavedConfig} disabled={!topologyId}>
                    Load Saved
                  </Button>
                  <Button variant="secondary" size="sm" onClick={handleExportNetworkConfig} disabled={!topologyId}>
                    Export
                  </Button>
                  <input
                    ref={networkConfigFileInputRef}
                    type="file"
                    accept="application/json,.json"
                    className="hidden"
                    onChange={(e) => {
                      const file = e.target.files?.[0] || null
                      e.currentTarget.value = ''
                      void handleImportNetworkConfigFile(file)
                    }}
                  />
                  <Button
                    variant="secondary"
                    size="sm"
                    type="button"
                    onClick={() => networkConfigFileInputRef.current?.click()}
                  >
                    Import
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <Input
                    label={t('common.name', 'Name')}
                    value={networkConfigName}
                    onChange={(e) => setNetworkConfigName(e.target.value)}
                    placeholder="My network config"
                  />
                  <Input
                    label={t('common.description', 'Description')}
                    value={networkConfigDescription}
                    onChange={(e) => setNetworkConfigDescription(e.target.value)}
                    placeholder="Interfaces, IPs, routes…"
                  />
                </div>

                <div className="flex items-center justify-between gap-3">
                  <label className="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                    <input
                      type="checkbox"
                      checked={networkConfigDryRun}
                      onChange={(e) => setNetworkConfigDryRun(e.target.checked)}
                      className="h-4 w-4 rounded border-gray-300 dark:border-gray-600"
                    />
                    Dry run (validate + show steps)
                  </label>
                  <div className="flex items-center gap-2">
                    <Button variant="secondary" onClick={handleSaveNetworkConfig} disabled={!topologyId}>
                      Save
                    </Button>
                    <Button
                      variant="primary"
                      onClick={handleApplyNetworkConfig}
                      disabled={!topologyId || !isRunning}
                    >
                      Apply to Running Network
                    </Button>
                  </div>
                </div>

                <textarea
                  value={networkConfigText}
                  onChange={(e) => setNetworkConfigText(e.target.value)}
                  className="w-full h-[520px] rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-mono text-sm p-4 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                  spellCheck={false}
                />

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Preview</div>
                    {networkConfigPreview.error && (
                      <div className="text-xs text-red-600 dark:text-red-400">{networkConfigPreview.error}</div>
                    )}
                  </div>
                  {networkConfigPreview.data ? (
                    <JsonViewer data={networkConfigPreview.data} collapsed={2} />
                  ) : (
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      Enter valid JSON to preview.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
            )}
	          </div>
	        )}

	        {activeTab === 'topology-export' && (
	          <div className="animate-fade-in space-y-6">
	            <Card>
	              <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
	                <div>
	                  <CardTitle>Topology Export (Python)</CardTitle>
	                  <p className="text-sm text-gray-600 dark:text-gray-400">
	                    Generate Mininet / Mininet-WiFi / Containernet scripts from this topology and download the file.
	                  </p>
	                </div>
	                <div className="flex flex-wrap items-center gap-2">
	                  <select
	                    value={topologyExportFormat}
	                    onChange={(e) => setTopologyExportFormat(e.target.value as typeof topologyExportFormat)}
	                    className="input px-3 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
	                    disabled={!topologyId}
	                  >
	                    <option value="mininet">Mininet</option>
	                    <option value="mininet-wifi">Mininet-WiFi</option>
	                    <option value="containernet">Containernet</option>
	                  </select>
	                  <Button
	                    variant="secondary"
	                    size="sm"
	                    onClick={handleRefreshTopologyExport}
	                    disabled={!topologyId}
	                    isLoading={topologyExportQuery.isFetching}
	                  >
	                    Refresh
	                  </Button>
	                  <Button
	                    variant="secondary"
	                    size="sm"
	                    onClick={handleCopyTopologyExport}
	                    disabled={!topologyExportQuery.data?.content}
	                  >
	                    Copy
	                  </Button>
	                  <Button
	                    variant="primary"
	                    size="sm"
	                    onClick={handleDownloadTopologyExport}
	                    disabled={!topologyId}
	                    isLoading={topologyExportQuery.isFetching}
	                  >
	                    Export
	                  </Button>
	                </div>
	              </CardHeader>
	              <CardContent className="space-y-3">
	                {!topologyId ? (
	                  <div className="text-sm text-gray-600 dark:text-gray-400">Select a topology to export.</div>
	                ) : (
	                  <>
	                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-gray-500 dark:text-gray-400">
	                      <div className="font-mono">
	                        {topologyExportQuery.data?.filename
	                          ? `File: ${topologyExportQuery.data.filename}`
	                          : topologyExportQuery.isFetching
	                            ? 'Loading script…'
	                            : 'Click Refresh to load the script.'}
	                      </div>
	                      <div className="font-mono">
	                        Format: {topologyExportFormat}
	                        {topologyExportQuery.data?.timestamp ? ` • ${topologyExportQuery.data.timestamp}` : ''}
	                      </div>
	                    </div>
	                    <div className="h-[680px] overflow-hidden rounded-xl border border-gray-300 dark:border-gray-800">
	                      <Editor
	                        height="680px"
	                        defaultLanguage="python"
	                        value={topologyExportQuery.data?.content || ''}
	                        theme={theme === 'light' ? 'vs' : 'vs-dark'}
	                        loading="Loading editor..."
	                        options={{
	                          readOnly: true,
	                          minimap: { enabled: true },
	                          fontSize: 13,
	                          lineNumbers: 'on',
	                          wordWrap: 'off',
	                          automaticLayout: true,
	                          scrollBeyondLastLine: false,
	                          folding: true,
	                          renderWhitespace: 'selection',
	                        }}
	                      />
	                    </div>
	                  </>
	                )}
	              </CardContent>
	            </Card>
	          </div>
	        )}

	        {activeTab === 'algorithms' && (
		          <div className="animate-fade-in space-y-6">
		            <Card padding="none" className="overflow-hidden">
		              <div className="p-6 border-b border-gray-200 dark:border-gray-800 bg-gradient-to-br from-white to-blue-50 dark:from-gray-900 dark:to-gray-900">
		                <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
		                  <div className="space-y-1">
		                    <div className="flex flex-wrap items-center gap-2">
		                      <CardTitle>Algorithms</CardTitle>
		                      {!isRunning ? (
		                        <Badge variant="warning" size="sm" withIcon>
		                          Emulation stopped
		                        </Badge>
		                      ) : (
		                        <Badge variant="success" size="sm" withIcon>
		                          Emulation running
		                        </Badge>
		                      )}
		                      {algoRunQuery.data?.status ? (
		                        <Badge
		                          variant={
		                            String(algoRunQuery.data.status).toLowerCase() === 'running'
		                              ? 'info'
		                              : String(algoRunQuery.data.status).toLowerCase() === 'stopped'
		                                ? 'success'
		                                : 'default'
		                          }
		                          size="sm"
		                        >
		                          {String(algoRunQuery.data.status).toUpperCase()}
		                        </Badge>
		                      ) : algoRunId ? (
		                        <Badge variant="default" size="sm">
		                          RUN: <span className="font-mono">{algoRunId.slice(0, 8)}</span>
		                        </Badge>
		                      ) : (
		                        <Badge variant="default" size="sm">
		                          NO RUN
		                        </Badge>
		                      )}
		                    </div>
		                    <div className="text-sm text-gray-600 dark:text-gray-400">
		                      {(() => {
		                        const tpl = getAlgorithmTemplate(algoTemplateId)
		                        return (
		                          <>
		                            <span className="font-semibold text-gray-900 dark:text-gray-100">{tpl.name}</span>
		                            {tpl.description ? <span className="text-gray-500 dark:text-gray-400"> — {tpl.description}</span> : null}
		                          </>
		                        )
		                      })()}
		                    </div>
		                  </div>
		                  <div className="flex flex-wrap items-center gap-2">
		                    <Button
		                      variant="outline"
		                      size="sm"
		                      onClick={() => topologyId && navigate(`/topology-editor/${topologyId}`)}
		                      disabled={!topologyId}
		                    >
		                      Topology editor
		                    </Button>
		                  </div>
		                </div>
		              </div>
			              <CardContent className="p-6 space-y-4">
			                <div className="grid grid-cols-1 xl:grid-cols-12 gap-4">
			                  <div className="xl:col-span-4">
			                    <div className="space-y-4 xl:sticky xl:top-4">
			                      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-4">
			                        <div className="flex items-center justify-between gap-2">
			                          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Control center</div>
			                          <Badge variant={isRunning ? 'success' : 'warning'} size="sm" withIcon>
			                            {isRunning ? 'Ready' : 'Emulation off'}
			                          </Badge>
			                        </div>

			                        <div className="space-y-2">
			                          <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Template</div>
			                          <Select
			                            value={algoTemplateId as any}
			                            onChange={(v) => setAlgoTemplateId(v as any)}
			                            options={ALGORITHM_TEMPLATES.map((tpl) => ({
			                              value: tpl.id,
			                              label: tpl.name,
			                              description: tpl.description || undefined,
			                            }))}
			                          />
			                          <div className="text-[11px] text-gray-500 dark:text-gray-400">
			                            {getAlgorithmTemplate(algoTemplateId).description || '—'}
			                          </div>
			                        </div>

			                        <div className="grid grid-cols-2 gap-2">
			                          <div className="space-y-2">
			                            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Transport</div>
			                            <Select
			                              value={algoTransport as any}
			                              onChange={(v) => setAlgoTransport(v as any)}
			                              options={[
			                                { value: 'udp', label: 'UDP', description: 'Fast, low overhead (recommended)' },
			                                { value: 'tcp', label: 'TCP', description: 'Reliable, ordered delivery' },
			                              ]}
			                            />
			                          </div>
			                          <Input
			                            label="Port"
			                            type="number"
			                            value={algoListenPort}
			                            onChange={(e) => setAlgoListenPort(Number(e.target.value) || 50000)}
			                            placeholder="50000"
			                          />
			                        </div>

			                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
			                          <label className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-3 py-2">
			                            <div className="text-xs font-medium text-gray-700 dark:text-gray-300">Live updates</div>
			                            <input
			                              type="checkbox"
			                              className="h-4 w-4"
			                              checked={algoLiveUpdatesEnabled}
			                              onChange={(e) => setAlgoLiveUpdatesEnabled(e.target.checked)}
			                            />
			                          </label>
			                          <label className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-3 py-2">
			                            <div className="text-xs font-medium text-gray-700 dark:text-gray-300">Trace messages</div>
			                            <input
			                              type="checkbox"
			                              className="h-4 w-4"
			                              checked={algoTraceMessagesEnabled}
			                              onChange={(e) => setAlgoTraceMessagesEnabled(e.target.checked)}
			                            />
			                          </label>
			                          <label className="flex items-center justify-between gap-3 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-3 py-2 sm:col-span-2">
			                            <div className="text-xs font-medium text-gray-700 dark:text-gray-300">Include payload</div>
			                            <input
			                              type="checkbox"
			                              className="h-4 w-4"
			                              checked={algoTracePayloadEnabled}
			                              onChange={(e) => setAlgoTracePayloadEnabled(e.target.checked)}
			                              disabled={!algoTraceMessagesEnabled}
			                            />
			                          </label>
			                        </div>

			                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
			                          <Button
			                            variant="primary"
			                            size="sm"
			                            onClick={() => startAlgoMutation.mutate()}
			                            disabled={!topologyId || !isRunning || startAlgoMutation.isPending}
			                            isLoading={startAlgoMutation.isPending}
			                            leftIcon={<PlayIcon className="w-4 h-4" />}
			                            fullWidth
			                          >
			                            Run
			                          </Button>
			                          <Button
			                            variant="secondary"
			                            size="sm"
			                            onClick={() => stopAlgoMutation.mutate()}
			                            disabled={
			                              !algoRunId || stopAlgoMutation.isPending || String(algoRunQuery.data?.status || '').toLowerCase() === 'stopped'
			                            }
			                            isLoading={stopAlgoMutation.isPending}
			                            fullWidth
			                          >
			                            Stop
			                          </Button>
			                        </div>
			                      </div>

			                      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-4">
			                        <div className="flex items-center justify-between gap-2">
			                          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Live run</div>
			                          {algoRunQuery.data?.persisting_to_influx ? (
			                            <Badge variant="info" size="sm" isLoading>
			                              Saving
			                            </Badge>
			                          ) : algoRunQuery.data?.persisted_to_influx ? (
			                            <Badge variant="success" size="sm" withIcon>
			                              Saved
			                            </Badge>
			                          ) : algoRunQuery.data?.persist_error ? (
			                            <Badge variant="warning" size="sm" withIcon>
			                              Influx error
			                            </Badge>
			                          ) : (
			                            <Badge variant="default" size="sm">
			                              Influx
			                            </Badge>
			                          )}
			                        </div>

			                        <div className="flex flex-wrap items-center gap-2">
			                          <Badge
			                            variant={
			                              String(algoRunQuery.data?.status || '').toLowerCase() === 'running'
			                                ? 'info'
			                                : String(algoRunQuery.data?.status || '').toLowerCase() === 'stopped'
			                                  ? 'success'
			                                  : 'default'
			                            }
			                            size="sm"
			                          >
			                            {algoRunQuery.data?.status ? String(algoRunQuery.data.status).toUpperCase() : 'NO RUN'}
			                          </Badge>
			                          <Badge variant="default" size="sm">
			                            Run: <span className="font-mono">{algoRunId ? algoRunId.slice(0, 8) : '—'}</span>
			                          </Badge>
			                          <Badge variant="default" size="sm">
			                            Duration: <span className="font-mono">{algoRunDurationLabel || '—'}</span>
			                          </Badge>
			                        </div>

			                        <div className="grid grid-cols-2 gap-3">
			                          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3">
			                            <div className="text-[11px] text-gray-500 dark:text-gray-400">Nodes</div>
			                            <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{algoNodeTableRows.length || 0}</div>
			                          </div>
			                          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3">
			                            <div className="text-[11px] text-gray-500 dark:text-gray-400">Events</div>
			                            <div className="text-lg font-bold text-gray-900 dark:text-gray-100">{algoEvents.length}</div>
			                          </div>
			                          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3">
			                            <div className="text-[11px] text-gray-500 dark:text-gray-400">Net Δ packets</div>
			                            <div className="text-lg font-bold text-gray-900 dark:text-gray-100">
			                              {algoMetricsDelta ? algoMetricsDelta.totalPackets : '—'}
			                            </div>
			                          </div>
			                          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3">
			                            <div className="text-[11px] text-gray-500 dark:text-gray-400">Msgs (out/in)</div>
			                            <div className="text-lg font-bold text-gray-900 dark:text-gray-100">
			                              {algoMessageTotals.out}/{algoMessageTotals.in}
			                            </div>
			                          </div>
			                        </div>

			                        {Array.isArray(algoRunQuery.data?.errors) && algoRunQuery.data.errors.length > 0 && (
			                          <div className="max-h-[140px] overflow-auto rounded-xl bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-3">
			                            <div className="text-xs font-semibold text-red-700 dark:text-red-300 mb-2">Errors</div>
			                            <ul className="space-y-1">
			                              {algoRunQuery.data.errors.slice(-10).map((e: string, idx: number) => (
			                                <li key={idx} className="text-[11px] text-red-700 dark:text-red-300 font-mono">
			                                  {e}
			                                </li>
			                              ))}
			                            </ul>
			                          </div>
			                        )}
			                      </div>
			                    </div>
			                  </div>

			                  <div className="xl:col-span-8 space-y-4">
			                    <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3">
			                      <div className="flex flex-wrap gap-2">
			                        <button
			                          type="button"
			                          onClick={() => setAlgoUiTab('metrics')}
			                          className={cn(
			                            'px-3 py-1.5 text-sm font-medium rounded-full transition-colors flex items-center gap-2',
			                            algoUiTab === 'metrics'
			                              ? 'bg-blue-600 text-white shadow-sm'
			                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'
			                          )}
			                        >
			                          <ChartBarIcon className="w-4 h-4" />
			                          Dashboard
			                        </button>
			                        <button
			                          type="button"
			                          onClick={() => setAlgoUiTab('graph')}
			                          className={cn(
			                            'px-3 py-1.5 text-sm font-medium rounded-full transition-colors flex items-center gap-2',
			                            algoUiTab === 'graph'
			                              ? 'bg-blue-600 text-white shadow-sm'
			                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'
			                          )}
			                        >
			                          <WifiIcon className="w-4 h-4" />
			                          Graph
			                        </button>
			                        <button
			                          type="button"
			                          onClick={() => setAlgoUiTab('events')}
			                          className={cn(
			                            'px-3 py-1.5 text-sm font-medium rounded-full transition-colors flex items-center gap-2',
			                            algoUiTab === 'events'
			                              ? 'bg-blue-600 text-white shadow-sm'
			                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'
			                          )}
			                        >
			                          <ChatBubbleLeftRightIcon className="w-4 h-4" />
			                          Messages
			                        </button>
			                        <button
			                          type="button"
			                          onClick={() => setAlgoUiTab('editors')}
			                          className={cn(
			                            'px-3 py-1.5 text-sm font-medium rounded-full transition-colors flex items-center gap-2',
			                            algoUiTab === 'editors'
			                              ? 'bg-blue-600 text-white shadow-sm'
			                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'
			                          )}
			                        >
			                          <CodeBracketIcon className="w-4 h-4" />
			                          Code
			                        </button>
			                        <button
			                          type="button"
			                          onClick={() => setAlgoUiTab('history')}
			                          className={cn(
			                            'px-3 py-1.5 text-sm font-medium rounded-full transition-colors flex items-center gap-2',
			                            algoUiTab === 'history'
			                              ? 'bg-blue-600 text-white shadow-sm'
			                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'
			                          )}
			                        >
			                          <ClockIcon className="w-4 h-4" />
			                          History
			                        </button>
			                      </div>
			                    </div>

			                    {!isRunning && (
			                      <div className="rounded-2xl border border-yellow-200 dark:border-yellow-900/40 bg-yellow-50 dark:bg-yellow-900/20 p-4 text-sm text-yellow-800 dark:text-yellow-200">
			                        Start the emulation to run algorithms.
			                      </div>
			                    )}

		                    {algoUiTab === 'graph' && (
		                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
		                        <div className="lg:col-span-2 space-y-2">
		                          <div className="flex items-center justify-between gap-2">
                            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Discovered Graph</div>
		                            <div className="flex items-center gap-2">
		                              <Badge variant="default" size="sm">
		                                BLACK
		                              </Badge>
		                              <Badge variant="default" size="sm">
		                                GRAY
		                              </Badge>
		                              <Badge variant="default" size="sm">
		                                WHITE
		                              </Badge>
		                            </div>
		                          </div>
		                          <div className="h-[520px] overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
		                            {algoGraphNodes.length ? (
		                              <ReactFlow
		                                nodes={algoGraphNodes}
		                                edges={algoGraphEdges}
		                                nodeTypes={algorithmPreviewNodeTypes}
		                                nodesDraggable={false}
		                                nodesConnectable={false}
		                                elementsSelectable
		                                zoomOnScroll
		                                panOnScroll
		                                fitView
		                              >
		                                <Background />
		                                <MiniMap pannable zoomable />
		                                <Controls showInteractive={false} />
		                              </ReactFlow>
		                            ) : (
		                              <div className="h-full flex items-center justify-center text-sm text-gray-500 dark:text-gray-400">
		                                Run an algorithm to render the algorithm graph.
		                              </div>
		                            )}
		                          </div>
		                        </div>

			                        <div className="space-y-2">
			                          <div className="flex items-center justify-between gap-2">
			                            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Node Results</div>
			                            <Badge variant="default" size="sm">
			                              {algoNodeTableRowsFiltered.length}
			                            </Badge>
			                          </div>
			                          <Input
			                            value={algoNodeSearch}
			                            onChange={(e) => setAlgoNodeSearch(e.target.value)}
			                            placeholder="Filter nodes (id / name / status / role)…"
			                          />
			                          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
			                            <div className="max-h-[520px] overflow-auto">
			                              <table className="w-full text-sm">
			                                <thead className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
			                                  <tr>
			                                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Algo</th>
			                                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Node</th>
			                                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Nbs</th>
			                                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Status</th>
			                                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Role</th>
			                                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Out</th>
			                                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">In</th>
			                                  </tr>
			                                </thead>
			                                <tbody>
			                                  {algoNodeTableRowsFiltered.length ? (
			                                    algoNodeTableRowsFiltered.map((r) => (
			                                      <tr key={r.algoId} className="border-b border-gray-100 dark:border-gray-800">
			                                        <td className="py-2 px-3 font-mono text-xs text-gray-900 dark:text-gray-100">
			                                          {r.algoId}
			                                        </td>
			                                        <td className="py-2 px-3 font-mono text-[11px] text-gray-700 dark:text-gray-300">
			                                          {r.nodeId}
			                                        </td>
			                                        <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{String(r.neighbors)}</td>
			                                        <td className="py-2 px-3">
			                                          <Badge
			                                            variant={r.status === 'started' ? 'info' : r.status === 'skipped' ? 'warning' : 'default'}
			                                            size="sm"
			                                          >
			                                            {String(r.status).toUpperCase()}
			                                          </Badge>
			                                        </td>
			                                        <td className="py-2 px-3">
			                                          {(() => {
			                                            const c = String(r.color || '').toUpperCase()
			                                            const variant =
			                                              c === 'BS' || c === 'BASE_STATION'
			                                                ? 'error'
			                                                : c === 'CH'
			                                                  ? 'info'
			                                                  : c === 'LEADER' || c === 'CHAIN_LEADER'
			                                                    ? 'primary'
			                                                    : c === 'SENSOR'
			                                                      ? 'success'
			                                                      : c === 'LOW'
			                                                        ? 'warning'
			                                                        : c === 'CRITICAL'
			                                                          ? 'error'
			                                                          : c === 'DEAD'
			                                                            ? 'default'
			                                                            : 'default'
			                                            return (
			                                              <Badge variant={variant as any} size="sm">
			                                                {c || '—'}
			                                              </Badge>
			                                            )
			                                          })()}
			                                        </td>
			                                        <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{String(r.outMsgs)}</td>
			                                        <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{String(r.inMsgs)}</td>
			                                      </tr>
			                                    ))
			                                  ) : (
			                                    <tr>
			                                      <td colSpan={7} className="py-8 text-center text-xs text-gray-500 dark:text-gray-400">
			                                        No node results yet.
			                                      </td>
			                                    </tr>
			                                  )}
		                                </tbody>
		                              </table>
		                            </div>
		                          </div>
		                        </div>
		                      </div>
		                    )}

		                    {algoUiTab === 'metrics' && (
		                      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
		                        <div className="lg:col-span-2 space-y-3">
			                          <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
			                            <div className="flex items-center justify-between gap-2 mb-3">
                                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Network Δ (Mininet metrics)</div>
                                  <div className="flex items-center gap-2">
                                    <Badge variant="default" size="sm">
                                      Source: monitoring-service
                                    </Badge>
                                    {!algoLiveUpdatesEnabled ? (
                                      <Badge variant="warning" size="sm" withIcon>
                                        Live updates off
                                      </Badge>
                                    ) : algoRunIsStopped ? (
                                      <Badge variant="success" size="sm" withIcon>
                                        Run stopped • polling paused
                                      </Badge>
                                    ) : (
			                                  <Badge variant="info" size="sm">
			                                    Live
			                                  </Badge>
			                                )}
			                              </div>
			                            </div>
			                            {algoNetSeries.length ? (
			                              <div className="h-[260px]">
			                                <ResponsiveContainer width="100%" height="100%">
			                                  <LineChart data={algoNetSeries}>
			                                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
			                                    <XAxis dataKey="ts" tick={{ fontSize: 11 }} />
			                                    <YAxis yAxisId="pkts" tick={{ fontSize: 11 }} />
			                                    <YAxis yAxisId="bytes" orientation="right" tick={{ fontSize: 11 }} />
			                                    <Tooltip />
			                                    <Legend />
			                                    <Line
			                                      yAxisId="pkts"
			                                      type="monotone"
			                                      dataKey="rxPacketsDelta"
			                                      name="Δ RX packets"
			                                      stroke="#22c55e"
			                                      strokeWidth={2}
			                                      dot={false}
			                                    />
			                                    <Line
			                                      yAxisId="pkts"
			                                      type="monotone"
			                                      dataKey="txPacketsDelta"
			                                      name="Δ TX packets"
			                                      stroke="#3b82f6"
			                                      strokeWidth={2}
			                                      dot={false}
			                                    />
			                                    <Line
			                                      yAxisId="bytes"
			                                      type="monotone"
			                                      dataKey="bytesDelta"
			                                      name="Δ bytes"
			                                      stroke="#a855f7"
			                                      strokeWidth={2}
			                                      dot={false}
			                                    />
			                                  </LineChart>
			                                </ResponsiveContainer>
			                              </div>
			                            ) : (
			                              <div className="text-sm text-gray-500 dark:text-gray-400">Start a run to collect chart data.</div>
			                            )}
		                            <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 mt-4">
		                              <MetricCard title="Packets rate" value={algoTopologyMetrics?.packets ?? '—'} variant="primary" />
		                              <MetricCard title="Δ packets" value={algoMetricsDelta ? String(algoMetricsDelta.totalPackets) : '—'} variant="success" />
		                              <MetricCard title="Δ bytes" value={algoMetricsDelta ? String(algoMetricsDelta.totalBytes) : '—'} variant="warning" />
		                              <MetricCard title="Algo msgs out" value={String(algoMessageTotals.out)} variant="primary" />
		                              <MetricCard title="Algo msgs in" value={String(algoMessageTotals.in)} variant="default" />
		                            </div>
				                            <div className="mt-3 text-[11px] text-gray-500 dark:text-gray-400">
				                              Real interface counters aggregated by the monitoring pipeline; background traffic can affect totals. Live polling stops when the run
				                              stops.
				                            </div>
				                          </div>
				                          <AlgoMessageTimelineChart
				                            events={algoNetEvents}
				                            runStartedAt={Number((algoRunQuery.data as any)?.created_at) || null}
				                          />
				                          <AlgoNodeStatsCharts rows={algoNodeTableRows} formatNodeLabel={formatAlgoNodeLabel} />
	                                {(String(algoTemplateId || '').startsWith('wsn-') || algoHasWsnMetrics) && (
	                                  <WSNDashboard templateId={algoTemplateId} events={algoSystemEvents} />
	                                )}
			                        </div>
		                        <div className="space-y-3">
		                          <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
		                            <div className="flex items-center justify-between gap-2 mb-2">
		                              <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Validation</div>
		                              {String(algoRunQuery.data?.status || '').toLowerCase() === 'stopped' ? (
		                                algoValidateQuery.data?.ok ? (
		                                  <Badge variant="success" size="sm" withIcon>
		                                    OK
		                                  </Badge>
		                                ) : (
		                                  <Badge variant="warning" size="sm" withIcon>
		                                    FAIL
		                                  </Badge>
		                                )
		                              ) : (
		                                <Badge variant="default" size="sm">
		                                  Waiting
		                                </Badge>
		                              )}
		                            </div>
		                            {String(algoRunQuery.data?.status || '').toLowerCase() !== 'stopped' ? (
		                              <div className="text-xs text-gray-500 dark:text-gray-400">
		                                Validation runs after the algorithm stops.
		                              </div>
		                            ) : algoValidateQuery.isFetching ? (
		                              <div className="text-xs text-gray-500 dark:text-gray-400">Validating…</div>
		                            ) : algoValidateQuery.data?.checks?.length ? (
		                              <div className="space-y-2">
		                                <div className="space-y-1">
		                                  {algoValidateQuery.data.checks.slice(0, 6).map((c: any) => (
		                                    <div key={String(c?.name || Math.random())} className="flex items-center justify-between gap-3 text-xs">
		                                      <div className="text-gray-700 dark:text-gray-300">{String(c?.name || 'check')}</div>
		                                      <Badge variant={c?.ok ? 'success' : 'warning'} size="sm">
		                                        {c?.ok ? 'OK' : 'FAIL'}
		                                      </Badge>
		                                    </div>
		                                  ))}
		                                </div>
		                                <div className="text-[11px] text-gray-500 dark:text-gray-400">
		                                  Based on the discovered neighbor graph (HELLO/ACK events).
		                                </div>
		                              </div>
		                            ) : (
		                              <div className="text-xs text-gray-500 dark:text-gray-400">No validation data.</div>
		                            )}
		                          </div>
		                          <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
		                            <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">Event Stats</div>
		                            <div className="flex flex-wrap gap-2">
		                              {Object.entries(algoEventTypeCounts)
		                                .sort((a, b) => b[1] - a[1])
		                                .slice(0, 10)
		                                .map(([k, v]) => (
		                                  <Badge key={k} variant="default" size="sm">
		                                    {k}: <span className="font-mono">{v}</span>
		                                  </Badge>
		                                ))}
		                            </div>
		                          </div>
		                          <AlgoMessageTypesChart events={algoNetEvents as any} />
		                        </div>
		                      </div>
		                    )}

                    {algoUiTab === 'events' && (
                      <div className="space-y-3">
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                            <div className="space-y-2">
                              <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Messages & Events</div>
                              <div className="flex flex-wrap gap-2">
                                <Badge variant="default" size="sm">
                                  Msgs: <span className="font-mono">{algoMsgCounts.total}</span>
                                </Badge>
                                <Badge variant="default" size="sm">
                                  TX: <span className="font-mono">{algoMsgCounts.tx}</span>
                                </Badge>
                                <Badge variant="default" size="sm">
                                  RX: <span className="font-mono">{algoMsgCounts.rx}</span>
                                </Badge>
                                <Badge variant="default" size="sm">
                                  BCAST: <span className="font-mono">{algoMsgCounts.bcast}</span>
                                </Badge>
                                <Badge variant="default" size="sm">
                                  Peers: <span className="font-mono">{algoMsgPeers.length}</span>
                                </Badge>
                                {algoEventsView === 'system'
                                  ? Object.entries(algoEventTypeCounts)
                                      .sort((a, b) => b[1] - a[1])
                                      .slice(0, 5)
                                      .map(([k, v]) => (
                                        <Badge key={k} variant="default" size="sm">
                                          {k}: <span className="font-mono">{v}</span>
                                        </Badge>
                                      ))
                                  : null}
                              </div>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              <Button
                                variant={algoEventsView === 'messages' ? 'primary' : 'secondary'}
                                size="sm"
                                onClick={() => setAlgoEventsView('messages')}
                              >
                                Messages
                              </Button>
                              <Button
                                variant={algoEventsView === 'system' ? 'primary' : 'secondary'}
                                size="sm"
                                onClick={() => setAlgoEventsView('system')}
                              >
                                System
                              </Button>

                              {algoEventsView === 'messages' ? (
                                <>
                                  <Select
                                    value={algoMsgDirFilter as any}
                                    onChange={(v) => setAlgoMsgDirFilter(v as any)}
                                    className="w-44"
                                    options={[
                                      { value: 'all', label: 'All directions' },
                                      { value: 'tx', label: 'TX' },
                                      { value: 'rx', label: 'RX' },
                                      { value: 'bcast', label: 'BCAST' },
                                    ]}
                                  />
                                  <Select
                                    value={algoMsgLocalNodeFilter as any}
                                    onChange={(v) => setAlgoMsgLocalNodeFilter(String(v))}
                                    className="w-56"
                                    options={[
                                      { value: 'all', label: 'All local nodes' },
                                      ...algoNodeTableRows.map((r) => ({
                                        value: String(r.algoId),
                                        label: formatAlgoNodeLabel(r.algoId),
                                      })),
                                    ]}
                                  />
                                  <Select
                                    value={algoMsgPeerFilter as any}
                                    onChange={(v) => setAlgoMsgPeerFilter(String(v))}
                                    className="w-56"
                                    options={[
                                      { value: 'all', label: 'All peers' },
                                      ...algoMsgPeers.map((id) => ({
                                        value: String(id),
                                        label: formatAlgoNodeLabel(id),
                                      })),
                                    ]}
                                  />
                                  <Select
                                    value={algoMsgTypeFilter as any}
                                    onChange={(v) => setAlgoMsgTypeFilter(String(v))}
                                    className="w-48"
                                    options={[
                                      { value: 'all', label: 'All msg types' },
                                      ...algoMsgTypes.map((mt) => ({ value: mt, label: mt })),
                                    ]}
                                  />
                                </>
                              ) : (
                                <>
                                  <Select
                                    value={algoEventNodeFilter as any}
                                    onChange={(v) => setAlgoEventNodeFilter(String(v))}
                                    className="w-56"
                                    options={[
                                      { value: 'all', label: 'All nodes' },
                                      ...algoNodeTableRows.map((r) => ({
                                        value: String(r.algoId),
                                        label: formatAlgoNodeLabel(r.algoId),
                                      })),
                                    ]}
                                  />
                                  <Select
                                    value={algoEventTypeFilter as any}
                                    onChange={(v) => setAlgoEventTypeFilter(String(v))}
                                    className="w-56"
                                    options={[
                                      { value: 'all', label: 'All types' },
                                      ...Object.keys(algoEventTypeCounts)
                                        .sort()
                                        .map((k) => ({ value: k, label: k })),
                                    ]}
                                  />
                                </>
                              )}
                              <Button
                                variant={algoEventsTab === 'table' ? 'primary' : 'secondary'}
                                size="sm"
                                onClick={() => setAlgoEventsTab('table')}
		                            >
		                              Table
		                            </Button>
		                            <Button
		                              variant={algoEventsTab === 'raw' ? 'primary' : 'secondary'}
		                              size="sm"
		                              onClick={() => setAlgoEventsTab('raw')}
		                            >
		                              Raw JSON
		                            </Button>
		                            <Button
		                              variant="secondary"
		                              size="sm"
		                              onClick={() => void algoEventsQuery.refetch()}
		                              disabled={!algoRunId}
		                            >
		                              Refresh
                              </Button>
	                            </div>
	                          </div>

	                          {algoEventsView === 'messages' && (
	                            <AlgoMessageTimelineChart
	                              events={algoNetEvents}
	                              runStartedAt={Number((algoRunQuery.data as any)?.created_at) || null}
	                              height={160}
	                              title="Message traffic (live)"
	                            />
	                          )}

				                        {algoEventsTab === 'table' ? (
				                          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
					                            <div className="lg:col-span-2 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
					                              <div className="max-h-[520px] overflow-auto">
				                                <table className="w-full text-sm">
				                                  <thead className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
				                                    <tr>
				                                      <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Time</th>
				                                      <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Δt</th>
				                                      {algoEventsView === 'messages' ? (
				                                        <>
				                                          <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Dir</th>
				                                          <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Local</th>
				                                          <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Peer</th>
				                                          <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Msg</th>
				                                          <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Bytes</th>
				                                          <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Color</th>
				                                          <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Endpoint</th>
				                                        </>
				                                      ) : (
				                                        <>
				                                          <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Type</th>
				                                          <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Node</th>
				                                          <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Summary</th>
				                                        </>
				                                      )}
				                                    </tr>
				                                  </thead>
				                                  <tbody>
				                                    {algoVisibleRows.length ? (
				                                      algoVisibleRows.map((row: any) => {
				                                        const selected = algoSelectedEventRow?.key && algoSelectedEventRow.key === row.key
				                                        const typ = String(row.type || '').toLowerCase()
				                                        const isMsg = typ === 'net_tx' || typ === 'net_rx' || typ === 'net_bcast'
				                                        return (
				                                          <tr
				                                            key={row.key}
				                                            onClick={() => setAlgoSelectedEventKey(String(row.key))}
				                                            className={cn(
				                                              'border-b border-gray-100 dark:border-gray-800 cursor-pointer',
				                                              selected
				                                                ? 'bg-blue-50/60 dark:bg-blue-950/20'
				                                                : 'hover:bg-gray-50 dark:hover:bg-gray-800/30'
				                                            )}
				                                          >
				                                            <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300 whitespace-nowrap">
				                                              {row.ts}
				                                            </td>
				                                            <td className="py-2 px-3 font-mono text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
				                                              {row.elapsed || '—'}
				                                            </td>
				                                            {algoEventsView === 'messages' ? (
				                                              <>
				                                                <td className="py-2 px-3 whitespace-nowrap">
				                                                  <Badge
				                                                    size="sm"
				                                                    variant={typ === 'net_tx' ? 'success' : typ === 'net_rx' ? 'info' : 'warning'}
				                                                  >
				                                                    {typ === 'net_tx' ? 'TX →' : typ === 'net_rx' ? 'RX ←' : 'BCAST'}
				                                                  </Badge>
				                                                </td>
				                                                <td className="py-2 px-3 whitespace-nowrap">
				                                                  <Badge size="sm" variant="default">
				                                                    <span className="font-mono">{String(row.localNode || formatAlgoNodeLabel(row.node))}</span>
				                                                  </Badge>
				                                                </td>
				                                                <td className="py-2 px-3 whitespace-nowrap">
				                                                  <Badge size="sm" variant="default">
				                                                    <span className="font-mono">{String(row.otherLabel || 'BROADCAST')}</span>
				                                                  </Badge>
				                                                </td>
				                                                <td className="py-2 px-3 whitespace-nowrap">
				                                                  <Badge size="sm" variant={isMsg ? 'primary' : 'default'}>
				                                                    <span className="font-mono">{String(row.msgType || 'msg')}</span>
				                                                  </Badge>
				                                                </td>
				                                                <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300 whitespace-nowrap">
				                                                  {row.bytes != null ? String(row.bytes) : '—'}
				                                                </td>
				                                                <td className="py-2 px-3 whitespace-nowrap">
				                                                  {row.color ? (
				                                                    <Badge size="sm" variant="default">
				                                                      <span className="font-mono">{String(row.color)}</span>
				                                                    </Badge>
				                                                  ) : (
				                                                    <span className="text-xs text-gray-400">—</span>
				                                                  )}
				                                                </td>
				                                                <td className="py-2 px-3 font-mono text-[11px] text-gray-600 dark:text-gray-400 whitespace-nowrap">
				                                                  {String(row.endpoint || '—')}
				                                                </td>
				                                              </>
				                                            ) : (
				                                              <>
				                                                <td className="py-2 px-3 whitespace-nowrap">
				                                                  <Badge
				                                                    size="sm"
				                                                    variant={
				                                                      String(row.type || '').toLowerCase() === 'error'
				                                                        ? 'error'
				                                                        : String(row.type || '').toLowerCase() === 'done'
				                                                          ? 'success'
				                                                          : String(row.type || '').toLowerCase() === 'overlay'
				                                                            ? 'primary'
				                                                            : 'default'
				                                                    }
				                                                  >
				                                                    {row.type}
				                                                  </Badge>
				                                                </td>
				                                                <td className="py-2 px-3 whitespace-nowrap">
				                                                  <Badge size="sm" variant="default">
				                                                    <span className="font-mono">{formatAlgoNodeLabel(row.node)}</span>
				                                                  </Badge>
				                                                </td>
				                                                <td className="py-2 px-3 text-xs text-gray-700 dark:text-gray-300 font-mono">
				                                                  {row.summary}
				                                                </td>
				                                              </>
				                                            )}
				                                          </tr>
				                                        )
				                                      })
				                                    ) : (
				                                      <tr>
				                                        <td
				                                          colSpan={algoEventsView === 'messages' ? 9 : 5}
				                                          className="py-10 text-center text-sm text-gray-500 dark:text-gray-400"
				                                        >
				                                          {algoEventsView === 'messages' ? 'No messages for this filter.' : 'No events for this filter.'}
				                                        </td>
				                                      </tr>
				                                    )}
				                                  </tbody>
				                                </table>
			                              </div>
			                            </div>
			
			                            <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 space-y-3">
			                              <div className="flex items-start justify-between gap-2">
			                                <div>
			                                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Event Details</div>
			                                  <div className="text-xs text-gray-500 dark:text-gray-400">Click a row to inspect its full payload.</div>
			                                </div>
			                                <Button
			                                  variant="secondary"
			                                  size="sm"
			                                  onClick={handleCopySelectedAlgoEvent}
			                                  disabled={!algoSelectedEventRow?.raw}
			                                >
			                                  Copy JSON
			                                </Button>
			                              </div>
			
				                              {algoSelectedEventRow?.raw ? (
				                                <>
				                                  <div className="flex flex-wrap items-center gap-2">
				                                    {(() => {
				                                      const t = String(algoSelectedEventRow.type || '').toLowerCase()
				                                      const raw: any = algoSelectedEventRow.raw
				                                      const isMsg = t === 'net_tx' || t === 'net_rx' || t === 'net_bcast'
				                                      if (!isMsg) return null

				                                      const local = formatAlgoNodeLabel(raw?.node ?? algoSelectedEventRow.node)
				                                      const from =
				                                        t === 'net_tx'
				                                          ? local
				                                          : raw?.from != null
				                                            ? formatAlgoNodeLabel(raw.from)
				                                            : 'unknown'
				                                      const to =
				                                        t === 'net_rx'
				                                          ? local
				                                          : t === 'net_bcast'
				                                            ? 'BROADCAST'
				                                            : raw?.to != null
				                                              ? formatAlgoNodeLabel(raw.to)
				                                              : 'addr'

				                                      const msgType = String(raw?.msg_type || 'msg')
				                                      const bytes = raw?.bytes != null ? String(raw.bytes) : '—'
				                                      const endpoint =
				                                        t === 'net_tx'
				                                          ? `${String(raw?.dst_ip || '—')}:${String(raw?.dst_port ?? '—')}`
				                                          : t === 'net_rx'
				                                            ? `${String(raw?.src_ip || '—')}:${String(raw?.src_port ?? '—')}`
				                                            : `:${String(raw?.dst_port ?? '—')}`

				                                      const payload = raw?.payload && typeof raw.payload === 'object' ? raw.payload : null
				                                      const color = payload?.color ?? payload?.overlay?.badge

				                                      return (
				                                        <>
				                                          <Badge size="sm" variant={t === 'net_tx' ? 'success' : t === 'net_rx' ? 'info' : 'warning'}>
				                                            {t === 'net_tx' ? 'TX →' : t === 'net_rx' ? 'RX ←' : 'BCAST'}
				                                          </Badge>
				                                          <Badge size="sm" variant="default">
				                                            From: <span className="font-mono">{from}</span>
				                                          </Badge>
				                                          <Badge size="sm" variant="default">
				                                            To: <span className="font-mono">{to}</span>
				                                          </Badge>
				                                          <Badge size="sm" variant="primary">
				                                            <span className="font-mono">{msgType}</span>
				                                          </Badge>
				                                          <Badge size="sm" variant="default">
				                                            Bytes: <span className="font-mono">{bytes}</span>
				                                          </Badge>
				                                          {color ? (
				                                            <Badge size="sm" variant="default">
				                                              Color: <span className="font-mono">{String(color).toUpperCase()}</span>
				                                            </Badge>
				                                          ) : null}
				                                          <Badge size="sm" variant="default">
				                                            Endpoint: <span className="font-mono">{endpoint}</span>
				                                          </Badge>
				                                        </>
				                                      )
				                                    })()}
				                                    <Badge
				                                      size="sm"
				                                      variant={
				                                        String(algoSelectedEventRow.type || '').toLowerCase() === 'error'
			                                          ? 'error'
			                                          : String(algoSelectedEventRow.type || '').toLowerCase() === 'done'
			                                            ? 'success'
			                                            : 'default'
			                                      }
				                                    >
				                                      {algoSelectedEventRow.type}
				                                    </Badge>
				                                    {String(algoSelectedEventRow.type || '').toLowerCase() !== 'net_tx' &&
				                                    String(algoSelectedEventRow.type || '').toLowerCase() !== 'net_rx' &&
				                                    String(algoSelectedEventRow.type || '').toLowerCase() !== 'net_bcast' ? (
				                                      <Badge size="sm" variant="default">
				                                        Node: <span className="font-mono">{formatAlgoNodeLabel(algoSelectedEventRow.node)}</span>
				                                      </Badge>
				                                    ) : null}
				                                    <Badge size="sm" variant="default">
				                                      Time: <span className="font-mono">{algoSelectedEventRow.ts}</span>
				                                    </Badge>
			                                    {algoSelectedEventRow.elapsed ? (
			                                      <Badge size="sm" variant="default">
			                                        Δt: <span className="font-mono">{algoSelectedEventRow.elapsed}</span>
			                                      </Badge>
			                                    ) : null}
			                                  </div>
			
			                                  {String(algoSelectedEventRow.type || '').toLowerCase() === 'error' ? (
			                                    <div className="rounded-xl border border-red-200 dark:border-red-900/40 bg-red-50 dark:bg-red-950/20 px-3 py-2 text-xs text-red-700 dark:text-red-200 font-mono">
			                                      {String(algoSelectedEventRow.raw?.error || '').slice(0, 500)}
			                                    </div>
			                                  ) : null}
			
			                                  <JsonViewer data={algoSelectedEventRow.raw} collapsed={2} />
			                                </>
			                              ) : (
			                                <div className="text-sm text-gray-500 dark:text-gray-400">No event selected yet.</div>
			                              )}
			                            </div>
			                          </div>
			                        ) : (
		                          <div className="h-[520px] overflow-hidden rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
		                            <Editor
		                              height="520px"
		                              defaultLanguage="json"
		                              value={algoEventsText}
		                              theme={theme === 'light' ? 'vs' : 'vs-dark'}
		                              options={{
		                                readOnly: true,
		                                minimap: { enabled: false },
		                                fontSize: 11,
		                                lineNumbers: 'on',
		                                wordWrap: 'on',
		                                automaticLayout: true,
		                                scrollBeyondLastLine: false,
		                              }}
		                            />
		                          </div>
		                        )}
		                      </div>
		                    )}

		                    {algoUiTab === 'editors' && (
		                      <div className="space-y-4">
		                        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
		                          <div className="space-y-2">
		                            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Manifest (JSON)</div>
		                            <div className="h-[240px] overflow-hidden rounded-xl border border-gray-300 dark:border-gray-800">
		                              <Editor
		                                height="240px"
		                                defaultLanguage="json"
		                                value={algoManifestText}
		                                onChange={(v) => setAlgoManifestText(v || '')}
		                                theme={theme === 'light' ? 'vs' : 'vs-dark'}
		                                options={{
		                                  minimap: { enabled: false },
		                                  fontSize: 12,
		                                  lineNumbers: 'on',
		                                  wordWrap: 'on',
		                                  automaticLayout: true,
		                                  scrollBeyondLastLine: false,
		                                }}
		                              />
		                            </div>
		                          </div>
		                          <div className="space-y-2">
		                            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Params (JSON)</div>
		                            <div className="h-[240px] overflow-hidden rounded-xl border border-gray-300 dark:border-gray-800">
		                              <Editor
		                                height="240px"
		                                defaultLanguage="json"
		                                value={algoParamsText}
		                                onChange={(v) => setAlgoParamsText(v || '')}
		                                theme={theme === 'light' ? 'vs' : 'vs-dark'}
		                                options={{
		                                  minimap: { enabled: false },
		                                  fontSize: 12,
		                                  lineNumbers: 'on',
		                                  wordWrap: 'on',
		                                  automaticLayout: true,
		                                  scrollBeyondLastLine: false,
		                                }}
		                              />
		                            </div>
		                            {algoParamsPreview.error && (
		                              <div className="text-xs text-red-600 dark:text-red-400">{algoParamsPreview.error}</div>
		                            )}
		                          </div>
		                          <div className="space-y-2">
		                            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Run Status</div>
		                            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-3 space-y-2">
		                              <div className="text-xs text-gray-600 dark:text-gray-400">
		                                Run ID:{' '}
		                                <span className="font-mono text-gray-900 dark:text-gray-100">{algoRunId || '(none)'}</span>
		                              </div>
		                              {algoRunQuery.data && (
		                                <>
		                                  <div className="text-xs text-gray-600 dark:text-gray-400">
		                                    Status: <span className="font-mono">{algoRunQuery.data.status}</span>
		                                  </div>
		                                  <div className="text-xs text-gray-600 dark:text-gray-400">
		                                    Started:{' '}
		                                    <span className="font-mono">{(algoRunQuery.data.started_nodes || []).length}</span> • Skipped:{' '}
		                                    <span className="font-mono">{(algoRunQuery.data.skipped_nodes || []).length}</span>
		                                  </div>
		                                  {Array.isArray(algoRunQuery.data.errors) && algoRunQuery.data.errors.length > 0 && (
		                                    <div className="max-h-[120px] overflow-auto rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 p-2">
		                                      <div className="text-xs font-semibold text-red-700 dark:text-red-300 mb-1">Errors</div>
		                                      <ul className="space-y-1">
		                                        {algoRunQuery.data.errors.slice(-10).map((e: string, idx: number) => (
		                                          <li key={idx} className="text-[11px] text-red-700 dark:text-red-300 font-mono">
		                                            {e}
		                                          </li>
		                                        ))}
		                                      </ul>
		                                    </div>
		                                  )}
		                                  {String(algoRunQuery.data.status || '').toLowerCase() === 'stopped' && (
		                                    <div className="text-xs text-emerald-700 dark:text-emerald-300 font-semibold">
		                                      Completed (auto-detected)
		                                    </div>
		                                  )}
		                                </>
		                              )}
		                            </div>
		                          </div>
		                        </div>

		                        <div className="space-y-2">
		                          <div className="flex items-center justify-between gap-3">
		                            <div className="text-xs font-semibold text-gray-700 dark:text-gray-300">Algorithm Code (Python)</div>
		                            <div className="text-xs text-gray-500 dark:text-gray-400 font-mono">
		                              Entry:{' '}
		                              {(() => {
		                                try {
		                                  return (
		                                    JSON.parse(algoManifestText || '{}')?.node_class ||
		                                    JSON.parse(algoManifestText || '{}')?.entrypoint ||
		                                    '(set node_class)'
		                                  )
		                                } catch {
		                                  return '(invalid manifest)'
		                                }
		                              })()}
		                            </div>
		                          </div>
		                          <div className="h-[620px] overflow-hidden rounded-xl border border-gray-300 dark:border-gray-800">
		                            <Editor
		                              height="620px"
		                              defaultLanguage="python"
		                              value={algoSourceCode}
		                              onChange={(v) => setAlgoSourceCode(v || '')}
		                              theme={theme === 'light' ? 'vs' : 'vs-dark'}
		                              options={{
		                                minimap: { enabled: true },
		                                fontSize: 13,
		                                lineNumbers: 'on',
		                                wordWrap: 'off',
		                                automaticLayout: true,
		                                scrollBeyondLastLine: false,
		                                folding: true,
		                                renderWhitespace: 'selection',
		                              }}
		                            />
		                          </div>
		                        </div>
		                      </div>
		                    )}

			                    {algoUiTab === 'history' && (
			                      <div className="space-y-4">
			                        <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
			                          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
			                            <div>
			                              <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Saved Runs (InfluxDB)</div>
			                              <div className="text-xs text-gray-600 dark:text-gray-400">
			                                Filter persisted runs and inspect stored per-node results.
			                              </div>
			                            </div>
			                            <div className="flex flex-wrap items-end gap-2">
			                              <div className="flex items-center gap-2">
			                                <Button
			                                  variant={algoHistoryMode === 'inspect' ? 'primary' : 'secondary'}
			                                  size="sm"
			                                  onClick={() => setAlgoHistoryMode('inspect')}
			                                >
			                                  Inspect
			                                </Button>
			                                <Button
			                                  variant={algoHistoryMode === 'compare' ? 'primary' : 'secondary'}
			                                  size="sm"
			                                  onClick={() => setAlgoHistoryMode('compare')}
			                                >
			                                  Compare
			                                </Button>
			                                {algoHistoryMode === 'compare' && (
			                                  <>
			                                    <Badge variant="default" size="sm">
			                                      Selected: {algoHistoryCompareRunIdsNormalized.length}
			                                    </Badge>
			                                    <Button
			                                      variant="secondary"
			                                      size="sm"
			                                      onClick={() => setAlgoHistoryCompareRunIds([])}
			                                      disabled={!algoHistoryCompareRunIdsNormalized.length}
			                                    >
			                                      Clear
			                                    </Button>
			                                  </>
			                                )}
			                              </div>
			                              <Input
			                                label="Algorithm"
			                                value={algoHistoryAlgorithmFilter}
			                                onChange={(e) => setAlgoHistoryAlgorithmFilter(e.target.value)}
		                                placeholder="distributed-mis"
		                                className="w-48"
		                              />
		                              <Input
		                                label="Window (min)"
		                                type="number"
		                                value={algoHistoryWindowMinutes}
		                                onChange={(e) => setAlgoHistoryWindowMinutes(Number(e.target.value) || 1440)}
		                                className="w-36"
			                              />
			                            </div>
			                          </div>
			                        </div>

			                        {algoHistoryMode === 'inspect' ? (
			                          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
			                            <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
			                              <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
			                                <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Runs</div>
			                                <Badge variant="default" size="sm">
			                                  {(algoHistoryRuns as any)?.runs?.length || 0}
			                                </Badge>
			                              </div>
			                              <div className="max-h-[520px] overflow-auto">
			                                <table className="w-full text-sm">
			                                  <thead className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
			                                    <tr>
			                                      <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Run</th>
			                                      <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Algorithm</th>
			                                      <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Time</th>
			                                    </tr>
			                                  </thead>
			                                  <tbody>
			                                    {Array.isArray((algoHistoryRuns as any)?.runs) && (algoHistoryRuns as any).runs.length ? (
			                                      (algoHistoryRuns as any).runs.map((r: any) => {
			                                        const rid = String(r?.run_id || '')
			                                        const selected = rid && rid === algoHistorySelectedRunId
			                                        return (
			                                          <tr
			                                            key={rid || Math.random()}
			                                            className={cn(
			                                              'border-b border-gray-100 dark:border-gray-800 cursor-pointer',
			                                              selected
			                                                ? 'bg-blue-50 dark:bg-blue-900/20'
			                                                : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
			                                            )}
			                                            onClick={() => setAlgoHistorySelectedRunId(rid)}
			                                          >
			                                            <td className="py-2 px-3 font-mono text-xs text-gray-900 dark:text-gray-100">
			                                              {rid ? rid.slice(0, 10) : '—'}
			                                            </td>
			                                            <td className="py-2 px-3 text-xs text-gray-700 dark:text-gray-300">{r?.algorithm || '—'}</td>
			                                            <td className="py-2 px-3 font-mono text-[11px] text-gray-600 dark:text-gray-400">
			                                              {String(r?.time || '').replace('T', ' ').slice(0, 19) || '—'}
			                                            </td>
			                                          </tr>
			                                        )
			                                      })
			                                    ) : (
			                                      <tr>
			                                        <td colSpan={3} className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">
			                                          No saved runs in this window.
			                                        </td>
			                                      </tr>
			                                    )}
			                                  </tbody>
			                                </table>
			                              </div>
			                            </div>

			                            <div className="lg:col-span-2 space-y-4">
			                              <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
			                                <div className="flex items-center justify-between gap-2 mb-3">
			                                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Run Summary</div>
			                                  {(() => {
			                                    const ok = Number((algoHistorySummary as any)?.fields?.validation_ok)
			                                    if (ok === 1) return <Badge variant="success" size="sm" withIcon>OK</Badge>
			                                    if (ok === 0) return <Badge variant="warning" size="sm" withIcon>FAIL</Badge>
			                                    return <Badge variant="default" size="sm">—</Badge>
			                                  })()}
			                                </div>
			                                {(() => {
			                                  const f = (algoHistorySummary as any)?.fields || {}
			                                  if (!f || typeof f !== 'object' || !Object.keys(f).length) {
			                                    return <div className="text-xs text-gray-500 dark:text-gray-400">No summary stored for this run yet.</div>
			                                  }
			                                  const duration = f.duration_s !== undefined ? `${Number(f.duration_s).toFixed(2)}s` : '—'
			                                  const algoOut = Number(f.algo_sent_msgs || 0) + Number(f.algo_broadcast_msgs || 0)
			                                  const algoIn = Number(f.algo_recv_msgs || 0)
			                                  return (
			                                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
			                                      <MetricCard title="Duration" value={duration} />
			                                      <MetricCard title="Mininet Δ packets" value={String(f.mininet_delta_total_packets ?? '—')} />
			                                      <MetricCard title="Mininet Δ bytes" value={String(f.mininet_delta_total_bytes ?? '—')} />
			                                      <MetricCard title="Algo msgs (out/in)" value={`${algoOut}/${algoIn}`} />
			                                    </div>
			                                  )
			                                })()}
			                              </div>

			                              <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
			                                <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
			                                  <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Per-Node Results</div>
			                                  <Badge variant="default" size="sm">
			                                    {(algoHistoryNodes as any)?.nodes?.length || 0}
			                                  </Badge>
			                                </div>
			                                <div className="max-h-[520px] overflow-auto">
			                                  <table className="w-full text-sm">
			                                    <thead className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
			                                      <tr>
			                                        <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Algo</th>
			                                        <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Node</th>
			                                        <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Color</th>
			                                        <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Out</th>
			                                        <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">In</th>
			                                      </tr>
			                                    </thead>
			                                    <tbody>
			                                      {Array.isArray((algoHistoryNodes as any)?.nodes) && (algoHistoryNodes as any).nodes.length ? (
			                                        (algoHistoryNodes as any).nodes.map((n: any) => {
			                                          const fields = n?.fields || {}
			                                          const out = Number(fields?.sent_msgs || 0) + Number(fields?.broadcast_msgs || 0)
			                                          const inn = Number(fields?.recv_msgs || 0)
			                                          return (
			                                            <tr key={`${n?.algo_id}:${n?.node_uuid}`} className="border-b border-gray-100 dark:border-gray-800">
			                                              <td className="py-2 px-3 font-mono text-xs text-gray-900 dark:text-gray-100">{n?.algo_id}</td>
			                                              <td className="py-2 px-3 font-mono text-[11px] text-gray-700 dark:text-gray-300">
			                                                {n?.node_name || n?.node_uuid || '—'}
			                                              </td>
			                                              <td className="py-2 px-3">
			                                                <Badge variant="default" size="sm">
			                                                  {String(fields?.color || '').toUpperCase() || '—'}
			                                                </Badge>
			                                              </td>
			                                              <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{out}</td>
			                                              <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{inn}</td>
			                                            </tr>
			                                          )
			                                        })
			                                      ) : (
			                                        <tr>
			                                          <td colSpan={5} className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">
			                                            Select a run to view saved node results.
			                                          </td>
			                                        </tr>
			                                      )}
			                                    </tbody>
			                                  </table>
			                                </div>
			                              </div>
			                            </div>
			                          </div>
			                        ) : (
			                          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
			                            <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
			                              <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
			                                <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Runs</div>
			                                <Badge variant="default" size="sm">
			                                  {(algoHistoryRuns as any)?.runs?.length || 0}
			                                </Badge>
			                              </div>
			                              <div className="max-h-[520px] overflow-auto">
			                                <table className="w-full text-sm">
			                                  <thead className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
			                                    <tr>
			                                      <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Sel</th>
			                                      <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Run</th>
			                                      <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Algorithm</th>
			                                      <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Time</th>
			                                    </tr>
			                                  </thead>
			                                  <tbody>
			                                    {Array.isArray((algoHistoryRuns as any)?.runs) && (algoHistoryRuns as any).runs.length ? (
			                                      (algoHistoryRuns as any).runs.map((r: any) => {
			                                        const rid = String(r?.run_id || '')
			                                        const checked = algoHistoryCompareRunIdsNormalized.includes(rid)
			                                        return (
			                                          <tr
			                                            key={rid || Math.random()}
			                                            className={cn(
			                                              'border-b border-gray-100 dark:border-gray-800 cursor-pointer',
			                                              checked ? 'bg-blue-50 dark:bg-blue-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
			                                            )}
			                                            onClick={() => toggleAlgoHistoryCompareRun(rid)}
			                                          >
			                                            <td className="py-2 px-3">
			                                              <input
			                                                type="checkbox"
			                                                className="w-4 h-4 text-blue-600 rounded"
			                                                checked={checked}
			                                                onChange={() => toggleAlgoHistoryCompareRun(rid)}
			                                              />
			                                            </td>
			                                            <td className="py-2 px-3 font-mono text-xs text-gray-900 dark:text-gray-100">
			                                              {rid ? rid.slice(0, 10) : '—'}
			                                            </td>
			                                            <td className="py-2 px-3 text-xs text-gray-700 dark:text-gray-300">{r?.algorithm || '—'}</td>
			                                            <td className="py-2 px-3 font-mono text-[11px] text-gray-600 dark:text-gray-400">
			                                              {String(r?.time || '').replace('T', ' ').slice(0, 19) || '—'}
			                                            </td>
			                                          </tr>
			                                        )
			                                      })
			                                    ) : (
			                                      <tr>
			                                        <td colSpan={4} className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">
			                                          No saved runs in this window.
			                                        </td>
			                                      </tr>
			                                    )}
			                                  </tbody>
			                                </table>
			                              </div>
			                            </div>

			                            <div className="lg:col-span-2 space-y-4">
			                              {algoHistoryCompareSummariesLoading && (
			                                <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 text-xs text-gray-500 dark:text-gray-400">
			                                  Loading summaries…
			                                </div>
			                              )}
			                              {algoHistoryCompareRunIdsNormalized.length ? (
			                                <AlgorithmRunsCompare items={algoHistoryCompareItems} />
			                              ) : (
			                                <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
			                                  <div className="text-sm text-gray-500 dark:text-gray-400">
			                                    Select 2+ runs from the list to compare stored metrics.
			                                  </div>
			                                </div>
			                              )}
			                            </div>
			                          </div>
			                        )}
			                      </div>
			                    )}
			                  </div>
			                </div>
		              </CardContent>
		            </Card>
		          </div>
		        )}

	        {activeTab === 'mininet-cli' && (
	          <div className="animate-fade-in">
	            <Card padding="none" className="overflow-hidden">
	              <CardContent className="p-0">
                {isRunning ? (
                  <div className="h-[700px]">
                    <MininetCLI container={containerName} onClose={() => {}} />
                  </div>
                ) : (
                  <div className="h-[700px] flex items-center justify-center">
                    <div className="text-center text-gray-500 dark:text-gray-400">
                      <CommandLineIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                      <p className="text-lg font-medium mb-2">Mininet CLI Not Available</p>
                      <p>Start the emulation to access Mininet CLI</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {activeTab === 'terminal' && (
          <div className="animate-fade-in">
            <Card padding="none" className="overflow-hidden">
              <CardHeader className="p-6">
                <div className="flex items-center justify-between">
                  <CardTitle>{t('webshell.title')}</CardTitle>
                  <div className="flex items-center gap-2">
                    {selectedDeviceData && (
                      <Badge variant="primary" size="sm">
                        Device: {selectedDeviceData.name}
                      </Badge>
                    )}
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setActiveTab('config')}
                      disabled={!selectedDeviceData}
                    >
                      Configuration
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="p-0">
                {isRunning && runtimeDevices && runtimeDevices.length > 0 ? (
                  <div className="h-[600px]">
                    <WebShell
                      device={
                        (selectedDeviceData && getRuntimeName(selectedDeviceData)) ||
                        (runtimeDevices[0] && getRuntimeName(runtimeDevices[0])) ||
                        'h1'
                      }
                      container={containerName}
                      onClose={() => {}}
                    />
                  </div>
                ) : (
                  <div className="h-[600px] flex items-center justify-center">
                    <div className="text-center text-gray-500 dark:text-gray-400">
                      <CommandLineIcon className="w-12 h-12 mx-auto mb-4 opacity-50" />
                      <p>{isRunning ? 'No devices available' : 'Start the emulation to access terminal'}</p>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {activeTab === 'diagnostics' && (
          <div className="animate-fade-in">
            <TopologyDiagnostics topologyId={topologyId || undefined} runtimeDevices={runtimeDevices} />
          </div>
        )}

        {activeTab === 'mano' && (
          <>
            <ManoTab
              topologyId={topologyId}
              isRunning={isRunning}
              setActiveTab={setActiveTab}
              manoPane={manoPane}
              setManoPane={setManoPane}
              manoInfoQuery={manoInfoQuery}
              manoNsdsQuery={manoNsdsQuery}
              manoVnfdsQuery={manoVnfdsQuery}
              manoNsInstancesQuery={manoNsInstancesQuery}
              manoAllVnfsQuery={manoAllVnfsQuery}
              manoSelectedNsId={manoSelectedNsId}
              setManoSelectedNsId={setManoSelectedNsId}
              manoInventoryQuery={manoInventoryQuery}
              manoOpsQuery={manoOpsQuery}
              manoVnfsQuery={manoVnfsQuery}
              manoSelectedVnfId={manoSelectedVnfId}
              setManoSelectedVnfId={setManoSelectedVnfId}
              manoVnfDeleteForce={manoVnfDeleteForce}
              setManoVnfDeleteForce={setManoVnfDeleteForce}
              manoExecCommand={manoExecCommand}
              setManoExecCommand={setManoExecCommand}
              execVnfMutation={execVnfMutation}
              deleteVnfMutation={deleteVnfMutation}
              terminateNsMutation={terminateNsMutation}
              createNsMutation={createNsMutation}
              manoNsName={manoNsName}
              setManoNsName={setManoNsName}
              manoNsDryRun={manoNsDryRun}
              setManoNsDryRun={setManoNsDryRun}
              manoNsBackend={manoNsBackend}
              setManoNsBackend={setManoNsBackend}
              manoSelectedNsdId={manoSelectedNsdId}
              setManoSelectedNsdId={setManoSelectedNsdId}
              manoOsmNsdId={manoOsmNsdId}
              setManoOsmNsdId={setManoOsmNsdId}
              manoOsmVimAccountId={manoOsmVimAccountId}
              setManoOsmVimAccountId={setManoOsmVimAccountId}
              manoVnfName={manoVnfName}
              setManoVnfName={setManoVnfName}
              manoVnfDeviceType={manoVnfDeviceType}
              setManoVnfDeviceType={setManoVnfDeviceType}
              manoVnfPropsRows={manoVnfPropsRows}
              setManoVnfPropsRows={setManoVnfPropsRows}
              manoVnfProperties={manoVnfProperties}
              manoVnfDryRun={manoVnfDryRun}
              setManoVnfDryRun={setManoVnfDryRun}
              createVnfMutation={createVnfMutation}
              manoCatalogTab={manoCatalogTab}
              setManoCatalogTab={setManoCatalogTab}
              manoNsdName={manoNsdName}
              setManoNsdName={setManoNsdName}
              manoNsdTopologyId={manoNsdTopologyId}
              setManoNsdTopologyId={setManoNsdTopologyId}
              manoNsdOptionRows={manoNsdOptionRows}
              setManoNsdOptionRows={setManoNsdOptionRows}
              manoNsdDescriptor={manoNsdDescriptor}
              upsertNsdMutation={upsertNsdMutation}
              manoSelectedNsd={manoSelectedNsd}
              manoVnfdName={manoVnfdName}
              setManoVnfdName={setManoVnfdName}
              manoVnfdDeviceType={manoVnfdDeviceType}
              setManoVnfdDeviceType={setManoVnfdDeviceType}
              manoVnfdDefaultsRows={manoVnfdDefaultsRows}
              setManoVnfdDefaultsRows={setManoVnfdDefaultsRows}
              manoVnfdDescriptor={manoVnfdDescriptor}
              upsertVnfdMutation={upsertVnfdMutation}
              manoSelectedVnfdId={manoSelectedVnfdId}
              setManoSelectedVnfdId={setManoSelectedVnfdId}
              manoSelectedVnfd={manoSelectedVnfd}
              osmConnectorRunning={osmConnectorRunning}
              osmEnsureInfraMutation={osmEnsureInfraMutation}
              osmReconcileMutation={osmReconcileMutation}
              osmStopInfraMutation={osmStopInfraMutation}
              osmPurgeInfraMutation={osmPurgeInfraMutation}
              osmTab={osmTab}
              setOsmTab={setOsmTab}
              osmUiKind={osmUiKind}
              setOsmUiKind={setOsmUiKind}
              osmInfraStatusQuery={osmInfraStatusQuery}
              osmInfoQuery={osmInfoQuery}
              osmProjectsQuery={osmProjectsQuery}
              osmVimAccountsQuery={osmVimAccountsQuery}
              osmSelectedVimAccountId={osmSelectedVimAccountId}
              setOsmSelectedVimAccountId={setOsmSelectedVimAccountId}
              osmWimAccountsQuery={osmWimAccountsQuery}
              osmSdnControllersQuery={osmSdnControllersQuery}
              osmMirrorStatsQuery={osmMirrorStatsQuery}
              osmMirrorSyncMutation={osmMirrorSyncMutation}
              osmNsdPackagesQuery={osmNsdPackagesQuery}
              osmVnfdPackagesQuery={osmVnfdPackagesQuery}
              uploadOsmNsdMutation={uploadOsmNsdMutation}
              uploadOsmVnfdMutation={uploadOsmVnfdMutation}
              deleteOsmNsdMutation={deleteOsmNsdMutation}
              deleteOsmVnfdMutation={deleteOsmVnfdMutation}
              osmNsInstancesQuery={osmNsInstancesQuery}
              osmCreateNsName={osmCreateNsName}
              setOsmCreateNsName={setOsmCreateNsName}
              osmCreateNsDescription={osmCreateNsDescription}
              setOsmCreateNsDescription={setOsmCreateNsDescription}
              osmSelectedNsdPkgId={osmSelectedNsdPkgId}
              setOsmSelectedNsdPkgId={setOsmSelectedNsdPkgId}
              osmCreateNsMutation={osmCreateNsMutation}
              osmSelectedNsInstanceId={osmSelectedNsInstanceId}
              setOsmSelectedNsInstanceId={setOsmSelectedNsInstanceId}
              osmInstantiateNsMutation={osmInstantiateNsMutation}
              osmInstantiateJson={osmInstantiateJson}
              setOsmInstantiateJson={setOsmInstantiateJson}
              osmTerminateNsMutation={osmTerminateNsMutation}
              osmDeleteNsMutation={osmDeleteNsMutation}
              osmMirrorResourceType={osmMirrorResourceType}
              setOsmMirrorResourceType={setOsmMirrorResourceType}
              osmMirrorIncludeDeleted={osmMirrorIncludeDeleted}
              setOsmMirrorIncludeDeleted={setOsmMirrorIncludeDeleted}
              osmMirrorResourcesQuery={osmMirrorResourcesQuery}
              osmMirrorSelectedId={osmMirrorSelectedId}
              setOsmMirrorSelectedId={setOsmMirrorSelectedId}
            />
            {/*
	          <div className="space-y-6 animate-fade-in">
	            <Card>
	              <CardHeader>
	                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
	                  <div>
	                    <CardTitle>MANO</CardTitle>
	                    <p className="text-sm text-gray-600 dark:text-gray-400">
	                      Manage network services (NFVO/VNFM/VIM) and integrate ETSI OSM per-topology.
	                    </p>
	                  </div>
	                  <div className="flex flex-wrap items-center gap-2">
	                    <Button
	                      size="xs"
	                      variant={manoPane === 'overview' ? 'primary' : 'secondary'}
	                      onClick={() => setManoPane('overview')}
	                    >
	                      Overview
	                    </Button>
	                    <Button
	                      size="xs"
	                      variant={manoPane === 'local' ? 'primary' : 'secondary'}
	                      onClick={() => setManoPane('local')}
	                    >
	                      Local MANO
	                    </Button>
	                    <Button
	                      size="xs"
	                      variant={manoPane === 'osm' ? 'primary' : 'secondary'}
	                      onClick={() => setManoPane('osm')}
	                    >
	                      OSM (ETSI)
	                    </Button>
	                  </div>
	                </div>
	              </CardHeader>
	              <CardContent>
	                <div className="flex flex-wrap items-center gap-2">
	                  <Badge variant="default" size="sm">
	                    Southbound: {String(manoInfoQuery.data?.features?.southbound_mode || '—')}
	                  </Badge>
                  <Badge variant="default" size="sm">
                    Catalog: {String(manoInfoQuery.data?.features?.catalog ?? '—')}
                  </Badge>
                  <Badge variant="default" size="sm">
                    NFVO: {String(manoInfoQuery.data?.features?.nfvo || '—')}
                  </Badge>
                  <Badge variant="default" size="sm">
                    VNFM: {String(manoInfoQuery.data?.features?.vnfm || '—')}
                  </Badge>
                  <Badge variant="default" size="sm">
                    VIM: {String(manoInfoQuery.data?.features?.vim || '—')}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex flex-col gap-1">
                  <CardTitle>Quick Start</CardTitle>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    New to MANO? Use these shortcuts to get something running quickly.
                  </p>
                </div>
              </CardHeader>
              <CardContent>
                {!topologyId ? (
                  <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 p-3 text-sm text-gray-700 dark:text-gray-300">
                    Select a topology first. OSM runs isolated per topology and Local MANO actions can target a topology.
                  </div>
                ) : (
	                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
	                    <div className="rounded-2xl border border-blue-200/70 dark:border-blue-900/50 p-4 space-y-3 bg-gradient-to-br from-blue-50/70 via-white to-cyan-50/60 dark:from-blue-950/25 dark:via-gray-950 dark:to-cyan-950/20">
	                      <div className="flex items-start justify-between gap-2">
	                        <div className="flex items-start gap-3 min-w-0">
                            <div className="h-10 w-10 rounded-xl bg-blue-600/10 dark:bg-blue-400/10 text-blue-700 dark:text-blue-300 flex items-center justify-center">
                              <Cog6ToothIcon className="h-5 w-5" />
                            </div>
                            <div className="min-w-0">
	                            <div className="text-sm font-semibold text-gray-900 dark:text-white">Local MANO</div>
                              <div className="text-xs text-gray-600 dark:text-gray-400">
                                Built-in NFVO/VNFM for fast experiments.
                              </div>
                            </div>
                          </div>
	                        <Badge variant="info" size="sm">Fast</Badge>
	                      </div>
	                      <div className="text-sm text-gray-600 dark:text-gray-400">
	                        Create NS/VNF directly against the emulation via built-in NFVO/VNFM.
	                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="primary" onClick={() => setManoPane('local')}>
                          Open Local MANO
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setActiveTab('config')}>
                          Control Config
                        </Button>
                      </div>
	                      <div className="text-xs text-gray-600 dark:text-gray-400">
	                        Tip: start the emulation first if you plan to run commands on devices.
	                      </div>
	                    </div>
	
	                    <div className="rounded-2xl border border-indigo-200/70 dark:border-indigo-900/50 p-4 space-y-3 bg-gradient-to-br from-indigo-50/70 via-white to-purple-50/60 dark:from-indigo-950/25 dark:via-gray-950 dark:to-purple-950/20">
	                      <div className="flex items-start justify-between gap-2">
	                        <div className="flex items-start gap-3 min-w-0">
                            <div className="h-10 w-10 rounded-xl bg-indigo-600/10 dark:bg-indigo-400/10 text-indigo-700 dark:text-indigo-300 flex items-center justify-center">
                              <ServerIcon className="h-5 w-5" />
                            </div>
                            <div className="min-w-0">
	                            <div className="text-sm font-semibold text-gray-900 dark:text-white">OSM (ETSI)</div>
                              <div className="text-xs text-gray-600 dark:text-gray-400">
                                Real MANO stack per topology (isolated).
                              </div>
                            </div>
                          </div>
	                        <Badge variant={osmConnectorRunning ? 'success' : 'warning'} size="sm">
	                          {osmConnectorRunning ? 'Running' : 'Stopped'}
	                        </Badge>
	                      </div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        Use a real MANO stack (OSM) per topology: VIM/WIM/Packages/NS lifecycle + native UI.
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="primary"
                          onClick={() => {
                            setManoPane('osm')
                            setOsmTab('overview')
                            osmReconcileMutation.mutate()
                          }}
                          disabled={osmReconcileMutation.isPending}
                          isLoading={osmReconcileMutation.isPending}
                        >
                          Ensure + Sync
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => {
                            setManoPane('osm')
                            setOsmTab('ui')
                          }}
                        >
                          Open OSM UI
                        </Button>
                      </div>
	                      <div className="text-xs text-gray-600 dark:text-gray-400">
	                        Default login: <span className="font-mono">admin / admin</span>
	                      </div>
	                    </div>
	
	                    <div className="rounded-2xl border border-emerald-200/70 dark:border-emerald-900/50 p-4 space-y-3 bg-gradient-to-br from-emerald-50/70 via-white to-teal-50/60 dark:from-emerald-950/25 dark:via-gray-950 dark:to-teal-950/20">
	                      <div className="flex items-start justify-between gap-2">
	                        <div className="flex items-start gap-3 min-w-0">
                            <div className="h-10 w-10 rounded-xl bg-emerald-600/10 dark:bg-emerald-400/10 text-emerald-700 dark:text-emerald-300 flex items-center justify-center">
                              <ChartBarIcon className="h-5 w-5" />
                            </div>
                            <div className="min-w-0">
	                            <div className="text-sm font-semibold text-gray-900 dark:text-white">Verify It Works</div>
                              <div className="text-xs text-gray-600 dark:text-gray-400">
                                Prove MANO actions change the emulation.
                              </div>
                            </div>
                          </div>
	                        <Badge variant={isRunning ? 'success' : 'default'} size="sm">
	                          Emulation: {isRunning ? 'running' : 'stopped'}
	                        </Badge>
	                      </div>
                      <div className="text-sm text-gray-600 dark:text-gray-400">
                        After instantiating an NS, you should see new runtime devices/containers created in the emulation.
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button size="sm" variant="secondary" onClick={() => setActiveTab('container-ui')}>
                          Container UI
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => setActiveTab('terminal')}>
                          Device Terminal
                        </Button>
                      </div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">
                        Also available: <span className="font-mono">bash scripts/mano_smoke_test.sh {String(topologyId)}</span>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            {manoPane === 'overview' && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  <MetricCard
                    title="Local NSDs"
                    value={manoNsdsQuery.data?.length || 0}
                    subtitle="Service descriptors (custom)"
                    variant="primary"
                    isLoading={manoNsdsQuery.isFetching}
                    onClick={() => setManoPane('local')}
                  />
                  <MetricCard
                    title="Local VNFDs"
                    value={manoVnfdsQuery.data?.length || 0}
                    subtitle="VNF descriptors (custom)"
                    variant="primary"
                    isLoading={manoVnfdsQuery.isFetching}
                    onClick={() => setManoPane('local')}
                  />
                  <MetricCard
                    title="Local NS Instances"
                    value={manoNsInstancesQuery.data?.length || 0}
                    subtitle={topologyId ? `Topology ${String(topologyId).slice(0, 8)}` : 'All topologies'}
                    variant={manoNsInstancesQuery.data?.length ? 'success' : 'default'}
                    isLoading={manoNsInstancesQuery.isFetching}
                    onClick={() => setManoPane('local')}
                  />
                  <MetricCard
                    title="VNF Instances"
                    value={manoAllVnfsQuery.data?.length || 0}
                    subtitle="Across MANO database"
                    variant={manoAllVnfsQuery.data?.length ? 'success' : 'default'}
                    isLoading={manoAllVnfsQuery.isFetching}
                    onClick={() => setManoPane('local')}
                  />
                  <MetricCard
                    title="OSM Stack"
                    value={osmConnectorRunning ? 'RUNNING' : 'STOPPED'}
                    subtitle={topologyId ? `Per-topology (${String(topologyId).slice(0, 8)})` : 'Select a topology'}
                    variant={osmConnectorRunning ? 'success' : 'warning'}
                    isLoading={osmInfraStatusQuery.isFetching}
                    onClick={() => setManoPane('osm')}
                  />
                  <MetricCard
                    title="OSM VIM Accounts"
                    value={(osmVimAccountsQuery.data || []).length}
                    subtitle="VIM accounts inside ETSI OSM"
                    variant={(osmVimAccountsQuery.data || []).length ? 'success' : 'default'}
                    isLoading={osmVimAccountsQuery.isFetching}
                    onClick={() => setManoPane('osm')}
                  />
                  <MetricCard
                    title="OSM WIM Accounts"
                    value={(osmWimAccountsQuery.data || []).length}
                    subtitle="WIM accounts inside ETSI OSM"
                    variant={(osmWimAccountsQuery.data || []).length ? 'success' : 'default'}
                    isLoading={osmWimAccountsQuery.isFetching}
                    onClick={() => setManoPane('osm')}
                  />
                  <MetricCard
                    title="OSM SDN Controllers"
                    value={Array.isArray(osmSdnControllersQuery.data) ? osmSdnControllersQuery.data.length : 0}
                    subtitle="Discovered/registered SDNs"
                    variant={Array.isArray(osmSdnControllersQuery.data) && osmSdnControllersQuery.data.length ? 'success' : 'default'}
                    isLoading={osmSdnControllersQuery.isFetching}
                    onClick={() => setManoPane('osm')}
                  />
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card>
                    <CardHeader>
                      <div className="flex items-center justify-between gap-3">
                        <CardTitle>ETSI OSM (per-topology)</CardTitle>
                        <Button size="xs" variant="secondary" onClick={() => setManoPane('osm')}>
                          Open Panel
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm text-gray-700 dark:text-gray-300">
                      <div>
                        This project runs an isolated ETSI OSM stack per topology. Use it to upload VNFD/NSD packages and
                        instantiate NS instances against the emulated infrastructure.
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Button
                          size="xs"
                          variant="primary"
                          onClick={() => osmEnsureInfraMutation.mutate()}
                          disabled={!topologyId || osmEnsureInfraMutation.isPending}
                          isLoading={osmEnsureInfraMutation.isPending}
                        >
                          Start / Ensure
                        </Button>
	                        <Button
	                          size="xs"
	                          variant="secondary"
	                          onClick={() => osmReconcileMutation.mutate()}
	                          disabled={!topologyId || osmReconcileMutation.isPending}
	                          isLoading={osmReconcileMutation.isPending}
	                        >
	                          Sync Mirror
	                        </Button>
                      </div>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <div className="flex items-center justify-between gap-3">
                        <CardTitle>Local MANO</CardTitle>
                        <Button size="xs" variant="secondary" onClick={() => setManoPane('local')}>
                          Open Panel
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3 text-sm text-gray-700 dark:text-gray-300">
                      <div>
                        Local MANO is a lightweight NFVO/VNFM flow that starts emulations and creates runtime VNFs
                        (containers/devices) through the platform APIs.
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="default" size="sm">
                          Backend: local
                        </Badge>
                        <Badge variant="default" size="sm">
                          Topology: {topologyId ? String(topologyId).slice(0, 8) : '—'}
                        </Badge>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              </div>
            )}

	            {manoPane === 'osm' && (
	              <>
	              <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <CardTitle>OSM (ETSI)</CardTitle>
                  <div className="flex items-center gap-2">
                    <Button size="xs" variant={osmTab === 'overview' ? 'primary' : 'secondary'} onClick={() => setOsmTab('overview')}>
                      Overview
                    </Button>
                    <Button size="xs" variant={osmTab === 'packages' ? 'primary' : 'secondary'} onClick={() => setOsmTab('packages')}>
                      Packages
                    </Button>
                    <Button size="xs" variant={osmTab === 'ns' ? 'primary' : 'secondary'} onClick={() => setOsmTab('ns')}>
                      NS
                    </Button>
	                    <Button size="xs" variant={osmTab === 'mirror' ? 'primary' : 'secondary'} onClick={() => setOsmTab('mirror')}>
	                      Mirror
	                    </Button>
	                    <Button size="xs" variant={osmTab === 'ui' ? 'primary' : 'secondary'} onClick={() => setOsmTab('ui')}>
	                      UI
	                    </Button>
	                  </div>
	                </div>
	              </CardHeader>
              <CardContent className="space-y-4">
                {(() => {
                  const id8 = topologyId ? String(topologyId).slice(0, 8) : ''
                  return (
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => window.open(`/infra-proxy/osm-ng-ui/${id8}/`, '_blank', 'noopener,noreferrer')}
                        disabled={!topologyId}
                      >
                        Open OSM NG-UI
                      </Button>
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => window.open(`/infra-proxy/osm-light-ui/${id8}/`, '_blank', 'noopener,noreferrer')}
                        disabled={!topologyId}
                      >
                        Open OSM Light UI
                      </Button>
                      {!topologyId ? (
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          Select a topology to open its isolated OSM UI.
                        </span>
                      ) : null}
                    </div>
                  )
                })()}

                {!topologyId ? (
                  <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 p-3 text-sm text-gray-700 dark:text-gray-300">
                    Select a topology first. This OSM panel is per-topology (isolated OSM stack per topology).
                  </div>
                ) : (
                  <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 p-3 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="default" size="sm">Topology: {String(topologyId).slice(0, 8)}</Badge>
                      <Badge variant={osmConnectorRunning ? 'success' : 'default'} size="sm">
                        Stack: {osmConnectorRunning ? 'running' : (osmEnsureInfraMutation.isPending ? 'starting' : 'stopped')}
                      </Badge>
                      <Badge variant="default" size="sm">
                        Connector: {String(osmInfraStatusQuery.data?.osm?.connector?.service_name || `osm-connector-${String(topologyId).slice(0, 8)}`)}
                      </Badge>
                      <Badge
                        variant={(osmInfraStatusQuery.data as any)?.osm?.bootstrap?.emulation_vim?.vim_account_id ? 'success' : 'default'}
                        size="sm"
                      >
                        Emu VIM: {String((osmInfraStatusQuery.data as any)?.osm?.bootstrap?.emulation_vim?.name || `mininet-${String(topologyId).slice(0, 8)}`)}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        size="xs"
                        variant="primary"
                        onClick={() => osmEnsureInfraMutation.mutate()}
                        disabled={!topologyId || osmEnsureInfraMutation.isPending}
                      >
                        Start / Ensure
                      </Button>
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => osmReconcileMutation.mutate()}
                        disabled={!topologyId || osmReconcileMutation.isPending}
                      >
                        Ensure + Sync
                      </Button>
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => osmMirrorSyncMutation.mutate()}
                        disabled={!topologyId || osmMirrorSyncMutation.isPending}
                      >
                        Sync OSM → DB
                      </Button>
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => osmStopInfraMutation.mutate(true)}
                        disabled={!topologyId || osmStopInfraMutation.isPending}
                      >
                        Stop
                      </Button>
                      <Button
                        size="xs"
                        variant="danger"
                        onClick={() => {
                          if (!confirm('Purge per-topology OSM stack? (containers + volumes)')) return
                          osmPurgeInfraMutation.mutate()
                        }}
                        disabled={!topologyId || osmPurgeInfraMutation.isPending}
                      >
                        Purge
                      </Button>
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => osmInfraStatusQuery.refetch()}
                        disabled={!topologyId || osmInfraStatusQuery.isFetching}
                      >
                        Refresh
                      </Button>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {(() => {
                        const counts = (osmMirrorStatsQuery.data as any)?.counts || {}
                        const get = (k: string) => Number(counts?.[k] || 0)
                        const chips = [
                          { label: 'Projects', v: get('osm:osm_project') },
                          { label: 'VIM', v: get('osm:vim_account') },
                          { label: 'WIM', v: get('osm:wim_account') },
                          { label: 'SDN', v: get('osm:sdn_controller') },
                          { label: 'VNFD', v: get('osm:vnfd_package') },
                          { label: 'NSD', v: get('osm:nsd_package') },
                          { label: 'NS', v: get('osm:ns_instance') },
                        ]
                        return chips.map((c) => (
                          <Badge key={c.label} variant="default" size="sm">
                            {c.label}: {c.v}
                          </Badge>
                        ))
                      })()}
                      {osmMirrorStatsQuery.isFetching ? (
                        <span className="text-xs text-gray-500 dark:text-gray-400">Syncing…</span>
                      ) : null}
                    </div>
                  </div>
                )}

                {topologyId && !osmConnectorRunning ? (
                  <div className="rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-800 dark:text-amber-200">
                    This topology does not have a running OSM stack yet. Click <span className="font-medium">Start / Ensure</span>.
                  </div>
                ) : null}

                {osmConnectorRunning ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="default" size="sm">NBI: {String(osmInfoQuery.data?.osm?.nbi_url || '—')}</Badge>
                    <Badge variant="default" size="sm">Auth: {String(osmInfoQuery.data?.osm?.auth_mode || '—')}</Badge>
                    <Badge variant="default" size="sm">Project: {String(osmInfoQuery.data?.osm?.project_id || '—')}</Badge>
                  </div>
                ) : null}

                {osmTab === 'overview' && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Projects</div>
                      <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                        <table className="min-w-full text-sm">
                          <thead className="bg-gray-50 dark:bg-gray-800">
                            <tr className="text-left">
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">ID</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(Array.isArray(osmProjectsQuery.data) ? osmProjectsQuery.data : []).map((p: any) => (
                              <tr key={String(p?._id || p?.id || p?.name)} className="border-t border-gray-200 dark:border-gray-800">
                                <td className="px-3 py-2 font-medium">{String(p?.name || '—')}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(p?._id || p?.id || '').slice(0, 12)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {!Array.isArray(osmProjectsQuery.data) || !osmProjectsQuery.data.length ? (
                          <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No projects.</div>
                        ) : null}
                      </div>
                      <details className="mt-2 text-sm">
                        <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Raw JSON</summary>
                        <div className="mt-2">
                          <JsonViewer data={osmProjectsQuery.data || null} collapsed={2} />
                        </div>
                      </details>
                    </div>
                    <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">VIM Accounts</div>
                      <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                        <table className="min-w-full text-sm">
                          <thead className="bg-gray-50 dark:bg-gray-800">
                            <tr className="text-left">
                              <th className="px-3 py-2 font-medium w-10" />
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">Type</th>
                              <th className="px-3 py-2 font-medium">State</th>
                              <th className="px-3 py-2 font-medium">ID</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(Array.isArray(osmVimAccountsQuery.data) ? osmVimAccountsQuery.data : []).map((v: any) => {
                              const id = String(v?._id || v?.id || '')
                              const name = String(v?.name || id || '—')
                              const vimType = String(v?.vim_type || '—')
                              const opState = String(v?._admin?.operationalState || v?.operationalState || '—')
                              const selected = id && id === String(osmSelectedVimAccountId)
                              return (
                                <tr
                                  key={id || name}
                                  className={cn(
                                    'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                                    selected && 'bg-blue-50 dark:bg-blue-950/30'
                                  )}
                                  onClick={() => setOsmSelectedVimAccountId(id)}
                                >
                                  <td className="px-3 py-2">
                                    <input
                                      type="radio"
                                      checked={selected}
                                      onChange={() => setOsmSelectedVimAccountId(id)}
                                    />
                                  </td>
                                  <td className="px-3 py-2 font-medium">{name}</td>
                                  <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{vimType}</td>
                                  <td className="px-3 py-2">
                                    <Badge variant={opState.toUpperCase() === 'ENABLED' ? 'success' : 'default'} size="sm">
                                      {opState}
                                    </Badge>
                                  </td>
                                  <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{id.slice(0, 12)}</td>
                                </tr>
                              )
                            })}
                          </tbody>
                        </table>
                        {!Array.isArray(osmVimAccountsQuery.data) || !osmVimAccountsQuery.data.length ? (
                          <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No VIM accounts.</div>
                        ) : null}
                      </div>
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <div className="text-xs text-gray-600 dark:text-gray-400">
                          Selected: {osmSelectedVimAccountId ? String(osmSelectedVimAccountId).slice(0, 12) : '—'}
                        </div>
                        <Button size="xs" variant="secondary" onClick={() => osmVimAccountsQuery.refetch()} disabled={osmVimAccountsQuery.isFetching}>
                          Refresh
                        </Button>
                      </div>
                      <details className="mt-2 text-sm">
                        <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Raw JSON</summary>
                        <div className="mt-2">
                          <JsonViewer data={osmVimAccountsQuery.data || null} collapsed={2} />
                        </div>
                      </details>
                    </div>

                    <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">SDN Controllers</div>
                      <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                        <table className="min-w-full text-sm">
                          <thead className="bg-gray-50 dark:bg-gray-800">
                            <tr className="text-left">
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">Type</th>
                              <th className="px-3 py-2 font-medium">URL</th>
                              <th className="px-3 py-2 font-medium">ID</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(Array.isArray(osmSdnControllersQuery.data) ? osmSdnControllersQuery.data : []).map((s: any) => (
                              <tr key={String(s?._id || s?.id || s?.name)} className="border-t border-gray-200 dark:border-gray-800">
                                <td className="px-3 py-2 font-medium">{String(s?.name || '—')}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(s?.type || '—')}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(s?.url || '—')}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(s?._id || s?.id || '').slice(0, 12)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {!Array.isArray(osmSdnControllersQuery.data) || !osmSdnControllersQuery.data.length ? (
                          <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No SDN controllers.</div>
                        ) : null}
                      </div>
                      <details className="mt-2 text-sm">
                        <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Raw JSON</summary>
                        <div className="mt-2">
                          <JsonViewer data={osmSdnControllersQuery.data || null} collapsed={2} />
                        </div>
                      </details>
                    </div>

                    <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">WIM Accounts</div>
                      <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                        <table className="min-w-full text-sm">
                          <thead className="bg-gray-50 dark:bg-gray-800">
                            <tr className="text-left">
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">Type</th>
                              <th className="px-3 py-2 font-medium">URL</th>
                              <th className="px-3 py-2 font-medium">ID</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(Array.isArray(osmWimAccountsQuery.data) ? osmWimAccountsQuery.data : []).map((w: any) => (
                              <tr key={String(w?._id || w?.id || w?.name)} className="border-t border-gray-200 dark:border-gray-800">
                                <td className="px-3 py-2 font-medium">{String(w?.name || '—')}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(w?.wim_type || '—')}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(w?.wim_url || '—')}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(w?._id || w?.id || '').slice(0, 12)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {!Array.isArray(osmWimAccountsQuery.data) || !osmWimAccountsQuery.data.length ? (
                          <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No WIM accounts.</div>
                        ) : null}
                      </div>
                      <details className="mt-2 text-sm">
                        <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Raw JSON</summary>
                        <div className="mt-2">
                          <JsonViewer data={osmWimAccountsQuery.data || null} collapsed={2} />
                        </div>
                      </details>
                    </div>
                  </div>
                )}

                {osmTab === 'packages' && (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-medium text-gray-700 dark:text-gray-300">NSD Packages</div>
                        <input
                          type="file"
                          className="text-sm"
                          onChange={(e) => {
                            const f = e.target.files?.[0]
                            if (f) uploadOsmNsdMutation.mutate(f)
                            e.currentTarget.value = ''
                          }}
                        />
                      </div>
                      <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                        <table className="min-w-full text-sm">
                          <thead className="bg-gray-50 dark:bg-gray-800">
                            <tr className="text-left">
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">ID</th>
                              <th className="px-3 py-2 w-24" />
                            </tr>
                          </thead>
                          <tbody>
                            {(Array.isArray(osmNsdPackagesQuery.data) ? osmNsdPackagesQuery.data : []).map((p: any) => (
                              <tr key={String(p._id || p.id)} className="border-t border-gray-200 dark:border-gray-800">
                                <td className="px-3 py-2">{String(p.name || p.id || p._id)}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(p._id || p.id).slice(0, 8)}</td>
                                <td className="px-3 py-2 text-right">
                                  <Button
                                    size="xs"
                                    variant="danger"
                                    onClick={() => deleteOsmNsdMutation.mutate(String(p._id || p.id))}
                                    disabled={deleteOsmNsdMutation.isPending}
                                  >
                                    Delete
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {!Array.isArray(osmNsdPackagesQuery.data) || !osmNsdPackagesQuery.data.length ? (
                          <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No NSD packages.</div>
                        ) : null}
                      </div>
                    </div>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="text-sm font-medium text-gray-700 dark:text-gray-300">VNFD Packages</div>
                        <input
                          type="file"
                          className="text-sm"
                          onChange={(e) => {
                            const f = e.target.files?.[0]
                            if (f) uploadOsmVnfdMutation.mutate(f)
                            e.currentTarget.value = ''
                          }}
                        />
                      </div>
                      <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                        <table className="min-w-full text-sm">
                          <thead className="bg-gray-50 dark:bg-gray-800">
                            <tr className="text-left">
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">ID</th>
                              <th className="px-3 py-2 w-24" />
                            </tr>
                          </thead>
                          <tbody>
                            {(Array.isArray(osmVnfdPackagesQuery.data) ? osmVnfdPackagesQuery.data : []).map((p: any) => (
                              <tr key={String(p._id || p.id)} className="border-t border-gray-200 dark:border-gray-800">
                                <td className="px-3 py-2">{String(p.name || p.id || p['product-name'] || p._id)}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(p._id || p.id).slice(0, 8)}</td>
                                <td className="px-3 py-2 text-right">
                                  <Button
                                    size="xs"
                                    variant="danger"
                                    onClick={() => deleteOsmVnfdMutation.mutate(String(p._id || p.id))}
                                    disabled={deleteOsmVnfdMutation.isPending}
                                  >
                                    Delete
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {!Array.isArray(osmVnfdPackagesQuery.data) || !osmVnfdPackagesQuery.data.length ? (
                          <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No VNFD packages.</div>
                        ) : null}
                      </div>
                    </div>
                  </div>
                )}

                {osmTab === 'ns' && (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                      <Input value={osmCreateNsName} onChange={(e) => setOsmCreateNsName(e.target.value)} label="NS name" />
                      <Input
                        value={osmCreateNsDescription}
                        onChange={(e) => setOsmCreateNsDescription(e.target.value)}
                        label="Description"
                      />
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">NSD package</label>
                        <select
                          value={osmSelectedNsdPkgId}
                          onChange={(e) => setOsmSelectedNsdPkgId(e.target.value)}
                          className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                        >
                          <option value="">(select)</option>
                          {(Array.isArray(osmNsdPackagesQuery.data) ? osmNsdPackagesQuery.data : []).map((p: any) => (
                            <option key={String(p._id || p.id)} value={String(p._id || p.id)}>
                              {String(p.name || p.id || p._id)}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        onClick={() => osmCreateNsMutation.mutate()}
                        disabled={!osmSelectedNsdPkgId || !osmCreateNsName.trim() || osmCreateNsMutation.isPending}
                        variant="primary"
                      >
                        Create NS Instance
                      </Button>
                      <Badge variant="default" size="sm">selected: {osmSelectedNsInstanceId ? osmSelectedNsInstanceId.slice(0, 8) : '—'}</Badge>
                    </div>
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">vimAccountId</label>
                        <select
                          value={osmSelectedVimAccountId}
                          onChange={(e) => setOsmSelectedVimAccountId(e.target.value)}
                          className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                        >
                          <option value="">(select)</option>
                          {(osmVimAccountsQuery.data || []).map((v: any) => (
                            <option key={String(v._id || v.id || v.name)} value={String(v._id || v.id || '')}>
                              {String(v.name || v._id || v.id)}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="flex items-end">
                        <Button
                          onClick={() => osmInstantiateNsMutation.mutate()}
                          disabled={!osmSelectedNsInstanceId || osmInstantiateNsMutation.isPending}
                          variant="secondary"
                        >
                          Instantiate (selected)
                        </Button>
                      </div>
                    </div>
                    <details className="text-sm">
                      <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Instantiate JSON (advanced)</summary>
                      <div className="mt-2">
                        <textarea
                          value={osmInstantiateJson}
                          onChange={(e) => setOsmInstantiateJson(e.target.value)}
                          rows={6}
                          className="w-full px-3 py-2 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 font-mono text-xs"
                        />
                      </div>
                    </details>

                    <div className="max-h-80 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                          <tr className="text-left">
                            <th className="px-3 py-2 font-medium">Name</th>
                            <th className="px-3 py-2 font-medium">State</th>
                            <th className="px-3 py-2 font-medium">ID</th>
                            <th className="px-3 py-2 w-40" />
                          </tr>
                        </thead>
                        <tbody>
                          {(Array.isArray(osmNsInstancesQuery.data) ? osmNsInstancesQuery.data : []).map((x: any) => (
                            <tr
                              key={String(x._id || x.id)}
                              className={cn(
                                'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                                osmSelectedNsInstanceId === String(x._id || x.id) && 'bg-blue-50 dark:bg-blue-950/30'
                              )}
                              onClick={() => setOsmSelectedNsInstanceId(String(x._id || x.id))}
                            >
                              <td className="px-3 py-2">{String(x.name || x.nsName || x._id || x.id)}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(x.nsState || x.status || x.operationalStatus || '—')}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(x._id || x.id).slice(0, 8)}</td>
                              <td className="px-3 py-2 text-right flex items-center justify-end gap-2">
                                <Button
                                  size="xs"
                                  variant="secondary"
                                  onClick={(e) => {
                                    e.preventDefault()
                                    e.stopPropagation()
                                    osmTerminateNsMutation.mutate(String(x._id || x.id))
                                  }}
                                  disabled={osmTerminateNsMutation.isPending}
                                >
                                  Terminate
                                </Button>
                                <Button
                                  size="xs"
                                  variant="danger"
                                  onClick={(e) => {
                                    e.preventDefault()
                                    e.stopPropagation()
                                    osmDeleteNsMutation.mutate(String(x._id || x.id))
                                  }}
                                  disabled={osmDeleteNsMutation.isPending}
                                >
                                  Delete
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {!Array.isArray(osmNsInstancesQuery.data) || !osmNsInstancesQuery.data.length ? (
                        <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No OSM NS instances.</div>
                      ) : null}
                    </div>
                  </div>
                )}

	                {osmTab === 'mirror' && (
	                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-3">
                      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Resource type</label>
                      <select
                        value={osmMirrorResourceType}
                        onChange={(e) => setOsmMirrorResourceType(e.target.value)}
                        className="px-3 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
                      >
                        <option value="">(all)</option>
                        <option value="osm_project">osm_project</option>
                        <option value="vim_account">vim_account</option>
                        <option value="wim_account">wim_account</option>
                        <option value="sdn_controller">sdn_controller</option>
                        <option value="vnfd_package">vnfd_package</option>
                        <option value="nsd_package">nsd_package</option>
                        <option value="ns_instance">ns_instance</option>
                        <option value="ns_lcm_op_occ">ns_lcm_op_occ</option>
                      </select>

                      <label className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={osmMirrorIncludeDeleted}
                          onChange={(e) => setOsmMirrorIncludeDeleted(e.target.checked)}
                        />
                        include deleted
                      </label>

                      <div className="flex-1" />
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => osmMirrorResourcesQuery.refetch()}
                        disabled={!topologyId || osmMirrorResourcesQuery.isFetching}
                      >
                        Refresh
                      </Button>
                    </div>

                    <div className="max-h-80 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                          <tr className="text-left">
                            <th className="px-3 py-2 font-medium">Type</th>
                            <th className="px-3 py-2 font-medium">Name</th>
                            <th className="px-3 py-2 font-medium">External ID</th>
                            <th className="px-3 py-2 font-medium">Deleted</th>
                          </tr>
                        </thead>
                        <tbody>
                          {((osmMirrorResourcesQuery.data as any)?.items || []).map((r: any) => {
                            const id = String(r?.id || '')
                            const selected = id && id === String(osmMirrorSelectedId)
                            return (
                              <tr
                                key={id || String(r?.external_id || Math.random())}
                                className={cn(
                                  'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                                  selected && 'bg-blue-50 dark:bg-blue-950/30'
                                )}
                                onClick={() => setOsmMirrorSelectedId(id)}
                              >
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(r?.resource_type || '—')}</td>
                                <td className="px-3 py-2 font-medium">{String(r?.name || '—')}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(r?.external_id || '').slice(0, 18)}</td>
                                <td className="px-3 py-2">
                                  <Badge variant={r?.deleted ? 'default' : 'success'} size="sm">
                                    {r?.deleted ? 'yes' : 'no'}
                                  </Badge>
                                </td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                      {!((osmMirrorResourcesQuery.data as any)?.items || []).length ? (
                        <div className="p-3 text-sm text-gray-600 dark:text-gray-400">
                          {osmMirrorResourcesQuery.isFetching ? 'Loading…' : 'No mirrored resources.'}
                        </div>
                      ) : null}
                    </div>

                    {(() => {
                      const items = ((osmMirrorResourcesQuery.data as any)?.items || []) as any[]
                      const selected = items.find((x) => String(x?.id) === String(osmMirrorSelectedId))
                      if (!selected) return null
                      return (
                        <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
                              Selected: {String(selected?.resource_type || 'resource')} · {String(selected?.name || '').trim() || String(selected?.external_id || '').slice(0, 12)}
                            </div>
                            <Button size="xs" variant="secondary" onClick={() => setOsmMirrorSelectedId('')}>
                              Clear
                            </Button>
                          </div>
                          <div className="mt-2">
                            <JsonViewer data={selected} collapsed={2} />
                          </div>
                        </div>
                      )
                    })()}
	                  </div>
	                )}

	                {osmTab === 'ui' && (
	                  <div className="space-y-3">
	                    {!topologyId ? (
	                      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 p-3 text-sm text-gray-700 dark:text-gray-300">
	                        Select a topology first. ETSI OSM runs as an isolated per-topology stack.
	                      </div>
	                    ) : (
	                      <>
	                        <div className="flex flex-wrap items-center gap-2">
	                          <Badge variant="default" size="sm">
	                            Login: admin / admin
	                          </Badge>
	                          <Badge variant={osmConnectorRunning ? 'success' : 'default'} size="sm">
	                            Stack: {osmConnectorRunning ? 'running' : 'stopped'}
	                          </Badge>
	                          <Button
	                            size="xs"
	                            variant="secondary"
	                            onClick={() => osmEnsureInfraMutation.mutate()}
	                            disabled={!topologyId || osmEnsureInfraMutation.isPending}
	                          >
	                            Start / Ensure
	                          </Button>
	                        </div>

	                        <div className="flex flex-wrap items-center gap-2">
	                          <Button
	                            size="xs"
	                            variant={osmUiKind === 'ng' ? 'primary' : 'secondary'}
	                            onClick={() => setOsmUiKind('ng')}
	                          >
	                            NG-UI
	                          </Button>
	                          <Button
	                            size="xs"
	                            variant={osmUiKind === 'light' ? 'primary' : 'secondary'}
	                            onClick={() => setOsmUiKind('light')}
	                          >
	                            Light UI
	                          </Button>
	                          <Button
	                            size="xs"
	                            variant="secondary"
	                            onClick={() => {
	                              const id8 = String(topologyId).slice(0, 8)
	                              window.open(
	                                osmUiKind === 'ng' ? `/infra-proxy/osm-ng-ui/${id8}/` : `/infra-proxy/osm-light-ui/${id8}/`,
	                                '_blank',
	                                'noopener,noreferrer'
	                              )
	                            }}
	                          >
	                            Open in new tab
	                          </Button>
	                        </div>

	                        {!osmConnectorRunning ? (
	                          <div className="rounded-xl border border-yellow-200 dark:border-yellow-900 bg-yellow-50 dark:bg-yellow-950/30 p-3 text-sm text-yellow-900 dark:text-yellow-200">
	                            OSM stack is not running yet. Click “Start / Ensure”, then reload this tab.
	                          </div>
	                        ) : (
	                          <div className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
	                            <iframe
	                              title={osmUiKind === 'ng' ? 'OSM NG-UI' : 'OSM Light UI'}
	                              className="w-full h-[720px] bg-white"
	                              src={
	                                osmUiKind === 'ng'
	                                  ? `/infra-proxy/osm-ng-ui/${String(topologyId).slice(0, 8)}/`
	                                  : `/infra-proxy/osm-light-ui/${String(topologyId).slice(0, 8)}/`
	                              }
	                            />
	                          </div>
	                        )}
	                      </>
	                    )}
	                  </div>
	                )}
	              </CardContent>
		            </Card>
	              </>
	            )}

	            {manoPane === 'local' && (
	              <>
	              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between gap-3">
                    <CardTitle>Catalog</CardTitle>
                    <div className="flex items-center gap-2">
                      <Button
                        size="xs"
                        variant={manoCatalogTab === 'nsd' ? 'primary' : 'secondary'}
                        onClick={() => setManoCatalogTab('nsd')}
                      >
                        NSDs
                      </Button>
                      <Button
                        size="xs"
                        variant={manoCatalogTab === 'vnfd' ? 'primary' : 'secondary'}
                        onClick={() => setManoCatalogTab('vnfd')}
                      >
                        VNFDs
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {manoCatalogTab === 'nsd' ? (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      <div className="space-y-3">
                        <Input value={manoNsdName} onChange={(e) => setManoNsdName(e.target.value)} label="NSD name" />
                        <Input
                          value={manoNsdTopologyId}
                          onChange={(e) => setManoNsdTopologyId(e.target.value)}
                          label="Topology ID"
                          helperText="Leave empty for descriptor-only catalogs; use a valid topology UUID to orchestrate."
                        />
                        <div>
                          <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Options</div>
                          <KvTableEditor rows={manoNsdOptionRows} setRows={setManoNsdOptionRows} />
                          {!!manoNsdDescriptor.errors.length && (
                            <div className="mt-2 text-xs text-red-600 dark:text-red-400">
                              {manoNsdDescriptor.errors.join(' · ')}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            onClick={() => upsertNsdMutation.mutate()}
                            disabled={upsertNsdMutation.isPending || !!manoNsdDescriptor.errors.length || !manoNsdName.trim()}
                            variant="primary"
                          >
                            Save NSD
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() => {
                              setManoSelectedNsdId('')
                              setManoNsdName('demo-nsd')
                              setManoNsdTopologyId(topologyId || '')
                              setManoNsdOptionRows([newKvRow()])
                            }}
                          >
                            New
                          </Button>
                        </div>
                        <details className="text-sm">
                          <summary className="cursor-pointer text-gray-700 dark:text-gray-300">JSON preview</summary>
                          <div className="mt-2">
                            <JsonViewer data={manoNsdDescriptor.descriptor} collapsed={2} />
                          </div>
                        </details>
                      </div>

                      <div className="space-y-2">
                        <div className="text-sm font-medium text-gray-700 dark:text-gray-300">NSDs</div>
                        <div className="max-h-80 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                          <table className="min-w-full text-sm">
                            <thead className="bg-gray-50 dark:bg-gray-800">
                              <tr className="text-left">
                                <th className="px-3 py-2 font-medium">Name</th>
                                <th className="px-3 py-2 font-medium">ID</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(manoNsdsQuery.data || []).map((nsd: any) => (
                                <tr
                                  key={nsd.id}
                                  className={cn(
                                    'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                                    manoSelectedNsdId === String(nsd.id) && 'bg-blue-50 dark:bg-blue-950/30'
                                  )}
                                  onClick={() => {
                                    setManoSelectedNsdId(String(nsd.id))
                                    setManoNsdName(String(nsd.name || ''))
                                    const d = (nsd.descriptor || {}) as any
                                    setManoNsdTopologyId(String(d.topology_id || topologyId || ''))
                                    setManoNsdOptionRows(kvObjectToRows(d.options || {}))
                                  }}
                                >
                                  <td className="px-3 py-2 font-medium">{nsd.name}</td>
                                  <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                                    {String(nsd.id).slice(0, 8)}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {!manoNsdsQuery.data?.length && (
                            <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No NSDs yet.</div>
                          )}
                        </div>

                        {manoSelectedNsd && (
                          <details className="text-sm">
                            <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Selected NSD details</summary>
                            <div className="mt-2">
                              <JsonViewer data={manoSelectedNsd} collapsed={2} />
                            </div>
                          </details>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                      <div className="space-y-3">
                        <Input value={manoVnfdName} onChange={(e) => setManoVnfdName(e.target.value)} label="VNFD name" />
                        <Input
                          value={manoVnfdDeviceType}
                          onChange={(e) => setManoVnfdDeviceType(e.target.value)}
                          label="Device type"
                          helperText="Examples: container, host, router, switch, station"
                        />
                        <div>
                          <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Default properties</div>
                          <KvTableEditor rows={manoVnfdDefaultsRows} setRows={setManoVnfdDefaultsRows} />
                          {!!manoVnfdDescriptor.errors.length && (
                            <div className="mt-2 text-xs text-red-600 dark:text-red-400">
                              {manoVnfdDescriptor.errors.join(' · ')}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            onClick={() => upsertVnfdMutation.mutate()}
                            disabled={upsertVnfdMutation.isPending || !!manoVnfdDescriptor.errors.length || !manoVnfdName.trim()}
                            variant="primary"
                          >
                            Save VNFD
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() => {
                              setManoSelectedVnfdId('')
                              setManoVnfdName('demo-vnfd')
                              setManoVnfdDeviceType('container')
                              setManoVnfdDefaultsRows([newKvRow()])
                            }}
                          >
                            New
                          </Button>
                        </div>
                        <details className="text-sm">
                          <summary className="cursor-pointer text-gray-700 dark:text-gray-300">JSON preview</summary>
                          <div className="mt-2">
                            <JsonViewer data={manoVnfdDescriptor.descriptor} collapsed={2} />
                          </div>
                        </details>
                      </div>

                      <div className="space-y-2">
                        <div className="text-sm font-medium text-gray-700 dark:text-gray-300">VNFDs</div>
                        <div className="max-h-80 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                          <table className="min-w-full text-sm">
                            <thead className="bg-gray-50 dark:bg-gray-800">
                              <tr className="text-left">
                                <th className="px-3 py-2 font-medium">Name</th>
                                <th className="px-3 py-2 font-medium">Type</th>
                              </tr>
                            </thead>
                            <tbody>
                              {(manoVnfdsQuery.data || []).map((vnfd: any) => (
                                <tr
                                  key={vnfd.id}
                                  className={cn(
                                    'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                                    manoSelectedVnfdId === String(vnfd.id) && 'bg-blue-50 dark:bg-blue-950/30'
                                  )}
                                  onClick={() => {
                                    setManoSelectedVnfdId(String(vnfd.id))
                                    setManoVnfdName(String(vnfd.name || ''))
                                    const d = (vnfd.descriptor || {}) as any
                                    setManoVnfdDeviceType(String(d.device_type || 'container'))
                                    setManoVnfdDefaultsRows(kvObjectToRows(d.default_properties || {}))
                                  }}
                                >
                                  <td className="px-3 py-2 font-medium">{vnfd.name}</td>
                                  <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                                    {String(vnfd?.descriptor?.device_type || '—')}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                          {!manoVnfdsQuery.data?.length && (
                            <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No VNFDs yet.</div>
                          )}
                        </div>
                        {manoSelectedVnfd && (
                          <details className="text-sm">
                            <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Selected VNFD details</summary>
                            <div className="mt-2">
                              <JsonViewer data={manoSelectedVnfd} collapsed={2} />
                            </div>
                          </details>
                        )}
                      </div>
                    </div>
                    )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>NS Instances</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <Input value={manoNsName} onChange={(e) => setManoNsName(e.target.value)} label="NS name" />
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">NSD</label>
                      {manoNsBackend === 'osm' ? (
                        <Input
                          value={manoOsmNsdId}
                          onChange={(e) => setManoOsmNsdId(e.target.value)}
                          placeholder="OSM nsd_id"
                        />
                      ) : (
                        <select
                          value={manoSelectedNsdId}
                          onChange={(e) => setManoSelectedNsdId(e.target.value)}
                          className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                        >
                          <option value="">(none)</option>
                          {(manoNsdsQuery.data || []).map((nsd: any) => (
                            <option key={nsd.id} value={String(nsd.id)}>
                              {nsd.name}
                            </option>
                          ))}
                        </select>
                      )}
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Backend</label>
                      <select
                        value={manoNsBackend}
                        onChange={(e) => setManoNsBackend(e.target.value as any)}
                        className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                      >
                        <option value="local">local (Mininet)</option>
                        <option value="osm">OSM (ETSI NFVO)</option>
                      </select>
                    </div>
                    {manoNsBackend === 'osm' ? (
                      <Input
                        value={manoOsmVimAccountId}
                        onChange={(e) => setManoOsmVimAccountId(e.target.value)}
                        label="vim_account_id"
                        placeholder="OSM vimAccountId"
                      />
                    ) : (
                      <div />
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <label className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={manoNsDryRun} onChange={(e) => setManoNsDryRun(e.target.checked)} />
                      dry_run
                    </label>
                    <Button onClick={() => createNsMutation.mutate()} disabled={createNsMutation.isPending || !manoNsName.trim()} variant="primary">
                      Create NS
                    </Button>
                    {manoNsBackend === 'local' && (
                      <Badge variant="default" size="sm">
                        topology: {topologyId ? topologyId.slice(0, 8) : '—'}
                      </Badge>
                    )}
                  </div>

                  <div className="max-h-[420px] overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-50 dark:bg-gray-800">
                        <tr className="text-left">
                          <th className="px-3 py-2 font-medium">Name</th>
                          <th className="px-3 py-2 font-medium">Status</th>
                          <th className="px-3 py-2 font-medium">Backend</th>
                          <th className="px-3 py-2 font-medium">NSD</th>
                          <th className="px-3 py-2 w-28" />
                        </tr>
                      </thead>
                      <tbody>
                        {(manoNsInstancesQuery.data || []).map((ns: any) => (
                          <tr
                            key={ns.id}
                            className={cn(
                              'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                              manoSelectedNsId === String(ns.id) && 'bg-blue-50 dark:bg-blue-950/30'
                            )}
                            onClick={() => setManoSelectedNsId(String(ns.id))}
                          >
                            <td className="px-3 py-2 font-medium">{ns.name}</td>
                            <td className="px-3 py-2">
                              <Badge variant="default" size="sm">
                                {String(ns.status)}
                              </Badge>
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(ns.backend || 'local')}</td>
                            <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                              {ns.nsd_id ? String(ns.nsd_id).slice(0, 8) : '—'}
                            </td>
                            <td className="px-3 py-2 text-right">
                              <Button
                                size="xs"
                                variant="secondary"
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  terminateNsMutation.mutate(String(ns.id))
                                }}
                                disabled={terminateNsMutation.isPending}
                              >
                                Terminate
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!manoNsInstancesQuery.data?.length && (
                      <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No NS instances yet.</div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>VNFM (VNF Instances)</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">NS</label>
                    <select
                      value={manoSelectedNsId}
                      onChange={(e) => setManoSelectedNsId(e.target.value)}
                      className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                    >
                      <option value="">(select NS instance)</option>
                      {(manoNsInstancesQuery.data || []).map((ns: any) => (
                        <option key={ns.id} value={String(ns.id)}>
                          {ns.name} ({String(ns.id).slice(0, 8)})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">VNFD</label>
                    <select
                      value={manoSelectedVnfdId}
                      onChange={(e) => setManoSelectedVnfdId(e.target.value)}
                      className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                    >
                      <option value="">(optional)</option>
                      {(manoVnfdsQuery.data || []).map((vnfd: any) => (
                        <option key={vnfd.id} value={String(vnfd.id)}>
                          {vnfd.name}
                        </option>
                      ))}
                    </select>
                    {manoSelectedVnfd && (
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <div className="text-xs text-gray-600 dark:text-gray-400">
                          type: {String(manoSelectedVnfd?.descriptor?.device_type || '—')}
                        </div>
                        <Button
                          size="xs"
                          variant="secondary"
                          onClick={() => {
                            const d = (manoSelectedVnfd?.descriptor || {}) as any
                            setManoVnfDeviceType(String(d.device_type || manoVnfDeviceType || 'container'))
                            setManoVnfPropsRows(kvObjectToRows(d.default_properties || {}))
                          }}
                        >
                          Apply defaults
                        </Button>
                      </div>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <Input value={manoVnfName} onChange={(e) => setManoVnfName(e.target.value)} label="VNF name" />
                    <Input
                      value={manoVnfDeviceType}
                      onChange={(e) => setManoVnfDeviceType(e.target.value)}
                      label="Device type"
                      helperText="Used if VNFD is not set or defaults are overridden."
                    />
                  </div>

                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Properties</div>
                    <KvTableEditor rows={manoVnfPropsRows} setRows={setManoVnfPropsRows} />
                    {!!manoVnfProperties.errors.length && (
                      <div className="mt-2 text-xs text-red-600 dark:text-red-400">
                        {manoVnfProperties.errors.join(' · ')}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    <label className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={manoVnfDryRun} onChange={(e) => setManoVnfDryRun(e.target.checked)} />
                      dry_run
                    </label>
                    <Button
                      onClick={() => createVnfMutation.mutate()}
                      disabled={!manoSelectedNsId || createVnfMutation.isPending || !!manoVnfProperties.errors.length || !manoVnfName.trim()}
                      variant="primary"
                    >
                      Create VNF
                    </Button>
                  </div>

                  <details className="text-sm">
                    <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Properties JSON</summary>
                    <div className="mt-2">
                      <JsonViewer data={manoVnfProperties.properties} collapsed={2} />
                    </div>
                  </details>

                  <div className="max-h-64 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-50 dark:bg-gray-800">
                        <tr className="text-left">
                          <th className="px-3 py-2 font-medium">Name</th>
                          <th className="px-3 py-2 font-medium">Status</th>
                          <th className="px-3 py-2 font-medium">Device</th>
                          <th className="px-3 py-2 font-medium">Message</th>
                          <th className="px-3 py-2 w-24" />
                        </tr>
                      </thead>
                      <tbody>
                        {(manoVnfsQuery.data || []).map((vnf: any) => (
                          <tr
                            key={vnf.id}
                            className={cn(
                              'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                              manoSelectedVnfId === String(vnf.id) && 'bg-blue-50 dark:bg-blue-950/30'
                            )}
                            onClick={() => setManoSelectedVnfId(String(vnf.id))}
                          >
                            <td className="px-3 py-2 font-medium">{vnf.name}</td>
                            <td className="px-3 py-2">
                              <Badge variant="default" size="sm">
                                {String(vnf.status)}
                              </Badge>
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                              {vnf.device_name || '—'} ({vnf.device_type})
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400 truncate max-w-[240px]" title={String(vnf.message || '')}>
                              {String(vnf.message || '—')}
                            </td>
                            <td className="px-3 py-2 text-right">
                              <Button
                                size="xs"
                                variant="danger"
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  const name = String(vnf?.name || vnf?.id || 'VNF')
                                  if (!confirm(`Delete ${name}?`)) return
                                  deleteVnfMutation.mutate({ vnfId: String(vnf.id), force: manoVnfDeleteForce })
                                }}
                                disabled={deleteVnfMutation.isPending}
                              >
                                Delete
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!manoVnfsQuery.data?.length && (
                      <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No VNFs yet.</div>
                    )}
                  </div>

                  <div className="flex flex-wrap items-center gap-3">
                    <label className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={manoVnfDeleteForce}
                        onChange={(e) => setManoVnfDeleteForce(e.target.checked)}
                      />
                      force delete
                    </label>
                    <div className="flex-1" />
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => {
                        if (!manoSelectedVnfId) return
                        const selected = (manoVnfsQuery.data || []).find((x: any) => String(x?.id) === String(manoSelectedVnfId))
                        const name = String(selected?.name || manoSelectedVnfId)
                        if (!confirm(`Delete selected VNF: ${name}?`)) return
                        deleteVnfMutation.mutate({ vnfId: manoSelectedVnfId, force: manoVnfDeleteForce })
                      }}
                      disabled={!manoSelectedVnfId || deleteVnfMutation.isPending}
                    >
                      Delete selected
                    </Button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <Input value={manoExecCommand} onChange={(e) => setManoExecCommand(e.target.value)} label="Command" />
                    <Button onClick={() => execVnfMutation.mutate()} disabled={!manoSelectedVnfId || execVnfMutation.isPending} variant="secondary">
                      Exec (selected VNF)
                    </Button>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>VIM Inventory</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3 max-h-[720px] overflow-auto">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="default" size="sm">topology: {manoInventoryQuery.data?.scope?.topology_id ? String(manoInventoryQuery.data.scope.topology_id).slice(0, 8) : '—'}</Badge>
                    <Badge variant="default" size="sm">emulation: {manoInventoryQuery.data?.scope?.emulation_id ? String(manoInventoryQuery.data.scope.emulation_id).slice(0, 8) : '—'}</Badge>
                    <Badge variant="default" size="sm">errors: {String((manoInventoryQuery.data?.errors || []).length)}</Badge>
                  </div>
                  {!!(manoInventoryQuery.data?.errors || []).length && (
                    <div className="space-y-1">
                      {(manoInventoryQuery.data?.errors || []).map((e: any, idx: number) => (
                        <div key={idx} className="text-xs text-red-600 dark:text-red-400">
                          {e.component}: {e.error}
                        </div>
                      ))}
                    </div>
                  )}
                  <details className="text-sm">
                    <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Devices</summary>
                    <div className="mt-2">
                      <JsonViewer data={manoInventoryQuery.data?.devices || null} collapsed={2} />
                    </div>
                  </details>
                  <details className="text-sm">
                    <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Containers</summary>
                    <div className="mt-2">
                      <JsonViewer data={manoInventoryQuery.data?.containers || null} collapsed={2} />
                    </div>
                  </details>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Operations</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2 max-h-[720px] overflow-auto">
                  {(manoOpsQuery.data?.items || []).map((op: any) => (
                    <details key={op.id} className="p-3 rounded-lg border border-gray-200 dark:border-gray-800">
                      <summary className="cursor-pointer list-none">
                        <div className="flex items-center justify-between gap-2">
                          <div className="font-medium text-sm">{op.kind}</div>
                          <Badge variant="default" size="sm">{op.status}</Badge>
                        </div>
                        <div className="text-xs text-gray-600 dark:text-gray-400">{String(op.id).slice(0, 8)}</div>
                        {op.message && <div className="text-xs mt-1">{op.message}</div>}
                      </summary>
                      <div className="mt-2">
                        <JsonViewer data={op} collapsed={2} />
                      </div>
                    </details>
                  ))}
                  {!manoOpsQuery.data?.items?.length && (
                    <div className="text-sm text-gray-600 dark:text-gray-400">No operations yet.</div>
                  )}
                </CardContent>
	              </Card>
	            </div>
	              </>
	            )}
          </div>
            */}
          </>
        )}

        {activeTab === 'container-ui' && (
          <div className="animate-fade-in">
            <ContainerUI topologyId={topologyId || undefined} devices={runtimeDevices} isRunning={isRunning} />
          </div>
        )}

        {activeTab === 'ai-console' && (
          <AiConsole scopeTopologyId={topologyId || undefined} />
        )}

        {activeTab === 'ml-models' && (
          <div className="space-y-4 animate-fade-in">
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">ML Models</h2>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Upload and select operational ML models/algorithms for streaming decisions (anomaly, routing, MANO).
              </p>
            </div>
            <MlModelsPanel />
          </div>
        )}

        {activeTab === 'data-lab' && (
          <div className="space-y-4 animate-fade-in">
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">Data Lab</h2>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Embedded JupyterLab workspace for training/evaluation and offline analysis (metrics, models, pcaps).
              </p>
            </div>
            <DataLabPanel embedded />
          </div>
        )}
      </div>
    </div>
  )
}
