import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, Legend, ReferenceLine } from 'recharts'

export type WSNLifetime = {
  fnd_round?: number | null
  hnd_round?: number | null
  lnd_round?: number | null
}

export type WSNLifetimePoint = {
  round: number
  alive_nodes: number
  dead_nodes: number
}

export default function NetworkLifetimeChart({ data, lifetime }: { data: WSNLifetimePoint[]; lifetime: WSNLifetime }) {
  const hasFnd = typeof lifetime.fnd_round === 'number' && Number.isFinite(lifetime.fnd_round)
  const hasHnd = typeof lifetime.hnd_round === 'number' && Number.isFinite(lifetime.hnd_round)
  const hasLnd = typeof lifetime.lnd_round === 'number' && Number.isFinite(lifetime.lnd_round)

  return (
    <Card padding="lg">
      <CardHeader className="mb-2">
        <CardTitle className="text-base">Network lifetime</CardTitle>
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
                <Line type="monotone" dataKey="alive_nodes" stroke="#22c55e" strokeWidth={2} dot={false} name="Alive" />
                <Line type="monotone" dataKey="dead_nodes" stroke="#ef4444" strokeWidth={2} dot={false} name="Dead" />
                {hasFnd && (
                  <ReferenceLine
                    x={lifetime.fnd_round}
                    stroke="#f97316"
                    strokeDasharray="3 3"
                    label={{ value: 'FND', position: 'insideTopRight', fill: '#f97316', fontSize: 10 }}
                  />
                )}
                {hasHnd && (
                  <ReferenceLine
                    x={lifetime.hnd_round}
                    stroke="#a855f7"
                    strokeDasharray="3 3"
                    label={{ value: 'HND', position: 'insideTopRight', fill: '#a855f7', fontSize: 10 }}
                  />
                )}
                {hasLnd && (
                  <ReferenceLine
                    x={lifetime.lnd_round}
                    stroke="#0ea5e9"
                    strokeDasharray="3 3"
                    label={{ value: 'LND', position: 'insideTopRight', fill: '#0ea5e9', fontSize: 10 }}
                  />
                )}
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
