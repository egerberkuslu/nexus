import { useEffect, useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { emulationAPI, topologiesAPI } from '@/services/api'
import { Button } from '@/components/atoms/Button'
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Input } from '@/components/atoms/Input'
import { Play, Upload, X } from 'lucide-react'

export type ImportTopologyProject = { id: string; name: string }
type ImportTopologyTarget = { id: string; name: string }

export interface ImportTopologyModalProps {
  isOpen: boolean
  onClose: () => void
  projects: ImportTopologyProject[]
  onImported?: (topologyId: string) => void
}

const PLACEHOLDER_TOKEN = 'REPLACE_ME_SHARED_P2P_TOKEN'

const readFileAsText = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('Failed to read file'))
    reader.readAsText(file)
  })

const replaceDeep = (value: any, match: string, replacement: string): any => {
  if (typeof value === 'string') return value === match ? replacement : value
  if (Array.isArray(value)) return value.map((v) => replaceDeep(v, match, replacement))
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, v]) => [key, replaceDeep(v, match, replacement)])
    )
  }
  return value
}

export const ImportTopologyModal: React.FC<ImportTopologyModalProps> = ({
  isOpen,
  onClose,
  projects,
  onImported,
}) => {
  const { t } = useTranslation()
  const [projectId, setProjectId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [startAfterImport, setStartAfterImport] = useState(false)
  const [overwriteEnabled, setOverwriteEnabled] = useState(false)
  const [overwriteTopologyId, setOverwriteTopologyId] = useState<string>('')
  const [availableTopologies, setAvailableTopologies] = useState<ImportTopologyTarget[]>([])
  const [loadingTopologies, setLoadingTopologies] = useState(false)
  const [tokenOverride, setTokenOverride] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const projectOptions = useMemo(() => projects || [], [projects])

  useEffect(() => {
    if (!isOpen) return
    if (!projectId && projectOptions.length > 0) {
      setProjectId(projectOptions[0].id)
    }
  }, [isOpen, projectId, projectOptions])

  useEffect(() => {
    if (!isOpen || !projectId) return
    let cancelled = false
    setLoadingTopologies(true)
    topologiesAPI
      .list(projectId)
      .then((res) => {
        if (cancelled) return
        const tops = (res.data || []).map((t: any) => ({ id: t.id, name: t.name }))
        setAvailableTopologies(tops)
        // If the project has exactly one topology, default to overwrite to avoid
        // accidentally creating a "new ID" topology that users can't easily find later.
        if (tops.length === 1) {
          setOverwriteEnabled(true)
          setOverwriteTopologyId(tops[0].id)
          return
        }
        if (!overwriteTopologyId && tops.length > 0) setOverwriteTopologyId(tops[0].id)
      })
      .catch(() => {
        if (cancelled) return
        setAvailableTopologies([])
      })
      .finally(() => {
        if (cancelled) return
        setLoadingTopologies(false)
      })
    return () => {
      cancelled = true
    }
  }, [isOpen, projectId, overwriteTopologyId])

  const closeAndReset = () => {
    onClose()
    setErrorMessage(null)
    setFile(null)
    setStartAfterImport(false)
    setOverwriteEnabled(false)
    setOverwriteTopologyId('')
    setTokenOverride('')
  }

  const importMutation = useMutation({
    mutationFn: async () => {
      setErrorMessage(null)

      if (!projectId) throw new Error('Select a project')
      if (!file) throw new Error('Select a topology JSON file')

      const text = await readFileAsText(file)

      let parsed: any
      try {
        parsed = JSON.parse(text)
      } catch {
        throw new Error('Invalid JSON file')
      }

      const token = tokenOverride.trim()
      if (token) {
        parsed = replaceDeep(parsed, PLACEHOLDER_TOKEN, token)
      }

      const optionsFromFile =
        parsed && typeof parsed === 'object' && parsed.options && typeof parsed.options === 'object'
          ? parsed.options
          : {}

      if (overwriteEnabled && overwriteTopologyId) {
        const res = await topologiesAPI.importDefinition(projectId, parsed, overwriteTopologyId)
        if (startAfterImport) {
          await emulationAPI.start(overwriteTopologyId, optionsFromFile)
        }
        return res.data
      }

      if (startAfterImport) {
        const res = await topologiesAPI.importAndStart({
          project_id: projectId,
          topology: parsed,
          options: optionsFromFile,
        })
        return res.data?.topology ?? res.data
      }

      const res = await topologiesAPI.importDefinition(projectId, parsed)
      return res.data
    },
    onSuccess: (topology: any) => {
      const topologyId = topology?.id
      closeAndReset()
      if (topologyId && onImported) onImported(topologyId)
    },
    onError: (err: any) => {
      setErrorMessage(err?.response?.data?.detail || err?.message || 'Failed to import topology')
    },
  })

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 dark:bg-black/80 backdrop-blur-sm">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Import Topology</CardTitle>
            <button
              onClick={closeAndReset}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            >
              <X size={20} />
            </button>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {errorMessage && (
            <div className="rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/20 px-4 py-3 text-sm text-red-700 dark:text-red-300">
              {errorMessage}
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              Project
            </label>
            <select
              className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent"
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              disabled={projectOptions.length === 0}
            >
              {projectOptions.length === 0 ? (
                <option value="">No projects</option>
              ) : (
                projectOptions.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))
              )}
            </select>
          </div>

          <label className="flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={overwriteEnabled}
              onChange={(e) => setOverwriteEnabled(e.target.checked)}
              className="h-4 w-4"
              disabled={loadingTopologies}
            />
            Overwrite an existing topology (keep the same topology ID)
          </label>

          {overwriteEnabled && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                Target topology
              </label>
              <select
                className="w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 focus:border-transparent"
                value={overwriteTopologyId}
                onChange={(e) => setOverwriteTopologyId(e.target.value)}
                disabled={loadingTopologies || availableTopologies.length === 0}
              >
                {availableTopologies.length === 0 ? (
                  <option value="">No topologies in this project</option>
                ) : (
                  availableTopologies.map((top) => (
                    <option key={top.id} value={top.id}>
                      {top.name} ({top.id})
                    </option>
                  ))
                )}
              </select>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
              Topology JSON
            </label>
            <input
              type="file"
              accept="application/json,.json"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="block w-full text-sm text-gray-700 dark:text-gray-300 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:bg-gray-200 file:text-gray-900 hover:file:bg-gray-300 dark:file:bg-gray-700 dark:file:text-gray-100 dark:hover:file:bg-gray-600"
            />
            {file && (
              <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                Selected: {file.name}
              </div>
            )}
          </div>

          <Input
            label="Replace LocalAI token placeholder (optional)"
            value={tokenOverride}
            onChange={(e) => setTokenOverride(e.target.value)}
            placeholder={`Paste token to replace ${PLACEHOLDER_TOKEN}`}
          />

          <label className="flex items-center gap-3 text-sm text-gray-700 dark:text-gray-300">
            <input
              type="checkbox"
              checked={startAfterImport}
              onChange={(e) => setStartAfterImport(e.target.checked)}
              className="h-4 w-4"
            />
            Start emulation after import
          </label>
        </CardContent>

        <CardFooter>
          <Button type="button" variant="secondary" onClick={closeAndReset}>
            {t('common.cancel')}
          </Button>
          <Button
            type="button"
            variant="primary"
            isLoading={importMutation.isPending}
            disabled={
              !projectId ||
              !file ||
              projectOptions.length === 0 ||
              (overwriteEnabled && !overwriteTopologyId)
            }
            leftIcon={startAfterImport ? <Play size={18} /> : <Upload size={18} />}
            onClick={() => importMutation.mutate()}
          >
            {startAfterImport ? 'Import & Start' : 'Import'}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
