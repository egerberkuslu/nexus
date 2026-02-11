import { useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'
import { Select } from '@/components/atoms/Select'
import { MetricCard } from '@/components/molecules/MetricCard'
import { ResponsiveContainer, BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, Legend } from 'recharts'

export type AlgorithmRunCompareItem = {
  run_id: string
  algorithm: string
  time?: string
  fields: Record<string, unknown>
}

const toNum = (v: unknown): number | null => {
  if (v == null) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const fmt = (v: unknown, digits = 2): string => {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  if (Math.abs(n) >= 1000) return String(Math.round(n))
  return n.toFixed(digits)
}

export default function AlgorithmRunsCompare({ items }: { items: AlgorithmRunCompareItem[] }) {
  const [metricKey, setMetricKey] = useState<string>('mininet_delta_total_packets')

  const rows = useMemo(() => {
    return (items || []).map((it) => {
      const f = it.fields || {}
      const outMsgs = (toNum(f.algo_sent_msgs) ?? 0) + (toNum(f.algo_broadcast_msgs) ?? 0)
      const inMsgs = toNum(f.algo_recv_msgs) ?? 0
      const validationOk = toNum(f.validation_ok)

      return {
        run_id: it.run_id,
        algorithm: it.algorithm,
        time: it.time || '',
        label: `${String(it.algorithm || 'algo')} • ${String(it.run_id || '').slice(0, 8)}`,
        duration_s: toNum(f.duration_s) ?? null,
        mininet_delta_total_packets: toNum(f.mininet_delta_total_packets) ?? null,
        mininet_delta_total_bytes: toNum(f.mininet_delta_total_bytes) ?? null,
        mininet_delta_rx_packets: toNum(f.mininet_delta_rx_packets) ?? null,
        mininet_delta_tx_packets: toNum(f.mininet_delta_tx_packets) ?? null,
        mininet_delta_rx_bytes: toNum(f.mininet_delta_rx_bytes) ?? null,
        mininet_delta_tx_bytes: toNum(f.mininet_delta_tx_bytes) ?? null,
        algo_out_msgs: outMsgs,
        algo_in_msgs: inMsgs,
        algo_sent_bytes: toNum(f.algo_sent_bytes) ?? null,
        algo_broadcast_bytes: toNum(f.algo_broadcast_bytes) ?? null,
        algo_recv_bytes: toNum(f.algo_recv_bytes) ?? null,
        validation_ok: validationOk == null ? null : validationOk === 1,
        wsn_total_nodes: toNum(f.wsn_total_nodes) ?? null,
        wsn_total_rounds: toNum(f.wsn_total_rounds) ?? null,
        wsn_fnd_round: toNum(f.wsn_fnd_round) ?? null,
        wsn_hnd_round: toNum(f.wsn_hnd_round) ?? null,
        wsn_lnd_round: toNum(f.wsn_lnd_round) ?? null,
        wsn_packets_to_bs: toNum(f.wsn_packets_to_bs) ?? null,
        wsn_packets_to_bs_per_round: toNum(f.wsn_packets_to_bs_per_round) ?? null,
        wsn_energy_spent_j: toNum(f.wsn_energy_spent_j) ?? null,
        wsn_energy_spent_per_round_j: toNum(f.wsn_energy_spent_per_round_j) ?? null,
        wsn_cluster_count_avg: toNum(f.wsn_cluster_count_avg) ?? null,
        wsn_cluster_count_min: toNum(f.wsn_cluster_count_min) ?? null,
        wsn_cluster_count_max: toNum(f.wsn_cluster_count_max) ?? null,
        wsn_cluster_count_last: toNum(f.wsn_cluster_count_last) ?? null,
        wsn_cluster_size_avg: toNum(f.wsn_cluster_size_avg) ?? null,
        wsn_cluster_size_min: toNum(f.wsn_cluster_size_min) ?? null,
        wsn_cluster_size_max: toNum(f.wsn_cluster_size_max) ?? null,
        __fields: f,
      }
    })
  }, [items])

  const hasWsn = useMemo(() => {
    return rows.some((r) => r.wsn_total_nodes != null || r.wsn_fnd_round != null || r.wsn_energy_spent_j != null)
  }, [rows])

  const metricOptions = useMemo(() => {
    const labelByKey: Record<string, string> = {
      duration_s: 'Duration (s)',
      mininet_delta_total_packets: 'Mininet Δ total packets',
      mininet_delta_total_bytes: 'Mininet Δ total bytes',
      mininet_delta_rx_packets: 'Mininet Δ RX packets',
      mininet_delta_tx_packets: 'Mininet Δ TX packets',
      mininet_delta_rx_bytes: 'Mininet Δ RX bytes',
      mininet_delta_tx_bytes: 'Mininet Δ TX bytes',
      algo_out_msgs: 'Algo msgs out (TX+BCAST)',
      algo_in_msgs: 'Algo msgs in (RX)',
      algo_sent_bytes: 'Algo bytes sent',
      algo_broadcast_bytes: 'Algo bytes broadcast',
      algo_recv_bytes: 'Algo bytes received',
      wsn_total_nodes: 'WSN total nodes',
      wsn_total_rounds: 'WSN total rounds',
      wsn_fnd_round: 'WSN FND round',
      wsn_hnd_round: 'WSN HND round',
      wsn_lnd_round: 'WSN LND round',
      wsn_packets_to_bs: 'WSN packets→BS (total)',
      wsn_packets_to_bs_per_round: 'WSN packets→BS / round',
      wsn_energy_spent_j: 'WSN energy spent (J)',
      wsn_energy_spent_per_round_j: 'WSN energy spent / round (J)',
      wsn_cluster_count_avg: 'WSN cluster count avg',
      wsn_cluster_count_min: 'WSN cluster count min',
      wsn_cluster_count_max: 'WSN cluster count max',
      wsn_cluster_count_last: 'WSN cluster count last',
      wsn_cluster_size_avg: 'WSN cluster size avg',
      wsn_cluster_size_min: 'WSN cluster size min',
      wsn_cluster_size_max: 'WSN cluster size max',
    }

    const keys = new Set<string>()
    for (const r of rows) {
      for (const k of Object.keys(r.__fields || {})) keys.add(k)
    }
    for (const k of Object.keys(labelByKey)) keys.add(k)

    const isNumericKey = (k: string): boolean => {
      if (k.endsWith('_json')) return false
      for (const r of rows) {
        const v = (r as any)[k] ?? (r.__fields as any)?.[k]
        if (toNum(v) != null) return true
      }
      return false
    }

    const out = Array.from(keys.values())
      .filter(isNumericKey)
      .map((k) => ({ value: k, label: labelByKey[k] || k }))
      .sort((a, b) => a.label.localeCompare(b.label))

    return out
  }, [rows])

  useEffect(() => {
    if (!metricOptions.length) return
    if (metricOptions.some((o) => o.value === metricKey)) return
    const preferred = hasWsn ? 'wsn_energy_spent_j' : 'mininet_delta_total_packets'
    setMetricKey(metricOptions.some((o) => o.value === preferred) ? preferred : metricOptions[0].value)
  }, [hasWsn, metricOptions, metricKey])

  const totals = useMemo(() => {
    if (!rows.length) return null
    const durations = rows.map((r) => r.duration_s).filter((n): n is number => typeof n === 'number' && Number.isFinite(n))
    const packets = rows
      .map((r) => r.mininet_delta_total_packets)
      .filter((n): n is number => typeof n === 'number' && Number.isFinite(n))
    const bytes = rows
      .map((r) => r.mininet_delta_total_bytes)
      .filter((n): n is number => typeof n === 'number' && Number.isFinite(n))
    return {
      count: rows.length,
      durationAvg: durations.length ? durations.reduce((a, b) => a + b, 0) / durations.length : null,
      packetsAvg: packets.length ? packets.reduce((a, b) => a + b, 0) / packets.length : null,
      bytesAvg: bytes.length ? bytes.reduce((a, b) => a + b, 0) / bytes.length : null,
    }
  }, [rows])

  if (!rows.length) {
    return (
      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
        <div className="text-sm text-gray-500 dark:text-gray-400">Select runs to compare.</div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Compare runs</div>
        <Badge variant="default" size="sm">
          {rows.length} selected
        </Badge>
      </div>

      {totals && (
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <MetricCard title="Runs" value={String(totals.count)} variant="default" />
          <MetricCard title="Avg duration (s)" value={totals.durationAvg == null ? '—' : fmt(totals.durationAvg)} variant="primary" />
          <MetricCard title="Avg Δ packets" value={totals.packetsAvg == null ? '—' : fmt(totals.packetsAvg, 0)} variant="success" />
          <MetricCard title="Avg Δ bytes" value={totals.bytesAvg == null ? '—' : fmt(totals.bytesAvg, 0)} variant="warning" />
        </div>
      )}

      <Card padding="lg" className="overflow-hidden">
        <CardHeader className="mb-2">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <CardTitle className="text-base">Metric explorer</CardTitle>
              <div className="text-xs text-gray-600 dark:text-gray-400">Pick any numeric InfluxDB field and compare across runs.</div>
            </div>
            <div className="w-full sm:w-[360px]">
              <Select
                label="Metric"
                value={metricKey as any}
                onChange={(v) => setMetricKey(String(v))}
                options={metricOptions.map((o) => ({ value: o.value, label: o.label }))}
              />
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={rows.map((r) => ({
                  ...r,
                  metric_value: toNum((r as any)[metricKey] ?? (r.__fields as any)?.[metricKey]),
                }))}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="metric_value" name="Value" fill="#8b5cf6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card padding="lg">
          <CardHeader className="mb-2">
            <CardTitle className="text-base">Duration (s)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="duration_s" name="Duration (s)" fill="#3b82f6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card padding="lg">
          <CardHeader className="mb-2">
            <CardTitle className="text-base">Mininet Δ packets</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="mininet_delta_total_packets" name="Δ packets" fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <Card padding="lg">
          <CardHeader className="mb-2">
            <CardTitle className="text-base">Mininet Δ bytes</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="mininet_delta_total_bytes" name="Δ bytes" fill="#a855f7" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card padding="lg">
          <CardHeader className="mb-2">
            <CardTitle className="text-base">Algorithm traffic (messages)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[260px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={rows}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="algo_out_msgs" name="Out (TX+BCAST)" stackId="msgs" fill="#3b82f6" />
                  <Bar dataKey="algo_in_msgs" name="In (RX)" stackId="msgs" fill="#22c55e" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      {hasWsn && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <Card padding="lg">
            <CardHeader className="mb-2">
              <CardTitle className="text-base">WSN lifetime (rounds)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rows}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="wsn_fnd_round" name="FND" fill="#f97316" />
                    <Bar dataKey="wsn_hnd_round" name="HND" fill="#a855f7" />
                    <Bar dataKey="wsn_lnd_round" name="LND" fill="#0ea5e9" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card padding="lg">
            <CardHeader className="mb-2">
              <CardTitle className="text-base">WSN energy spent (J)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rows}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="wsn_energy_spent_j" name="Energy spent (J)" fill="#ef4444" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {hasWsn && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <Card padding="lg">
            <CardHeader className="mb-2">
              <CardTitle className="text-base">WSN packets → BS</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rows}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="wsn_packets_to_bs" name="Packets to BS" fill="#0ea5e9" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <Card padding="lg">
            <CardHeader className="mb-2">
              <CardTitle className="text-base">WSN cluster heads</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={rows}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                    <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={0} angle={-20} textAnchor="end" height={60} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="wsn_cluster_count_avg" name="Cluster count (avg)" fill="#f59e0b" />
                    <Bar dataKey="wsn_cluster_count_max" name="Cluster count (max)" fill="#f97316" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-800 flex items-center justify-between">
          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Metrics table</div>
          <Badge variant="default" size="sm">
            {rows.length}
          </Badge>
        </div>
        <div className="max-h-[520px] overflow-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
              <tr>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Run</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Algorithm</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Duration</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Δ pkts</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Δ bytes</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Msgs out</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Msgs in</th>
                <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Valid</th>
                {hasWsn && (
                  <>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">FND</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">HND</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">LND</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Energy (J)</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Pkts→BS</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">CH avg</th>
                    <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">CH max</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.run_id} className="border-b border-gray-100 dark:border-gray-800">
                  <td className="py-2 px-3 font-mono text-xs text-gray-900 dark:text-gray-100">{String(r.run_id || '').slice(0, 10) || '—'}</td>
                  <td className="py-2 px-3 text-xs text-gray-700 dark:text-gray-300">{r.algorithm || '—'}</td>
                  <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.duration_s == null ? '—' : fmt(r.duration_s)}</td>
                  <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.mininet_delta_total_packets == null ? '—' : fmt(r.mininet_delta_total_packets, 0)}</td>
                  <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.mininet_delta_total_bytes == null ? '—' : fmt(r.mininet_delta_total_bytes, 0)}</td>
                  <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{fmt(r.algo_out_msgs, 0)}</td>
                  <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{fmt(r.algo_in_msgs, 0)}</td>
                  <td className="py-2 px-3">
                    <Badge variant={r.validation_ok === true ? 'success' : r.validation_ok === false ? 'warning' : 'default'} size="sm">
                      {r.validation_ok === true ? 'OK' : r.validation_ok === false ? 'FAIL' : '—'}
                    </Badge>
                  </td>
                  {hasWsn && (
                    <>
                      <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.wsn_fnd_round == null ? '—' : fmt(r.wsn_fnd_round, 0)}</td>
                      <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.wsn_hnd_round == null ? '—' : fmt(r.wsn_hnd_round, 0)}</td>
                      <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.wsn_lnd_round == null ? '—' : fmt(r.wsn_lnd_round, 0)}</td>
                      <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.wsn_energy_spent_j == null ? '—' : fmt(r.wsn_energy_spent_j, 3)}</td>
                      <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.wsn_packets_to_bs == null ? '—' : fmt(r.wsn_packets_to_bs, 0)}</td>
                      <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.wsn_cluster_count_avg == null ? '—' : fmt(r.wsn_cluster_count_avg, 2)}</td>
                      <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{r.wsn_cluster_count_max == null ? '—' : fmt(r.wsn_cluster_count_max, 0)}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
