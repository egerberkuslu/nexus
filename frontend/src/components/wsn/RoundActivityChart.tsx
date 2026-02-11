import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend } from 'recharts'

export type WSNActivityPoint = {
  round: number
  packets_to_bs: number
  cluster_count: number
}

export default function RoundActivityChart({ data }: { data: WSNActivityPoint[] }) {
  return (
    <Card padding="lg">
      <CardHeader className="mb-2">
        <CardTitle className="text-base">Per-round activity</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length ? (
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                <XAxis dataKey="round" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="packets_to_bs"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={false}
                  name="Packets → BS"
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="cluster_count"
                  stroke="#a855f7"
                  strokeWidth={2}
                  dot={false}
                  name="Clusters"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="text-sm text-gray-500 dark:text-gray-400">Waiting for round metrics…</div>
        )}
      </CardContent>
    </Card>
  )
}

