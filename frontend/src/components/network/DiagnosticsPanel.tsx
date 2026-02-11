import { useTranslation } from 'react-i18next'
import { ModernCard } from '@components/ModernCard'
import { ModernButton } from '@components/ModernButton'
import { StatusBadge } from '@components/StatusBadge'
import { CheckCircleIcon, XCircleIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline'

export default function DiagnosticsPanel() {
  const { t } = useTranslation()

  const diagnostics = [
    { id: 1, component: 'Router r1', status: 'healthy', message: 'All interfaces operational' },
    { id: 2, component: 'Switch s1', status: 'warning', message: 'High packet drop rate' },
    { id: 3, component: 'Controller', status: 'healthy', message: 'Connected to all switches' },
    { id: 4, component: 'Host h1', status: 'error', message: 'Network unreachable' },
  ]

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircleIcon className="h-5 w-5 text-green-600 dark:text-green-400" />
      case 'warning':
        return <ExclamationTriangleIcon className="h-5 w-5 text-yellow-600 dark:text-yellow-400" />
      case 'error':
        return <XCircleIcon className="h-5 w-5 text-red-600 dark:text-red-400" />
      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      <ModernCard padding="lg">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t('diagnostics.title')}
          </h2>
          <StatusBadge status="warning" label="2 Issues Found" />
        </div>

        <div className="space-y-3">
          {diagnostics.map((item) => (
            <div
              key={item.id}
              className="flex items-start gap-4 p-4 bg-gray-50 dark:bg-gray-700 rounded-lg"
            >
              {getStatusIcon(item.status)}
              <div className="flex-1">
                <h4 className="font-medium text-gray-900 dark:text-white">{item.component}</h4>
                <p className="text-sm text-gray-600 dark:text-gray-400">{item.message}</p>
              </div>
              {item.status === 'error' && (
                <ModernButton variant="primary" size="sm">
                  {t('diagnostics.autoFix')}
                </ModernButton>
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 flex gap-3">
          <ModernButton variant="primary">{t('diagnostics.runFullScan')}</ModernButton>
          <ModernButton variant="secondary">{t('diagnostics.exportReport')}</ModernButton>
        </div>
      </ModernCard>

      <ModernCard padding="lg">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {t('diagnostics.recommendations')}
        </h3>
        <ul className="space-y-2">
          <li className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
            <span className="text-blue-600 dark:text-blue-400">•</span>
            Reconfigure router r1 interfaces for optimal routing
          </li>
          <li className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
            <span className="text-blue-600 dark:text-blue-400">•</span>
            Check switch s1 flow table for conflicting rules
          </li>
          <li className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
            <span className="text-blue-600 dark:text-blue-400">•</span>
            Verify host h1 network configuration
          </li>
        </ul>
      </ModernCard>
    </div>
  )
}

