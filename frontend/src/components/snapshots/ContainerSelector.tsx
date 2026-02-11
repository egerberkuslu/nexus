import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { CheckIcon, ServerIcon, CpuChipIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { emulationAPI } from '@/services/api'
import { StatusBadge } from '@/components/StatusBadge'

interface Container {
  name: string
  type: string
  is_docker: boolean
  status: string
  container_id?: string
}

interface ContainerSelectorProps {
  topologyId?: string
  selectedContainers: string[]
  onSelectionChange: (containers: string[]) => void
  selectAll?: boolean
  onSelectAllChange?: (selectAll: boolean) => void
}

export default function ContainerSelector({
  topologyId,
  selectedContainers,
  onSelectionChange,
  selectAll = true,
  onSelectAllChange,
}: ContainerSelectorProps) {
  const [localSelectAll, setLocalSelectAll] = useState(selectAll)

  // Fetch containers from emulation or topology
  const { data: containersData, isLoading } = useQuery({
    queryKey: ['emulation-containers', topologyId],
    queryFn: async () => {
      if (!topologyId) {
        return []
      }

      try {
        const res = await emulationAPI.getContainers(topologyId)
        const items = res.data?.items || []
        return items.map((c: any) => ({
          name: String(c?.name || c?.container_name || 'unknown'),
          type: String((Array.isArray(c?.image) ? c.image[0] : c?.image) || 'docker'),
          is_docker: true,
          status: String(c?.status || 'unknown'),
          container_id: String(c?.container_id || ''),
        }))
      } catch (err) {
        toast.error('Failed to load containers', { id: `snapshot-containers-${topologyId}` })
        return []
      }
    },
    refetchInterval: 10000,
    enabled: !!topologyId,
  })

  const containers: Container[] = containersData || []

  useEffect(() => {
    setLocalSelectAll(selectAll)
  }, [selectAll])

  const handleSelectAll = () => {
    const newSelectAll = !localSelectAll
    setLocalSelectAll(newSelectAll)
    onSelectAllChange?.(newSelectAll)

    if (newSelectAll) {
      onSelectionChange([])
    }
  }

  const handleContainerToggle = (containerName: string) => {
    if (localSelectAll) {
      // Switch to specific selection mode
      setLocalSelectAll(false)
      onSelectAllChange?.(false)
      onSelectionChange([containerName])
    } else {
      const newSelection = selectedContainers.includes(containerName)
        ? selectedContainers.filter((c) => c !== containerName)
        : [...selectedContainers, containerName]
      onSelectionChange(newSelection)
    }
  }

  const getContainerIcon = (type: string) => {
    if (type === 'docker' || type === 'docker_host') {
      return <ServerIcon className="w-5 h-5" />
    }
    return <CpuChipIcon className="w-5 h-5" />
  }

  const getStatusColor = (status: string) => {
    return status === 'running' ? 'text-green-500 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'
  }

  if (isLoading) {
    return (
      <div className="p-4 text-center text-gray-500 dark:text-gray-400">
        Loading containers...
      </div>
    )
  }

  if (containers.length === 0) {
    return (
      <div className="p-4 text-center text-gray-500 dark:text-gray-400">
        No containers found in emulation
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {/* Select All Option */}
      <label className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 border border-transparent hover:border-gray-200 dark:hover:border-gray-700">
        <input
          type="checkbox"
          checked={localSelectAll}
          onChange={handleSelectAll}
          className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
        />
        <span className="font-medium text-gray-900 dark:text-white">All containers</span>
        <span className="text-sm text-gray-500 dark:text-gray-400">({containers.length} total)</span>
      </label>

      {/* Individual Container Selection */}
      {!localSelectAll && (
        <div className="border border-gray-200 dark:border-gray-700 rounded-lg divide-y divide-gray-200 dark:divide-gray-700 max-h-60 overflow-y-auto custom-scrollbar">
          {containers.map((container) => {
            const isSelected = selectedContainers.includes(container.name)

            return (
              <label
                key={container.name}
                className={`flex items-center gap-3 p-3 cursor-pointer ${isSelected
                  ? 'bg-blue-50 dark:bg-blue-900/20'
                  : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
                  }`}
              >
                <input
                  type="checkbox"
                  checked={isSelected}
                  onChange={() => handleContainerToggle(container.name)}
                  className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                />

                <div className={getStatusColor(container.status)}>
                  {getContainerIcon(container.type)}
                </div>

                <div className="flex-1">
                  <div className="font-medium text-gray-900 dark:text-white">{container.name}</div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    {container.type}
                    {container.is_docker && ' (Docker)'}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <StatusBadge
                    status={container.status === 'running' ? 'success' : 'stopped'}
                    label={container.status}
                    size="sm"
                  />

                  {isSelected && (
                    <CheckIcon className="w-5 h-5 text-blue-600 dark:text-blue-400" />
                  )}
                </div>
              </label>
            )
          })}
        </div>
      )}

      {/* Selection Summary */}
      {!localSelectAll && selectedContainers.length > 0 && (
        <div className="text-sm text-gray-600 dark:text-gray-400">
          {selectedContainers.length} container{selectedContainers.length !== 1 ? 's' : ''} selected
        </div>
      )}
    </div>
  )
}
