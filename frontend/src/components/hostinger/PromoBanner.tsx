import React from 'react'
import clsx from 'clsx'

type Props = {
  title: string
  subtitle?: string
  className?: string
  rightSlot?: React.ReactNode
}

export default function PromoBanner({ title, subtitle, className, rightSlot }: Props) {
  return (
    <div
      className={clsx(
        'relative overflow-hidden rounded-2xl border border-violet-200/60 dark:border-violet-500/20',
        'bg-gradient-to-r from-violet-600 via-indigo-600 to-violet-600 text-white',
        className
      )}
    >
      {/* Decorative blocks */}
      <div className="absolute inset-0 opacity-20">
        <div className="absolute -top-10 left-8 h-24 w-24 rounded-2xl bg-white/30" />
        <div className="absolute top-8 left-28 h-10 w-10 rounded-xl bg-white/25" />
        <div className="absolute -bottom-10 right-10 h-24 w-24 rounded-2xl bg-white/30" />
        <div className="absolute top-10 right-32 h-10 w-10 rounded-xl bg-white/25" />
      </div>

      <div className="relative flex items-center justify-between gap-4 px-6 py-5">
        <div className="min-w-0">
          {subtitle && (
            <div className="text-sm font-semibold tracking-wide text-white/90">
              {subtitle}
            </div>
          )}
          <div className="mt-1 text-xl sm:text-2xl font-bold truncate">{title}</div>
        </div>
        {rightSlot && <div className="hidden sm:block">{rightSlot}</div>}
      </div>
    </div>
  )
}

