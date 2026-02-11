import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'
import type { Topology, Project, Controller, DeviceMetrics, Snapshot } from '../types/topology'

interface TopologyState {
  // Projects
  projects: Project[]
  currentProject: Project | null
  setProjects: (projects: Project[]) => void
  setCurrentProject: (project: Project | null) => void

  // Topologies
  topologies: Topology[]
  currentTopology: Topology | null
  setTopologies: (topologies: Topology[]) => void
  setCurrentTopology: (topology: Topology | null) => void

  // Controllers
  controllers: Controller[]
  setControllers: (controllers: Controller[]) => void

  // Emulation
  emulationStatus: 'stopped' | 'starting' | 'running' | 'paused' | 'error'
  setEmulationStatus: (status: 'stopped' | 'starting' | 'running' | 'paused' | 'error') => void

  // Metrics
  metrics: Record<string, DeviceMetrics>
  setMetrics: (metrics: Record<string, DeviceMetrics>) => void
  updateDeviceMetrics: (device: string, metrics: DeviceMetrics) => void

  // Snapshots
  snapshots: Snapshot[]
  setSnapshots: (snapshots: Snapshot[]) => void

  // UI State
  selectedNode: string | null
  setSelectedNode: (nodeId: string | null) => void
  isLoading: boolean
  setIsLoading: (loading: boolean) => void
  error: string | null
  setError: (error: string | null) => void
}

export const useStore = create<TopologyState>()(
  devtools(
    persist(
      (set) => ({
        // Projects
        projects: [],
        currentProject: null,
        setProjects: (projects) => set({ projects }),
        setCurrentProject: (project) => set({ currentProject: project }),

        // Topologies
        topologies: [],
        currentTopology: null,
        setTopologies: (topologies) => set({ topologies }),
        setCurrentTopology: (topology) => set({ currentTopology: topology }),

        // Controllers
        controllers: [],
        setControllers: (controllers) => set({ controllers }),

        // Emulation
        emulationStatus: 'stopped',
        setEmulationStatus: (status) => set({ emulationStatus: status }),

        // Metrics
        metrics: {},
        setMetrics: (metrics) => set({ metrics }),
        updateDeviceMetrics: (device, deviceMetrics) =>
          set((state) => ({
            metrics: {
              ...state.metrics,
              [device]: deviceMetrics
            }
          })),

        // Snapshots
        snapshots: [],
        setSnapshots: (snapshots) => set({ snapshots }),

        // UI State
        selectedNode: null,
        setSelectedNode: (nodeId) => set({ selectedNode: nodeId }),
        isLoading: false,
        setIsLoading: (loading) => set({ isLoading: loading }),
        error: null,
        setError: (error) => set({ error }),
      }),
      {
        name: 'caduceus-flux-storage',
        partialize: (state) => ({
          currentProject: state.currentProject,
          currentTopology: state.currentTopology
        }),
      }
    )
  )
)
