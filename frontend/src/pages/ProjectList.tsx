import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'
import { PlusIcon, FolderIcon, ArrowUpTrayIcon, PlayIcon } from '@heroicons/react/24/outline'
import { emulationAPI, projectsAPI, topologiesAPI } from '@services/api'
import { ModernCard } from '@components/ModernCard'
import { ModernButton } from '@components/ModernButton'
import { ModernInput } from '@components/ModernInput'
import PromoBanner from '@/components/hostinger/PromoBanner'
import toast from 'react-hot-toast'

export default function ProjectList() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showImportModal, setShowImportModal] = useState(false)
  const [newProject, setNewProject] = useState({ name: '', description: '' })
  const [importProjectId, setImportProjectId] = useState<string>('')
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importStartAfter, setImportStartAfter] = useState<boolean>(false)
  const [importOverwriteEnabled, setImportOverwriteEnabled] = useState<boolean>(false)
  const [importTargetTopologyId, setImportTargetTopologyId] = useState<string>('')
  const [importTokenOverride, setImportTokenOverride] = useState<string>('')
  const queryClient = useQueryClient()

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await projectsAPI.list()
      return response.data
    },
  })

  const { data: importTopologies, isLoading: importTopologiesLoading } = useQuery({
    queryKey: ['import-topologies', importProjectId],
    queryFn: async () => {
      const res = await topologiesAPI.list(importProjectId)
      return res.data || []
    },
    enabled: showImportModal && !!importProjectId,
    staleTime: 0,
  })

  useEffect(() => {
    if (!importOverwriteEnabled) return
    if (importTargetTopologyId) return
    const first = (importTopologies || [])[0]
    if (first?.id) setImportTargetTopologyId(first.id)
  }, [importOverwriteEnabled, importTargetTopologyId, importTopologies])

  const importMutation = useMutation({
    mutationFn: async () => {
      if (!importProjectId) {
        throw new Error('Select a project')
      }
      if (!importFile) {
        throw new Error('Select a topology JSON file')
      }

      const text = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result || ''))
        reader.onerror = () => reject(new Error('Failed to read file'))
        reader.readAsText(importFile)
      })

      let parsed: any
      try {
        parsed = JSON.parse(text)
      } catch (err) {
        throw new Error('Invalid JSON file')
      }

      const token = importTokenOverride.trim()
      if (token) {
        const placeholder = 'REPLACE_ME_SHARED_P2P_TOKEN'
        const replaceDeep = (value: any): any => {
          if (typeof value === 'string') return value === placeholder ? token : value
          if (Array.isArray(value)) return value.map(replaceDeep)
          if (value && typeof value === 'object') {
            return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, replaceDeep(v)]))
          }
          return value
        }
        parsed = replaceDeep(parsed)
      }

      if (importOverwriteEnabled && importTargetTopologyId) {
        const res = await topologiesAPI.importDefinition(importProjectId, parsed, importTargetTopologyId)
        if (importStartAfter) {
          await emulationAPI.start(importTargetTopologyId, parsed?.options || {})
        }
        return { topology: res.data, started: importStartAfter }
      }

      if (importStartAfter) {
        const res = await topologiesAPI.importAndStart({ project_id: importProjectId, topology: parsed, options: {} })
        return { topology: res.data?.topology ?? res.data, started: true }
      }

      const res = await topologiesAPI.importDefinition(importProjectId, parsed)
      return { topology: res.data, started: false }
    },
    onSuccess: (data) => {
      const topologyId = data?.topology?.id
      toast.success(data.started ? 'Topology imported & started' : 'Topology imported')
      setShowImportModal(false)
      setImportFile(null)
      setImportStartAfter(false)
      setImportOverwriteEnabled(false)
      setImportTargetTopologyId('')
      setImportTokenOverride('')
      if (topologyId) {
        navigate(`/topology/${topologyId}`)
      }
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to import topology')
    },
  })

  const createMutation = useMutation({
    mutationFn: async (project: { name: string; description: string }) => {
      // Create the project (backend automatically creates a default topology)
      const projectResponse = await projectsAPI.create(project)
      const projectId = projectResponse.data.id

      // Fetch the auto-created topology
      const topologiesResponse = await topologiesAPI.list(projectId)
      const topology = topologiesResponse.data[0] // Get the first (default) topology

      return { project: projectResponse.data, topology }
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
      setShowCreateModal(false)
      setNewProject({ name: '', description: '' })
      // Navigate to the auto-created topology
      navigate(`/topology/${data.topology.id}`)
    },
  })

  const handleCreate = () => {
    createMutation.mutate(newProject)
  }

  const handleProjectClick = async (projectId: string) => {
    try {
      // Fetch existing topologies for this project
      const response = await topologiesAPI.list(projectId)
      const topologies = response.data

      if (topologies && topologies.length > 0) {
        // Navigate to the first topology
        navigate(`/topology/${topologies[0].id}`)
      } else {
        // Create a new topology for this project
        const newTopology = await topologiesAPI.create({
          project_id: projectId,
          name: 'Main Topology',
          description: 'Default topology',
          nodes: [],
          links: [],
          controllers: []
        })
        navigate(`/topology/${newTopology.data.id}`)
      }
    } catch (error) {
      console.error('Error opening project:', error)
    }
  }

  const openImportModal = () => {
    const defaultProjectId = importProjectId || projects?.[0]?.id || ''
    setImportProjectId(defaultProjectId)
    setImportOverwriteEnabled(false)
    setImportTargetTopologyId('')
    setShowImportModal(true)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900">
        <div className="text-gray-900 dark:text-white text-xl">{t('common.loading')}</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-gray-950 transition-colors duration-200 pb-20 md:pb-8">
      <div className="max-w-[1920px] mx-auto px-6 sm:px-8 lg:px-12 py-8">
        <PromoBanner subtitle="Projects" title={t('projects.title')} />
        {/* Header */}
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{t('projects.title')}</h1>
          <div className="flex items-center gap-3">
            <ModernButton
              variant="secondary"
              icon={<ArrowUpTrayIcon className="h-5 w-5" />}
              onClick={openImportModal}
            >
              Import Topology
            </ModernButton>
            <ModernButton
              variant="primary"
              icon={<PlusIcon className="h-5 w-5" />}
              onClick={() => setShowCreateModal(true)}
            >
              {t('projects.create')}
            </ModernButton>
          </div>
        </div>

        {/* Projects Grid */}
        {projects && projects.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map((project) => (
              <div
                key={project.id}
                onClick={() => handleProjectClick(project.id)}
                className="cursor-pointer transition-transform hover:scale-105"
              >
                <ModernCard padding="lg">
                  <div className="flex items-start">
                    <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-xl mr-4">
                      <FolderIcon className="h-8 w-8 text-blue-600 dark:text-blue-400" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-xl font-semibold mb-2 text-gray-900 dark:text-white">
                        {project.name}
                      </h3>
                      <p className="text-gray-600 dark:text-gray-400 text-sm mb-2">
                        {project.description}
                      </p>
                      <p className="text-gray-500 dark:text-gray-500 text-xs">
                        {t('projects.created')}: {new Date(project.created_at).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                </ModernCard>
              </div>
            ))}
          </div>
        ) : (
          <ModernCard padding="lg">
            <div className="text-center py-12">
              <FolderIcon className="h-16 w-16 text-gray-400 dark:text-gray-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                {t('projects.noProjects')}
              </h3>
              <p className="text-gray-600 dark:text-gray-400 mb-6">{t('projects.createFirst')}</p>
              <ModernButton
                variant="primary"
                icon={<PlusIcon className="h-5 w-5" />}
                onClick={() => setShowCreateModal(true)}
              >
                {t('projects.create')}
              </ModernButton>
            </div>
          </ModernCard>
        )}

        {/* Import Topology Modal */}
        {showImportModal && (
          <div className="fixed inset-0 bg-black/60 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl max-w-lg w-full shadow-2xl border border-gray-200 dark:border-gray-700">
              <h2 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">Import Topology</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Project</label>
                  <select
                    className="input-field"
                    value={importProjectId}
                    onChange={(e) => {
                      const next = e.target.value
                      setImportProjectId(next)
                      if (importOverwriteEnabled) setImportTargetTopologyId('')
                    }}
                  >
                    {(projects || []).map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Topology JSON</label>
                  <input
                    type="file"
                    accept="application/json,.json"
                    onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                    className="block w-full text-sm text-gray-600 dark:text-gray-300"
                  />
                  {importFile && (
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">Selected: {importFile.name}</div>
                  )}
                </div>

                <ModernInput
                  label="Replace LocalAI token placeholder (optional)"
                  value={importTokenOverride}
                  onChange={(e) => setImportTokenOverride(e.target.value)}
                  placeholder="Paste token to replace REPLACE_ME_SHARED_P2P_TOKEN"
                />

                <label className="flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    checked={importOverwriteEnabled}
                    onChange={(e) => {
                      const enabled = e.target.checked
                      setImportOverwriteEnabled(enabled)
                      if (enabled) {
                        const first = (importTopologies || [])[0]
                        setImportTargetTopologyId(first?.id || '')
                      } else {
                        setImportTargetTopologyId('')
                      }
                    }}
                    className="h-4 w-4"
                    disabled={importTopologiesLoading}
                  />
                  Overwrite an existing topology (keep the same topology ID)
                </label>

                {importOverwriteEnabled && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      Target topology
                    </label>
                    <select
                      className="input-field"
                      value={importTargetTopologyId}
                      onChange={(e) => setImportTargetTopologyId(e.target.value)}
                      disabled={importTopologiesLoading || (importTopologies || []).length === 0}
                    >
                      {(importTopologies || []).length === 0 ? (
                        <option value="">No topologies in this project</option>
                      ) : (
                        (importTopologies || []).map((top) => (
                          <option key={top.id} value={top.id}>
                            {top.name} ({top.id.slice(0, 8)})
                          </option>
                        ))
                      )}
                    </select>
                  </div>
                )}

                <label className="flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300">
                  <input
                    type="checkbox"
                    checked={importStartAfter}
                    onChange={(e) => setImportStartAfter(e.target.checked)}
                    className="h-4 w-4"
                  />
                  Start emulation after import
                </label>

                <div className="flex justify-end space-x-3 pt-4">
                  <ModernButton
                    variant="secondary"
                    onClick={() => {
                      setShowImportModal(false)
                      setImportFile(null)
                      setImportStartAfter(false)
                      setImportOverwriteEnabled(false)
                      setImportTargetTopologyId('')
                      setImportTokenOverride('')
                    }}
                  >
                    {t('common.cancel')}
                  </ModernButton>
                  <ModernButton
                    variant="primary"
                    icon={importStartAfter ? <PlayIcon className="h-5 w-5" /> : <ArrowUpTrayIcon className="h-5 w-5" />}
                    onClick={() => importMutation.mutate()}
                    disabled={!importProjectId || !importFile || (importOverwriteEnabled && !importTargetTopologyId)}
                    loading={importMutation.isPending}
                  >
                    {importStartAfter ? 'Import & Start' : 'Import'}
                  </ModernButton>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Create Modal */}
        {showCreateModal && (
          <div className="fixed inset-0 bg-black/60 dark:bg-black/80 backdrop-blur-sm flex items-center justify-center z-50">
            <div className="bg-white dark:bg-gray-800 p-8 rounded-2xl max-w-md w-full shadow-2xl border border-gray-200 dark:border-gray-700">
              <h2 className="text-2xl font-bold mb-6 text-gray-900 dark:text-white">
                {t('projects.create')}
              </h2>
              <div className="space-y-4">
                <ModernInput
                  label={t('projects.name')}
                  value={newProject.name}
                  onChange={(e) =>
                    setNewProject({ ...newProject, name: e.target.value })
                  }
                  placeholder={t('projects.name')}
                />
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                    {t('projects.description')}
                  </label>
                  <textarea
                    value={newProject.description}
                    onChange={(e) =>
                      setNewProject({ ...newProject, description: e.target.value })
                    }
                    rows={3}
                    className="input-field"
                    placeholder={t('projects.description')}
                  />
                </div>
                <div className="flex justify-end space-x-3 pt-4">
                  <ModernButton
                    variant="secondary"
                    onClick={() => setShowCreateModal(false)}
                  >
                    {t('common.cancel')}
                  </ModernButton>
                  <ModernButton
                    variant="primary"
                    onClick={handleCreate}
                    disabled={!newProject.name}
                    loading={createMutation.isPending}
                  >
                    {t('common.create')}
                  </ModernButton>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
