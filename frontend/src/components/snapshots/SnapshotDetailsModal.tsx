import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { XMarkIcon, CalendarIcon, ServerIcon, CircleStackIcon, ArrowPathIcon } from '@heroicons/react/24/outline'
import { snapshotsAPI } from '@/services/api'
import { ModernButton } from '@/components/ModernButton'
import { StatusBadge } from '@/components/StatusBadge'
import { ModernCard } from '@/components/ModernCard'
import RestoreSnapshotModal from './RestoreSnapshotModal'

interface SnapshotDetailsModalProps {
    snapshotId: string
    topologyId?: string
    onClose: () => void
}

export default function SnapshotDetailsModal({
    snapshotId,
    topologyId,
    onClose,
}: SnapshotDetailsModalProps) {
    const [showRestoreModal, setShowRestoreModal] = useState(false)

    const { data: snapshot, isLoading } = useQuery({
        queryKey: ['snapshot', snapshotId],
        queryFn: async () => {
            const response = await snapshotsAPI.get(snapshotId)
            return response.data
        },
    })

    const formatDate = (dateString?: string) => {
        if (!dateString) return 'N/A'
        return new Date(dateString).toLocaleString()
    }

    const formatSize = (bytes?: number) => {
        if (bytes === undefined) return 'N/A'
        if (bytes === 0) return '0 B'
        const k = 1024
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
        const i = Math.floor(Math.log(bytes) / Math.log(k))
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
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
                <div className="relative inline-block bg-white dark:bg-gray-800 rounded-2xl text-left overflow-hidden shadow-xl transform transition-all sm:my-8 sm:max-w-2xl sm:w-full border border-gray-200 dark:border-gray-700">
                    {/* Header */}
                    <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
                        <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                            Snapshot Details
                        </h3>
                        <button
                            onClick={onClose}
                            className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300 transition-colors"
                        >
                            <XMarkIcon className="w-6 h-6" />
                        </button>
                    </div>

                    {/* Content */}
                    <div className="px-6 py-6 max-h-[70vh] overflow-y-auto custom-scrollbar">
                        {isLoading ? (
                            <div className="text-center py-12">
                                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 dark:border-blue-400"></div>
                                <p className="mt-4 text-gray-600 dark:text-gray-400">Loading details...</p>
                            </div>
                        ) : snapshot ? (
                            <div className="space-y-6">
                                {/* Header Info */}
                                <div className="flex items-start justify-between">
                                    <div>
                                        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-1">
                                            {snapshot.name}
                                        </h2>
                                        <p className="text-gray-500 dark:text-gray-400 text-sm">
                                            ID: {snapshot.id}
                                        </p>
                                    </div>
                                    <StatusBadge
                                        status={snapshot.status === 'captured' ? 'success' : snapshot.status === 'failed' ? 'error' : 'info'}
                                        label={snapshot.status}
                                    />
                                </div>

                                {/* Description */}
                                {snapshot.description && (
                                    <div className="bg-gray-50 dark:bg-gray-800/50 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
                                        <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">Description</h4>
                                        <p className="text-gray-600 dark:text-gray-400 text-sm">{snapshot.description}</p>
                                    </div>
                                )}

                                {/* Key Stats */}
                                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                                    <ModernCard padding="sm" className="bg-blue-50 dark:bg-blue-900/10 border-blue-100 dark:border-blue-900/30">
                                        <div className="flex items-center gap-3">
                                            <CalendarIcon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                                            <div>
                                                <p className="text-xs text-gray-500 dark:text-gray-400">Created At</p>
                                                <p className="text-sm font-medium text-gray-900 dark:text-white">
                                                    {formatDate(snapshot.created_at)}
                                                </p>
                                            </div>
                                        </div>
                                    </ModernCard>

                                    <ModernCard padding="sm" className="bg-purple-50 dark:bg-purple-900/10 border-purple-100 dark:border-purple-900/30">
                                        <div className="flex items-center gap-3">
                                            <CircleStackIcon className="w-5 h-5 text-purple-600 dark:text-purple-400" />
                                            <div>
                                                <p className="text-xs text-gray-500 dark:text-gray-400">Size</p>
                                                <p className="text-sm font-medium text-gray-900 dark:text-white">
                                                    {formatSize(snapshot.size_bytes)}
                                                </p>
                                            </div>
                                        </div>
                                    </ModernCard>

                                    <ModernCard padding="sm" className="bg-green-50 dark:bg-green-900/10 border-green-100 dark:border-green-900/30">
                                        <div className="flex items-center gap-3">
                                            <ServerIcon className="w-5 h-5 text-green-600 dark:text-green-400" />
                                            <div>
                                                <p className="text-xs text-gray-500 dark:text-gray-400">Type</p>
                                                <p className="text-sm font-medium text-gray-900 dark:text-white capitalize">
                                                    {snapshot.snapshot_type?.replace('_', ' ') || 'Unknown'}
                                                </p>
                                            </div>
                                        </div>
                                    </ModernCard>
                                </div>

                                {/* Configuration */}
                                <div>
                                    <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">Configuration</h4>
                                    <div className="grid grid-cols-2 gap-4">
                                        <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
                                            <span className="text-sm text-gray-600 dark:text-gray-400">Compression</span>
                                            <span className={`text-sm font-medium ${snapshot.compression ? 'text-green-600 dark:text-green-400' : 'text-gray-500'}`}>
                                                {snapshot.compression ? 'Enabled' : 'Disabled'}
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
                                            <span className="text-sm text-gray-600 dark:text-gray-400">Routing Tables</span>
                                            <span className={`text-sm font-medium ${snapshot.include_routing_tables ? 'text-green-600 dark:text-green-400' : 'text-gray-500'}`}>
                                                {snapshot.include_routing_tables ? 'Included' : 'Excluded'}
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
                                            <span className="text-sm text-gray-600 dark:text-gray-400">Flow Tables</span>
                                            <span className={`text-sm font-medium ${snapshot.include_flow_tables ? 'text-green-600 dark:text-green-400' : 'text-gray-500'}`}>
                                                {snapshot.include_flow_tables ? 'Included' : 'Excluded'}
                                            </span>
                                        </div>
                                        <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg border border-gray-200 dark:border-gray-700">
                                            <span className="text-sm text-gray-600 dark:text-gray-400">ARP Tables</span>
                                            <span className={`text-sm font-medium ${snapshot.include_arp_tables ? 'text-green-600 dark:text-green-400' : 'text-gray-500'}`}>
                                                {snapshot.include_arp_tables ? 'Included' : 'Excluded'}
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                {/* Target Containers */}
                                {snapshot.target_containers && Array.isArray(snapshot.target_containers) && snapshot.target_containers.length > 0 && (
                                    <div>
                                        <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-3">
                                            Target Containers ({snapshot.target_containers.length})
                                        </h4>
                                        <div className="flex flex-wrap gap-2">
                                            {snapshot.target_containers.map((container: string) => (
                                                <span
                                                    key={container}
                                                    className="px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded text-xs font-mono border border-gray-200 dark:border-gray-600"
                                                >
                                                    {container}
                                                </span>
                                            ))}
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-center py-12 text-gray-500 dark:text-gray-400">
                                Snapshot not found
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="flex items-center justify-between gap-3 px-6 py-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
                        <ModernButton
                            variant="secondary"
                            onClick={onClose}
                        >
                            Close
                        </ModernButton>
                        {snapshot && snapshot.status === 'captured' && (
                            <ModernButton
                                onClick={() => setShowRestoreModal(true)}
                                icon={<ArrowPathIcon className="w-5 h-5" />}
                            >
                                Restore Snapshot
                            </ModernButton>
                        )}
                    </div>
                </div>
            </div>

            {/* Restore Modal */}
            {showRestoreModal && snapshot && (
                <RestoreSnapshotModal
                    snapshot={snapshot}
                    topologyId={topologyId}
                    onClose={() => setShowRestoreModal(false)}
                    onSuccess={() => {
                        setShowRestoreModal(false)
                        onClose()
                    }}
                />
            )}
        </div>
    )
}
