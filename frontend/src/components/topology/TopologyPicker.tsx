import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { topologiesAPI, emulationAPI } from '@/services/api'
import { ModernCard } from '@/components/ModernCard'
import { ModernButton } from '@/components/ModernButton'
import { StatusBadge } from '@/components/StatusBadge'
import type { Topology } from '@/types/topology'

type Props = {
  title: string
  description?: string
  toPathPrefix: '/snapshots' | '/schedules'
}

export default function TopologyPicker({ title, description, toPathPrefix }: Props) {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')

  const topologiesQuery = useQuery<Topology[]>({
    queryKey: ['topologies'],
    queryFn: async () => {
      const res = await topologiesAPI.list()
      return res.data || []
    },
  })

  const activeEmulationsQuery = useQuery<any[]>({
    queryKey: ['active-emulations'],
    queryFn: async () => {
      const res = await emulationAPI.active()
      return res.data?.emulations || []
    },
    refetchInterval: 10000,
  })

  useEffect(() => {
    if (topologiesQuery.isError) {
      toast.error('Failed to load topologies', { id: 'topologies-load' })
    }
  }, [topologiesQuery.isError])

  useEffect(() => {
    if (activeEmulationsQuery.isError) {
      toast.error('Failed to load active emulations', { id: 'active-emulations-load' })
    }
  }, [activeEmulationsQuery.isError])

  const items = useMemo(() => {
    const byTopologyId = new Map<string, any>()
    for (const e of activeEmulationsQuery.data || []) byTopologyId.set(e.topology_id, e)

    return (topologiesQuery.data || []).map((t) => ({
      id: t.id,
      name: t.name,
      status: byTopologyId.get(t.id)?.status as string | undefined,
      node_count: byTopologyId.get(t.id)?.node_count ?? t.nodes?.length ?? 0,
      link_count: byTopologyId.get(t.id)?.link_count ?? t.links?.length ?? 0,
    }))
  }, [topologiesQuery.data, activeEmulationsQuery.data])

  const filteredItems = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return items
    return items.filter((t) => t.name.toLowerCase().includes(q) || t.id.toLowerCase().includes(q))
  }, [items, query])

  const isLoading = topologiesQuery.isLoading

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-3xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{title}</h1>
          {description && (
            <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">{description}</p>
          )}
        </div>

        <ModernCard hover={false}>
          <div className="space-y-4">
            <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
              <div className="flex-1">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Find a topology
                </label>
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search by name…"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-xl bg-white dark:bg-gray-800 text-gray-900 dark:text-white outline-none"
                />
              </div>
              <div className="sm:pt-7">
                <ModernButton variant="outline" onClick={() => topologiesQuery.refetch()}>
                  Refresh
                </ModernButton>
              </div>
            </div>

            {isLoading ? (
              <div className="text-sm text-gray-600 dark:text-gray-400">Loading topologies…</div>
            ) : filteredItems.length === 0 ? (
              <div className="text-sm text-gray-600 dark:text-gray-400">No topologies found.</div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {filteredItems.map((t) => {
                  const status = t.status || 'stopped'
                  const badgeStatus = status === 'running' ? 'running' : status === 'paused' ? 'warning' : 'stopped'
                  return (
                    <div
                      key={t.id}
                      onClick={() => navigate(`${toPathPrefix}/${t.id}`)}
                      className="cursor-pointer"
                    >
                      <ModernCard hover={false} className="border border-gray-200 dark:border-gray-700">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="text-base font-semibold text-gray-900 dark:text-white truncate">
                              {t.name}
                            </div>
                            <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                              {t.node_count} nodes • {t.link_count} links
                            </div>
                            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400 font-mono truncate">
                              {t.id}
                            </div>
                          </div>
                          <div className="flex-shrink-0">
                            <StatusBadge
                              status={badgeStatus as any}
                              label={status}
                              size="sm"
                              showIcon={false}
                            />
                          </div>
                        </div>
                      </ModernCard>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </ModernCard>
      </div>
    </div>
  )
}
