import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'
import type { WSNLifetime } from './NetworkLifetimeChart'

export default function ProtocolComparison({ protocolLabel, lifetime }: { protocolLabel: string; lifetime: WSNLifetime }) {
  const hasFnd = typeof lifetime.fnd_round === 'number' && Number.isFinite(lifetime.fnd_round)
  const hasHnd = typeof lifetime.hnd_round === 'number' && Number.isFinite(lifetime.hnd_round)
  const hasLnd = typeof lifetime.lnd_round === 'number' && Number.isFinite(lifetime.lnd_round)

  return (
    <Card padding="lg">
      <CardHeader className="mb-2">
        <CardTitle className="text-base">Protocol summary</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="default" size="sm">
            {protocolLabel || 'WSN'}
          </Badge>
          <Badge variant="default" size="sm">
            FND: <span className="font-mono">{hasFnd ? String(lifetime.fnd_round) : '—'}</span>
          </Badge>
          <Badge variant="default" size="sm">
            HND: <span className="font-mono">{hasHnd ? String(lifetime.hnd_round) : '—'}</span>
          </Badge>
          <Badge variant="default" size="sm">
            LND: <span className="font-mono">{hasLnd ? String(lifetime.lnd_round) : '—'}</span>
          </Badge>
        </div>
        <div className="text-[11px] text-gray-500 dark:text-gray-400">
          To compare protocols, run multiple WSN templates and use the Algorithms → History tab.
        </div>
      </CardContent>
    </Card>
  )
}
