import { useMemo } from 'react'
import { Button } from '@/components/atoms/Button'
import { Badge } from '@/components/atoms/Badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { cn } from '@/utils/cn'
import JsonViewer from '@/components/JsonViewer'

export type ToolRunStatus = 'idle' | 'generated' | 'running' | 'success' | 'error'

function parseToonFirstLine(toon: string): { method: string; path: string } {
  const firstLine = (toon || '')
    .split('\n')
    .map((l) => l.trim())
    .find((l) => Boolean(l))
  if (!firstLine) return { method: '', path: '' }
  const parts = firstLine.split(/\s+/)
  if (parts.length >= 2) return { method: parts[0].toUpperCase(), path: parts[1] }
  return { method: '', path: '' }
}

function httpMethodVariant(method: string) {
  const m = method.toUpperCase()
  if (m === 'GET') return 'info'
  if (m === 'POST') return 'primary'
  if (m === 'PUT' || m === 'PATCH') return 'warning'
  if (m === 'DELETE') return 'error'
  return 'default'
}

export function ToolStatusBadge({ status }: { status: ToolRunStatus }) {
  const props = useMemo(() => {
    switch (status) {
      case 'generated':
        return { variant: 'info' as const, text: 'Ready' }
      case 'running':
        return { variant: 'primary' as const, text: 'Running' }
      case 'success':
        return { variant: 'success' as const, text: 'Success' }
      case 'error':
        return { variant: 'error' as const, text: 'Error' }
      default:
        return { variant: 'default' as const, text: 'Idle' }
    }
  }, [status])

  return (
    <Badge variant={props.variant} size="sm">
      {props.text}
    </Badge>
  )
}

export function CodeBlock({
  label,
  value,
  monospace = true,
  rightActions,
  className,
}: {
  label: string
  value: string
  monospace?: boolean
  rightActions?: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{label}</div>
        {rightActions}
      </div>
      <pre
        className={cn(
          'w-full whitespace-pre-wrap break-words px-4 py-3 rounded-2xl border',
          'bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100',
          'border-gray-200 dark:border-gray-800',
          monospace ? 'font-mono text-sm' : 'text-sm'
        )}
      >
        {value || '—'}
      </pre>
    </div>
  )
}

export function JsonBlock({
  label,
  value,
  rightActions,
  className,
  collapsed = 2,
}: {
  label: string
  value: unknown
  rightActions?: React.ReactNode
  className?: string
  collapsed?: boolean | number
}) {
  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">{label}</div>
        {rightActions}
      </div>
      <JsonViewer data={value} collapsed={collapsed} />
    </div>
  )
}

export function CopyButton({ value, label = 'Copy' }: { value: string; label?: string }) {
  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={async () => {
        await navigator.clipboard.writeText(value || '')
      }}
      disabled={!value}
    >
      {label}
    </Button>
  )
}

export function ToolCallCard({
  title,
  subtitle,
  status,
  requestText,
  responseText,
  responseJson,
  errorText,
  meta,
  onRun,
  runLabel = 'Run',
  runDisabled,
  isRunning,
  extraHeaderRight,
}: {
  title: string
  subtitle?: string
  status: ToolRunStatus
  requestText: string
  responseText: string
  responseJson?: unknown
  errorText?: string
  meta?: { statusCode?: number; durationMs?: number }
  onRun: () => void
  runLabel?: string
  runDisabled?: boolean
  isRunning?: boolean
  extraHeaderRight?: React.ReactNode
}) {
  const first = useMemo(() => parseToonFirstLine(requestText), [requestText])
  const statusCode = meta?.statusCode
  const durationMs = meta?.durationMs

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-3">
            <CardTitle className="truncate">{title}</CardTitle>
            <ToolStatusBadge status={status} />
          </div>
          {(first.method || first.path) && (
            <div className="mt-1 flex flex-wrap items-center gap-2">
              {first.method && (
                <Badge variant={httpMethodVariant(first.method) as any} size="sm" className="shrink-0">
                  {first.method}
                </Badge>
              )}
              {first.path && (
                <div className="font-mono text-xs text-gray-900 dark:text-gray-100 break-words">{first.path}</div>
              )}
              {typeof statusCode === 'number' && (
                <Badge variant={statusCode >= 200 && statusCode < 300 ? ('success' as any) : ('error' as any)} size="sm">
                  HTTP {statusCode}
                </Badge>
              )}
              {typeof durationMs === 'number' && (
                <Badge variant="default" size="sm">
                  {durationMs}ms
                </Badge>
              )}
            </div>
          )}
          {subtitle && (
            <div className="mt-1 text-sm text-gray-600 dark:text-gray-400 truncate">{subtitle}</div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {extraHeaderRight}
          <Button
            variant="primary"
            size="sm"
            onClick={onRun}
            isLoading={isRunning}
            disabled={Boolean(runDisabled)}
          >
            {runLabel}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <CodeBlock
          label="Request (TOON)"
          value={requestText}
          rightActions={<CopyButton value={requestText} />}
        />
        {errorText && (
          <div className="rounded-2xl border border-red-200 dark:border-red-900/40 bg-red-50 dark:bg-red-950/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">
            {errorText}
          </div>
        )}
        {responseJson !== undefined ? (
          <JsonBlock
            label="Response"
            value={responseJson}
            rightActions={<CopyButton value={responseText} />}
            collapsed={2}
          />
        ) : (
          <CodeBlock
            label="Response"
            value={responseText}
            rightActions={<CopyButton value={responseText} />}
            monospace
          />
        )}
      </CardContent>
    </Card>
  )
}
