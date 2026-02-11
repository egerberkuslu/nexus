import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import {
  CpuChipIcon,
  ServerIcon,
  ChartBarIcon,
  CodeBracketIcon,
  CloudIcon,
  CommandLineIcon,
  CubeIcon,
  WrenchScrewdriverIcon,
  ShieldCheckIcon,
  BoltIcon,
  CircleStackIcon,
  GlobeAltIcon,
  ArrowPathIcon,
  BeakerIcon,
  CameraIcon,
  FolderArrowDownIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import { Button } from '@/components/atoms/Button'

export default function Features() {
  const { t } = useTranslation()

  const coreFeatures = [
    {
      icon: <CpuChipIcon className="w-8 h-8" />,
      title: t('features.core.topology.title'),
      description: t('features.core.topology.description'),
      color: 'from-blue-500 to-cyan-500',
      tags: [t('features.tags.visualEditor'), t('features.tags.realtime'), t('features.tags.multiDevice')],
    },
    {
      icon: <ServerIcon className="w-8 h-8" />,
      title: t('features.core.sdn.title'),
      description: t('features.core.sdn.description'),
      color: 'from-purple-500 to-pink-500',
      tags: [t('features.tags.openflow'), t('features.tags.multiController'), t('features.tags.restApi')],
    },
    {
      icon: <CodeBracketIcon className="w-8 h-8" />,
      title: t('features.core.p4.title'),
      description: t('features.core.p4.description'),
      color: 'from-orange-500 to-red-500',
      tags: [t('features.tags.p4runtime'), t('features.tags.grpc'), t('features.tags.programmable')],
    },
    {
      icon: <ChartBarIcon className="w-8 h-8" />,
      title: t('features.core.monitoring.title'),
      description: t('features.core.monitoring.description'),
      color: 'from-green-500 to-emerald-500',
      tags: [t('features.tags.prometheus'), t('features.tags.grafana'), t('features.tags.liveMetrics')],
    },
    {
      icon: <GlobeAltIcon className="w-8 h-8" />,
      title: t('features.core.protocols.title'),
      description: t('features.core.protocols.description'),
      color: 'from-indigo-500 to-purple-500',
      tags: [t('features.tags.frr'), t('features.tags.dynamicRouting'), t('features.tags.multiProtocol')],
    },
    {
      icon: <CommandLineIcon className="w-8 h-8" />,
      title: t('features.core.webshell.title'),
      description: t('features.core.webshell.description'),
      color: 'from-yellow-500 to-orange-500',
      tags: [t('features.tags.terminal'), t('features.tags.ssh'), t('features.tags.realtime')],
    },
    {
      icon: <CloudIcon className="w-8 h-8" />,
      title: t('features.core.container.title'),
      description: t('features.core.container.description'),
      color: 'from-cyan-500 to-blue-500',
      tags: [t('features.tags.docker'), t('features.tags.containerized'), t('features.tags.microservices')],
    },
    {
      icon: <CameraIcon className="w-8 h-8" />,
      title: t('features.core.snapshot.title'),
      description: t('features.core.snapshot.description'),
      color: 'from-pink-500 to-rose-500',
      tags: [t('features.tags.stateManagement'), t('features.tags.backup'), t('features.tags.restore')],
    },
  ]

  const advancedFeatures = [
    {
      icon: <FolderArrowDownIcon className="w-6 h-6" />,
      title: t('features.advanced.importExport.title'),
      description: t('features.advanced.importExport.description'),
    },
    {
      icon: <BeakerIcon className="w-6 h-6" />,
      title: t('features.advanced.generator.title'),
      description: t('features.advanced.generator.description'),
    },
    {
      icon: <WrenchScrewdriverIcon className="w-6 h-6" />,
      title: t('features.advanced.deviceManager.title'),
      description: t('features.advanced.deviceManager.description'),
    },
    {
      icon: <ArrowPathIcon className="w-6 h-6" />,
      title: t('features.advanced.orchestrator.title'),
      description: t('features.advanced.orchestrator.description'),
    },
    {
      icon: <CircleStackIcon className="w-6 h-6" />,
      title: t('features.advanced.multiDb.title'),
      description: t('features.advanced.multiDb.description'),
    },
    {
      icon: <ShieldCheckIcon className="w-6 h-6" />,
      title: t('features.advanced.serviceDiscovery.title'),
      description: t('features.advanced.serviceDiscovery.description'),
    },
  ]

  const technicalSpecs = [
    {
      category: t('features.specs.devices.category'),
      items: t('features.specs.devices.items', { returnObjects: true }) as string[],
    },
    {
      category: t('features.specs.networkFeatures.category'),
      items: t('features.specs.networkFeatures.items', { returnObjects: true }) as string[],
    },
    {
      category: t('features.specs.controllers.category'),
      items: t('features.specs.controllers.items', { returnObjects: true }) as string[],
    },
    {
      category: t('features.specs.protocols.category'),
      items: t('features.specs.protocols.items', { returnObjects: true }) as string[],
    },
  ]

  const architectureHighlights = [
    {
      icon: <BoltIcon className="w-6 h-6 text-yellow-600" />,
      title: t('features.architecture.microservices.title'),
      description: t('features.architecture.microservices.description'),
    },
    {
      icon: <SparklesIcon className="w-6 h-6 text-purple-600" />,
      title: t('features.architecture.eventDriven.title'),
      description: t('features.architecture.eventDriven.description'),
    },
    {
      icon: <CubeIcon className="w-6 h-6 text-blue-600" />,
      title: t('features.architecture.containerNative.title'),
      description: t('features.architecture.containerNative.description'),
    },
  ]

  return (
    <div className="min-h-screen pb-20 md:pb-8 bg-gray-50 dark:bg-gray-950">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-gray-950 dark:via-gray-900 dark:to-blue-950">
        <div className="absolute inset-0 overflow-hidden opacity-20">
          <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-blue-500 rounded-full mix-blend-multiply filter blur-3xl animate-pulse"></div>
          <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl animate-pulse delay-1000"></div>
        </div>

        <div className="relative container-custom py-16 sm:py-24">
          <div className="text-center space-y-6">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl border border-gray-200 dark:border-gray-800 shadow-lg">
              <SparklesIcon className="w-4 h-4 text-purple-600" />
              <span className="text-sm font-medium text-gray-900 dark:text-white">
                {t('features.hero.badge')}
              </span>
            </div>

            <h1 className="heading-1 text-gray-900 dark:text-white px-4">
              {t('features.hero.title')}
            </h1>

            <p className="text-lg sm:text-xl text-gray-600 dark:text-gray-400 max-w-3xl mx-auto px-4">
              {t('features.hero.subtitle')}
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 px-4">
              <Link to="/projects">
                <Button variant="primary" size="lg">
                  {t('home.getStarted')}
                </Button>
              </Link>
              <Link to="/">
                <Button variant="secondary" size="lg">
                  {t('features.hero.learnMore')}
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Core Features */}
      <section className="container-custom py-16">
        <div className="text-center mb-12">
          <h2 className="heading-2 text-gray-900 dark:text-white mb-4">
            {t('features.coreTitle')}
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl mx-auto">
            {t('features.coreSubtitle')}
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {coreFeatures.map((feature, index) => (
            <div
              key={index}
              className="modern-card p-6 hover-lift"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className={`inline-flex p-3 rounded-2xl bg-gradient-to-br ${feature.color} text-white mb-4`}>
                {feature.icon}
              </div>
              <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2">
                {feature.title}
              </h3>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4 leading-relaxed">
                {feature.description}
              </p>
              <div className="flex flex-wrap gap-2">
                {feature.tags.map((tag, i) => (
                  <span
                    key={i}
                    className="badge badge-primary text-xs"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Advanced Features */}
      <section className="bg-white dark:bg-gray-900 py-16">
        <div className="container-custom">
          <div className="text-center mb-12">
            <h2 className="heading-2 text-gray-900 dark:text-white mb-4">
              {t('features.advancedTitle')}
            </h2>
            <p className="text-lg text-gray-600 dark:text-gray-400">
              {t('features.advancedSubtitle')}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {advancedFeatures.map((feature, index) => (
              <div
                key={index}
                className="modern-card p-6 flex gap-4"
              >
                <div className="flex-shrink-0">
                  <div className="w-12 h-12 rounded-xl bg-blue-100 dark:bg-blue-950 flex items-center justify-center text-blue-600 dark:text-blue-400">
                    {feature.icon}
                  </div>
                </div>
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    {feature.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Technical Specifications */}
      <section className="container-custom py-16">
        <div className="text-center mb-12">
          <h2 className="heading-2 text-gray-900 dark:text-white mb-4">
            {t('features.specsTitle')}
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {technicalSpecs.map((spec, index) => (
            <div
              key={index}
              className="modern-card p-6"
            >
              <h3 className="font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                <div className="w-2 h-2 bg-blue-600 rounded-full"></div>
                {spec.category}
              </h3>
              <ul className="space-y-2">
                {spec.items.map((item, i) => (
                  <li
                    key={i}
                    className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2"
                  >
                    <span className="text-green-600 dark:text-green-400 mt-0.5">✓</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* Architecture Highlights */}
      <section className="bg-gradient-to-br from-gray-900 to-blue-900 dark:from-gray-950 dark:to-blue-950 py-16 text-white">
        <div className="container-custom">
          <div className="text-center mb-12">
            <h2 className="heading-2 mb-4">
              {t('features.architectureTitle')}
            </h2>
            <p className="text-lg text-gray-300">
              {t('features.architectureSubtitle')}
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {architectureHighlights.map((item, index) => (
              <div
                key={index}
                className="text-center p-8 rounded-2xl bg-white/10 backdrop-blur-xl border border-white/20 hover:bg-white/15 transition-all"
              >
                <div className="inline-flex p-4 rounded-full bg-white/20 mb-4">
                  {item.icon}
                </div>
                <h3 className="text-xl font-bold mb-2">
                  {item.title}
                </h3>
                <p className="text-gray-300">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="container-custom py-16">
        <div className="modern-card p-8 md:p-12 text-center">
          <h2 className="heading-2 text-gray-900 dark:text-white mb-4">
            {t('features.cta.title')}
          </h2>
          <p className="text-lg text-gray-600 dark:text-gray-400 mb-8 max-w-2xl mx-auto">
            {t('features.cta.subtitle')}
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/projects">
              <Button variant="primary" size="lg">
                {t('projects.create')}
              </Button>
            </Link>
            <a href="https://github.com/caduceus-flux" target="_blank" rel="noopener noreferrer">
              <Button variant="secondary" size="lg">
                {t('features.cta.documentation')}
              </Button>
            </a>
          </div>
        </div>
      </section>
    </div>
  )
}
