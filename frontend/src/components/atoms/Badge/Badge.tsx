import { forwardRef, HTMLAttributes } from 'react'
import { cn } from '@/utils/cn'
import { CheckCircle, XCircle, AlertCircle, Info, Loader2 } from 'lucide-react'

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'primary'
  size?: 'sm' | 'md' | 'lg'
  withIcon?: boolean
  isLoading?: boolean
}

const variantStyles = {
  default: 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300',
  success: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  warning: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400',
  error: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
  info: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  primary: 'bg-blue-600 dark:bg-blue-500 text-white',
}

const sizeStyles = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-3 py-1 text-sm',
  lg: 'px-4 py-1.5 text-base',
}

const iconMap = {
  default: Info,
  success: CheckCircle,
  warning: AlertCircle,
  error: XCircle,
  info: Info,
  primary: Info,
}

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ children, className, variant = 'default', size = 'md', withIcon = false, isLoading = false, ...props }, ref) => {
    const Icon = iconMap[variant]
    const iconSize = size === 'sm' ? 12 : size === 'md' ? 14 : 16

    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center gap-1.5 rounded-full font-medium',
          variantStyles[variant],
          sizeStyles[size],
          className
        )}
        {...props}
      >
        {isLoading && <Loader2 size={iconSize} className="animate-spin" />}
        {!isLoading && withIcon && <Icon size={iconSize} />}
        {children}
      </span>
    )
  }
)

Badge.displayName = 'Badge'

