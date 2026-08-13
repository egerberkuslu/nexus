import { useEffect, useState } from 'react'

// SwarmInfer unified view: the cyber-physical inference loop that ties the thesis
// strategic tier (CHA-S forecast + ProAct scale + FD-DSP route) to the AeroWeave
// physics plane and the Nexus mn-wifi/wmediumd operational plane. The active
// strategic policies are read LIVE from the AI-Gateway; the loop + verified
// results summarise what runs on the real testbed.

type Assignment = { task: string; model_id: string }
type ModelInfo = { task: string; algorithm?: string; name?: string; framework?: string }

const TASK_LABEL: Record<string, string> = {
  mano_policy: 'Scale (MANO)',
  routing_policy: 'Route (FD-DSP)',
  anomaly_detection: 'Anomaly',
  attack_detection: 'Attack',
}

const LOOP = [
  { k: 'Physics', d: 'AeroWeave drone poses → SetPosition', c: 'from-sky-500 to-blue-600' },
  { k: 'Network', d: 'mn-wifi + wmediumd → real RSSI', c: 'from-emerald-500 to-teal-600' },
  { k: 'Metrics', d: 'RSSI + demand → metrics.processed', c: 'from-violet-500 to-purple-600' },
  { k: 'Decide', d: 'CHA-S forecast · ProAct scale · FD-DSP route', c: 'from-amber-500 to-orange-600' },
  { k: 'Actuate', d: 'VNFM warm-pool · reposition · re-route', c: 'from-rose-500 to-pink-600' },
]

const VERIFIED = [
  { mb: 'MB-1', t: 'Forecast → scale → serve', r: 'per-worker load 2.6× lower (12 vs 31 req/min); 8/8 pool associated' },
  { mb: 'MB-2', t: 'Real DistilBERT over Wi-Fi', r: 'loadgen → worker /infer ~42 ms; transport tracks distance/RSSI' },
  { mb: 'MB-3', t: 'FD-DSP link-aware routing', r: 'routes to best-link worker; ranked candidates, 0 errors' },
  { mb: 'MB-4', t: 'Physics-coupled autonomy', r: 'drone → RSSI −60→−87 → autonomous re-route worker-01 → worker-02' },
]

export default function SwarmInfer() {
  const [models, setModels] = useState<Record<string, ModelInfo>>({})
  const [assignments, setAssignments] = useState<Assignment[]>([])
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    const load = () =>
      fetch('/api/ai/ml/assignments')
        .then((r) => r.json())
        .then((d) => {
          if (!alive) return
          setModels(d.models_by_id || {})
          setAssignments(d.assignments || [])
          setErr(null)
        })
        .catch((e) => alive && setErr(String(e)))
    load()
    const id = setInterval(load, 5000)
    return () => {
      alive = false
      clearInterval(id)
    }
  }, [])

  const active = (task: string) => {
    const a = assignments.find((x) => x.task === task)
    const m = a ? models[a.model_id] : undefined
    return m?.algorithm || 'noop'
  }

  const strategic = [
    { task: 'mano_policy', want: 'proact', desc: 'CHA-S forecast + ProAct predictive autoscaler' },
    { task: 'routing_policy', want: 'fd_dsp', desc: 'Forecast-driven, link-quality-aware placement' },
  ]

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">SwarmInfer</h1>
        <p className="text-gray-500 dark:text-gray-400 mt-1">
          Cyber-physical distributed inference loop — CHA-S · ProAct · FD-DSP over real Wi-Fi
        </p>
      </div>

      {/* live strategic policies */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
          Strategic policies <span className="text-xs text-gray-400">(live)</span>
        </h2>
        {err && <div className="text-sm text-rose-500 mb-2">gateway: {err}</div>}
        <div className="grid gap-4 sm:grid-cols-2">
          {strategic.map((s) => {
            const cur = active(s.task)
            const on = cur === s.want
            return (
              <div key={s.task} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-gray-900 dark:text-white">{TASK_LABEL[s.task] || s.task}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${on ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'}`}>
                    {on ? '● ' + cur : cur}
                  </span>
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">{s.desc}</p>
              </div>
            )
          })}
        </div>
      </section>

      {/* the loop */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">The loop</h2>
        <div className="flex flex-wrap items-stretch gap-2">
          {LOOP.map((s, i) => (
            <div key={s.k} className="flex items-center gap-2">
              <div className={`rounded-lg px-3 py-2 text-white bg-gradient-to-br ${s.c} min-w-[9rem]`}>
                <div className="font-semibold text-sm">{s.k}</div>
                <div className="text-[11px] opacity-90 leading-tight">{s.d}</div>
              </div>
              {i < LOOP.length - 1 && <span className="text-gray-400">→</span>}
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-2">Closed loop: Actuate feeds back into Physics/Network.</p>
      </section>

      {/* verified on the real testbed */}
      <section>
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">Verified on the real wmediumd testbed</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {VERIFIED.map((v) => (
            <div key={v.mb} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300">{v.mb}</span>
                <span className="font-medium text-gray-900 dark:text-white">{v.t}</span>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">{v.r}</p>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
