import ReactJson from 'react-json-view'
import { useEffect, useState } from 'react'
import { cn } from '@/utils/cn'

export type JsonViewerProps = {
  data: unknown
  collapsed?: boolean | number
  className?: string
  name?: string | false
}

export default function JsonViewer({ data, collapsed = 2, className, name = false }: JsonViewerProps) {
  const [theme, setTheme] = useState<'rjv-default' | 'monokai'>('rjv-default')

  useEffect(() => {
    if (typeof document === 'undefined') return

    const update = () => {
      setTheme(document.documentElement.classList.contains('dark') ? 'monokai' : 'rjv-default')
    }

    update()

    const el = document.documentElement
    const obs = new MutationObserver(update)
    obs.observe(el, { attributes: true, attributeFilter: ['class'] })
    return () => obs.disconnect()
  }, [])

  return (
    <div
      className={cn(
        'rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900',
        'px-4 py-3 text-sm',
        className
      )}
    >
      <ReactJson
        src={data as any}
        name={name as any}
        collapsed={collapsed as any}
        theme={theme as any}
        displayDataTypes={false}
        displayObjectSize={false}
        enableClipboard={false}
        indentWidth={2}
        collapseStringsAfterLength={80}
        quotesOnKeys={false}
        iconStyle="triangle"
      />
    </div>
  )
}
