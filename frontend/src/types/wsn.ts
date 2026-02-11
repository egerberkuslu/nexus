export type WSNProtocol = 'leach' | 'leach-c' | 'pegasis' | 'sep' | 'teen'

export type WSNRole = 'sensor' | 'cluster_head' | 'chain_leader' | 'base_station'

export interface WSNConfig {
  protocol: WSNProtocol
  p?: number
  max_rounds?: number
  packet_size?: number
  initial_energy?: number

  // SEP heterogeneity
  alpha?: number
  m?: number

  // TEEN thresholds
  hard_threshold?: number
  soft_threshold?: number

  // Optional simulation params (first-order radio model)
  field_size?: [number, number]
  bs_position?: [number, number]
  e_elec?: number
  e_amp?: number
  e_da?: number
}

export type WSNAlgorithmEvent =
  | WSNNodeEnergyEvent
  | WSNNodeDeathEvent
  | WSNRoleChangeEvent
  | WSNClusterInfoEvent
  | WSNClusterFormedEvent
  | WSNRoundSummaryEvent
  | WSNRoundMetricsEvent
  | WSNLifetimeEvent
  | WSNSimulationCompleteEvent

export interface WSNEventBase {
  ts: number
  node: number
  type: string
  [key: string]: unknown
}

export interface WSNNodeEnergyEvent extends WSNEventBase {
  type: 'energy'
  round: number
  node_id: number
  current_energy: number
  initial_energy: number
  residual_ratio: number
  is_alive: boolean
  role: WSNRole | string
  position?: [number, number] | number[]
}

export interface WSNNodeDeathEvent extends WSNEventBase {
  type: 'node_death'
  round: number
  node_id: number
  total_packets_sent?: number
  total_energy_consumed?: number
  times_as_ch?: number
}

export interface WSNRoleChangeEvent extends WSNEventBase {
  type: 'role_change'
  round: number
  old_role: string
  new_role: string
  cluster_id?: number | null
}

export interface WSNClusterInfoEvent extends WSNEventBase {
  type: 'cluster_info'
  round: number
  node_id: number
  role: string
  cluster_id?: number | null
  cluster_head_id?: number | null
  is_ch: boolean
  members?: number[]
}

export interface WSNClusterFormedEvent extends WSNEventBase {
  type: 'cluster_formed'
  round: number
  ch_id: number
  members: number[]
  size: number
}

export interface WSNRoundSummaryEvent extends WSNEventBase {
  type: 'round_summary'
  round: number
  node_id: number
  is_alive: boolean
  current_energy: number
  energy_consumed: number
  role: string
  cluster_id?: number | null
  packets_sent: number
  packets_received: number
  packets_to_bs: number
}

export interface WSNRoundMetricsEvent extends WSNEventBase {
  type: 'round_metrics'
  round: number
  alive_nodes: number
  dead_nodes: number
  total_energy: number
  avg_energy: number
  min_energy: number
  max_energy: number
  energy_variance: number
  packets_to_bs: number
  cluster_count: number
  ch_ids: number[]
  newly_dead: number[]
}

export type WSNLifetimeEvent =
  | (WSNEventBase & { type: 'fnd'; round: number; dead_node_id: number })
  | (WSNEventBase & { type: 'hnd'; round: number; dead_count: number })
  | (WSNEventBase & { type: 'lnd'; round: number })

export interface WSNSimulationCompleteEvent extends WSNEventBase {
  type: 'simulation_complete'
  summary: Record<string, unknown> | null
  lifetime: {
    fnd_round?: number | null
    hnd_round?: number | null
    lnd_round?: number | null
    stability_period?: number
    total_nodes?: number
    total_packets_delivered?: number
    total_energy_consumed?: number
    [key: string]: unknown
  }
}
