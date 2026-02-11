import { useTranslation } from 'react-i18next'
import { ModernCard } from '@components/ModernCard'
import { ModernButton } from '@components/ModernButton'
import { StatusBadge } from '@components/StatusBadge'

export default function SwitchConfigPanel() {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      <ModernCard padding="lg">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t('switch.configuration')}
          </h2>
          <StatusBadge status="running" label="OpenFlow 1.3" />
        </div>

        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {t('switch.dpid')}
              </label>
              <p className="mt-1 text-lg font-mono text-gray-900 dark:text-white">
                0000000000000001
              </p>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {t('switch.controller')}
              </label>
              <p className="mt-1 text-lg text-gray-900 dark:text-white">
                tcp:127.0.0.1:6653
              </p>
            </div>
          </div>
        </div>
      </ModernCard>

      <ModernCard padding="lg">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {t('switch.flowTable')}
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 dark:bg-gray-700">
              <tr>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700 dark:text-gray-300">Priority</th>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700 dark:text-gray-300">Match</th>
                <th className="px-4 py-2 text-left text-sm font-medium text-gray-700 dark:text-gray-300">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
              <tr className="hover:bg-gray-50 dark:hover:bg-gray-700">
                <td className="px-4 py-2 text-sm text-gray-900 dark:text-white">100</td>
                <td className="px-4 py-2 text-sm font-mono text-gray-600 dark:text-gray-400">ip,nw_dst=10.0.0.1</td>
                <td className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400">output:1</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div className="mt-4 flex justify-end">
          <ModernButton variant="primary">{t('switch.addFlow')}</ModernButton>
        </div>
      </ModernCard>
    </div>
  )
}

