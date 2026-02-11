import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'
import { Button } from '@/components/atoms/Button'

export type WSNRoundRow = {
  round: number
  alive_nodes: number
  dead_nodes: number
  cluster_count: number
  packets_to_bs: number
  total_energy: number
  avg_energy: number
  min_energy: number
  max_energy: number
  energy_variance: number
}

const fmt = (v: number, digits = 4) => {
  if (!Number.isFinite(v)) return '—'
  if (Math.abs(v) >= 1000) return String(Math.round(v))
  return v.toFixed(digits)
}

export default function RoundMetricsTable({
  rows,
  totalRounds,
  toggleLabel,
  onToggle,
  toggleDisabled,
}: {
  rows: WSNRoundRow[]
  totalRounds: number
  toggleLabel?: string
  onToggle?: () => void
  toggleDisabled?: boolean
}) {
  return (
    <Card padding="lg">
      <CardHeader className="mb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">Round metrics</CardTitle>
          <div className="flex items-center gap-2">
            {toggleLabel && onToggle ? (
              <Button variant="secondary" size="sm" onClick={onToggle} disabled={!!toggleDisabled}>
                {toggleLabel}
              </Button>
            ) : null}
            <Badge variant="default" size="sm">
              Showing: <span className="font-mono">{rows.length}</span> / <span className="font-mono">{totalRounds}</span>
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {rows.length ? (
          <div className="max-h-[340px] overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
                <tr>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Round</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Alive</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Dead</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Clusters</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Pkts→BS</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">E(total)</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">E(avg)</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">E(min)</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Var(E)</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.round} className="border-b border-gray-100 dark:border-gray-800">
                    <td className="py-2 px-3 font-mono text-xs text-gray-900 dark:text-gray-100">{r.round}</td>
                    <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.alive_nodes}</td>
                    <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.dead_nodes}</td>
                    <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.cluster_count}</td>
                    <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.packets_to_bs}</td>
                    <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{fmt(r.total_energy, 4)}</td>
                    <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{fmt(r.avg_energy, 4)}</td>
                    <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{fmt(r.min_energy, 4)}</td>
                    <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{fmt(r.energy_variance, 6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-sm text-gray-500 dark:text-gray-400">Waiting for round metrics…</div>
        )}
      </CardContent>
    </Card>
  )
}
