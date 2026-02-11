import { useState, useMemo, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'
import { ServerIcon, ExclamationTriangleIcon, CpuChipIcon } from '@heroicons/react/24/outline'
import { infrastructureAPI } from '@/services/api'
import toast from 'react-hot-toast'

interface Device {
  name: string
  device_type?: string
  type?: string
  ip?: string
  properties?: any
  runtime_name?: string
  interfaces?: Array<{ name?: string; ip?: string; status?: string }>
}

interface ContainerUIProps {
  devices?: Device[]
  isRunning?: boolean
  topologyId?: string
}

const INFRASTRUCTURE_SERVICES = [
  { name: 'grafana', displayName: 'Grafana', port: 3001, description: 'Metrics visualization and dashboards' },
  { name: 'prometheus', displayName: 'Prometheus', port: 9090, description: 'Metrics collection and querying' },
  { name: 'consul', displayName: 'Consul', port: 8500, description: 'Service mesh and discovery' },
  { name: 'influxdb', displayName: 'InfluxDB', port: 8086, description: 'Time-series database UI' },
  { name: 'pgadmin', displayName: 'pgAdmin', port: 5050, description: 'PostgreSQL admin UI (shared)' },
  { name: 'mongo-express', displayName: 'Mongo Express', port: 8096, description: 'MongoDB admin UI (shared)' },
  { name: 'rabbitmq', displayName: 'RabbitMQ', port: 15672, description: 'Message broker management' },
  { name: 'kafka-ui', displayName: 'Kafka UI', port: 8093, description: 'Kafka topics/consumers browser (shared)' },
  { name: 'flink', displayName: 'Flink', port: 8088, description: 'Flink streaming job manager UI (shared)' },
  { name: 'spark', displayName: 'Spark', port: 8094, description: 'Spark master UI (shared)' },
  { name: 'hdfs', displayName: 'HDFS', port: 9870, description: 'HDFS NameNode UI (shared)' },
  { name: 'hive', displayName: 'Hive', port: 10002, description: 'HiveServer2 web UI (shared)' },
  { name: 'hue', displayName: 'Hue', port: 8889, description: 'HDFS + Hive web UI (shared)' },
]

type InfraService = {
  name: string
  displayName: string
  port: number
  description: string
  path?: string
  scheme?: string
  controllerId?: string
  controllerUiPort?: number
}

export default function ContainerUI({ devices = [], isRunning = false, topologyId }: ContainerUIProps) {
  const { t } = useTranslation()
  const [selectedNode, setSelectedNode] = useState<string>('')
  const [selectedPort, setSelectedPort] = useState<string>('8080')
  const [viewMode, setViewMode] = useState<'emulation' | 'infrastructure'>(() => (topologyId ? 'infrastructure' : 'emulation'))
  const [selectedService, setSelectedService] = useState<string>(() => (topologyId ? 'osm-ng-ui' : INFRASTRUCTURE_SERVICES[0].name))
  const [iframeError, setIframeError] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [loadTimeout, setLoadTimeout] = useState<NodeJS.Timeout | null>(null)
  const [topologyInfra, setTopologyInfra] = useState<any>(null)
  const [topologyInfraError, setTopologyInfraError] = useState<string | null>(null)
  const [topologyInfraCreds, setTopologyInfraCreds] = useState<any>(null)
  const [infraActionError, setInfraActionError] = useState<string | null>(null)
  const infraLoadInFlight = useRef(false)

  // Get container/host devices from emulation
  const containerDevices = useMemo(() => {
    return devices.filter((d: Device) => {
      const type = (d.device_type || d.type || '').toLowerCase()
      return ['host', 'container'].includes(type)
    })
  }, [devices])

  // Set default selected node
  useMemo(() => {
    if (containerDevices.length > 0 && !selectedNode) {
      setSelectedNode(containerDevices[0].name)
    }
  }, [containerDevices, selectedNode])

  const selectedDevice = useMemo(() => {
    return containerDevices.find((d: Device) => d.name === selectedNode)
  }, [containerDevices, selectedNode])

  const infraServices = useMemo(() => {
    const services = topologyInfra?.infra?.services
    const out: InfraService[] = []
    if (!services || typeof services !== 'object') {
      out.push(...(INFRASTRUCTURE_SERVICES as any))
    } else {
      const desc: Record<string, string> = {
        grafana: 'Topology dashboards (isolated)',
        prometheus: 'Topology Prometheus (isolated)',
        consul: 'Topology Consul UI (isolated)',
        influxdb: 'Topology InfluxDB UI (isolated)',
        rabbitmq: 'Topology RabbitMQ Management (isolated)',
        'kafka-ui': 'Topology Kafka UI (isolated)',
      }
      const display: Record<string, string> = {
        grafana: 'Grafana',
        prometheus: 'Prometheus',
        consul: 'Consul',
        influxdb: 'InfluxDB',
        rabbitmq: 'RabbitMQ',
        'kafka-ui': 'Kafka UI',
      }

      out.push(
        ...Object.entries(services)
          .map(([id, cfg]: any) => {
            const port = Number(cfg?.host_port)
            return {
              name: id,
              displayName: display[id] || id,
              port: Number.isFinite(port) ? port : 0,
              description: desc[id] || 'Topology infrastructure service',
              path: String(cfg?.path || '/'),
              scheme: String(cfg?.scheme || 'http'),
            } satisfies InfraService
          })
          .filter((s) => s.port > 0)
      )

      // Always include shared UIs that are not part of the isolated infra stack (best-effort).
      const sharedExtras = new Set(['pgadmin', 'mongo-express', 'flink', 'spark', 'hdfs', 'hive', 'hue'])
      for (const svc of INFRASTRUCTURE_SERVICES as any[]) {
        if (!sharedExtras.has(String(svc.name))) continue
        if (out.some((s) => s.name === svc.name)) continue
        out.push(svc as any)
      }
    }

    const controllerEntries = (topologyInfra as any)?.controllers?.controllers
    if (controllerEntries && typeof controllerEntries === 'object') {
      for (const [controllerId, cfg] of Object.entries(controllerEntries as any)) {
        const c = cfg as any
        const ui = c?.ui
        const hostPort = Number(ui?.host_port)
        const containerPort = Number(ui?.container_port)
        if (!Number.isFinite(hostPort) || hostPort <= 0) continue
        if (!Number.isFinite(containerPort) || containerPort <= 0) continue
        const nodeName = String(c?.node_name || controllerId)
        const controllerType = String(c?.controller_type || 'controller')
        const path = String(ui?.path || '/')
        out.push({
          name: `controller:${controllerId}`,
          displayName: `${nodeName} (${controllerType})`,
          port: hostPort,
          description: `Controller UI for ${nodeName} (${controllerType})`,
          path,
          controllerId: String(controllerId),
          controllerUiPort: containerPort,
        })
      }
    }

    if (topologyId) {
      out.push(
        {
          name: 'osm-ng-ui',
          displayName: 'OSM NG-UI (ETSI)',
          port: 80,
          description: 'Per-topology ETSI OSM native UI (proxied)',
          path: '/',
          scheme: 'http',
        },
        {
          name: 'osm-light-ui',
          displayName: 'OSM Light UI (ETSI)',
          port: 80,
          description: 'Per-topology ETSI OSM Light UI (proxied)',
          path: '/',
          scheme: 'http',
        }
      )
    }

    return out.length ? out : (INFRASTRUCTURE_SERVICES as any)
  }, [topologyId, topologyInfra])

  const parseDockerPorts = (value: any): Record<string, number> => {
    const out: Record<string, number> = {}
    if (!value) return out
    if (typeof value === 'object') {
      for (const [k, v] of Object.entries(value)) {
        const port = Number(v as any)
        if (Number.isFinite(port) && port > 0) out[String(k)] = port
      }
      return out
    }
    const s = String(value)
    const re = /['"]?(\d+)\/(tcp|udp)['"]?\s*:\s*([0-9]+)/g
    let m: RegExpExecArray | null
    while ((m = re.exec(s))) {
      out[`${m[1]}/${m[2]}`] = Number(m[3])
    }
    return out
  }

  const pickDeviceIp = (d?: Device): string | undefined => {
    const fromInterfaces = d?.interfaces?.find((i) => i?.ip && String(i.ip).includes('.'))?.ip
    const ip = String(fromInterfaces || d?.ip || '').trim()
    if (!ip) return undefined
    return ip.split('/', 1)[0]
  }

  const getNodeUrl = (): string => {
    const hasIsolatedInfraService = (serviceId: string): boolean => {
      const services = (topologyInfra as any)?.infra?.services
      if (!services || typeof services !== 'object') return false
      return Boolean((services as any)[serviceId])
    }

    if (viewMode === 'infrastructure') {
      if ((selectedService === 'osm-ng-ui' || selectedService === 'osm-light-ui') && topologyId) {
        const id8 = topologyId.slice(0, 8)
        return selectedService === 'osm-ng-ui' ? `/infra-proxy/osm-ng-ui/${id8}/` : `/infra-proxy/osm-light-ui/${id8}/`
      }
      if (selectedService === 'kafka-ui') {
        if (topologyId && topologyInfra?.mode === 'isolated') {
          const id8 = topologyId.slice(0, 8)
          return `/infra-proxy/kafka-ui/${id8}/`
        }
        return `/infra-proxy/kafka-ui-shared/`
      }
      if (selectedService === 'flink') {
        // Shared mode: keep same-origin for iframe + https compatibility.
        // Isolated mode: per-topology Flink UI proxy (to be used when TOPOLOGY_INFRA_MODE=isolated adds Flink).
        if (topologyId && topologyInfra?.mode === 'isolated' && hasIsolatedInfraService('flink')) {
          const id8 = topologyId.slice(0, 8)
          return `/infra-proxy/flink/${id8}/`
        }
        return `/infra-proxy/flink-shared/`
      }
      if (selectedService === 'spark') {
        if (topologyId && topologyInfra?.mode === 'isolated' && hasIsolatedInfraService('spark')) {
          const id8 = topologyId.slice(0, 8)
          return `/infra-proxy/spark/${id8}/`
        }
        return `/infra-proxy/spark-shared/`
      }
      if (selectedService === 'hdfs') {
        if (topologyId && topologyInfra?.mode === 'isolated' && hasIsolatedInfraService('hdfs')) {
          const id8 = topologyId.slice(0, 8)
          return `/infra-proxy/hdfs/${id8}/`
        }
        return `/infra-proxy/hdfs-shared/`
      }
      if (selectedService === 'hive') {
        return `/infra-proxy/hive-shared/`
      }
      if (selectedService === 'pgadmin') {
        return `/infra-proxy/pgadmin-shared/`
      }
      if (selectedService === 'mongo-express') {
        return `/infra-proxy/mongo-express-shared/`
      }
      if (selectedService === 'hue') {
        return `/infra-proxy/hue-shared/`
      }
      if ((selectedService === 'portainer' || selectedService === 'portainer-http') && topologyId) {
        const id8 = topologyId.slice(0, 8)
        return `/infra-proxy/portainer/${id8}/`
      }
      const service = infraServices.find((s) => s.name === selectedService) || infraServices[0]
      if (service?.name?.startsWith('controller:') && topologyId) {
        const id8 = topologyId.slice(0, 8)
        const ctrlId = service.controllerId || service.name.split(':', 2)[1]
        const ctrlPort = service.controllerUiPort || 8080
        const base = `/infra-proxy/controllers/${id8}/${ctrlId}/${ctrlPort}/`
        const suffix = String(service.path || '/').replace(/^\//, '')
        return `${base}${suffix}`
      }
      const port = service?.port || 8080
      const scheme = String((service as any)?.scheme || 'http')
      const hostname = window.location.hostname
      const suffix = String(service?.path || '/')
      return `${scheme}://${hostname}:${port}${suffix.startsWith('/') ? suffix : `/${suffix}`}`
    } else {
      // For emulation nodes, use the node's IP if available, otherwise use hostname
      const isDockerized =
        String((selectedDevice as any)?.properties?.dockerized || '').toLowerCase() === 'true' ||
        Boolean((selectedDevice as any)?.properties?.docker_image)
      const dockerPorts = isDockerized ? parseDockerPorts((selectedDevice as any)?.properties?.docker_ports) : {}
      const desiredPort = Number(selectedPort)
      const mappedHostPort = dockerPorts[`${desiredPort}/tcp`]
      const matchesHostPort = Object.values(dockerPorts).some((p) => p === desiredPort)

      if (isDockerized && (Number.isFinite(mappedHostPort) || matchesHostPort)) {
        const port = Number.isFinite(mappedHostPort) ? mappedHostPort : desiredPort
        return `http://${window.location.hostname}:${port}`
      }

      const hostname = pickDeviceIp(selectedDevice) || window.location.hostname
      return `http://${hostname}:${selectedPort}`
    }
  }

  const handleNodeChange = (nodeName: string) => {
    setSelectedNode(nodeName)
    setIframeError(false)
    setIsLoading(true)
  }

  const handlePortChange = (port: string) => {
    setSelectedPort(port)
    setIframeError(false)
    setIsLoading(true)
  }

  const handleViewModeChange = (mode: 'emulation' | 'infrastructure') => {
    setViewMode(mode)
    setIframeError(false)
    setIsLoading(true)
  }

  const handleServiceChange = (service: string) => {
    setSelectedService(service)
    setIframeError(false)
    setIsLoading(true)
  }

  const handleIframeLoad = () => {
    setIsLoading(false)
    setIframeError(false)
    if (loadTimeout) {
      clearTimeout(loadTimeout)
      setLoadTimeout(null)
    }
  }

  const handleIframeError = () => {
    setIframeError(true)
    setIsLoading(false)
  }

  const handleRetry = () => {
    setIframeError(false)
    setIsLoading(true)
  }

  const selectedInfraService = useMemo(() => {
    return infraServices.find((s) => s.name === selectedService) || infraServices[0]
  }, [infraServices, selectedService])

  const serviceBlocksEmbedding = useMemo(() => false, [])

  const openInfraInNewTab = () => {
    try {
      window.open(getNodeUrl(), '_blank', 'noopener,noreferrer')
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (!topologyId) {
      setTopologyInfra(null)
      setTopologyInfraError(null)
      setTopologyInfraCreds(null)
      return
    }

    let cancelled = false
    const load = async () => {
      if (infraLoadInFlight.current) return
      infraLoadInFlight.current = true
      try {
        const res = await infrastructureAPI.topologyInfraStatus(topologyId)
        if (cancelled) return
        const mode = (res.data as any)?.mode
        const infra = (res.data as any)?.infra
        if (mode === 'isolated' && !infra) {
          await infrastructureAPI.ensureTopologyInfra(topologyId)
          const again = await infrastructureAPI.topologyInfraStatus(topologyId)
          if (cancelled) return
          setTopologyInfra(again.data as any)
        } else {
          setTopologyInfra(res.data as any)
        }
        setTopologyInfraError(null)

        // Fetch credentials for UI display (best-effort).
        try {
          const creds = await infrastructureAPI.topologyInfraCredentials(topologyId)
          if (!cancelled) setTopologyInfraCreds(creds.data as any)
        } catch {
          if (!cancelled) setTopologyInfraCreds(null)
        }
      } catch (e: any) {
        if (cancelled) return
        setTopologyInfraError(e?.response?.data?.detail || e?.message || 'Failed to load topology infra')
      } finally {
        infraLoadInFlight.current = false
      }
    }

    load()
    const interval = window.setInterval(load, 5000)
    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [topologyId])

  const handleEnsureInfra = async () => {
    if (!topologyId) return
    setInfraActionError(null)
    const toastId = toast.loading('Starting / ensuring topology infrastructure…')
    try {
      await infrastructureAPI.ensureTopologyInfra(topologyId)
      const res = await infrastructureAPI.topologyInfraStatus(topologyId)
      setTopologyInfra(res.data as any)
      const creds = await infrastructureAPI.topologyInfraCredentials(topologyId)
      setTopologyInfraCreds(creds.data as any)
      toast.success('Topology infrastructure is ready', { id: toastId })
    } catch (e: any) {
      toast.error('Failed to ensure topology infrastructure', { id: toastId })
      setInfraActionError(e?.response?.data?.detail || e?.message || 'Failed to ensure topology infrastructure')
    }
  }

  const handleStopInfra = async () => {
    if (!topologyId) return
    setInfraActionError(null)
    const toastId = toast.loading('Stopping topology infrastructure (keeping data)…')
    try {
      await infrastructureAPI.stopTopologyInfra(topologyId, true)
      const res = await infrastructureAPI.topologyInfraStatus(topologyId)
      setTopologyInfra(res.data as any)
      toast.success('Topology infrastructure stopped (data preserved)', { id: toastId })
    } catch (e: any) {
      toast.error('Failed to stop topology infrastructure', { id: toastId })
      setInfraActionError(e?.response?.data?.detail || e?.message || 'Failed to stop topology infrastructure')
    }
  }

  const handlePurgeInfra = async () => {
    if (!topologyId) return
    const ok = window.confirm(
      'Delete isolated topology infrastructure data? This removes the topology’s Grafana/InfluxDB/Prometheus/etc volumes and cannot be undone.'
    )
    if (!ok) return
    setInfraActionError(null)
    const toastId = toast.loading('Deleting topology infrastructure data…')
    try {
      await infrastructureAPI.purgeTopologyInfra(topologyId)
      const res = await infrastructureAPI.topologyInfraStatus(topologyId)
      setTopologyInfra(res.data as any)
      setTopologyInfraCreds(null)
      toast.success('Topology infrastructure data deleted', { id: toastId })
    } catch (e: any) {
      toast.error('Failed to delete topology infrastructure data', { id: toastId })
      setInfraActionError(e?.response?.data?.detail || e?.message || 'Failed to purge topology infrastructure')
    }
  }

  const handleSyncLogins = async () => {
    if (!topologyId) return
    setInfraActionError(null)
    const toastId = toast.loading('Fixing topology service logins…')
    try {
      await infrastructureAPI.syncTopologyInfraLogins(topologyId)
      const res = await infrastructureAPI.topologyInfraStatus(topologyId)
      setTopologyInfra(res.data as any)
      const creds = await infrastructureAPI.topologyInfraCredentials(topologyId)
      setTopologyInfraCreds(creds.data as any)
      toast.success('Service logins updated', { id: toastId })
    } catch (e: any) {
      toast.error('Failed to sync service logins', { id: toastId })
      setInfraActionError(e?.response?.data?.detail || e?.message || 'Failed to sync service logins')
    }
  }

  const isOsmUiService = selectedService === 'osm-ng-ui' || selectedService === 'osm-light-ui'

  const handleRestartSelectedInfraService = async () => {
    if (!topologyId) return
    if (isOsmUiService) {
      toast.error('Restart OSM from Network Manager → MANO → OSM (ETSI)')
      return
    }
    setInfraActionError(null)
    const toastId = toast.loading('Restarting service…')
    try {
      if (selectedService.startsWith('controller:')) {
        const id = selectedService.split(':', 2)[1]
        await infrastructureAPI.restartTopologyInfra(topologyId, { controller_id: id })
      } else {
        await infrastructureAPI.restartTopologyInfra(topologyId, { service: selectedService })
      }
      const res = await infrastructureAPI.topologyInfraStatus(topologyId)
      setTopologyInfra(res.data as any)
      const creds = await infrastructureAPI.topologyInfraCredentials(topologyId)
      setTopologyInfraCreds(creds.data as any)
      toast.success('Service restarted', { id: toastId })
    } catch (e: any) {
      toast.error('Failed to restart service', { id: toastId })
      setInfraActionError(e?.response?.data?.detail || e?.message || 'Failed to restart service')
    }
  }

  useEffect(() => {
    if (viewMode !== 'infrastructure') return
    if (!infraServices.length) return
    if (infraServices.some((s) => s.name === selectedService)) return
    setSelectedService(infraServices[0].name)
  }, [infraServices, selectedService, viewMode])

  // Set up timeout to detect loading failures
  useEffect(() => {
    if (viewMode === 'infrastructure' || (viewMode === 'emulation' && isRunning && containerDevices.length > 0)) {
      setIsLoading(true)
      setIframeError(false)

      // Clear existing timeout
      if (loadTimeout) {
        clearTimeout(loadTimeout)
      }

      // Set new timeout - some infra UIs can take a while to boot on first load.
      const timeout = setTimeout(() => {
        setIframeError(true)
        setIsLoading(false)
      }, 15000)

      setLoadTimeout(timeout)

      return () => {
        if (timeout) {
          clearTimeout(timeout)
        }
      }
    }
  }, [getNodeUrl(), viewMode, isRunning, containerDevices.length])

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4" style={{ height: 'calc(100vh - 280px)' }}>
      {/* Left Sidebar - Controls */}
      <div className="lg:col-span-3 overflow-y-auto">
        <Card className="h-full">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ServerIcon className="w-5 h-5" />
              {t('container.selectContainer', 'Container UI')}
            </CardTitle>
            <Badge variant="primary" size="sm" className="mt-2">
              {viewMode === 'emulation' ? t('container.emulationNode', 'Emulation Node') : t('container.infrastructureService', 'Infrastructure')}
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
            {/* View Mode Toggle */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                {t('container.viewMode', 'View Mode')}
              </label>
              <div className="flex flex-col gap-2">
                <button
                  onClick={() => handleViewModeChange('emulation')}
                  className={`w-full px-4 py-3 rounded-xl font-medium transition-all text-left ${
                    viewMode === 'emulation'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                >
                  <CpuChipIcon className="w-5 h-5 inline mr-2" />
                  {t('container.emulationNodes', 'Emulation Nodes')}
                </button>
                <button
                  onClick={() => handleViewModeChange('infrastructure')}
                  className={`w-full px-4 py-3 rounded-xl font-medium transition-all text-left ${
                    viewMode === 'infrastructure'
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                >
                  <ServerIcon className="w-5 h-5 inline mr-2" />
                  {t('container.infrastructureServices', 'Infrastructure')}
                </button>
              </div>
            </div>

            {viewMode === 'emulation' ? (
              <>
                {!isRunning ? (
                  <div className="p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-xl">
                    <p className="text-sm text-yellow-800 dark:text-yellow-300">
                      {t('container.emulationNotRunning', 'Start the emulation to view node UIs')}
                    </p>
                  </div>
                ) : containerDevices.length === 0 ? (
                  <div className="p-4 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl">
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                      {t('container.noNodes', 'No container or host nodes found in the emulation')}
                    </p>
                  </div>
                ) : (
                  <>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          {t('container.selectNode', 'Select Node')}
                        </label>
                        <select
                          value={selectedNode}
                          onChange={(e) => handleNodeChange(e.target.value)}
                          className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        >
                          {containerDevices.map((device: Device) => (
                            <option key={device.name} value={device.name}>
                              {device.name} {device.ip ? `(${device.ip})` : ''}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                          {t('container.port', 'Port')}
                        </label>
                        <input
                          type="number"
                          value={selectedPort}
                          onChange={(e) => handlePortChange(e.target.value)}
                          placeholder="8080"
                          className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        />
                      </div>
                    </div>

                    {selectedDevice && (
                      <div className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl">
                        <CpuChipIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <div className="flex-1">
                          <p className="font-medium text-blue-900 dark:text-blue-300">
                            {selectedDevice.name} - Port {selectedPort}
                          </p>
                          <p className="text-xs mt-1 text-blue-700 dark:text-blue-400">
                            URL: {getNodeUrl()}
                          </p>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </>
            ) : (
              <>
                {topologyId && (
                  <div className="p-4 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl">
                    <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                      {t('container.topologyResources', 'Topology Resources')}
                    </div>
                    {topologyInfraError ? (
                      <div className="mt-1 text-xs text-red-600 dark:text-red-400 break-words">{topologyInfraError}</div>
                    ) : (
                      <div className="mt-1 text-xs text-gray-700 dark:text-gray-300">
                        Mode: <span className="font-mono">{topologyInfra?.mode || '—'}</span>
                      </div>
                    )}

                    {infraActionError && (
                      <div className="mt-2 text-xs text-red-600 dark:text-red-400 break-words">{infraActionError}</div>
                    )}

                    <div className="mt-3 flex flex-col gap-2">
                      <button
                        onClick={handleEnsureInfra}
                        className="w-full px-3 py-2 rounded-lg text-sm font-medium bg-blue-600 text-white hover:bg-blue-700 transition-colors"
                      >
                        {t('container.ensureInfra', 'Ensure / Start Infra')}
                      </button>
                      <button
                        onClick={handleStopInfra}
                        className="w-full px-3 py-2 rounded-lg text-sm font-medium bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                      >
                        {t('container.stopInfra', 'Stop Infra (keep data)')}
                      </button>
                      <button
                        onClick={handleSyncLogins}
                        className="w-full px-3 py-2 rounded-lg text-sm font-medium bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100 hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
                      >
                        {t('container.syncInfraLogins', 'Fix Logins')}
                      </button>
                      <button
                        onClick={handlePurgeInfra}
                        className="w-full px-3 py-2 rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
                      >
                        {t('container.deleteInfraData', 'Delete Infra Data')}
                      </button>
                    </div>

                    {topologyInfraCreds?.credentials?.grafana && (
                      <div className="mt-3 text-xs text-gray-700 dark:text-gray-300 space-y-1">
                        <div className="font-semibold text-gray-900 dark:text-gray-100">Grafana Login</div>
                        <div>
                          User: <span className="font-mono">{topologyInfraCreds.credentials.grafana.user || '—'}</span>
                        </div>
                        <div>
                          Pass: <span className="font-mono break-all">{topologyInfraCreds.credentials.grafana.password || '—'}</span>
                        </div>
                      </div>
                    )}

	                    {topologyInfraCreds?.credentials?.influxdb && (
	                      <div className="mt-3 text-xs text-gray-700 dark:text-gray-300 space-y-1">
	                        <div className="font-semibold text-gray-900 dark:text-gray-100">InfluxDB</div>
	                        <div>
	                          Org: <span className="font-mono">{topologyInfraCreds.credentials.influxdb.org || '—'}</span>
	                        </div>
	                        <div>
	                          Bucket: <span className="font-mono">{topologyInfraCreds.credentials.influxdb.bucket || '—'}</span>
	                        </div>
	                        <div>
	                          Token: <span className="font-mono break-all">{topologyInfraCreds.credentials.influxdb.token || '—'}</span>
	                        </div>
	                      </div>
	                    )}

	                    {topologyInfra?.controllers?.controllers && (
	                      <div className="mt-3 text-xs text-gray-700 dark:text-gray-300 space-y-2">
	                        <div className="font-semibold text-gray-900 dark:text-gray-100">
	                          Controllers
	                        </div>
	                        {Object.entries((topologyInfra as any).controllers.controllers as any).map(([controllerId, cfg]: any) => {
	                          const c = cfg as any
	                          const name = String(c?.node_name || controllerId)
	                          const type = String(c?.controller_type || 'controller')
	                          const containerName = String(c?.container_name || '—')
	                          const ofPort = c?.openflow_port != null ? String(c.openflow_port) : '—'
	                          const ui = c?.ui
	                          const uiHostPort = Number(ui?.host_port)
	                          const uiContainerPort = Number(ui?.container_port)
	                          const id8 = topologyId ? topologyId.slice(0, 8) : ''
	                          const uiPath = String(ui?.path || '/')
	                          const uiUrl =
	                            topologyId && Number.isFinite(uiHostPort) && uiHostPort > 0 && Number.isFinite(uiContainerPort) && uiContainerPort > 0
	                              ? `/infra-proxy/controllers/${id8}/${controllerId}/${uiContainerPort}/${String(uiPath || '/').replace(/^\//, '')}`
	                              : null

	                          return (
	                            <div key={controllerId} className="p-2 rounded-lg bg-white/60 dark:bg-gray-900/30 border border-gray-200 dark:border-gray-700">
	                              <div className="font-semibold text-gray-900 dark:text-gray-100">
	                                {name} <span className="font-normal text-gray-600 dark:text-gray-400">({type})</span>
	                              </div>
	                              <div>
	                                Container: <span className="font-mono break-all">{containerName}</span>
	                              </div>
	                              <div>
	                                OpenFlow: <span className="font-mono">tcp:{containerName}:{ofPort}</span>
	                              </div>
	                              <div>
	                                UI:{' '}
	                                {uiUrl ? (
	                                  <span className="font-mono break-all">{uiUrl}</span>
	                                ) : (
	                                  <span className="text-gray-500 dark:text-gray-400">Not available (OSKen has no built-in web UI)</span>
	                                )}
	                              </div>
	                            </div>
	                          )
	                        })}
	                      </div>
	                    )}
	                  </div>
	                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    {t('container.selectService', 'Select Service')}
                  </label>
                  <select
                    value={selectedService}
                    onChange={(e) => handleServiceChange(e.target.value)}
                    className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {infraServices.map((service) => (
                      <option key={service.name} value={service.name}>
                        {service.displayName} (Port {service.port})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="flex items-start gap-2 text-sm text-gray-600 dark:text-gray-400 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-xl">
                  <ServerIcon className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <div className="flex-1">
                    <p className="font-medium text-blue-900 dark:text-blue-300">
                      {infraServices.find((s) => s.name === selectedService)?.displayName}
                    </p>
                    <p className="text-xs mt-1 text-blue-700 dark:text-blue-400">
                      {infraServices.find((s) => s.name === selectedService)?.description}
                    </p>
                    <p className="text-xs mt-1 text-blue-700 dark:text-blue-400">
                      URL: {getNodeUrl()}
                    </p>

                    {selectedService === 'grafana' && (
                      <div className="mt-2 text-xs text-blue-800 dark:text-blue-300 space-y-1">
                        <div className="font-semibold">Login</div>
                        <div>
                          User:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.grafana?.user || '—'}
                          </span>
                        </div>
                        <div>
                          Pass:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.grafana?.password || '—'}
                          </span>
                        </div>
                      </div>
                    )}

                    {selectedService === 'influxdb' && (
                      <div className="mt-2 text-xs text-blue-800 dark:text-blue-300 space-y-1">
                        <div className="font-semibold">Login / Token</div>
                        <div>
                          User:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.influxdb?.user || '—'}
                          </span>
                        </div>
                        <div>
                          Pass:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.influxdb?.password || '—'}
                          </span>
                        </div>
                        <div>
                          Org:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.influxdb?.org || '—'}
                          </span>
                        </div>
                        <div>
                          Bucket:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.influxdb?.bucket || '—'}
                          </span>
                        </div>
                        <div>
                          Token:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.influxdb?.token || '—'}
                          </span>
                        </div>
                      </div>
                    )}

                    {selectedService === 'pgadmin' && (
                      <div className="mt-2 text-xs text-blue-800 dark:text-blue-300 space-y-1">
                        <div className="font-semibold">Login</div>
                        <div>
                          Email:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.pgadmin?.email || '—'}
                          </span>
                        </div>
                        <div>
                          Pass:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.pgadmin?.password || '—'}
                          </span>
                        </div>
                      </div>
                    )}

                    {selectedService === 'mongo-express' && (
                      <div className="mt-2 text-xs text-blue-800 dark:text-blue-300 space-y-1">
                        <div className="font-semibold">Login</div>
                        <div>
                          User:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.mongo_express?.user || '—'}
                          </span>
                        </div>
                        <div>
                          Pass:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.mongo_express?.password || '—'}
                          </span>
                        </div>
                      </div>
                    )}

                    {selectedService === 'hue' && (
                      <div className="mt-2 text-xs text-blue-800 dark:text-blue-300 space-y-1">
                        <div className="font-semibold">Login</div>
                        <div>
                          User:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.hue?.user || '—'}
                          </span>
                        </div>
                        <div>
                          Pass:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.hue?.password || '—'}
                          </span>
                        </div>
                      </div>
                    )}

                    {selectedService === 'rabbitmq' && (
                      <div className="mt-2 text-xs text-blue-800 dark:text-blue-300 space-y-1">
                        <div className="font-semibold">Login</div>
                        <div>
                          User:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.rabbitmq?.user || '—'}
                          </span>
                        </div>
                        <div>
                          Pass:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.rabbitmq?.password || '—'}
                          </span>
                        </div>
                        <div>
                          VHost:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.rabbitmq?.vhost || '—'}
                          </span>
                        </div>
                      </div>
                    )}

                    {(selectedService === 'portainer' || selectedService === 'portainer-http') && (
                      <div className="mt-2 text-xs text-blue-800 dark:text-blue-300 space-y-1">
                        <div className="font-semibold">Login</div>
                        <div className="text-[11px] text-blue-700/90 dark:text-blue-300/90">
                          Note: Portainer shows Docker containers (infra, the emulation container, and dockerized hosts like <span className="font-mono">mn.*</span>).
                          Mininet devices (switches/routers/hosts) are network namespaces inside the emulation container and won’t appear here unless they are dockerized.
                        </div>
                        {topologyInfraCreds?.credentials?.portainer_view?.user && (
                          <div className="mt-2">
                            <div className="font-semibold">Topology-only user</div>
                            <div>
                              User:{' '}
                              <span className="font-mono break-all">
                                {topologyInfraCreds?.credentials?.portainer_view?.user || '—'}
                              </span>
                            </div>
                            <div>
                              Pass:{' '}
                              <span className="font-mono break-all">
                                {topologyInfraCreds?.credentials?.portainer_view?.password || '—'}
                              </span>
                            </div>
                          </div>
                        )}
                        <div>
                          User:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.portainer?.user || '—'}
                          </span>
                        </div>
                        <div>
                          Pass:{' '}
                          <span className="font-mono break-all">
                            {topologyInfraCreds?.credentials?.portainer?.password || '—'}
                          </span>
                        </div>
                      </div>
                    )}

                    {selectedService.startsWith('controller:') && (
                      <div className="mt-2 text-xs text-blue-800 dark:text-blue-300 space-y-1">
                        <div className="font-semibold">Login</div>
                        {(() => {
                          const id = selectedService.split(':', 2)[1]
                          const ctrl = topologyInfraCreds?.credentials?.controllers?.[id]
                          const creds = ctrl?.credentials
                          if (!creds) {
                            return <div>No credentials (or not required)</div>
                          }
                          return (
                            <div className="space-y-1">
                              {creds.user && (
                                <div>
                                  User: <span className="font-mono break-all">{creds.user}</span>
                                </div>
                              )}
                              {creds.password && (
                                <div>
                                  Pass: <span className="font-mono break-all">{creds.password}</span>
                                </div>
                              )}
                            </div>
                          )
                        })()}
                      </div>
                    )}

                    <button
                      onClick={openInfraInNewTab}
                      className="mt-2 inline-flex px-3 py-1.5 rounded-lg text-xs font-medium bg-white/70 dark:bg-gray-900/30 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 hover:bg-white dark:hover:bg-gray-900/50 transition-colors"
                    >
                      {t('container.openNewTab', 'Open in new tab')}
                    </button>
                    <button
                      onClick={handleRestartSelectedInfraService}
                      className="ml-2 mt-2 inline-flex px-3 py-1.5 rounded-lg text-xs font-medium bg-white/70 dark:bg-gray-900/30 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-300 hover:bg-white dark:hover:bg-gray-900/50 transition-colors"
                    >
                      {t('container.restartService', 'Restart')}
                    </button>
                  </div>
                </div>
              </>
            )}

            {iframeError && (
              <div className="flex items-start gap-2 p-3 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-xl">
                <ExclamationTriangleIcon className="w-5 h-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
                <div className="text-sm">
                  <p className="font-medium text-yellow-800 dark:text-yellow-300">
                    {t('container.loadError', 'Unable to load UI')}
                  </p>
                  <p className="text-yellow-700 dark:text-yellow-400 mt-1">
                    {t(
                      'container.loadErrorDesc',
                      'The service may not be running or the port may be incorrect. Please verify the node/service is accessible.'
                    )}
                  </p>
                </div>
              </div>
            )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Right Side - Iframe Display */}
      <div className="lg:col-span-9 h-full">
        {(viewMode === 'infrastructure' || (viewMode === 'emulation' && isRunning && containerDevices.length > 0)) ? (
          <Card padding="none" className="overflow-hidden h-full flex flex-col">
            <CardContent className="p-0 flex-1">
              <div className="relative w-full h-full bg-gray-50 dark:bg-gray-900">
                {serviceBlocksEmbedding ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center p-8 max-w-lg">
                      <ExclamationTriangleIcon className="w-16 h-16 mx-auto mb-4 text-yellow-500 dark:text-yellow-400" />
                      <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                        {t('container.embeddingBlocked', 'Embedding blocked by this service')}
                      </h3>
                      <p className="text-gray-600 dark:text-gray-400 mb-4">
                        {t(
                          'container.embeddingBlockedDesc',
                          'This service sets security headers (X-Frame-Options) that prevent it from loading inside an iframe.'
                        )}
                      </p>
                      <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3 mb-4">
                        <code className="text-sm text-blue-600 dark:text-blue-400 break-all">{getNodeUrl()}</code>
                      </div>
                      <button
                        onClick={openInfraInNewTab}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                      >
                        {t('container.openNewTab', 'Open in new tab')}
                      </button>
                    </div>
                  </div>
                ) : iframeError ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center p-8 max-w-md">
                      <ExclamationTriangleIcon className="w-16 h-16 mx-auto mb-4 text-yellow-500 dark:text-yellow-400" />
                      <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                        {t('container.connectionFailed', 'Connection Failed')}
                      </h3>
                      <p className="text-gray-600 dark:text-gray-400 mb-4">
                        {t('container.cannotConnect', 'Cannot establish a connection to')}
                      </p>
                      <div className="bg-gray-100 dark:bg-gray-800 rounded-lg p-3 mb-4">
                        <code className="text-sm text-blue-600 dark:text-blue-400 break-all">
                          {getNodeUrl()}
                        </code>
                      </div>
                      <div className="text-left bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
                        <p className="text-sm font-medium text-blue-900 dark:text-blue-300 mb-2">
                          {t('container.possibleReasons', 'Possible reasons:')}
                        </p>
                        <ul className="text-sm text-blue-800 dark:text-blue-400 space-y-1 list-disc list-inside">
                          <li>{t('container.serviceNotRunning', 'Service is not running on this port')}</li>
                          <li>{t('container.portIncorrect', 'Port number is incorrect')}</li>
                          <li>{t('container.firewallBlocking', 'Firewall or network is blocking the connection')}</li>
                          <li>{t('container.nodeNotReachable', 'Node is not reachable from your browser')}</li>
                        </ul>
                      </div>
                      <button
                        onClick={handleRetry}
                        className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                      >
                        {t('common.retry', 'Retry')}
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {isLoading && (
                      <div className="absolute inset-0 flex items-center justify-center bg-white dark:bg-gray-900 z-10">
                        <div className="text-center">
                          <div className="w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                          <p className="text-gray-600 dark:text-gray-400">
                            {t('common.loading', 'Loading...')}
                          </p>
                        </div>
                      </div>
                    )}
                    <iframe
                      key={getNodeUrl()}
                      src={getNodeUrl()}
                      title={viewMode === 'emulation' ? `${selectedNode} - Port ${selectedPort}` : selectedInfraService?.displayName}
                      className="w-full h-full border-0"
                      sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals"
                      onLoad={handleIframeLoad}
                      onError={handleIframeError}
                      style={{
                        backgroundColor: 'white',
                      }}
                    />
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="h-full flex items-center justify-center">
            <CardContent>
              <div className="text-center py-20">
                <ServerIcon className="w-16 h-16 mx-auto mb-4 text-gray-400 dark:text-gray-600" />
                <p className="text-lg font-medium text-gray-600 dark:text-gray-400 mb-2">
                  {!isRunning
                    ? t('container.emulationNotRunning', 'Start the emulation to view node UIs')
                    : t('container.selectNodeToView', 'Select a node and port to view its UI')
                  }
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
