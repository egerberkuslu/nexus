import { useTranslation } from 'react-i18next'
import { ProjectCard, ProjectCardProps } from './ProjectCard'
import { ModernCard } from '@/components/ModernCard'
import { ModernButton } from '@/components/ModernButton'
import { FolderPlus } from 'lucide-react'

export interface ProjectListProps {
  projects: ProjectCardProps[]
  isLoading?: boolean
  onCreateNew?: () => void
  onDelete?: (id: string) => void
  onEdit?: (id: string) => void
}

export const ProjectList: React.FC<ProjectListProps> = ({
  projects,
  isLoading = false,
  onCreateNew,
  onDelete,
  onEdit,
}) => {
  const { t } = useTranslation()

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[...Array(6)].map((_, i) => (
          <ModernCard key={i} hover={false}>
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-gray-200 dark:bg-gray-700 rounded-xl"></div>
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
                  <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
                </div>
              </div>
            </div>
          </ModernCard>
        ))}
      </div>
    )
  }

  if (projects.length === 0) {
    return (
      <ModernCard hover={false}>
        <div className="text-center py-12">
          <div className="inline-flex p-4 bg-gray-100 dark:bg-gray-800 rounded-full mb-4">
            <FolderPlus className="h-12 w-12 text-gray-400 dark:text-gray-600" />
          </div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
            {t('projects.noProjects')}
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            {t('projects.createFirst')}
          </p>
          {onCreateNew && (
            <ModernButton icon={<FolderPlus size={20} />} onClick={onCreateNew}>
              {t('projects.create')}
            </ModernButton>
          )}
        </div>
      </ModernCard>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {projects.map((project) => (
        <ProjectCard
          key={project.id}
          {...project}
          onDelete={onDelete}
          onEdit={onEdit}
        />
      ))}
    </div>
  )
}
