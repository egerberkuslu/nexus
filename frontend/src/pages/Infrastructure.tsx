import { useMemo, useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { infrastructureAPI } from '@/services/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Button } from '@/components/atoms/Button'
import { Badge } from '@/components/atoms/Badge'
import { Input } from '@/components/atoms/Input'
import JsonViewer from '@/components/JsonViewer'

function statusVariant(status: string | undefined) {
  const s = (status || '').toLowerCase()
  if (s === 'running') return 'success'
  if (s === 'restarting' || s === 'created') return 'warning'
  if (s) return 'error'
  return 'default'
}

function findHostUrl(
  serviceId: string,
  ports: Array<{ container_port: string; host: { ip?: string; port?: string } | null }>
) {
  const portMap: Record<string, string> = {
    grafana: '3000/tcp',
    prometheus: '9090/tcp',
    consul: '8500/tcp',
    influxdb: '8086/tcp',
    pgadmin: '80/tcp',
    'mongo-express': '8081/tcp',
    rabbitmq: '15672/tcp',
    kafka: '9092/tcp',
    'kafka-ui': '8080/tcp',
    'schema-registry': '8081/tcp',
    'kafka-connect': '8083/tcp',
    flink: '8081/tcp',
    spark: '8080/tcp',
    hdfs: '9870/tcp',
    hive: '10002/tcp',
    hue: '8888/tcp',
    nginx: '80/tcp',
  }
  const wanted = portMap[serviceId]
  if (!wanted) return null
  const match = ports.find((p) => p.container_port === wanted && p.host?.port)
  if (!match?.host?.port) return null
  return `http://localhost:${match.host.port}`
}

export default function Infrastructure() {
  const [topologyId, setTopologyId] = useState('')
  const [includeStopped, setIncludeStopped] = useState(true)

  const topologiesQuery = useQuery({
    queryKey: ['infrastructure-topologies'],
    queryFn: async () => {
      const res = await infrastructureAPI.topologies()
      return res.data as any
    },
    refetchInterval: 5000,
  })

  const infraQuery = useQuery({
    queryKey: ['infrastructure-status', topologyId, includeStopped],
    queryFn: async () => {
      const res = await infrastructureAPI.status({
        topology_id: topologyId.trim() || undefined,
        include_stopped: includeStopped,
      })
      return res.data as any
    },
    refetchInterval: 5000,
  })

  const ensureMutation = useMutation({
    mutationFn: async () => {
      await infrastructureAPI.ensure()
    },
    onSuccess: async () => {
      toast.success('Infrastructure ensure triggered')
      await infraQuery.refetch()
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to ensure infrastructure')
    },
  })

  const items = infraQuery.data?.infrastructure?.items || []
  const missing = infraQuery.data?.infrastructure?.missing || []
  const emulation = infraQuery.data?.emulation
  const topoItems = topologiesQuery.data?.items || []

  const groups = useMemo(() => {
    const byCat: Record<string, any[]> = {}
    for (const it of items) {
      const cat = it.category || 'other'
      byCat[cat] ||= []
      byCat[cat].push(it)
    }
    return byCat
  }, [items])

  return (
    <div className="container-custom py-8 space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Infrastructure</h1>
          <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
            View and manage monitoring/messaging/storage services used by NEXUS - Network EXperimentation Unified System.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => infraQuery.refetch()} disabled={infraQuery.isFetching}>
            Refresh
          </Button>
          <Button variant="primary" onClick={() => ensureMutation.mutate()} isLoading={ensureMutation.isPending}>
            Ensure Running
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Scope</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-2">
            <Input
              label="Topology ID (optional)"
              value={topologyId}
              onChange={(e) => setTopologyId(e.target.value)}
              placeholder="uuid…"
            />
            <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300 mt-7">
              <input
                type="checkbox"
                checked={includeStopped}
                onChange={(e) => setIncludeStopped(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 dark:border-gray-600"
              />
              Include stopped containers
            </label>
          </div>

          {emulation && (
            <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/30 px-4 py-3">
              <div className="flex items-center justify-between gap-3">
                <div className="font-semibold text-gray-900 dark:text-gray-100">Emulation Container</div>
                <Badge variant={statusVariant(emulation?.container?.status) as any} size="sm">
                  {emulation?.container?.status || 'missing'}
                </Badge>
              </div>
              <div className="mt-2 text-sm text-gray-700 dark:text-gray-300">
                <div className="font-mono">{emulation.container_name}</div>
                {typeof emulation.grpc_host_port === 'number' && (
                  <div className="mt-1">gRPC: localhost:{emulation.grpc_host_port}</div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Active Topologies</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {topologiesQuery.isError && (
            <div className="text-sm text-red-700 dark:text-red-300">
              {(topologiesQuery.error as any)?.response?.data?.detail ||
                (topologiesQuery.error as any)?.message ||
                'Failed to load active topologies'}
            </div>
          )}
          {topoItems.length === 0 ? (
            <div className="text-sm text-gray-600 dark:text-gray-400">No active emulations found.</div>
          ) : (
            <div className="space-y-2">
              {topoItems.map((row: any) => (
                <div
                  key={row.topology_id}
                  className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/60 dark:bg-gray-900/30 px-4 py-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="font-semibold text-gray-900 dark:text-gray-100 font-mono break-all">
                          {row.topology_id}
                        </div>
                        <Badge variant={statusVariant(row.status) as any} size="sm">
                          {row.status || 'unknown'}
                        </Badge>
                      </div>
                      <div className="mt-1 text-xs text-gray-600 dark:text-gray-400 font-mono break-all">
                        {row.container_name || '—'}
                      </div>
                      {row.influxdb_bucket && (
                        <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                          Influx bucket: <span className="font-mono">{row.influxdb_bucket}</span>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <a
                        href={`/network-manager?topology=${row.topology_id}`}
                        className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        Open Network Manager
                      </a>
                      <a
                        href={`/topology/${row.topology_id}`}
                        className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        Open Topology
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {missing.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Missing Containers</CardTitle>
          </CardHeader>
          <CardContent>
            <JsonViewer data={missing} collapsed={1} />
          </CardContent>
        </Card>
      )}

      {infraQuery.isError && (
        <div className="rounded-2xl border border-red-200 dark:border-red-900/40 bg-red-50 dark:bg-red-950/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">
          {(infraQuery.error as any)?.response?.data?.detail || (infraQuery.error as any)?.message || 'Failed to load infrastructure status'}
        </div>
      )}

      {Object.entries(groups).map(([cat, rows]) => (
        <Card key={cat}>
          <CardHeader>
            <CardTitle className="capitalize">{cat}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {(rows as any[]).map((row) => {
              const container = row.container
              const status = container?.status as string | undefined
              const ports = (container?.ports || []) as any[]
              const url = container ? findHostUrl(row.id, ports) : null
              return (
                <div
                  key={row.id}
                  className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/60 dark:bg-gray-900/30 px-4 py-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="font-semibold text-gray-900 dark:text-gray-100">{row.id}</div>
                        <Badge variant={statusVariant(status) as any} size="sm">
                          {status || 'missing'}
                        </Badge>
                      </div>
                      <div className="mt-1 text-xs text-gray-600 dark:text-gray-400 font-mono break-all">
                        {row.container_name}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {url && (
                        <a
                          href={url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          Open
                        </a>
                      )}
                    </div>
                  </div>

                  {container && (
                    <div className="mt-3 grid gap-4 lg:grid-cols-2">
                      <div className="space-y-2">
                        <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Ports</div>
                        <JsonViewer data={ports} collapsed={2} />
                      </div>
                      <div className="space-y-2">
                        <div className="text-sm font-semibold text-gray-900 dark:text-gray-100">Config (Env)</div>
                        <JsonViewer data={container.env || {}} collapsed={2} />
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
