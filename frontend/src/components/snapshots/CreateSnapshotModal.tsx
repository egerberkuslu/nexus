import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { XMarkIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { snapshotsAPI } from '@/services/api'
import ContainerSelector from './ContainerSelector'
import { ModernButton } from '@/components/ModernButton'
import { ModernInput } from '@/components/ModernInput'

type SnapshotType = 'topology_only' | 'docker_commit' | 'criu_live' | 'hybrid_full'

interface CreateSnapshotModalProps {
    topologyId?: string
    emulationId?: string
    onClose: () => void
    onSuccess?: () => void
}

export default function CreateSnapshotModal({
    topologyId,
    emulationId,
    onClose,
    onSuccess,
}: CreateSnapshotModalProps) {
    const queryClient = useQueryClient()

    const [formData, setFormData] = useState({
        name: '',
        description: '',
        snapshot_type: 'topology_only' as SnapshotType,
        compression: true,
        include_routing_tables: true,
        include_flow_tables: true,
        include_arp_tables: true,
    })

    const [selectAllContainers, setSelectAllContainers] = useState(true)
    const [selectedContainers, setSelectedContainers] = useState<string[]>([])

    const snapshotTypesQuery = useQuery({
        queryKey: ['snapshot-types'],
        queryFn: async () => {
            const res = await snapshotsAPI.types()
            return res.data
        },
        staleTime: 60_000,
    })

    const criuAvailable = Boolean(snapshotTypesQuery.data?.criu_available)
    const requiresRunning = (type: SnapshotType) => type !== 'topology_only'
    const requiresCriu = (type: SnapshotType) => type === 'criu_live' || type === 'hybrid_full'

    const createMutation = useMutation({
        mutationFn: (data: typeof formData & { topology_id?: string; emulation_id?: string; target_containers?: string[] }) =>
            snapshotsAPI.create(data),
        onSuccess: () => {
            toast.success('Snapshot creation started')
            queryClient.invalidateQueries({ queryKey: ['snapshots'] })
            onSuccess?.()
            onClose()
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.detail || 'Failed to create snapshot')
        },
    })

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault()

        if (!topologyId) {
            toast.error('Select a topology first')
            return
        }

        if (!formData.name.trim()) {
            toast.error('Snapshot name is required')
            return
        }

        if (requiresCriu(formData.snapshot_type) && !criuAvailable) {
            toast.error('CRIU is not available on this deployment')
            return
        }

        if (requiresRunning(formData.snapshot_type) && !emulationId && requiresCriu(formData.snapshot_type)) {
            toast.error('Start the emulation before creating this snapshot type')
            return
        }

        const submitData = {
            ...formData,
            topology_id: topologyId,
            emulation_id: emulationId,
            target_containers: selectAllContainers ? undefined : selectedContainers,
        }

        createMutation.mutate(submitData)
    }

    const SNAPSHOT_TYPES = [
        {
            value: 'topology_only',
            label: 'Topology Only',
            description: 'Fast, small (~1KB)',
            help: 'Saves network configuration, topology structure, and device settings. Best for quick backups.'
        },
        {
            value: 'docker_commit',
            label: 'Docker Commit',
            description: 'Filesystem (~500MB)',
            help: 'Saves container filesystems using Docker commit. Preserves installed packages and files.'
        },
        {
            value: 'criu_live',
            label: 'CRIU Live',
            description: 'Live state (~300MB)',
            help: 'Captures live process memory with CRIU. Includes running processes, open connections, and memory state.'
        },
        {
            value: 'hybrid_full',
            label: 'Hybrid Full',
            description: 'Complete (~700MB)',
            help: 'Combines Docker commit + CRIU. Complete snapshot with filesystem and process state.'
        },
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
                            Create Snapshot
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
                                label="Snapshot Name *"
                                value={formData.name}
                                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                placeholder="e.g., Pre-test Baseline"
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

                            {/* Snapshot Type */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                                    Snapshot Type *
                                </label>
	                                <div className="grid grid-cols-1 gap-3">
	                                    {SNAPSHOT_TYPES.map((type) => {
	                                        const value = type.value as SnapshotType
	                                        const disabled =
	                                            (requiresCriu(value) && !criuAvailable) ||
	                                            (requiresCriu(value) && !emulationId)
	                                        const selected = formData.snapshot_type === value

	                                        return (
	                                            <label
	                                                key={type.value}
	                                                className={`flex flex-col p-4 border-2 rounded-xl ${disabled
	                                                    ? 'opacity-60 cursor-not-allowed border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/30'
	                                                    : selected
	                                                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 shadow-sm cursor-pointer'
	                                                        : 'border-gray-300 dark:border-gray-600 hover:border-gray-400 dark:hover:border-gray-500 bg-white dark:bg-gray-800 cursor-pointer'
	                                                    }`}
	                                            >
	                                            <input
	                                                type="radio"
	                                                name="snapshot_type"
	                                                value={type.value}
	                                                checked={selected}
	                                                disabled={disabled}
	                                                onChange={(e) => {
	                                                    if (disabled) return
	                                                    setFormData({ ...formData, snapshot_type: e.target.value as SnapshotType })
	                                                }}
	                                                className="sr-only"
	                                            />
	                                            <div className="flex items-start justify-between mb-1">
	                                                <span className={`font-semibold text-base ${selected
	                                                        ? 'text-blue-700 dark:text-blue-300'
	                                                        : 'text-gray-900 dark:text-gray-100'
	                                                    }`}>{type.label}</span>
	                                                <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded">
	                                                    {type.description}
	                                                </span>
	                                            </div>
	                                            <span className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
	                                                {type.help}
	                                                {requiresCriu(value) && !criuAvailable && (
	                                                    <span className="block mt-1 text-red-600 dark:text-red-400">
	                                                        Not available: CRIU support is disabled
	                                                    </span>
	                                                )}
	                                                {requiresCriu(value) && criuAvailable && !emulationId && (
	                                                    <span className="block mt-1 text-yellow-700 dark:text-yellow-400">
	                                                        Requires a running emulation
	                                                    </span>
	                                                )}
	                                            </span>
	                                        </label>
	                                        )
	                                    })}
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

                            {/* Options */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                                    Snapshot Options
                                </label>
                                <div className="space-y-3 bg-gray-50 dark:bg-gray-800/50 p-4 rounded-xl border border-gray-200 dark:border-gray-700">
                                    <label className="flex items-start gap-3 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={formData.compression}
                                            onChange={(e) => setFormData({ ...formData, compression: e.target.checked })}
                                            className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 mt-0.5"
                                        />
                                        <div>
                                            <span className="text-gray-900 dark:text-white font-medium text-sm block">Compress snapshot</span>
                                            <span className="text-xs text-gray-600 dark:text-gray-400">Use gzip compression to reduce file size</span>
                                        </div>
                                    </label>

                                    <label className="flex items-start gap-3 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={formData.include_routing_tables}
                                            onChange={(e) =>
                                                setFormData({ ...formData, include_routing_tables: e.target.checked })
                                            }
                                            className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 mt-0.5"
                                        />
                                        <div>
                                            <span className="text-gray-900 dark:text-white font-medium text-sm block">Include routing tables</span>
                                            <span className="text-xs text-gray-600 dark:text-gray-400">Save IP routing configurations</span>
                                        </div>
                                    </label>

                                    <label className="flex items-start gap-3 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={formData.include_flow_tables}
                                            onChange={(e) =>
                                                setFormData({ ...formData, include_flow_tables: e.target.checked })
                                            }
                                            className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 mt-0.5"
                                        />
                                        <div>
                                            <span className="text-gray-900 dark:text-white font-medium text-sm block">Include flow tables</span>
                                            <span className="text-xs text-gray-600 dark:text-gray-400">Save OpenFlow switch rules</span>
                                        </div>
                                    </label>

                                    <label className="flex items-start gap-3 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={formData.include_arp_tables}
                                            onChange={(e) =>
                                                setFormData({ ...formData, include_arp_tables: e.target.checked })
                                            }
                                            className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 mt-0.5"
                                        />
                                        <div>
                                            <span className="text-gray-900 dark:text-white font-medium text-sm block">Include ARP tables</span>
                                            <span className="text-xs text-gray-600 dark:text-gray-400">Save MAC address resolution tables</span>
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
                            >
                                Cancel
                            </ModernButton>
                            <ModernButton
                                type="submit"
                                loading={createMutation.isPending}
                            >
                                Create Snapshot
                            </ModernButton>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    )
}
