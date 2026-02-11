import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { projectsAPI } from '@/services/api'
import { ProjectList } from '../components/ProjectList'
import { CreateProjectModal } from '../components/CreateProjectModal'
import { ImportTopologyModal } from '../components/ImportTopologyModal'
import { Button } from '@/components/atoms/Button'
import { FolderPlus, Upload } from 'lucide-react'

export const ProjectsPage: React.FC = () => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showImportModal, setShowImportModal] = useState(false)
  const queryClient = useQueryClient()

  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const response = await projectsAPI.list()
      return response.data
    },
  })

  const deleteMutation = useMutation({
    mutationFn: projectsAPI.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })

  const handleDelete = (id: string) => {
    if (confirm(t('projects.confirmDelete'))) {
      deleteMutation.mutate(id)
    }
  }

  // Transform API data to component props
  const projectCards = projects?.map((project: any) => ({
    id: project.id,
    name: project.name,
    description: project.description,
    createdAt: project.created_at,
    status: 'inactive' as const,
  })) || []

  return (
    <div className="min-h-screen pb-20 md:pb-8">
      <div className="container-custom py-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div className="space-y-1">
            <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
              {t('projects.title')}
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              {t('projects.subtitle')}
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto">
            <Button
              variant="secondary"
              size="lg"
              leftIcon={<Upload size={20} />}
              onClick={() => setShowImportModal(true)}
              className="w-full sm:w-auto"
              disabled={!projects || projects.length === 0}
            >
              Import Topology
            </Button>
            <Button
              variant="primary"
              size="lg"
              leftIcon={<FolderPlus size={20} />}
              onClick={() => setShowCreateModal(true)}
              className="w-full sm:w-auto"
            >
              {t('projects.create')}
            </Button>
          </div>
        </div>

        {/* Project List */}
        <ProjectList
          projects={projectCards}
          isLoading={isLoading}
          onCreateNew={() => setShowCreateModal(true)}
          onDelete={handleDelete}
        />

        {/* Import Modal */}
        {showImportModal && (
          <ImportTopologyModal
            isOpen={showImportModal}
            onClose={() => setShowImportModal(false)}
            projects={(projects || []).map((p: any) => ({ id: p.id, name: p.name }))}
            onImported={(topologyId) => navigate(`/topology/${topologyId}`)}
          />
        )}

        {/* Create Modal */}
        {showCreateModal && (
          <CreateProjectModal
            isOpen={showCreateModal}
            onClose={() => setShowCreateModal(false)}
          />
        )}
      </div>
    </div>
  )
}
