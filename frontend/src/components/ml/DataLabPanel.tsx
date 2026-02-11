import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Button } from '@/components/atoms/Button'
import { Input } from '@/components/atoms/Input'
import { infrastructureAPI } from '@/services/api'

type Props = {
  embedded?: boolean
}

export default function DataLabPanel({ embedded }: Props) {
  const [token, setToken] = useState('')

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      try {
        const res = await infrastructureAPI.jupyter()
        const t = String((res.data as any)?.token || '').trim()
        if (!t) return
        if (cancelled) return
        setToken((prev) => (prev.trim() ? prev : t))
      } catch {
        // ignore (user can paste token manually)
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [])

  const src = useMemo(() => {
    const t = token.trim()
    if (!t) return '/jupyter/lab'
    return `/jupyter/lab?token=${encodeURIComponent(t)}`
  }, [token])

  const iframeHeight = embedded ? 'h-[70vh]' : 'h-[80vh]'

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>JupyterLab</CardTitle>
          <div className="flex items-center gap-2">
            <a href={src} target="_blank" rel="noopener noreferrer">
              <Button variant="secondary" size="sm">
                Open in new tab
              </Button>
            </a>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
            <Input
              label="Token (optional)"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="Paste JUPYTER_TOKEN to auto-login"
            />
            <div className="text-xs text-gray-500 dark:text-gray-400 flex items-end">
              URL: <span className="ml-2 font-mono">{src}</span>
            </div>
          </div>

          <div className={`w-full ${iframeHeight} rounded-xl overflow-hidden border border-gray-200 dark:border-gray-800`}>
            <iframe
              title="JupyterLab"
              src={src}
              className="w-full h-full bg-white dark:bg-gray-950"
              allow="clipboard-read; clipboard-write"
            />
          </div>

          <div className="text-xs text-gray-500 dark:text-gray-400">
            If the iframe shows a token prompt, paste <span className="font-mono">JUPYTER_TOKEN</span> (see `docker-compose.yml`) or use the
            “Open in new tab” button.
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
