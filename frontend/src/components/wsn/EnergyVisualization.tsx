import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend } from 'recharts'

export type WSNEnergyPoint = {
  round: number
  total_energy: number
  avg_energy: number
  min_energy: number
  max_energy: number
}

export default function EnergyVisualization({ data }: { data: WSNEnergyPoint[] }) {
  return (
    <Card padding="lg">
      <CardHeader className="mb-2">
        <CardTitle className="text-base">Energy (residual)</CardTitle>
      </CardHeader>
      <CardContent>
        {data.length ? (
          <div className="h-[260px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.2} />
                <XAxis dataKey="round" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="total_energy" stroke="#10b981" strokeWidth={2} dot={false} name="Total (J)" />
                <Line type="monotone" dataKey="avg_energy" stroke="#3b82f6" strokeWidth={2} dot={false} name="Avg (J)" />
                <Line type="monotone" dataKey="min_energy" stroke="#f59e0b" strokeWidth={1} dot={false} name="Min (J)" />
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

