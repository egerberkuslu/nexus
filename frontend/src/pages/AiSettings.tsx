import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { aiAPI, type AIProvider } from '@services/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'
import { Button } from '@/components/atoms/Button'
import { Input } from '@/components/atoms/Input'

const providers: AIProvider[] = ['ollama', 'openai', 'anthropic', 'gemini']

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

export default function AiSettings() {
  const queryClient = useQueryClient()

  const { data: settingsData, isLoading: settingsLoading } = useQuery({
    queryKey: ['ai-settings'],
    queryFn: async () => {
      const res = await aiAPI.settings()
      return res.data
    },
    retry: false,
  })

  const statusByProvider = useMemo(() => {
    const map = new Map<AIProvider, { configured: boolean; default_model: string | null }>()
    for (const p of providers) {
      const row = settingsData?.providers?.find((x) => x.provider === p)
      map.set(p, { configured: row?.configured ?? (p === 'ollama'), default_model: row?.default_model ?? null })
    }
    return map
  }, [settingsData])

  const [apiKeyDraft, setApiKeyDraft] = useState<Record<string, string>>({})
  const [defaultModelDraft, setDefaultModelDraft] = useState<Record<string, string>>({})

  const modelsQueries = useQueries({
    queries: providers.map((provider) => ({
      queryKey: ['ai-models', provider],
      queryFn: async () => {
        const res = await aiAPI.models(provider)
        const models = (res.data as any)?.models
        if (!Array.isArray(models)) {
          throw new Error('Invalid models response')
        }
        return models as string[]
      },
      staleTime: 0,
      refetchOnMount: 'always' as const,
      refetchOnWindowFocus: true,
      retry: false,
    })),
  })

  const modelsByProvider = useMemo(() => {
    const map = new Map<AIProvider, { models: string[]; isLoading: boolean }>()
    providers.forEach((provider, idx) => {
      map.set(provider, {
        models: (modelsQueries[idx]?.data as string[]) || [],
        isLoading: Boolean(modelsQueries[idx]?.isLoading),
      })
    })
    return map
  }, [modelsQueries])

  useEffect(() => {
    setDefaultModelDraft((prev) => {
      let changed = false
      const next = { ...prev }
      for (const p of providers) {
        const current = next[p]
        const models = modelsByProvider.get(p)?.models || []
        const saved = statusByProvider.get(p)?.default_model || ''
        const resolved = saved || (models[0] || '')
        if (!current && resolved) {
          next[p] = resolved
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [modelsByProvider, settingsData, statusByProvider])

  const setCredentialMutation = useMutation({
    mutationFn: async ({ provider, api_key }: { provider: Exclude<AIProvider, 'ollama'>; api_key: string }) => {
      await aiAPI.setCredential({ provider, api_key })
    },
    onSuccess: async () => {
      toast.success('API key saved')
      await queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to save API key')
    },
  })

  const clearCredentialMutation = useMutation({
    mutationFn: async (provider: Exclude<AIProvider, 'ollama'>) => {
      await aiAPI.clearCredential(provider)
    },
    onSuccess: async () => {
      toast.success('API key cleared')
      await queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to clear API key')
    },
  })

  const setDefaultModelMutation = useMutation({
    mutationFn: async ({ provider, default_model }: { provider: AIProvider; default_model: string }) => {
      await aiAPI.setDefaultModel({ provider, default_model })
    },
    onSuccess: async () => {
      toast.success('Default model saved')
      await queryClient.invalidateQueries({ queryKey: ['ai-settings'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to save default model')
    },
  })

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 pb-20 md:pb-8">
      <div className="container-custom py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">AI Settings</h1>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Manage provider API keys and default models (stored in PostgreSQL).
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {providers.map((provider) => {
            const status = statusByProvider.get(provider)
            const configured = status?.configured ?? (provider === 'ollama')
            const models = modelsByProvider.get(provider)?.models || []
            const modelsLoading = modelsByProvider.get(provider)?.isLoading
            const defaultModel = defaultModelDraft[provider] || ''

            return (
              <Card key={provider}>
                <CardHeader className="flex items-center justify-between">
                  <CardTitle>{providerLabel(provider)}</CardTitle>
                  <Badge variant={configured ? 'success' : 'default'} size="sm">
                    {configured ? 'Configured' : 'Not configured'}
                  </Badge>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                      Default Model
                    </label>
                    <select
                      value={defaultModel}
                      onChange={(e) => setDefaultModelDraft((prev) => ({ ...prev, [provider]: e.target.value }))}
                      disabled={modelsLoading}
                      className="w-full px-4 py-2 rounded-xl border bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 disabled:opacity-50"
                    >
                      {models.map((m) => (
                        <option key={m} value={m}>
                          {m}
                        </option>
                      ))}
                    </select>
                    <div className="flex items-center justify-end mt-2">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => setDefaultModelMutation.mutate({ provider, default_model: defaultModel })}
                        isLoading={setDefaultModelMutation.isPending}
                        disabled={!defaultModel}
                      >
                        Save Default
                      </Button>
                    </div>
                  </div>

                  {provider !== 'ollama' && (
                    <div className="space-y-2">
                      <Input
                        label="API Key"
                        type="password"
                        value={apiKeyDraft[provider] || ''}
                        onChange={(e) => setApiKeyDraft((prev) => ({ ...prev, [provider]: e.target.value }))}
                        placeholder="Paste API key (not stored in browser)"
                      />

                      <div className="flex items-center justify-end gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => clearCredentialMutation.mutate(provider as Exclude<AIProvider, 'ollama'>)}
                          isLoading={clearCredentialMutation.isPending}
                        >
                          Clear Key
                        </Button>
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() =>
                            setCredentialMutation.mutate({
                              provider: provider as Exclude<AIProvider, 'ollama'>,
                              api_key: (apiKeyDraft[provider] || '').trim(),
                            })
                          }
                          isLoading={setCredentialMutation.isPending}
                          disabled={!(apiKeyDraft[provider] || '').trim()}
                        >
                          Save Key
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )
          })}
        </div>

        {settingsLoading && (
          <div className="text-sm text-gray-500 dark:text-gray-400">Loading settings…</div>
        )}
      </div>
    </div>
  )
}
