import React from 'react'
import clsx from 'clsx'
import { CheckCircle, XCircle, AlertCircle, Info } from 'lucide-react'

interface StatusBadgeProps {
  status: 'success' | 'error' | 'warning' | 'info' | 'running' | 'stopped'
  label?: string
  showIcon?: boolean
  size?: 'sm' | 'md' | 'lg'
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  label,
  showIcon = true,
  size = 'md',
}) => {
  const statusConfig = {
    success: {
      bg: 'bg-green-100 dark:bg-green-900/30',
      text: 'text-green-700 dark:text-green-400',
      icon: CheckCircle,
      label: label || 'Success',
    },
    error: {
      bg: 'bg-red-100 dark:bg-red-900/30',
      text: 'text-red-700 dark:text-red-400',
      icon: XCircle,
      label: label || 'Error',
    },
    warning: {
      bg: 'bg-yellow-100 dark:bg-yellow-900/30',
      text: 'text-yellow-700 dark:text-yellow-400',
      icon: AlertCircle,
      label: label || 'Warning',
    },
    info: {
      bg: 'bg-blue-100 dark:bg-blue-900/30',
      text: 'text-blue-700 dark:text-blue-400',
      icon: Info,
      label: label || 'Info',
    },
    running: {
      bg: 'bg-green-100 dark:bg-green-900/30',
      text: 'text-green-700 dark:text-green-400',
      icon: CheckCircle,
      label: label || 'Running',
    },
    stopped: {
      bg: 'bg-gray-100 dark:bg-gray-700/30',
      text: 'text-gray-700 dark:text-gray-400',
      icon: XCircle,
      label: label || 'Stopped',
    },
  }

  const sizeClasses = {
    sm: 'px-2 py-1 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base',
  }

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
    lg: 'w-5 h-5',
  }

  const config = statusConfig[status]
  const Icon = config.icon

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full font-medium',
        config.bg,
        config.text,
        sizeClasses[size]
      )}
    >
      {showIcon && <Icon className={iconSizes[size]} />}
      {config.label}
    </span>
  )
}

