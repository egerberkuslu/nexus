import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { aiAPI, metricsCollectorAPI, testsAPI } from '@services/api'
import { Button } from '@/components/atoms/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Input } from '@/components/atoms/Input'
import JsonViewer from '@/components/JsonViewer'
import MarkdownViewer from '@/components/MarkdownViewer'
import AiConsole from '@/components/ai/AiConsole'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

type Props = {
  topologyId: string
  devices: any[]
  isRunning: boolean
}

type MetricsCollectorHealth = {
  collection_active?: boolean
  active_streams?: number
  buffer_size?: number
}

type TestResults = {
  run_id: string
  topology_id: string
  window_minutes: number
  metrics: {
    series_by_device: Record<string, { t: number | null; cpu_percent: number; memory_percent: number; reason: string }[]>
    summary_by_device: Record<string, { cpu_max: number; cpu_avg: number; mem_max: number; mem_avg: number }>
  }
  ping: { t: number | null; src: string; dst: string; success: number; loss_pct: number; rtt_avg_ms: number; exit_code: number }[]
  iperf: {
    t: number | null
    src: string
    dst: string
    proto: string
    throughput_mbps: number
    seconds?: number | null
    parallel?: number | null
    bandwidth_mbps?: number | null
    packet_size?: number | null
    jitter_ms?: number | null
    loss_pct?: number | null
    lost?: number | null
    total?: number | null
  }[]
  counters: {
    t: number | null
    device: string
    reason: string
    bytes_sent_delta: number
    bytes_received_delta: number
    packets_sent_delta: number
    packets_received_delta: number
    errors_in_delta: number
    errors_out_delta: number
    drops_in_delta: number
    drops_out_delta: number
  }[]
}

const getDeviceType = (device: any) => String(device?.device_type || device?.type || '').toLowerCase()
const getRuntimeName = (device: any) => String(device?.runtime_name || device?.name || '')
const extractIpv4 = (value: string) => (value || '').trim().split('/', 1)[0]

const getDeviceIpv4 = (device: any): string => {
  const fromDevice = extractIpv4(String(device?.ip || ''))
  const interfaces = Array.isArray(device?.interfaces) ? device.interfaces : []
  for (const iface of interfaces) {
    const name = String(iface?.name || '')
    const ip = extractIpv4(String(iface?.ip || ''))
    if (!ip) continue
    if (name === 'lo' || ip.startsWith('127.')) continue
    return ip
  }
  return fromDevice
}

const clampInt = (raw: string, min: number, max: number, fallback: number) => {
  const val = Number.parseInt(raw || '', 10)
  if (Number.isFinite(val)) return Math.max(min, Math.min(max, val))
  return fallback
}

const clampFloat = (raw: string, min: number, max: number, fallback: number) => {
  const val = Number.parseFloat(raw || '')
  if (Number.isFinite(val)) return Math.max(min, Math.min(max, val))
  return fallback
}

export default function TopologyTests({ topologyId, devices, isRunning }: Props) {
  const eligibleDevices = useMemo(() => (devices || []).filter((d) => getRuntimeName(d)), [devices])
  const hostLikeDevices = useMemo(
    () => eligibleDevices.filter((d) => ['host', 'router', 'station', 'container'].includes(getDeviceType(d))),
    [eligibleDevices]
  )

  const [tab, setTab] = useState<'suite' | 'connectivity' | 'stress' | 'results' | 'ai'>('suite')
  const [collectorHealth, setCollectorHealth] = useState<MetricsCollectorHealth | null>(null)
  const [collectorBusy, setCollectorBusy] = useState(false)

  const [pingSrc, setPingSrc] = useState<string>(hostLikeDevices[0] ? getRuntimeName(hostLikeDevices[0]) : '')
  const [pingDst, setPingDst] = useState<string>(hostLikeDevices[1] ? getRuntimeName(hostLikeDevices[1]) : pingSrc)
  const [pingCount, setPingCount] = useState<string>('3')
  const [pingOutput, setPingOutput] = useState<string>('')
  const [pingRunning, setPingRunning] = useState<boolean>(false)

  const [iperfSrc, setIperfSrc] = useState<string>(hostLikeDevices[0] ? getRuntimeName(hostLikeDevices[0]) : '')
  const [iperfDst, setIperfDst] = useState<string>(hostLikeDevices[1] ? getRuntimeName(hostLikeDevices[1]) : iperfSrc)
  const [iperfSeconds, setIperfSeconds] = useState<string>('10')
  const [iperfParallel, setIperfParallel] = useState<string>('1')
  const [iperfOutput, setIperfOutput] = useState<string>('')
  const [iperfRunning, setIperfRunning] = useState<boolean>(false)

  const [udpSrc, setUdpSrc] = useState<string>(hostLikeDevices[0] ? getRuntimeName(hostLikeDevices[0]) : '')
  const [udpDst, setUdpDst] = useState<string>(hostLikeDevices[1] ? getRuntimeName(hostLikeDevices[1]) : udpSrc)
  const [udpSeconds, setUdpSeconds] = useState<string>('10')
  const [udpBandwidth, setUdpBandwidth] = useState<string>('10')
  const [udpPacketSize, setUdpPacketSize] = useState<string>('1400')
  const [udpOutput, setUdpOutput] = useState<string>('')
  const [udpRunning, setUdpRunning] = useState<boolean>(false)

  const [cpuDuration, setCpuDuration] = useState<string>('10')
  const [cpuWorkers, setCpuWorkers] = useState<string>('1')
  const [memDuration, setMemDuration] = useState<string>('10')
  const [memMb, setMemMb] = useState<string>('256')
  const [sampleInterval, setSampleInterval] = useState<string>('1')

  const [stressRunning, setStressRunning] = useState<boolean>(false)
  const [cpuStressOutput, setCpuStressOutput] = useState<string>('')
  const [memStressOutput, setMemStressOutput] = useState<string>('')

  const [fullPingMatrixCount, setFullPingMatrixCount] = useState<string>('1')
  const [fullTcpSeconds, setFullTcpSeconds] = useState<string>('10')
  const [fullTcpParallel, setFullTcpParallel] = useState<string>('1')
  const [fullUdpSeconds, setFullUdpSeconds] = useState<string>('10')
  const [fullUdpBandwidth, setFullUdpBandwidth] = useState<string>('10')
  const [fullUdpPacketSize, setFullUdpPacketSize] = useState<string>('1400')
  const [fullCpuDuration, setFullCpuDuration] = useState<string>('10')
  const [fullMemDuration, setFullMemDuration] = useState<string>('10')
  const [fullMemMb, setFullMemMb] = useState<string>('256')

  const [fullRunId, setFullRunId] = useState<string>('')
  const [fullRunStatus, setFullRunStatus] = useState<any>(null)
  const [fullRunning, setFullRunning] = useState<boolean>(false)
  const [templateRunning, setTemplateRunning] = useState<string>('')

  const [resultsRunId, setResultsRunId] = useState<string>('')
  const [results, setResults] = useState<TestResults | null>(null)
  const [resultsLoading, setResultsLoading] = useState<boolean>(false)
  const [selectedDevice, setSelectedDevice] = useState<string>('')
  const [selectedReason, setSelectedReason] = useState<string>('cpu_stress')

  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analysisContent, setAnalysisContent] = useState<string>('')
  const [analysisHighlights, setAnalysisHighlights] = useState<any>(null)

  useEffect(() => {
    if (!isRunning) return
    let canceled = false
    const load = async () => {
      try {
        const res = await metricsCollectorAPI.health()
        if (!canceled) setCollectorHealth(res.data as any)
      } catch {
        if (!canceled) setCollectorHealth(null)
      }
    }
    load()
    const t = window.setInterval(load, 10_000)
    return () => {
      canceled = true
      window.clearInterval(t)
    }
  }, [isRunning])

  const toggleMetricsCollection = async () => {
    setCollectorBusy(true)
    try {
      if (collectorHealth?.collection_active) {
        await metricsCollectorAPI.stop()
        toast.success('Metrics collection stopped')
      } else {
        await metricsCollectorAPI.start()
        toast.success('Metrics collection started')
      }
      const res = await metricsCollectorAPI.health()
      setCollectorHealth(res.data as any)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to toggle metrics collection')
    } finally {
      setCollectorBusy(false)
    }
  }

  useEffect(() => {
    if (!hostLikeDevices.length) return
    const first = getRuntimeName(hostLikeDevices[0])
    const second = getRuntimeName(hostLikeDevices[1] || hostLikeDevices[0])
    if (!pingSrc) setPingSrc(first)
    if (!pingDst) setPingDst(second)
    if (!iperfSrc) setIperfSrc(first)
    if (!iperfDst) setIperfDst(second)
    if (!udpSrc) setUdpSrc(first)
    if (!udpDst) setUdpDst(second)
    if (!selectedDevice) setSelectedDevice(first)
  }, [hostLikeDevices, pingSrc, pingDst, iperfSrc, iperfDst, udpSrc, udpDst, selectedDevice])

  const devicesByName = useMemo(() => {
    const map = new Map<string, any>()
    for (const d of eligibleDevices) map.set(getRuntimeName(d), d)
    return map
  }, [eligibleDevices])

  const deviceOptions = (list: any[]) =>
    list.map((d) => {
      const name = getRuntimeName(d)
      const type = getDeviceType(d)
      const ip = getDeviceIpv4(d)
      const label = `${name}${type ? ` (${type})` : ''}${ip ? ` • ${ip}` : ''}`
      return { value: name, label }
    })

  const hostOptions = useMemo(() => deviceOptions(hostLikeDevices), [hostLikeDevices])
  const hasPair = hostLikeDevices.length >= 2

  const pollRun = async (runId: string, onUpdate: (data: any) => void) => {
    const start = Date.now()
    while (true) {
      const res = await testsAPI.status(runId)
      const data = res.data
      onUpdate(data)
      const status = String(data?.status || '').toLowerCase()
      if (['completed', 'failed', 'canceled'].includes(status)) return data
      if (Date.now() - start > 10 * 60 * 1000) return data
      await new Promise((r) => setTimeout(r, 1000))
    }
  }

  const loadResults = async (runId: string) => {
    setResultsLoading(true)
    setResultsRunId(runId)
    try {
      const res = await testsAPI.results(runId, topologyId, 240)
      setResults(res.data as any)
      const keys = Object.keys((res.data as any)?.metrics?.series_by_device || {})
      if (!selectedDevice && keys.length) setSelectedDevice(keys[0])
    } catch (e: any) {
      setResults(null)
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to load results')
    } finally {
      setResultsLoading(false)
    }
  }

  const runSuite = async (suite: string, params: any, onUpdate?: (data: any) => void) => {
    const res = await testsAPI.run({ topology_id: topologyId, suite, params })
    const runId = String(res.data?.run_id || '')
    if (!runId) return res.data
    setResultsRunId(runId)
    const final = await pollRun(runId, (data) => onUpdate?.(data))
    await loadResults(runId)
    return final
  }

  const runTemplate = async (suite: 'sdn_smoke' | 'mano_local_smoke') => {
    if (!isRunning) return toast.error('Start the emulation first')
    setTemplateRunning(suite)
    try {
      const final = await runSuite(suite, {})
      const status = String(final?.status || '').toLowerCase()
      if (status === 'completed') toast.success(`${suite} completed`)
      else toast.error(final?.message || `${suite} failed`)
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || `${suite} failed`)
    } finally {
      setTemplateRunning('')
    }
  }

  const handlePing = async () => {
    if (!isRunning) return toast.error('Start the emulation first')
    const src = pingSrc
    const dst = pingDst
    if (!src || !dst || src === dst) return toast.error('Select two different devices')
    const dstDevice = devicesByName.get(dst)
    const ip = dstDevice ? getDeviceIpv4(dstDevice) : ''
    if (!ip) return toast.error('Target device has no IPv4 address')

    const count = clampInt(pingCount, 1, 50, 3)
    setPingRunning(true)
    setPingOutput('')
    try {
      const data = await runSuite(
        'ping',
        { src, dst, count },
        (upd) => {
          const step = (upd?.steps || []).find((s: any) => String(s.step_id) === 'ping')
          const out = String(step?.data?.stdout || '')
          if (out) setPingOutput(out.trim())
        }
      )
      const step = (data?.steps || []).find((s: any) => String(s.step_id) === 'ping')
      setPingOutput(String(step?.data?.stdout || pingOutput || '').trim())
      toast.success('Ping completed')
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Ping failed'
      setPingOutput(String(msg))
      toast.error(msg)
    } finally {
      setPingRunning(false)
    }
  }

  const handleIperf = async () => {
    if (!isRunning) return toast.error('Start the emulation first')
    const src = iperfSrc
    const dst = iperfDst
    if (!src || !dst || src === dst) return toast.error('Select two different devices')
    const dstDevice = devicesByName.get(dst)
    const ip = dstDevice ? getDeviceIpv4(dstDevice) : ''
    if (!ip) return toast.error('Target device has no IPv4 address')

    const seconds = clampInt(iperfSeconds, 1, 15, 10)
    const parallel = clampInt(iperfParallel, 1, 16, 1)
    setIperfRunning(true)
    setIperfOutput('')
    try {
      const data = await runSuite(
        'iperf_tcp',
        { src, dst, seconds, parallel },
        (upd) => {
          const step = (upd?.steps || []).find((s: any) => String(s.step_id) === 'iperf_tcp')
          const out = String(step?.data?.stdout || '')
          if (out) setIperfOutput(out.trim())
        }
      )
      const step = (data?.steps || []).find((s: any) => String(s.step_id) === 'iperf_tcp')
      setIperfOutput(String(step?.data?.stdout || iperfOutput || '').trim())
      toast.success('TCP bandwidth test completed')
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'TCP bandwidth test failed'
      setIperfOutput(String(msg))
      toast.error(msg)
    } finally {
      setIperfRunning(false)
    }
  }

  const handleUdp = async () => {
    if (!isRunning) return toast.error('Start the emulation first')
    const src = udpSrc
    const dst = udpDst
    if (!src || !dst || src === dst) return toast.error('Select two different devices')
    const dstDevice = devicesByName.get(dst)
    const ip = dstDevice ? getDeviceIpv4(dstDevice) : ''
    if (!ip) return toast.error('Target device has no IPv4 address')

    const seconds = clampInt(udpSeconds, 1, 15, 10)
    const bandwidth_mbps = clampFloat(udpBandwidth, 0.1, 5000, 10)
    const packet_size = clampInt(udpPacketSize, 64, 65507, 1400)
    setUdpRunning(true)
    setUdpOutput('')
    try {
      const data = await runSuite(
        'iperf_udp',
        { src, dst, seconds, bandwidth_mbps, packet_size },
        (upd) => {
          const step = (upd?.steps || []).find((s: any) => String(s.step_id) === 'iperf_udp')
          const out = String(step?.data?.stdout || '')
          if (out) setUdpOutput(out.trim())
        }
      )
      const step = (data?.steps || []).find((s: any) => String(s.step_id) === 'iperf_udp')
      setUdpOutput(String(step?.data?.stdout || udpOutput || '').trim())
      toast.success('UDP load test completed')
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'UDP load test failed'
      setUdpOutput(String(msg))
      toast.error(msg)
    } finally {
      setUdpRunning(false)
    }
  }

  const runCpuStress = async () => {
    if (!isRunning) return toast.error('Start the emulation first')
    if (!hostLikeDevices.length) return toast.error('No host-like devices found')
    setStressRunning(true)
    setCpuStressOutput('')
    try {
      const duration_s = clampInt(cpuDuration, 3, 120, 10)
      const workers_per_device = clampInt(cpuWorkers, 1, 8, 1)
      const sample_interval_s = clampFloat(sampleInterval, 0.5, 5, 1)
      const data = await runSuite('cpu_stress', { duration_s, workers_per_device, sample_interval_s }, (upd) => {
        const step = (upd?.steps || []).find((s: any) => String(s.step_id) === 'cpu_stress')
        const msg = String(step?.message || '')
        if (msg) setCpuStressOutput(msg)
      })
      const step = (data?.steps || []).find((s: any) => String(s.step_id) === 'cpu_stress')
      setCpuStressOutput(step?.message || 'CPU stress completed')
      toast.success('CPU stress completed')
    } finally {
      setStressRunning(false)
    }
  }

  const stopCpuStress = async () => {
    setStressRunning(true)
    try {
      await runSuite('cpu_stress_stop', {})
      toast.success('CPU stress stopped')
    } finally {
      setStressRunning(false)
    }
  }

  const runMemStress = async () => {
    if (!isRunning) return toast.error('Start the emulation first')
    if (!hostLikeDevices.length) return toast.error('No host-like devices found')
    setStressRunning(true)
    setMemStressOutput('')
    try {
      const duration_s = clampInt(memDuration, 3, 120, 10)
      const mb_per_device = clampInt(memMb, 16, 4096, 256)
      const sample_interval_s = clampFloat(sampleInterval, 0.5, 5, 1)
      const data = await runSuite('memory_stress', { duration_s, mb_per_device, sample_interval_s }, (upd) => {
        const step = (upd?.steps || []).find((s: any) => String(s.step_id) === 'memory_stress')
        const msg = String(step?.message || '')
        if (msg) setMemStressOutput(msg)
      })
      const step = (data?.steps || []).find((s: any) => String(s.step_id) === 'memory_stress')
      setMemStressOutput(step?.message || 'Memory stress completed')
      toast.success('Memory stress completed')
    } finally {
      setStressRunning(false)
    }
  }

  const stopMemStress = async () => {
    setStressRunning(true)
    try {
      await runSuite('memory_stress_stop', {})
      toast.success('Memory stress stopped')
    } finally {
      setStressRunning(false)
    }
  }

  const captureSnapshot = async () => {
    if (!isRunning) return toast.error('Start the emulation first')
    try {
      await runSuite('metrics_snapshot', {})
      toast.success('Metrics snapshot saved to topology InfluxDB')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to capture snapshot')
    }
  }

  const startFullSuite = async () => {
    if (!isRunning) return toast.error('Start the emulation first')
    setFullRunning(true)
    setFullRunStatus(null)
    setFullRunId('')
    try {
      const seconds = clampInt(fullTcpSeconds, 1, 15, 10)
      const parallel = clampInt(fullTcpParallel, 1, 16, 1)
      const udp_seconds = clampInt(fullUdpSeconds, 1, 15, 10)
      const bandwidth_mbps = clampFloat(fullUdpBandwidth, 0.1, 5000, 10)
      const packet_size = clampInt(fullUdpPacketSize, 64, 65507, 1400)
      const cpu_duration_s = clampInt(fullCpuDuration, 3, 120, 10)
      const mem_duration_s = clampInt(fullMemDuration, 3, 120, 10)
      const mb_per_device = clampInt(fullMemMb, 16, 4096, 256)
      const cpu_workers_per_device = clampInt(cpuWorkers, 1, 8, 1)
      const sample_interval_s = clampFloat(sampleInterval, 0.5, 5, 1)
      const ping_matrix_count = clampInt(fullPingMatrixCount, 1, 10, 1)

      const res = await testsAPI.run({
        topology_id: topologyId,
        suite: 'full',
        params: {
          seconds,
          parallel,
          udp_seconds,
          bandwidth_mbps,
          packet_size,
          cpu_duration_s,
          mem_duration_s,
          mb_per_device,
          cpu_workers_per_device,
          sample_interval_s,
          ping_matrix_count,
        },
      })
      const runId = String(res.data?.run_id || '')
      setFullRunId(runId)
      const data = await pollRun(runId, setFullRunStatus)
      setFullRunStatus(data)
      await loadResults(runId)
      const status = String(data?.status || '').toLowerCase()
      if (status === 'completed') toast.success('Full suite completed')
      else if (status === 'canceled') toast.error('Full suite canceled')
      else toast.error(data?.message || 'Full suite failed')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to start full suite')
    } finally {
      setFullRunning(false)
    }
  }

  const stopFullSuite = async () => {
    if (!fullRunId) return
    try {
      await testsAPI.stop(fullRunId)
      toast.success('Cancel requested')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'Failed to cancel')
    }
  }

  const analyzeWithAi = async () => {
    const runId = resultsRunId || fullRunId
    if (!runId) return toast.error('Run a test suite first')
    setAnalysisLoading(true)
    setAnalysisContent('')
    setAnalysisHighlights(null)
    try {
      const settings = await aiAPI.settings()
      const configured = (settings.data?.providers || []).find((p: any) => p.configured)
      const provider = (configured?.provider || 'ollama') as any
      const model = configured?.default_model || undefined
      const res = await aiAPI.network.analyzeTests({ topology_id: topologyId, run_id: runId, provider, model })
      setAnalysisContent(String(res.data?.content || ''))
      setAnalysisHighlights(res.data?.highlights || null)
      toast.success('AI analysis ready')
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || e?.message || 'AI analysis failed')
    } finally {
      setAnalysisLoading(false)
    }
  }

  const deviceKeys = useMemo(() => Object.keys(results?.metrics?.series_by_device || {}), [results])
  const reasons = useMemo(() => {
    const set = new Set<string>()
    for (const dev of Object.keys(results?.metrics?.series_by_device || {})) {
      for (const p of (results?.metrics?.series_by_device || {})[dev] || []) {
        if (p?.reason) set.add(String(p.reason))
      }
    }
    const list = Array.from(set)
    list.sort()
    return list
  }, [results])

  const selectedSeries = useMemo(() => {
    const raw = (results?.metrics?.series_by_device || {})[selectedDevice] || []
    const filtered = selectedReason ? raw.filter((p) => String(p.reason || '') === String(selectedReason)) : raw
    return filtered
      .filter((p) => typeof p.t === 'number')
      .map((p) => ({
        t: p.t as number,
        time: new Date(p.t as number).toLocaleTimeString(),
        cpu_percent: Number(p.cpu_percent || 0),
        memory_percent: Number(p.memory_percent || 0),
      }))
  }, [results, selectedDevice, selectedReason])

  const iperfChart = useMemo(() => {
    const items = (results?.iperf || []).slice().sort((a, b) => Number(a.t || 0) - Number(b.t || 0))
    const lastByProto: Record<string, any> = {}
    for (const it of items) lastByProto[String(it.proto || 'unknown')] = it
    return Object.values(lastByProto).map((it: any) => ({
      proto: String(it.proto || 'unknown').toUpperCase(),
      link: `${it.src} → ${it.dst}`,
      throughput_mbps: Number(it.throughput_mbps || 0),
    }))
  }, [results])

  const pingTable = useMemo(() => {
    const items = (results?.ping || []).slice().sort((a, b) => Number(a.t || 0) - Number(b.t || 0))
    const lastByPair: Record<string, any> = {}
    for (const it of items) lastByPair[`${it.src}__${it.dst}`] = it
    return Object.values(lastByPair)
  }, [results])

  if (!isRunning) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Test Network Topology</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="text-sm text-gray-600 dark:text-gray-400">Start the emulation to run connectivity and stress tests.</div>
        </CardContent>
      </Card>
    )
  }

  const latestRunId = resultsRunId || fullRunId
  const collectorOn = Boolean(collectorHealth?.collection_active)

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="text-lg font-semibold text-gray-900 dark:text-white">Test Network Topology</div>
            <div className="text-sm text-gray-600 dark:text-gray-400">
              Run connectivity, load and stress tests; results are stored in topology InfluxDB.
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={toggleMetricsCollection} disabled={collectorBusy}>
              {collectorBusy ? 'Working…' : collectorOn ? 'Stop Metrics Collection' : 'Start Metrics Collection'}
            </Button>
            <Button variant="secondary" onClick={() => latestRunId && loadResults(latestRunId)} disabled={!latestRunId || resultsLoading}>
              {resultsLoading ? 'Loading…' : 'Refresh Results'}
            </Button>
            <div
              className={`rounded-full px-3 py-1 text-xs font-medium border ${
                collectorOn
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900/50 dark:bg-emerald-900/20 dark:text-emerald-300'
                  : 'border-gray-200 bg-gray-50 text-gray-700 dark:border-gray-800 dark:bg-gray-900/40 dark:text-gray-300'
              }`}
            >
              Metrics: {collectorOn ? `ON • streams ${collectorHealth?.active_streams ?? '—'}` : 'OFF'}
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900/40 p-1">
          <div className="flex gap-1 overflow-x-auto">
          {(
            [
              { id: 'suite', label: 'Suite' },
              { id: 'connectivity', label: 'Connectivity' },
              { id: 'stress', label: 'Stress' },
              { id: 'results', label: 'Results' },
              { id: 'ai', label: 'AI' },
            ] as const
          ).map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                tab === t.id
                  ? 'bg-white dark:bg-gray-950 text-gray-900 dark:text-white shadow-sm'
                  : 'text-gray-600 dark:text-gray-300 hover:bg-white/70 dark:hover:bg-gray-950/50'
              }`}
            >
              {t.label}
            </button>
          ))}
          </div>
        </div>
      </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        <div className={tab === 'results' ? 'hidden' : 'xl:col-span-1 space-y-6'}>
          {tab === 'suite' && (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Verification Templates (SDN + MANO)</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  One-click smoke tests to verify that SDN/MANO actions really affect the running emulation.
                </div>
                <div className="grid grid-cols-1 gap-2">
                  <Button onClick={() => runTemplate('sdn_smoke')} disabled={Boolean(templateRunning) || fullRunning}>
                    {templateRunning === 'sdn_smoke' ? 'Running SDN smoke…' : 'Run SDN Smoke (controller enforcement)'}
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => runTemplate('mano_local_smoke')}
                    disabled={Boolean(templateRunning) || fullRunning}
                  >
                    {templateRunning === 'mano_local_smoke' ? 'Running MANO smoke…' : 'Run MANO Smoke (local NFVO/VNFM)'}
                  </Button>
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  SDN smoke temporarily disables a switch controller to prove dataplane dependence. MANO smoke creates a temporary container VNF
                  and removes it.
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Full Test Suite</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Ping count (matrix)</div>
                    <Input value={fullPingMatrixCount} onChange={(e) => setFullPingMatrixCount(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Sample interval (s)</div>
                    <Input value={sampleInterval} onChange={(e) => setSampleInterval(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">TCP seconds</div>
                    <Input value={fullTcpSeconds} onChange={(e) => setFullTcpSeconds(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">TCP parallel</div>
                    <Input value={fullTcpParallel} onChange={(e) => setFullTcpParallel(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">UDP seconds</div>
                    <Input value={fullUdpSeconds} onChange={(e) => setFullUdpSeconds(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">UDP bandwidth (Mbps)</div>
                    <Input value={fullUdpBandwidth} onChange={(e) => setFullUdpBandwidth(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">UDP packet size</div>
                    <Input value={fullUdpPacketSize} onChange={(e) => setFullUdpPacketSize(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">CPU workers/device</div>
                    <Input value={cpuWorkers} onChange={(e) => setCpuWorkers(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">CPU duration (s)</div>
                    <Input value={fullCpuDuration} onChange={(e) => setFullCpuDuration(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Mem duration (s)</div>
                    <Input value={fullMemDuration} onChange={(e) => setFullMemDuration(e.target.value)} />
                  </div>
                  <div className="sm:col-span-2">
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Mem MB/device</div>
                    <Input value={fullMemMb} onChange={(e) => setFullMemMb(e.target.value)} />
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <Button onClick={startFullSuite} disabled={fullRunning || Boolean(templateRunning)}>
                    {fullRunning ? 'Running…' : 'Run Full Suite'}
                  </Button>
                  <Button variant="secondary" onClick={stopFullSuite} disabled={!fullRunId || !fullRunning}>
                    Cancel
                  </Button>
                  <Button variant="secondary" onClick={captureSnapshot} disabled={fullRunning || Boolean(templateRunning)}>
                    Save Metrics Snapshot
                  </Button>
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Bandwidth tests are capped to ~15s due to device command timeouts.
                </div>
              </CardContent>
            </Card>
          </>
          )}

          {tab === 'connectivity' && (
          <Card>
            <CardHeader>
              <CardTitle>Quick Connectivity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Source</div>
                  <select
                    className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                    value={pingSrc}
                    onChange={(e) => setPingSrc(e.target.value)}
                  >
                    {hostOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Target</div>
                  <select
                    className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                    value={pingDst}
                    onChange={(e) => setPingDst(e.target.value)}
                  >
                    {hostOptions.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Count</div>
                  <Input value={pingCount} onChange={(e) => setPingCount(e.target.value)} />
                </div>
                <div className="flex items-end">
                  <Button className="w-full" onClick={handlePing} disabled={pingRunning || !hasPair}>
                    {pingRunning ? 'Running…' : 'Run Ping'}
                  </Button>
                </div>
              </div>
              <OutputPanel title="Ping output" value={pingOutput} placeholder="Output will appear here…" maxHeightClass="max-h-40" />
            </CardContent>
          </Card>
          )}

          {tab === 'connectivity' && (
          <Card>
            <CardHeader>
              <CardTitle>Bandwidth (TCP) & Packet Load (UDP)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-3">
                <div className="text-sm font-medium text-gray-800 dark:text-gray-200">TCP (iperf)</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Client</div>
                    <select
                      className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                      value={iperfSrc}
                      onChange={(e) => setIperfSrc(e.target.value)}
                    >
                      {hostOptions.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Server</div>
                    <select
                      className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                      value={iperfDst}
                      onChange={(e) => setIperfDst(e.target.value)}
                    >
                      {hostOptions.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Seconds</div>
                    <Input value={iperfSeconds} onChange={(e) => setIperfSeconds(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Parallel</div>
                    <Input value={iperfParallel} onChange={(e) => setIperfParallel(e.target.value)} />
                  </div>
                  <div className="sm:col-span-2">
                    <Button className="w-full" onClick={handleIperf} disabled={iperfRunning || !hasPair}>
                      {iperfRunning ? 'Running…' : 'Run TCP Bandwidth Test'}
                    </Button>
                  </div>
                </div>
                <OutputPanel title="TCP output" value={iperfOutput} placeholder="Output will appear here…" maxHeightClass="max-h-40" />
              </div>

              <div className="space-y-3">
                <div className="text-sm font-medium text-gray-800 dark:text-gray-200">UDP (iperf)</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Client</div>
                    <select
                      className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                      value={udpSrc}
                      onChange={(e) => setUdpSrc(e.target.value)}
                    >
                      {hostOptions.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Server</div>
                    <select
                      className="w-full rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
                      value={udpDst}
                      onChange={(e) => setUdpDst(e.target.value)}
                    >
                      {hostOptions.map((o) => (
                        <option key={o.value} value={o.value}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Seconds</div>
                    <Input value={udpSeconds} onChange={(e) => setUdpSeconds(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Bandwidth (Mbps)</div>
                    <Input value={udpBandwidth} onChange={(e) => setUdpBandwidth(e.target.value)} />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Packet size</div>
                    <Input value={udpPacketSize} onChange={(e) => setUdpPacketSize(e.target.value)} />
                  </div>
                  <div className="flex items-end">
                    <Button className="w-full" onClick={handleUdp} disabled={udpRunning || !hasPair}>
                      {udpRunning ? 'Running…' : 'Run UDP Load Test'}
                    </Button>
                  </div>
                </div>
                <OutputPanel title="UDP output" value={udpOutput} placeholder="Output will appear here…" maxHeightClass="max-h-40" />
              </div>
            </CardContent>
          </Card>
          )}

          {tab === 'stress' && (
          <Card>
            <CardHeader>
              <CardTitle>Stress (CPU & Memory)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Sample interval (s)</div>
                  <Input value={sampleInterval} onChange={(e) => setSampleInterval(e.target.value)} />
                </div>
                <div />
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">CPU duration (s)</div>
                  <Input value={cpuDuration} onChange={(e) => setCpuDuration(e.target.value)} />
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">CPU workers/device</div>
                  <Input value={cpuWorkers} onChange={(e) => setCpuWorkers(e.target.value)} />
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Mem duration (s)</div>
                  <Input value={memDuration} onChange={(e) => setMemDuration(e.target.value)} />
                </div>
                <div>
                  <div className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Mem MB/device</div>
                  <Input value={memMb} onChange={(e) => setMemMb(e.target.value)} />
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button onClick={runCpuStress} disabled={stressRunning}>
                  {stressRunning ? 'Running…' : 'Run CPU Stress'}
                </Button>
                <Button variant="secondary" onClick={stopCpuStress} disabled={stressRunning}>
                  Stop CPU Stress
                </Button>
                <Button onClick={runMemStress} disabled={stressRunning}>
                  {stressRunning ? 'Running…' : 'Run Memory Stress'}
                </Button>
                <Button variant="secondary" onClick={stopMemStress} disabled={stressRunning}>
                  Stop Memory Stress
                </Button>
              </div>
              <OutputPanel title="CPU status" value={cpuStressOutput} placeholder="CPU status will appear here…" maxHeightClass="max-h-28" />
              <OutputPanel title="Memory status" value={memStressOutput} placeholder="Memory status will appear here…" maxHeightClass="max-h-28" />
            </CardContent>
          </Card>
          )}

          {tab === 'ai' && (
          <Card>
            <CardHeader>
              <CardTitle>AI Analysis (MCP → LLM)</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <Button onClick={analyzeWithAi} disabled={analysisLoading}>
                  {analysisLoading ? 'Analyzing…' : 'Analyze Latest Results'}
                </Button>
                <div className="text-xs text-gray-600 dark:text-gray-400">
                  Renders Markdown; tool outputs remain in Results.
                </div>
              </div>

              <div>
                <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">Highlights</div>
                <JsonViewer data={analysisHighlights || {}} collapsed={2} />
              </div>

              <div>
                <div className="text-sm font-semibold text-gray-900 dark:text-gray-100 mb-2">Analysis</div>
                <div className="max-h-96 overflow-auto">
                  <MarkdownViewer value={analysisContent} placeholder="Analysis will appear here…" />
                </div>
              </div>

              <details className="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white/70 dark:bg-gray-900/40 px-4 py-3">
                <summary className="cursor-pointer select-none text-sm font-semibold text-gray-800 dark:text-gray-200">
                  AI Console (Agents + MCP)
                </summary>
                <div className="mt-3">
                  <AiConsole scopeTopologyId={topologyId} />
                </div>
              </details>
            </CardContent>
          </Card>
          )}
        </div>

        <div className={tab === 'results' ? 'xl:col-span-3 space-y-6' : 'xl:col-span-2 space-y-6'}>
          {(tab === 'results' || tab === 'stress' || tab === 'ai') && (
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <CardTitle>Results Dashboard</CardTitle>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" onClick={() => (latestRunId ? loadResults(latestRunId) : null)} disabled={!latestRunId || resultsLoading}>
                    {resultsLoading ? 'Refreshing…' : 'Refresh'}
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-3">
                  <div className="text-xs text-gray-600 dark:text-gray-400">Run ID</div>
                  <div className="font-mono text-sm break-all">{resultsRunId || fullRunId || '—'}</div>
                </div>
                <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-3">
                  <div className="text-xs text-gray-600 dark:text-gray-400">Status</div>
                  <div className="text-sm">{String(fullRunStatus?.status || '—')}</div>
                </div>
                <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-3">
                  <div className="text-xs text-gray-600 dark:text-gray-400">Devices (metrics)</div>
                  <div className="text-sm">{deviceKeys.length || '—'}</div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
                <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-gray-800 dark:text-gray-200">CPU / Memory</div>
                    <div className="flex items-center gap-2">
                      <select
                        className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-xs"
                        value={selectedReason}
                        onChange={(e) => setSelectedReason(e.target.value)}
                      >
                        {(reasons.length ? reasons : ['cpu_stress']).map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                      <select
                        className="rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-2 py-1 text-xs"
                        value={selectedDevice}
                        onChange={(e) => setSelectedDevice(e.target.value)}
                      >
                        {deviceKeys.map((k) => (
                          <option key={k} value={k}>
                            {k}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={selectedSeries}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="time" tick={{ fontSize: 11 }} />
                        <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Legend />
                        <Line type="monotone" dataKey="cpu_percent" name="CPU %" stroke="#8b5cf6" dot={false} strokeWidth={2} />
                        <Line type="monotone" dataKey="memory_percent" name="Memory %" stroke="#22c55e" dot={false} strokeWidth={2} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                  {results?.metrics?.summary_by_device?.[selectedDevice] ? (
                    <div className="grid grid-cols-2 gap-2 text-xs text-gray-700 dark:text-gray-300">
                      <div className="rounded border border-gray-200 dark:border-gray-800 p-2">
                        CPU max: {results.metrics.summary_by_device[selectedDevice].cpu_max.toFixed(1)}%
                      </div>
                      <div className="rounded border border-gray-200 dark:border-gray-800 p-2">
                        Mem max: {results.metrics.summary_by_device[selectedDevice].mem_max.toFixed(1)}%
                      </div>
                      <div className="rounded border border-gray-200 dark:border-gray-800 p-2">
                        CPU avg: {results.metrics.summary_by_device[selectedDevice].cpu_avg.toFixed(1)}%
                      </div>
                      <div className="rounded border border-gray-200 dark:border-gray-800 p-2">
                        Mem avg: {results.metrics.summary_by_device[selectedDevice].mem_avg.toFixed(1)}%
                      </div>
                    </div>
                  ) : (
                    <div className="text-sm text-gray-600 dark:text-gray-400">No metrics yet…</div>
                  )}
                </div>

                <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-3 space-y-2">
                  <div className="text-sm font-medium text-gray-800 dark:text-gray-200">Throughput</div>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={iperfChart}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="proto" tick={{ fontSize: 11 }} />
                        <YAxis tick={{ fontSize: 11 }} />
                        <Tooltip />
                        <Legend />
                        <Bar dataKey="throughput_mbps" name="Mbps" fill="#3b82f6" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="text-xs text-gray-600 dark:text-gray-400">
                    {iperfChart.length ? iperfChart.map((i) => `${i.proto} ${i.link}: ${i.throughput_mbps.toFixed(2)} Mbps`).join(' • ') : 'No iperf results yet…'}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          )}

          {tab === 'results' && (
          <Card>
            <CardHeader>
              <CardTitle>Ping Results (latest per pair)</CardTitle>
            </CardHeader>
            <CardContent>
              {pingTable.length ? (
                <div className="overflow-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs text-gray-600 dark:text-gray-400">
                      <tr>
                        <th className="text-left py-2 pr-3">Source</th>
                        <th className="text-left py-2 pr-3">Target</th>
                        <th className="text-right py-2 pr-3">Loss %</th>
                        <th className="text-right py-2 pr-3">RTT avg (ms)</th>
                        <th className="text-right py-2">OK</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pingTable.map((p: any) => (
                        <tr key={`${p.src}-${p.dst}`} className="border-t border-gray-200 dark:border-gray-800">
                          <td className="py-2 pr-3">{p.src}</td>
                          <td className="py-2 pr-3">{p.dst}</td>
                          <td className="py-2 pr-3 text-right">{Number(p.loss_pct || 0).toFixed(1)}</td>
                          <td className="py-2 pr-3 text-right">{Number(p.rtt_avg_ms || 0).toFixed(3)}</td>
                          <td className="py-2 text-right">{Number(p.success || 0) ? 'yes' : 'no'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-sm text-gray-600 dark:text-gray-400">No ping results yet…</div>
              )}
            </CardContent>
          </Card>
          )}

          {tab === 'results' && (
          <Card>
            <CardHeader>
              <CardTitle>Interface Counters (deltas)</CardTitle>
            </CardHeader>
            <CardContent>
              {(results?.counters || []).length ? (
                <div className="overflow-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs text-gray-600 dark:text-gray-400">
                      <tr>
                        <th className="text-left py-2 pr-3">Device</th>
                        <th className="text-left py-2 pr-3">Reason</th>
                        <th className="text-right py-2 pr-3">Bytes TX</th>
                        <th className="text-right py-2 pr-3">Bytes RX</th>
                        <th className="text-right py-2 pr-3">Pkts TX</th>
                        <th className="text-right py-2">Pkts RX</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(results?.counters || []).slice(-12).map((c) => (
                        <tr key={`${c.device}-${c.reason}-${c.t}`} className="border-t border-gray-200 dark:border-gray-800">
                          <td className="py-2 pr-3">{c.device}</td>
                          <td className="py-2 pr-3">{c.reason}</td>
                          <td className="py-2 pr-3 text-right">{c.bytes_sent_delta}</td>
                          <td className="py-2 pr-3 text-right">{c.bytes_received_delta}</td>
                          <td className="py-2 pr-3 text-right">{c.packets_sent_delta}</td>
                          <td className="py-2 text-right">{c.packets_received_delta}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-sm text-gray-600 dark:text-gray-400">No counter deltas yet…</div>
              )}
            </CardContent>
          </Card>
          )}

          {(tab === 'suite' || tab === 'results') && (
          <Card>
            <CardHeader>
              <CardTitle>Run Steps</CardTitle>
            </CardHeader>
            <CardContent className="grid grid-cols-1 lg:grid-cols-2 gap-3">
              <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-3">
                <div className="text-sm font-medium text-gray-800 dark:text-gray-200 mb-2">Steps</div>
                <div className="space-y-2">
                  {(fullRunStatus?.steps || []).length ? (
                    (fullRunStatus.steps || []).map((s: any, idx: number) => (
                      <div key={`${String(s.step_id)}-${idx}`} className="flex items-center justify-between gap-3 text-sm">
                        <div className="min-w-0 truncate">{s.name || s.step_id}</div>
                        <div className="font-mono text-xs text-gray-600 dark:text-gray-400">{String(s.status || '')}</div>
                      </div>
                    ))
                  ) : (
                    <div className="text-sm text-gray-600 dark:text-gray-400">No steps yet…</div>
                  )}
                </div>
              </div>
              <div className="rounded-lg border border-gray-200 dark:border-gray-800 p-3">
                <div className="text-sm font-medium text-gray-800 dark:text-gray-200 mb-2">Logs</div>
                <OutputPanel title="Logs" value={(fullRunStatus?.logs || []).join('\n')} placeholder="Logs will appear here…" maxHeightClass="max-h-64" />
              </div>
            </CardContent>
          </Card>
          )}

          {tab === 'connectivity' && !hasPair && (
            <Card>
              <CardHeader>
                <CardTitle>Missing devices</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Add at least two host-like devices (host/router/station/container) to run ping and bandwidth tests.
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}

function OutputPanel({
  title,
  value,
  placeholder,
  maxHeightClass = 'max-h-64',
}: {
  title: string
  value: string
  placeholder: string
  maxHeightClass?: string
}) {
  const canCopy = Boolean(value && value.trim())
  const handleCopy = async () => {
    if (!canCopy) return
    try {
      await navigator.clipboard.writeText(value)
      toast.success('Copied')
    } catch {
      toast.error('Copy failed')
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-gray-950">
      <div className="flex items-center justify-between gap-3 px-3 py-2 border-b border-gray-800/60">
        <div className="text-xs font-medium text-gray-200">{title}</div>
        <button
          type="button"
          className={`text-xs font-medium ${canCopy ? 'text-gray-200 hover:text-white' : 'text-gray-500'}`}
          onClick={handleCopy}
          disabled={!canCopy}
        >
          Copy
        </button>
      </div>
      <pre className={`text-xs text-gray-100 px-3 py-2 overflow-auto whitespace-pre-wrap ${maxHeightClass}`}>
        {value || placeholder}
      </pre>
    </div>
  )
}
