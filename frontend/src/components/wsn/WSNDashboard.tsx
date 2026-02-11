import { useMemo, useState } from 'react'
import { Badge } from '@/components/atoms/Badge'
import { MetricCard } from '@/components/molecules/MetricCard'
import EnergyVisualization, { type WSNEnergyPoint } from './EnergyVisualization'
import NetworkLifetimeChart, { type WSNLifetime, type WSNLifetimePoint } from './NetworkLifetimeChart'
import ProtocolComparison from './ProtocolComparison'
import RoundActivityChart, { type WSNActivityPoint } from './RoundActivityChart'
import RoundMetricsTable, { type WSNRoundRow } from './RoundMetricsTable'
import WSNNodesTable from './WSNNodesTable'

const protocolLabelFromTemplateId = (templateId?: string) => {
  const id = String(templateId || '').trim().toLowerCase()
  if (id === 'wsn-leach') return 'LEACH'
  if (id === 'wsn-leach-c') return 'LEACH-C'
  if (id === 'wsn-pegasis') return 'PEGASIS'
  if (id === 'wsn-sep') return 'SEP'
  if (id === 'wsn-teen') return 'TEEN'
  return 'WSN'
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

const isFiniteNumber = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

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

export default function WSNDashboard({ templateId, events }: { templateId?: string; events: unknown[] }) {
  const protocolLabel = useMemo(() => protocolLabelFromTemplateId(templateId), [templateId])
  const [showAllRounds, setShowAllRounds] = useState(false)

  const { roundSeries, lifetime } = useMemo(() => {
    type NodeSnapshot = {
      ts: number
      current_energy: number | null
      is_alive: boolean | null
      role: string | null
      cluster_id: number | null
      packets_to_bs_cum: number | null
    }

    const roundByNo = new Map<number, Record<string, unknown>>() // explicit `round_metrics` events
    const snapshotsByRound = new Map<number, Map<number, NodeSnapshot>>() // derived from per-node events
    const deathRoundByNode = new Map<number, number>()
    const baseStationNodes = new Set<number>()
    const packetsToBsByRound = new Map<number, number>()
    const life: WSNLifetime = { fnd_round: null, hnd_round: null, lnd_round: null }

    const upsertSnapshot = (round: number, nodeId: number, patch: Partial<NodeSnapshot>, ts: number) => {
      let byNode = snapshotsByRound.get(round)
      if (!byNode) {
        byNode = new Map()
        snapshotsByRound.set(round, byNode)
      }
      const prev = byNode.get(nodeId)
      const next: NodeSnapshot = {
        ts: Math.max(prev?.ts ?? 0, ts),
        current_energy: prev?.current_energy ?? null,
        is_alive: prev?.is_alive ?? null,
        role: prev?.role ?? null,
        cluster_id: prev?.cluster_id ?? null,
        packets_to_bs_cum: prev?.packets_to_bs_cum ?? null,
        ...patch,
      }
      byNode.set(nodeId, next)
    }

    for (const raw of events || []) {
      const e = asRecord(raw)
      if (!e) continue
      const typ = String(e.type || '').toLowerCase()
      const ts = toNum(e.ts) ?? 0

      if (typ === 'round_metrics') {
        const r = toNum(e.round)
        if (r == null) continue
        const prev = roundByNo.get(r)
        const prevTs = prev ? toNum(prev.ts) ?? 0 : -1
        if (!prev || ts >= prevTs) roundByNo.set(r, e)
        continue
      }

      if (typ === 'round_summary' || typ === 'energy') {
        const r = toNum(e.round)
        const nodeId = toNum(e.node_id) ?? toNum(e.node)
        if (r == null || nodeId == null) continue

        const role = String(e.role || '').trim().toLowerCase()
        if (role === 'base_station') baseStationNodes.add(nodeId)

        if (typ === 'round_summary') {
          upsertSnapshot(
            r,
            nodeId,
            {
              current_energy: toNum(e.current_energy),
              is_alive: toBool(e.is_alive),
              role: role || null,
              cluster_id: toNum(e.cluster_id),
              packets_to_bs_cum: toNum(e.packets_to_bs),
            },
            ts
          )
        } else {
          upsertSnapshot(
            r,
            nodeId,
            {
              current_energy: toNum(e.current_energy),
              is_alive: toBool(e.is_alive),
              role: role || null,
            },
            ts
          )
        }
        continue
      }

      if (typ === 'packet_to_bs') {
        const r = toNum(e.round)
        if (r == null) continue
        packetsToBsByRound.set(r, (packetsToBsByRound.get(r) || 0) + 1)
        continue
      }

      if (typ === 'node_death') {
        const r = toNum(e.round)
        const nodeId = toNum(e.node_id) ?? toNum(e.node)
        if (r != null && nodeId != null && !deathRoundByNode.has(nodeId)) deathRoundByNode.set(nodeId, r)
        continue
      }

      if (typ === 'fnd') {
        const r = toNum(e.round)
        if (r != null && (life.fnd_round == null || r < Number(life.fnd_round))) life.fnd_round = r
        continue
      }
      if (typ === 'hnd') {
        const r = toNum(e.round)
        if (r != null && (life.hnd_round == null || r < Number(life.hnd_round))) life.hnd_round = r
        continue
      }
      if (typ === 'lnd') {
        const r = toNum(e.round)
        if (r != null && (life.lnd_round == null || r < Number(life.lnd_round))) life.lnd_round = r
        continue
      }

      if (typ === 'simulation_complete') {
        const lf = asRecord(e.lifetime)
        if (lf) {
          const fnd = toNum(lf.fnd_round)
          const hnd = toNum(lf.hnd_round)
          const lnd = toNum(lf.lnd_round)
          if (fnd != null) life.fnd_round = fnd
          if (hnd != null) life.hnd_round = hnd
          if (lnd != null) life.lnd_round = lnd
        }
      }
    }

    // Prefer explicit network-wide `round_metrics` if present.
    if (roundByNo.size) {
      const rounds = Array.from(roundByNo.values())
        .map((e) => ({
          round: toNum(e.round) ?? 0,
          alive_nodes: toNum(e.alive_nodes) ?? 0,
          dead_nodes: toNum(e.dead_nodes) ?? 0,
          total_energy: toNum(e.total_energy) ?? 0,
          avg_energy: toNum(e.avg_energy) ?? 0,
          min_energy: toNum(e.min_energy) ?? 0,
          max_energy: toNum(e.max_energy) ?? 0,
          energy_variance: toNum(e.energy_variance) ?? 0,
          packets_to_bs: toNum(e.packets_to_bs) ?? 0,
          cluster_count: toNum(e.cluster_count) ?? 0,
        }))
        .filter((r) => Number.isFinite(r.round))
        .sort((a, b) => a.round - b.round)

      return { roundSeries: rounds, lifetime: life }
    }

    // Fallback: derive network-wide metrics from per-node `round_summary` / `energy` / `packet_to_bs` events.
    const nodeIds = new Set<number>()
    for (const [round, byNode] of snapshotsByRound.entries()) {
      if (!Number.isFinite(round)) continue
      for (const nodeId of byNode.keys()) nodeIds.add(nodeId)
    }
    for (const nodeId of deathRoundByNode.keys()) nodeIds.add(nodeId)
    for (const bs of baseStationNodes.values()) nodeIds.delete(bs)

    const sortedNodeIds = Array.from(nodeIds.values()).sort((a, b) => a - b)
    const totalNodes = sortedNodeIds.length

    const sortedRounds = Array.from(
      new Set<number>([...snapshotsByRound.keys(), ...packetsToBsByRound.keys()].filter((n) => Number.isFinite(Number(n)) && Number(n) > 0).map(Number))
    ).sort((a, b) => a - b)

    const lastByNode = new Map<number, NodeSnapshot>()

    const derived = sortedRounds.map((roundNo) => {
      const perRound = snapshotsByRound.get(roundNo) || new Map<number, NodeSnapshot>()
      for (const [nodeId, snap] of perRound.entries()) lastByNode.set(nodeId, snap)

      let aliveNodes = 0
      let deadNodes = 0
      const energies: number[] = []
      const clusterHeadCountIds = new Set<number>()
      const clusterIds = new Set<number>()

      for (const nodeId of sortedNodeIds) {
        const deathRound = deathRoundByNode.get(nodeId)
        const isDead = deathRound != null && Number.isFinite(deathRound) && deathRound <= roundNo
        const snap = perRound.get(nodeId) || lastByNode.get(nodeId)
        const aliveFlag = snap?.is_alive
        const isAlive = (aliveFlag == null ? !isDead : Boolean(aliveFlag)) && !isDead

        if (isAlive) {
          aliveNodes += 1
          const e = snap?.current_energy
          energies.push(isFiniteNumber(e) ? e : 0)
          const role = String(snap?.role || '').toLowerCase()
          if (role === 'cluster_head') clusterHeadCountIds.add(nodeId)
          if (snap?.cluster_id != null && Number.isFinite(Number(snap.cluster_id))) clusterIds.add(Number(snap.cluster_id))
        } else {
          deadNodes += 1
        }
      }

      const totalEnergy = energies.reduce((acc, v) => acc + (Number.isFinite(v) ? v : 0), 0)
      const avgEnergy = aliveNodes > 0 ? totalEnergy / aliveNodes : 0
      const minEnergy = energies.length ? Math.min(...energies) : 0
      const maxEnergy = energies.length ? Math.max(...energies) : 0
      const variance =
        energies.length > 1
          ? energies.reduce((acc, v) => acc + (v - avgEnergy) ** 2, 0) / energies.length
          : 0

      const clusterCount = Math.max(clusterHeadCountIds.size, clusterIds.size)
      const packetsToBs = packetsToBsByRound.get(roundNo) || 0

      return {
        round: roundNo,
        alive_nodes: aliveNodes,
        dead_nodes: deadNodes,
        total_energy: totalEnergy,
        avg_energy: avgEnergy,
        min_energy: minEnergy,
        max_energy: maxEnergy,
        energy_variance: variance,
        packets_to_bs: packetsToBs,
        cluster_count: clusterCount,
      }
    })

    // If lifetime events weren't emitted, derive from `node_death` events.
    if (life.fnd_round == null || life.hnd_round == null || life.lnd_round == null) {
      const deathRounds = Array.from(deathRoundByNode.entries())
        .filter(([nodeId]) => nodeIds.has(nodeId))
        .map(([, r]) => r)
        .filter((r) => Number.isFinite(r))
        .sort((a, b) => a - b)

      if (life.fnd_round == null && deathRounds.length) life.fnd_round = deathRounds[0]

      const half = Math.floor(totalNodes / 2)
      if (life.hnd_round == null && half >= 1 && deathRounds.length >= half) life.hnd_round = deathRounds[half - 1]

      if (life.lnd_round == null && totalNodes > 0 && deathRounds.length >= totalNodes) life.lnd_round = deathRounds[totalNodes - 1]
    }

    return { roundSeries: derived, lifetime: life }
  }, [events])

  const energySeries: WSNEnergyPoint[] = useMemo(() => {
    return roundSeries.map((r) => ({
      round: r.round,
      total_energy: r.total_energy,
      avg_energy: r.avg_energy,
      min_energy: r.min_energy,
      max_energy: r.max_energy,
    }))
  }, [roundSeries])

  const lifetimeSeries: WSNLifetimePoint[] = useMemo(() => {
    return roundSeries.map((r) => ({
      round: r.round,
      alive_nodes: r.alive_nodes,
      dead_nodes: r.dead_nodes,
    }))
  }, [roundSeries])

  const activitySeries: WSNActivityPoint[] = useMemo(() => {
    return roundSeries.map((r) => ({
      round: r.round,
      packets_to_bs: r.packets_to_bs,
      cluster_count: r.cluster_count,
    }))
  }, [roundSeries])

  const tableRows: WSNRoundRow[] = useMemo(() => {
    const src = showAllRounds ? roundSeries : roundSeries.slice(-50)
    return src.map((r) => ({
      round: r.round,
      alive_nodes: r.alive_nodes,
      dead_nodes: r.dead_nodes,
      cluster_count: r.cluster_count,
      packets_to_bs: r.packets_to_bs,
      total_energy: r.total_energy,
      avg_energy: r.avg_energy,
      min_energy: r.min_energy,
      max_energy: r.max_energy,
      energy_variance: r.energy_variance ?? 0,
    }))
  }, [roundSeries, showAllRounds])

  const summary = useMemo(() => {
    if (!roundSeries.length) {
      return {
        rounds: null as number | null,
        alive: null as number | null,
        dead: null as number | null,
        totalEnergy: null as number | null,
        initialTotalEnergy: null as number | null,
        packetsToBsTotal: null as number | null,
        clusters: null as number | null,
      }
    }
    const last = roundSeries[roundSeries.length - 1]
    const initialTotalEnergy = roundSeries[0]?.total_energy ?? null
    const packetsToBsTotal = roundSeries.reduce((acc, r) => acc + (toNum(r.packets_to_bs) ?? 0), 0)
    return {
      rounds: last.round,
      alive: last.alive_nodes,
      dead: last.dead_nodes,
      totalEnergy: last.total_energy,
      initialTotalEnergy,
      packetsToBsTotal,
      clusters: last.cluster_count,
    }
  }, [roundSeries])

  if (
    !roundSeries.length &&
    !(
      (lifetime.fnd_round != null && Number.isFinite(Number(lifetime.fnd_round))) ||
      (lifetime.hnd_round != null && Number.isFinite(Number(lifetime.hnd_round))) ||
      (lifetime.lnd_round != null && Number.isFinite(Number(lifetime.lnd_round)))
    )
  ) {
    return (
      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">WSN Metrics</div>
          <Badge variant="default" size="sm">
            {protocolLabel}
          </Badge>
        </div>
        <div className="text-sm text-gray-500 dark:text-gray-400">
          No WSN metrics yet. Run the algorithm and wait for the first round to complete.
        </div>
      </div>
    )
  }

  const energySpent =
    summary.initialTotalEnergy == null || summary.totalEnergy == null ? null : Math.max(0, summary.initialTotalEnergy - summary.totalEnergy)

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">WSN Metrics</div>
        <div className="flex items-center gap-2">
          <Badge variant="default" size="sm">
            {protocolLabel}
          </Badge>
          <Badge variant="default" size="sm">
            Source: algo events
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-5 gap-3">
        <MetricCard title="FND (round)" value={lifetime.fnd_round ?? '—'} />
        <MetricCard title="HND (round)" value={lifetime.hnd_round ?? '—'} />
        <MetricCard title="LND (round)" value={lifetime.lnd_round ?? '—'} />
        <MetricCard title="Alive" value={summary.alive ?? '—'} />
        <MetricCard title="Energy spent (J)" value={energySpent == null ? '—' : fmt(energySpent)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <NetworkLifetimeChart data={lifetimeSeries} lifetime={lifetime} />
        <EnergyVisualization data={energySeries} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <RoundActivityChart data={activitySeries} />
        <RoundMetricsTable
          rows={tableRows}
          totalRounds={roundSeries.length}
          toggleLabel={showAllRounds ? 'Show last 50' : 'Show all'}
          onToggle={() => setShowAllRounds((v) => !v)}
          toggleDisabled={!roundSeries.length}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="lg:col-span-2 space-y-3">
          <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
            <div className="flex items-center justify-between gap-2 mb-3">
              <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Round stats</div>
              <Badge variant="default" size="sm">
                Latest round: <span className="font-mono">{summary.rounds == null ? '—' : String(summary.rounds)}</span>
              </Badge>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
              <MetricCard title="Clusters" value={summary.clusters ?? '—'} />
              <MetricCard title="Packets to BS" value={summary.packetsToBsTotal == null ? '—' : String(Math.round(summary.packetsToBsTotal))} />
              <MetricCard title="Residual total (J)" value={summary.totalEnergy == null ? '—' : fmt(summary.totalEnergy)} />
              <MetricCard title="Residual avg (J)" value={roundSeries.length ? fmt(roundSeries[roundSeries.length - 1].avg_energy) : '—'} />
            </div>
          </div>
          <WSNNodesTable events={events} />
        </div>
        <ProtocolComparison protocolLabel={protocolLabel} lifetime={lifetime} />
      </div>
    </div>
  )
}
