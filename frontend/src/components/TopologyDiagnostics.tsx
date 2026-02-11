import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { diagnosticsAPI, aiAPI, type AIProvider } from '@services/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Button } from '@/components/atoms/Button'
import { Input } from '@/components/atoms/Input'
import { Badge } from '@/components/atoms/Badge'
import JsonViewer from '@/components/JsonViewer'
import MarkdownViewer from '@/components/MarkdownViewer'
import AiConsole from '@/components/ai/AiConsole'
import { cn } from '@/utils/cn'
import {
  Line,
  LineChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
} from 'recharts'

type Props = {
  topologyId?: string
  runtimeDevices?: any[]
}

type ChatMsg = {
  id: string
  role: 'user' | 'assistant'
  content: string
  createdAt: number
}

const COLORS = ['#3b82f6', '#22c55e', '#a855f7', '#f97316', '#ef4444', '#06b6d4', '#eab308', '#6366f1']

const FIELD_LABELS: Record<string, { label: string; group: string }> = {
  cpu_percent: { label: 'CPU %', group: 'Performance' },
  memory_percent: { label: 'Memory %', group: 'Performance' },
  bytes_sent: { label: 'Bytes sent', group: 'Traffic' },
  bytes_received: { label: 'Bytes received', group: 'Traffic' },
  packets_sent: { label: 'Packets sent', group: 'Traffic' },
  packets_received: { label: 'Packets received', group: 'Traffic' },
  errors_in: { label: 'Errors in', group: 'Errors' },
  errors_out: { label: 'Errors out', group: 'Errors' },
  drops_in: { label: 'Drops in', group: 'Errors' },
  drops_out: { label: 'Drops out', group: 'Errors' },
}

function uid() {
  return (globalThis as any).crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`
}

function clampInt(raw: string, min: number, max: number, fallback: number) {
  const val = Number.parseInt(raw || '', 10)
  if (Number.isFinite(val)) return Math.max(min, Math.min(max, val))
  return fallback
}

function msFromDatetimeLocal(value: string): number | null {
  const raw = (value || '').trim()
  if (!raw) return null
  const dt = new Date(raw)
  const ms = dt.getTime()
  return Number.isFinite(ms) ? ms : null
}

function safeFieldLabel(field: string) {
  return FIELD_LABELS[field]?.label || field
}

function safeGroup(field: string) {
  return FIELD_LABELS[field]?.group || 'Other'
}

export default function TopologyDiagnostics({ topologyId, runtimeDevices }: Props) {
  const tid = (topologyId || '').trim()
  const [windowMinutes, setWindowMinutes] = useState<string>('60')
  const [everySeconds, setEverySeconds] = useState<string>('5')
  const [selectedDevice, setSelectedDevice] = useState<string>('') // '' => all
  const [customRange, setCustomRange] = useState<boolean>(false)
  const [startLocal, setStartLocal] = useState<string>('')
  const [endLocal, setEndLocal] = useState<string>('')
  const [selectedFields, setSelectedFields] = useState<Set<string>>(new Set(['cpu_percent', 'memory_percent']))

  const [chat, setChat] = useState<ChatMsg[]>([])
  const [chatInput, setChatInput] = useState<string>('')
  const [chatLoading, setChatLoading] = useState<boolean>(false)
  const [lastSummary, setLastSummary] = useState<any>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const { data: settingsData } = useQuery({
    queryKey: ['ai-settings'],
    queryFn: async () => {
      const res = await aiAPI.settings()
      return res.data
    },
    retry: false,
  })

  const providerStatus = useMemo(() => {
    const list = settingsData?.providers || []
    const configured = (list || []).find((p: any) => p.configured)
    return {
      provider: (configured?.provider || 'ollama') as AIProvider,
      model: (configured?.default_model || '') as string,
    }
  }, [settingsData])

  const {
    data: features,
    isLoading: featuresLoading,
    refetch: refetchFeatures,
  } = useQuery({
    queryKey: ['diagnostics-influx-features', tid],
    queryFn: async () => {
      if (!tid) return null
      const res = await diagnosticsAPI.influxFeatures(tid)
      return res.data
    },
    enabled: Boolean(tid),
    staleTime: 15_000,
    retry: false,
  })

  useEffect(() => {
    if (!features?.fields?.length) return
    setSelectedFields((prev) => {
      const next = new Set(prev)
      for (const f of ['cpu_percent', 'memory_percent', 'bytes_sent', 'bytes_received']) {
        if (features.fields.includes(f)) next.add(f)
      }
      return next
    })
  }, [features?.fields])

  const deviceOptions = useMemo(() => {
    const fromInflux = Array.isArray(features?.devices) ? features?.devices : []
    const fromRuntime = Array.isArray(runtimeDevices) ? runtimeDevices.map((d) => String(d?.runtime_name || d?.name || '').trim()) : []
    const list = [...fromInflux, ...fromRuntime].filter(Boolean)
    const uniq = Array.from(new Set(list))
    uniq.sort()
    return uniq
  }, [features?.devices, runtimeDevices])

  const fieldsByGroup = useMemo(() => {
    const available = Array.isArray(features?.fields) ? features.fields : []
    const items = available.length ? available : Array.from(selectedFields)
    const groups = new Map<string, string[]>()
    for (const f of items) {
      const g = safeGroup(f)
      const cur = groups.get(g) || []
      cur.push(f)
      groups.set(g, cur)
    }
    for (const [k, v] of groups) {
      v.sort()
      groups.set(k, v)
    }
    return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]))
  }, [features?.fields, selectedFields])

  const queryPayload = useMemo(() => {
    const fields = Array.from(selectedFields)
    const every = clampInt(everySeconds, 1, 3600, 5)
    const win = clampInt(windowMinutes, 5, 14 * 24 * 60, 60)

    const payload: any = { every_seconds: every, fields }
    if (selectedDevice) payload.device = selectedDevice

    if (customRange) {
      const s = msFromDatetimeLocal(startLocal)
      const e = msFromDatetimeLocal(endLocal)
      if (s && e && e > s) {
        payload.start_ms = s
        payload.end_ms = e
      } else {
        payload.window_minutes = win
      }
    } else {
      payload.window_minutes = win
    }
    return payload
  }, [selectedFields, everySeconds, windowMinutes, selectedDevice, customRange, startLocal, endLocal])

  const {
    data: series,
    isLoading: seriesLoading,
    refetch: refetchSeries,
  } = useQuery({
    queryKey: ['diagnostics-influx-query', tid, queryPayload],
    queryFn: async () => {
      if (!tid) return null
      const res = await diagnosticsAPI.influxQuery(tid, queryPayload)
      return res.data
    },
    enabled: Boolean(tid) && selectedFields.size > 0,
    staleTime: 0,
    retry: false,
  })

  const chartData = useMemo(() => {
    const pts = Array.isArray(series?.points) ? series?.points : []
    const fields = Array.isArray(series?.fields) ? series?.fields : Array.from(selectedFields)
    return pts.map((p: any) => {
      const t = typeof p?.t === 'number' ? p.t : null
      const row: any = {
        t,
        time: t ? new Date(t).toLocaleTimeString() : '',
      }
      for (const f of fields) row[f] = typeof p?.[f] === 'number' ? p[f] : null
      return row
    })
  }, [series?.points, series?.fields, selectedFields])

  const stats = useMemo(() => {
    const fields = Array.isArray(series?.fields) ? series?.fields : Array.from(selectedFields)
    const out: { field: string; min: number; avg: number; max: number; last: number }[] = []
    for (const f of fields) {
      const vals = chartData.map((r: any) => Number(r?.[f])).filter((n) => Number.isFinite(n))
      if (!vals.length) continue
      const sum = vals.reduce((a, b) => a + b, 0)
      out.push({
        field: f,
        min: Math.min(...vals),
        avg: sum / vals.length,
        max: Math.max(...vals),
        last: vals[vals.length - 1],
      })
    }
    return out
  }, [chartData, series?.fields, selectedFields])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [chat.length, chatLoading])

  const toggleField = (f: string) => {
    setSelectedFields((prev) => {
      const next = new Set(prev)
      if (next.has(f)) next.delete(f)
      else next.add(f)
      return next
    })
  }

  const sendAi = async () => {
    const prompt = chatInput.trim()
    if (!tid) return toast.error('Select a topology first')
    if (!selectedFields.size) return toast.error('Select at least one metric')
    if (!prompt) return toast.error('Write a message to analyze')

    const runId = uid()
    setChat((prev) => [...prev, { id: runId, role: 'user', content: prompt, createdAt: Date.now() }])
    setChatInput('')
    setChatLoading(true)
    setLastSummary(null)
    try {
      const res = await aiAPI.network.analyzeDiagnostics({
        topology_id: tid,
        ...queryPayload,
        prompt,
        provider: providerStatus.provider,
        model: providerStatus.model || undefined,
      })
      const content = String((res.data as any)?.content || '').trim()
      setLastSummary((res.data as any)?.summary ?? null)
      setChat((prev) => [...prev, { id: `${runId}-assistant`, role: 'assistant', content, createdAt: Date.now() }])
      toast.success('Analysis ready')
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'AI analysis failed'
      toast.error(msg)
    } finally {
      setChatLoading(false)
    }
  }

  if (!tid) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Diagnostics</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-gray-600 dark:text-gray-400">Select a topology first.</CardContent>
      </Card>
    )
  }

  const fields = Array.isArray(series?.fields) ? series?.fields : Array.from(selectedFields)

  return (
    <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
      <div className="xl:col-span-3 space-y-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Telemetry Filters</CardTitle>
            <Button variant="secondary" size="sm" onClick={() => refetchFeatures()} disabled={featuresLoading}>
              Refresh
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-3">
              <div>
                <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Device</div>
                <select
                  className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                  value={selectedDevice}
                  onChange={(e) => setSelectedDevice(e.target.value)}
                >
                  <option value="">All devices</option>
                  {deviceOptions.map((d) => (
                    <option key={d} value={d}>
                      {d}
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Window (min)</div>
                  <select
                    className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                    value={windowMinutes}
                    onChange={(e) => setWindowMinutes(e.target.value)}
                    disabled={customRange}
                  >
                    <option value="15">15</option>
                    <option value="60">60</option>
                    <option value="240">240</option>
                    <option value="1440">1440</option>
                  </select>
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Interval (s)</div>
                  <select
                    className="w-full rounded-xl border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                    value={everySeconds}
                    onChange={(e) => setEverySeconds(e.target.value)}
                  >
                    <option value="1">1</option>
                    <option value="5">5</option>
                    <option value="10">10</option>
                    <option value="30">30</option>
                    <option value="60">60</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center justify-between gap-2">
                <div className="text-sm font-medium text-gray-700 dark:text-gray-300">Custom range</div>
                <button
                  type="button"
                  onClick={() => setCustomRange((v) => !v)}
                  className={cn(
                    'h-6 w-11 rounded-full border transition-colors',
                    customRange
                      ? 'bg-blue-600 border-blue-600'
                      : 'bg-gray-200 dark:bg-gray-800 border-gray-300 dark:border-gray-700'
                  )}
                  aria-pressed={customRange}
                >
                  <span
                    className={cn(
                      'block h-5 w-5 rounded-full bg-white shadow-sm transition-transform',
                      customRange ? 'translate-x-5' : 'translate-x-0.5'
                    )}
                  />
                </button>
              </div>

              {customRange && (
                <div className="grid grid-cols-1 gap-3">
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Start</div>
                    <Input type="datetime-local" value={startLocal} onChange={(e) => setStartLocal(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">End</div>
                    <Input type="datetime-local" value={endLocal} onChange={(e) => setEndLocal(e.target.value)} />
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2">
                <Button variant="primary" size="sm" onClick={() => refetchSeries()} disabled={seriesLoading}>
                  {seriesLoading ? 'Loading…' : 'Run Query'}
                </Button>
                <Badge variant="info" size="sm">
                  {Array.isArray(series?.points) ? `${series.points.length} pts` : '—'}
                </Badge>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Metrics</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {featuresLoading ? (
              <div className="text-sm text-gray-600 dark:text-gray-400">Loading available metrics…</div>
            ) : (
              <div className="space-y-4">
                {fieldsByGroup.map(([group, items]) => (
                  <div key={group}>
                    <div className="text-xs font-semibold text-gray-600 dark:text-gray-400 mb-2">{group}</div>
                    <div className="space-y-2">
                      {items.map((f) => (
                        <label key={f} className="flex items-center gap-2 text-sm text-gray-800 dark:text-gray-200">
                          <input
                            type="checkbox"
                            checked={selectedFields.has(f)}
                            onChange={() => toggleField(f)}
                            className="h-4 w-4 rounded border-gray-300 dark:border-gray-700"
                          />
                          <span className="flex-1">{safeFieldLabel(f)}</span>
                          <span className="font-mono text-xs text-gray-500">{f}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
            {features && !features.fields?.length && (
              <div className="text-xs text-gray-500 dark:text-gray-400">
                No field keys found yet. Start Metrics Collection and refresh.
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setSelectedFields(new Set(['cpu_percent', 'memory_percent']))}
              >
                CPU + Memory
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() =>
                  setSelectedFields(
                    new Set(['bytes_sent', 'bytes_received', 'packets_sent', 'packets_received'].filter((f) => (features?.fields || []).includes(f) || selectedFields.has(f)))
                  )
                }
              >
                Traffic
              </Button>
              <Button variant="secondary" size="sm" onClick={() => setSelectedFields(new Set())}>
                Clear
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="xl:col-span-6 space-y-6">
        <Card>
          <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <CardTitle>Charts</CardTitle>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              {selectedDevice ? `device=${selectedDevice}` : 'all devices'} · every={clampInt(everySeconds, 1, 3600, 5)}s
            </div>
          </CardHeader>
          <CardContent>
            {!chartData.length ? (
              <div className="text-sm text-gray-600 dark:text-gray-400">No data yet. Start Metrics Collection and run a query.</div>
            ) : (
              <div className="h-[360px]">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="time" tick={{ fontSize: 11 }} minTickGap={24} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    {fields.map((f, idx) => (
                      <Line
                        key={f}
                        type="monotone"
                        dataKey={f}
                        name={safeFieldLabel(f)}
                        dot={false}
                        stroke={COLORS[idx % COLORS.length]}
                        strokeWidth={2}
                        connectNulls
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Summary</CardTitle>
          </CardHeader>
          <CardContent>
            {!stats.length ? (
              <div className="text-sm text-gray-600 dark:text-gray-400">No summary yet.</div>
            ) : (
              <div className="overflow-auto">
                <table className="w-full text-sm">
                  <thead className="text-xs text-gray-600 dark:text-gray-400">
                    <tr>
                      <th className="text-left py-2 pr-3">Metric</th>
                      <th className="text-right py-2 pr-3">Min</th>
                      <th className="text-right py-2 pr-3">Avg</th>
                      <th className="text-right py-2 pr-3">Max</th>
                      <th className="text-right py-2">Last</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.map((s) => (
                      <tr key={s.field} className="border-t border-gray-200 dark:border-gray-800">
                        <td className="py-2 pr-3">
                          <div className="font-medium text-gray-900 dark:text-gray-100">{safeFieldLabel(s.field)}</div>
                          <div className="font-mono text-xs text-gray-500">{s.field}</div>
                        </td>
                        <td className="py-2 pr-3 text-right">{Number(s.min).toFixed(3)}</td>
                        <td className="py-2 pr-3 text-right">{Number(s.avg).toFixed(3)}</td>
                        <td className="py-2 pr-3 text-right">{Number(s.max).toFixed(3)}</td>
                        <td className="py-2 text-right">{Number(s.last).toFixed(3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="xl:col-span-3 space-y-6">
        <Card className="overflow-hidden">
          <CardHeader className="flex flex-col gap-2">
            <CardTitle>AI Diagnostics</CardTitle>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Chat-style analysis · {providerStatus.provider} {providerStatus.model ? `· ${providerStatus.model}` : ''}
            </div>
          </CardHeader>
          <CardContent>
            <div
              ref={scrollRef}
              className={cn(
                'min-h-[520px] max-h-[calc(100vh-260px)] overflow-y-auto',
                'rounded-2xl border border-gray-200 dark:border-gray-800',
                'bg-gradient-to-b from-white to-gray-50 dark:from-gray-950/50 dark:to-gray-900 px-4 py-4 space-y-4'
              )}
            >
              {chat.length === 0 && (
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  Ask for an explanation (example: “Why is throughput low?”, “Any bottlenecks?”, “Explain spikes”).
                </div>
              )}

              {chat.map((m) =>
                m.role === 'user' ? (
                  <div key={m.id} className="flex justify-end">
                    <div className="max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-relaxed bg-blue-600 text-white whitespace-pre-wrap break-words">
                      {m.content}
                    </div>
                  </div>
                ) : (
                  <div key={m.id} className="flex justify-start">
                    <div className="max-w-[90%] rounded-2xl px-4 py-3 text-sm leading-relaxed bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100">
                      <MarkdownViewer value={m.content} variant="plain" />
                    </div>
                  </div>
                )
              )}

              {chatLoading && (
                <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/30 px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                  <div className="font-semibold">Thinking…</div>
                  <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                    Analyzing the selected window and metrics.
                  </div>
                </div>
              )}
            </div>

            <div className="mt-4 flex items-end gap-2">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendAi()
                  }
                }}
                rows={2}
                placeholder="Ask about this telemetry… (Enter to send, Shift+Enter for newline)"
                className="flex-1 resize-none px-4 py-2 rounded-xl border bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
              />
              <Button variant="primary" size="sm" onClick={sendAi} disabled={!chatInput.trim() || chatLoading}>
                Send
              </Button>
            </div>

            {lastSummary && (
              <details className="mt-4 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/40 px-4 py-3">
                <summary className="cursor-pointer select-none text-sm font-semibold text-gray-800 dark:text-gray-200">
                  Analysis context
                </summary>
                <div className="mt-3">
                  <JsonViewer data={lastSummary} collapsed={2} />
                </div>
              </details>
            )}

            {tid && (
              <details className="mt-4 rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/40 px-4 py-3">
                <summary className="cursor-pointer select-none text-sm font-semibold text-gray-800 dark:text-gray-200">
                  AI Console (Agents + MCP)
                </summary>
                <div className="mt-3">
                  <AiConsole scopeTopologyId={tid} />
                </div>
              </details>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
