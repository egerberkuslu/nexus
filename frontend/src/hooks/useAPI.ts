import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/apiClient'
import { useStore } from '../store/useStore'

// Topology Hooks
export const useTopologies = () => {
  const setTopologies = useStore((state) => state.setTopologies)
  return useQuery({
    queryKey: ['topologies'],
    queryFn: async () => {
      const response = await api.topology.getAll()
      setTopologies(response.data)
      return response.data
    },
  })
}

export const useTopology = (id: string) => {
  const setCurrentTopology = useStore((state) => state.setCurrentTopology)
  return useQuery({
    queryKey: ['topology', id],
    queryFn: async () => {
      const response = await api.topology.getById(id)
      setCurrentTopology(response.data)
      return response.data
    },
    enabled: !!id,
  })
}

export const useCreateTopology = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.topology.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['topologies'] })
    },
  })
}

export const useUpdateTopology = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => api.topology.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['topologies'] })
    },
  })
}

// Orchestrator Hooks
export const useStartEmulation = () => {
  const setEmulationStatus = useStore((state) => state.setEmulationStatus)
  return useMutation({
    mutationFn: (topologyId: string) => api.orchestrator.start(topologyId),
    onSuccess: () => {
      setEmulationStatus('starting')
    },
  })
}

export const useStopEmulation = () => {
  const setEmulationStatus = useStore((state) => state.setEmulationStatus)
  return useMutation({
    mutationFn: (topologyId: string) => api.orchestrator.stop(topologyId),
    onSuccess: () => {
      setEmulationStatus('stopped')
    },
  })
}

export const useEmulationStatus = (topologyId: string) => {
  const setEmulationStatus = useStore((state) => state.setEmulationStatus)
  return useQuery({
    queryKey: ['emulation-status', topologyId],
    queryFn: async () => {
      const response = await api.orchestrator.status(topologyId)
      setEmulationStatus(response.data.status)
      return response.data
    },
    enabled: !!topologyId,
    refetchInterval: 5000, // Poll every 5 seconds
  })
}

// Device Hooks
export const useDevices = (topologyId: string) => {
  return useQuery({
    queryKey: ['devices', topologyId],
    queryFn: async () => {
      const response = await api.devices.getAll(topologyId)
      return response.data
    },
    enabled: !!topologyId,
  })
}

export const useExecuteCommand = () => {
  return useMutation({
    mutationFn: ({ deviceId, command }: { deviceId: string; command: string }) =>
      api.devices.execute(deviceId, command),
  })
}

// Controller Hooks
export const useControllers = () => {
  const setControllers = useStore((state) => state.setControllers)
  return useQuery({
    queryKey: ['controllers'],
    queryFn: async () => {
      const response = await api.controllers.getAll()
      setControllers(response.data)
      return response.data
    },
  })
}

export const useCreateController = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.controllers.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['controllers'] })
    },
  })
}

// Protocol Hooks
export const useConfigureProtocol = () => {
  return useMutation({
    mutationFn: ({ deviceId, data }: { deviceId: string; data: any }) =>
      api.protocols.configure(deviceId, data),
  })
}

export const useProtocolStatus = (deviceId: string) => {
  return useQuery({
    queryKey: ['protocol-status', deviceId],
    queryFn: async () => {
      const response = await api.protocols.getStatus(deviceId)
      return response.data
    },
    enabled: !!deviceId,
  })
}

// Snapshot Hooks
export const useSnapshots = (topologyId: string) => {
  const setSnapshots = useStore((state) => state.setSnapshots)
  return useQuery({
    queryKey: ['snapshots', topologyId],
    queryFn: async () => {
      const response = await api.snapshots.getAll(topologyId)
      setSnapshots(response.data)
      return response.data
    },
    enabled: !!topologyId,
  })
}

export const useCreateSnapshot = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ topologyId, data }: { topologyId: string; data: any }) =>
      api.snapshots.create(topologyId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['snapshots'] })
    },
  })
}

export const useRestoreSnapshot = () => {
  return useMutation({
    mutationFn: (snapshotId: string) => api.snapshots.restore(snapshotId),
  })
}

// Monitoring Hooks
export const useDeviceMetrics = (deviceId: string) => {
  const updateDeviceMetrics = useStore((state) => state.updateDeviceMetrics)
  return useQuery({
    queryKey: ['device-metrics', deviceId],
    queryFn: async () => {
      const response = await api.monitoring.getDeviceMetrics(deviceId)
      updateDeviceMetrics(deviceId, response.data)
      return response.data
    },
    enabled: !!deviceId,
    refetchInterval: 10000, // Poll every 10 seconds
  })
}

export const useTopologyMetrics = (topologyId: string) => {
  return useQuery({
    queryKey: ['topology-metrics', topologyId],
    queryFn: async () => {
      const response = await api.monitoring.getMetrics(topologyId)
      return response.data
    },
    enabled: !!topologyId,
    refetchInterval: 10000,
  })
}

// P4 Hooks
export const useCompileP4 = () => {
  return useMutation({
    mutationFn: (code: string) => api.p4.compile(code),
  })
}

export const useDeployP4 = () => {
  return useMutation({
    mutationFn: ({ deviceId, program }: { deviceId: string; program: any }) =>
      api.p4.deploy(deviceId, program),
  })
}

// Project Hooks
export const useProjects = () => {
  const setProjects = useStore((state) => state.setProjects)
  return useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await api.projects.getAll()
      setProjects(response.data)
      return response.data
    },
  })
}

export const useCreateProject = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.projects.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

// Topology Generator Hooks
export const useGenerateTopology = () => {
  return useMutation({
    mutationFn: ({ type, params }: { type: string; params: any }) =>
      api.generator.generate(type, params),
  })
}

export const useTemplates = () => {
  return useQuery({
    queryKey: ['templates'],
    queryFn: async () => {
      const response = await api.generator.templates()
      return response.data
    },
  })
}
