import React from 'react'
import clsx from 'clsx'

interface ModernCardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
  variant?: 'default' | 'compact'
}

export const ModernCard: React.FC<ModernCardProps> = ({
  children,
  className,
  hover = true,
  padding = 'md',
  variant = 'default',
}) => {
  const paddingClasses = {
    none: '',
    sm: 'p-4',
    md: 'p-6',
    lg: 'p-8',
  }

  const variantBaseClasses = {
    default: 'rounded-2xl shadow-sm',
    compact: 'rounded-xl shadow-sm',
  }

  const variantHoverClasses = {
    default: 'hover:shadow-md',
    compact: 'hover:shadow',
  }

  return (
    <div
      className={clsx(
        'bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800',
        hover && 'transition-all duration-300',
        variantBaseClasses[variant],
        hover && variantHoverClasses[variant],
        hover && 'cursor-pointer',
        paddingClasses[padding],
        className
      )}
    >
      {children}
    </div>
  )
}
