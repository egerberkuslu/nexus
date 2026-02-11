import axios from 'axios'
import type {
  Project,
  Topology,
  Node,
  Link,
  Controller,
  ProtocolConfig,
  EmulationStatus,
  EmulationControlResponse,
  DeviceMetrics,
  Snapshot,
  SnapshotSchedule,
  ScheduleCreate,
  ScheduleUpdate,
} from '@/types/topology'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
api.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

// Projects API
export const projectsAPI = {
  list: () => api.get<Project[]>('/projects'),
  get: (id: string) => api.get<Project>(`/projects/${id}`),
  create: (data: Partial<Project>) => api.post<Project>('/projects', data),
  update: (id: string, data: Partial<Project>) =>
    api.put<Project>(`/projects/${id}`, data),
  delete: (id: string) => api.delete(`/projects/${id}`),
}

// Topologies API
export const topologiesAPI = {
  list: (projectId?: string) =>
    api.get<Topology[]>('/topologies', { params: { project_id: projectId } }),
  get: (id: string) => api.get<Topology>(`/topologies/${id}`),
  create: (data: Partial<Topology>) => api.post<Topology>('/topologies', data),
  update: (id: string, data: Partial<Topology>) =>
    api.put<Topology>(`/topologies/${id}`, data),
  delete: (id: string) => api.delete(`/topologies/${id}`),
  importDefinition: (projectId: string, topologyDefinition: any, targetTopologyId?: string) => {
    if (targetTopologyId) {
      return api.put<Topology>(`/topologies/${targetTopologyId}/import`, topologyDefinition)
    }
    return api.post<Topology>(`/topologies/import`, topologyDefinition, { params: { project_id: projectId } })
  },
  importAndStart: (payload: { project_id: string; topology: any; options?: any }) =>
    api.post(`/topologies/import-and-start`, payload),
  export: (id: string, format: 'mininet' | 'mininet-wifi' | 'containernet' | 'graphml' | 'json' | 'yaml') =>
    api.post(`/export`, { topology_id: id, format }),
  import: (file: File, format: 'json' | 'graphml') => {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('format', format)
    return api.post('/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

export type P4ProgramDraft = {
  draft_id: string
  name: string
  source_code: string
  target: string
  architecture: string
  compiled_program_id?: string | null
  created_at: string
  updated_at: string
}

export const topologyP4API = {
  listDrafts: (topologyId: string) =>
    api.get<P4ProgramDraft[]>(`/topologies/${topologyId}/p4/programs`),
  getDraft: (topologyId: string, draftId: string) =>
    api.get<P4ProgramDraft>(`/topologies/${topologyId}/p4/programs/${draftId}`),
  saveDraft: (
    topologyId: string,
    payload: {
      draft_id?: string
      name: string
      source_code: string
      target?: string
      architecture?: string
      compiled_program_id?: string | null
    }
  ) => api.post<P4ProgramDraft>(`/topologies/${topologyId}/p4/programs`, payload),
  deleteDraft: (topologyId: string, draftId: string) =>
    api.delete(`/topologies/${topologyId}/p4/programs/${draftId}`),
}

// Nodes API
export const nodesAPI = {
  add: (topologyId: string, node: Partial<Node>) =>
    api.post(`/topologies/${topologyId}/nodes`, node),
  update: (topologyId: string, nodeId: string, data: Partial<Node>) =>
    api.put(`/topologies/${topologyId}/nodes/${nodeId}`, data),
  delete: (topologyId: string, nodeId: string) =>
    api.delete(`/topologies/${topologyId}/nodes/${nodeId}`),
}

// Links API
export const linksAPI = {
  add: (topologyId: string, link: Partial<Link>) =>
    api.post(`/topologies/${topologyId}/links`, link),
  update: (topologyId: string, linkId: string, data: Partial<Link>) =>
    api.put(`/topologies/${topologyId}/links/${linkId}`, data),
  delete: (topologyId: string, linkId: string) =>
    api.delete(`/topologies/${topologyId}/links/${linkId}`),
}

// Emulation API
export const emulationAPI = {
  start: (topologyId: string, options?: any) =>
    api.post<EmulationControlResponse>('/emulation/start', { topology_id: topologyId, options }),
  stop: (
    emulationId: string,
    options?: { cleanup?: boolean; stop_infra?: boolean; preserve_infra_data?: boolean }
  ) =>
    api.post<EmulationControlResponse>(`/emulation/stop/${emulationId}`, {
      cleanup: options?.cleanup ?? true,
      stop_infra: options?.stop_infra ?? true,
      preserve_infra_data: options?.preserve_infra_data ?? true,
    }),
  pause: (emulationId: string) =>
    api.post<EmulationControlResponse>(`/emulation/pause/${emulationId}`),
  resume: (emulationId: string) =>
    api.post<EmulationControlResponse>(`/emulation/resume/${emulationId}`),
  status: (emulationId: string) =>
    api.get<EmulationStatus>(`/emulation/status/${emulationId}`),
  active: () =>
    api.get('/emulation/active'),
  sync: (topologyId: string) =>
    api.post(`/emulation/sync/${topologyId}`),
  shellInfo: (emulationId: string) =>
    api.get(`/emulation/shell/${emulationId}`),
  getContainers: (topologyId?: string) =>
    api.get('/emulation/containers', { params: { topology_id: topologyId } }),
  execute: (payload: { device: string; command: string; topology_id?: string; emulation_id?: string }) =>
    api.post('/emulation/execute', payload),
  applyNetworkConfig: (payload: { topology_id?: string; emulation_id?: string; config: any; dry_run?: boolean }) =>
    api.post('/emulation/network-config/apply', payload),
}

export const testsAPI = {
  run: (payload: { topology_id: string; suite: string; params?: any }) =>
    api.post('/tests/run', payload),
  status: (runId: string) =>
    api.get(`/tests/${runId}`),
  results: (runId: string, topologyId: string, window_minutes = 240) =>
    api.get(`/tests/${runId}/results`, { params: { topology_id: topologyId, window_minutes } }),
  stop: (runId: string) =>
    api.post(`/tests/${runId}/stop`, { cancel: true }),
}

export const metricsCollectorAPI = {
  health: () => api.get('/metrics-collector/health'),
  start: () => api.post('/metrics-collector/api/start-collection', []),
  stop: () => api.post('/metrics-collector/api/stop-collection'),
}

export const algorithmsAPI = {
  startRun: (payload: {
    topology_id: string
    transport?: 'udp' | 'tcp'
    listen_port?: number
    params?: any
    manifest_json?: string
    source_code?: string
    bundle?: File
  }) => {
    const form = new FormData()
    form.append('topology_id', payload.topology_id)
    form.append('transport', payload.transport || 'udp')
    form.append('listen_port', String(payload.listen_port ?? 50000))
    if (payload.params !== undefined) form.append('params_json', JSON.stringify(payload.params))
    if (payload.manifest_json !== undefined) form.append('manifest_json', payload.manifest_json)
    if (payload.source_code !== undefined) form.append('source_code', payload.source_code)
    if (payload.bundle) form.append('bundle', payload.bundle)
    return api.post('/algorithms/runs', form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  getRun: (runId: string) => api.get(`/algorithms/runs/${runId}`),
  stopRun: (runId: string) => api.post(`/algorithms/runs/${runId}/stop`),
  events: (runId: string, params?: { algo_id?: number; tail?: number }) =>
    api.get(`/algorithms/runs/${runId}/events`, { params }),
  overlay: (topologyId: string, params?: { run_id?: string }) => api.get(`/algorithms/topologies/${topologyId}/overlay`, { params }),
  validate: (runId: string) => api.get(`/algorithms/runs/${runId}/validate`),
}

export const infrastructureAPI = {
  status: (params?: { topology_id?: string; include_stopped?: boolean }) =>
    api.get('/infrastructure/status', { params }),
  ensure: (services?: string[]) =>
    api.post('/infrastructure/ensure', { services }),
  jupyter: () => api.get('/infrastructure/jupyter'),
  topologies: () =>
    api.get('/infrastructure/topologies'),
  ensureTopologyInfra: (topologyId: string) =>
    api.post(`/infrastructure/topologies/${topologyId}/infra/ensure`),
  topologyInfraStatus: (topologyId: string) =>
    api.get(`/infrastructure/topologies/${topologyId}/infra/status`),
  topologyInfraCredentials: (topologyId: string) =>
    api.get(`/infrastructure/topologies/${topologyId}/infra/credentials`),
  syncTopologyInfraLogins: (topologyId: string) =>
    api.post(`/infrastructure/topologies/${topologyId}/infra/sync-logins`),
  restartTopologyInfra: (topologyId: string, payload?: { service?: string; controller_id?: string }) =>
    api.post(`/infrastructure/topologies/${topologyId}/infra/restart`, payload || {}),
  stopTopologyInfra: (topologyId: string, preserveData = true) =>
    api.post(`/infrastructure/topologies/${topologyId}/infra/stop`, { preserve_data: preserveData }),
  purgeTopologyInfra: (topologyId: string) =>
    api.post(`/infrastructure/topologies/${topologyId}/infra/purge`, { confirm: true }),
  execTopologyController: (
    topologyId: string,
    controllerId: string,
    payload: { command: string; timeout_seconds?: number }
  ) => api.post(`/infrastructure/topologies/${topologyId}/controllers/${controllerId}/exec`, payload),
  startTopologyController: (topologyId: string, controllerId: string, payload?: { timeout_seconds?: number }) =>
    api.post(`/infrastructure/topologies/${topologyId}/controllers/${controllerId}/start`, payload || {}),
  stopTopologyController: (topologyId: string, controllerId: string, payload?: { timeout_seconds?: number }) =>
    api.post(`/infrastructure/topologies/${topologyId}/controllers/${controllerId}/stop`, payload || {}),
  restartTopologyController: (topologyId: string, controllerId: string, payload?: { timeout_seconds?: number }) =>
    api.post(`/infrastructure/topologies/${topologyId}/controllers/${controllerId}/restart`, payload || {}),
  ensureTopologyOsm: (topologyId: string) =>
    api.post(`/infrastructure/topologies/${topologyId}/osm/ensure`),
  topologyOsmStatus: (topologyId: string) =>
    api.get(`/infrastructure/topologies/${topologyId}/osm/status`),
  stopTopologyOsm: (topologyId: string, preserveData = true) =>
    api.post(`/infrastructure/topologies/${topologyId}/osm/stop`, { preserve_data: preserveData }),
  purgeTopologyOsm: (topologyId: string, removeVolumes = true) =>
    api.post(`/infrastructure/topologies/${topologyId}/osm/purge`, { confirm: true, remove_volumes: removeVolumes }),
}

// Devices API
export const devicesAPI = {
  list: () => api.get('/devices'),
  add: (device: Partial<Node>) => api.post('/devices', device),
  update: (device: string, data: Partial<Node>) => api.put(`/devices/${device}`, data),
  remove: (name: string) => api.delete(`/devices/${name}`),
  execute: (device: string, command: string) =>
    api.post(`/devices/${device}/execute`, { command }),
  interfaces: (device: string) => api.get(`/devices/${device}/interfaces`),
  stats: (device: string) => api.get<DeviceMetrics>(`/devices/${device}/stats`),
}

export const manoAPI = {
  info: () => api.get('/mano/info'),
  osmReconcile: (payload: { topology_id: string; ensure_osm_stack?: boolean; sync_after?: boolean; resources?: string[]; mark_deleted?: boolean }) =>
    api.post('/mano/osm/reconcile', payload),
  osmMirrorSync: (payload: { topology_id: string; resources?: string[]; mark_deleted?: boolean }) => api.post('/mano/osm/sync', payload),
  osmMirrorStats: (params?: { topology_id?: string; include_deleted?: boolean }) => api.get('/mano/osm/mirror/stats', { params }),
  osmMirrorResources: (params?: {
    topology_id?: string
    resource_type?: string
    backend?: string
    include_deleted?: boolean
    limit?: number
    offset?: number
  }) => api.get('/mano/osm/mirror/resources', { params }),
  listNsds: () => api.get('/mano/catalog/nsds'),
  upsertNsd: (payload: { id?: string; name: string; version?: string; provider?: string; descriptor?: any }) =>
    api.post('/mano/catalog/nsds', payload),
  listVnfds: () => api.get('/mano/catalog/vnfds'),
  upsertVnfd: (payload: { id?: string; name: string; version?: string; provider?: string; descriptor?: any }) =>
    api.post('/mano/catalog/vnfds', payload),
  listNsInstances: (params?: { topology_id?: string }) => api.get('/mano/ns-instances', { params }),
  createNsInstance: (payload: {
    name: string
    nsd_id?: string | null
    topology_id?: string | null
    options?: any
    dry_run?: boolean
    backend?: 'local' | 'osm'
  }) => api.post('/mano/ns-instances', payload),
  terminateNsInstance: (nsId: string, payload?: { reason?: string }) =>
    api.post(`/mano/ns-instances/${nsId}/terminate`, payload || {}),
  listOperations: (params?: { ns_instance_id?: string; kind?: string; status?: string; limit?: number; offset?: number }) =>
    api.get('/mano/operations', { params }),
  listVnfs: (params?: { ns_instance_id?: string }) => api.get('/mano/vnfm/vnf-instances', { params }),
  createVnf: (payload: {
    ns_instance_id: string
    vnfd_id?: string | null
    name: string
    device_type?: string
    device_name?: string | null
    properties?: any
    dry_run?: boolean
  }) => api.post('/mano/vnfm/vnf-instances', payload),
  deleteVnf: (vnfId: string, params?: { force?: boolean }) =>
    api.delete(`/mano/vnfm/vnf-instances/${vnfId}`, { params }),
  execVnf: (vnfId: string, payload: { command: string }) => api.post(`/mano/vnfm/vnf-instances/${vnfId}/exec`, payload),
  vimInventory: (params?: { ns_instance_id?: string }) => api.get('/mano/vim/inventory', { params }),
}

export const configAPI = {
  template: (params?: { topology_id?: string }) => api.get('/config/template', { params }),
  validate: (payload: any) => api.post('/config/validate', payload),
  apply: (payload: any) => api.post('/config/apply', payload),
}

export const osmAPI = {
  _base: (topologyId?: string) => `/osm${topologyId ? `/${encodeURIComponent(topologyId)}` : ''}`,
  info: (topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/info`),
  listProjects: (topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/projects`),
  listVimAccounts: (topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/vim-accounts`),
  listWimAccounts: (topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/wim-accounts`),
  listNsdPackages: (topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/nsd-packages`),
  getNsdPackage: (id: string, topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/nsd-packages/${id}`),
  deleteNsdPackage: (id: string, topologyId?: string) => api.delete(`${osmAPI._base(topologyId)}/nsd-packages/${id}`),
  uploadNsdPackage: (file: File, topologyId?: string) => {
    const form = new FormData()
    form.append('package', file)
    return api.post(`${osmAPI._base(topologyId)}/nsd-packages/upload`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  listVnfdPackages: (topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/vnfd-packages`),
  getVnfdPackage: (id: string, topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/vnfd-packages/${id}`),
  deleteVnfdPackage: (id: string, topologyId?: string) => api.delete(`${osmAPI._base(topologyId)}/vnfd-packages/${id}`),
  uploadVnfdPackage: (file: File, topologyId?: string) => {
    const form = new FormData()
    form.append('package', file)
    return api.post(`${osmAPI._base(topologyId)}/vnfd-packages/upload`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  listNsInstances: (topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/ns-instances`),
  getNsInstance: (id: string, topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/ns-instances/${id}`),
  createNsInstance: (payload: { nsd_id: string; name: string; description?: string; vim_account_id?: string }, topologyId?: string) =>
    api.post(`${osmAPI._base(topologyId)}/ns-instances`, payload),
  instantiateNsInstance: (id: string, payload: any, topologyId?: string) =>
    api.post(`${osmAPI._base(topologyId)}/ns-instances/${id}/instantiate`, payload || {}),
  terminateNsInstance: (id: string, payload?: any, topologyId?: string) =>
    api.post(`${osmAPI._base(topologyId)}/ns-instances/${id}/terminate`, payload || {}),
  deleteNsInstance: (id: string, topologyId?: string) => api.delete(`${osmAPI._base(topologyId)}/ns-instances/${id}`),
  listNsLcmOps: (topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/ns-lcm-op-occs`),
  getNsLcmOp: (id: string, topologyId?: string) => api.get(`${osmAPI._base(topologyId)}/ns-lcm-op-occs/${id}`),
  proxy: (method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE', path: string, payload?: any, params?: any, topologyId?: string) =>
    api.request({
      method,
      url: `${osmAPI._base(topologyId)}/proxy/${path.replace(/^\/+/, '')}`,
      data: payload,
      params,
    }),
}

// Protocol Manager API
export const protocolsAPI = {
  list: () => api.get('/protocols'),
  configure: (device: string, protocol: string, config: any) =>
    api.post('/protocols/configure', { device, protocol, config }),
  enable: (device: string, protocol: string) =>
    api.post('/protocols/enable', { device, protocol }),
  disable: (device: string, protocol: string) =>
    api.post('/protocols/disable', { device, protocol }),
  hotSwap: (device: string, fromProtocol: string, toProtocol: string) =>
    api.post('/protocols/hot-swap', { device, from_protocol: fromProtocol, to_protocol: toProtocol }),
  status: (device: string, protocol: string) =>
    api.get(`/protocols/status/${device}/${protocol}`),
}

// Snapshot API (Enhanced with CRIU support)
export const snapshotsAPI = {
  list: (topologyId?: string, snapshotType?: string, status?: string) =>
    api.get<{ items: Snapshot[], total: number, page: number, per_page: number, has_next: boolean, has_prev: boolean }>(`/snapshots`, {
      params: {
        topology_id: topologyId,
        snapshot_type: snapshotType,
        status: status
      }
    }),
  create: (data: {
    name: string;
    topology_id?: string;
    emulation_id?: string;
    snapshot_type?: 'topology_only' | 'docker_commit' | 'criu_live' | 'hybrid_full';
    description?: string;
    compression?: boolean;
    target_containers?: string[];
    include_routing_tables?: boolean;
    include_flow_tables?: boolean;
    include_arp_tables?: boolean;
    // Legacy fields for backward compatibility
    devices?: string[];
  }) =>
    api.post<Snapshot>('/snapshots', data),
  get: (id: string) =>
    api.get<Snapshot>(`/snapshots/${id}`),
  restore: (id: string, devices?: string[], restoreNetworkState?: boolean) =>
    api.post(`/snapshots/${id}/restore`, {
      snapshot_id: id,
      devices,
      restore_network_state: restoreNetworkState
    }),
  delete: (id: string) =>
    api.delete(`/snapshots/${id}`),
  rename: (id: string, name: string) =>
    api.patch(`/snapshots/${id}`, { name }),
  download: (id: string) =>
    api.get(`/snapshots/${id}/download`, { responseType: 'blob' }),
  import: (file: File, name?: string, description?: string) => {
    const formData = new FormData()
    formData.append('file', file)
    if (name) formData.append('name', name)
    if (description) formData.append('description', description)
    return api.post('/snapshots/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
  compare: (id1: string, id2: string) =>
    api.post(`/snapshots/compare`, { snapshot1_id: id1, snapshot2_id: id2 }),
  types: () =>
    api.get('/snapshots/types'),
  stats: () =>
    api.get('/snapshots/stats'),
  progress: (id: string) =>
    new EventSource(`/api/snapshots/${id}/progress`),

  // Schedule endpoints
  schedules: {
    list: (topologyId?: string) =>
      api.get<{ items: SnapshotSchedule[] }>('/snapshots/schedules', { params: { topology_id: topologyId } }),
    get: (id: string) =>
      api.get<SnapshotSchedule>(`/snapshots/schedules/${id}`),
    create: (data: ScheduleCreate) =>
      api.post<SnapshotSchedule>('/snapshots/schedules', data),
    update: (id: string, data: ScheduleUpdate) =>
      api.put<SnapshotSchedule>(`/snapshots/schedules/${id}`, data),
    delete: (id: string) =>
      api.delete(`/snapshots/schedules/${id}`),
    trigger: (id: string) =>
      api.post(`/snapshots/schedules/${id}/trigger`),
  },
}

// Monitoring API
export const monitoringAPI = {
  deviceMetrics: (device: string, topologyId?: string) =>
    api.get<DeviceMetrics>(`/monitoring/devices/${device}`, { params: topologyId ? { topology_id: topologyId } : undefined }),
  deviceInterfaces: (device: string, topologyId: string, iface?: string) =>
    api.get(`/monitoring/devices/${device}/interfaces`, { params: { topology_id: topologyId, interface: iface } }),
  deviceRoutes: (device: string, topologyId: string) =>
    api.get(`/monitoring/devices/${device}/routes`, { params: { topology_id: topologyId } }),
  deviceArp: (device: string, topologyId: string) =>
    api.get(`/monitoring/devices/${device}/arp`, { params: { topology_id: topologyId } }),
  switchFlows: (switchName: string, topologyId: string) =>
    api.get(`/monitoring/switches/${switchName}/flows`, { params: { topology_id: topologyId } }),
  topologyMetrics: (topologyId: string) =>
    api.get(`/monitoring/topology/${topologyId}/metrics`),
  algorithmRuns: (topologyId: string, params?: { window_minutes?: number; algorithm?: string }) =>
    api.get(`/monitoring/algorithms/topology/${topologyId}/runs`, { params }),
  algorithmRunNodes: (topologyId: string, runId: string, params?: { window_minutes?: number }) =>
    api.get(`/monitoring/algorithms/topology/${topologyId}/runs/${runId}/nodes`, { params }),
  algorithmRunSummary: (topologyId: string, runId: string, params?: { window_minutes?: number }) =>
    api.get(`/monitoring/algorithms/topology/${topologyId}/runs/${runId}/summary`, { params }),
  subscribe: (device: string) =>
    api.post(`/monitoring/subscribe`, { device }),
}

export const networkConfigsAPI = {
  template: (topologyId: string) => api.get(`/network-configs/${topologyId}/template`),
  listVersions: (topologyId: string) => api.get(`/network-configs/${topologyId}/versions`),
  getLatest: (topologyId: string) => api.get(`/network-configs/${topologyId}`),
  exportLatest: (topologyId: string) => api.get(`/network-configs/${topologyId}/export`),
  create: (topologyId: string, payload: { name?: string; description?: string; config: any }) =>
    api.post(`/network-configs/${topologyId}`, payload),
}

export type P4Program = {
  program_id: string
  name: string
  target: string
  architecture: string
  status: string
  compiled_at?: string
  source_file?: string | null
  json_file?: string | null
  p4info_file?: string | null
  error?: string | null
}

export const p4API = {
  listPrograms: () => api.get<P4Program[]>('/p4/programs'),
  getProgram: (programId: string) => api.get<P4Program>(`/p4/programs/${programId}`),
  compile: (payload: { name: string; source_code: string; target?: string; architecture?: string }) =>
    api.post<P4Program>('/p4/programs/compile', payload),
  upload: (file: File, payload?: { name?: string; target?: string; architecture?: string }) => {
    const formData = new FormData()
    formData.append('file', file)
    if (payload?.name) formData.append('name', payload.name)
    if (payload?.target) formData.append('target', payload.target)
    if (payload?.architecture) formData.append('architecture', payload.architecture)
    return api.post<P4Program>('/p4/programs/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

// Controllers API
export const controllersAPI = {
  list: () => api.get<Controller[]>('/controllers'),
  add: (controller: Partial<Controller>) =>
    api.post<Controller>('/controllers', controller),
  remove: (id: string) => api.delete(`/controllers/${id}`),
  configure: (id: string, config: any) =>
    api.post(`/controllers/${id}/configure`, config),
  status: (id: string) => api.get(`/controllers/${id}/status`),
  logs: (id: string, lines?: number) =>
    api.get(`/controllers/${id}/logs`, { params: { lines } }),
}

// Topology Generator API
export const generatorAPI = {
  generate: (algorithm: string, params: any) =>
    api.post('/generate', { algorithm, parameters: params }),
}

export type AIProvider = 'openai' | 'anthropic' | 'gemini' | 'ollama'

export type MLTask = 'anomaly_detection' | 'attack_detection' | 'routing_policy' | 'mano_policy'
export type MLFramework = 'builtin' | 'onnx' | 'torchscript'

export type MLModel = {
  id: string
  task: MLTask | string
  name: string
  algorithm?: string | null
  framework: MLFramework | string
  version?: string | null
  description?: string | null
  artifact_filename?: string | null
  artifact_sha256?: string | null
  artifact_size_bytes?: number | null
  input_schema?: Record<string, any>
  output_schema?: Record<string, any>
  meta?: Record<string, any>
  created_at?: string | null
  updated_at?: string | null
}

export const aiAPI = {
  providers: () => api.get<{ providers: { id: AIProvider; label: string }[] }>('/ai/providers'),
  models: (provider: AIProvider) => api.get<{ provider: AIProvider; models: string[] }>('/ai/models', { params: { provider } }),
  settings: () =>
    api.get<{ providers: { provider: AIProvider; configured: boolean; default_model: string | null }[] }>('/ai/settings'),
  setDefaultModel: (data: { provider: AIProvider; default_model: string }) =>
    api.put('/ai/settings/default-model', data),
  setCredential: (data: { provider: Exclude<AIProvider, 'ollama'>; api_key: string }) =>
    api.put('/ai/credentials', data),
  clearCredential: (provider: Exclude<AIProvider, 'ollama'>) =>
    api.delete('/ai/credentials', { params: { provider } }),
  chat: (data: {
    provider: AIProvider
    model: string
    prompt?: string
    messages?: { role: 'system' | 'user' | 'assistant'; content: string }[]
    api_key?: string // optional override; prefer stored credentials
    temperature?: number
    max_tokens?: number
  }) => api.post<{ provider: AIProvider; model: string; content: string; raw: any }>('/ai/chat', data),
  mcp: {
    generate: (data: { provider: AIProvider; model: string; prompt: string; scope_topology_id?: string; api_key?: string }) =>
      api.post<{ request: { method: string; path: string; query?: any; headers?: any; body?: any }; toon: string; raw: any }>(
        '/ai/mcp/generate',
        data
      ),
    capabilities: (scope_topology_id?: string) =>
      api.get<{
        scope_topology_id?: string | null
        allowed_prefixes: string[]
        notes: string[]
        items: { method: string; path: string; description: string; scope: 'global' | 'scoped' | 'both' }[]
        examples: string[]
      }>('/ai/mcp/capabilities', { params: { scope_topology_id } }),
    agent: (data: {
      provider: AIProvider
      model: string
      messages: { role: 'user' | 'assistant'; content: string }[]
      scope_topology_id?: string
      max_steps?: number
    }) =>
      api.post<{
        assistant: string
        tool_calls: { toon: string; result: { status_code: number; headers: any; body: any } }[]
        raw_steps: any[]
      }>('/ai/mcp/agent', data),
    execute: (request: { method: string; path: string; query?: any; headers?: any; body?: any }) =>
      api.post<{ status_code: number; headers: any; body: any }>('/ai/mcp/execute', { request }),
    executeToon: (toon: string, scope_topology_id?: string) =>
      api.post<{ status_code: number; headers: any; body: any }>('/ai/mcp/execute', { toon, scope_topology_id }),
  },
  agents: {
    list: () =>
      api.get<{
        agents: {
          id: string
          name: string
          description: string
          scope: 'global' | 'topology' | 'both'
          allowed_prefixes: string[]
          allowed_methods: string[]
        }[]
      }>('/ai/agents'),
    threads: (agent_id: string, topology_id?: string) =>
      api.get<{ threads: { id: string; agent_id: string; topology_id?: string | null; title?: string | null; updated_at?: string | null; created_at?: string | null }[] }>(
        '/ai/threads',
        { params: { agent_id, topology_id } }
      ),
    deleteThreads: (agent_id: string, topology_id?: string) => api.delete('/ai/threads', { params: { agent_id, topology_id } }),
    createThread: (data: { agent_id: string; topology_id?: string; title?: string }) =>
      api.post<{ id: string; agent_id: string; topology_id?: string | null; title?: string | null; updated_at?: string | null; created_at?: string | null }>(
        '/ai/threads',
        data
      ),
    thread: (thread_id: string) =>
      api.get<{
        thread: { id: string; agent_id: string; topology_id?: string | null; title?: string | null; updated_at?: string | null; created_at?: string | null }
        messages: { id: string; role: 'user' | 'assistant' | 'system'; content_md: string; created_at: string; meta: any; tool_calls: any[] }[]
      }>(`/ai/threads/${thread_id}`),
    deleteThread: (thread_id: string) => api.delete(`/ai/threads/${thread_id}`),
    chat: (data: {
      message: string
      topology_id?: string
      agent_id?: string
      thread_id?: string
      provider?: AIProvider
      model?: string
      max_steps?: number
    }) =>
      api.post<{
        thread_id: string
        thread_agent_id: string
        agent_id: string
        assistant: string
        tool_calls: { toon: string; result: { status_code: number; headers: any; body: any; meta?: any } }[]
        raw_steps: any[]
        memory_hits: any[]
        route?: any
      }>('/ai/agents/chat', data),
    exportThreadReport: (
      thread_id: string,
      data: { format: 'md' | 'pdf'; title?: string; provider?: AIProvider; model?: string }
    ) =>
      api.post(`/ai/reports/thread/${thread_id}`, data, { responseType: 'blob' }),
    executeToolCall: (tool_call_id: string) =>
      api.post<{ status_code: number; headers: any; body: any; meta?: any }>(`/ai/tool-calls/${tool_call_id}/execute`, {}),
  },
  network: {
    diagnose: (data: { topology_id: string; provider?: AIProvider; model?: string }) =>
      api.post<{ topology_id: string; provider: AIProvider; model: string; content: string; heuristics: any }>(
        '/ai/network/diagnose',
        data
      ),
    analyzeTests: (data: { topology_id: string; run_id: string; provider?: AIProvider; model?: string }) =>
      api.post<{ topology_id: string; run_id: string; provider: AIProvider; model: string; content: string; highlights: any }>(
        '/ai/network/tests/analyze',
        data
      ),
    analyzeDiagnostics: (data: {
      topology_id: string
      window_minutes?: number
      start_ms?: number
      end_ms?: number
      every_seconds?: number
      device?: string
      source?: string
      emulation_id?: string
      fields?: string[]
      prompt?: string
      provider?: AIProvider
      model?: string
    }) =>
      api.post<{ topology_id: string; provider: AIProvider; model: string; content: string; summary: any }>(
        '/ai/network/diagnostics/analyze',
        data
      ),
  },
  ml: {
    listModels: (params?: { task?: string; framework?: string }) =>
      api.get<{ models: MLModel[] }>('/ai/ml/models', { params }),
    assignments: () =>
      api.get<{
        tasks: string[]
        assignments: { task: string; model_id: string }[]
        models_by_id: Record<string, MLModel>
      }>('/ai/ml/assignments'),
    setAssignment: (data: { task: string; model_id: string }) => api.put('/ai/ml/assignments', data),
    uploadModel: (file: File, data: { task: string; name: string; framework: string; algorithm?: string; version?: string; description?: string }) => {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('task', data.task)
      formData.append('name', data.name)
      formData.append('framework', data.framework)
      if (data.algorithm) formData.append('algorithm', data.algorithm)
      if (data.version) formData.append('version', data.version)
      if (data.description) formData.append('description', data.description)
      return api.post<MLModel>('/ai/ml/models/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } })
    },
    downloadModel: (modelId: string) => api.get(`/ai/ml/models/${modelId}/download`, { responseType: 'blob' }),
    deleteModel: (modelId: string) => api.delete(`/ai/ml/models/${modelId}`),
  },
}

export default api

export const diagnosticsAPI = {
  influxFeatures: (topology_id: string) =>
    api.get<{
      topology_id: string
      bucket: string
      measurement: string
      fields: string[]
      devices: string[]
      sources: string[]
      emulation_ids: string[]
    }>(`/diagnostics/${topology_id}/influx/features`),
  influxQuery: (
    topology_id: string,
    data: {
      window_minutes?: number
      start_ms?: number
      end_ms?: number
      every_seconds?: number
      device?: string
      source?: string
      emulation_id?: string
      fields?: string[]
    }
  ) =>
    api.post<{
      topology_id: string
      bucket: string
      measurement: string
      every_seconds: number
      start_ms: number | null
      end_ms: number | null
      device: string | null
      source: string | null
      emulation_id: string | null
      fields: string[]
      points: any[]
    }>(`/diagnostics/${topology_id}/influx/query`, data),
}
