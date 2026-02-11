import { Link, useLocation } from 'react-router-dom'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Bars3Icon, XMarkIcon } from '@heroicons/react/24/outline'
import ThemeSwitcher from '@/components/ThemeSwitcher'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'
import clsx from 'clsx'

type NavItem = {
  name: string
  href: string
}

export default function HostHeader() {
  const location = useLocation()
  const { t } = useTranslation()
  const [mobileOpen, setMobileOpen] = useState(false)

  const nav: NavItem[] = useMemo(
    () => [
      { name: t('nav.home'), href: '/' },
      { name: t('nav.features'), href: '/features' },
      { name: t('nav.projects'), href: '/projects' },
      { name: 'Snapshots', href: '/snapshots' },
      { name: 'Schedules', href: '/schedules' },
      { name: t('nav.networkManager'), href: '/network-manager' },
      { name: 'AI Console', href: '/ai-console' },
      { name: 'AI Settings', href: '/ai-settings' },
    ],
    [t]
  )

  const isActive = (href: string) => {
    if (href === '/') return location.pathname === '/'
    return location.pathname.startsWith(href)
  }

  return (
    <header className="sticky top-0 z-50">
      {/* Promo strip */}
      <div className="bg-fuchsia-600 text-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-2 flex items-center justify-between">
          <div className="text-xs sm:text-sm font-semibold">
            Cyber Week fırsatlarını kaçırmayın
          </div>
          <div className="text-xs font-mono opacity-90 hidden sm:block">
            00 : 16 : 17 : 33
          </div>
        </div>
      </div>

      {/* Main nav */}
      <div className="bg-white/90 dark:bg-gray-950/90 backdrop-blur border-b border-gray-200 dark:border-gray-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Link to="/" className="flex items-center gap-3 min-w-0">
              <img src="/logo2.png" alt="NEXUS - Network EXperimentation Unified System" className="w-9 h-9 object-contain" />
              <div className="hidden sm:block min-w-0">
                <div className="text-sm font-extrabold tracking-tight text-gray-900 dark:text-white truncate">
                  {t('app.name')}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 truncate">
                  {t('app.tagline')}
                </div>
              </div>
            </Link>
          </div>

          <nav className="hidden lg:flex items-center gap-1">
            {nav.map((item) => {
              const active = isActive(item.href)
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  className={clsx(
                    'px-3 py-2 rounded-xl text-sm font-semibold',
                    active
                      ? 'bg-violet-600 text-white'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-900'
                  )}
                >
                  {item.name}
                </Link>
              )
            })}
          </nav>

          <div className="flex items-center gap-2">
            <ThemeSwitcher />
            <LanguageSwitcher />
            <Link
              to="/projects"
              className="hidden sm:inline-flex items-center justify-center px-4 py-2 rounded-xl bg-gray-900 text-white dark:bg-white dark:text-gray-900 text-sm font-semibold"
            >
              Hesabım
            </Link>
            <button
              className="lg:hidden p-2 rounded-xl hover:bg-gray-100 dark:hover:bg-gray-900 text-gray-700 dark:text-gray-300"
              onClick={() => setMobileOpen((v) => !v)}
            >
              {mobileOpen ? <XMarkIcon className="w-6 h-6" /> : <Bars3Icon className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {mobileOpen && (
          <div className="lg:hidden border-t border-gray-200 dark:border-gray-800">
            <div className="max-w-7xl mx-auto px-4 py-3 grid grid-cols-1 gap-1">
              {nav.map((item) => {
                const active = isActive(item.href)
                return (
                  <Link
                    key={item.href}
                    to={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={clsx(
                      'px-4 py-3 rounded-xl text-sm font-semibold',
                      active
                        ? 'bg-violet-600 text-white'
                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-900'
                    )}
                  >
                    {item.name}
                  </Link>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </header>
  )
}
