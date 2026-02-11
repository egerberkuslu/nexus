import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Node } from 'reactflow'
import { Input } from '@/components/atoms/Input'
import { Button } from '@/components/atoms/Button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/atoms/Card'
import { Trash2, Terminal } from 'lucide-react'
import DeviceTerminalModal from './DeviceTerminalModal'
import { p4API, type P4Program } from '@/services/api'

interface DevicePropertiesPanelProps {
  node: Node
  onUpdate: (key: string, value: any) => void
  onDelete: () => void
}

type TabConfig = {
  id: string
  label: string
  content: JSX.Element
}

const parseListValue = (value: any): string[] => {
  if (Array.isArray(value)) {
    return value
  }
  if (typeof value === 'string') {
    return value
      .split(/[\n,;]+/)
      .map((item) => item.trim())
      .filter(Boolean)
  }
  return []
}

const toInputValue = (value: any) => {
  if (value === undefined || value === null) {
    return ''
  }
  return value
}

const asBoolean = (value: any): boolean => value === true || value === 'true'

export const DevicePropertiesPanel: React.FC<DevicePropertiesPanelProps> = ({
  node,
  onUpdate,
  onDelete,
}) => {
  const { t } = useTranslation()
  const deviceType = (node.data.deviceType || '').toLowerCase()
  const props = node.data.properties || {}
  const [activeTab, setActiveTab] = useState<string>('general')
  const [p4Programs, setP4Programs] = useState<P4Program[]>([])
  const [p4Loading, setP4Loading] = useState(false)
  const [p4Error, setP4Error] = useState<string | null>(null)

  const updateProperty = useCallback(
    (key: string, value: any) => {
      onUpdate(key, value)
    },
    [onUpdate]
  )

  const refreshP4Programs = useCallback(async () => {
    setP4Loading(true)
    setP4Error(null)
    try {
      const res = await p4API.listPrograms()
      setP4Programs(res.data || [])
    } catch (err: any) {
      setP4Error(err?.response?.data?.detail || err?.message || 'Failed to load P4 programs')
    } finally {
      setP4Loading(false)
    }
  }, [])

  const applyP4ProgramToNode = useCallback(
    (program: P4Program | null) => {
      if (!program) {
        updateProperty('p4_program_id', '')
        return
      }
      updateProperty('p4_program_id', program.program_id)
      if (program.source_file) updateProperty('p4_source', program.source_file)
      if (program.p4info_file) updateProperty('p4info_path', program.p4info_file)
      if (program.json_file) updateProperty('device_config_path', program.json_file)
    },
    [updateProperty]
  )

  useEffect(() => {
    if (deviceType !== 'p4switch') return
    void refreshP4Programs()
  }, [deviceType, refreshP4Programs])

  const tabs = useMemo<TabConfig[]>(() => {
    const labelField = (
      <Input
        label={t('topology.nodeLabel', 'Node ID / Name')}
        value={node.data.label}
        onChange={(e) => onUpdate('label', e.target.value)}
        placeholder="e.g., h1, s1, r1"
      />
    )

    // Docker configuration tab (common for all device types)
    const dockerTab: TabConfig = {
      id: 'docker',
      label: 'Docker',
      content: (
        <div className="space-y-4">
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="dockerized"
              checked={asBoolean(props.dockerized)}
              onChange={(e) => updateProperty('dockerized', e.target.checked)}
              className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <label htmlFor="dockerized" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {t('topology.enableDocker', 'Enable Docker Container')}
            </label>
          </div>

          {asBoolean(props.dockerized) && (
            <>
              <Input
                label={t('topology.dockerImage', 'Docker Image')}
                value={toInputValue(props.docker_image)}
                onChange={(e) => updateProperty('docker_image', e.target.value)}
                placeholder="ubuntu:22.04"
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.dockerCommand', 'Command (optional)')}
                </label>
                <textarea
                  value={toInputValue(props.docker_command)}
                  onChange={(e) => updateProperty('docker_command', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  rows={2}
                  placeholder="/bin/bash -c 'your command here'"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.dockerEnvironment', 'Environment Variables')}
                </label>
                <textarea
                  value={toInputValue(
                    props.docker_environment
                      ? Object.entries(props.docker_environment)
                          .map(([k, v]) => `${k}=${v}`)
                          .join('\n')
                      : ''
                  )}
                  onChange={(e) => {
                    const envVars = e.target.value
                      .split('\n')
                      .filter(Boolean)
                      .reduce((acc, line) => {
                        const [key, ...valueParts] = line.split('=')
                        if (key && valueParts.length > 0) {
                          let value = valueParts.join('=').trim()
                          // Strip surrounding quotes (single or double) from the value
                          if ((value.startsWith("'") && value.endsWith("'")) ||
                              (value.startsWith('"') && value.endsWith('"'))) {
                            value = value.slice(1, -1)
                          }
                          acc[key.trim()] = value
                        }
                        return acc
                      }, {} as Record<string, string>)
                    updateProperty('docker_environment', envVars)
                  }}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  rows={3}
                  placeholder="KEY1=value1&#10;KEY2=value2"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.dockerVolumes', 'Volumes (one per line)')}
                </label>
                <textarea
                  value={toInputValue(
                    Array.isArray(props.docker_volumes) ? props.docker_volumes.join('\n') : props.docker_volumes || ''
                  )}
                  onChange={(e) => {
                    const volumes = e.target.value.split('\n').filter(Boolean)
                    updateProperty('docker_volumes', volumes)
                  }}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  rows={2}
                  placeholder="/host/path:/container/path&#10;/another/path:/mount/point"
                />
              </div>
            </>
          )}
        </div>
      ),
    }

    if (deviceType === 'host') {
      return [
        {
          id: 'general',
          label: t('common.general', 'General'),
          content: <div className="space-y-4">{labelField}</div>,
        },
        {
          id: 'network',
          label: t('common.network', 'Network'),
          content: (
            <div className="space-y-4">
              <Input
                label={t('topology.ipv4', 'IPv4 Address')}
                value={toInputValue(props.ip)}
                onChange={(e) => updateProperty('ip', e.target.value)}
                placeholder="10.0.0.1/24"
              />
              <Input
                label={t('topology.ipv6', 'IPv6 Address')}
                value={toInputValue(props.ip6)}
                onChange={(e) => updateProperty('ip6', e.target.value)}
                placeholder="fd00::1/64"
              />
              <Input
                label={t('topology.mac', 'MAC Address')}
                value={toInputValue(props.mac)}
                onChange={(e) => updateProperty('mac', e.target.value)}
                placeholder="00:00:00:00:00:01"
              />
              <Input
                label={t('topology.defaultGateway', 'Default Gateway')}
                value={toInputValue(props.default_route)}
                onChange={(e) => updateProperty('default_route', e.target.value)}
                placeholder="10.0.0.254"
              />
              <Input
                label={t('topology.mtu', 'MTU')}
                value={toInputValue(props.mtu)}
                onChange={(e) => updateProperty('mtu', e.target.value)}
                placeholder="1500"
              />
            </div>
          ),
        },
        {
          id: 'resources',
          label: t('common.resources', 'Resources'),
          content: (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.cpuLimit', 'CPU Limit (cores)')}
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={toInputValue(props.cpu)}
                  onChange={(e) => updateProperty('cpu', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  placeholder="1.0"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.memoryLimit', 'Memory Limit (MB)')}
                </label>
                <input
                  type="number"
                  value={toInputValue(props.memory)}
                  onChange={(e) => updateProperty('memory', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  placeholder="512"
                />
              </div>
            </div>
          ),
        },
        {
          id: 'advanced',
          label: t('common.advanced', 'Advanced'),
          content: (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.staticRoutes', 'Static Routes')}
                </label>
                <textarea
                  value={toInputValue(props.static_routes)}
                  onChange={(e) => updateProperty('static_routes', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  rows={3}
                  placeholder="10.1.0.0/24 via 10.0.0.2&#10;default via 10.0.0.254"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.dnsServers', 'DNS Servers')}
                </label>
                <textarea
                  value={toInputValue(props.dns_servers)}
                  onChange={(e) => updateProperty('dns_servers', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  rows={2}
                  placeholder="8.8.8.8&#10;1.1.1.1"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.startupCommands', 'Startup Commands')}
                </label>
                <textarea
                  value={toInputValue(props.startup_commands)}
                  onChange={(e) => updateProperty('startup_commands', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  rows={3}
                  placeholder="ip neigh add 10.0.0.5 lladdr 02:00:00:00:00:05 dev host-eth0"
                />
              </div>
            </div>
          ),
        },
        dockerTab,
      ]
    }

    if (deviceType === 'switch' || deviceType === 'p4switch') {
      return [
        {
          id: 'general',
          label: t('common.general', 'General'),
          content: (
            <div className="space-y-4">
              {labelField}
              <Input
                label="Datapath ID (DPID)"
                value={toInputValue(props.dpid || props.datapath_id)}
                onChange={(e) => updateProperty('dpid', e.target.value)}
                placeholder="0000000000000001"
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.switchType', 'Switch Type')}
                </label>
                <select
                  value={toInputValue(props.switch_type) || 'ovs'}
                  onChange={(e) => updateProperty('switch_type', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                >
                  <option value="ovs">Open vSwitch (OVS)</option>
                  <option value="linuxbridge">Linux Bridge</option>
                  <option value="p4">P4 Switch</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.openflowVersion', 'OpenFlow Version')}
                </label>
                <select
                  value={toInputValue(props.openflow_version) || '1.3'}
                  onChange={(e) => updateProperty('openflow_version', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                >
                  <option value="1.0">OpenFlow 1.0</option>
                  <option value="1.3">OpenFlow 1.3</option>
                  <option value="1.4">OpenFlow 1.4</option>
                  <option value="1.5">OpenFlow 1.5</option>
                </select>
              </div>
            </div>
          ),
        },
        {
          id: 'controller',
          label: t('topology.controller', 'Controller'),
          content: (
            <div className="space-y-4">
              <Input
                label={t('topology.controllerEndpoint', 'Controller Endpoint')}
                value={toInputValue(props.controller)}
                onChange={(e) => updateProperty('controller', e.target.value)}
                placeholder="127.0.0.1:6653"
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.maxFlows', 'Max Flow Entries')}
                </label>
                <input
                  type="number"
                  value={toInputValue(props.max_flows)}
                  onChange={(e) => updateProperty('max_flows', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  placeholder="10000"
                />
              </div>
            </div>
          ),
        },
        ...(deviceType === 'p4switch'
          ? [
              {
                id: 'p4',
                label: 'P4',
                content: (
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                          P4 Program
                        </label>
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => void refreshP4Programs()}
                          disabled={p4Loading}
                        >
                          {p4Loading ? 'Loading…' : 'Refresh'}
                        </Button>
                      </div>
                      <select
                        value={toInputValue(props.p4_program_id)}
                        onChange={(e) => {
                          const selected = (e.target.value || '').trim()
                          const program = p4Programs.find((p) => p.program_id === selected) || null
                          applyP4ProgramToNode(program)
                        }}
                        className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                      >
                        <option value="">(none)</option>
                        {p4Programs.map((p) => (
                          <option key={p.program_id} value={p.program_id}>
                            {p.name} · {p.status}
                          </option>
                        ))}
                      </select>
                      {p4Error && (
                        <div className="text-sm text-red-600 dark:text-red-400">{p4Error}</div>
                      )}
                      <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                          Upload .p4 (compile)
                        </label>
                        <input
                          type="file"
                          accept=".p4"
                          onChange={(e) => {
                            const file = e.target.files?.[0] || null
                            if (!file) return
                            void (async () => {
                              setP4Loading(true)
                              setP4Error(null)
                              try {
                                const res = await p4API.upload(file)
                                const program = res.data
                                setP4Programs((prev) => [program, ...prev.filter((p) => p.program_id !== program.program_id)])
                                applyP4ProgramToNode(program)
                              } catch (err: any) {
                                setP4Error(err?.response?.data?.detail || err?.message || 'Failed to compile P4 program')
                              } finally {
                                setP4Loading(false)
                              }
                            })()
                          }}
                          className="block w-full text-sm text-gray-700 dark:text-gray-300 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-sm file:font-medium file:bg-gray-100 dark:file:bg-gray-800 file:text-gray-700 dark:file:text-gray-200 hover:file:bg-gray-200 dark:hover:file:bg-gray-700"
                        />
                      </div>
                    </div>
                    <Input
                      label="P4 Program Source"
                      value={toInputValue(props.p4_source)}
                      onChange={(e) => updateProperty('p4_source', e.target.value)}
                      placeholder="/path/to/program.p4"
                    />
                    <Input
                      label="P4Info Path"
                      value={toInputValue(props.p4info_path)}
                      onChange={(e) => updateProperty('p4info_path', e.target.value)}
                      placeholder="/path/to/program.p4info"
                    />
                    <Input
                      label="Device Config Path"
                      value={toInputValue(props.device_config_path)}
                      onChange={(e) => updateProperty('device_config_path', e.target.value)}
                      placeholder="/path/to/device_config.json"
                    />
                    <div>
                      <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                        gRPC Port
                      </label>
                      <input
                        type="number"
                        value={toInputValue(props.grpc_port)}
                        onChange={(e) => updateProperty('grpc_port', e.target.value)}
                        className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                        placeholder="50051"
                      />
                    </div>
                    <Input
                      label="P4Runtime Address"
                      value={toInputValue(props.runtime_address)}
                      onChange={(e) => updateProperty('runtime_address', e.target.value)}
                      placeholder="127.0.0.1:9559"
                    />
                  </div>
                ),
              },
            ]
          : []),
        dockerTab,
      ]
    }

    if (deviceType === 'router') {
      const routerProtocols = parseListValue(props.protocols)
      return [
        {
          id: 'general',
          label: t('common.general', 'General'),
          content: (
            <div className="space-y-4">
              {labelField}
              <Input
                label={t('topology.routerIp', 'Router IP')}
                value={toInputValue(props.ip)}
                onChange={(e) => updateProperty('ip', e.target.value)}
                placeholder="192.168.1.1/24"
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.routingDaemon', 'Routing Daemon')}
                </label>
                <select
                  value={toInputValue(props.router_daemon) || 'frr'}
                  onChange={(e) => updateProperty('router_daemon', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                >
                  <option value="frr">FRRouting (FRR)</option>
                  <option value="bird">BIRD</option>
                  <option value="quagga">Quagga</option>
                </select>
              </div>
            </div>
          ),
        },
        {
          id: 'protocols',
          label: t('topology.protocols', 'Protocols'),
          content: (
            <div className="space-y-4">
              <div>
                <span className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.routingProtocols', 'Routing Protocols')}
                </span>
                <div className="space-y-2">
                  {['ospf', 'bgp', 'rip', 'isis', 'eigrp', 'static'].map((protocol) => (
                    <label key={protocol} className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={routerProtocols.includes(protocol)}
                        onChange={(e) => {
                          const current = routerProtocols
                          const updated = e.target.checked
                            ? [...current, protocol]
                            : current.filter((p) => p !== protocol)
                          updateProperty('protocols', updated)
                        }}
                        className="rounded border-gray-300 dark:border-gray-600"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300 uppercase">{protocol}</span>
                    </label>
                  ))}
                </div>
              </div>
              <Input
                label="AS Number (for BGP)"
                value={toInputValue(props.as_number)}
                onChange={(e) => updateProperty('as_number', e.target.value)}
                placeholder="65001"
              />
            </div>
          ),
        },
        dockerTab,
      ]
    }

    if (deviceType === 'ap') {
      return [
        {
          id: 'general',
          label: t('common.general', 'General'),
          content: <div className="space-y-4">{labelField}</div>,
        },
        {
          id: 'wireless',
          label: t('topology.wireless', 'Wireless'),
          content: (
            <div className="space-y-4">
              <Input
                label="SSID"
                value={toInputValue(props.ssid)}
                onChange={(e) => updateProperty('ssid', e.target.value)}
                placeholder="MyNetwork"
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.wifiMode', 'WiFi Mode')}
                </label>
                <select
                  value={toInputValue(props.mode) || 'g'}
                  onChange={(e) => updateProperty('mode', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                >
                  <option value="a">802.11a (5 GHz)</option>
                  <option value="b">802.11b (2.4 GHz)</option>
                  <option value="g">802.11g (2.4 GHz)</option>
                  <option value="n">802.11n (2.4/5 GHz)</option>
                  <option value="ac">802.11ac (5 GHz)</option>
                  <option value="ax">802.11ax (WiFi 6)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.channel', 'Channel')}
                </label>
                <input
                  type="number"
                  min={1}
                  max={165}
                  value={toInputValue(props.channel)}
                  onChange={(e) => updateProperty('channel', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  placeholder="6"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.security', 'Security')}
                </label>
                <select
                  value={toInputValue(props.security) || 'wpa2'}
                  onChange={(e) => updateProperty('security', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                >
                  <option value="open">Open (No Security)</option>
                  <option value="wpa">WPA</option>
                  <option value="wpa2">WPA2</option>
                  <option value="wpa3">WPA3</option>
                </select>
              </div>
              {toInputValue(props.security) !== 'open' && (
                <Input
                  label={t('topology.password', 'Password')}
                  type="password"
                  value={toInputValue(props.password)}
                  onChange={(e) => updateProperty('password', e.target.value)}
                  placeholder="Enter WiFi password"
                />
              )}
            </div>
          ),
        },
        {
          id: 'network',
          label: t('common.network', 'Network'),
          content: (
            <div className="space-y-4">
              <Input
                label={t('topology.ipAddress', 'IP Address')}
                value={toInputValue(props.ip)}
                onChange={(e) => updateProperty('ip', e.target.value)}
                placeholder="192.168.1.1/24"
              />
            </div>
          ),
        },
        dockerTab,
      ]
    }

    if (deviceType === 'station') {
      return [
        {
          id: 'general',
          label: t('common.general', 'General'),
          content: <div className="space-y-4">{labelField}</div>,
        },
        {
          id: 'wireless',
          label: t('topology.wireless', 'Wireless'),
          content: (
            <div className="space-y-4">
              <Input
                label="Connect to SSID"
                value={toInputValue(props.ssid)}
                onChange={(e) => updateProperty('ssid', e.target.value)}
                placeholder="MyNetwork"
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.wifiMode', 'WiFi Mode')}
                </label>
                <select
                  value={toInputValue(props.mode) || 'g'}
                  onChange={(e) => updateProperty('mode', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                >
                  <option value="a">802.11a</option>
                  <option value="b">802.11b</option>
                  <option value="g">802.11g</option>
                  <option value="n">802.11n</option>
                  <option value="ac">802.11ac</option>
                  <option value="ax">802.11ax</option>
                </select>
              </div>
              <Input
                label={t('topology.password', 'Password')}
                type="password"
                value={toInputValue(props.password)}
                onChange={(e) => updateProperty('password', e.target.value)}
                placeholder="Enter password"
              />
              <Input
                label="IP Address (DHCP if empty)"
                value={toInputValue(props.ip)}
                onChange={(e) => updateProperty('ip', e.target.value)}
                placeholder="DHCP or 10.0.0.5"
              />
            </div>
          ),
        },
        {
          id: 'mobility',
          label: t('topology.mobility', 'Mobility'),
          content: (
            <div className="space-y-4">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={asBoolean(props.mobility_enabled)}
                  onChange={(e) => updateProperty('mobility_enabled', e.target.checked)}
                  className="rounded border-gray-300 dark:border-gray-600"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {t('topology.enableMobility', 'Enable Mobility')}
                </span>
              </label>
              <Input
                label="Movement Speed (m/s)"
                value={toInputValue(props.mobility_speed)}
                onChange={(e) => updateProperty('mobility_speed', e.target.value)}
                placeholder="1.5"
              />
              <Input
                label="Movement Pattern"
                value={toInputValue(props.mobility_pattern)}
                onChange={(e) => updateProperty('mobility_pattern', e.target.value)}
                placeholder="random, grid, replay"
              />
            </div>
          ),
        },
        dockerTab,
      ]
    }

    // Removed 'container' device type - use dockerized property on other device types instead

    if (deviceType === 'controller') {
      return [
        {
          id: 'general',
          label: t('common.general', 'General'),
          content: (
            <div className="space-y-4">
              {labelField}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.controllerType', 'Controller Type')}
                </label>
                <select
                  value={toInputValue(props.controller_type) || 'osken'}
                  onChange={(e) => updateProperty('controller_type', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                >
                  <option value="osken">Osken</option>
                  <option value="ryu">Ryu</option>
                  <option value="opendaylight">OpenDaylight</option>
                  <option value="onos">ONOS</option>
                  <option value="pox">POX</option>
                  <option value="floodlight">Floodlight</option>
                  <option value="custom">Custom</option>
                </select>
              </div>
              <Input
                label={t('topology.ipAddress', 'IP Address')}
                value={toInputValue(props.ip)}
                onChange={(e) => updateProperty('ip', e.target.value)}
                placeholder="127.0.0.1"
              />
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  {t('topology.port', 'Port')}
                </label>
                <input
                  type="number"
                  value={toInputValue(props.port)}
                  onChange={(e) => updateProperty('port', e.target.value)}
                  className="input w-full px-4 py-2 rounded-xl border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800"
                  placeholder="6653"
                />
              </div>
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={asBoolean(props.auto_start)}
                  onChange={(e) => updateProperty('auto_start', e.target.checked)}
                  className="rounded border-gray-300 dark:border-gray-600"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {t('topology.autoStart', 'Auto-start with topology')}
                </span>
              </label>
            </div>
          ),
        },
        dockerTab,
      ]
    }

    // Default fallback for unknown device types
    return [
      {
        id: 'general',
        label: t('common.general', 'General'),
        content: <div className="space-y-4">{labelField}</div>,
      },
      dockerTab,
    ]
  }, [
    applyP4ProgramToNode,
    deviceType,
    node.data.label,
    onUpdate,
    p4Error,
    p4Loading,
    p4Programs,
    props,
    refreshP4Programs,
    t,
    updateProperty,
  ])

  useEffect(() => {
    if (!tabs.length) {
      setActiveTab('general')
      return
    }
    if (!tabs.some((tab) => tab.id === activeTab)) {
      setActiveTab(tabs[0].id)
    }
  }, [deviceType, node.id, tabs])

  const activeTabContent =
    tabs.find((tab) => tab.id === activeTab)?.content ?? (
      <div className="text-sm text-gray-500 dark:text-gray-400">
        {t('topology.noConfiguration', 'No configuration available for this device type.')}
      </div>
    )

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center justify-between">
          <span>{t('topology.properties')}</span>
          <span className="text-xs font-normal px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-full uppercase">
            {deviceType || 'device'}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2 border-b border-gray-200 dark:border-gray-700 pb-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 text-sm font-medium rounded-full transition-colors ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="pt-2 space-y-4">{activeTabContent}</div>

        <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
          <Button
            variant="danger"
            fullWidth
            leftIcon={<Trash2 size={16} />}
            onClick={onDelete}
          >
            {t('topology.deleteNode')}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
