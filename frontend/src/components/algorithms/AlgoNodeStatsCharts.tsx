import { useMemo } from 'react'
import { ResponsiveContainer, BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, Legend } from 'recharts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'

type NodeRow = {
  algoId: number
  outMsgs: number | string
  inMsgs: number | string
  neighbors?: number | string
  status?: string
}

const toNum = (v: unknown): number | null => {
  if (v == null) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

export default function AlgoNodeStatsCharts({
  rows,
  formatNodeLabel,
}: {
  rows: NodeRow[]
  formatNodeLabel?: (algoId: number) => string
}) {
  const data = useMemo(() => {
    const out: Array<{
      node: string
      algoId: number
      outMsgs: number
      inMsgs: number
      neighbors: number
    }> = []
    for (const r of rows || []) {
      const algoId = Number((r as any)?.algoId)
      if (!Number.isFinite(algoId)) continue
      const outMsgs = toNum((r as any)?.outMsgs) ?? 0
      const inMsgs = toNum((r as any)?.inMsgs) ?? 0
      const neighbors = toNum((r as any)?.neighbors) ?? 0
      out.push({
        node: `#${algoId}`,
        algoId,
        outMsgs,
        inMsgs,
        neighbors,
      })
    }
    return out
  }, [rows])

  const topByMsgs = useMemo(() => {
    const sorted = [...data]
    sorted.sort((a, b) => (b.outMsgs + b.inMsgs) - (a.outMsgs + a.inMsgs))
    return sorted.slice(0, 30)
  }, [data])

  const topByNeighbors = useMemo(() => {
    const sorted = [...data]
    sorted.sort((a, b) => b.neighbors - a.neighbors)
    return sorted.slice(0, 30)
  }, [data])

  const hasAny = data.some((d) => d.outMsgs > 0 || d.inMsgs > 0 || d.neighbors > 0)
  if (!hasAny) {
    return (
      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400">No node stats yet.</div>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
      <Card padding="lg" className="overflow-hidden">
        <CardHeader className="mb-2">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">Messages per node</CardTitle>
            <Badge variant="default" size="sm">
              Top {topByMsgs.length}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topByMsgs}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                <XAxis dataKey="node" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(v: any, name: any, ctx: any) => [v, name]}
                  labelFormatter={(label: any, payload: any) => {
                    const p = Array.isArray(payload) && payload[0]?.payload ? payload[0].payload : null
                    const id = Number(p?.algoId)
                    if (formatNodeLabel && Number.isFinite(id)) return formatNodeLabel(id)
                    return String(label || '')
                  }}
                />
                <Legend />
                <Bar dataKey="outMsgs" name="Out (TX+BCAST)" stackId="msgs" fill="#3b82f6" radius={[6, 6, 0, 0]} />
                <Bar dataKey="inMsgs" name="In (RX)" stackId="msgs" fill="#22c55e" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <Card padding="lg" className="overflow-hidden">
        <CardHeader className="mb-2">
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-base">Neighbors per node</CardTitle>
            <Badge variant="default" size="sm">
              Top {topByNeighbors.length}
            </Badge>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={topByNeighbors}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                <XAxis dataKey="node" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(v: any, name: any) => [v, name]}
                  labelFormatter={(label: any, payload: any) => {
                    const p = Array.isArray(payload) && payload[0]?.payload ? payload[0].payload : null
                    const id = Number(p?.algoId)
                    if (formatNodeLabel && Number.isFinite(id)) return formatNodeLabel(id)
                    return String(label || '')
                  }}
                />
                <Legend />
                <Bar dataKey="neighbors" name="Neighbors" fill="#a855f7" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

