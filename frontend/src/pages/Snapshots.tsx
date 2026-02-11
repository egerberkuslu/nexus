import { useEffect, useState } from 'react'
import CreateSnapshotModal from '@/components/snapshots/CreateSnapshotModal'
import SnapshotDetailsModal from '@/components/snapshots/SnapshotDetailsModal'
import RestoreSnapshotModal from '@/components/snapshots/RestoreSnapshotModal'
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { snapshotsAPI, emulationAPI } from '@services/api'
import {
  PlusIcon,
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  TrashIcon,
  ArrowPathIcon,
  ChartBarIcon,
  FunnelIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline'
import {
  CheckCircleIcon,
} from '@heroicons/react/24/solid'
import { ModernButton } from '@/components/ModernButton'
import { ModernCard } from '@/components/ModernCard'
import { StatusBadge } from '@/components/StatusBadge'
import TopologyPicker from '@/components/topology/TopologyPicker'

type SnapshotType = 'topology_only' | 'docker_commit' | 'criu_live' | 'hybrid_full' | 'all'
type SnapshotStatus = 'pending' | 'capturing' | 'captured' | 'failed' | 'all'

export default function Snapshots() {
  const { t } = useTranslation()
  const { topologyId } = useParams()
  const queryClient = useQueryClient()
  const hasTopologyId = Boolean(topologyId)

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [selectedSnapshot, setSelectedSnapshot] = useState<any>(null)
  const [showDetailsModal, setShowDetailsModal] = useState(false)
  const [showRestoreModal, setShowRestoreModal] = useState(false)
  const [filterType, setFilterType] = useState<SnapshotType>('all')
  const [filterStatus, setFilterStatus] = useState<SnapshotStatus>('all')
  const [importFile, setImportFile] = useState<File | null>(null)

  // Get emulation info
  const { data: activeEmulations } = useQuery({
    queryKey: ['active-emulations'],
    queryFn: async () => {
      if (!topologyId) return { emulations: [] }
      try {
        const response = await emulationAPI.active()
        return response.data
      } catch {
        toast.error('Failed to load active emulations', { id: 'active-emulations-load' })
        return { emulations: [] }
      }
    },
    refetchInterval: 5000,
    enabled: hasTopologyId,
  })

  const currentEmulation = activeEmulations?.emulations?.find(
    (e: any) => e.topology_id === topologyId && String(e?.status || '').toLowerCase() === 'running'
  )

  const containersQuery = useQuery<any>({
    queryKey: ['emulation-containers', topologyId],
    queryFn: async () => {
      if (!topologyId) return { items: [] }
      const res = await emulationAPI.getContainers(topologyId)
      return res.data
    },
    enabled: hasTopologyId,
    refetchInterval: 10000,
  })
  const containers = containersQuery.data?.items || []

  useEffect(() => {
    if (containersQuery.isError) {
      const err: any = containersQuery.error
      toast.error(err?.response?.data?.detail || 'Failed to load containers', {
        id: `snapshot-page-containers-${topologyId}`,
      })
    }
  }, [containersQuery.isError, containersQuery.error, topologyId])

  // Fetch snapshots
  const snapshotsQuery = useQuery<any>({
    queryKey: ['snapshots', topologyId, filterType, filterStatus],
    queryFn: async () => {
      if (!topologyId) return { items: [] }
      const response = await snapshotsAPI.list(
        topologyId,
        filterType === 'all' ? undefined : filterType,
        filterStatus === 'all' ? undefined : filterStatus
      )
      return response.data
    },
    enabled: hasTopologyId,
    refetchInterval: 5000,
  })

  const snapshotsData = snapshotsQuery.data
  const snapshots = snapshotsData?.items || []

  // Fetch snapshot stats
  const statsQuery = useQuery<any>({
    queryKey: ['snapshot-stats'],
    queryFn: async () => {
      const response = await snapshotsAPI.stats()
      return response.data
    },
    refetchInterval: 10000,
  })
  const stats = statsQuery.data

  useEffect(() => {
    if (snapshotsQuery.isError) {
      const err: any = snapshotsQuery.error
      toast.error(err?.response?.data?.detail || 'Failed to load snapshots', { id: 'snapshots-load' })
    }
  }, [snapshotsQuery.isError, snapshotsQuery.error])

  useEffect(() => {
    if (statsQuery.isError) {
      toast.error('Failed to load snapshot stats', { id: 'snapshot-stats-load' })
    }
  }, [statsQuery.isError])

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => snapshotsAPI.delete(id),
    onSuccess: () => {
      toast.success('Snapshot deleted successfully')
      queryClient.invalidateQueries({ queryKey: ['snapshots'] })
      queryClient.invalidateQueries({ queryKey: ['snapshot-stats'] })
    },
    onError: (error: any) => {
      toast.error(`Failed to delete snapshot: ${error.message}`)
    },
  })

  // Download mutation
  const downloadMutation = useMutation({
    mutationFn: async (id: string) => {
      const response = await snapshotsAPI.download(id)
      return { data: response.data, id }
    },
    onSuccess: ({ data, id }) => {
      const snapshot = snapshots.find((s: any) => s.id === id)
      const filename = snapshot?.name || 'snapshot'
      const blob = new Blob([data])
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${filename}.json.gz`
      a.click()
      window.URL.revokeObjectURL(url)
      toast.success('Snapshot downloaded')
    },
    onError: (error: any) => {
      toast.error(`Download failed: ${error.message}`)
    },
  })

  // Import mutation
  const importMutation = useMutation({
    mutationFn: (file: File) => snapshotsAPI.import(file),
    onSuccess: () => {
      toast.success('Snapshot imported successfully')
      queryClient.invalidateQueries({ queryKey: ['snapshots'] })
      setImportFile(null)
    },
    onError: (error: any) => {
      toast.error(`Import failed: ${error.message}`)
    },
  })

  const handleDelete = (id: string, name: string) => {
    if (confirm(`Are you sure you want to delete snapshot "${name}"?`)) {
      deleteMutation.mutate(id)
    }
  }

  const handleDownload = (id: string) => {
    downloadMutation.mutate(id)
  }

  const handleImport = () => {
    if (importFile) {
      importMutation.mutate(importFile)
    }
  }

  const getStatusBadgeProps = (status: string): { status: 'success' | 'warning' | 'info' | 'error' | 'running', label: string } => {
    switch (status) {
      case 'captured':
        return { status: 'success', label: 'Captured' }
      case 'capturing':
        return { status: 'running', label: 'Capturing' }
      case 'pending':
        return { status: 'info', label: 'Pending' }
      case 'failed':
        return { status: 'error', label: 'Failed' }
      default:
        return { status: 'info', label: status }
    }
  }

  const getTypeColor = (type: string) => {
    const colors: Record<string, string> = {
      topology_only: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300',
      docker_commit: 'bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300',
      criu_live: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
      hybrid_full: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
    }
    return colors[type] || 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300'
  }

  const formatSize = (bytes: number | null) => {
    if (!bytes) return 'N/A'
    const mb = bytes / (1024 * 1024)
    if (mb < 1) return `${(bytes / 1024).toFixed(1)} KB`
    if (mb < 1024) return `${mb.toFixed(1)} MB`
    return `${(mb / 1024).toFixed(2)} GB`
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  if (!hasTopologyId) {
    return (
      <TopologyPicker
        title="Snapshots"
        description="Select a topology to view and create snapshots."
        toPathPrefix="/snapshots"
      />
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <div className="container-custom py-8">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          <div className="lg:col-span-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
            {t('Snapshots')}
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Create, manage, and restore network topology snapshots with CRIU support
          </p>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <ModernCard hover={false} padding="md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Total Snapshots</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total_snapshots}</p>
                </div>
                <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                  <ChartBarIcon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
              </div>
            </ModernCard>
            <ModernCard hover={false} padding="md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Total Size</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {(stats.total_size_mb || 0).toFixed(1)} MB
                  </p>
                </div>
                <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                  <ArrowDownTrayIcon className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
              </div>
            </ModernCard>
            <ModernCard hover={false} padding="md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">CRIU Snapshots</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {(stats.by_type?.criu_live || 0) + (stats.by_type?.hybrid_full || 0)}
                  </p>
                </div>
                <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                  <CheckCircleIcon className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                </div>
              </div>
            </ModernCard>
            <ModernCard hover={false} padding="md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Captured</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">
                    {stats.by_status?.captured || 0}
                  </p>
                </div>
                <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                  <CheckCircleIcon className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
              </div>
            </ModernCard>
          </div>
        )}

        {/* Actions Bar */}
        <ModernCard hover={false} className="mb-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <ModernButton
                onClick={() => setShowCreateModal(true)}
                icon={<PlusIcon className="w-5 h-5" />}
              >
                Create Snapshot
              </ModernButton>

              <div className="flex items-center gap-2">
                <input
                  type="file"
                  accept=".json,.json.gz,.tar,.tar.gz"
                  onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                  className="hidden"
                  id="import-file"
                />
                <label htmlFor="import-file" className="cursor-pointer">
                  <ModernButton variant="outline" icon={<ArrowUpTrayIcon className="w-5 h-5" />}>
                    Import
                  </ModernButton>
                </label>
                {importFile && (
                  <ModernButton
                    onClick={handleImport}
                    loading={importMutation.isPending}
                    variant="primary"
                  >
                    Upload
                  </ModernButton>
                )}
              </div>

              <ModernButton
                variant="outline"
                onClick={() => snapshotsQuery.refetch()}
                icon={<ArrowPathIcon className="w-5 h-5" />}
              >
                Refresh
              </ModernButton>
            </div>

            {/* Filters */}
            <div className="flex items-center gap-2">
              <FunnelIcon className="w-5 h-5 text-gray-400" />
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value as SnapshotType)}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
              >
                <option value="all">All Types</option>
                <option value="topology_only">Topology Only</option>
                <option value="docker_commit">Docker Commit</option>
                <option value="criu_live">CRIU Live</option>
                <option value="hybrid_full">Hybrid Full</option>
              </select>

              <select
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value as SnapshotStatus)}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
              >
                <option value="all">All Status</option>
                <option value="captured">Captured</option>
                <option value="capturing">Capturing</option>
                <option value="pending">Pending</option>
                <option value="failed">Failed</option>
              </select>
            </div>
          </div>
        </ModernCard>

        {/* Snapshots Grid */}
        {snapshotsQuery.isLoading ? (
          <div className="text-center py-12">
            <p className="mt-4 text-gray-600 dark:text-gray-400">Loading snapshots...</p>
          </div>
        ) : snapshots.length === 0 ? (
          <ModernCard hover={false} padding="lg" className="text-center">
            <ChartBarIcon className="w-16 h-16 text-gray-400 dark:text-gray-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">No snapshots found</h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Create your first snapshot to preserve your network topology state
            </p>
            <ModernButton onClick={() => setShowCreateModal(true)} icon={<PlusIcon className="w-5 h-5" />}>
              Create Snapshot
            </ModernButton>
          </ModernCard>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {snapshots.map((snapshot: any) => (
              <div
                key={snapshot.id}
                onClick={() => {
                  setSelectedSnapshot(snapshot)
                  setShowDetailsModal(true)
                }}
                className="cursor-pointer"
              >
                <ModernCard hover={false} className="h-full">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white truncate max-w-[180px]" title={snapshot.name}>
                        {snapshot.name}
                      </h3>
                    </div>
                    <StatusBadge {...getStatusBadgeProps(snapshot.status)} size="sm" />
                  </div>

                  {snapshot.description && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 line-clamp-2">{snapshot.description}</p>
                  )}

                  <div className="space-y-3 mb-6">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-500 dark:text-gray-400">Type:</span>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${getTypeColor(snapshot.snapshot_type)}`}>
                        {snapshot.snapshot_type.replace('_', ' ')}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-500 dark:text-gray-400">Size:</span>
                      <span className="font-medium text-gray-900 dark:text-white">{formatSize(snapshot.size_bytes)}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-500 dark:text-gray-400">Devices:</span>
                      <span className="font-medium text-gray-900 dark:text-white">{snapshot.device_count || 0}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-500 dark:text-gray-400">Created:</span>
                      <span className="text-gray-700 dark:text-gray-300">{formatDate(snapshot.timestamp)}</span>
                    </div>
                  </div>

                  {snapshot.criu_available && (
                    <div className="mb-4">
                      <StatusBadge status="success" label="CRIU Enabled" size="sm" />
                    </div>
                  )}

                  <div className="space-y-2 pt-4 border-t border-gray-200 dark:border-gray-700 mt-auto">
                    {snapshot.status === 'captured' && (
                      <ModernButton
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedSnapshot(snapshot)
                          setShowRestoreModal(true)
                        }}
                        className="w-full"
                        icon={<ArrowPathIcon className="w-4 h-4" />}
                      >
                        Restore
                      </ModernButton>
                    )}
                    <div className="flex items-center gap-2">
                      <ModernButton
                        size="sm"
                        variant="outline"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDownload(snapshot.id)
                        }}
                        disabled={downloadMutation.isPending}
                        className="flex-1"
                        icon={<ArrowDownTrayIcon className="w-4 h-4" />}
                      >
                        Download
                      </ModernButton>
                      <ModernButton
                        size="sm"
                        variant="danger"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDelete(snapshot.id, snapshot.name)
                        }}
                        disabled={deleteMutation.isPending}
                        icon={<TrashIcon className="w-4 h-4" />}
                      />
                    </div>
                  </div>
                </ModernCard>
              </div>
            ))}
          </div>
        )}
          </div>

          <div className="lg:col-span-4 space-y-6 lg:sticky lg:top-24 self-start">
            <ModernCard hover={false}>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-gray-900 dark:text-white">Order summary</div>
                  <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                    Snapshots for this topology
                  </div>
                </div>
                <StatusBadge
                  status={currentEmulation?.status === 'running' ? 'success' : 'stopped'}
                  label={currentEmulation?.status === 'running' ? 'Emulation running' : 'Emulation stopped'}
                  size="sm"
                />
              </div>

              <div className="mt-5 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Containers detected</span>
                  <span className="font-semibold text-gray-900 dark:text-white">{containers.length}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Total snapshots</span>
                  <span className="font-semibold text-gray-900 dark:text-white">{stats?.total_snapshots ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Captured</span>
                  <span className="font-semibold text-gray-900 dark:text-white">{stats?.by_status?.captured ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Failed</span>
                  <span className="font-semibold text-gray-900 dark:text-white">{stats?.by_status?.failed ?? '—'}</span>
                </div>
                <div className="flex items-center justify-between pt-3 border-t border-gray-200 dark:border-gray-800">
                  <span className="text-gray-500 dark:text-gray-400">Total size</span>
                  <span className="font-semibold text-gray-900 dark:text-white">
                    {(stats?.total_size_mb || 0).toFixed(1)} MB
                  </span>
                </div>
              </div>

              <div className="mt-5">
                <ModernButton
                  onClick={() => setShowCreateModal(true)}
                  className="w-full"
                  icon={<PlusIcon className="w-5 h-5" />}
                >
                  Create snapshot
                </ModernButton>
              </div>
            </ModernCard>

            <ModernCard hover={false} className="bg-blue-50 dark:bg-blue-900/15 border-blue-200 dark:border-blue-900/40">
              <div className="flex gap-3">
                <InformationCircleIcon className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-1">
                    Snapshot types
                  </h4>
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    Use <strong>Topology Only</strong> for fast backups, or <strong>Docker Commit</strong> for full container filesystem capture.
                  </p>
                </div>
              </div>
            </ModernCard>
          </div>
        </div>
      </div>

      {/* Modals */}
      {showCreateModal && (
        <CreateSnapshotModal
          topologyId={topologyId}
          emulationId={currentEmulation?.emulation_id}
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false)
            queryClient.invalidateQueries({ queryKey: ['snapshots'] })
          }}
        />
      )}

      {showDetailsModal && selectedSnapshot && (
        <SnapshotDetailsModal
          snapshotId={selectedSnapshot.id}
          topologyId={topologyId}
          onClose={() => {
            setShowDetailsModal(false)
            setSelectedSnapshot(null)
          }}
        />
      )}

      {showRestoreModal && selectedSnapshot && (
        <RestoreSnapshotModal
          snapshot={selectedSnapshot}
          topologyId={topologyId}
          onClose={() => {
            setShowRestoreModal(false)
            setSelectedSnapshot(null)
          }}
          onSuccess={() => {
            setShowRestoreModal(false)
            setSelectedSnapshot(null)
            queryClient.invalidateQueries({ queryKey: ['snapshots'] })
          }}
        />
      )}
    </div>
  )
}
