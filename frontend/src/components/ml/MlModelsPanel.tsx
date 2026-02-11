import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { aiAPI, type MLModel } from '@services/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Badge } from '@/components/atoms/Badge'
import { Button } from '@/components/atoms/Button'
import { Input } from '@/components/atoms/Input'

function taskLabel(task: string) {
  switch (task) {
    case 'anomaly_detection':
      return 'Anomaly Detection'
    case 'attack_detection':
      return 'Attack Detection'
    case 'routing_policy':
      return 'Routing / TE Policy'
    case 'mano_policy':
      return 'MANO Policy'
    default:
      return task
  }
}

function isBuiltin(model?: MLModel | null) {
  return Boolean((model as any)?.meta?.is_builtin)
}

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.URL.revokeObjectURL(url)
}

export default function MlModelsPanel() {
  const queryClient = useQueryClient()

  const { data: modelsData, isLoading: modelsLoading } = useQuery({
    queryKey: ['ml-models'],
    queryFn: async () => {
      const res = await aiAPI.ml.listModels()
      return res.data
    },
    retry: false,
  })

  const { data: assignmentsData, isLoading: assignmentsLoading } = useQuery({
    queryKey: ['ml-assignments'],
    queryFn: async () => {
      const res = await aiAPI.ml.assignments()
      return res.data
    },
    retry: false,
  })

  const tasks = useMemo(() => {
    const apiTasks = assignmentsData?.tasks
    if (Array.isArray(apiTasks) && apiTasks.length) return apiTasks
    return ['anomaly_detection', 'attack_detection', 'routing_policy', 'mano_policy']
  }, [assignmentsData])

  const assignmentsByTask = useMemo(() => {
    const map = new Map<string, string>()
    for (const a of assignmentsData?.assignments || []) {
      if (a?.task && a?.model_id) map.set(a.task, a.model_id)
    }
    return map
  }, [assignmentsData])

  const models = useMemo(() => (modelsData?.models || []) as MLModel[], [modelsData])

  const modelsByTask = useMemo(() => {
    const map = new Map<string, MLModel[]>()
    for (const m of models) {
      const t = String(m.task || '')
      if (!t) continue
      map.set(t, [...(map.get(t) || []), m])
    }
    for (const [t, list] of map.entries()) {
      list.sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || '')))
      map.set(t, list)
    }
    return map
  }, [models])

  const setAssignmentMutation = useMutation({
    mutationFn: async (data: { task: string; model_id: string }) => {
      await aiAPI.ml.setAssignment(data)
    },
    onSuccess: async () => {
      toast.success('Active model updated')
      await queryClient.invalidateQueries({ queryKey: ['ml-assignments'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to update assignment')
    },
  })

  const deleteModelMutation = useMutation({
    mutationFn: async (modelId: string) => {
      await aiAPI.ml.deleteModel(modelId)
    },
    onSuccess: async () => {
      toast.success('Model deleted')
      await queryClient.invalidateQueries({ queryKey: ['ml-models'] })
      await queryClient.invalidateQueries({ queryKey: ['ml-assignments'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Failed to delete model')
    },
  })

  const downloadModelMutation = useMutation({
    mutationFn: async (m: MLModel) => {
      const res = await aiAPI.ml.downloadModel(m.id)
      return { blob: res.data as Blob, filename: m.artifact_filename || `model-${m.id}.bin` }
    },
    onSuccess: async ({ blob, filename }) => {
      downloadBlob(blob, filename)
      toast.success('Downloaded')
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Download failed')
    },
  })

  const [uploadTask, setUploadTask] = useState<string>('anomaly_detection')
  const [uploadName, setUploadName] = useState<string>('')
  const [uploadFramework, setUploadFramework] = useState<string>('onnx')
  const [uploadAlgorithm, setUploadAlgorithm] = useState<string>('')
  const [uploadVersion, setUploadVersion] = useState<string>('')
  const [uploadDescription, setUploadDescription] = useState<string>('')
  const [uploadFile, setUploadFile] = useState<File | null>(null)

  const uploadMutation = useMutation({
    mutationFn: async () => {
      if (!uploadFile) throw new Error('Choose a model file')
      const res = await aiAPI.ml.uploadModel(uploadFile, {
        task: uploadTask,
        name: uploadName.trim(),
        framework: uploadFramework,
        algorithm: uploadAlgorithm.trim() || undefined,
        version: uploadVersion.trim() || undefined,
        description: uploadDescription.trim() || undefined,
      })
      return res.data
    },
    onSuccess: async (model: MLModel) => {
      toast.success(`Uploaded: ${model.name}`)
      setUploadName('')
      setUploadAlgorithm('')
      setUploadVersion('')
      setUploadDescription('')
      setUploadFile(null)
      await queryClient.invalidateQueries({ queryKey: ['ml-models'] })
      await queryClient.invalidateQueries({ queryKey: ['ml-assignments'] })
    },
    onError: (err: any) => {
      toast.error(err?.response?.data?.detail || err?.message || 'Upload failed')
    },
  })

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Active Models (per task)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {tasks.map((task) => {
              const activeId = assignmentsByTask.get(task) || ''
              const candidates = modelsByTask.get(task) || []
              const activeModel =
                candidates.find((m) => m.id === activeId) || (assignmentsData?.models_by_id || {})[activeId]
              return (
                <div key={task} className="rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold text-gray-900 dark:text-white">{taskLabel(task)}</div>
                    <Badge variant={activeModel ? 'success' : 'default'} size="sm">
                      {activeModel ? (isBuiltin(activeModel) ? 'Builtin' : 'Custom') : 'Unassigned'}
                    </Badge>
                  </div>

                  <div className="text-xs text-gray-600 dark:text-gray-400">
                    Active: <span className="font-mono">{activeModel?.name || activeId || '—'}</span>
                  </div>

                  <div className="flex items-center gap-2">
                    <select
                      value={activeId}
                      onChange={(e) => setAssignmentMutation.mutate({ task, model_id: e.target.value })}
                      disabled={setAssignmentMutation.isPending || candidates.length === 0}
                      className="w-full px-4 py-2 rounded-xl border bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 disabled:opacity-50"
                    >
                      {candidates.length === 0 ? (
                        <option value="">No models registered for this task</option>
                      ) : (
                        candidates.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.name} ({m.framework}
                            {m.version ? `:${m.version}` : ''})
                          </option>
                        ))
                      )}
                    </select>
                  </div>
                </div>
              )
            })}

            {(assignmentsLoading || modelsLoading) && (
              <div className="text-sm text-gray-500 dark:text-gray-400">Loading…</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Upload Model</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Task</label>
                <select
                  value={uploadTask}
                  onChange={(e) => setUploadTask(e.target.value)}
                  className="w-full px-4 py-2 rounded-xl border bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                >
                  {tasks.map((t) => (
                    <option key={t} value={t}>
                      {taskLabel(t)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">Framework</label>
                <select
                  value={uploadFramework}
                  onChange={(e) => setUploadFramework(e.target.value)}
                  className="w-full px-4 py-2 rounded-xl border bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400"
                >
                  <option value="onnx">ONNX (.onnx)</option>
                  <option value="torchscript">TorchScript (.pt/.pth)</option>
                </select>
              </div>
            </div>

            <Input label="Name" value={uploadName} onChange={(e) => setUploadName(e.target.value)} placeholder="e.g. TranAD v1" />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Algorithm (optional)"
                value={uploadAlgorithm}
                onChange={(e) => setUploadAlgorithm(e.target.value)}
                placeholder="e.g. tranad"
              />
              <Input
                label="Version (optional)"
                value={uploadVersion}
                onChange={(e) => setUploadVersion(e.target.value)}
                placeholder="e.g. 1.0.0"
              />
            </div>
            <Input
              label="Description (optional)"
              value={uploadDescription}
              onChange={(e) => setUploadDescription(e.target.value)}
              placeholder="Short notes for operators"
            />

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">Model file</label>
              <input
                type="file"
                onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                className="block w-full text-sm text-gray-700 dark:text-gray-200 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-blue-900/20 dark:file:text-blue-300"
              />
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Allowed extensions: <span className="font-mono">.onnx</span>, <span className="font-mono">.pt</span>,{' '}
                <span className="font-mono">.pth</span>
              </div>
            </div>

            <div className="flex items-center justify-end">
              <Button
                variant="primary"
                onClick={() => uploadMutation.mutate()}
                isLoading={uploadMutation.isPending}
                disabled={!uploadName.trim() || !uploadFile}
              >
                Upload
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <CardTitle>Registered Models</CardTitle>
          <div className="text-xs text-gray-500 dark:text-gray-400">{models.length} total</div>
        </CardHeader>
        <CardContent className="space-y-3">
          {models.map((m) => {
            const builtin = isBuiltin(m)
            const canDownload = Boolean(m.artifact_filename)
            return (
              <div
                key={m.id}
                className="flex flex-col md:flex-row md:items-center justify-between gap-3 rounded-xl border border-gray-200 dark:border-gray-800 p-4"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="font-semibold text-gray-900 dark:text-white truncate">{m.name}</div>
                    <Badge variant={builtin ? 'default' : 'success'} size="sm">
                      {builtin ? 'Builtin' : 'Custom'}
                    </Badge>
                    <Badge variant="default" size="sm">
                      {String(m.task)}
                    </Badge>
                    <Badge variant="default" size="sm">
                      {String(m.framework)}
                    </Badge>
                  </div>
                  {m.description && <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">{m.description}</div>}
                  <div className="text-xs text-gray-500 dark:text-gray-400 mt-2 space-x-2">
                    <span className="font-mono">{m.id}</span>
                    {m.artifact_filename && (
                      <span>
                        • file: <span className="font-mono">{m.artifact_filename}</span>
                      </span>
                    )}
                    {m.version && <span>• v{m.version}</span>}
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => downloadModelMutation.mutate(m)}
                    isLoading={downloadModelMutation.isPending}
                    disabled={!canDownload}
                  >
                    Download
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => deleteModelMutation.mutate(m.id)}
                    isLoading={deleteModelMutation.isPending}
                    disabled={builtin}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            )
          })}

          {models.length === 0 && <div className="text-sm text-gray-500 dark:text-gray-400">No models registered yet.</div>}
        </CardContent>
      </Card>
    </div>
  )
}

