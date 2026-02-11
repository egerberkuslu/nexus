import { ChartBarIcon, Cog6ToothIcon, ServerIcon } from '@heroicons/react/24/outline'

import { Badge } from '@/components/atoms/Badge'
import { Button } from '@/components/atoms/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Input } from '@/components/atoms/Input'
import JsonViewer from '@/components/JsonViewer'
import { MetricCard } from '@/components/molecules/MetricCard'
import { cn } from '@/utils/cn'

import { KvTableEditor, kvObjectToRows, newKvRow } from './kv'

export default function ManoTab({
  topologyId,
  isRunning,
  setActiveTab,

  manoPane,
  setManoPane,
  manoInfoQuery,

  manoNsdsQuery,
  manoVnfdsQuery,
  manoNsInstancesQuery,
  manoAllVnfsQuery,
  manoSelectedNsId,
  setManoSelectedNsId,
  manoInventoryQuery,
  manoOpsQuery,
  manoVnfsQuery,
  manoSelectedVnfId,
  setManoSelectedVnfId,
  manoVnfDeleteForce,
  setManoVnfDeleteForce,
  manoExecCommand,
  setManoExecCommand,
  execVnfMutation,
  deleteVnfMutation,
  terminateNsMutation,
  createNsMutation,
  manoNsName,
  setManoNsName,
  manoNsDryRun,
  setManoNsDryRun,
  manoNsBackend,
  setManoNsBackend,
  manoSelectedNsdId,
  setManoSelectedNsdId,
  manoOsmNsdId,
  setManoOsmNsdId,
  manoOsmVimAccountId,
  setManoOsmVimAccountId,
  manoVnfName,
  setManoVnfName,
  manoVnfDeviceType,
  setManoVnfDeviceType,
  manoVnfPropsRows,
  setManoVnfPropsRows,
  manoVnfProperties,
  manoVnfDryRun,
  setManoVnfDryRun,
  createVnfMutation,

  manoCatalogTab,
  setManoCatalogTab,
  manoNsdName,
  setManoNsdName,
  manoNsdTopologyId,
  setManoNsdTopologyId,
  manoNsdOptionRows,
  setManoNsdOptionRows,
  manoNsdDescriptor,
  upsertNsdMutation,
  manoSelectedNsd,
  manoVnfdName,
  setManoVnfdName,
  manoVnfdDeviceType,
  setManoVnfdDeviceType,
  manoVnfdDefaultsRows,
  setManoVnfdDefaultsRows,
  manoVnfdDescriptor,
  upsertVnfdMutation,
  manoSelectedVnfdId,
  setManoSelectedVnfdId,
  manoSelectedVnfd,

  osmConnectorRunning,
  osmEnsureInfraMutation,
  osmReconcileMutation,
  osmStopInfraMutation,
  osmPurgeInfraMutation,
  osmTab,
  setOsmTab,
  osmUiKind,
  setOsmUiKind,
  osmInfraStatusQuery,
  osmInfoQuery,
  osmProjectsQuery,
  osmVimAccountsQuery,
  osmSelectedVimAccountId,
  setOsmSelectedVimAccountId,
  osmWimAccountsQuery,
  osmSdnControllersQuery,
  osmMirrorStatsQuery,
  osmMirrorSyncMutation,

  osmNsdPackagesQuery,
  osmVnfdPackagesQuery,
  uploadOsmNsdMutation,
  uploadOsmVnfdMutation,
  deleteOsmNsdMutation,
  deleteOsmVnfdMutation,
  osmNsInstancesQuery,
  osmCreateNsName,
  setOsmCreateNsName,
  osmCreateNsDescription,
  setOsmCreateNsDescription,
  osmSelectedNsdPkgId,
  setOsmSelectedNsdPkgId,
  osmCreateNsMutation,
  osmSelectedNsInstanceId,
  setOsmSelectedNsInstanceId,
  osmInstantiateNsMutation,
  osmInstantiateJson,
  setOsmInstantiateJson,
  osmTerminateNsMutation,
  osmDeleteNsMutation,

  osmMirrorResourceType,
  setOsmMirrorResourceType,
  osmMirrorIncludeDeleted,
  setOsmMirrorIncludeDeleted,
  osmMirrorResourcesQuery,
  osmMirrorSelectedId,
  setOsmMirrorSelectedId,
}: any) {
  return (
    <div className="space-y-6 animate-fade-in">
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>MANO</CardTitle>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Manage network services (NFVO/VNFM/VIM) and integrate ETSI OSM per-topology.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Button size="xs" variant={manoPane === 'overview' ? 'primary' : 'secondary'} onClick={() => setManoPane('overview')}>
                Overview
              </Button>
              <Button size="xs" variant={manoPane === 'local' ? 'primary' : 'secondary'} onClick={() => setManoPane('local')}>
                Local MANO
              </Button>
              <Button size="xs" variant={manoPane === 'osm' ? 'primary' : 'secondary'} onClick={() => setManoPane('osm')}>
                OSM (ETSI)
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="default" size="sm">
              Southbound: {String(manoInfoQuery.data?.features?.southbound_mode || '—')}
            </Badge>
            <Badge variant="default" size="sm">
              Catalog: {String(manoInfoQuery.data?.features?.catalog ?? '—')}
            </Badge>
            <Badge variant="default" size="sm">
              NFVO: {String(manoInfoQuery.data?.features?.nfvo || '—')}
            </Badge>
            <Badge variant="default" size="sm">
              VNFM: {String(manoInfoQuery.data?.features?.vnfm || '—')}
            </Badge>
            <Badge variant="default" size="sm">
              VIM: {String(manoInfoQuery.data?.features?.vim || '—')}
            </Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-1">
            <CardTitle>Quick Start</CardTitle>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              New to MANO? Use these shortcuts to get something running quickly.
            </p>
          </div>
        </CardHeader>
        <CardContent>
          {!topologyId ? (
            <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 p-3 text-sm text-gray-700 dark:text-gray-300">
              Select a topology first. OSM runs isolated per topology and Local MANO actions can target a topology.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="rounded-2xl border border-blue-200/70 dark:border-blue-900/50 p-4 space-y-3 bg-gradient-to-br from-blue-50/70 via-white to-cyan-50/60 dark:from-blue-950/25 dark:via-gray-950 dark:to-cyan-950/20">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="h-10 w-10 rounded-xl bg-blue-600/10 dark:bg-blue-400/10 text-blue-700 dark:text-blue-300 flex items-center justify-center">
                      <Cog6ToothIcon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-gray-900 dark:text-white">Local MANO</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">Built-in NFVO/VNFM for fast experiments.</div>
                    </div>
                  </div>
                  <Badge variant="info" size="sm">
                    Fast
                  </Badge>
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Create NS/VNF directly against the emulation via built-in NFVO/VNFM.
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="primary" onClick={() => setManoPane('local')}>
                    Open Local MANO
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setActiveTab('config')}>
                    Control Config
                  </Button>
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400">
                  Tip: start the emulation first if you plan to run commands on devices.
                </div>
              </div>

              <div className="rounded-2xl border border-indigo-200/70 dark:border-indigo-900/50 p-4 space-y-3 bg-gradient-to-br from-indigo-50/70 via-white to-purple-50/60 dark:from-indigo-950/25 dark:via-gray-950 dark:to-purple-950/20">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="h-10 w-10 rounded-xl bg-indigo-600/10 dark:bg-indigo-400/10 text-indigo-700 dark:text-indigo-300 flex items-center justify-center">
                      <ServerIcon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-gray-900 dark:text-white">OSM (ETSI)</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">Real MANO stack per topology (isolated).</div>
                    </div>
                  </div>
                  <Badge variant={osmConnectorRunning ? 'success' : 'warning'} size="sm">
                    {osmConnectorRunning ? 'Running' : 'Stopped'}
                  </Badge>
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Use a real MANO stack (OSM) per topology: VIM/WIM/Packages/NS lifecycle + native UI.
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => {
                      setManoPane('osm')
                      setOsmTab('overview')
                      osmReconcileMutation.mutate()
                    }}
                    disabled={osmReconcileMutation.isPending}
                    isLoading={osmReconcileMutation.isPending}
                  >
                    Ensure + Sync
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setManoPane('osm')
                      setOsmTab('ui')
                    }}
                  >
                    Open OSM UI
                  </Button>
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400">
                  Default login: <span className="font-mono">admin / admin</span>
                </div>
              </div>

              <div className="rounded-2xl border border-emerald-200/70 dark:border-emerald-900/50 p-4 space-y-3 bg-gradient-to-br from-emerald-50/70 via-white to-teal-50/60 dark:from-emerald-950/25 dark:via-gray-950 dark:to-teal-950/20">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="h-10 w-10 rounded-xl bg-emerald-600/10 dark:bg-emerald-400/10 text-emerald-700 dark:text-emerald-300 flex items-center justify-center">
                      <ChartBarIcon className="h-5 w-5" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold text-gray-900 dark:text-white">Verify It Works</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">Prove MANO actions change the emulation.</div>
                    </div>
                  </div>
                  <Badge variant={isRunning ? 'success' : 'default'} size="sm">
                    Emulation: {isRunning ? 'running' : 'stopped'}
                  </Badge>
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  After instantiating an NS, you should see new runtime devices/containers created in the emulation.
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="secondary" onClick={() => setActiveTab('container-ui')}>
                    Container UI
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => setActiveTab('terminal')}>
                    Device Terminal
                  </Button>
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400">
                  Also available: <span className="font-mono">bash scripts/mano_smoke_test.sh {String(topologyId)}</span>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {manoPane === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <MetricCard
              title="Local NSDs"
              value={manoNsdsQuery.data?.length || 0}
              subtitle="Service descriptors (custom)"
              variant="primary"
              isLoading={manoNsdsQuery.isFetching}
              onClick={() => setManoPane('local')}
            />
            <MetricCard
              title="Local VNFDs"
              value={manoVnfdsQuery.data?.length || 0}
              subtitle="VNF descriptors (custom)"
              variant="primary"
              isLoading={manoVnfdsQuery.isFetching}
              onClick={() => setManoPane('local')}
            />
            <MetricCard
              title="Local NS Instances"
              value={manoNsInstancesQuery.data?.length || 0}
              subtitle={topologyId ? `Topology ${String(topologyId).slice(0, 8)}` : 'All topologies'}
              variant={manoNsInstancesQuery.data?.length ? 'success' : 'default'}
              isLoading={manoNsInstancesQuery.isFetching}
              onClick={() => setManoPane('local')}
            />
            <MetricCard
              title="VNF Instances"
              value={manoAllVnfsQuery.data?.length || 0}
              subtitle="Across MANO database"
              variant={manoAllVnfsQuery.data?.length ? 'success' : 'default'}
              isLoading={manoAllVnfsQuery.isFetching}
              onClick={() => setManoPane('local')}
            />
            <MetricCard
              title="OSM Stack"
              value={osmConnectorRunning ? 'RUNNING' : 'STOPPED'}
              subtitle={topologyId ? `Per-topology (${String(topologyId).slice(0, 8)})` : 'Select a topology'}
              variant={osmConnectorRunning ? 'success' : 'warning'}
              isLoading={osmInfraStatusQuery.isFetching}
              onClick={() => setManoPane('osm')}
            />
            <MetricCard
              title="OSM VIM Accounts"
              value={(osmVimAccountsQuery.data || []).length}
              subtitle="VIM accounts inside ETSI OSM"
              variant={(osmVimAccountsQuery.data || []).length ? 'success' : 'default'}
              isLoading={osmVimAccountsQuery.isFetching}
              onClick={() => setManoPane('osm')}
            />
            <MetricCard
              title="OSM WIM Accounts"
              value={(osmWimAccountsQuery.data || []).length}
              subtitle="WIM accounts inside ETSI OSM"
              variant={(osmWimAccountsQuery.data || []).length ? 'success' : 'default'}
              isLoading={osmWimAccountsQuery.isFetching}
              onClick={() => setManoPane('osm')}
            />
            <MetricCard
              title="OSM SDN Controllers"
              value={Array.isArray(osmSdnControllersQuery.data) ? osmSdnControllersQuery.data.length : 0}
              subtitle="Discovered/registered SDNs"
              variant={Array.isArray(osmSdnControllersQuery.data) && osmSdnControllersQuery.data.length ? 'success' : 'default'}
              isLoading={osmSdnControllersQuery.isFetching}
              onClick={() => setManoPane('osm')}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <CardTitle>ETSI OSM (per-topology)</CardTitle>
                  <Button size="xs" variant="secondary" onClick={() => setManoPane('osm')}>
                    Open Panel
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-gray-700 dark:text-gray-300">
                <div>
                  This project runs an isolated ETSI OSM stack per topology. Use it to upload VNFD/NSD packages and instantiate
                  NS instances against the emulated infrastructure.
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    size="xs"
                    variant="primary"
                    onClick={() => osmEnsureInfraMutation.mutate()}
                    disabled={!topologyId || osmEnsureInfraMutation.isPending}
                    isLoading={osmEnsureInfraMutation.isPending}
                  >
                    Start / Ensure
                  </Button>
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => osmReconcileMutation.mutate()}
                    disabled={!topologyId || osmReconcileMutation.isPending}
                    isLoading={osmReconcileMutation.isPending}
                  >
                    Sync Mirror
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <CardTitle>Local MANO</CardTitle>
                  <Button size="xs" variant="secondary" onClick={() => setManoPane('local')}>
                    Open Panel
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-3 text-sm text-gray-700 dark:text-gray-300">
                <div>
                  Local MANO is a lightweight NFVO/VNFM flow that starts emulations and creates runtime VNFs (containers/devices)
                  through the platform APIs.
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="default" size="sm">
                    Backend: local
                  </Badge>
                  <Badge variant="default" size="sm">
                    Topology: {topologyId ? String(topologyId).slice(0, 8) : '—'}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {manoPane === 'osm' && (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-3">
                <CardTitle>OSM (ETSI)</CardTitle>
                <div className="flex items-center gap-2">
                  <Button size="xs" variant={osmTab === 'overview' ? 'primary' : 'secondary'} onClick={() => setOsmTab('overview')}>
                    Overview
                  </Button>
                  <Button size="xs" variant={osmTab === 'packages' ? 'primary' : 'secondary'} onClick={() => setOsmTab('packages')}>
                    Packages
                  </Button>
                  <Button size="xs" variant={osmTab === 'ns' ? 'primary' : 'secondary'} onClick={() => setOsmTab('ns')}>
                    NS
                  </Button>
                  <Button size="xs" variant={osmTab === 'mirror' ? 'primary' : 'secondary'} onClick={() => setOsmTab('mirror')}>
                    Mirror
                  </Button>
                  <Button size="xs" variant={osmTab === 'ui' ? 'primary' : 'secondary'} onClick={() => setOsmTab('ui')}>
                    UI
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {(() => {
                const id8 = topologyId ? String(topologyId).slice(0, 8) : ''
                return (
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => window.open(`/infra-proxy/osm-ng-ui/${id8}/`, '_blank', 'noopener,noreferrer')}
                      disabled={!topologyId}
                    >
                      Open OSM NG-UI
                    </Button>
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => window.open(`/infra-proxy/osm-light-ui/${id8}/`, '_blank', 'noopener,noreferrer')}
                      disabled={!topologyId}
                    >
                      Open OSM Light UI
                    </Button>
                    {!topologyId ? (
                      <span className="text-xs text-gray-500 dark:text-gray-400">Select a topology to open its isolated OSM UI.</span>
                    ) : null}
                  </div>
                )
              })()}

              {!topologyId ? (
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 p-3 text-sm text-gray-700 dark:text-gray-300">
                  Select a topology first. This OSM panel is per-topology (isolated OSM stack per topology).
                </div>
              ) : (
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 p-3 space-y-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant="default" size="sm">
                      Topology: {String(topologyId).slice(0, 8)}
                    </Badge>
                    <Badge variant={osmConnectorRunning ? 'success' : 'default'} size="sm">
                      Stack: {osmConnectorRunning ? 'running' : (osmEnsureInfraMutation.isPending ? 'starting' : 'stopped')}
                    </Badge>
                    <Badge variant="default" size="sm">
                      Connector:{' '}
                      {String(
                        osmInfraStatusQuery.data?.osm?.connector?.service_name || `osm-connector-${String(topologyId).slice(0, 8)}`
                      )}
                    </Badge>
                    <Badge
                      variant={(osmInfraStatusQuery.data as any)?.osm?.bootstrap?.emulation_vim?.vim_account_id ? 'success' : 'default'}
                      size="sm"
                    >
                      Emu VIM:{' '}
                      {String(
                        (osmInfraStatusQuery.data as any)?.osm?.bootstrap?.emulation_vim?.name || `mininet-${String(topologyId).slice(0, 8)}`
                      )}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      size="xs"
                      variant="primary"
                      onClick={() => osmEnsureInfraMutation.mutate()}
                      disabled={!topologyId || osmEnsureInfraMutation.isPending}
                    >
                      Start / Ensure
                    </Button>
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => osmReconcileMutation.mutate()}
                      disabled={!topologyId || osmReconcileMutation.isPending}
                    >
                      Ensure + Sync
                    </Button>
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => osmMirrorSyncMutation.mutate()}
                      disabled={!topologyId || osmMirrorSyncMutation.isPending}
                    >
                      Sync OSM → DB
                    </Button>
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => osmStopInfraMutation.mutate(true)}
                      disabled={!topologyId || osmStopInfraMutation.isPending}
                    >
                      Stop
                    </Button>
                    <Button
                      size="xs"
                      variant="danger"
                      onClick={() => {
                        if (!confirm('Purge per-topology OSM stack? (containers + volumes)')) return
                        osmPurgeInfraMutation.mutate()
                      }}
                      disabled={!topologyId || osmPurgeInfraMutation.isPending}
                    >
                      Purge
                    </Button>
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => osmInfraStatusQuery.refetch()}
                      disabled={!topologyId || osmInfraStatusQuery.isFetching}
                    >
                      Refresh
                    </Button>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {(() => {
                      const counts = (osmMirrorStatsQuery.data as any)?.counts || {}
                      const get = (k: string) => Number(counts?.[k] || 0)
                      const chips = [
                        { label: 'Projects', v: get('osm:osm_project') },
                        { label: 'VIM', v: get('osm:vim_account') },
                        { label: 'WIM', v: get('osm:wim_account') },
                        { label: 'SDN', v: get('osm:sdn_controller') },
                        { label: 'VNFD', v: get('osm:vnfd_package') },
                        { label: 'NSD', v: get('osm:nsd_package') },
                        { label: 'NS', v: get('osm:ns_instance') },
                      ]
                      return chips.map((c) => (
                        <Badge key={c.label} variant="default" size="sm">
                          {c.label}: {c.v}
                        </Badge>
                      ))
                    })()}
                    {osmMirrorStatsQuery.isFetching ? (
                      <span className="text-xs text-gray-500 dark:text-gray-400">Syncing…</span>
                    ) : null}
                  </div>
                </div>
              )}

              {topologyId && !osmConnectorRunning ? (
                <div className="rounded-xl border border-amber-200 dark:border-amber-900 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-800 dark:text-amber-200">
                  This topology does not have a running OSM stack yet. Click <span className="font-medium">Start / Ensure</span>.
                </div>
              ) : null}

              {osmConnectorRunning ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="default" size="sm">
                    NBI: {String(osmInfoQuery.data?.osm?.nbi_url || '—')}
                  </Badge>
                  <Badge variant="default" size="sm">
                    Auth: {String(osmInfoQuery.data?.osm?.auth_mode || '—')}
                  </Badge>
                  <Badge variant="default" size="sm">
                    Project: {String(osmInfoQuery.data?.osm?.project_id || '—')}
                  </Badge>
                </div>
              ) : null}

              {osmTab === 'overview' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Projects</div>
                    <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                          <tr className="text-left">
                            <th className="px-3 py-2 font-medium">Name</th>
                            <th className="px-3 py-2 font-medium">ID</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(Array.isArray(osmProjectsQuery.data) ? osmProjectsQuery.data : []).map((p: any) => (
                            <tr key={String(p?._id || p?.id || p?.name)} className="border-t border-gray-200 dark:border-gray-800">
                              <td className="px-3 py-2 font-medium">{String(p?.name || '—')}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                                {String(p?._id || p?.id || '').slice(0, 12)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {!Array.isArray(osmProjectsQuery.data) || !osmProjectsQuery.data.length ? (
                        <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No projects.</div>
                      ) : null}
                    </div>
                    <details className="mt-2 text-sm">
                      <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Raw JSON</summary>
                      <div className="mt-2">
                        <JsonViewer data={osmProjectsQuery.data || null} collapsed={2} />
                      </div>
                    </details>
                  </div>
                  <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">VIM Accounts</div>
                    <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                          <tr className="text-left">
                            <th className="px-3 py-2 font-medium w-10" />
                            <th className="px-3 py-2 font-medium">Name</th>
                            <th className="px-3 py-2 font-medium">Type</th>
                            <th className="px-3 py-2 font-medium">State</th>
                            <th className="px-3 py-2 font-medium">ID</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(Array.isArray(osmVimAccountsQuery.data) ? osmVimAccountsQuery.data : []).map((v: any) => {
                            const id = String(v?._id || v?.id || '')
                            const name = String(v?.name || id || '—')
                            const vimType = String(v?.vim_type || '—')
                            const opState = String(v?._admin?.operationalState || v?.operationalState || '—')
                            const selected = id && id === String(osmSelectedVimAccountId)
                            return (
                              <tr
                                key={id || name}
                                className={cn(
                                  'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                                  selected && 'bg-blue-50 dark:bg-blue-950/30'
                                )}
                                onClick={() => setOsmSelectedVimAccountId(id)}
                              >
                                <td className="px-3 py-2">
                                  <input type="radio" checked={selected} onChange={() => setOsmSelectedVimAccountId(id)} />
                                </td>
                                <td className="px-3 py-2 font-medium">{name}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{vimType}</td>
                                <td className="px-3 py-2">
                                  <Badge variant={opState.toUpperCase() === 'ENABLED' ? 'success' : 'default'} size="sm">
                                    {opState}
                                  </Badge>
                                </td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{id.slice(0, 12)}</td>
                              </tr>
                            )
                          })}
                        </tbody>
                      </table>
                      {!Array.isArray(osmVimAccountsQuery.data) || !osmVimAccountsQuery.data.length ? (
                        <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No VIM accounts.</div>
                      ) : null}
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <div className="text-xs text-gray-600 dark:text-gray-400">
                        Selected: {osmSelectedVimAccountId ? String(osmSelectedVimAccountId).slice(0, 12) : '—'}
                      </div>
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => osmVimAccountsQuery.refetch()}
                        disabled={osmVimAccountsQuery.isFetching}
                      >
                        Refresh
                      </Button>
                    </div>
                    <details className="mt-2 text-sm">
                      <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Raw JSON</summary>
                      <div className="mt-2">
                        <JsonViewer data={osmVimAccountsQuery.data || null} collapsed={2} />
                      </div>
                    </details>
                  </div>

                  <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">SDN Controllers</div>
                    <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                          <tr className="text-left">
                            <th className="px-3 py-2 font-medium">Name</th>
                            <th className="px-3 py-2 font-medium">Type</th>
                            <th className="px-3 py-2 font-medium">URL</th>
                            <th className="px-3 py-2 font-medium">ID</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(Array.isArray(osmSdnControllersQuery.data) ? osmSdnControllersQuery.data : []).map((s: any) => (
                            <tr key={String(s?._id || s?.id || s?.name)} className="border-t border-gray-200 dark:border-gray-800">
                              <td className="px-3 py-2 font-medium">{String(s?.name || '—')}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(s?.type || '—')}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(s?.url || '—')}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                                {String(s?._id || s?.id || '').slice(0, 12)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {!Array.isArray(osmSdnControllersQuery.data) || !osmSdnControllersQuery.data.length ? (
                        <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No SDN controllers.</div>
                      ) : null}
                    </div>
                    <details className="mt-2 text-sm">
                      <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Raw JSON</summary>
                      <div className="mt-2">
                        <JsonViewer data={osmSdnControllersQuery.data || null} collapsed={2} />
                      </div>
                    </details>
                  </div>

                  <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">WIM Accounts</div>
                    <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                          <tr className="text-left">
                            <th className="px-3 py-2 font-medium">Name</th>
                            <th className="px-3 py-2 font-medium">Type</th>
                            <th className="px-3 py-2 font-medium">URL</th>
                            <th className="px-3 py-2 font-medium">ID</th>
                          </tr>
                        </thead>
                        <tbody>
                          {(Array.isArray(osmWimAccountsQuery.data) ? osmWimAccountsQuery.data : []).map((w: any) => (
                            <tr key={String(w?._id || w?.id || w?.name)} className="border-t border-gray-200 dark:border-gray-800">
                              <td className="px-3 py-2 font-medium">{String(w?.name || '—')}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(w?.wim_type || '—')}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(w?.wim_url || '—')}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                                {String(w?._id || w?.id || '').slice(0, 12)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {!Array.isArray(osmWimAccountsQuery.data) || !osmWimAccountsQuery.data.length ? (
                        <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No WIM accounts.</div>
                      ) : null}
                    </div>
                    <details className="mt-2 text-sm">
                      <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Raw JSON</summary>
                      <div className="mt-2">
                        <JsonViewer data={osmWimAccountsQuery.data || null} collapsed={2} />
                      </div>
                    </details>
                  </div>
                </div>
              )}

              {osmTab === 'packages' && (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300">NSD Packages</div>
                      <input
                        type="file"
                        className="text-sm"
                        onChange={(e) => {
                          const f = e.target.files?.[0]
                          if (f) uploadOsmNsdMutation.mutate(f)
                          e.currentTarget.value = ''
                        }}
                      />
                    </div>
                    <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                          <tr className="text-left">
                            <th className="px-3 py-2 font-medium">Name</th>
                            <th className="px-3 py-2 font-medium">ID</th>
                            <th className="px-3 py-2 w-24" />
                          </tr>
                        </thead>
                        <tbody>
                          {(Array.isArray(osmNsdPackagesQuery.data) ? osmNsdPackagesQuery.data : []).map((p: any) => (
                            <tr key={String(p._id || p.id)} className="border-t border-gray-200 dark:border-gray-800">
                              <td className="px-3 py-2">{String(p.name || p.id || p._id)}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                                {String(p._id || p.id).slice(0, 8)}
                              </td>
                              <td className="px-3 py-2 text-right">
                                <Button
                                  size="xs"
                                  variant="danger"
                                  onClick={() => deleteOsmNsdMutation.mutate(String(p._id || p.id))}
                                  disabled={deleteOsmNsdMutation.isPending}
                                >
                                  Delete
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {!Array.isArray(osmNsdPackagesQuery.data) || !osmNsdPackagesQuery.data.length ? (
                        <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No NSD packages.</div>
                      ) : null}
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300">VNFD Packages</div>
                      <input
                        type="file"
                        className="text-sm"
                        onChange={(e) => {
                          const f = e.target.files?.[0]
                          if (f) uploadOsmVnfdMutation.mutate(f)
                          e.currentTarget.value = ''
                        }}
                      />
                    </div>
                    <div className="max-h-72 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                      <table className="min-w-full text-sm">
                        <thead className="bg-gray-50 dark:bg-gray-800">
                          <tr className="text-left">
                            <th className="px-3 py-2 font-medium">Name</th>
                            <th className="px-3 py-2 font-medium">ID</th>
                            <th className="px-3 py-2 w-24" />
                          </tr>
                        </thead>
                        <tbody>
                          {(Array.isArray(osmVnfdPackagesQuery.data) ? osmVnfdPackagesQuery.data : []).map((p: any) => (
                            <tr key={String(p._id || p.id)} className="border-t border-gray-200 dark:border-gray-800">
                              <td className="px-3 py-2">{String(p.name || p.id || p['product-name'] || p._id)}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                                {String(p._id || p.id).slice(0, 8)}
                              </td>
                              <td className="px-3 py-2 text-right">
                                <Button
                                  size="xs"
                                  variant="danger"
                                  onClick={() => deleteOsmVnfdMutation.mutate(String(p._id || p.id))}
                                  disabled={deleteOsmVnfdMutation.isPending}
                                >
                                  Delete
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {!Array.isArray(osmVnfdPackagesQuery.data) || !osmVnfdPackagesQuery.data.length ? (
                        <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No VNFD packages.</div>
                      ) : null}
                    </div>
                  </div>
                </div>
              )}

              {osmTab === 'ns' && (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
                    <Input value={osmCreateNsName} onChange={(e) => setOsmCreateNsName(e.target.value)} label="NS name" />
                    <Input value={osmCreateNsDescription} onChange={(e) => setOsmCreateNsDescription(e.target.value)} label="Description" />
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">NSD package</label>
                      <select
                        value={osmSelectedNsdPkgId}
                        onChange={(e) => setOsmSelectedNsdPkgId(e.target.value)}
                        className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                      >
                        <option value="">(select)</option>
                        {(Array.isArray(osmNsdPackagesQuery.data) ? osmNsdPackagesQuery.data : []).map((p: any) => (
                          <option key={String(p._id || p.id)} value={String(p._id || p.id)}>
                            {String(p.name || p.id || p._id)}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      onClick={() => osmCreateNsMutation.mutate()}
                      disabled={!osmSelectedNsdPkgId || !osmCreateNsName.trim() || osmCreateNsMutation.isPending}
                      variant="primary"
                    >
                      Create NS Instance
                    </Button>
                    <Badge variant="default" size="sm">
                      selected: {osmSelectedNsInstanceId ? osmSelectedNsInstanceId.slice(0, 8) : '—'}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">vimAccountId</label>
                      <select
                        value={osmSelectedVimAccountId}
                        onChange={(e) => setOsmSelectedVimAccountId(e.target.value)}
                        className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                      >
                        <option value="">(select)</option>
                        {(osmVimAccountsQuery.data || []).map((v: any) => (
                          <option key={String(v._id || v.id || v.name)} value={String(v._id || v.id || '')}>
                            {String(v.name || v._id || v.id)}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="flex items-end">
                      <Button
                        onClick={() => osmInstantiateNsMutation.mutate()}
                        disabled={!osmSelectedNsInstanceId || osmInstantiateNsMutation.isPending}
                        variant="secondary"
                      >
                        Instantiate (selected)
                      </Button>
                    </div>
                  </div>
                  <details className="text-sm">
                    <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Instantiate JSON (advanced)</summary>
                    <div className="mt-2">
                      <textarea
                        value={osmInstantiateJson}
                        onChange={(e) => setOsmInstantiateJson(e.target.value)}
                        rows={6}
                        className="w-full px-3 py-2 rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 font-mono text-xs"
                      />
                    </div>
                  </details>

                  <div className="max-h-80 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-50 dark:bg-gray-800">
                        <tr className="text-left">
                          <th className="px-3 py-2 font-medium">Name</th>
                          <th className="px-3 py-2 font-medium">State</th>
                          <th className="px-3 py-2 font-medium">ID</th>
                          <th className="px-3 py-2 w-40" />
                        </tr>
                      </thead>
                      <tbody>
                        {(Array.isArray(osmNsInstancesQuery.data) ? osmNsInstancesQuery.data : []).map((x: any) => (
                          <tr
                            key={String(x._id || x.id)}
                            className={cn(
                              'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                              osmSelectedNsInstanceId === String(x._id || x.id) && 'bg-blue-50 dark:bg-blue-950/30'
                            )}
                            onClick={() => setOsmSelectedNsInstanceId(String(x._id || x.id))}
                          >
                            <td className="px-3 py-2">{String(x.name || x.nsName || x._id || x.id)}</td>
                            <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                              {String(x.nsState || x.status || x.operationalStatus || '—')}
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(x._id || x.id).slice(0, 8)}</td>
                            <td className="px-3 py-2 text-right flex items-center justify-end gap-2">
                              <Button
                                size="xs"
                                variant="secondary"
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  osmTerminateNsMutation.mutate(String(x._id || x.id))
                                }}
                                disabled={osmTerminateNsMutation.isPending}
                              >
                                Terminate
                              </Button>
                              <Button
                                size="xs"
                                variant="danger"
                                onClick={(e) => {
                                  e.preventDefault()
                                  e.stopPropagation()
                                  osmDeleteNsMutation.mutate(String(x._id || x.id))
                                }}
                                disabled={osmDeleteNsMutation.isPending}
                              >
                                Delete
                              </Button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {!Array.isArray(osmNsInstancesQuery.data) || !osmNsInstancesQuery.data.length ? (
                      <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No OSM NS instances.</div>
                    ) : null}
                  </div>
                </div>
              )}

              {osmTab === 'mirror' && (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">Resource type</label>
                    <select
                      value={osmMirrorResourceType}
                      onChange={(e) => setOsmMirrorResourceType(e.target.value)}
                      className="px-3 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-sm"
                    >
                      <option value="">(all)</option>
                      <option value="osm_project">osm_project</option>
                      <option value="vim_account">vim_account</option>
                      <option value="wim_account">wim_account</option>
                      <option value="sdn_controller">sdn_controller</option>
                      <option value="vnfd_package">vnfd_package</option>
                      <option value="nsd_package">nsd_package</option>
                      <option value="ns_instance">ns_instance</option>
                      <option value="ns_lcm_op_occ">ns_lcm_op_occ</option>
                    </select>

                    <label className="flex items-center gap-2 text-sm">
                      <input type="checkbox" checked={osmMirrorIncludeDeleted} onChange={(e) => setOsmMirrorIncludeDeleted(e.target.checked)} />
                      include deleted
                    </label>

                    <div className="flex-1" />
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => osmMirrorResourcesQuery.refetch()}
                      disabled={!topologyId || osmMirrorResourcesQuery.isFetching}
                    >
                      Refresh
                    </Button>
                  </div>

                  <div className="max-h-80 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                    <table className="min-w-full text-sm">
                      <thead className="bg-gray-50 dark:bg-gray-800">
                        <tr className="text-left">
                          <th className="px-3 py-2 font-medium">Type</th>
                          <th className="px-3 py-2 font-medium">Name</th>
                          <th className="px-3 py-2 font-medium">External ID</th>
                          <th className="px-3 py-2 font-medium">Deleted</th>
                        </tr>
                      </thead>
                      <tbody>
                        {((osmMirrorResourcesQuery.data as any)?.items || []).map((r: any) => {
                          const id = String(r?.id || '')
                          const selected = id && id === String(osmMirrorSelectedId)
                          return (
                            <tr
                              key={id || String(r?.external_id || Math.random())}
                              className={cn('border-t border-gray-200 dark:border-gray-800 cursor-pointer', selected && 'bg-blue-50 dark:bg-blue-950/30')}
                              onClick={() => setOsmMirrorSelectedId(id)}
                            >
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(r?.resource_type || '—')}</td>
                              <td className="px-3 py-2 font-medium">{String(r?.name || '—')}</td>
                              <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                                {String(r?.external_id || '').slice(0, 18)}
                              </td>
                              <td className="px-3 py-2">
                                <Badge variant={r?.deleted ? 'default' : 'success'} size="sm">
                                  {r?.deleted ? 'yes' : 'no'}
                                </Badge>
                              </td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                    {!((osmMirrorResourcesQuery.data as any)?.items || []).length ? (
                      <div className="p-3 text-sm text-gray-600 dark:text-gray-400">
                        {osmMirrorResourcesQuery.isFetching ? 'Loading…' : 'No mirrored resources.'}
                      </div>
                    ) : null}
                  </div>

                  {(() => {
                    const items = ((osmMirrorResourcesQuery.data as any)?.items || []) as any[]
                    const selected = items.find((x) => String(x?.id) === String(osmMirrorSelectedId))
                    if (!selected) return null
                    return (
                      <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
                            Selected: {String(selected?.resource_type || 'resource')} ·{' '}
                            {String(selected?.name || '').trim() || String(selected?.external_id || '').slice(0, 12)}
                          </div>
                          <Button size="xs" variant="secondary" onClick={() => setOsmMirrorSelectedId('')}>
                            Clear
                          </Button>
                        </div>
                        <div className="mt-2">
                          <JsonViewer data={selected} collapsed={2} />
                        </div>
                      </div>
                    )
                  })()}
                </div>
              )}

              {osmTab === 'ui' && (
                <div className="space-y-3">
                  {!topologyId ? (
                    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 p-3 text-sm text-gray-700 dark:text-gray-300">
                      Select a topology first. ETSI OSM runs as an isolated per-topology stack.
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="default" size="sm">
                          Login: admin / admin
                        </Badge>
                        <Badge variant={osmConnectorRunning ? 'success' : 'default'} size="sm">
                          Stack: {osmConnectorRunning ? 'running' : 'stopped'}
                        </Badge>
                        <Button
                          size="xs"
                          variant="secondary"
                          onClick={() => osmEnsureInfraMutation.mutate()}
                          disabled={!topologyId || osmEnsureInfraMutation.isPending}
                        >
                          Start / Ensure
                        </Button>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <Button size="xs" variant={osmUiKind === 'ng' ? 'primary' : 'secondary'} onClick={() => setOsmUiKind('ng')}>
                          NG-UI
                        </Button>
                        <Button size="xs" variant={osmUiKind === 'light' ? 'primary' : 'secondary'} onClick={() => setOsmUiKind('light')}>
                          Light UI
                        </Button>
                        <Button
                          size="xs"
                          variant="secondary"
                          onClick={() => {
                            const id8 = String(topologyId).slice(0, 8)
                            window.open(
                              osmUiKind === 'ng' ? `/infra-proxy/osm-ng-ui/${id8}/` : `/infra-proxy/osm-light-ui/${id8}/`,
                              '_blank',
                              'noopener,noreferrer'
                            )
                          }}
                        >
                          Open in new tab
                        </Button>
                      </div>

                      {!osmConnectorRunning ? (
                        <div className="rounded-xl border border-yellow-200 dark:border-yellow-900 bg-yellow-50 dark:bg-yellow-950/30 p-3 text-sm text-yellow-900 dark:text-yellow-200">
                          OSM stack is not running yet. Click “Start / Ensure”, then reload this tab.
                        </div>
                      ) : (
                        <div className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
                          <iframe
                            title={osmUiKind === 'ng' ? 'OSM NG-UI' : 'OSM Light UI'}
                            className="w-full h-[720px] bg-white"
                            src={
                              osmUiKind === 'ng'
                                ? `/infra-proxy/osm-ng-ui/${String(topologyId).slice(0, 8)}/`
                                : `/infra-proxy/osm-light-ui/${String(topologyId).slice(0, 8)}/`
                            }
                          />
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}

      {manoPane === 'local' && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-3">
                  <CardTitle>Catalog</CardTitle>
                  <div className="flex items-center gap-2">
                    <Button size="xs" variant={manoCatalogTab === 'nsd' ? 'primary' : 'secondary'} onClick={() => setManoCatalogTab('nsd')}>
                      NSDs
                    </Button>
                    <Button
                      size="xs"
                      variant={manoCatalogTab === 'vnfd' ? 'primary' : 'secondary'}
                      onClick={() => setManoCatalogTab('vnfd')}
                    >
                      VNFDs
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {manoCatalogTab === 'nsd' ? (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="space-y-3">
                      <Input value={manoNsdName} onChange={(e) => setManoNsdName(e.target.value)} label="NSD name" />
                      <Input
                        value={manoNsdTopologyId}
                        onChange={(e) => setManoNsdTopologyId(e.target.value)}
                        label="Topology ID"
                        helperText="Leave empty for descriptor-only catalogs; use a valid topology UUID to orchestrate."
                      />
                      <div>
                        <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Options</div>
                        <KvTableEditor rows={manoNsdOptionRows} setRows={setManoNsdOptionRows} />
                        {!!manoNsdDescriptor.errors.length && (
                          <div className="mt-2 text-xs text-red-600 dark:text-red-400">{manoNsdDescriptor.errors.join(' · ')}</div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          onClick={() => upsertNsdMutation.mutate()}
                          disabled={upsertNsdMutation.isPending || !!manoNsdDescriptor.errors.length || !manoNsdName.trim()}
                          variant="primary"
                        >
                          Save NSD
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => {
                            setManoSelectedNsdId('')
                            setManoNsdName('demo-nsd')
                            setManoNsdTopologyId(topologyId || '')
                            setManoNsdOptionRows([newKvRow()])
                          }}
                        >
                          New
                        </Button>
                      </div>
                      <details className="text-sm">
                        <summary className="cursor-pointer text-gray-700 dark:text-gray-300">JSON preview</summary>
                        <div className="mt-2">
                          <JsonViewer data={manoNsdDescriptor.descriptor} collapsed={2} />
                        </div>
                      </details>
                    </div>

                    <div className="space-y-2">
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300">NSDs</div>
                      <div className="max-h-80 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                        <table className="min-w-full text-sm">
                          <thead className="bg-gray-50 dark:bg-gray-800">
                            <tr className="text-left">
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">ID</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(manoNsdsQuery.data || []).map((nsd: any) => (
                              <tr
                                key={nsd.id}
                                className={cn(
                                  'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                                  manoSelectedNsdId === String(nsd.id) && 'bg-blue-50 dark:bg-blue-950/30'
                                )}
                                onClick={() => {
                                  setManoSelectedNsdId(String(nsd.id))
                                  setManoNsdName(String(nsd.name || ''))
                                  const d = (nsd.descriptor || {}) as any
                                  setManoNsdTopologyId(String(d.topology_id || topologyId || ''))
                                  setManoNsdOptionRows(kvObjectToRows(d.options || {}))
                                }}
                              >
                                <td className="px-3 py-2 font-medium">{nsd.name}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(nsd.id).slice(0, 8)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {!manoNsdsQuery.data?.length && <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No NSDs yet.</div>}
                      </div>

                      {manoSelectedNsd && (
                        <details className="text-sm">
                          <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Selected NSD details</summary>
                          <div className="mt-2">
                            <JsonViewer data={manoSelectedNsd} collapsed={2} />
                          </div>
                        </details>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div className="space-y-3">
                      <Input value={manoVnfdName} onChange={(e) => setManoVnfdName(e.target.value)} label="VNFD name" />
                      <Input
                        value={manoVnfdDeviceType}
                        onChange={(e) => setManoVnfdDeviceType(e.target.value)}
                        label="Device type"
                        helperText="Examples: container, host, router, switch, station"
                      />
                      <div>
                        <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Default properties</div>
                        <KvTableEditor rows={manoVnfdDefaultsRows} setRows={setManoVnfdDefaultsRows} />
                        {!!manoVnfdDescriptor.errors.length && (
                          <div className="mt-2 text-xs text-red-600 dark:text-red-400">{manoVnfdDescriptor.errors.join(' · ')}</div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          onClick={() => upsertVnfdMutation.mutate()}
                          disabled={upsertVnfdMutation.isPending || !!manoVnfdDescriptor.errors.length || !manoVnfdName.trim()}
                          variant="primary"
                        >
                          Save VNFD
                        </Button>
                        <Button
                          variant="secondary"
                          onClick={() => {
                            setManoSelectedVnfdId('')
                            setManoVnfdName('demo-vnfd')
                            setManoVnfdDeviceType('container')
                            setManoVnfdDefaultsRows([newKvRow()])
                          }}
                        >
                          New
                        </Button>
                      </div>
                      <details className="text-sm">
                        <summary className="cursor-pointer text-gray-700 dark:text-gray-300">JSON preview</summary>
                        <div className="mt-2">
                          <JsonViewer data={manoVnfdDescriptor.descriptor} collapsed={2} />
                        </div>
                      </details>
                    </div>

                    <div className="space-y-2">
                      <div className="text-sm font-medium text-gray-700 dark:text-gray-300">VNFDs</div>
                      <div className="max-h-80 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                        <table className="min-w-full text-sm">
                          <thead className="bg-gray-50 dark:bg-gray-800">
                            <tr className="text-left">
                              <th className="px-3 py-2 font-medium">Name</th>
                              <th className="px-3 py-2 font-medium">Type</th>
                            </tr>
                          </thead>
                          <tbody>
                            {(manoVnfdsQuery.data || []).map((vnfd: any) => (
                              <tr
                                key={vnfd.id}
                                className={cn(
                                  'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                                  manoSelectedVnfdId === String(vnfd.id) && 'bg-blue-50 dark:bg-blue-950/30'
                                )}
                                onClick={() => {
                                  setManoSelectedVnfdId(String(vnfd.id))
                                  setManoVnfdName(String(vnfd.name || ''))
                                  const d = (vnfd.descriptor || {}) as any
                                  setManoVnfdDeviceType(String(d.device_type || 'container'))
                                  setManoVnfdDefaultsRows(kvObjectToRows(d.default_properties || {}))
                                }}
                              >
                                <td className="px-3 py-2 font-medium">{vnfd.name}</td>
                                <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(vnfd?.descriptor?.device_type || '—')}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                        {!manoVnfdsQuery.data?.length && <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No VNFDs yet.</div>}
                      </div>
                      {manoSelectedVnfd && (
                        <details className="text-sm">
                          <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Selected VNFD details</summary>
                          <div className="mt-2">
                            <JsonViewer data={manoSelectedVnfd} collapsed={2} />
                          </div>
                        </details>
                      )}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>NS Instances</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Input value={manoNsName} onChange={(e) => setManoNsName(e.target.value)} label="NS name" />
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">NSD</label>
                    {manoNsBackend === 'osm' ? (
                      <Input value={manoOsmNsdId} onChange={(e) => setManoOsmNsdId(e.target.value)} placeholder="OSM nsd_id" />
                    ) : (
                      <select
                        value={manoSelectedNsdId}
                        onChange={(e) => setManoSelectedNsdId(e.target.value)}
                        className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                      >
                        <option value="">(none)</option>
                        {(manoNsdsQuery.data || []).map((nsd: any) => (
                          <option key={nsd.id} value={String(nsd.id)}>
                            {nsd.name}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Backend</label>
                    <select
                      value={manoNsBackend}
                      onChange={(e) => setManoNsBackend(e.target.value as any)}
                      className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                    >
                      <option value="local">local (Mininet)</option>
                      <option value="osm">OSM (ETSI NFVO)</option>
                    </select>
                  </div>
                  {manoNsBackend === 'osm' ? (
                    <Input value={manoOsmVimAccountId} onChange={(e) => setManoOsmVimAccountId(e.target.value)} label="vim_account_id" placeholder="OSM vimAccountId" />
                  ) : (
                    <div />
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={manoNsDryRun} onChange={(e) => setManoNsDryRun(e.target.checked)} />
                    dry_run
                  </label>
                  <Button onClick={() => createNsMutation.mutate()} disabled={createNsMutation.isPending || !manoNsName.trim()} variant="primary">
                    Create NS
                  </Button>
                  {manoNsBackend === 'local' && (
                    <Badge variant="default" size="sm">
                      topology: {topologyId ? topologyId.slice(0, 8) : '—'}
                    </Badge>
                  )}
                </div>

                <div className="max-h-[420px] overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-800">
                      <tr className="text-left">
                        <th className="px-3 py-2 font-medium">Name</th>
                        <th className="px-3 py-2 font-medium">Status</th>
                        <th className="px-3 py-2 font-medium">Backend</th>
                        <th className="px-3 py-2 font-medium">NSD</th>
                        <th className="px-3 py-2 w-28" />
                      </tr>
                    </thead>
                    <tbody>
                      {(manoNsInstancesQuery.data || []).map((ns: any) => (
                        <tr
                          key={ns.id}
                          className={cn(
                            'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                            manoSelectedNsId === String(ns.id) && 'bg-blue-50 dark:bg-blue-950/30'
                          )}
                          onClick={() => setManoSelectedNsId(String(ns.id))}
                        >
                          <td className="px-3 py-2 font-medium">{ns.name}</td>
                          <td className="px-3 py-2">
                            <Badge variant="default" size="sm">
                              {String(ns.status)}
                            </Badge>
                          </td>
                          <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">{String(ns.backend || 'local')}</td>
                          <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                            {ns.nsd_id ? String(ns.nsd_id).slice(0, 8) : '—'}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <Button
                              size="xs"
                              variant="secondary"
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                terminateNsMutation.mutate(String(ns.id))
                              }}
                              disabled={terminateNsMutation.isPending}
                            >
                              Terminate
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!manoNsInstancesQuery.data?.length && (
                    <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No NS instances yet.</div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>VNFM (VNF Instances)</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">NS</label>
                  <select
                    value={manoSelectedNsId}
                    onChange={(e) => setManoSelectedNsId(e.target.value)}
                    className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  >
                    <option value="">(select NS instance)</option>
                    {(manoNsInstancesQuery.data || []).map((ns: any) => (
                      <option key={ns.id} value={String(ns.id)}>
                        {ns.name} ({String(ns.id).slice(0, 8)})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">VNFD</label>
                  <select
                    value={manoSelectedVnfdId}
                    onChange={(e) => setManoSelectedVnfdId(e.target.value)}
                    className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  >
                    <option value="">(optional)</option>
                    {(manoVnfdsQuery.data || []).map((vnfd: any) => (
                      <option key={vnfd.id} value={String(vnfd.id)}>
                        {vnfd.name}
                      </option>
                    ))}
                  </select>
                  {manoSelectedVnfd && (
                    <div className="mt-2 flex items-center justify-between gap-2">
                      <div className="text-xs text-gray-600 dark:text-gray-400">type: {String(manoSelectedVnfd?.descriptor?.device_type || '—')}</div>
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => {
                          const d = (manoSelectedVnfd?.descriptor || {}) as any
                          setManoVnfDeviceType(String(d.device_type || manoVnfDeviceType || 'container'))
                          setManoVnfPropsRows(kvObjectToRows(d.default_properties || {}))
                        }}
                      >
                        Apply defaults
                      </Button>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Input value={manoVnfName} onChange={(e) => setManoVnfName(e.target.value)} label="VNF name" />
                  <Input
                    value={manoVnfDeviceType}
                    onChange={(e) => setManoVnfDeviceType(e.target.value)}
                    label="Device type"
                    helperText="Used if VNFD is not set or defaults are overridden."
                  />
                </div>

                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Properties</div>
                  <KvTableEditor rows={manoVnfPropsRows} setRows={setManoVnfPropsRows} />
                  {!!manoVnfProperties.errors.length && (
                    <div className="mt-2 text-xs text-red-600 dark:text-red-400">{manoVnfProperties.errors.join(' · ')}</div>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={manoVnfDryRun} onChange={(e) => setManoVnfDryRun(e.target.checked)} />
                    dry_run
                  </label>
                  <Button
                    onClick={() => createVnfMutation.mutate()}
                    disabled={!manoSelectedNsId || createVnfMutation.isPending || !!manoVnfProperties.errors.length || !manoVnfName.trim()}
                    variant="primary"
                  >
                    Create VNF
                  </Button>
                </div>

                <details className="text-sm">
                  <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Properties JSON</summary>
                  <div className="mt-2">
                    <JsonViewer data={manoVnfProperties.properties} collapsed={2} />
                  </div>
                </details>

                <div className="max-h-64 overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-800">
                      <tr className="text-left">
                        <th className="px-3 py-2 font-medium">Name</th>
                        <th className="px-3 py-2 font-medium">Status</th>
                        <th className="px-3 py-2 font-medium">Device</th>
                        <th className="px-3 py-2 font-medium">Message</th>
                        <th className="px-3 py-2 w-24" />
                      </tr>
                    </thead>
                    <tbody>
                      {(manoVnfsQuery.data || []).map((vnf: any) => (
                        <tr
                          key={vnf.id}
                          className={cn(
                            'border-t border-gray-200 dark:border-gray-800 cursor-pointer',
                            manoSelectedVnfId === String(vnf.id) && 'bg-blue-50 dark:bg-blue-950/30'
                          )}
                          onClick={() => setManoSelectedVnfId(String(vnf.id))}
                        >
                          <td className="px-3 py-2 font-medium">{vnf.name}</td>
                          <td className="px-3 py-2">
                            <Badge variant="default" size="sm">
                              {String(vnf.status)}
                            </Badge>
                          </td>
                          <td className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400">
                            {vnf.device_name || '—'} ({vnf.device_type})
                          </td>
                          <td
                            className="px-3 py-2 text-xs text-gray-600 dark:text-gray-400 truncate max-w-[240px]"
                            title={String(vnf.message || '')}
                          >
                            {String(vnf.message || '—')}
                          </td>
                          <td className="px-3 py-2 text-right">
                            <Button
                              size="xs"
                              variant="danger"
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                const name = String(vnf?.name || vnf?.id || 'VNF')
                                if (!confirm(`Delete ${name}?`)) return
                                deleteVnfMutation.mutate({ vnfId: String(vnf.id), force: manoVnfDeleteForce })
                              }}
                              disabled={deleteVnfMutation.isPending}
                            >
                              Delete
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!manoVnfsQuery.data?.length && <div className="p-3 text-sm text-gray-600 dark:text-gray-400">No VNFs yet.</div>}
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={manoVnfDeleteForce} onChange={(e) => setManoVnfDeleteForce(e.target.checked)} />
                    force delete
                  </label>
                  <div className="flex-1" />
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => {
                      if (!manoSelectedVnfId) return
                      const selected = (manoVnfsQuery.data || []).find((x: any) => String(x?.id) === String(manoSelectedVnfId))
                      const name = String(selected?.name || manoSelectedVnfId)
                      if (!confirm(`Delete selected VNF: ${name}?`)) return
                      deleteVnfMutation.mutate({ vnfId: manoSelectedVnfId, force: manoVnfDeleteForce })
                    }}
                    disabled={!manoSelectedVnfId || deleteVnfMutation.isPending}
                  >
                    Delete selected
                  </Button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <Input value={manoExecCommand} onChange={(e) => setManoExecCommand(e.target.value)} label="Command" />
                  <Button
                    onClick={() => execVnfMutation.mutate()}
                    disabled={!manoSelectedVnfId || execVnfMutation.isPending}
                    variant="secondary"
                  >
                    Exec (selected VNF)
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>VIM Inventory</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 max-h-[720px] overflow-auto">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="default" size="sm">
                    topology:{' '}
                    {manoInventoryQuery.data?.scope?.topology_id ? String(manoInventoryQuery.data.scope.topology_id).slice(0, 8) : '—'}
                  </Badge>
                  <Badge variant="default" size="sm">
                    emulation:{' '}
                    {manoInventoryQuery.data?.scope?.emulation_id ? String(manoInventoryQuery.data.scope.emulation_id).slice(0, 8) : '—'}
                  </Badge>
                  <Badge variant="default" size="sm">
                    errors: {String((manoInventoryQuery.data?.errors || []).length)}
                  </Badge>
                </div>
                {!!(manoInventoryQuery.data?.errors || []).length && (
                  <div className="space-y-1">
                    {(manoInventoryQuery.data?.errors || []).map((e: any, idx: number) => (
                      <div key={idx} className="text-xs text-red-600 dark:text-red-400">
                        {e.component}: {e.error}
                      </div>
                    ))}
                  </div>
                )}
                <details className="text-sm">
                  <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Devices</summary>
                  <div className="mt-2">
                    <JsonViewer data={manoInventoryQuery.data?.devices || null} collapsed={2} />
                  </div>
                </details>
                <details className="text-sm">
                  <summary className="cursor-pointer text-gray-700 dark:text-gray-300">Containers</summary>
                  <div className="mt-2">
                    <JsonViewer data={manoInventoryQuery.data?.containers || null} collapsed={2} />
                  </div>
                </details>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Operations</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 max-h-[720px] overflow-auto">
                {(manoOpsQuery.data?.items || []).map((op: any) => (
                  <details key={op.id} className="p-3 rounded-lg border border-gray-200 dark:border-gray-800">
                    <summary className="cursor-pointer list-none">
                      <div className="flex items-center justify-between gap-2">
                        <div className="font-medium text-sm">{op.kind}</div>
                        <Badge variant="default" size="sm">
                          {op.status}
                        </Badge>
                      </div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">{String(op.id).slice(0, 8)}</div>
                      {op.message && <div className="text-xs mt-1">{op.message}</div>}
                    </summary>
                    <div className="mt-2">
                      <JsonViewer data={op} collapsed={2} />
                    </div>
                  </details>
                ))}
                {!manoOpsQuery.data?.items?.length && <div className="text-sm text-gray-600 dark:text-gray-400">No operations yet.</div>}
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  )
}
