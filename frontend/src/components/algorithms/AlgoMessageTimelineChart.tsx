import { useMemo } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { ResponsiveContainer, AreaChart, Area, CartesianGrid, XAxis, YAxis, Tooltip, Legend } from 'recharts'

type Bucket = { sec: number; tx: number; rx: number; bcast: number }

const asRecord = (v: unknown): Record<string, unknown> | null => {
  if (!v || typeof v !== 'object') return null
  return v as Record<string, unknown>
}

const toNum = (v: unknown): number | null => {
  if (v == null) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export default function AlgoMessageTimelineChart({
  events,
  runStartedAt,
  windowSeconds = 90,
  height = 220,
  title = 'Message traffic (last 90s)',
}: {
  events: unknown[]
  runStartedAt?: number | null
  windowSeconds?: number
  height?: number
  title?: string
}) {
  const series = useMemo(() => {
    const rows = Array.isArray(events) ? events : []
    const points: Array<{ sec: number; kind: 'tx' | 'rx' | 'bcast' }> = []

    for (const raw of rows.slice(-6000)) {
      const e = asRecord(raw)
      if (!e) continue
      const t = String(e.type || '').toLowerCase()
      const kind = t === 'net_tx' ? 'tx' : t === 'net_rx' ? 'rx' : t === 'net_bcast' ? 'bcast' : null
      if (!kind) continue
      const ts = toNum(e.ts)
      if (ts == null) continue
      points.push({ sec: Math.floor(ts), kind })
    }

    if (!points.length) return []

    const window = Math.max(10, Math.min(10 * 60, Number(windowSeconds) || 90))
    const end = Math.max(...points.map((p) => p.sec))
    const start = end - window + 1

    const buckets = new Map<number, Bucket>()
    for (let s = start; s <= end; s += 1) buckets.set(s, { sec: s, tx: 0, rx: 0, bcast: 0 })

    for (const p of points) {
      if (p.sec < start || p.sec > end) continue
      const b = buckets.get(p.sec)
      if (!b) continue
      if (p.kind === 'tx') b.tx += 1
      else if (p.kind === 'rx') b.rx += 1
      else b.bcast += 1
    }

    const base = toNum(runStartedAt)
    return Array.from(buckets.values()).map((b) => ({
      t: base != null ? b.sec - Math.floor(base) : b.sec - start,
      tx: b.tx,
      rx: b.rx,
      bcast: b.bcast,
      total: b.tx + b.rx + b.bcast,
    }))
  }, [events, runStartedAt, windowSeconds])

  return (
    <Card padding="lg">
      <CardHeader className="mb-2">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {series.length ? (
          <div style={{ height }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                <XAxis dataKey="t" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Area type="monotone" dataKey="tx" stackId="1" name="TX" stroke="#22c55e" fill="#22c55e" fillOpacity={0.35} />
                <Area type="monotone" dataKey="rx" stackId="1" name="RX" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.35} />
                <Area type="monotone" dataKey="bcast" stackId="1" name="BCAST" stroke="#f97316" fill="#f97316" fillOpacity={0.35} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="text-sm text-gray-500 dark:text-gray-400">Waiting for message events…</div>
        )}
      </CardContent>
    </Card>
  )
}

