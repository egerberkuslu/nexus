import { useEffect, useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'

import { Button } from '@/components/atoms/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'
import { Input } from '@/components/atoms/Input'
import JsonViewer from '@/components/JsonViewer'
import { configAPI } from '@/services/api'
import { cn } from '@/utils/cn'
import { Boxes, Cpu, PlayCircle, Server, Settings2, Terminal } from 'lucide-react'

type ControlConfigPanelProps = {
  topologyId?: string | null
  emulationId?: string | null
  deviceNames?: string[]
  controllerIds?: string[]
}

type JsonParseOk = { ok: true; data: any }
type JsonParseErr = { ok: false; error: string }
type JsonParseResult = JsonParseOk | JsonParseErr

const isJsonParseErr = (res: JsonParseResult): res is JsonParseErr => res.ok === false

const safeJsonParse = (value: string): JsonParseResult => {
  try {
    return { ok: true, data: JSON.parse(value || '{}') }
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Invalid JSON' }
  }
}

export default function ControlConfigPanel({
  topologyId,
  emulationId,
  deviceNames = [],
  controllerIds = [],
}: ControlConfigPanelProps) {
  const selectClassName = cn(
    'w-full px-4 py-2 rounded-xl border transition-all duration-200',
    'bg-white dark:bg-gray-800',
    'text-gray-900 dark:text-gray-100',
    'focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent',
    'border-gray-300 dark:border-gray-600'
  )
  const [uiMode, setUiMode] = useState<'guided' | 'json'>('guided')
  const [text, setText] = useState<string>(() =>
    JSON.stringify(
      {
        schema: 'caduceus.control-config.v1',
        topology_id: topologyId || '',
        dry_run: true,
        actions: [],
      },
      null,
      2
    )
  )
  const [forceDryRun, setForceDryRun] = useState<boolean>(true)
  const [validateResult, setValidateResult] = useState<any>(null)
  const [applyResult, setApplyResult] = useState<any>(null)

  const parsed = useMemo(() => safeJsonParse(text), [text])
  const parsedCfg = useMemo(() => (parsed.ok ? (parsed.data || {}) : {}), [parsed])

  const actions = useMemo(() => {
    const list = (parsedCfg as any)?.actions
    return Array.isArray(list) ? list : []
  }, [parsedCfg])

  const deviceOptions = useMemo(
    () => Array.from(new Set((deviceNames || []).map((d) => String(d || '').trim()).filter(Boolean))).sort(),
    [deviceNames]
  )
  const controllerOptions = useMemo(
    () => Array.from(new Set((controllerIds || []).map((c) => String(c || '').trim()).filter(Boolean))).sort(),
    [controllerIds]
  )

  const updateConfig = (mutate: (cfg: any) => any) => {
    const base = parsed.ok
      ? parsed.data
      : {
          schema: 'caduceus.control-config.v1',
          topology_id: topologyId || '',
          dry_run: true,
          actions: [],
        }
    const cloned = JSON.parse(JSON.stringify(base || {}))
    const next = mutate(cloned)
    setText(JSON.stringify(next, null, 2))
  }

  const ensureConfigBasics = (cfg: any) => {
    if (!cfg || typeof cfg !== 'object') cfg = {}
    if (!cfg.schema) cfg.schema = 'caduceus.control-config.v1'
    if (typeof cfg.topology_id !== 'string' || !cfg.topology_id.trim()) cfg.topology_id = topologyId || ''
    if (!Array.isArray(cfg.actions)) cfg.actions = []
    return cfg
  }

  const addAction = (kind: string, params: any = {}, dryRunOverride?: boolean) => {
    updateConfig((cfg) => {
      cfg = ensureConfigBasics(cfg)
      const idBase = kind.replace(/[^\w]+/g, '-').slice(0, 28) || 'action'
      const id = `${idBase}-${Date.now().toString(36)}`
      const action: any = { id, kind, params: params || {} }
      if (typeof dryRunOverride === 'boolean') action.dry_run = dryRunOverride
      cfg.actions.push(action)
      return cfg
    })
    toast.success('Action added')
  }

  const removeActionAt = (idx: number) => {
    updateConfig((cfg) => {
      cfg = ensureConfigBasics(cfg)
      cfg.actions = cfg.actions.filter((_: any, i: number) => i !== idx)
      return cfg
    })
  }

  const moveAction = (idx: number, dir: -1 | 1) => {
    updateConfig((cfg) => {
      cfg = ensureConfigBasics(cfg)
      const list = cfg.actions
      const j = idx + dir
      if (idx < 0 || idx >= list.length || j < 0 || j >= list.length) return cfg
      const next = [...list]
      const [item] = next.splice(idx, 1)
      next.splice(j, 0, item)
      cfg.actions = next
      return cfg
    })
  }

  const humanizeAction = (a: any): string => {
    const kind = String(a?.kind || '')
    const p = (a?.params && typeof a.params === 'object') ? a.params : {}
    if (kind === 'topology.infra.ensure') return 'Ensure topology infrastructure'
    if (kind === 'topology.osm.ensure') return 'Ensure per-topology ETSI OSM stack'
    if (kind === 'emulation.start') return 'Start emulation'
    if (kind === 'emulation.stop') return `Stop emulation (${String(p.emulation_id || '').slice(0, 12) || 'emulation_id?'})`
    if (kind === 'device.exec') return `Exec on ${String(p.device || 'device?')}: ${String(p.command || '').slice(0, 40)}`
    if (kind === 'sdn.controller.restart') return `Restart controller ${String(p.controller_id || 'controller?')}`
    if (kind === 'sdn.controller.exec') return `Exec on controller ${String(p.controller_id || 'controller?')}: ${String(p.command || '').slice(0, 40)}`
    if (kind === 'mano.ns.create') return `Create NS (${String(p.backend || 'local')}) ${String(p.name || 'name?')}`
    if (kind === 'mano.ns.terminate') return `Terminate NS ${String(p.ns_instance_id || p.ns_id || '').slice(0, 12) || 'ns_id?'}`
    if (kind === 'mano.vnf.create') return `Create VNF ${String(p.name || 'name?')} (ns=${String(p.ns_instance_id || '').slice(0, 12) || '?'})`
    if (kind === 'mano.vnf.exec') return `Exec VNF ${String(p.vnf_instance_id || p.vnf_id || '').slice(0, 12) || 'vnf_id?'}`
    if (kind === 'mcp.request') return `${String(p.method || 'GET').toUpperCase()} ${String(p.path || '/api/...')}`
    return kind || 'action'
  }

  const kindVariant = (kindRaw: unknown): 'default' | 'success' | 'warning' | 'error' | 'info' | 'primary' => {
    const kind = String(kindRaw || '')
    if (kind.startsWith('topology.') || kind.startsWith('mcp.')) return 'info'
    if (kind.startsWith('emulation.')) return 'success'
    if (kind.startsWith('network_config.') || kind.startsWith('device.')) return 'primary'
    if (kind.startsWith('sdn.')) return 'warning'
    if (kind.startsWith('mano.')) return 'warning'
    return 'default'
  }

  const [quickSysctlDevice, setQuickSysctlDevice] = useState<string>('')
  const [quickSysctlKey, setQuickSysctlKey] = useState<string>('net.ipv4.ip_forward')
  const [quickSysctlValue, setQuickSysctlValue] = useState<string>('1')

  const [quickExecDevice, setQuickExecDevice] = useState<string>('')
  const [quickExecCommand, setQuickExecCommand] = useState<string>('ip addr')

  const [quickControllerId, setQuickControllerId] = useState<string>('')
  const [quickControllerCommand, setQuickControllerCommand] = useState<string>('ps aux | head')

  const [quickNsName, setQuickNsName] = useState<string>('demo-ns')
  const [quickNsBackend, setQuickNsBackend] = useState<'local' | 'osm'>('local')

  useEffect(() => {
    if (!quickSysctlDevice && deviceOptions.length) setQuickSysctlDevice(deviceOptions[0])
    if (!quickExecDevice && deviceOptions.length) setQuickExecDevice(deviceOptions[0])
  }, [deviceOptions, quickExecDevice, quickSysctlDevice])

  useEffect(() => {
    if (!quickControllerId && controllerOptions.length) setQuickControllerId(controllerOptions[0])
  }, [controllerOptions, quickControllerId])

  const loadTemplateMutation = useMutation({
    mutationFn: async () => (await configAPI.template({ topology_id: topologyId || undefined })).data,
    onSuccess: (data) => {
      setText(JSON.stringify(data, null, 2))
      toast.success('Template loaded')
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || err?.message || 'Failed to load template'),
  })

  const validateMutation = useMutation({
    mutationFn: async (payload: any) => (await configAPI.validate(payload)).data,
    onSuccess: (data) => {
      setValidateResult(data)
      toast[data?.ok ? 'success' : 'error'](data?.ok ? 'Valid' : 'Validation failed')
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || err?.message || 'Validation failed'),
  })

  const applyMutation = useMutation({
    mutationFn: async (payload: any) => (await configAPI.apply(payload)).data,
    onSuccess: (data) => {
      setApplyResult(data)
      toast[data?.ok ? 'success' : 'error'](data?.ok ? 'Applied' : 'Completed with errors')
    },
    onError: (err: any) => toast.error(err?.response?.data?.detail || err?.message || 'Apply failed'),
  })

  const buildPayload = (): any => {
    const res = safeJsonParse(text)
    if (isJsonParseErr(res)) throw new Error(res.error)
    const payload = res.data || {}
    if (topologyId && !payload.topology_id) payload.topology_id = topologyId
    if (forceDryRun) payload.dry_run = true
    return payload
  }

  const prettify = () => {
    const res = safeJsonParse(text)
    if (isJsonParseErr(res)) {
      toast.error(res.error)
      return
    }
    setText(JSON.stringify(res.data, null, 2))
  }

  return (
    <Card>
      <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle>Control Config (MANO + SDN + Network)</CardTitle>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Guided controls for common actions, plus an advanced JSON editor when you need full flexibility.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {topologyId ? (
            <Badge variant="info" size="sm">
              Topology: <span className="font-mono">{topologyId.slice(0, 8)}</span>
            </Badge>
          ) : (
            <Badge variant="default" size="sm">
              Select a topology
            </Badge>
          )}
          {emulationId ? (
            <Badge variant="default" size="sm">
              Emulation: <span className="font-mono">{String(emulationId).slice(0, 12)}</span>
            </Badge>
          ) : null}
          <Button size="sm" variant={uiMode === 'guided' ? 'primary' : 'secondary'} onClick={() => setUiMode('guided')}>
            Guided
          </Button>
          <Button size="sm" variant={uiMode === 'json' ? 'primary' : 'secondary'} onClick={() => setUiMode('json')}>
            JSON
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => loadTemplateMutation.mutate()}
            disabled={!topologyId || loadTemplateMutation.isPending}
            isLoading={loadTemplateMutation.isPending}
          >
            Load Template
          </Button>
          <Button variant="secondary" size="sm" onClick={prettify} disabled={!parsed.ok}>
            Prettify
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={forceDryRun}
              onChange={(e) => setForceDryRun(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 dark:border-gray-600"
            />
            Force dry run
          </label>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => {
                try {
                  validateMutation.mutate(buildPayload())
                } catch (e: any) {
                  toast.error(e?.message || 'Invalid JSON')
                }
              }}
              disabled={!parsed.ok || validateMutation.isPending}
              isLoading={validateMutation.isPending}
            >
              Validate
            </Button>
            <Button
              variant="primary"
              onClick={() => {
                try {
                  applyMutation.mutate(buildPayload())
                } catch (e: any) {
                  toast.error(e?.message || 'Invalid JSON')
                }
              }}
              disabled={!parsed.ok || applyMutation.isPending}
              isLoading={applyMutation.isPending}
            >
              Apply
            </Button>
          </div>
        </div>

        {isJsonParseErr(parsed) && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200">
            JSON parse error: <span className="font-mono">{parsed.error}</span>
          </div>
        )}

        {uiMode === 'guided' ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-4">
              <div className="rounded-2xl border border-gray-200 dark:border-gray-800 p-4 space-y-3 bg-gradient-to-br from-blue-50/60 via-white to-purple-50/60 dark:from-blue-950/25 dark:via-gray-950 dark:to-purple-950/20">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="h-9 w-9 rounded-xl bg-blue-600/10 dark:bg-blue-400/10 text-blue-700 dark:text-blue-300 flex items-center justify-center">
                      <PlayCircle size={18} />
                    </div>
                    <div>
                      <div className="text-sm font-semibold text-gray-900 dark:text-white">Quick actions</div>
                      <div className="text-xs text-gray-600 dark:text-gray-400">Build a run plan without writing JSON.</div>
                    </div>
                  </div>
                  <Button
                    size="xs"
                    variant="danger"
                    onClick={() => {
                      if (!confirm('Clear all actions?')) return
                      updateConfig((cfg) => {
                        cfg = ensureConfigBasics(cfg)
                        cfg.actions = []
                        return cfg
                      })
                    }}
                    disabled={!actions.length}
                  >
                    Clear
                  </Button>
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400">
                  Add common actions as structured cards. Switch to JSON for advanced editing.
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-2xl border border-blue-200/70 dark:border-blue-900/50 bg-white/70 dark:bg-gray-900/40 p-4 space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="h-10 w-10 rounded-xl bg-blue-600/10 dark:bg-blue-400/10 text-blue-700 dark:text-blue-300 flex items-center justify-center">
                        <Server size={18} />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Infrastructure</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400">
                          Ensure infra + per-topology ETSI OSM, then start emulation.
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="xs" variant="secondary" onClick={() => addAction('topology.infra.ensure', {})} disabled={!topologyId}>
                        Ensure infra
                      </Button>
                      <Button size="xs" variant="secondary" onClick={() => addAction('topology.osm.ensure', {})} disabled={!topologyId}>
                        Ensure OSM
                      </Button>
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => {
                          addAction('topology.infra.ensure', {})
                          addAction('topology.osm.ensure', {})
                          addAction('emulation.start', { options: {} })
                        }}
                        disabled={!topologyId}
                      >
                        Quick start flow
                      </Button>
                    </div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">
                      Tip: click <span className="font-mono">Quick start flow</span> for a ready-to-run sequence.
                    </div>
                  </div>

                  <div className="rounded-2xl border border-green-200/70 dark:border-green-900/50 bg-white/70 dark:bg-gray-900/40 p-4 space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="h-10 w-10 rounded-xl bg-green-600/10 dark:bg-green-400/10 text-green-700 dark:text-green-300 flex items-center justify-center">
                        <PlayCircle size={18} />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Emulation</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400">Start/stop the runtime for this topology.</div>
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button size="xs" variant="secondary" onClick={() => addAction('emulation.start', { options: {} })} disabled={!topologyId}>
                        Start
                      </Button>
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() =>
                          addAction('emulation.stop', {
                            emulation_id: emulationId || '',
                            cleanup: true,
                            stop_infra: true,
                            preserve_infra_data: true,
                          })
                        }
                      >
                        Stop…
                      </Button>
                    </div>
                    <div className="text-xs text-gray-600 dark:text-gray-400">
                      Use JSON mode to fill <span className="font-mono">emulation_id</span> (stop needs an id).
                    </div>
                  </div>

                  <div className="rounded-2xl border border-purple-200/70 dark:border-purple-900/50 bg-white/70 dark:bg-gray-900/40 p-4 space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="h-10 w-10 rounded-xl bg-purple-600/10 dark:bg-purple-400/10 text-purple-700 dark:text-purple-300 flex items-center justify-center">
                        <Settings2 size={18} />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Network config (sysctl)</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400">
                          Apply sysctls on a device (e.g. routing, TCP params).
                        </div>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <div className="sm:col-span-1">
                        <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Device</label>
                        <select className={selectClassName} value={quickSysctlDevice} onChange={(e) => setQuickSysctlDevice(e.target.value)}>
                          <option value="">{deviceOptions.length ? 'Select…' : 'No devices (start emulation)'}</option>
                          {deviceOptions.map((d) => (
                            <option key={d} value={d}>
                              {d}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="sm:col-span-1">
                        <Input label="Key" value={quickSysctlKey} onChange={(e) => setQuickSysctlKey(e.target.value)} />
                      </div>
                      <div className="sm:col-span-1">
                        <Input label="Value" value={quickSysctlValue} onChange={(e) => setQuickSysctlValue(e.target.value)} />
                      </div>
                    </div>
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => {
                        if (!quickSysctlDevice) return toast.error('Select a device')
                        if (!quickSysctlKey.trim()) return toast.error('Enter a sysctl key')
                        const cfg = {
                          devices: [
                            {
                              name: quickSysctlDevice,
                              sysctls: { [quickSysctlKey.trim()]: quickSysctlValue },
                            },
                          ],
                        }
                        addAction('network_config.apply', { config: cfg })
                      }}
                      disabled={!topologyId}
                    >
                      Add sysctl apply
                    </Button>
                    <div className="text-xs text-gray-600 dark:text-gray-400">
                      Example: enable routing with <span className="font-mono">net.ipv4.ip_forward=1</span>.
                    </div>
                  </div>

                  <div className="rounded-2xl border border-teal-200/70 dark:border-teal-900/50 bg-white/70 dark:bg-gray-900/40 p-4 space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="h-10 w-10 rounded-xl bg-teal-600/10 dark:bg-teal-400/10 text-teal-700 dark:text-teal-300 flex items-center justify-center">
                        <Terminal size={18} />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">Exec command</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400">Run a one-off command on a device.</div>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Device</label>
                        <select className={selectClassName} value={quickExecDevice} onChange={(e) => setQuickExecDevice(e.target.value)}>
                          <option value="">{deviceOptions.length ? 'Select…' : 'No devices (start emulation)'}</option>
                          {deviceOptions.map((d) => (
                            <option key={d} value={d}>
                              {d}
                            </option>
                          ))}
                        </select>
                      </div>
                      <Input label="Command" value={quickExecCommand} onChange={(e) => setQuickExecCommand(e.target.value)} />
                    </div>
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => {
                        if (!quickExecDevice) return toast.error('Select a device')
                        if (!quickExecCommand.trim()) return toast.error('Enter a command')
                        addAction('device.exec', { device: quickExecDevice, command: quickExecCommand })
                      }}
                      disabled={!topologyId}
                    >
                      Add device exec
                    </Button>
                  </div>

                  <div className="rounded-2xl border border-indigo-200/70 dark:border-indigo-900/50 bg-white/70 dark:bg-gray-900/40 p-4 space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="h-10 w-10 rounded-xl bg-indigo-600/10 dark:bg-indigo-400/10 text-indigo-700 dark:text-indigo-300 flex items-center justify-center">
                        <Cpu size={18} />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">SDN controller</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400">Restart or exec a command inside the controller container.</div>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Controller</label>
                        <select className={selectClassName} value={quickControllerId} onChange={(e) => setQuickControllerId(e.target.value)}>
                          <option value="">{controllerOptions.length ? 'Select…' : 'No controllers (ensure infra)'}</option>
                          {controllerOptions.map((c) => (
                            <option key={c} value={c}>
                              {c}
                            </option>
                          ))}
                        </select>
                      </div>
                      <Input label="Command" value={quickControllerCommand} onChange={(e) => setQuickControllerCommand(e.target.value)} />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => {
                          if (!quickControllerId) return toast.error('Select a controller')
                          addAction('sdn.controller.restart', { controller_id: quickControllerId })
                        }}
                        disabled={!topologyId}
                      >
                        Add restart
                      </Button>
                      <Button
                        size="xs"
                        variant="secondary"
                        onClick={() => {
                          if (!quickControllerId) return toast.error('Select a controller')
                          if (!quickControllerCommand.trim()) return toast.error('Enter a command')
                          addAction('sdn.controller.exec', { controller_id: quickControllerId, command: quickControllerCommand })
                        }}
                        disabled={!topologyId}
                      >
                        Add exec
                      </Button>
                    </div>
                  </div>

                  <div className="rounded-2xl border border-amber-200/70 dark:border-amber-900/50 bg-white/70 dark:bg-gray-900/40 p-4 space-y-3">
                    <div className="flex items-start gap-3">
                      <div className="h-10 w-10 rounded-xl bg-amber-500/15 dark:bg-amber-400/10 text-amber-700 dark:text-amber-300 flex items-center justify-center">
                        <Boxes size={18} />
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">MANO (local)</div>
                        <div className="text-xs text-gray-600 dark:text-gray-400">Create a simple NS using local NFVO/VNFM.</div>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <Input label="NS name" value={quickNsName} onChange={(e) => setQuickNsName(e.target.value)} />
                      <div>
                        <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">Backend</label>
                        <select className={selectClassName} value={quickNsBackend} onChange={(e) => setQuickNsBackend(e.target.value as any)}>
                          <option value="local">local</option>
                          <option value="osm">osm</option>
                        </select>
                      </div>
                    </div>
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => {
                        if (!quickNsName.trim()) return toast.error('Enter an NS name')
                        addAction('mano.ns.create', { name: quickNsName.trim(), backend: quickNsBackend, options: {} })
                      }}
                      disabled={!topologyId}
                    >
                      Add create NS
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium text-gray-900 dark:text-white">Actions</div>
                  <Badge variant="default" size="sm">
                    {actions.length} action{actions.length === 1 ? '' : 's'}
                  </Badge>
                </div>
                <div className="max-h-[420px] overflow-auto rounded-xl border border-gray-200 dark:border-gray-800">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gray-50 dark:bg-gray-800">
                      <tr className="text-left">
                        <th className="px-3 py-2 font-medium">Kind</th>
                        <th className="px-3 py-2 font-medium">Summary</th>
                        <th className="px-3 py-2 w-28" />
                      </tr>
                    </thead>
                    <tbody>
                      {actions.map((a: any, idx: number) => (
                        <tr key={String(a?.id || idx)} className="border-t border-gray-200 dark:border-gray-800">
                          <td className="px-3 py-2">
                            <Badge variant={kindVariant(a?.kind)} size="sm">
                              <span className="font-mono">{String(a?.kind || '—')}</span>
                            </Badge>
                          </td>
                          <td className="px-3 py-2">{humanizeAction(a)}</td>
                          <td className="px-3 py-2 text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button size="xs" variant="secondary" onClick={() => moveAction(idx, -1)} disabled={idx === 0}>
                                ↑
                              </Button>
                              <Button size="xs" variant="secondary" onClick={() => moveAction(idx, 1)} disabled={idx === actions.length - 1}>
                                ↓
                              </Button>
                              <Button
                                size="xs"
                                variant="danger"
                                onClick={() => {
                                  if (!confirm(`Remove action: ${String(a?.kind || 'action')}?`)) return
                                  removeActionAt(idx)
                                }}
                              >
                                Remove
                              </Button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {!actions.length ? (
                    <div className="p-3 text-sm text-gray-600 dark:text-gray-400">
                      No actions yet. Add actions from the left.
                    </div>
                  ) : null}
                </div>
                <details className="text-sm">
                  <summary className="cursor-pointer text-gray-700 dark:text-gray-300">JSON preview</summary>
                  <div className="mt-2">
                    <JsonViewer data={parsedCfg || null} collapsed={2} />
                  </div>
                </details>
              </div>
            </div>
          </div>
        ) : (
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full h-[420px] rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-gray-100 font-mono text-sm p-4 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
            spellCheck={false}
          />
        )}

        {validateResult && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Validation</h3>
              <Badge variant={validateResult.ok ? 'success' : 'error'} size="sm">
                {validateResult.ok ? 'OK' : 'ERROR'}
              </Badge>
            </div>
            <JsonViewer data={validateResult} collapsed={2} />
          </div>
        )}

        {applyResult && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Apply Result</h3>
              <Badge variant={applyResult.ok ? 'success' : 'error'} size="sm">
                {applyResult.ok ? 'OK' : 'ERROR'}
              </Badge>
            </div>
            <JsonViewer data={applyResult} collapsed={2} />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
