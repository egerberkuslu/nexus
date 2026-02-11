import { Card, CardContent } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/utils/cn'

export interface MetricCardProps {
  title: string
  value: string | number
  icon?: React.ReactNode
  trend?: number
  subtitle?: string
  variant?: 'default' | 'primary' | 'success' | 'warning' | 'error'
  isLoading?: boolean
  onClick?: () => void
}

const variantStyles = {
  default: {
    icon: 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400',
    value: 'text-gray-900 dark:text-white',
  },
  primary: {
    icon: 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
    value: 'text-blue-600 dark:text-blue-400',
  },
  success: {
    icon: 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400',
    value: 'text-green-600 dark:text-green-400',
  },
  warning: {
    icon: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400',
    value: 'text-yellow-600 dark:text-yellow-400',
  },
  error: {
    icon: 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
    value: 'text-red-600 dark:text-red-400',
  },
}

export const MetricCard: React.FC<MetricCardProps> = ({
  title,
  value,
  icon,
  trend,
  subtitle,
  variant = 'default',
  isLoading = false,
  onClick,
}) => {
  const styles = variantStyles[variant]

  return (
    <Card
      padding="lg"
      hover={!!onClick}
      onClick={onClick}
      className={cn(onClick && 'cursor-pointer')}
    >
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            {icon && (
              <div className={cn('inline-flex p-2 rounded-xl mb-3', styles.icon)}>
                {icon}
              </div>
            )}
            <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
              {title}
            </p>
          </div>
          {trend !== undefined && (
            <Badge
              variant={trend > 0 ? 'success' : trend < 0 ? 'error' : 'default'}
              size="sm"
              withIcon
            >
              {trend > 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {trend > 0 ? '+' : ''}
              {trend.toFixed(1)}%
            </Badge>
          )}
        </div>
        
        {isLoading ? (
          <div className="animate-pulse">
            <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-24"></div>
          </div>
        ) : (
          <p className={cn('text-3xl font-bold', styles.value)}>
            {value}
          </p>
        )}
        
        {subtitle && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {subtitle}
          </p>
        )}
      </CardContent>
    </Card>
  )
}

