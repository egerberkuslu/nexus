import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FolderIcon, LayoutList, Plus, RefreshCw, Trash2, Edit, Search, X } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { topologiesAPI } from '@/services/api'
import { ModernCard } from '@/components/ModernCard'
import type { Topology } from '@/types/topology'

export interface ProjectCardProps {
  id: string
  name: string
  description: string
  createdAt: string
  status?: 'active' | 'inactive'
  onDelete?: (id: string) => void
  onEdit?: (id: string) => void
}

export const ProjectCard: React.FC<ProjectCardProps> = ({
  id,
  name,
  description,
  createdAt,
  status = 'inactive',
  onDelete,
  onEdit,
}) => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [manageOpen, setManageOpen] = useState(false)
  const [search, setSearch] = useState('')

  const {
    data: topologies,
    isLoading: topologiesLoading,
    refetch: refetchTopologies,
  } = useQuery({
    queryKey: ['project-topologies', id],
    queryFn: async () => (await topologiesAPI.list(id)).data,
    enabled: manageOpen,
    staleTime: 0,
  })

  const derivedProjectStatus = useMemo(() => {
    const hasRunning = (topologies || []).some((top: any) => top?.is_active || String(top?.emulation_status).toLowerCase() === 'running')
    return hasRunning ? 'active' : status
  }, [status, topologies])

  const sortedTopologies = useMemo(() => {
    const list = [...(topologies || [])] as any[]
    list.sort((a, b) => String(b?.updated_at || '').localeCompare(String(a?.updated_at || '')))
    return list
  }, [topologies])

  const filteredTopologies = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return sortedTopologies
    return sortedTopologies.filter((top: any) => {
      const hay = `${top?.name ?? ''} ${top?.id ?? ''}`.toLowerCase()
      return hay.includes(q)
    })
  }, [search, sortedTopologies])

  const topologyCount = topologies?.length ?? 0

  const handleOpenDefault = async () => {
    try {
      const list = sortedTopologies.length ? sortedTopologies : (await topologiesAPI.list(id)).data
      const next = (list || [])[0] as any
      if (next?.id) {
        navigate(`/topology/${next.id}`)
        return
      }
      const created = await topologiesAPI.create({
        project_id: id,
        name: `${name} - Main Topology`,
        description: 'Default topology',
        nodes: [],
        links: [],
        controllers: [],
      })
      navigate(`/topology/${created.data.id}`)
    } catch (error) {
      console.error('Error opening project:', error)
    }
  }

  const handleCreateTopology = async () => {
    try {
      const created = await topologiesAPI.create({
        project_id: id,
        name: `${name} - Topology ${topologyCount + 1}`,
        description: '',
        nodes: [],
        links: [],
        controllers: [],
      })
      setManageOpen(false)
      navigate(`/topology/${created.data.id}`)
    } catch (error) {
      console.error('Error creating topology:', error)
    }
  }

  const handleDeleteTopology = async (topologyId: string) => {
    if (!confirm('Delete this topology? This cannot be undone.')) return
    try {
      await topologiesAPI.delete(topologyId)
      await refetchTopologies()
    } catch (error) {
      console.error('Error deleting topology:', error)
    }
  }

  return (
    <ModernCard hover={false} className="overflow-hidden border-2 border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
      <div className="block">
        <div className="p-6 space-y-4">
          <div className="flex items-start justify-between">
            <div className="flex items-start gap-4 flex-1 min-w-0">
              <div className="relative">
                <div className="w-12 h-12 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-2xl flex items-center justify-center">
                  <FolderIcon className="h-6 w-6 text-white" />
                </div>
                {derivedProjectStatus === 'active' && (
                  <div className="absolute -top-1 -right-1 w-3 h-3 bg-emerald-500 border-2 border-white dark:border-gray-900 rounded-full" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="text-base font-bold text-gray-900 dark:text-white truncate mb-1">
                  {name}
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 line-clamp-2 leading-relaxed">
                  {description || t('projects.noDescription')}
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-gray-100 dark:border-gray-800">
            <div className="text-xs text-gray-500 dark:text-gray-500">
              {new Date(createdAt).toLocaleDateString()}
            </div>
            <div className="flex items-center gap-2">
              <span
                className={
                  derivedProjectStatus === 'active'
                    ? 'px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300'
                    : 'px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300'
                }
              >
                {derivedProjectStatus}
              </span>
              <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300">
                {topologyCount ? `${topologyCount} topologies` : 'Topologies'}
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between gap-3 pt-2">
            <button
              onClick={(e) => {
                e.preventDefault()
                void handleOpenDefault()
              }}
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700 transition-colors flex-1"
            >
              Open
            </button>
            <button
              onClick={(e) => {
                e.preventDefault()
                setManageOpen(true)
              }}
              className="inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
            >
              <LayoutList size={18} />
              Manage
            </button>
          </div>
        </div>
      </div>

      {manageOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 dark:bg-black/80 backdrop-blur-sm p-4"
          onClick={() => setManageOpen(false)}
        >
          <div
            className="w-full max-w-3xl rounded-3xl bg-white dark:bg-gray-900 shadow-2xl border border-gray-200 dark:border-gray-800 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6 border-b border-gray-100 dark:border-gray-800">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <div className="text-xl font-bold text-gray-900 dark:text-white truncate">
                    {name}
                  </div>
                  <div className="text-sm text-gray-600 dark:text-gray-400 truncate">
                    Manage topologies for this project
                  </div>
                </div>
                <button
                  onClick={() => setManageOpen(false)}
                  className="p-2 rounded-xl text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800"
                  aria-label="Close"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="mt-5 flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="relative flex-1">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search by name or ID…"
                    className="w-full pl-9 pr-3 py-2 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => void refetchTopologies()}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-2xl text-sm font-semibold text-gray-700 dark:text-gray-200 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700"
                  >
                    <RefreshCw size={16} />
                    Refresh
                  </button>
                  <button
                    onClick={() => void handleCreateTopology()}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-2xl text-sm font-semibold text-white bg-indigo-600 hover:bg-indigo-700"
                  >
                    <Plus size={16} />
                    New
                  </button>
                </div>
              </div>
            </div>

            <div className="p-6">
              <div className="flex items-center justify-between text-sm">
                <div className="font-semibold text-gray-900 dark:text-white">
                  {topologiesLoading ? 'Loading…' : `${filteredTopologies.length} / ${topologyCount} topologies`}
                </div>
              </div>

              <div className="mt-4 max-h-[60vh] overflow-auto pr-1 space-y-2">
                {topologiesLoading && (
                  <div className="space-y-2">
                    {[...Array(6)].map((_, idx) => (
                      <div
                        key={idx}
                        className="h-14 rounded-2xl bg-gray-100 dark:bg-gray-800 animate-pulse"
                      />
                    ))}
                  </div>
                )}

                {!topologiesLoading && filteredTopologies.length === 0 && (
                  <div className="text-sm text-gray-600 dark:text-gray-400">
                    No topologies found.
                  </div>
                )}

                {!topologiesLoading &&
                  filteredTopologies.map((topology: Topology & any) => {
                    const topoStatus = String(topology?.emulation_status || topology?.status || '').toLowerCase()
                    const topoActive = Boolean(topology?.is_active || topoStatus === 'running')
                    return (
                      <div
                        key={topology.id}
                        className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950/40 hover:bg-indigo-50/30 dark:hover:bg-indigo-950/20 transition-colors"
                      >
                        <div className="flex items-center justify-between gap-3 px-4 py-3">
                          <button
                            onClick={() => navigate(`/topology/${topology.id}`)}
                            className="min-w-0 flex-1 text-left"
                          >
                            <div className="flex items-center gap-3">
                              <div className="min-w-0">
                                <div className="text-sm font-semibold text-gray-900 dark:text-white truncate">
                                  {topology.name}
                                </div>
                                <div className="text-xs text-gray-500 dark:text-gray-500 truncate">
                                  {topology.id}
                                </div>
                              </div>
                            </div>
                          </button>

                          <div className="flex items-center gap-2">
                            <span
                              className={
                                topoActive
                                  ? 'px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-300'
                                  : 'px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300'
                              }
                            >
                              {topoStatus || 'stopped'}
                            </span>
                            <button
                              onClick={() => void handleDeleteTopology(topology.id)}
                              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-red-600 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-950/20"
                              aria-label="Delete topology"
                            >
                              <Trash2 size={14} />
                              Delete
                            </button>
                          </div>
                        </div>
                      </div>
                    )
                  })}
              </div>
            </div>
          </div>
        </div>
      )}

      {(onEdit || onDelete) && (
        <div className="px-6 py-3 bg-gray-50 dark:bg-gray-800/40 border-t border-gray-100 dark:border-gray-800">
          <div className="flex items-center justify-end gap-2">
            {onEdit && (
              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  onEdit(id)
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg"
              >
                <Edit size={14} />
                {t('common.edit')}
              </button>
            )}
            {onDelete && (
              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  onDelete(id)
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-red-600 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-950/20 rounded-lg"
              >
                <Trash2 size={14} />
                {t('common.delete')}
              </button>
            )}
          </div>
        </div>
      )}
    </ModernCard>
  )
}
