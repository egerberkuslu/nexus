import { useTranslation } from 'react-i18next'
import { ServerIcon, CpuChipIcon, WifiIcon } from '@heroicons/react/24/outline'
import { ModernCard } from '@components/ModernCard'
import { MetricCard } from '@components/MetricCard'
import { StatusBadge } from '@components/StatusBadge'
import { Activity, Network } from 'lucide-react'

interface OverviewDashboardProps {
  networkRunning: boolean
}

export default function OverviewDashboard({ networkRunning }: OverviewDashboardProps) {
  const { t } = useTranslation()

  const mockNodes = [
    { id: 'h1', type: 'host', name: 'Host 1', ip: '10.0.0.1', status: 'online' },
    { id: 'h2', type: 'host', name: 'Host 2', ip: '10.0.0.2', status: 'online' },
    { id: 's1', type: 'switch', name: 'Switch 1', ip: '10.0.1.1', status: 'online' },
    { id: 'r1', type: 'router', name: 'Router 1', ip: '10.0.2.1', status: 'online' },
    { id: 'c1', type: 'controller', name: 'Controller 1', ip: '127.0.0.1:6653', status: 'running' },
  ]

  const getNodeIcon = (type: string) => {
    switch (type) {
      case 'host':
        return <ServerIcon className="h-6 w-6" />
      case 'switch':
        return <CpuChipIcon className="h-6 w-6" />
      case 'router':
        return <CpuChipIcon className="h-6 w-6" />
      case 'controller':
        return <Network className="h-6 w-6" />
      default:
        return <WifiIcon className="h-6 w-6" />
    }
  }

  const getNodeColor = (type: string) => {
    switch (type) {
      case 'host':
        return 'blue'
      case 'switch':
        return 'green'
      case 'router':
        return 'purple'
      case 'controller':
        return 'indigo'
      default:
        return 'gray'
    }
  }

  return (
    <div className="space-y-6">
      {/* Network Health Panel */}
      <ModernCard padding="lg">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
          {t('network.health')}
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <MetricCard
            icon={<ServerIcon className="h-5 w-5" />}
            label={t('nodes.hosts')}
            value={mockNodes.filter(n => n.type === 'host').length}
            color="blue"
            subtitle={t('status.allOnline')}
          />
          <MetricCard
            icon={<CpuChipIcon className="h-5 w-5" />}
            label={t('nodes.switches')}
            value={mockNodes.filter(n => n.type === 'switch').length}
            color="green"
            subtitle={t('status.allOperational')}
          />
          <MetricCard
            icon={<CpuChipIcon className="h-5 w-5" />}
            label={t('nodes.routers')}
            value={mockNodes.filter(n => n.type === 'router').length}
            color="purple"
            subtitle={t('status.allActive')}
          />
          <MetricCard
            icon={<Network className="h-5 w-5" />}
            label={t('nodes.controllers')}
            value={mockNodes.filter(n => n.type === 'controller').length}
            color="indigo"
            subtitle={networkRunning ? t('status.running') : t('status.stopped')}
          />
        </div>

        <div className="mt-4 flex items-center gap-4">
          <StatusBadge
            status={networkRunning ? 'success' : 'stopped'}
            label={networkRunning ? t('network.running') : t('network.stopped')}
          />
          {networkRunning && (
            <>
              <StatusBadge status="success" label={t('controller.active')} />
              <StatusBadge status="success" label={t('status.healthy')} />
            </>
          )}
        </div>
      </ModernCard>

      {/* Node Grid */}
      <div>
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
          {t('network.nodes')}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {mockNodes.map((node) => (
            <ModernCard
              key={node.id}
              padding="md"
              hover={true}
              className="cursor-pointer"
            >
              <div className="flex items-start gap-3">
                <div className={`p-2 bg-${getNodeColor(node.type)}-100 dark:bg-${getNodeColor(node.type)}-900/30 rounded-lg`}>
                  {getNodeIcon(node.type)}
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                    {node.name}
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {node.id} • {node.ip}
                  </p>
                  <div className="mt-2">
                    <StatusBadge
                      status={node.status === 'online' || node.status === 'running' ? 'success' : 'error'}
                      label={node.status}
                      size="sm"
                    />
                  </div>
                </div>
              </div>
            </ModernCard>
          ))}
        </div>
      </div>

      {/* Quick Actions */}
      <ModernCard padding="lg">
        <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
          {t('common.quickActions')}
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button className="p-4 border-2 border-gray-200 dark:border-gray-700 rounded-xl hover:border-blue-500 dark:hover:border-blue-400 hover:bg-blue-50 dark:hover:bg-blue-900/10 transition-all">
            <Activity className="h-8 w-8 mx-auto mb-2 text-blue-600 dark:text-blue-400" />
            <p className="text-sm font-medium text-gray-900 dark:text-white">{t('actions.pingAll')}</p>
          </button>
          <button className="p-4 border-2 border-gray-200 dark:border-gray-700 rounded-xl hover:border-green-500 dark:hover:border-green-400 hover:bg-green-50 dark:hover:bg-green-900/10 transition-all">
            <Network className="h-8 w-8 mx-auto mb-2 text-green-600 dark:text-green-400" />
            <p className="text-sm font-medium text-gray-900 dark:text-white">{t('actions.checkTopology')}</p>
          </button>
          <button className="p-4 border-2 border-gray-200 dark:border-gray-700 rounded-xl hover:border-purple-500 dark:hover:border-purple-400 hover:bg-purple-50 dark:hover:bg-purple-900/10 transition-all">
            <ServerIcon className="h-8 w-8 mx-auto mb-2 text-purple-600 dark:text-purple-400" />
            <p className="text-sm font-medium text-gray-900 dark:text-white">{t('actions.addHost')}</p>
          </button>
          <button className="p-4 border-2 border-gray-200 dark:border-gray-700 rounded-xl hover:border-indigo-500 dark:hover:border-indigo-400 hover:bg-indigo-50 dark:hover:bg-indigo-900/10 transition-all">
            <CpuChipIcon className="h-8 w-8 mx-auto mb-2 text-indigo-600 dark:text-indigo-400" />
            <p className="text-sm font-medium text-gray-900 dark:text-white">{t('actions.configureRouter')}</p>
          </button>
        </div>
      </ModernCard>
    </div>
  )
}

