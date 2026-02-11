// Topology and Network Types

export interface Project {
  id: string
  name: string
  description: string
  created_at: string
  updated_at: string
}

export interface Topology {
  id: string
  project_id: string
  name: string
  description: string
  version: number
  status: 'draft' | 'active' | 'archived'
  nodes: Node[]
  links: Link[]
  controllers: Controller[]
  created_at: string
  updated_at: string
}

export type DeviceType =
  | 'host'
  | 'switch'
  | 'router'
  | 'ap'
  | 'station'
  | 'p4switch'
  | 'controller'

export interface Node {
  id: string
  name: string
  device_type: DeviceType
  properties: {
    ip?: string
    mac?: string
    cpu?: number
    memory?: number
    dpid?: string
    // Docker-related properties (applicable when dockerized=true)
    dockerized?: boolean
    docker_image?: string
    docker_command?: string
    docker_environment?: Record<string, string>
    docker_volumes?: string[]
    // Wireless properties (for AP and Station)
    ssid?: string
    channel?: string
    mode?: string
    security?: string
    password?: string
    position?: string
    [key: string]: any
  }
  position?: {
    x: number
    y: number
  }
}

export interface Link {
  id: string
  source: string
  target: string
  properties: {
    bandwidth?: string
    delay?: string
    loss?: number
    jitter?: string
    [key: string]: any
  }
}

export interface Controller {
  id: string
  name: string
  controller_type: 'osken' | 'ryu' | 'opendaylight' | 'onos' | 'custom'
  ip: string
  port: number
  config: {
    [key: string]: any
  }
}

export type ProtocolType = 'OSPF' | 'BGP' | 'RIP' | 'IS-IS' | 'STATIC'

export interface ProtocolConfig {
  device: string
  protocol: ProtocolType
  config: {
    [key: string]: any
  }
}

export interface EmulationStatus {
  topology_id: string
  status: 'stopped' | 'starting' | 'running' | 'paused' | 'error'
  message?: string
  started_at?: string
  devices?: string[]
  uptime_seconds?: number
  device_count?: number
  link_count?: number
  metadata?: Record<string, any>
}

export interface EmulationControlResponse {
  success: boolean
  message: string
  emulation_id?: string
}

export interface DeviceMetrics {
  device: string
  timestamp: string
  interfaces: {
    [key: string]: {
      rx_bytes: number
      tx_bytes: number
      rx_packets: number
      tx_packets: number
      rx_errors: number
      tx_errors: number
    }
  }
  stats?: {
    rx_bytes: number
    tx_bytes: number
    rx_packets: number
    tx_packets: number
  }
  cpu: {
    total_cpu_percent: number
    process_count: number
  }
  memory: {
    total_mb: number
    used_mb: number
    free_mb: number
  }
}

export type SnapshotType = 'topology_only' | 'docker_commit' | 'criu_live' | 'hybrid_full'
export type SnapshotStatus = 'pending' | 'capturing' | 'captured' | 'failed' | 'restoring' | 'restored'

export interface Snapshot {
  id: string
  topology_id?: string
  emulation_id?: string
  name: string
  description?: string
  snapshot_type: SnapshotType
  status: SnapshotStatus
  mongo_state_id?: string
  checkpoint_path?: string
  size_bytes?: number
  compressed: boolean
  created_at: string
  captured_at?: string
  restored_at?: string
  expires_at?: string
  device_count?: number
  container_count?: number
  criu_available?: boolean
  error_message?: string
  extra_metadata?: Record<string, any>
  target_containers?: string[]
  compression?: boolean
  include_routing_tables?: boolean
  include_flow_tables?: boolean
  include_arp_tables?: boolean
  // Legacy field for backward compatibility
  devices?: string[]
  state?: {
    [key: string]: any
  }
}

export interface SnapshotSchedule {
  id: string
  name: string
  description?: string
  topology_id?: string
  cron_expression: string
  snapshot_type: SnapshotType
  is_active: boolean
  retention_count?: number
  retention_days?: number
  last_run_at?: string
  next_run_at?: string
  last_snapshot_id?: string
  run_count: number
  failure_count: number
  created_at: string
  updated_at?: string
  target_containers?: string[]
  compression?: boolean
  include_routing_tables?: boolean
  include_flow_tables?: boolean
  include_arp_tables?: boolean
}

export interface ScheduleCreate {
  name: string
  description?: string
  topology_id?: string
  cron_expression: string
  snapshot_type: SnapshotType
  retention_count?: number
  retention_days?: number
  target_containers?: string[]
  compression?: boolean
  include_routing_tables?: boolean
  include_flow_tables?: boolean
  include_arp_tables?: boolean
}

export interface ScheduleUpdate {
  name?: string
  description?: string
  is_active?: boolean
  cron_expression?: string
  snapshot_type?: SnapshotType
  retention_count?: number
  retention_days?: number
  target_containers?: string[]
  compression?: boolean
  include_routing_tables?: boolean
  include_flow_tables?: boolean
  include_arp_tables?: boolean
}

