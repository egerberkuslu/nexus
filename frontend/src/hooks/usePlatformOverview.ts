import { useQuery } from '@tanstack/react-query'
import api, { controllersAPI, emulationAPI, projectsAPI, snapshotsAPI, topologiesAPI } from '@/services/api'

type ProjectLike = {
  id: string
  name: string
  description?: string
  created_at?: string
  updated_at?: string
}

type NodeLike = {
  device_type?: string
}

type TopologyLike = {
  id: string
  project_id?: string
  name?: string
  emulation_status?: string
  is_active?: boolean
  nodes?: NodeLike[]
  links?: unknown[]
  controllers?: unknown[]
}

type EmulationLike = {
  topology_id?: string
  status?: string
  container_id?: string | null
}

type ServiceLike = {
  name?: string
  status?: string
}

type ControllerLike = {
  id?: string
}

type SnapshotLike = {
  id?: string
}

type ProjectSummary = {
  id: string
  name: string
  description: string
  topologyCount: number
  nodeCount: number
  linkCount: number
  runningTopologies: number
  updatedAt: string
}

export type PlatformOverview = {
  projects: ProjectLike[]
  topologies: TopologyLike[]
  emulations: EmulationLike[]
  services: ServiceLike[]
  snapshots: SnapshotLike[]
  projectSummaries: ProjectSummary[]
  latestProject: ProjectSummary | null
  totals: {
    projects: number
    topologies: number
    nodes: number
    links: number
    controllers: number
    runningEmulations: number
    activeTopologies: number
    services: number
    healthyServices: number
    snapshots: number
    emulationsWithContainer: number
    deviceTypes: number
  }
  deviceTypeCounts: Record<string, number>
}

function asArray<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[]
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>
    if (Array.isArray(record.items)) return record.items as T[]
    if (Array.isArray(record.data)) return record.data as T[]
  }
  return []
}

function asDateValue(value?: string): number {
  if (!value) return 0
  const parsed = new Date(value).getTime()
  return Number.isFinite(parsed) ? parsed : 0
}

export function usePlatformOverview() {
  return useQuery<PlatformOverview>({
    queryKey: ['platform-overview'],
    queryFn: async () => {
      const [projectsResult, topologiesResult, activeResult, servicesResult, snapshotsResult, controllersResult] =
        await Promise.allSettled([
          projectsAPI.list(),
          topologiesAPI.list(),
          emulationAPI.active(),
          api.get('/services'),
          snapshotsAPI.list(),
          controllersAPI.list(),
        ])

      const projects =
        projectsResult.status === 'fulfilled' ? asArray<ProjectLike>(projectsResult.value.data) : []
      const topologies =
        topologiesResult.status === 'fulfilled' ? asArray<TopologyLike>(topologiesResult.value.data) : []
      const emulations =
        activeResult.status === 'fulfilled'
          ? asArray<EmulationLike>((activeResult.value.data as { emulations?: EmulationLike[] })?.emulations)
          : []
      const services =
        servicesResult.status === 'fulfilled'
          ? asArray<ServiceLike>((servicesResult.value.data as { services?: ServiceLike[] })?.services)
          : []
      const snapshots =
        snapshotsResult.status === 'fulfilled'
          ? asArray<SnapshotLike>((snapshotsResult.value.data as { items?: SnapshotLike[] })?.items)
          : []
      const externalControllers =
        controllersResult.status === 'fulfilled' ? asArray<ControllerLike>(controllersResult.value.data) : []

      const topologyByProjectId = new Map<string, TopologyLike[]>()
      for (const topology of topologies) {
        const projectId = String(topology?.project_id || '')
        if (!projectId) continue
        const list = topologyByProjectId.get(projectId) || []
        list.push(topology)
        topologyByProjectId.set(projectId, list)
      }

      const deviceTypeCounts: Record<string, number> = {}
      let totalNodes = 0
      let totalLinks = 0
      let totalControllers = 0
      let controllerNodeCount = 0
      let activeTopologies = 0

      for (const topology of topologies) {
        const nodes = asArray<NodeLike>(topology?.nodes)
        const links = asArray(topology?.links)
        const controllers = asArray(topology?.controllers)
        totalNodes += nodes.length
        totalLinks += links.length
        totalControllers += controllers.length

        const status = String(topology?.emulation_status || '').toLowerCase()
        if (topology?.is_active || status === 'running') {
          activeTopologies += 1
        }

        for (const node of nodes) {
          const type = String(node?.device_type || 'unknown').toLowerCase()
          deviceTypeCounts[type] = (deviceTypeCounts[type] || 0) + 1
          if (type === 'controller') {
            controllerNodeCount += 1
          }
        }
      }

      const projectSummaries: ProjectSummary[] = projects
        .map((project) => {
          const list = topologyByProjectId.get(project.id) || []
          const nodeCount = list.reduce((sum, topology) => sum + asArray<NodeLike>(topology.nodes).length, 0)
          const linkCount = list.reduce((sum, topology) => sum + asArray(topology.links).length, 0)
          const runningTopologies = list.filter(
            (topology) => String(topology.emulation_status || '').toLowerCase() === 'running' || topology.is_active
          ).length

          return {
            id: project.id,
            name: project.name || 'Unnamed Project',
            description: project.description || 'No description',
            topologyCount: list.length,
            nodeCount,
            linkCount,
            runningTopologies,
            updatedAt: String(project.updated_at || project.created_at || ''),
          }
        })
        .sort((a, b) => asDateValue(b.updatedAt) - asDateValue(a.updatedAt))

      const latestProject = projectSummaries[0] || null
      const runningEmulations = emulations.filter(
        (emulation) => String(emulation?.status || '').toLowerCase() === 'running'
      ).length
      const healthyServices = services.filter(
        (service) => String(service?.status || '').toLowerCase() === 'healthy'
      ).length
      const emulationsWithContainer = emulations.filter((emulation) => !!emulation?.container_id).length
      const deviceTypes = Object.keys(deviceTypeCounts).filter((type) => type !== 'unknown').length
      const controllers = Math.max(totalControllers + controllerNodeCount, externalControllers.length)

      return {
        projects,
        topologies,
        emulations,
        services,
        snapshots,
        projectSummaries,
        latestProject,
        totals: {
          projects: projects.length,
          topologies: topologies.length,
          nodes: totalNodes,
          links: totalLinks,
          controllers,
          runningEmulations,
          activeTopologies,
          services: services.length,
          healthyServices,
          snapshots: snapshots.length,
          emulationsWithContainer,
          deviceTypes,
        },
        deviceTypeCounts,
      }
    },
    refetchInterval: 15000,
    staleTime: 5000,
  })
}
