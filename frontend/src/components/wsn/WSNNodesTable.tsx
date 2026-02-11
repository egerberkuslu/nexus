import { useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'
import { Input } from '@/components/atoms/Input'

type NodeRow = {
  node_id: number
  role: string
  is_alive: boolean | null
  current_energy: number | null
  initial_energy: number | null
  residual_ratio: number | null
  cluster_id: number | null
  packets_to_bs: number | null
  ts: number
}

const asRecord = (v: unknown): Record<string, unknown> | null => {
  if (!v || typeof v !== 'object') return null
  return v as Record<string, unknown>
}

const toNum = (v: unknown): number | null => {
  if (v == null) return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

const toBool = (v: unknown): boolean | null => {
  if (v == null) return null
  if (typeof v === 'boolean') return v
  if (typeof v === 'number') return v !== 0
  const s = String(v).trim().toLowerCase()
  if (s === 'true' || s === '1' || s === 'yes' || s === 'y' || s === 'on') return true
  if (s === 'false' || s === '0' || s === 'no' || s === 'n' || s === 'off') return false
  return null
}

const fmt = (v: unknown, digits = 3): string => {
  const n = Number(v)
  if (!Number.isFinite(n)) return '—'
  if (Math.abs(n) >= 1000) return String(Math.round(n))
  return n.toFixed(digits)
}

const roleVariant = (roleRaw: string): 'default' | 'success' | 'warning' | 'error' | 'info' | 'primary' => {
  const role = String(roleRaw || '').trim().toLowerCase()
  if (role === 'base_station') return 'error'
  if (role === 'cluster_head') return 'info'
  if (role === 'chain_leader') return 'primary'
  if (role === 'sensor') return 'success'
  return 'default'
}

export default function WSNNodesTable({ events, maxRows = 40 }: { events: unknown[]; maxRows?: number }) {
  const [q, setQ] = useState('')

  const rows = useMemo(() => {
    const lastByNode = new Map<number, NodeRow>()

    for (const raw of Array.isArray(events) ? events : []) {
      const e = asRecord(raw)
      if (!e) continue
      const typ = String(e.type || '').toLowerCase()
      if (!(typ === 'round_summary' || typ === 'energy')) continue

      const nodeId = toNum(e.node_id) ?? toNum(e.node)
      if (nodeId == null) continue
      const nid = Math.trunc(nodeId)
      if (!Number.isFinite(nid)) continue

      const ts = toNum(e.ts) ?? 0
      const role = String(e.role || '').trim().toLowerCase()
      const isAlive = toBool(e.is_alive)

      const prev = lastByNode.get(nid)
      const prevTs = prev?.ts ?? -1
      if (ts < prevTs) continue

      const currentEnergy = toNum(e.current_energy)
      const initialEnergy = toNum(e.initial_energy)
      const residualRatio = toNum(e.residual_ratio)
      const clusterId = toNum(e.cluster_id)

      const packetsToBs =
        toNum(e.packets_to_bs) ??
        toNum(e.total_packets_to_bs) ??
        toNum(e.totalPacketsToBs) ??
        null

      lastByNode.set(nid, {
        node_id: nid,
        role,
        is_alive: isAlive,
        current_energy: currentEnergy,
        initial_energy: initialEnergy,
        residual_ratio: residualRatio,
        cluster_id: clusterId,
        packets_to_bs: packetsToBs,
        ts,
      })
    }

    const list = Array.from(lastByNode.values()).filter((r) => r.role !== 'base_station')

    // Default sort: lowest energy first (helps spot dying nodes).
    list.sort((a, b) => {
      const ea = typeof a.current_energy === 'number' ? a.current_energy : Number.POSITIVE_INFINITY
      const eb = typeof b.current_energy === 'number' ? b.current_energy : Number.POSITIVE_INFINITY
      if (ea !== eb) return ea - eb
      return a.node_id - b.node_id
    })

    const query = String(q || '').trim().toLowerCase()
    const filtered = query
      ? list.filter((r) => {
          const id = String(r.node_id)
          const role = String(r.role || '')
          const cluster = r.cluster_id == null ? '' : String(r.cluster_id)
          return id.includes(query) || role.includes(query) || cluster.includes(query)
        })
      : list

    return filtered.slice(0, Math.max(10, Math.min(200, Number(maxRows) || 40)))
  }, [events, maxRows, q])

  return (
    <Card padding="lg">
      <CardHeader className="mb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-base">Nodes (live)</CardTitle>
          <Badge variant="default" size="sm">
            {rows.length}
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-3">
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by node / role / cluster…" />
        </div>

        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden">
          <div className="max-h-[360px] overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
                <tr>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Node</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Role</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Alive</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Energy (J)</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Residual</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Cluster</th>
                  <th className="text-left py-2 px-3 text-xs font-semibold text-gray-700 dark:text-gray-300">Pkts→BS</th>
                </tr>
              </thead>
              <tbody>
                {rows.length ? (
                  rows.map((r) => {
                    const alive = r.is_alive
                    const roleLabel = r.role ? r.role.replace(/_/g, ' ').toUpperCase() : '—'
                    const residual =
                      r.residual_ratio != null && Number.isFinite(Number(r.residual_ratio))
                        ? `${Math.round(Number(r.residual_ratio) * 100)}%`
                        : r.initial_energy && r.current_energy != null
                          ? `${Math.round((Number(r.current_energy) / Number(r.initial_energy)) * 100)}%`
                          : '—'
                    return (
                      <tr key={r.node_id} className="border-b border-gray-100 dark:border-gray-800">
                        <td className="py-2 px-3 font-mono text-xs text-gray-900 dark:text-gray-100">{r.node_id}</td>
                        <td className="py-2 px-3">
                          <Badge variant={roleVariant(r.role)} size="sm">
                            {roleLabel}
                          </Badge>
                        </td>
                        <td className="py-2 px-3">
                          <Badge variant={alive === false ? 'error' : alive === true ? 'success' : 'default'} size="sm">
                            {alive === false ? 'DEAD' : alive === true ? 'ALIVE' : '—'}
                          </Badge>
                        </td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">
                          {r.current_energy == null ? '—' : fmt(r.current_energy)}
                        </td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">{residual}</td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">
                          {r.cluster_id == null ? '—' : String(Math.round(Number(r.cluster_id)))}
                        </td>
                        <td className="py-2 px-3 font-mono text-xs text-gray-700 dark:text-gray-300">
                          {r.packets_to_bs == null ? '—' : String(Math.round(Number(r.packets_to_bs)))}
                        </td>
                      </tr>
                    )
                  })
                ) : (
                  <tr>
                    <td colSpan={7} className="py-10 text-center text-sm text-gray-500 dark:text-gray-400">
                      Waiting for `round_summary` / `energy` events…
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

