import toast from 'react-hot-toast'
import { ChartBarIcon, Cog6ToothIcon, CommandLineIcon, CpuChipIcon, PlayIcon } from '@heroicons/react/24/outline'

import { Badge } from '@/components/atoms/Badge'
import { Button } from '@/components/atoms/Button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/atoms/Card'
import { Input } from '@/components/atoms/Input'
import { MetricCard } from '@/components/molecules/MetricCard'
import WebShell from '@/components/WebShell'

type ControllerPane = 'overview' | 'terminal' | 'quick' | 'ui'

type ControllersTabProps = {
  controllersList: any[]
  controllersSummary: { total: number; running: number; healthy: number; withUi: number; withCreds: number }
  controllerSearch: string
  setControllerSearch: (value: string) => void
  setControllerConsole: (value: string[]) => void
  setControllerOutput: (value: string) => void
  selectedControllerId: string
  setSelectedControllerId: (value: string) => void
  selectedController: any
  controllerUiUrl: string
  controllerPane: ControllerPane
  setControllerPane: (value: ControllerPane) => void
  controllerLifecycleMutation: any
  controllerCommand: string
  setControllerCommand: (value: string) => void
  controllerConsole: string[]
  execControllerMutation: any
}

export default function ControllersTab({
  controllersList,
  controllersSummary,
  controllerSearch,
  setControllerSearch,
  setControllerConsole,
  setControllerOutput,
  selectedControllerId,
  setSelectedControllerId,
  selectedController,
  controllerUiUrl,
  controllerPane,
  setControllerPane,
  controllerLifecycleMutation,
  controllerCommand,
  setControllerCommand,
  controllerConsole,
  execControllerMutation,
}: ControllersTabProps) {
  return (
    <div className="animate-fade-in space-y-6">
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <CardTitle>Controllers</CardTitle>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                UI, credentials, lifecycle actions, and a lightweight terminal.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Input
                value={controllerSearch}
                onChange={(e) => setControllerSearch(e.target.value)}
                placeholder="Search controllers…"
                className="w-full sm:w-72"
              />
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setControllerSearch('')
                  setControllerConsole([])
                  setControllerOutput('')
                }}
              >
                Reset
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {controllersList.length === 0 ? (
            <div className="text-sm text-gray-600 dark:text-gray-300">
              No controllers found for this topology. Use the Container UI tab to deploy/ensure infra and controllers.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
                <MetricCard
                  title="Controllers"
                  value={controllersSummary.total}
                  subtitle="Configured for topology"
                  variant="default"
                  icon={<CpuChipIcon className="w-5 h-5" />}
                />
                <MetricCard
                  title="Running"
                  value={controllersSummary.running}
                  subtitle="Container status"
                  variant={controllersSummary.running ? 'success' : 'warning'}
                  icon={<PlayIcon className="w-5 h-5" />}
                />
                <MetricCard
                  title="Healthy"
                  value={controllersSummary.healthy}
                  subtitle="Healthchecks"
                  variant={controllersSummary.healthy ? 'success' : 'default'}
                  icon={<ChartBarIcon className="w-5 h-5" />}
                />
                <MetricCard
                  title="With UI"
                  value={controllersSummary.withUi}
                  subtitle="Embeddable UI"
                  variant={controllersSummary.withUi ? 'primary' : 'default'}
                  icon={<CommandLineIcon className="w-5 h-5" />}
                />
                <MetricCard
                  title="With Creds"
                  value={controllersSummary.withCreds}
                  subtitle="User/pass available"
                  variant={controllersSummary.withCreds ? 'primary' : 'default'}
                  icon={<Cog6ToothIcon className="w-5 h-5" />}
                />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-[280px_minmax(0,1fr)] gap-4">
                <div className="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden max-h-[680px] overflow-y-auto">
                  {controllersList.map((c: any) => {
                    const isActive = String(c.id) === String(selectedControllerId)
                    const status = String(c.container_status || '').toLowerCase()
                    const badgeVariant =
                      status === 'running' ? 'success' : status === 'exited' || status === 'dead' ? 'warning' : 'default'
                    return (
                      <button
                        key={String(c.id)}
                        onClick={() => setSelectedControllerId(String(c.id))}
                        className={`w-full text-left px-3 py-2 border-b border-gray-100 dark:border-gray-900 transition-colors ${
                          isActive ? 'bg-blue-50 dark:bg-blue-950/30' : 'hover:bg-gray-50 dark:hover:bg-gray-900'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="min-w-0">
                            <div className="font-medium text-gray-900 dark:text-white truncate">{c.node_name || c.id}</div>
                            <div className="text-xs text-gray-600 dark:text-gray-400 truncate">
                              {String(c.controller_type || '').toUpperCase()} · OF {c.openflow_port}
                            </div>
                          </div>
                          <Badge variant={badgeVariant as any} size="sm">
                            {status || 'unknown'}
                          </Badge>
                        </div>
                        <div className="text-[11px] text-gray-500 dark:text-gray-500 font-mono truncate mt-1">
                          {c.container_name}
                        </div>
                      </button>
                    )
                  })}
                </div>

                <div className="space-y-4">
                  {selectedController && (
                    <>
                      <Card>
                        <CardContent className="p-4 sm:p-6 space-y-4">
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                              <div className="text-lg font-semibold text-gray-900 dark:text-white">
                                {selectedController.node_name || selectedControllerId}
                              </div>
                              <div className="text-sm text-gray-600 dark:text-gray-400">
                                {String(selectedController.controller_type || '').toUpperCase()} controller · OpenFlow{' '}
                                <span className="font-mono">{selectedController.openflow_port}</span>
                              </div>
                            </div>
                            <div className="flex flex-wrap items-center gap-2">
                              {controllerUiUrl && (
                                <Button onClick={() => window.open(controllerUiUrl, '_blank', 'noopener,noreferrer')}>Open UI</Button>
                              )}
                              <Button
                                variant="secondary"
                                onClick={() => controllerLifecycleMutation.mutate('start')}
                                disabled={controllerLifecycleMutation.isPending}
                              >
                                Start
                              </Button>
                              <Button
                                variant="secondary"
                                onClick={() => controllerLifecycleMutation.mutate('stop')}
                                disabled={controllerLifecycleMutation.isPending}
                              >
                                Stop
                              </Button>
                              <Button
                                variant="secondary"
                                onClick={() => controllerLifecycleMutation.mutate('restart')}
                                disabled={controllerLifecycleMutation.isPending}
                              >
                                Restart
                              </Button>
                            </div>
                          </div>

                          <div className="flex flex-wrap items-center gap-2">
                            <Button
                              size="sm"
                              variant={controllerPane === 'overview' ? 'primary' : 'secondary'}
                              onClick={() => setControllerPane('overview')}
                            >
                              Overview
                            </Button>
                            <Button
                              size="sm"
                              variant={controllerPane === 'terminal' ? 'primary' : 'secondary'}
                              onClick={() => setControllerPane('terminal')}
                            >
                              Terminal
                            </Button>
                            <Button
                              size="sm"
                              variant={controllerPane === 'quick' ? 'primary' : 'secondary'}
                              onClick={() => setControllerPane('quick')}
                            >
                              Quick Cmd
                            </Button>
                            {controllerUiUrl && (
                              <Button
                                size="sm"
                                variant={controllerPane === 'ui' ? 'primary' : 'secondary'}
                                onClick={() => setControllerPane('ui')}
                              >
                                Embedded UI
                              </Button>
                            )}
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-2 text-sm">
                              <div className="flex items-center justify-between gap-3">
                                <span className="text-gray-600 dark:text-gray-400">Container</span>
                                <span className="font-mono text-gray-900 dark:text-white">{selectedController.container_name}</span>
                              </div>
                              <div className="flex items-center justify-between gap-3">
                                <span className="text-gray-600 dark:text-gray-400">Status</span>
                                <Badge
                                  variant={String(selectedController.container_status).toLowerCase() === 'running' ? 'success' : 'default'}
                                  size="sm"
                                >
                                  {String(selectedController.container_status || 'unknown')}
                                </Badge>
                              </div>
                              <div className="flex items-center justify-between gap-3">
                                <span className="text-gray-600 dark:text-gray-400">OpenFlow target</span>
                                <span className="font-mono text-gray-900 dark:text-white">
                                  tcp:{selectedController.container_name}:{selectedController.openflow_port}
                                </span>
                              </div>
                              {selectedController.ui?.host_port && (
                                <div className="flex items-center justify-between gap-3">
                                  <span className="text-gray-600 dark:text-gray-400">UI host port</span>
                                  <span className="font-mono text-gray-900 dark:text-white">{selectedController.ui.host_port}</span>
                                </div>
                              )}
                              {selectedController.credentials?.user && (
                                <div className="flex items-center justify-between gap-3">
                                  <span className="text-gray-600 dark:text-gray-400">Login</span>
                                  <button
                                    className="font-mono text-gray-900 dark:text-white hover:underline"
                                    onClick={() => {
                                      const user = selectedController.credentials.user
                                      const pass = selectedController.credentials.password
                                      const text = `${user}:${pass}`
                                      navigator.clipboard?.writeText(text).then(
                                        () => toast.success('Copied credentials'),
                                        () => toast.error('Failed to copy')
                                      )
                                    }}
                                  >
                                    {selectedController.credentials.user}:{selectedController.credentials.password}
                                  </button>
                                </div>
                              )}
                            </div>

                            <div className="rounded-xl border border-gray-200 dark:border-gray-800 p-4 space-y-3">
                              {controllerPane === 'overview' && (
                                <div className="space-y-3">
                                  <div className="text-sm font-medium text-gray-900 dark:text-white">Shortcuts</div>
                                  <div className="flex flex-wrap gap-2">
                                    <Button size="sm" variant="secondary" onClick={() => setControllerPane('terminal')}>
                                      Open Terminal
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="secondary"
                                      onClick={() => {
                                        setControllerPane('quick')
                                        setControllerCommand('ps aux | head')
                                      }}
                                    >
                                      Health Check
                                    </Button>
                                    {controllerUiUrl && (
                                      <Button size="sm" variant="secondary" onClick={() => setControllerPane('ui')}>
                                        Open Embedded UI
                                      </Button>
                                    )}
                                  </div>
                                  <div className="text-xs text-gray-600 dark:text-gray-400">
                                    Use <span className="font-mono">Quick Cmd</span> for one-off checks, or{' '}
                                    <span className="font-mono">Terminal</span> for an interactive shell inside the controller container.
                                  </div>
                                </div>
                              )}

                              {controllerPane === 'quick' && (
                                <>
                                  <div className="flex flex-wrap gap-2">
                                    {String(selectedController.controller_type || '').toLowerCase() === 'onos' && (
                                      <>
                                        <Button
                                          size="sm"
                                          variant="secondary"
                                          onClick={() =>
                                            setControllerCommand('tail -n 120 /root/onos/apache-karaf-*/data/log/karaf.log || true')
                                          }
                                        >
                                          View Logs
                                        </Button>
                                        <Button size="sm" variant="secondary" onClick={() => setControllerCommand('ls -la /root/onos || true')}>
                                          ONOS Dir
                                        </Button>
                                      </>
                                    )}
                                    <Button size="sm" variant="secondary" onClick={() => setControllerCommand('ps aux | head')}>
                                      ps
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="secondary"
                                      onClick={() => setControllerCommand('netstat -tulpn | head || ss -lntup | head')}
                                    >
                                      Ports
                                    </Button>
                                  </div>

                                  <div className="bg-black dark:bg-gray-950 rounded-xl p-3 font-mono text-xs text-green-400 h-[260px] overflow-y-auto border border-gray-800">
                                    {controllerConsole.length ? (
                                      controllerConsole.map((line, i) => <div key={i}>{line}</div>)
                                    ) : (
                                      <div className="text-green-300/70">Run a command to see output…</div>
                                    )}
                                  </div>

                                  <div className="flex items-center gap-2">
                                    <Input
                                      value={controllerCommand}
                                      onChange={(e) => setControllerCommand(e.target.value)}
                                      placeholder="Enter command…"
                                      className="font-mono"
                                      onKeyDown={(e) => {
                                        if (e.key === 'Enter' && controllerCommand.trim() && !execControllerMutation.isPending) {
                                          execControllerMutation.mutate()
                                        }
                                      }}
                                    />
                                    <Button onClick={() => execControllerMutation.mutate()} disabled={!controllerCommand.trim() || execControllerMutation.isPending}>
                                      Run
                                    </Button>
                                    <Button
                                      variant="secondary"
                                      onClick={() => {
                                        setControllerConsole([])
                                        setControllerOutput('')
                                      }}
                                    >
                                      Clear
                                    </Button>
                                  </div>
                                </>
                              )}

                              {controllerPane !== 'overview' && controllerPane !== 'quick' && (
                                <div className="text-sm text-gray-600 dark:text-gray-400">
                                  Use the buttons above to open the controller terminal or embedded UI.
                                </div>
                              )}
                            </div>
                          </div>

                          {controllerPane === 'terminal' && (
                            <div className="mt-4 border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden h-[560px] bg-gray-950">
                              <WebShell device="container-shell" container={selectedController.container_name} />
                            </div>
                          )}
                        </CardContent>
                      </Card>

                      {controllerUiUrl && controllerPane === 'ui' && (
                        <Card>
                          <CardHeader>
                            <div className="flex items-center justify-between">
                              <CardTitle>Embedded UI</CardTitle>
                              <Badge variant="info" size="sm">
                                If the UI is blank, refresh
                              </Badge>
                            </div>
                          </CardHeader>
                          <CardContent>
                            <div className="h-[600px] border border-gray-200 dark:border-gray-800 rounded-xl overflow-hidden bg-white dark:bg-gray-950">
                              <iframe src={controllerUiUrl} title="controller-ui" className="w-full h-full" />
                            </div>
                          </CardContent>
                        </Card>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

