import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { ModernCard } from '@components/ModernCard'
import { ModernInput } from '@components/ModernInput'
import { ModernButton } from '@components/ModernButton'

export default function HostConfigPanel() {
  const { t } = useTranslation()
  const [config, setConfig] = useState({
    hostname: 'h1',
    ipAddress: '10.0.0.1',
    netmask: '255.255.255.0',
    gateway: '10.0.0.254',
    dns: '8.8.8.8',
  })

  return (
    <div className="space-y-6">
      <ModernCard padding="lg">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
          {t('host.configuration')}
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <ModernInput
            label={t('host.hostname')}
            value={config.hostname}
            onChange={(e) => setConfig({ ...config, hostname: e.target.value })}
            placeholder="h1"
          />
          <ModernInput
            label={t('host.ipAddress')}
            value={config.ipAddress}
            onChange={(e) => setConfig({ ...config, ipAddress: e.target.value })}
            placeholder="10.0.0.1"
          />
          <ModernInput
            label={t('host.netmask')}
            value={config.netmask}
            onChange={(e) => setConfig({ ...config, netmask: e.target.value })}
            placeholder="255.255.255.0"
          />
          <ModernInput
            label={t('host.gateway')}
            value={config.gateway}
            onChange={(e) => setConfig({ ...config, gateway: e.target.value })}
            placeholder="10.0.0.254"
          />
          <ModernInput
            label={t('host.dns')}
            value={config.dns}
            onChange={(e) => setConfig({ ...config, dns: e.target.value })}
            placeholder="8.8.8.8"
          />
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <ModernButton variant="secondary">{t('common.reset')}</ModernButton>
          <ModernButton variant="primary">{t('common.apply')}</ModernButton>
        </div>
      </ModernCard>

      <ModernCard padding="lg">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          {t('host.services')}
        </h3>
        <div className="space-y-2">
          {['HTTP Server', 'SSH Server', 'FTP Server'].map((service) => (
            <label key={service} className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer">
              <input type="checkbox" className="w-4 h-4 text-blue-600 rounded" />
              <span className="text-gray-900 dark:text-white">{service}</span>
            </label>
          ))}
        </div>
      </ModernCard>
    </div>
  )
}

