import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ModernCard } from '@components/ModernCard'
import { ModernButton } from '@components/ModernButton'
import { StatusBadge } from '@components/StatusBadge'

export default function RouterConfigPanel() {
  const { t } = useTranslation()
  const [selectedProtocol, setSelectedProtocol] = useState<string>('static')

  return (
    <div className="space-y-6">
      <ModernCard padding="lg">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          {t('router.configuration')}
        </h2>

        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              {t('router.interfaces')}
            </h3>
            <div className="space-y-3">
              {['eth0', 'eth1', 'eth2'].map((iface) => (
                <div key={iface} className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">{iface}</p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">192.168.1.1/24</p>
                  </div>
                  <StatusBadge status="success" label="UP" />
                </div>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              {t('router.protocols')}
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {['static', 'rip', 'ospf', 'bgp'].map((protocol) => (
                <button
                  key={protocol}
                  onClick={() => setSelectedProtocol(protocol)}
                  className={`p-4 rounded-lg border-2 transition-all ${
                    selectedProtocol === protocol
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  }`}
                >
                  <p className="font-medium text-gray-900 dark:text-white uppercase">{protocol}</p>
                </button>
              ))}
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-3">
              {t('router.frrIntegration')}
            </h3>
            <div className="space-y-3">
              <ModernButton variant="primary" fullWidth>{t('router.prepareDaemons')}</ModernButton>
              <ModernButton variant="success" fullWidth>{t('router.startRouting')}</ModernButton>
              <ModernButton variant="secondary" fullWidth>{t('router.viewLogs')}</ModernButton>
            </div>
          </div>
        </div>
      </ModernCard>
    </div>
  )
}

