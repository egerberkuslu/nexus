import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { HomeIcon } from '@heroicons/react/24/outline'
import { Button } from '@/components/atoms/Button'

export function NotFound() {
  const { t } = useTranslation()

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 transition-colors duration-200">
      <div className="container-custom py-10">
        <div className="max-w-xl">
          <div className="text-sm font-semibold text-gray-500 dark:text-gray-400">404</div>
          <h2 className="mt-2 text-3xl font-bold text-gray-900 dark:text-white">
            {t('errors.notFound')}
          </h2>
          <p className="mt-3 text-lg text-gray-600 dark:text-gray-400">
            {t('errors.notFoundMessage')}
          </p>
          <div className="mt-6">
            <Link to="/">
              <Button variant="primary" size="lg" leftIcon={<HomeIcon className="h-5 w-5" />}>
                {t('common.backHome')}
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
