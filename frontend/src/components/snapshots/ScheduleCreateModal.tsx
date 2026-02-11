import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { XMarkIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { snapshotsAPI } from '@/services/api'
import CronBuilder from './CronBuilder'
import ContainerSelector from './ContainerSelector'
import { ModernButton } from '@/components/ModernButton'
import { ModernInput } from '@/components/ModernInput'

type SnapshotType = 'topology_only' | 'docker_commit' | 'criu_live' | 'hybrid_full'

interface ScheduleCreateModalProps {
  topologyId?: string
  onClose: () => void
  onSuccess?: () => void
}

export default function ScheduleCreateModal({
  topologyId,
  onClose,
  onSuccess,
}: ScheduleCreateModalProps) {
  const queryClient = useQueryClient()

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    cron_expression: '0 */6 * * *',
    snapshot_type: 'topology_only' as SnapshotType,
    retention_count: 10,
    retention_days: null as number | null,
    compression: true,
    include_routing_tables: true,
    include_flow_tables: true,
    include_arp_tables: true,
  })

  const [selectAllContainers, setSelectAllContainers] = useState(true)
  const [selectedContainers, setSelectedContainers] = useState<string[]>([])
  const [cronError, setCronError] = useState<string>('')

  const createMutation = useMutation({
    mutationFn: (data: typeof formData & { topology_id?: string; target_containers?: string[] }) =>
      snapshotsAPI.schedules.create(data),
    onSuccess: () => {
      toast.success('Schedule created successfully')
      queryClient.invalidateQueries({ queryKey: ['snapshot-schedules'] })
      onSuccess?.()
      onClose()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to create schedule')
    },
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!formData.name.trim()) {
      toast.error('Schedule name is required')
      return
    }

    if (!formData.cron_expression.trim()) {
      toast.error('Schedule expression is required')
      return
    }

    const submitData = {
      ...formData,
      topology_id: topologyId,
      target_containers: selectAllContainers ? undefined : selectedContainers,
      retention_days: formData.retention_days || undefined,
    }

    createMutation.mutate(submitData)
  }

  const SNAPSHOT_TYPES = [
    { value: 'topology_only', label: 'Topology Only', description: 'Fast, small (~1KB)' },
    { value: 'docker_commit', label: 'Docker Commit', description: 'Filesystem (~500MB)' },
    { value: 'criu_live', label: 'CRIU Live', description: 'Live state (~300MB)' },
    { value: 'hybrid_full', label: 'Hybrid Full', description: 'Complete (~700MB)' },
  ]

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:p-0">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative inline-block bg-white dark:bg-gray-800 rounded-2xl text-left overflow-hidden shadow-xl sm:my-8 sm:max-w-lg sm:w-full border border-gray-200 dark:border-gray-700">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Create Snapshot Schedule
            </h3>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit}>
            <div className="px-6 py-4 space-y-6 max-h-[60vh] overflow-y-auto custom-scrollbar">
              {/* Name */}
              <ModernInput
                label="Schedule Name *"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Daily Production Backup"
                required
              />

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Description
                </label>
                <textarea
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Optional description..."
                  rows={2}
                  className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
                />
              </div>

              {/* Schedule */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Schedule *
                </label>
                <CronBuilder
                  value={formData.cron_expression}
                  onChange={(cron) => setFormData({ ...formData, cron_expression: cron })}
                  error={cronError}
                />
              </div>

              {/* Snapshot Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Snapshot Type
                </label>
                <div className="grid grid-cols-2 gap-2">
                  {SNAPSHOT_TYPES.map((type) => (
                    <label
                      key={type.value}
                      className={`flex flex-col p-3 border rounded-xl cursor-pointer ${formData.snapshot_type === type.value
                          ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                          : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 bg-white dark:bg-gray-800'
                        }`}
                    >
                      <input
                        type="radio"
                        name="snapshot_type"
                        value={type.value}
                        checked={formData.snapshot_type === type.value}
                        onChange={(e) =>
                          setFormData({ ...formData, snapshot_type: e.target.value as SnapshotType })
                        }
                        className="sr-only"
                      />
                      <span className={`font-medium text-sm ${formData.snapshot_type === type.value
                          ? 'text-blue-700 dark:text-blue-300'
                          : 'text-gray-900 dark:text-gray-100'
                        }`}>{type.label}</span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">{type.description}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Target Containers */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Target Containers
                </label>
                <ContainerSelector
                  topologyId={topologyId}
                  selectedContainers={selectedContainers}
                  onSelectionChange={setSelectedContainers}
                  selectAll={selectAllContainers}
                  onSelectAllChange={setSelectAllContainers}
                />
              </div>

              {/* Retention Policy */}
              <div className="space-y-3">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Retention Policy
                </label>

                <div className="flex items-center gap-3">
                  <span className="text-gray-700 dark:text-gray-300">Keep last</span>
                  <input
                    type="number"
                    value={formData.retention_count}
                    onChange={(e) =>
                      setFormData({ ...formData, retention_count: parseInt(e.target.value) || 10 })
                    }
                    min={1}
                    max={1000}
                    className="w-20 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
                  />
                  <span className="text-gray-700 dark:text-gray-300">snapshots</span>
                </div>

                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="enable_retention_days"
                    checked={formData.retention_days !== null}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        retention_days: e.target.checked ? 30 : null,
                      })
                    }
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                  />
                  <label htmlFor="enable_retention_days" className="text-gray-700 dark:text-gray-300">
                    Delete snapshots older than
                  </label>
                  {formData.retention_days !== null && (
                    <>
                      <input
                        type="number"
                        value={formData.retention_days}
                        onChange={(e) =>
                          setFormData({ ...formData, retention_days: parseInt(e.target.value) || 30 })
                        }
                        min={1}
                        max={365}
                        className="w-20 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 outline-none"
                      />
                      <span className="text-gray-700 dark:text-gray-300">days</span>
                    </>
                  )}
                </div>
              </div>

              {/* Options */}
              <div className="space-y-2">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  Options
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.compression}
                    onChange={(e) => setFormData({ ...formData, compression: e.target.checked })}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                  />
                  <span className="text-gray-700 dark:text-gray-300">Compress snapshots</span>
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.include_routing_tables}
                    onChange={(e) =>
                      setFormData({ ...formData, include_routing_tables: e.target.checked })
                    }
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                  />
                  <span className="text-gray-700 dark:text-gray-300">Include routing tables</span>
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.include_flow_tables}
                    onChange={(e) =>
                      setFormData({ ...formData, include_flow_tables: e.target.checked })
                    }
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                  />
                  <span className="text-gray-700 dark:text-gray-300">Include flow tables</span>
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={formData.include_arp_tables}
                    onChange={(e) =>
                      setFormData({ ...formData, include_arp_tables: e.target.checked })
                    }
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                  />
                  <span className="text-gray-700 dark:text-gray-300">Include ARP tables</span>
                </label>
              </div>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
              <ModernButton
                type="button"
                variant="secondary"
                onClick={onClose}
              >
                Cancel
              </ModernButton>
              <ModernButton
                type="submit"
                loading={createMutation.isPending}
              >
                Create Schedule
              </ModernButton>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
