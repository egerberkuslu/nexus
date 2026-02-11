import { useEffect, useState } from 'react'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import { monitoringAPI } from '@services/api'

interface MetricsData {
  timestamp: string
  rx_bytes: number
  tx_bytes: number
  rx_packets: number
  tx_packets: number
  cpu_percent: number
  memory_percent: number
}

interface MonitoringChartsProps {
  device?: string
  topologyId?: string
}

export default function MonitoringCharts({
  device,
  topologyId,
}: MonitoringChartsProps) {
  const [metricsHistory, setMetricsHistory] = useState<MetricsData[]>([])

  // Fetch device metrics
  const { data: deviceMetrics } = useQuery({
    queryKey: ['device-metrics', device],
    queryFn: async () => {
      if (!device) return null
      const response = await monitoringAPI.deviceMetrics(device, topologyId)
      return response.data
    },
    enabled: !!device,
    refetchInterval: 5000, // Refresh every 5 seconds
  })

  // Fetch topology metrics
  const { data: topologyMetrics } = useQuery({
    queryKey: ['topology-metrics', topologyId],
    queryFn: async () => {
      if (!topologyId) return null
      const response = await monitoringAPI.topologyMetrics(topologyId)
      return response.data
    },
    enabled: !!topologyId,
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  // Update metrics history
  useEffect(() => {
    if (deviceMetrics) {
      const newMetric: MetricsData = {
        timestamp: new Date().toLocaleTimeString(),
        rx_bytes: deviceMetrics.stats?.rx_bytes || 0,
        tx_bytes: deviceMetrics.stats?.tx_bytes || 0,
        rx_packets: deviceMetrics.stats?.rx_packets || 0,
        tx_packets: deviceMetrics.stats?.tx_packets || 0,
        cpu_percent: deviceMetrics.cpu?.total_cpu_percent || 0,
        memory_percent:
          (deviceMetrics.memory?.used_mb / deviceMetrics.memory?.total_mb) *
            100 || 0,
      }

      setMetricsHistory((prev) => {
        const updated = [...prev, newMetric]
        // Keep last 20 data points
        return updated.slice(-20)
      })
    }
  }, [deviceMetrics])

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  return (
    <div className="space-y-6">
      {/* Network Traffic Chart */}
      <div className="bg-gray-800 p-6 rounded-lg">
        <h3 className="text-lg font-semibold text-white mb-4">
          Network Traffic (Bytes)
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={metricsHistory}>
            <defs>
              <linearGradient id="colorRx" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.8} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="colorTx" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.8} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="timestamp"
              stroke="#9ca3af"
              tick={{ fill: '#9ca3af' }}
            />
            <YAxis stroke="#9ca3af" tick={{ fill: '#9ca3af' }} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1f2937',
                border: '1px solid #374151',
                borderRadius: '0.5rem',
              }}
              labelStyle={{ color: '#fff' }}
              formatter={(value: number) => formatBytes(value)}
            />
            <Legend wrapperStyle={{ color: '#fff' }} />
            <Area
              type="monotone"
              dataKey="rx_bytes"
              stroke="#3b82f6"
              fillOpacity={1}
              fill="url(#colorRx)"
              name="RX Bytes"
            />
            <Area
              type="monotone"
              dataKey="tx_bytes"
              stroke="#10b981"
              fillOpacity={1}
              fill="url(#colorTx)"
              name="TX Bytes"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Packet Rate Chart */}
      <div className="bg-gray-800 p-6 rounded-lg">
        <h3 className="text-lg font-semibold text-white mb-4">
          Packet Rate (Packets/s)
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={metricsHistory}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="timestamp"
              stroke="#9ca3af"
              tick={{ fill: '#9ca3af' }}
            />
            <YAxis stroke="#9ca3af" tick={{ fill: '#9ca3af' }} />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1f2937',
                border: '1px solid #374151',
                borderRadius: '0.5rem',
              }}
              labelStyle={{ color: '#fff' }}
            />
            <Legend wrapperStyle={{ color: '#fff' }} />
            <Line
              type="monotone"
              dataKey="rx_packets"
              stroke="#8b5cf6"
              strokeWidth={2}
              dot={false}
              name="RX Packets"
            />
            <Line
              type="monotone"
              dataKey="tx_packets"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
              name="TX Packets"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* CPU & Memory Chart */}
      <div className="bg-gray-800 p-6 rounded-lg">
        <h3 className="text-lg font-semibold text-white mb-4">
          System Resources
        </h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={metricsHistory}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="timestamp"
              stroke="#9ca3af"
              tick={{ fill: '#9ca3af' }}
            />
            <YAxis
              stroke="#9ca3af"
              tick={{ fill: '#9ca3af' }}
              domain={[0, 100]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1f2937',
                border: '1px solid #374151',
                borderRadius: '0.5rem',
              }}
              labelStyle={{ color: '#fff' }}
              formatter={(value: number) => `${value.toFixed(1)}%`}
            />
            <Legend wrapperStyle={{ color: '#fff' }} />
            <Bar dataKey="cpu_percent" fill="#ef4444" name="CPU %" />
            <Bar dataKey="memory_percent" fill="#06b6d4" name="Memory %" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Real-time Stats */}
      {deviceMetrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-gray-800 p-4 rounded-lg">
            <div className="text-gray-400 text-sm">RX Rate</div>
            <div className="text-2xl font-bold text-blue-500">
              {formatBytes(deviceMetrics.stats?.rx_bytes || 0)}
            </div>
          </div>
          <div className="bg-gray-800 p-4 rounded-lg">
            <div className="text-gray-400 text-sm">TX Rate</div>
            <div className="text-2xl font-bold text-green-500">
              {formatBytes(deviceMetrics.stats?.tx_bytes || 0)}
            </div>
          </div>
          <div className="bg-gray-800 p-4 rounded-lg">
            <div className="text-gray-400 text-sm">CPU Usage</div>
            <div className="text-2xl font-bold text-red-500">
              {deviceMetrics.cpu?.total_cpu_percent.toFixed(1)}%
            </div>
          </div>
          <div className="bg-gray-800 p-4 rounded-lg">
            <div className="text-gray-400 text-sm">Memory</div>
            <div className="text-2xl font-bold text-cyan-500">
              {(
                (deviceMetrics.memory?.used_mb /
                  deviceMetrics.memory?.total_mb) *
                100
              ).toFixed(1)}
              %
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
