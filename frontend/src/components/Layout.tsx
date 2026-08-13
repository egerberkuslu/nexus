import { Outlet, Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useState } from 'react'
import {
  HomeIcon,
  FolderIcon,
  ChartBarIcon,
  Bars3Icon,
  XMarkIcon,
  CameraIcon,
  CalendarIcon,
  CommandLineIcon,
  DocumentTextIcon,
  ServerIcon,
  CpuChipIcon,
} from '@heroicons/react/24/outline'
import ThemeSwitcher from './ThemeSwitcher'
import { LanguageSwitcher } from './LanguageSwitcher'

export default function Layout() {
  const location = useLocation()
  const { t } = useTranslation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const appName = t('app.name')
  const compactAppName = appName.split(' - ')[0]?.trim() || appName

  const navigation = [
    { name: t('nav.home'), href: '/', icon: HomeIcon },
    { name: 'SwarmInfer', href: '/swarminfer', icon: CpuChipIcon },
    { name: t('nav.features'), href: '/features', icon: ChartBarIcon },
    { name: t('nav.projects'), href: '/projects', icon: FolderIcon },
    { name: t('nav.apiDocs'), href: '/docs', icon: DocumentTextIcon },
    { name: t('nav.snapshots'), href: '/snapshots', icon: CameraIcon },
    { name: t('nav.schedules'), href: '/schedules', icon: CalendarIcon },
    { name: t('nav.infrastructure', 'Infrastructure'), href: '/infrastructure', icon: ServerIcon },
    { name: t('nav.aiConsole'), href: '/ai-console', icon: CommandLineIcon },
    { name: t('nav.aiSettings'), href: '/ai-settings', icon: CommandLineIcon },
  ]

  const isActive = (path: string) => {
    if (path === '/') return location.pathname === '/'
    return location.pathname.startsWith(path)
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors duration-200">
      <nav className="sticky top-0 z-40 bg-white/80 dark:bg-gray-900/80 backdrop-blur-xl border-b border-gray-200 dark:border-gray-800">
        <div className="max-w-[1920px] mx-auto px-6 sm:px-8 lg:px-12">
          <div className="flex items-center justify-between min-h-[4.5rem] py-3 gap-3">
            <div className="flex items-center gap-3 min-w-0">
              <div className="flex items-center min-w-0">
                <img
                  src="/logo2.png"
                  alt="NEXUS - Network EXperimentation Unified System Logo"
                  className="w-10 h-10 sm:w-11 sm:h-11 object-contain flex-shrink-0"
                />
                <div className="ml-2 hidden sm:block min-w-0 max-w-[14rem] lg:max-w-[18rem] 2xl:max-w-none">
                  <h1 className="font-bold text-gray-900 dark:text-white leading-tight text-sm lg:text-base 2xl:text-xl truncate 2xl:whitespace-normal">
                    <span className="2xl:hidden">{compactAppName}</span>
                    <span className="hidden 2xl:inline">{appName}</span>
                  </h1>
                  <p className="hidden lg:block text-xs text-gray-500 dark:text-gray-400 truncate">
                    {t('app.tagline')}
                  </p>
                </div>
              </div>
            </div>

            <div className="hidden md:flex items-center gap-1 lg:gap-2 overflow-x-auto [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
              {navigation.map((item) => {
                const active = isActive(item.href)
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    className={`
                      flex items-center gap-2 px-3 lg:px-3.5 py-2 rounded-full
                      text-sm font-medium whitespace-nowrap transition-all duration-200
                      ${active
                        ? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900'
                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                      }
                    `}
                  >
                    <item.icon className="h-4 w-4 lg:h-5 lg:w-5" />
                    <span className="hidden 2xl:inline">{item.name}</span>
                  </Link>
                )
              })}
            </div>

            <div className="flex items-center gap-2 shrink-0">
              <ThemeSwitcher />
              <LanguageSwitcher />

              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="md:hidden p-2 rounded-xl text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              >
                {mobileMenuOpen ? (
                  <XMarkIcon className="h-6 w-6" />
                ) : (
                  <Bars3Icon className="h-6 w-6" />
                )}
              </button>
            </div>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden border-t border-gray-200 dark:border-gray-800">
            <div className="px-4 py-3 space-y-1">
              {navigation.map((item) => {
                const active = isActive(item.href)
                return (
                  <Link
                    key={item.name}
                    to={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={`
                      flex items-center gap-3 px-4 py-3 rounded-xl
                      text-sm sm:text-base font-medium transition-all duration-200
                      ${active
                        ? 'bg-gray-900 dark:bg-white text-white dark:text-gray-900'
                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                      }
                    `}
                  >
                    <item.icon className="h-6 w-6" />
                    {item.name}
                  </Link>
                )
              })}
            </div>
          </div>
        )}
      </nav>

      {/* Main Content */}
      <main className="min-h-[calc(100vh-5rem)]">
        <Outlet />
      </main>

      {/* Bottom navigation */}
    </div>
  )
}
