import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import {
  DocumentTextIcon,
  ServerIcon,
  MagnifyingGlassIcon,
  ArrowTopRightOnSquareIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline'
import { ModernCard } from '@components/ModernCard'
import { ModernButton } from '@components/ModernButton'
import { ModernInput } from '@components/ModernInput'
import PromoBanner from '@/components/hostinger/PromoBanner'
import { Badge } from '@/components/atoms/Badge/Badge'
import api from '@services/api'

interface Service {
  name: string
  url: string
  port: number
  status: 'healthy' | 'unhealthy' | 'unknown'
}

interface ServiceListResponse {
  count: number
  services: Service[]
}

export default function ApiDocs() {
  const { t } = useTranslation()
  const [searchTerm, setSearchTerm] = useState('')

  const { data: servicesData, isLoading, refetch } = useQuery<ServiceListResponse>({
    queryKey: ['api-services'],
    queryFn: async () => {
      const response = await api.get<ServiceListResponse>('/services')
      return response.data
    },
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  const services = servicesData?.services || []

  // Filter services based on search term
  const filteredServices = services.filter(service =>
    service.name.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'healthy':
        return (
          <Badge variant="success" withIcon size="sm">
            {t('apiDocs.running')}
          </Badge>
        )
      case 'unhealthy':
        return (
          <Badge variant="error" withIcon size="sm">
            {t('apiDocs.stopped')}
          </Badge>
        )
      default:
        return (
          <Badge variant="warning" withIcon size="sm">
            {t('apiDocs.unknown')}
          </Badge>
        )
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
        return <CheckCircleIcon className="h-6 w-6 text-green-600 dark:text-green-400" />
      case 'unhealthy':
        return <XCircleIcon className="h-6 w-6 text-red-600 dark:text-red-400" />
      default:
        return <ExclamationTriangleIcon className="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
    }
  }

  const healthyCount = services.filter(s => s.status === 'healthy').length
  const unhealthyCount = services.filter(s => s.status === 'unhealthy').length

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50 dark:bg-gray-900">
        <div className="text-gray-900 dark:text-white text-xl">{t('common.loading')}</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-gray-950 transition-colors duration-200 pb-20 md:pb-8">
      <div className="max-w-[1920px] mx-auto px-6 sm:px-8 lg:px-12 py-8">
        <PromoBanner
          subtitle={t('apiDocs.subtitle')}
          title={t('apiDocs.title')}
          rightSlot={
            <ModernButton
              variant="secondary"
              size="sm"
              onClick={() => refetch()}
            >
              {t('common.refresh')}
            </ModernButton>
          }
        />

        {/* Stats Banner */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8 mt-6">
          <ModernCard padding="lg" hover={false}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">{t('apiDocs.totalServices')}</p>
                <p className="text-3xl font-bold text-gray-900 dark:text-white mt-1">
                  {services.length}
                </p>
              </div>
              <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
                <ServerIcon className="h-8 w-8 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
          </ModernCard>

          <ModernCard padding="lg" hover={false}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">{t('apiDocs.running')}</p>
                <p className="text-3xl font-bold text-green-600 dark:text-green-400 mt-1">
                  {healthyCount}
                </p>
              </div>
              <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-xl">
                <CheckCircleIcon className="h-8 w-8 text-green-600 dark:text-green-400" />
              </div>
            </div>
          </ModernCard>

          <ModernCard padding="lg" hover={false}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-600 dark:text-gray-400">{t('apiDocs.stopped')}</p>
                <p className="text-3xl font-bold text-red-600 dark:text-red-400 mt-1">
                  {unhealthyCount}
                </p>
              </div>
              <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-xl">
                <XCircleIcon className="h-8 w-8 text-red-600 dark:text-red-400" />
              </div>
            </div>
          </ModernCard>
        </div>

        {/* Search Bar */}
        <div className="mb-8">
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-4 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder={t('apiDocs.searchPlaceholder')}
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-12 pr-4 py-3 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
            />
          </div>
        </div>

        {/* Services Grid */}
        {filteredServices.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredServices.map((service) => (
              <ModernCard
                key={service.name}
                padding="lg"
                hover={false}
                className="relative"
              >
                {/* Status indicator dot */}
                <div className="absolute top-4 right-4">
                  {getStatusIcon(service.status)}
                </div>

                <div className="mb-4">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex-1">
                      <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                        {service.name}
                      </h3>
                      <div className="mb-3">
                        {getStatusBadge(service.status)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 mb-4">
                    <span className="px-3 py-1 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 text-xs font-mono rounded-full">
                      :{service.port}
                    </span>
                  </div>

                  <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 font-mono break-all">
                    {service.url}
                  </p>
                </div>

                {/* Documentation Links */}
                <div className="space-y-2 pt-4 border-t border-gray-200 dark:border-gray-800">
                  <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide mb-3">
                    {t('apiDocs.documentation')}
                  </p>

                  <a
                    href={`/api/docs/${service.name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between px-3 py-2 bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/30 rounded-lg transition-colors group"
                  >
                    <span className="text-sm font-medium text-blue-700 dark:text-blue-400">
                      {t('apiDocs.swaggerUI')}
                    </span>
                    <ArrowTopRightOnSquareIcon className="h-4 w-4 text-blue-600 dark:text-blue-400 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                  </a>

                  <a
                    href={`/api/redoc/${service.name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between px-3 py-2 bg-purple-50 dark:bg-purple-900/20 hover:bg-purple-100 dark:hover:bg-purple-900/30 rounded-lg transition-colors group"
                  >
                    <span className="text-sm font-medium text-purple-700 dark:text-purple-400">
                      {t('apiDocs.redoc')}
                    </span>
                    <ArrowTopRightOnSquareIcon className="h-4 w-4 text-purple-600 dark:text-purple-400 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                  </a>

                  <a
                    href={`/api/openapi/${service.name}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors group"
                  >
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300 font-mono">
                      {t('apiDocs.openapiJson')}
                    </span>
                    <ArrowTopRightOnSquareIcon className="h-4 w-4 text-gray-600 dark:text-gray-400 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-transform" />
                  </a>
                </div>
              </ModernCard>
            ))}
          </div>
        ) : (
          <ModernCard padding="lg" hover={false}>
            <div className="text-center py-12">
              <DocumentTextIcon className="h-16 w-16 text-gray-400 dark:text-gray-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                {t('apiDocs.noServicesFound')}
              </h3>
              <p className="text-gray-600 dark:text-gray-400">
                {searchTerm
                  ? `${t('apiDocs.noServicesMatch')} "${searchTerm}"`
                  : t('apiDocs.noServicesAvailable')}
              </p>
            </div>
          </ModernCard>
        )}

        {/* Footer Info */}
        <div className="mt-8">
          <ModernCard padding="lg" hover={false}>
            <div className="flex items-start gap-4">
              <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-xl">
                <DocumentTextIcon className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <h4 className="font-semibold text-gray-900 dark:text-white mb-2">
                  {t('apiDocs.aboutTitle')}
                </h4>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
                  {t('apiDocs.aboutDescription')}
                </p>
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  <strong className="text-gray-900 dark:text-white">{t('apiDocs.tip')}</strong> {t('apiDocs.tipDescription')}
                </p>
              </div>
            </div>
          </ModernCard>
        </div>
      </div>
    </div>
  )
}
