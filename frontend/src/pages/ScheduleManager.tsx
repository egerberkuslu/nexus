import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  PlusIcon,
  CalendarIcon,
  ClockIcon,
  PlayIcon,
  PauseIcon,
  TrashIcon,
  ArrowPathIcon,
  ChartBarIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline'
import { snapshotsAPI } from '@/services/api'
import { SnapshotSchedule } from '@/types/topology'
import ScheduleCreateModal from '@/components/snapshots/ScheduleCreateModal'
import { ModernButton } from '@/components/ModernButton'
import { ModernCard } from '@/components/ModernCard'
import { StatusBadge } from '@/components/StatusBadge'
import TopologyPicker from '@/components/topology/TopologyPicker'

export default function ScheduleManager() {
  const { topologyId } = useParams()
  const queryClient = useQueryClient()
  const hasTopologyId = Boolean(topologyId)

  const [showCreateModal, setShowCreateModal] = useState(false)

  // Fetch schedules
  const schedulesQuery = useQuery<SnapshotSchedule[]>({
    queryKey: ['snapshot-schedules', topologyId],
    queryFn: async () => {
      if (!topologyId) return []
      const response = await snapshotsAPI.schedules.list(topologyId)
      return response.data?.items || []
    },
    enabled: hasTopologyId,
    refetchInterval: 30000,
  })
  const schedules = schedulesQuery.data || []

  useEffect(() => {
    if (schedulesQuery.isError) {
      const err: any = schedulesQuery.error
      toast.error(err?.response?.data?.detail || 'Failed to load schedules', { id: 'schedules-load' })
    }
  }, [schedulesQuery.isError, schedulesQuery.error])

  // Toggle active mutation
  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      snapshotsAPI.schedules.update(id, { is_active }),
    onSuccess: () => {
      toast.success('Schedule updated')
      queryClient.invalidateQueries({ queryKey: ['snapshot-schedules'] })
    },
    onError: () => {
      toast.error('Failed to update schedule')
    },
  })

  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: (id: string) => snapshotsAPI.schedules.delete(id),
    onSuccess: () => {
      toast.success('Schedule deleted')
      queryClient.invalidateQueries({ queryKey: ['snapshot-schedules'] })
    },
    onError: () => {
      toast.error('Failed to delete schedule')
    },
  })

  // Trigger mutation
  const triggerMutation = useMutation({
    mutationFn: (id: string) => snapshotsAPI.schedules.trigger(id),
    onSuccess: () => {
      toast.success('Snapshot triggered')
      queryClient.invalidateQueries({ queryKey: ['snapshots'] })
    },
    onError: () => {
      toast.error('Failed to trigger snapshot')
    },
  })

  const handleDelete = (schedule: SnapshotSchedule) => {
    if (confirm(`Delete schedule "${schedule.name}"?`)) {
      deleteMutation.mutate(schedule.id)
    }
  }

  const formatNextRun = (nextRun?: string) => {
    if (!nextRun) return 'Not scheduled'

    const next = new Date(nextRun)
    const now = new Date()
    const diff = next.getTime() - now.getTime()

    if (diff < 0) return 'Overdue'

    const hours = Math.floor(diff / (1000 * 60 * 60))
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))

    if (hours > 24) {
      const days = Math.floor(hours / 24)
      return `${days}d ${hours % 24}h`
    }

    if (hours > 0) {
      return `${hours}h ${minutes}m`
    }

    return `${minutes}m`
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleString()
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

  if (!hasTopologyId) {
    return (
      <TopologyPicker
        title="Snapshot Schedules"
        description="Select a topology to manage schedules."
        toPathPrefix="/schedules"
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
            Snapshot Schedules
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Manage automatic snapshot schedules with retention policies
          </p>
        </div>

        {/* Summary Stats */}
        {schedules.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <ModernCard hover={false} padding="md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Total Schedules</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{schedules.length}</p>
                </div>
                <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                  <CalendarIcon className="w-6 h-6 text-blue-600 dark:text-blue-400" />
                </div>
              </div>
            </ModernCard>
            <ModernCard hover={false} padding="md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Active Schedules</p>
                  <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                    {schedules.filter((s: SnapshotSchedule) => s.is_active).length}
                  </p>
                </div>
                <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                  <PlayIcon className="w-6 h-6 text-green-600 dark:text-green-400" />
                </div>
              </div>
            </ModernCard>
            <ModernCard hover={false} padding="md">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">Total Runs</p>
                  <p className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                    {schedules.reduce((sum: number, s: SnapshotSchedule) => sum + s.run_count, 0)}
                  </p>
                </div>
                <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                  <ChartBarIcon className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                </div>
              </div>
            </ModernCard>
          </div>
        )}

        {/* Actions Bar */}
        <ModernCard hover={false} className="mb-6">
          <div className="flex items-center justify-between">
            <ModernButton
              onClick={() => setShowCreateModal(true)}
              icon={<PlusIcon className="w-5 h-5" />}
            >
              Create Schedule
            </ModernButton>

            <ModernButton
              variant="outline"
              onClick={() => schedulesQuery.refetch()}
              icon={<ArrowPathIcon className="w-5 h-5" />}
            >
              Refresh
            </ModernButton>
          </div>
        </ModernCard>

        {/* Schedules Table */}
        {schedulesQuery.isLoading ? (
          <div className="text-center py-12">
            <p className="mt-4 text-gray-600 dark:text-gray-400">Loading schedules...</p>
          </div>
        ) : schedules.length === 0 ? (
          <ModernCard hover={false} padding="lg" className="text-center">
            <CalendarIcon className="w-16 h-16 text-gray-400 dark:text-gray-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
              No schedules configured
            </h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Create your first automatic snapshot schedule
            </p>
            <ModernButton onClick={() => setShowCreateModal(true)} icon={<PlusIcon className="w-5 h-5" />}>
              Create Schedule
            </ModernButton>
          </ModernCard>
        ) : (
          <ModernCard hover={false} padding="none" className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                <thead className="bg-gray-50 dark:bg-gray-800/50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Schedule
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Type
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Cron
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Next Run
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Stats
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                  {schedules.map((schedule: SnapshotSchedule) => (
                    <tr key={schedule.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="font-medium text-gray-900 dark:text-white">{schedule.name}</div>
                        <div className="text-sm text-gray-500 dark:text-gray-400">
                          Retention: {schedule.retention_count || 10} snapshots
                          {schedule.retention_days && `, ${schedule.retention_days} days`}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getTypeColor(schedule.snapshot_type)}`}>
                          {schedule.snapshot_type.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <code className="text-sm bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded text-gray-800 dark:text-gray-200 font-mono">
                          {schedule.cron_expression}
                        </code>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <ClockIcon className="w-4 h-4 text-gray-400 dark:text-gray-500" />
                          <span className="text-sm font-medium text-gray-900 dark:text-white">
                            {formatNextRun(schedule.next_run_at)}
                          </span>
                        </div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          Last: {formatDate(schedule.last_run_at)}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center gap-4">
                          <StatusBadge status="success" label={schedule.run_count.toString()} size="sm" />
                          {schedule.failure_count > 0 && (
                            <StatusBadge status="error" label={schedule.failure_count.toString()} size="sm" />
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <button
                          onClick={() =>
                            toggleMutation.mutate({
                              id: schedule.id,
                              is_active: !schedule.is_active,
                            })
                          }
                          className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium ${schedule.is_active
                              ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50'
                              : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600'
                            }`}
                        >
                          {schedule.is_active ? (
                            <>
                              <PlayIcon className="w-3 h-3" /> Active
                            </>
                          ) : (
                            <>
                              <PauseIcon className="w-3 h-3" /> Paused
                            </>
                          )}
                        </button>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right">
                        <div className="flex items-center justify-end gap-2">
                          <ModernButton
                            size="sm"
                            variant="outline"
                            onClick={() => triggerMutation.mutate(schedule.id)}
                            disabled={triggerMutation.isPending}
                            title="Run now"
                            icon={<PlayIcon className="w-4 h-4 text-blue-600 dark:text-blue-400" />}
                          />
                          <ModernButton
                            size="sm"
                            variant="danger"
                            onClick={() => handleDelete(schedule)}
                            disabled={deleteMutation.isPending}
                            title="Delete"
                            icon={<TrashIcon className="w-4 h-4" />}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </ModernCard>
        )}
          </div>

          <div className="lg:col-span-4 space-y-6 lg:sticky lg:top-24 self-start">
            <ModernCard hover={false}>
              <div className="text-sm font-semibold text-gray-900 dark:text-white">Order summary</div>
              <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Schedules for this topology
              </div>

              <div className="mt-5 space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Total schedules</span>
                  <span className="font-semibold text-gray-900 dark:text-white">{schedules.length}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Active schedules</span>
                  <span className="font-semibold text-gray-900 dark:text-white">
                    {schedules.filter((s: SnapshotSchedule) => s.is_active).length}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 dark:text-gray-400">Total runs</span>
                  <span className="font-semibold text-gray-900 dark:text-white">
                    {schedules.reduce((sum: number, s: SnapshotSchedule) => sum + s.run_count, 0)}
                  </span>
                </div>
                <div className="flex items-center justify-between pt-3 border-t border-gray-200 dark:border-gray-800">
                  <span className="text-gray-500 dark:text-gray-400">Failures</span>
                  <span className="font-semibold text-gray-900 dark:text-white">
                    {schedules.reduce((sum: number, s: SnapshotSchedule) => sum + s.failure_count, 0)}
                  </span>
                </div>
              </div>

              <div className="mt-5">
                <ModernButton
                  onClick={() => setShowCreateModal(true)}
                  className="w-full"
                  icon={<PlusIcon className="w-5 h-5" />}
                >
                  Create schedule
                </ModernButton>
              </div>
            </ModernCard>

            <ModernCard hover={false} className="bg-blue-50 dark:bg-blue-900/15 border-blue-200 dark:border-blue-900/40">
              <div className="flex gap-3">
                <InformationCircleIcon className="w-5 h-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-1">
                    About schedules
                  </h4>
                  <p className="text-sm text-blue-800 dark:text-blue-300">
                    Schedules run snapshots using <strong>cron expressions</strong> and retention rules to keep storage under control.
                  </p>
                </div>
              </div>
            </ModernCard>
          </div>
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <ScheduleCreateModal
          topologyId={topologyId}
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ['snapshot-schedules'] })
          }}
        />
      )}
    </div>
  )
}
