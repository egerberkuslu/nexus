import { useMemo } from 'react'
import { ResponsiveContainer, BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, Legend } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'

const toKey = (v: unknown) => String(v ?? '').trim()

export default function AlgoMessageTypesChart({ events }: { events: any[] }) {
  const rows = useMemo(() => {
    const counts = new Map<string, number>()
    for (const e of events || []) {
      const mt = toKey(e?.msg_type || e?.type)
      if (!mt) continue
      counts.set(mt, (counts.get(mt) || 0) + 1)
    }
    const out = Array.from(counts.entries())
      .map(([msgType, count]) => ({ msgType, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 12)
    return out
  }, [events])

  const total = useMemo(() => rows.reduce((acc, r) => acc + (Number(r.count) || 0), 0), [rows])

  if (!rows.length) return null

  return (
    <Card padding="lg" className="overflow-hidden">
      <CardHeader className="mb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">Message types</CardTitle>
          <Badge variant="default" size="sm">
            Top {rows.length} • <span className="font-mono">{total}</span>
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-[220px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} layout="vertical" margin={{ left: 12, right: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="msgType" tick={{ fontSize: 11 }} width={120} />
              <Tooltip />
              <Legend />
              <Bar dataKey="count" name="Count" fill="#f59e0b" radius={[6, 6, 6, 6]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  )
}

