import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { Link } from 'react-router-dom'
import { aiAPI, type AIProvider } from '@services/api'
import { Button } from '@/components/atoms/Button'
import { Badge } from '@/components/atoms/Badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import MarkdownViewer from '@/components/MarkdownViewer'
import { ToolCallCard, type ToolRunStatus } from '@components/ai/ToolUi'
import JsonViewer from '@/components/JsonViewer'
import { cn } from '@/utils/cn'

type Agent = {
  id: string
  name: string
  description: string
  scope: 'global' | 'topology' | 'both'
  allowed_prefixes: string[]
  allowed_methods: string[]
}

type ThreadInfo = {
  id: string
  agent_id: string
  topology_id?: string | null
  title?: string | null
  updated_at?: string | null
  created_at?: string | null
}

type ThreadMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content_md: string
  created_at: string
  meta?: any
  tool_calls: {
    id: string
    toon: string
    status: 'success' | 'error' | 'running' | 'pending'
    duration_ms?: number | null
    result?: any
    created_at?: string
  }[]
}

function providerLabel(provider: AIProvider) {
  switch (provider) {
    case 'ollama':
      return 'Ollama'
    case 'openai':
      return 'OpenAI'
    case 'anthropic':
      return 'Anthropic'
    case 'gemini':
      return 'Gemini'
  }
}

function formatToonValue(value: any): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return String(value)
  if (typeof value === 'object') return JSON.stringify(value)
  const text = String(value)
  if (/\s/.test(text) || /[="':]/.test(text)) return JSON.stringify(text)
  return text
}

function flattenToon(value: any, prefix = '', out: string[] = []) {
  if (Array.isArray(value)) {
    out.push(`${prefix}=${JSON.stringify(value)}`)
    return out
  }
  if (value && typeof value === 'object') {
    Object.entries(value).forEach(([k, v]) => {
      const next = prefix ? `${prefix}.${k}` : k
      flattenToon(v, next, out)
    })
    return out
  }
  out.push(`${prefix}=${formatToonValue(value)}`)
  return out
}

function summarizeArrayBody(body: any[]): string {
  const items = body.filter((x) => x && typeof x === 'object')
  if (!items.length) return `items=${body.length}\nbody=${JSON.stringify(body)}`

  const lines: string[] = [`items=${body.length}`]
  for (const row of items.slice(0, 15)) {
    const name = (row as any).name ?? (row as any).id ?? 'item'
    const id = (row as any).id
    const status = (row as any).emulation_status ?? (row as any).status ?? ((row as any).is_active ? 'active' : undefined)
    const nodes = Array.isArray((row as any).nodes) ? (row as any).nodes.length : (row as any).node_count
    const links = Array.isArray((row as any).links) ? (row as any).links.length : (row as any).link_count
    const container = (row as any).container_name

    let suffix = ''
    if (id) suffix += ` (id=${id})`
    if (status) suffix += `${suffix ? ', ' : ' ('}status=${status}${suffix ? '' : ')'}`
    if (typeof nodes === 'number' && typeof links === 'number') suffix += `, nodes=${nodes}, links=${links}`
    if (container) suffix += `, container=${container}`

    lines.push(`- ${String(name)}${suffix}`)
  }
  if (items.length > 15) lines.push(`…and ${items.length - 15} more`)
  return lines.join('\n')
}

function methodBadge(method: string) {
  const m = method.toUpperCase()
  const variant =
    m === 'GET'
      ? 'info'
      : m === 'POST'
        ? 'primary'
        : m === 'DELETE'
          ? 'error'
          : m === 'PATCH' || m === 'PUT'
            ? 'warning'
            : 'default'
  return (
    <Badge variant={variant as any} size="sm" className="shrink-0">
      {m}
    </Badge>
  )
}

export default function AiConsole({ scopeTopologyId }: { scopeTopologyId?: string }) {
  const queryClient = useQueryClient()
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const [provider, setProvider] = useState<AIProvider>('ollama')
  const [model, setModel] = useState<string>('')
  const [agentId, setAgentId] = useState<string>('')
  const [threadId, setThreadId] = useState<string>('')
  const [input, setInput] = useState<string>('')
  const [mcpResultView, setMcpResultView] = useState<'toon' | 'json'>('toon')
  const [rerunResultByToolId, setRerunResultByToolId] = useState<Record<string, any | null>>({})
  const [lastTraceByThread, setLastTraceByThread] = useState<Record<string, any[]>>({})
  const [lastMemoryByThread, setLastMemoryByThread] = useState<Record<string, any[]>>({})
  const [lastRouteByThread, setLastRouteByThread] = useState<Record<string, any>>({})
  const [lastRunByThread, setLastRunByThread] = useState<Record<string, any>>({})

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
    const map = new Map<AIProvider, { configured: boolean; default_model: string | null }>()
    for (const row of list) {
      map.set(row.provider, { configured: row.configured, default_model: row.default_model })
    }
    if (!map.has('ollama')) {
      map.set('ollama', { configured: true, default_model: null })
    }
    return map
  }, [settingsData])

  const canSendProvider = useMemo(() => {
    if (provider === 'ollama') return true
    return Boolean(providerStatus.get(provider)?.configured)
  }, [provider, providerStatus])

  const {
    data: modelsData,
    isLoading: modelsLoading,
    isError: modelsError,
    error: modelsErrorObj,
    refetch: refetchModels,
  } = useQuery({
    queryKey: ['ai-models', provider],
    queryFn: async () => {
      const res = await aiAPI.models(provider)
      const models = (res.data as any)?.models
      if (!Array.isArray(models)) {
        throw new Error('Invalid models response')
      }
      return res.data
    },
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
    retry: false,
  })

  useEffect(() => {
    const models = modelsData?.models || []
    if (!models.length) return
    const defaultModel = providerStatus.get(provider)?.default_model || ''
    const next = (defaultModel && models.includes(defaultModel) ? defaultModel : models[0]) || ''
    if (!model || !models.includes(model)) setModel(next)
  }, [modelsData, model, provider, providerStatus])

  const { data: agentsData, isLoading: agentsLoading } = useQuery({
    queryKey: ['ai-agents'],
    queryFn: async () => {
      const res = await aiAPI.agents.list()
      return res.data
    },
    retry: false,
    staleTime: 30_000,
  })

  const agents = (agentsData?.agents || []) as Agent[]
  const selectedAgent = agents.find((a) => a.id === agentId) || null

  useEffect(() => {
    if (agentId) return
    if (!agents.length) return
    const preferred = 'router'
    const found = agents.find((a) => a.id === preferred) || agents[0]
    setAgentId(found.id)
  }, [agentId, agents, scopeTopologyId])

  const { data: threadsData, isLoading: threadsLoading } = useQuery({
    queryKey: ['ai-threads', agentId || 'none', scopeTopologyId || 'global'],
    queryFn: async () => {
      if (!agentId) return { threads: [] as ThreadInfo[] }
      const res = await aiAPI.agents.threads(agentId, scopeTopologyId)
      return res.data
    },
    enabled: Boolean(agentId),
    retry: false,
  })

  const threads = (threadsData?.threads || []) as ThreadInfo[]

  useEffect(() => {
    if (!agentId) return
    if (!threads.length) {
      if (threadId) setThreadId('')
      return
    }
    const exists = threadId && threads.some((t) => t.id === threadId)
    if (!exists) setThreadId(threads[0].id)
  }, [agentId, threadId, threads])

  const { data: threadData, isLoading: threadLoading } = useQuery({
    queryKey: ['ai-thread', threadId || 'none'],
    queryFn: async () => {
      if (!threadId) return null
      const res = await aiAPI.agents.thread(threadId)
      return res.data
    },
    enabled: Boolean(threadId),
    retry: false,
  })

  const threadMessages = (threadData?.messages || []) as ThreadMessage[]
  const persistedTraceSteps = useMemo(() => {
    const candidates = [...threadMessages].reverse()
    const found = candidates.find((m) => m.role === 'assistant' && Array.isArray(m?.meta?.raw_steps) && m.meta.raw_steps.length)
    return (found?.meta?.raw_steps as any[]) || []
  }, [threadMessages])
  const traceSteps = useMemo(() => {
    if (!threadId) return []
    const local = lastTraceByThread[threadId] || []
    return local.length ? local : persistedTraceSteps
  }, [lastTraceByThread, persistedTraceSteps, threadId])

  const persistedRun = useMemo(() => {
    const candidates = [...threadMessages].reverse()
    const found = candidates.find((m) => m.role === 'assistant' && m?.meta?.run && typeof m.meta.run === 'object')
    return found?.meta?.run || null
  }, [threadMessages])
  const runInfo = useMemo(() => {
    if (!threadId) return null
    return lastRunByThread[threadId] || persistedRun || null
  }, [lastRunByThread, persistedRun, threadId])

  const {
    data: mcpCaps,
    isLoading: mcpCapsLoading,
    isError: mcpCapsError,
    refetch: refetchMcpCaps,
  } = useQuery({
    queryKey: ['ai-mcp-capabilities', scopeTopologyId || 'global'],
    queryFn: async () => {
      const res = await aiAPI.mcp.capabilities(scopeTopologyId)
      return res.data
    },
    retry: false,
    staleTime: 10_000,
  })

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    el.scrollTop = el.scrollHeight
  }, [threadMessages.length, threadId, threadLoading])

  const renderToolResponseText = useMemo(() => {
    return (result: any | null) => {
      if (!result) return '—'
      const body = result.body
      if (Array.isArray(body)) {
        return [`status_code=${result.status_code}`, summarizeArrayBody(body)].join('\n')
      }
      if (body && typeof body === 'object') {
        const flat = flattenToon(body)
        return [`status_code=${result.status_code}`, ...flat].join('\n')
      }
      return `status_code=${result.status_code}\nbody=${formatToonValue(body)}`
    }
  }, [mcpResultView])

  const executeToolCall = async (toolId: string, toon: string, mode: 'execute' | 'rerun') => {
    setRerunResultByToolId((prev) => ({ ...prev, [toolId]: null }))
    try {
      if (mode === 'execute') {
        const res = await aiAPI.agents.executeToolCall(toolId)
        const data = res.data
        const ok = data?.status_code >= 200 && data?.status_code < 300
        setRerunResultByToolId((prev) => ({ ...prev, [toolId]: data }))
        await queryClient.invalidateQueries({ queryKey: ['ai-thread', threadId || 'none'] })
        if (ok) toast.success('Executed')
        else toast.error(`Failed (${data?.status_code ?? 'unknown'})`)
        return
      }

      const res = await aiAPI.mcp.executeToon(toon, scopeTopologyId)
      const data = res.data
      const ok = data?.status_code >= 200 && data?.status_code < 300
      setRerunResultByToolId((prev) => ({ ...prev, [toolId]: data }))
      if (ok) toast.success('Reran')
      else toast.error(`Failed (${data?.status_code ?? 'unknown'})`)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to execute MCP request')
    }
  }

  const deleteCurrentThread = async () => {
    if (!threadId) return
    const ok = window.confirm('Delete this thread? This cannot be undone.')
    if (!ok) return
    try {
      await aiAPI.agents.deleteThread(threadId)
      toast.success('Thread deleted')
      setThreadId('')
      await queryClient.invalidateQueries({ queryKey: ['ai-threads', agentId || 'none', scopeTopologyId || 'global'] })
      await queryClient.invalidateQueries({ queryKey: ['ai-thread', threadId || 'none'] })
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to delete thread')
    }
  }

  const deleteAllThreads = async () => {
    if (!agentId) return
    const ok = window.confirm('Delete ALL threads for this agent/scope? This cannot be undone.')
    if (!ok) return
    try {
      await aiAPI.agents.deleteThreads(agentId, scopeTopologyId)
      toast.success('Threads deleted')
      setThreadId('')
      await queryClient.invalidateQueries({ queryKey: ['ai-threads', agentId || 'none', scopeTopologyId || 'global'] })
      await queryClient.invalidateQueries({ queryKey: ['ai-thread', threadId || 'none'] })
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to delete threads')
    }
  }

  const sendMessageMutation = useMutation({
    mutationFn: async (payload: { message: string }) => {
      return aiAPI.agents.chat({
        message: payload.message,
        topology_id: scopeTopologyId,
        agent_id: agentId || undefined,
        thread_id: threadId || undefined,
        provider,
        model,
        max_steps: 6,
      })
    },
    onSuccess: async (res) => {
      const data = res.data as any
      const nextThreadId = String(data?.thread_id || '').trim()
      if (nextThreadId) setThreadId(nextThreadId)
      setLastTraceByThread((prev) => ({ ...prev, [nextThreadId || threadId || '']: data?.raw_steps || [] }))
      setLastMemoryByThread((prev) => ({ ...prev, [nextThreadId || threadId || '']: data?.memory_hits || [] }))
      setLastRouteByThread((prev) => ({ ...prev, [nextThreadId || threadId || '']: data?.route || null }))
      setLastRunByThread((prev) => ({ ...prev, [nextThreadId || threadId || '']: data?.run || null }))

      const toolCalls = Array.isArray(data?.tool_calls) ? data.tool_calls : []
      const anyError = toolCalls.some((t: any) => (t?.result?.status_code ?? 0) >= 400)
      if (anyError) toast.error('Some tool calls failed')
      else toast.success('Done')

      await queryClient.invalidateQueries({ queryKey: ['ai-threads'] })
      if (nextThreadId) await queryClient.invalidateQueries({ queryKey: ['ai-thread', nextThreadId] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to send message')
    },
  })

  const sendChat = async () => {
    const trimmed = input.trim()
    if (!trimmed) return
    if (!model) return toast.error('Select a model first')
    if (!canSendProvider) return toast.error('Provider is not configured. Set API key in AI Settings.')
    setInput('')
    await sendMessageMutation.mutateAsync({ message: trimmed })
  }

  const newThread = async () => {
    if (!agentId) return toast.error('Select an agent first')
    try {
      const res = await aiAPI.agents.createThread({ agent_id: agentId, topology_id: scopeTopologyId })
      setThreadId(res.data.id)
      await queryClient.invalidateQueries({ queryKey: ['ai-threads'] })
      toast.success('New chat created')
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to create thread')
    }
  }

  const downloadReport = async (format: 'md' | 'pdf') => {
    if (!threadId) return toast.error('Select a thread first')
    try {
      const res = await aiAPI.agents.exportThreadReport(threadId, { format, provider, model })
      const blob = res.data as Blob
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `report-${threadId}.${format}`
      document.body.appendChild(a)
      a.click()
      a.remove()
      window.URL.revokeObjectURL(url)
      toast.success(`Exported ${format.toUpperCase()}`)
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to export report')
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Model & Agent</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-2">
              {(['ollama', 'openai', 'anthropic', 'gemini'] as AIProvider[]).map((p) => (
                <button
                  key={p}
                  onClick={() => setProvider(p)}
                  className={cn(
                    'rounded-xl border px-3 py-2 text-sm font-medium transition-colors',
                    provider === p
                      ? 'border-blue-500 bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-200 dark:border-blue-500'
                      : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800'
                  )}
                >
                  {providerLabel(p)}
                </button>
              ))}
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Model</label>
                <select
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  disabled={modelsLoading}
                  className="w-full px-4 py-2 rounded-xl border bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 disabled:opacity-50"
                >
                  {(modelsData?.models || []).map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                {modelsError && (
                  <div className="mt-2 flex items-center justify-between gap-2">
                    <p className="text-xs text-red-600 dark:text-red-400">
                      Failed to load models. {(modelsErrorObj as any)?.message || ''}
                    </p>
                    <Button variant="secondary" size="sm" onClick={() => refetchModels()}>
                      Retry
                    </Button>
                  </div>
                )}
                {!modelsLoading && !modelsError && !(modelsData?.models || []).length && (
                  <p className="mt-1 text-xs text-red-600 dark:text-red-400">
                    Models list is empty. Check `/api/ai/models` routing.
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Agent</label>
                <select
                  value={agentId}
                  onChange={(e) => {
                    setAgentId(e.target.value)
                    setThreadId('')
                  }}
                  disabled={agentsLoading || !agents.length}
                  className="w-full px-4 py-2 rounded-xl border bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 disabled:opacity-50"
                >
                  {agents.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
                {selectedAgent?.description && (
                  <p className="mt-1 text-xs text-gray-600 dark:text-gray-400">{selectedAgent.description}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Thread</label>
                <div className="flex gap-2">
                  <select
                    value={threadId}
                    onChange={(e) => setThreadId(e.target.value)}
                    disabled={threadsLoading}
                    className="flex-1 px-4 py-2 rounded-xl border bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 disabled:opacity-50"
                  >
                    {!threads.length && <option value="">No threads yet</option>}
                    {threads.map((t) => (
                      <option key={t.id} value={t.id}>
                        {(t.title && t.title.slice(0, 40)) || t.id.slice(0, 8)}
                      </option>
                    ))}
                  </select>
                  <Button variant="secondary" onClick={newThread} size="sm" disabled={!agentId}>
                    New
                  </Button>
                  {(agentId === 'admin' || agentId === 'router') && (
                    <Button variant="danger" onClick={deleteCurrentThread} size="sm" disabled={!threadId}>
                      Delete
                    </Button>
                  )}
                  {(agentId === 'admin' || agentId === 'router') && (
                    <Button variant="danger" onClick={deleteAllThreads} size="sm" disabled={!threads.length}>
                      Delete all
                    </Button>
                  )}
                </div>
              </div>
            </div>

            {provider !== 'ollama' && !canSendProvider && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Provider not configured.{' '}
                <Link to="/ai-settings" className="text-blue-600 dark:text-blue-400 font-semibold hover:underline">
                  Set API key in AI Settings
                </Link>
                .
              </div>
            )}

            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-600 dark:text-gray-400">
                MCP capabilities: {mcpCapsLoading ? 'loading…' : mcpCapsError ? 'error' : mcpCaps?.items?.length || 0}
              </div>
              <Button variant="secondary" size="sm" onClick={() => refetchMcpCaps()} disabled={mcpCapsLoading}>
                Refresh
              </Button>
            </div>

            {selectedAgent && selectedAgent.id !== 'router' && (
              <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/30 px-4 py-3 text-xs text-gray-700 dark:text-gray-300">
                <div className="font-semibold text-sm text-gray-900 dark:text-gray-100">Allowed tools</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {selectedAgent.allowed_methods.map((m) => (
                    <Badge key={m} variant="info" size="sm">
                      {m}
                    </Badge>
                  ))}
                </div>
                <div className="mt-2 space-y-1">
                  {(selectedAgent.allowed_prefixes || []).slice(0, 10).map((p) => (
                    <div key={p} className="font-mono text-[11px]">
                      {p}*
                    </div>
                  ))}
                  {(selectedAgent.allowed_prefixes || []).length > 10 && (
                    <div className="text-[11px] text-gray-600 dark:text-gray-400">
                      …and {selectedAgent.allowed_prefixes.length - 10} more
                    </div>
                  )}
                </div>
              </div>
            )}

            {selectedAgent?.id === 'router' && (
              <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/30 px-4 py-3 text-xs text-gray-700 dark:text-gray-300">
                <div className="font-semibold text-sm text-gray-900 dark:text-gray-100">Auto routing</div>
                <div className="mt-1 text-[11px] text-gray-600 dark:text-gray-400">
                  Each message is routed to the best specialized agent; tool access is enforced per agent.
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {agents
                    .filter((a) => a.id !== 'router')
                    .map((a) => (
                      <Badge key={a.id} variant="default" size="sm">
                        {a.id}
                      </Badge>
                    ))}
                </div>
              </div>
            )}

            <details className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/40 px-4 py-3">
              <summary className="cursor-pointer select-none text-sm font-semibold text-gray-800 dark:text-gray-200">
                MCP capability list
              </summary>
              <div className="mt-3 space-y-3">
                {mcpCapsError && (
                  <div className="text-sm text-red-600 dark:text-red-400">
                    Failed to load capabilities. Ensure `/api/ai/mcp/capabilities` is routed.
                  </div>
                )}

                {mcpCaps && (
                  <div className="space-y-3">
                    <div className="text-xs text-gray-600 dark:text-gray-400">
                      {scopeTopologyId ? (
                        <span>
                          Scoped to <span className="font-mono">{scopeTopologyId}</span>
                        </span>
                      ) : (
                        <span>Global scope</span>
                      )}
                    </div>

                    <details className="text-sm">
                      <summary className="cursor-pointer select-none text-gray-700 dark:text-gray-300">Notes</summary>
                      <ul className="mt-2 space-y-1 text-xs text-gray-600 dark:text-gray-400">
                        {(mcpCaps.notes || []).map((n: string, idx: number) => (
                          <li key={idx}>• {n}</li>
                        ))}
                      </ul>
                    </details>

                    <div className="max-h-[260px] overflow-y-auto pr-1 space-y-2">
                      {(mcpCaps.items || []).map((it: any, idx: number) => (
                        <div
                          key={`${it.method}-${it.path}-${idx}`}
                          className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 px-3 py-2"
                        >
                          <div className="flex items-start gap-2">
                            {methodBadge(it.method)}
                            <div className="min-w-0">
                              <div className="font-mono text-xs text-gray-900 dark:text-gray-100 break-words">{it.path}</div>
                              <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">{it.description}</div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </details>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <CardTitle>MCP Agent Console</CardTitle>
              <div className="text-sm text-gray-600 dark:text-gray-400">
                {selectedAgent ? selectedAgent.name : '—'} · {providerLabel(provider)} · {model || '—'}
                {scopeTopologyId ? ` · topology_id=${scopeTopologyId}` : ' · global'}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button variant="secondary" size="sm" onClick={() => downloadReport('md')} disabled={!threadId}>
                Export MD
              </Button>
              <Button variant="secondary" size="sm" onClick={() => downloadReport('pdf')} disabled={!threadId}>
                Export PDF
              </Button>
              <Link to="/ai-settings" className="text-sm font-semibold text-blue-600 dark:text-blue-400 hover:underline">
                AI Settings
              </Link>
            </div>
          </CardHeader>

          <CardContent>
            <div className="flex items-center justify-end gap-2 mb-3">
              <Button
                variant={mcpResultView === 'toon' ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => setMcpResultView('toon')}
              >
                TOON
              </Button>
              <Button
                variant={mcpResultView === 'json' ? 'primary' : 'secondary'}
                size="sm"
                onClick={() => setMcpResultView('json')}
              >
                JSON
              </Button>
            </div>

            <div
              ref={scrollRef}
              className={cn(
                'min-h-[640px] max-h-[calc(100vh-220px)] overflow-y-auto',
                'rounded-2xl border border-gray-200 dark:border-gray-800',
                'bg-gradient-to-b from-white to-gray-50 dark:from-gray-950/50 dark:to-gray-900 px-4 py-4 space-y-4'
              )}
            >
              {!threadId && (
                <div className="text-sm text-gray-500 dark:text-gray-400">
                  Pick an agent (or Router) and create a thread, then start chatting.
                </div>
              )}

              {threadLoading && threadId && <div className="text-sm text-gray-500 dark:text-gray-400">Loading…</div>}

              {threadMessages
                .filter((m) => m.role !== 'system')
                .map((m) => {
                  const isUser = m.role === 'user'
                  const bubbleClass = isUser
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-900 dark:bg-gray-800 dark:text-gray-100'
                  const toolCalls = m.tool_calls || []
                  const route = !isUser ? m?.meta?.route : null
                  return (
                    <div key={m.id} className="space-y-3">
                      <div className={cn('flex', isUser ? 'justify-end' : 'justify-start')}>
                        <div className={cn('max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed', bubbleClass)}>
                          {!isUser && route?.selected_agent_name && (
                            <div className="mb-2 flex flex-wrap items-center gap-2">
                              <Badge variant="info" size="sm">
                                {String(route.selected_agent_name)}
                              </Badge>
                              {route?.mode && (
                                <Badge variant="default" size="sm">
                                  {String(route.mode)}
                                </Badge>
                              )}
                              {route?.confidence !== undefined && route?.confidence !== null && (
                                <Badge variant="default" size="sm">
                                  conf={Number(route.confidence).toFixed(2)}
                                </Badge>
                              )}
                              {route?.reason && (
                                <span className="text-xs text-gray-600 dark:text-gray-400">{String(route.reason)}</span>
                              )}
                            </div>
                          )}
                          {isUser ? (
                            <div className="whitespace-pre-wrap break-words">{m.content_md}</div>
                          ) : (
                            <MarkdownViewer value={m.content_md} variant="plain" className="max-w-none" />
                          )}
                        </div>
                      </div>

                      {!isUser &&
                        toolCalls.map((tc) => {
                          const rerun = Object.prototype.hasOwnProperty.call(rerunResultByToolId, tc.id)
                            ? rerunResultByToolId[tc.id]
                            : undefined
                          const result = rerun === undefined ? tc.result ?? null : rerun
                          const statusCode = result?.status_code
                          const isPending = tc.status === 'pending' || (result?.meta?.requires_confirmation && (statusCode === 0 || statusCode === null))
                          const ok = typeof statusCode === 'number' ? statusCode >= 200 && statusCode < 300 : tc.status === 'success'
                          const status: ToolRunStatus = isPending ? 'generated' : ok ? 'success' : 'error'
                          const runLabel = isPending ? 'Execute' : 'Rerun'
                          return (
                            <ToolCallCard
                              key={tc.id}
                              title="MCP Tool Call"
                              subtitle={scopeTopologyId ? `Scoped to topology_id=${scopeTopologyId}` : 'Global scope'}
                              status={status}
                              requestText={tc.toon}
                              responseText={
                                isPending
                                  ? 'Awaiting confirmation (click Execute)'
                                  : mcpResultView === 'json'
                                    ? JSON.stringify(result ?? null, null, 2)
                                    : renderToolResponseText(result ?? null)
                              }
                              responseJson={mcpResultView === 'json' ? result : undefined}
                              errorText={!isPending && !ok ? `HTTP ${statusCode ?? '—'}` : undefined}
                              meta={{
                                statusCode: isPending ? undefined : statusCode,
                                durationMs: result?.meta?.duration_ms ?? tc.duration_ms,
                              }}
                              onRun={() => executeToolCall(tc.id, tc.toon, isPending ? 'execute' : 'rerun')}
                              isRunning={false}
                              runDisabled={!tc.toon.trim()}
                              runLabel={runLabel}
                              extraHeaderRight={
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  onClick={() => navigator.clipboard.writeText(tc.toon || '')}
                                  disabled={!tc.toon}
                                >
                                  Copy TOON
                                </Button>
                              }
                            />
                          )
                        })}
                    </div>
                  )
                })}

              {sendMessageMutation.isPending && (
                <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/30 px-4 py-3 text-sm text-gray-700 dark:text-gray-300">
                  <div className="font-semibold">Thinking…</div>
                  <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">
                    The agent is deciding which MCP tools to call.
                  </div>
                </div>
              )}

              {threadId && (lastMemoryByThread[threadId]?.length || 0) > 0 && (
                <details className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/40 px-4 py-3">
                  <summary className="cursor-pointer select-none text-sm font-semibold text-gray-800 dark:text-gray-200">
                    Memory hits ({lastMemoryByThread[threadId]?.length || 0})
                  </summary>
                  <div className="mt-3 space-y-2">
                    {(lastMemoryByThread[threadId] || []).map((h: any, idx: number) => (
                      <div
                        key={idx}
                        className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/30 px-3 py-2 text-xs text-gray-700 dark:text-gray-300"
                      >
                        <div className="font-semibold">
                          {String(h?.type || 'memory')} score={String(h?.score ?? '—')}
                        </div>
                        <div className="mt-1">{String(h?.excerpt || '')}</div>
                      </div>
                    ))}
                  </div>
                </details>
              )}

              {threadId && (traceSteps.length || 0) > 0 && (
                <details className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/40 px-4 py-3">
                  <summary className="cursor-pointer select-none text-sm font-semibold text-gray-800 dark:text-gray-200">
                    Model trace ({traceSteps.length || 0})
                  </summary>
                  <div className="mt-3 space-y-2">
                    {traceSteps.map((s: any, idx: number) => {
                      const totalMs = typeof s?.total_duration === 'number' ? Math.round(s.total_duration / 1_000_000) : null
                      const promptTokens = s?.prompt_eval_count
                      const evalTokens = s?.eval_count
                      const doneReason = s?.done_reason
                      return (
                        <details
                          key={idx}
                          className="rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-950/30 px-3 py-2 text-xs text-gray-700 dark:text-gray-300"
                        >
                          <summary className="cursor-pointer select-none">
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                            <span className="font-semibold">Step {idx + 1}</span>
                            {typeof totalMs === 'number' && <span>{totalMs}ms</span>}
                            {typeof promptTokens === 'number' && <span>prompt={promptTokens}</span>}
                            {typeof evalTokens === 'number' && <span>gen={evalTokens}</span>}
                            {doneReason && <span>done={String(doneReason)}</span>}
                            </div>
                          </summary>
                          <div className="mt-2">
                            <JsonViewer data={s || {}} collapsed={2} />
                          </div>
                        </details>
                      )
                    })}
                  </div>
                </details>
              )}

              {threadId && runInfo && (
                <details className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/40 px-4 py-3">
                  <summary className="cursor-pointer select-none text-sm font-semibold text-gray-800 dark:text-gray-200">
                    Run details
                  </summary>
                  <div className="mt-3">
                    <JsonViewer data={runInfo} collapsed={2} />
                  </div>
                </details>
              )}
            </div>

            <div className="mt-4 flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    sendChat()
                  }
                }}
                rows={2}
                placeholder="Message… (Enter to send, Shift+Enter for newline)"
                className="flex-1 resize-none px-4 py-2 rounded-xl border bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
              />
              <Button
                variant="primary"
                size="sm"
                onClick={sendChat}
                disabled={!input.trim() || !model || !canSendProvider || sendMessageMutation.isPending}
                isLoading={sendMessageMutation.isPending}
              >
                Send
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
