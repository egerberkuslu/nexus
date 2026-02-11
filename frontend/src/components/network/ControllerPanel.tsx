import { useTranslation } from 'react-i18next'
import { ModernCard } from '@components/ModernCard'
import { StatusBadge } from '@components/StatusBadge'
import { MetricCard } from '@components/MetricCard'
import { Cpu, HardDrive, Activity } from 'lucide-react'

export default function ControllerPanel() {
  const { t } = useTranslation()

  return (
    <div className="space-y-6">
      <ModernCard padding="lg">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          {t('controller.status')}
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <MetricCard
            icon={<Activity className="h-5 w-5" />}
            label={t('controller.type')}
            value="Ryu"
            color="blue"
            subtitle="OpenFlow 1.3"
          />
          <MetricCard
            icon={<Cpu className="h-5 w-5" />}
            label={t('controller.cpu')}
            value="12%"
            color="green"
            subtitle="Low usage"
          />
          <MetricCard
            icon={<HardDrive className="h-5 w-5" />}
            label={t('controller.memory')}
            value="256 MB"
            color="purple"
            subtitle="Normal"
          />
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <span className="font-medium text-gray-900 dark:text-white">{t('controller.pid')}</span>
            <span className="text-gray-600 dark:text-gray-400">12345</span>
          </div>
          <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <span className="font-medium text-gray-900 dark:text-white">{t('controller.port')}</span>
            <span className="text-gray-600 dark:text-gray-400">6653</span>
          </div>
          <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
            <span className="font-medium text-gray-900 dark:text-white">{t('controller.uptime')}</span>
            <span className="text-gray-600 dark:text-gray-400">2h 34m</span>
          </div>
        </div>
      </ModernCard>

      <ModernCard padding="lg">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {t('controller.logs')}
        </h3>
        <div className="bg-black dark:bg-gray-950 rounded-lg p-4 font-mono text-sm text-green-400 h-64 overflow-y-auto">
          <div>[INFO] Controller started on port 6653</div>
          <div>[INFO] Switch 0000000000000001 connected</div>
          <div>[INFO] Flow table updated</div>
          <div>[DEBUG] Packet-in received from switch 1</div>
        </div>
      </ModernCard>
    </div>
  )
}

