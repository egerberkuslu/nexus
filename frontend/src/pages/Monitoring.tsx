import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import MonitoringCharts from '@components/MonitoringCharts'
import { monitoringAPI, devicesAPI, emulationAPI } from '@services/api'
import { ChartBarIcon, CpuChipIcon, SignalIcon } from '@heroicons/react/24/outline'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/atoms/Card'
import { MetricCard } from '@/components/molecules/MetricCard'
import { Badge } from '@/components/atoms/Badge'

export default function Monitoring() {
  const { t } = useTranslation()
  const { id } = useParams()
  const [selectedDevice, setSelectedDevice] = useState<string | null>(null)
  const [timeRange, setTimeRange] = useState<'1h' | '6h' | '24h' | '7d'>('1h')

  // Fetch topology metrics
  const { data: topologyMetrics } = useQuery({
    queryKey: ['topology-metrics', id],
    queryFn: async () => {
      if (!id) return null
      const response = await monitoringAPI.topologyMetrics(id)
      return response.data
    },
    enabled: !!id,
    refetchInterval: 10000,
  })

  // Fetch devices list
  const { data: devices } = useQuery({
    queryKey: ['devices'],
    queryFn: async () => {
      const response = await devicesAPI.list()
      return response.data
    },
    refetchInterval: 15000,
  })

  // Fetch emulation status
  const { data: emulationStatus } = useQuery({
    queryKey: ['emulation-status', id],
    queryFn: async () => {
      if (!id) return null
      try {
        const response = await emulationAPI.status(id)
        return response.data
      } catch (error) {
        // If emulation status fails (no emulation running), return null
        return null
      }
    },
    enabled: !!id,
    refetchInterval: 5000,
    retry: false, // Don't retry on error
  })

  const isRunning = emulationStatus?.status === 'running'

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 pb-20 md:pb-8">
      <div className="container-custom py-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
          <div>
            <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white">
              {t('monitoring.title')}
            </h1>
            <p className="mt-1 text-gray-600 dark:text-gray-400">
              {t('monitoring.realtime')} monitoring and analytics
            </p>
          </div>
          
          <div className="flex items-center gap-2">
            <Badge variant={isRunning ? 'success' : 'default'} withIcon>
              {isRunning ? t('status.running') : t('status.stopped')}
            </Badge>
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title={t('monitoring.bandwidth')}
            value={topologyMetrics?.bandwidth || '0 Mbps'}
            icon={<SignalIcon className="w-5 h-5" />}
            variant="primary"
            trend={topologyMetrics?.bandwidthTrend}
          />
          <MetricCard
            title={t('monitoring.latency')}
            value={topologyMetrics?.latency || '0 ms'}
            icon={<ChartBarIcon className="w-5 h-5" />}
            variant="success"
            trend={topologyMetrics?.latencyTrend}
          />
          <MetricCard
            title={t('monitoring.packets')}
            value={topologyMetrics?.packets || '0'}
            icon={<CpuChipIcon className="w-5 h-5" />}
            variant="warning"
          />
          <MetricCard
            title={t('common.refresh')}
            value={`${timeRange}`}
            icon={<ChartBarIcon className="w-5 h-5" />}
            variant="default"
          />
        </div>

        {/* Time Range Selector */}
        <div className="flex items-center gap-2 mb-6">
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
            {t('monitoring.refresh')}:
          </span>
          <div className="flex bg-gray-100 dark:bg-gray-800 rounded-full p-1">
            {(['1h', '6h', '24h', '7d'] as const).map((range) => (
              <button
                key={range}
                onClick={() => setTimeRange(range)}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
                  timeRange === range
                    ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-600 dark:text-gray-400'
                }`}
              >
                {range}
              </button>
            ))}
          </div>
        </div>

        {/* Monitoring Charts */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t('monitoring.charts.bandwidth')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <MonitoringCharts
                  topologyId={id || ''}
                  device={selectedDevice || undefined}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('monitoring.charts.latency')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
                {t('monitoring.charts.latency')} chart will appear here
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('monitoring.charts.throughput')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64 flex items-center justify-center text-gray-500 dark:text-gray-400">
                {t('monitoring.charts.throughput')} chart will appear here
              </div>
            </CardContent>
          </Card>

          {/* Device List */}
          {devices && devices.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t('nodes.hosts')}</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                  {devices.map((device: any) => (
                    <button
                      key={device.name}
                      onClick={() => setSelectedDevice(device.name)}
                      className={`p-4 rounded-xl border-2 transition-all text-left ${
                        selectedDevice === device.name
                          ? 'border-blue-600 dark:border-blue-400 bg-blue-50 dark:bg-blue-950/20'
                          : 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'
                      }`}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-semibold text-gray-900 dark:text-white">
                          {device.name}
                        </span>
                        <Badge variant="success" size="sm">
                          {t('status.running')}
                        </Badge>
                      </div>
                      <p className="text-xs text-gray-600 dark:text-gray-400 font-mono">
                        {device.ip || 'N/A'}
                      </p>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
