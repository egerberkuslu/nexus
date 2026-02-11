import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'
const LONG_REQUEST_TIMEOUT_MS = 10 * 60 * 1000

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if needed
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor
apiClient.interceptors.response.use(
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

// API endpoints for all microservices
export const api = {
  // Topology Service (8001)
  topology: {
    getAll: () => apiClient.get('topologies'),
    getById: (id: string) => apiClient.get(`topologies/${id}`),
    create: (data: any) => apiClient.post('topologies', data),
    update: (id: string, data: any) => apiClient.put(`topologies/${id}`, data),
    delete: (id: string) => apiClient.delete(`topologies/${id}`),
    getNodes: (id: string) => apiClient.get(`topologies/${id}/nodes`),
    getLinks: (id: string) => apiClient.get(`topologies/${id}/links`),
  },

  // Orchestrator Service (8002)
  orchestrator: {
    start: (topologyId: string) =>
      apiClient.post(`orchestrator/emulations/${topologyId}/start`, null, {
        timeout: LONG_REQUEST_TIMEOUT_MS,
      }),
    stop: (topologyId: string) =>
      apiClient.post(`orchestrator/emulations/${topologyId}/stop`, null, {
        timeout: LONG_REQUEST_TIMEOUT_MS,
      }),
    pause: (topologyId: string) => apiClient.post(`orchestrator/emulations/${topologyId}/pause`),
    resume: (topologyId: string) => apiClient.post(`orchestrator/emulations/${topologyId}/resume`),
    status: (topologyId: string) => apiClient.get(`orchestrator/emulations/${topologyId}/status`),
  },

  // Protocol Manager Service (8003)
  protocols: {
    configure: (deviceId: string, data: any) => apiClient.post(`protocols/${deviceId}/configure`, data),
    enable: (deviceId: string, protocol: string) => apiClient.post(`protocols/${deviceId}/${protocol}/enable`),
    disable: (deviceId: string, protocol: string) => apiClient.post(`protocols/${deviceId}/${protocol}/disable`),
    getStatus: (deviceId: string) => apiClient.get(`protocols/${deviceId}/status`),
    getRoutes: (deviceId: string) => apiClient.get(`protocols/${deviceId}/routes`),
  },

  // Device Manager Service (8004)
  devices: {
    getAll: (topologyId: string) => apiClient.get(`devices?topology_id=${topologyId}`),
    getById: (id: string) => apiClient.get(`devices/${id}`),
    create: (data: any) => apiClient.post('devices', data),
    update: (id: string, data: any) => apiClient.put(`devices/${id}`, data),
    delete: (id: string) => apiClient.delete(`devices/${id}`),
    execute: (id: string, command: string) => apiClient.post(`devices/${id}/execute`, { command }),
  },

  // Controller Manager Service (8005)
  controllers: {
    getAll: () => apiClient.get('controllers'),
    getById: (id: string) => apiClient.get(`controllers/${id}`),
    create: (data: any) => apiClient.post('controllers', data),
    update: (id: string, data: any) => apiClient.put(`controllers/${id}`, data),
    delete: (id: string) => apiClient.delete(`controllers/${id}`),
    getSwitches: (id: string) => apiClient.get(`controllers/${id}/switches`),
    getFlows: (id: string) => apiClient.get(`controllers/${id}/flows`),
  },

  // Snapshot Service (8006)
  snapshots: {
    getAll: (topologyId: string) => apiClient.get(`snapshots?topology_id=${topologyId}`),
    getById: (id: string) => apiClient.get(`snapshots/${id}`),
    create: (topologyId: string, data: any) => apiClient.post(`snapshots`, { topology_id: topologyId, ...data }),
    restore: (id: string) => apiClient.post(`snapshots/${id}/restore`),
    delete: (id: string) => apiClient.delete(`snapshots/${id}`),
  },

  // WebShell Service (8007)
  webshell: {
    connect: (deviceId: string) => `/ws/shell/${deviceId}`, // WebSocket URL
  },

  // Export/Import Service (8008)
  exportImport: {
    export: (topologyId: string) => apiClient.get(`export/${topologyId}`, { responseType: 'blob' }),
    import: (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      return apiClient.post('import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
  },

  // Topology Generator Service (8009)
  generator: {
    generate: (type: string, params: any) => apiClient.post(`generator/${type}`, params),
    templates: () => apiClient.get('generator/templates'),
  },

  // P4 Manager Service (8010)
  p4: {
    compile: (code: string) => apiClient.post('p4/compile', { code }),
    deploy: (deviceId: string, program: any) => apiClient.post(`p4/${deviceId}/deploy`, program),
    getPrograms: () => apiClient.get('p4/programs'),
  },

  // Monitoring Service (8011)
  monitoring: {
    getMetrics: (topologyId: string) => apiClient.get(`monitoring/${topologyId}/metrics`),
    getDeviceMetrics: (deviceId: string) => apiClient.get(`monitoring/devices/${deviceId}/metrics`),
    getAlerts: () => apiClient.get('monitoring/alerts'),
  },

  // Projects
  projects: {
    getAll: () => apiClient.get('projects'),
    getById: (id: string) => apiClient.get(`projects/${id}`),
    create: (data: any) => apiClient.post('projects', data),
    update: (id: string, data: any) => apiClient.put(`projects/${id}`, data),
    delete: (id: string) => apiClient.delete(`projects/${id}`),
  },
}
