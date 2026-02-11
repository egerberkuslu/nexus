import React from 'react'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface MetricCardProps {
  icon: React.ReactNode
  label: string
  value: string | number
  trend?: number
  color?: 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'indigo'
  subtitle?: string
}

const colorClasses = {
  blue: {
    bg: 'bg-blue-100 dark:bg-blue-900/30',
    border: 'border-blue-200 dark:border-blue-800',
    text: 'text-blue-600 dark:text-blue-400',
    iconBg: 'bg-blue-50 dark:bg-blue-900/20',
  },
  green: {
    bg: 'bg-green-100 dark:bg-green-900/30',
    border: 'border-green-200 dark:border-green-800',
    text: 'text-green-600 dark:text-green-400',
    iconBg: 'bg-green-50 dark:bg-green-900/20',
  },
  red: {
    bg: 'bg-red-100 dark:bg-red-900/30',
    border: 'border-red-200 dark:border-red-800',
    text: 'text-red-600 dark:text-red-400',
    iconBg: 'bg-red-50 dark:bg-red-900/20',
  },
  yellow: {
    bg: 'bg-yellow-100 dark:bg-yellow-900/30',
    border: 'border-yellow-200 dark:border-yellow-800',
    text: 'text-yellow-600 dark:text-yellow-400',
    iconBg: 'bg-yellow-50 dark:bg-yellow-900/20',
  },
  purple: {
    bg: 'bg-purple-100 dark:bg-purple-900/30',
    border: 'border-purple-200 dark:border-purple-800',
    text: 'text-purple-600 dark:text-purple-400',
    iconBg: 'bg-purple-50 dark:bg-purple-900/20',
  },
  indigo: {
    bg: 'bg-indigo-100 dark:bg-indigo-900/30',
    border: 'border-indigo-200 dark:border-indigo-800',
    text: 'text-indigo-600 dark:text-indigo-400',
    iconBg: 'bg-indigo-50 dark:bg-indigo-900/20',
  },
}

export const MetricCard: React.FC<MetricCardProps> = ({
  icon,
  label,
  value,
  trend,
  color = 'blue',
  subtitle,
}) => {
  const colors = colorClasses[color]

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-6 shadow hover:shadow-lg transition-all duration-300 hover:scale-105">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <div className={`p-2 ${colors.iconBg} rounded-xl border ${colors.border}`}>
              {icon}
            </div>
            <div>
              <p className={`${colors.text} text-sm font-medium`}>{label}</p>
              {subtitle && (
                <p className="text-gray-500 dark:text-gray-400 text-xs">{subtitle}</p>
              )}
            </div>
          </div>
          <p className="text-3xl font-bold text-gray-800 dark:text-gray-100 mb-1">
            {value}
          </p>
          {trend !== undefined && (
            <div
              className={`flex items-center gap-1 text-xs ${
                trend > 0
                  ? 'text-green-600 dark:text-green-400'
                  : trend < 0
                  ? 'text-red-600 dark:text-red-400'
                  : 'text-gray-500 dark:text-gray-400'
              }`}
            >
              {trend !== 0 && (
                trend > 0 ? (
                  <TrendingUp className="w-3 h-3" />
                ) : (
                  <TrendingDown className="w-3 h-3" />
                )
              )}
              <span>
                {trend > 0 ? '+' : ''}
                {trend.toFixed(1)}%
              </span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default MetricCard

