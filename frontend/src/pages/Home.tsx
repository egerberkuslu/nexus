import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import {
  PlayIcon,
  FolderPlusIcon,
  ChartBarIcon,
  CpuChipIcon,
  ServerIcon,
  CodeBracketIcon,
  ArrowRightIcon,
  SparklesIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'
import { usePlatformOverview } from '@/hooks/usePlatformOverview'

export default function Home() {
  const { t } = useTranslation()
  const { data: overview } = usePlatformOverview()
  const totals = overview?.totals

  const runningTopologyId =
    overview?.emulations.find((item) => String(item.status || '').toLowerCase() === 'running')?.topology_id ||
    overview?.topologies[0]?.id
  const monitoringLink = runningTopologyId ? `/monitoring/${runningTopologyId}` : '/network-manager'

  const features = [
    {
      icon: <CpuChipIcon className="w-7 h-7" />,
      title: t('home.features.topology'),
      description: t('home.features.topologyDesc'),
      color: 'from-blue-500 to-cyan-500',
      link: '/projects',
    },
    {
      icon: <ChartBarIcon className="w-7 h-7" />,
      title: t('home.features.monitoring'),
      description: t('home.features.monitoringDesc'),
      color: 'from-green-500 to-emerald-500',
      link: monitoringLink,
    },
    {
      icon: <ServerIcon className="w-7 h-7" />,
      title: t('home.features.controller'),
      description: t('home.features.controllerDesc'),
      color: 'from-purple-500 to-pink-500',
    },
    {
      icon: <CodeBracketIcon className="w-7 h-7" />,
      title: t('home.features.p4'),
      description: t('home.features.p4Desc'),
      color: 'from-orange-500 to-red-500',
    },
  ]

  const stats = [
    { label: 'Device Types', value: String(totals?.deviceTypes ?? 0), icon: <SparklesIcon className="w-5 h-5" /> },
    { label: 'Devices', value: String(totals?.nodes ?? 0), icon: <CpuChipIcon className="w-5 h-5" /> },
    { label: 'Controllers', value: String(totals?.controllers ?? 0), icon: <ServerIcon className="w-5 h-5" /> },
    { label: 'Services', value: String(totals?.services ?? 0), icon: <FolderPlusIcon className="w-5 h-5" /> },
  ]

  return (
    <div className="min-h-screen pb-20 md:pb-8">
      {/* Hero Section */}
      <section className="relative overflow-hidden">
        {/* Background Gradient */}
        <div className="absolute inset-0 bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-950 dark:via-gray-900 dark:to-blue-950"></div>
        
        {/* Animated Background Elements */}
        <div className="absolute inset-0 overflow-hidden opacity-20">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl animate-pulse"></div>
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl animate-pulse delay-1000"></div>
        </div>

        <div className="relative container-custom py-16 sm:py-24 lg:py-32">
          <div className="text-center space-y-8 animate-fade-in">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl border border-gray-200 dark:border-gray-800 shadow-lg">
              <ShieldCheckIcon className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                Next-Gen Network Emulation Platform
              </span>
            </div>

            {/* Heading */}
            <h1 className="heading-1 text-gray-900 dark:text-white px-4">
              {t('home.welcome')}
            </h1>

            {/* Description */}
            <p className="text-lg sm:text-xl text-gray-600 dark:text-gray-400 max-w-3xl mx-auto px-4">
              {t('home.description')}
            </p>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 px-4">
              <Link to="/projects">
                <button className="btn btn-primary w-full sm:w-auto text-base group">
                  <FolderPlusIcon className="w-5 h-5 group-hover:scale-110 transition-transform" />
                  {t('home.getStarted')}
                  <ArrowRightIcon className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                </button>
              </Link>
              <Link to={monitoringLink}>
                <button className="btn btn-secondary w-full sm:w-auto text-base">
                  <ChartBarIcon className="w-5 h-5" />
                  {runningTopologyId ? 'Open Monitoring' : t('nav.networkManager')}
                </button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section className="container-custom py-12 sm:py-16 animate-slide-up">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {stats.map((stat, index) => (
            <div
              key={index}
              className="modern-card p-6 text-center hover-lift"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-blue-100 dark:bg-blue-950 text-blue-600 dark:text-blue-400 mb-3">
                {stat.icon}
              </div>
              <div className="text-3xl sm:text-4xl font-bold text-gray-900 dark:text-white mb-1">
                {stat.value}
              </div>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {stat.label}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section className="container-custom py-12 sm:py-16">
        <div className="text-center mb-12">
          <h2 className="heading-2 text-gray-900 dark:text-white mb-4">
            {t('home.features.title')}
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
            Everything you need to build and test network topologies
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, index) => (
            <Link
              key={index}
              to={feature.link || '#'}
              className="modern-card modern-card-hover p-6 group"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className={`
                inline-flex items-center justify-center w-14 h-14 rounded-2xl
                bg-gradient-to-br ${feature.color}
                text-white mb-4 group-hover:scale-110 transition-transform duration-200
              `}>
                {feature.icon}
              </div>
              <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                {feature.title}
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                {feature.description}
              </p>
              {feature.link && (
                <div className="mt-4 flex items-center gap-2 text-sm font-medium text-blue-600 dark:text-blue-400 group-hover:gap-3 transition-all">
                  {t('common.explore')}
                  <ArrowRightIcon className="w-4 h-4" />
                </div>
              )}
            </Link>
          ))}
        </div>
      </section>

      {/* CTA Section */}
      <section className="container-custom py-12 sm:py-16">
        <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-blue-600 to-purple-600 p-8 sm:p-12 text-center text-white hover-lift">
          {/* Decorative circles */}
          <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2"></div>
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-white/10 rounded-full translate-y-1/2 -translate-x-1/2"></div>
          
          <div className="relative z-10 space-y-6">
            <h2 className="text-3xl sm:text-4xl font-bold">Ready to Start?</h2>
            <p className="text-lg text-blue-100 max-w-2xl mx-auto">
              Create your first network topology and start emulating complex scenarios
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link to="/projects">
                <button className="btn bg-white text-blue-600 hover:bg-gray-100 w-full sm:w-auto">
                  <FolderPlusIcon className="w-5 h-5" />
                  {t('projects.create')}
                </button>
              </Link>
              <Link to="/network-manager">
                <button className="btn bg-white/10 hover:bg-white/20 backdrop-blur-xl border border-white/20 w-full sm:w-auto">
                  <PlayIcon className="w-5 h-5" />
                  View Network Manager
                </button>
              </Link>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
