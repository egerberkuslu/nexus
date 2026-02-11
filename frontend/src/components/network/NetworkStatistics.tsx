import { useTranslation } from 'react-i18next'
import { ModernCard } from '@components/ModernCard'
import { MetricCard } from '@components/MetricCard'
import { Activity, TrendingUp, Zap, HardDrive } from 'lucide-react'

export default function NetworkStatistics() {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          icon={<Activity className="h-5 w-5" />}
          label={t('stats.packetsSent')}
          value="1,234,567"
          trend={5.2}
          color="blue"
        />
        <MetricCard
          icon={<TrendingUp className="h-5 w-5" />}
          label={t('stats.packetsReceived')}
          value="1,198,432"
          trend={4.8}
          color="green"
        />
        <MetricCard
          icon={<Zap className="h-5 w-5" />}
          label={t('stats.bandwidth')}
          value="85 Mbps"
          trend={-2.1}
          color="purple"
        />
        <MetricCard
          icon={<HardDrive className="h-5 w-5" />}
          label={t('stats.totalData')}
          value="2.4 GB"
          color="indigo"
        />
      </div>

      <ModernCard padding="lg">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-6">
          {t('stats.performanceMetrics')}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{t('stats.latency')}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">12.3 ms</p>
          </div>
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{t('stats.activeFlows')}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">42</p>
          </div>
          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{t('stats.interfaces')}</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">8</p>
          </div>
        </div>
      </ModernCard>

      <ModernCard padding="lg">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
          {t('stats.sdnMode')}
        </h2>
        <div className="flex items-center gap-4">
          <span className="px-4 py-2 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded-lg font-medium">
            OpenFlow
          </span>
          <span className="text-gray-600 dark:text-gray-400">Active</span>
        </div>
      </ModernCard>
    </div>
  )
}

