import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { XMarkIcon, ArrowPathIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { snapshotsAPI } from '@/services/api'
import ContainerSelector from './ContainerSelector'
import { ModernButton } from '@/components/ModernButton'

interface RestoreSnapshotModalProps {
  snapshot: {
    id: string
    name: string
    snapshot_type: string
    description?: string
    target_containers?: string[]
  }
  topologyId?: string
  onClose: () => void
  onSuccess?: () => void
}

export default function RestoreSnapshotModal({
  snapshot,
  topologyId,
  onClose,
  onSuccess,
}: RestoreSnapshotModalProps) {
  const queryClient = useQueryClient()

  const [selectAllContainers, setSelectAllContainers] = useState(true)
  const [selectedContainers, setSelectedContainers] = useState<string[]>([])
  const [restoreNetworkState, setRestoreNetworkState] = useState(true)

  const restoreMutation = useMutation({
    mutationFn: () =>
      snapshotsAPI.restore(
        snapshot.id,
        selectAllContainers ? undefined : selectedContainers,
        restoreNetworkState
      ),
    onSuccess: () => {
      toast.success('Snapshot restore started successfully')
      queryClient.invalidateQueries({ queryKey: ['snapshots'] })
      queryClient.invalidateQueries({ queryKey: ['active-emulations'] })
      onSuccess?.()
      onClose()
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to restore snapshot')
    },
  })

  const handleRestore = () => {
    if (!selectAllContainers && selectedContainers.length === 0) {
      toast.error('Please select at least one container to restore')
      return
    }

    restoreMutation.mutate()
  }

  const getTypeDescription = (type: string) => {
    const descriptions: Record<string, string> = {
      topology_only: 'Restores network topology configuration only',
      docker_commit: 'Restores Docker container filesystems',
      criu_live: 'Restores live process state with CRIU',
      hybrid_full: 'Full restoration including filesystem and process state',
    }
    return descriptions[type] || 'Restores snapshot data'
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex items-center justify-center min-h-screen px-4 pt-4 pb-20 text-center sm:p-0">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative inline-block bg-white dark:bg-gray-800 rounded-2xl text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:max-w-lg sm:w-full border border-gray-200 dark:border-gray-700">
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <ArrowPathIcon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Restore Snapshot
              </h3>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300 transition-colors"
            >
              <XMarkIcon className="w-6 h-6" />
            </button>
          </div>

          {/* Content */}
          <div className="px-6 py-4 space-y-6 max-h-[60vh] overflow-y-auto custom-scrollbar">
            {/* Warning */}
            <div className="flex gap-3 p-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-900/50 rounded-xl">
              <ExclamationTriangleIcon className="w-5 h-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-yellow-900 dark:text-yellow-200 mb-1">
                  Warning: This will modify the current network state
                </p>
                <p className="text-xs text-yellow-800 dark:text-yellow-300">
                  Restoring a snapshot will overwrite current container states and network configuration.
                  Make sure you have backed up any important data.
                </p>
              </div>
            </div>

            {/* Snapshot Info */}
            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Snapshot Name
                </label>
                <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
                  <p className="font-medium text-gray-900 dark:text-white">{snapshot.name}</p>
                  {snapshot.description && (
                    <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">{snapshot.description}</p>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Snapshot Type
                </label>
                <div className="px-4 py-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
                  <p className="font-medium text-gray-900 dark:text-white capitalize">
                    {snapshot.snapshot_type.replace('_', ' ')}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    {getTypeDescription(snapshot.snapshot_type)}
                  </p>
                </div>
              </div>
            </div>

            {/* Container Selection */}
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

            {/* Restore Options */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Restore Options
              </label>
              <div className="space-y-2">
                <label className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors border border-transparent hover:border-gray-200 dark:hover:border-gray-700">
                  <input
                    type="checkbox"
                    checked={restoreNetworkState}
                    onChange={(e) => setRestoreNetworkState(e.target.checked)}
                    className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 mt-0.5"
                  />
                  <div>
                    <span className="font-medium text-gray-900 dark:text-white block">
                      Restore Network State
                    </span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      Restores routing tables, flow tables, and ARP caches
                    </span>
                  </div>
                </label>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
            <ModernButton
              type="button"
              variant="secondary"
              onClick={onClose}
              disabled={restoreMutation.isPending}
            >
              Cancel
            </ModernButton>
            <ModernButton
              onClick={handleRestore}
              loading={restoreMutation.isPending}
              icon={<ArrowPathIcon className="w-5 h-5" />}
            >
              Restore Snapshot
            </ModernButton>
          </div>
        </div>
      </div>
    </div>
  )
}
