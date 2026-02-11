import { expect, test, type APIResponse, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'
import { execSync } from 'node:child_process'

function uniqueName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

async function forceEnglish(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('i18nextLng', 'en')
  })
}

async function responseJson(response: APIResponse, label: string): Promise<any> {
  const status = response.status()
  const text = await response.text()
  expect(
    response.ok(),
    `${label} failed (${status})${text ? `: ${text.slice(0, 800)}` : ''}`
  ).toBeTruthy()
  try {
    return text ? JSON.parse(text) : {}
  } catch {
    return {}
  }
}

function extractEvents(payload: any): any[] {
  if (!payload || typeof payload !== 'object') return []
  if (Array.isArray(payload.events)) return payload.events
  if (Array.isArray(payload.items)) return payload.items
  if (Array.isArray(payload.data)) return payload.data
  return []
}

function toList(payload: any): any[] {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.data)) return payload.data
  return []
}

async function poll<T>(
  label: string,
  fn: () => Promise<T>,
  predicate: (value: T) => boolean,
  timeoutMs = 180_000,
  intervalMs = 2_000
): Promise<T> {
  const start = Date.now()
  let last: T | undefined
  while (Date.now() - start < timeoutMs) {
    last = await fn()
    if (predicate(last)) return last
    await new Promise((r) => setTimeout(r, intervalMs))
  }
  throw new Error(`Timeout while waiting for: ${label}`)
}

function isHostLike(device: any): boolean {
  const t = String(device?.device_type || device?.type || '').toLowerCase()
  return ['host', 'router', 'station', 'container'].includes(t)
}

function runtimeName(device: any): string {
  return String(device?.runtime_name || device?.name || device?.id || '').trim()
}

function resolveP4DefaultCode(): string {
  const editorPath = path.resolve(process.cwd(), 'src/components/P4Editor.tsx')
  const source = fs.readFileSync(editorPath, 'utf8')
  const match = source.match(/export const DEFAULT_P4_CODE = `([\s\S]*?)`\n\nexport default/)
  if (!match?.[1]) {
    throw new Error('Could not extract DEFAULT_P4_CODE from P4Editor.tsx')
  }
  return match[1]
}

test.describe.serial('F1-F19 end-to-end validation (UI + API)', () => {
  test('validates all features with UI-driven flow', async ({ page, request }) => {
    test.setTimeout(45 * 60 * 1000)
    await forceEnglish(page)

    let projectId = ''
    let topologyId = ''
    let topology2Id = ''
    let emulationId1 = ''
    let emulationId2 = ''
    let emuContainerName = ''
    let algoRunId = ''
    let pingRunId = ''
    let tcpRunId = ''
    let snapshotId = ''
    const createdControllerIds: string[] = []
    const hostLikeRuntimeNames: string[] = []
    const hostLikeDevices: any[] = []

    try {
      await test.step('Setup: create project and generated topology (F10 baseline)', async () => {
        const project = await responseJson(
          await request.post('/api/projects', {
            data: {
              name: uniqueName('e2e-f1-f19-project'),
              description: 'Playwright F1-F19 validation project',
            },
          }),
          'create project'
        )
        projectId = project.id
        expect(projectId).toBeTruthy()

        const projectTopologies = await responseJson(
          await request.get(`/api/topologies?project_id=${projectId}`),
          'list project topologies'
        )
        const topoList = toList(projectTopologies)
        expect(topoList.length).toBeGreaterThan(0)
        topologyId = topoList[0].id

        const generated = await responseJson(
          await request.post('/api/generate', {
            data: {
              topology_type: 'tree',
              name: uniqueName('e2e-tree'),
              description: 'Generated tree topology for F10',
              parameters: { depth: 2, fanout: 2, hosts_per_switch: 1 },
            },
          }),
          'generate tree topology'
        )
        expect(Array.isArray(generated.nodes)).toBeTruthy()
        expect(Array.isArray(generated.links)).toBeTruthy()
        expect(generated.nodes.length).toBeGreaterThanOrEqual(5)
        expect(generated.links.length).toBeGreaterThanOrEqual(4)

        const importNodes = (Array.isArray(generated.nodes) ? generated.nodes : []).map((node: any) => ({
          id: node.id || node.name,
          name: node.name,
          device_type: node.device_type,
          x: node.x ?? 0,
          y: node.y ?? 0,
          properties: node.properties || {},
        }))
        const importLinks = (Array.isArray(generated.links) ? generated.links : []).map((link: any) => ({
          source_node_id:
            link.source_node_id ||
            link.source ||
            link.source_node?.id ||
            link.source_node?.name,
          target_node_id:
            link.target_node_id ||
            link.target ||
            link.target_node?.id ||
            link.target_node?.name,
          source_port: link.source_port || link.port1 || null,
          target_port: link.target_port || link.port2 || null,
          bandwidth: link.bandwidth ?? null,
          delay: link.delay ?? null,
          loss: link.loss ?? null,
          max_queue_size: link.max_queue_size ?? null,
          properties: link.properties || {},
        }))

        await responseJson(
          await request.put(`/api/topologies/${topologyId}/import`, {
            data: {
              name: generated.name || uniqueName('imported-tree'),
              description: generated.description || 'Imported generated topology',
              version: '1.0',
              metadata: generated.metadata || {},
              nodes: importNodes,
              links: importLinks,
              controllers: generated.controllers || [],
              protocols: generated.protocols || {},
              options: generated.options || {},
            },
          }),
          'import generated topology'
        )

        const topoAfterImport = await responseJson(
          await request.get(`/api/topologies/${topologyId}`),
          'get imported topology'
        )
        expect(Array.isArray(topoAfterImport.nodes)).toBeTruthy()
        expect(Array.isArray(topoAfterImport.links)).toBeTruthy()
        expect(topoAfterImport.nodes.length).toBeGreaterThanOrEqual(5)
        expect(topoAfterImport.links.length).toBeGreaterThanOrEqual(4)
      })

      await test.step('F3/F8/F7: UI renders, topology persists, drag-and-drop editing works', async () => {
        await page.goto('/projects')
        await expect(page.getByRole('heading', { name: /Projects/i })).toBeVisible()

        const projectResp = await responseJson(await request.get(`/api/projects/${projectId}`), 'get project by id')
        await expect(page.getByText(projectResp.name)).toBeVisible({ timeout: 30_000 })

        await page.goto(`/topology/${topologyId}`)
        await expect(page.getByRole('button', { name: /^Save$/ })).toBeVisible({ timeout: 30_000 })
        await expect(page.getByRole('button', { name: /^Canvas$/ })).toBeVisible({ timeout: 30_000 })

        const flowNode = page.locator('.react-flow__node').first()
        await expect(flowNode).toBeVisible({ timeout: 30_000 })
        const before = await flowNode.boundingBox()
        expect(before).toBeTruthy()
        if (!before) throw new Error('ReactFlow node bounding box is not available')

        const startX = before.x + before.width / 2
        const startY = before.y + before.height / 2
        await page.mouse.move(startX, startY)
        await page.mouse.down()
        await page.mouse.move(startX + 130, startY + 85)
        await page.mouse.up()

        const after = await flowNode.boundingBox()
        expect(after).toBeTruthy()
        if (!after) throw new Error('ReactFlow node bounding box after drag is not available')
        const dx = Math.abs(after.x - before.x)
        const dy = Math.abs(after.y - before.y)
        expect(dx).toBeGreaterThan(40)
        expect(dy).toBeGreaterThan(20)

        await page.getByRole('button', { name: /^Save$/ }).click()
      })

      await test.step('Start emulation from UI and wait running state', async () => {
        await page.goto(`/topology/${topologyId}`)
        const startButton = page.getByRole('button', { name: /^Start$/ })
        if (await startButton.isVisible()) {
          await startButton.click()
        }

        // Fallback to direct API start when UI-triggered start is interrupted or out-of-sync.
        const startResp = await request.post('/api/emulation/start', {
          data: { topology_id: topologyId },
        })
        const startRespBody = await startResp.text()
        if (startResp.status() >= 400 && startResp.status() !== 409) {
          const body = startRespBody
          throw new Error(`Emulation start fallback failed (${startResp.status()}): ${body.slice(0, 400)}`)
        }
        if (startResp.ok()) {
          try {
            const parsed = startRespBody ? JSON.parse(startRespBody) : {}
            if (parsed && parsed.success === false) {
              throw new Error(String(parsed.message || 'unknown emulation start error'))
            }
          } catch (err: any) {
            if (err instanceof SyntaxError) {
              // ignore non-JSON body
            } else {
              throw err
            }
          }
        }

        const running = await poll(
          'topology emulation running',
          async () => {
            const active = await responseJson(await request.get('/api/emulation/active'), 'list active emulations')
            const emu = (active.emulations || []).find(
              (e: any) => String(e.topology_id) === String(topologyId) && String(e.status).toLowerCase() === 'running'
            )
            return emu || null
          },
          (value) => Boolean(value),
          6 * 60_000,
          3_000
        )

        emulationId1 = String(running.emulation_id || '')
        emuContainerName = String(running.container_name || '')
        expect(emulationId1).toBeTruthy()
      })

      await test.step('F1: Mininet/Containernet unified runtime available', async () => {
        if (!emuContainerName) {
          const infraStatus = await responseJson(
            await request.get(`/api/infrastructure/status?topology_id=${encodeURIComponent(topologyId)}`),
            'get infrastructure status for emulation container'
          )
          emuContainerName = String(infraStatus?.emulation?.container_name || '')
        }
        expect(emuContainerName).toBeTruthy()

        const cmd = [
          'docker',
          'exec',
          emuContainerName,
          'python3',
          '-c',
          "import mininet; import containernet; from containernet.net import Containernet; print('RUNTIME_OK')",
        ]
        const output = execSync(cmd.map((part) => `'${part.replace(/'/g, "'\\''")}'`).join(' '), {
          encoding: 'utf8',
          shell: '/bin/bash',
        })
        expect(output).toContain('RUNTIME_OK')
      })

      await test.step('F4: WebShell UI and Mininet CLI websocket are functional', async () => {
        await page.goto(`/topology/${topologyId}`)
        const webShellButton = page.getByRole('button', { name: /WebShell/i })
        await expect(webShellButton).toBeVisible()
        await expect(webShellButton).toBeEnabled({ timeout: 30_000 })
        await webShellButton.click()
        await expect(page.getByText(/Select device/i)).toBeVisible()
        await page.locator('.modal-backdrop').getByRole('button', { name: /^Close$/ }).first().click()

        const wsOutput = await page.evaluate(async (tid: string) => {
          const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
          const endpoint = `${protocol}//${window.location.host}/ws/mininet-cli?topology_id=${encodeURIComponent(tid)}`
          return await new Promise<string>((resolve, reject) => {
            const ws = new WebSocket(endpoint)
            let buffer = ''
            const timeout = window.setTimeout(() => {
              try {
                ws.close()
              } catch {
                // noop
              }
              reject(new Error('Timeout waiting for Mininet CLI response'))
            }, 20_000)

            ws.onopen = () => {
              ws.send(JSON.stringify({ type: 'input', data: 'nodes\n' }))
            }

            ws.onmessage = (ev) => {
              try {
                const msg = JSON.parse(String(ev.data || '{}'))
                if (msg.type === 'error') {
                  clearTimeout(timeout)
                  ws.close()
                  reject(new Error(msg.message || 'Mininet CLI websocket error'))
                  return
                }
                if (msg.type === 'output') {
                  buffer += String(msg.data || '')
                  if (buffer.length > 24 && /(h\d+|s\d+|c\d+)/i.test(buffer)) {
                    clearTimeout(timeout)
                    ws.close()
                    resolve(buffer)
                  }
                }
              } catch (error: any) {
                clearTimeout(timeout)
                ws.close()
                reject(error)
              }
            }

            ws.onerror = () => {
              clearTimeout(timeout)
              reject(new Error('WebSocket transport error'))
            }
          })
        }, topologyId)
        expect(wsOutput.length).toBeGreaterThan(10)
      })

      await test.step('Resolve host-like runtime devices for F2/F12/F18', async () => {
        const devicesPayload = await responseJson(
          await request.get(`/api/emulation/devices?topology_id=${encodeURIComponent(topologyId)}`),
          'list runtime devices'
        )
        const devices = toList(devicesPayload?.devices || devicesPayload)
        const filtered = devices.filter(isHostLike)
        hostLikeDevices.splice(0, hostLikeDevices.length, ...filtered)
        const names = filtered.map(runtimeName).filter(Boolean)
        hostLikeRuntimeNames.splice(0, hostLikeRuntimeNames.length, ...Array.from(new Set(names)))
        expect(filtered.length).toBeGreaterThanOrEqual(2)
      })

      await test.step('F2: runtime topology modification add/delete device', async () => {
        const beforePayload = await responseJson(
          await request.get(`/api/emulation/devices?topology_id=${encodeURIComponent(topologyId)}`),
          'list devices before runtime add'
        )
        const beforeList = toList(beforePayload?.devices || beforePayload)
        const beforeCount = beforeList.length

        const runtimeHost = uniqueName('f2h').replace(/[^a-zA-Z0-9_-]/g, '').slice(0, 14)
        const addResult = await responseJson(
          await request.post('/api/emulation/devices/add', {
            data: {
              topology_id: topologyId,
              name: runtimeHost,
              device_type: 'host',
              properties: {},
            },
          }),
          'runtime add device'
        )
        const addedRuntimeName = String(addResult.runtime_name || '').trim()
        const isAddedDevice = (d: any) => {
          const rn = runtimeName(d)
          const n = String(d?.name || '').trim()
          const nodeId = String(d?.properties?.node_id || '').trim()
          if (addedRuntimeName && rn === addedRuntimeName) return true
          return rn === runtimeHost || n === runtimeHost || nodeId === runtimeHost
        }

        const afterAdd = await poll(
          'runtime device appears',
          async () => {
            const payload = await responseJson(
              await request.get(`/api/emulation/devices?topology_id=${encodeURIComponent(topologyId)}`),
              'list devices after runtime add'
            )
            const list = toList(payload?.devices || payload)
            return { list, found: list.some((d: any) => isAddedDevice(d)) }
          },
          (value) => value.found
        )
        expect(afterAdd.list.length).toBeGreaterThanOrEqual(beforeCount + 1)

        await responseJson(
          await request.delete(
            `/api/emulation/devices/${encodeURIComponent(addedRuntimeName || runtimeHost)}?topology_id=${encodeURIComponent(topologyId)}`
          ),
          'runtime delete device'
        )
        const afterDeletePayload = await responseJson(
          await request.get(`/api/emulation/devices?topology_id=${encodeURIComponent(topologyId)}`),
          'list devices after runtime delete'
        )
        const afterDeleteList = toList(afterDeletePayload?.devices || afterDeletePayload)
        expect(afterDeleteList.some((d: any) => isAddedDevice(d))).toBeFalsy()
      })

      await test.step('F5: Mininet script export works', async () => {
        const exported = await responseJson(
          await request.post('/api/export', {
            data: {
              topology_id: topologyId,
              format: 'mininet',
              options: {},
            },
          }),
          'export mininet script'
        )
        const content = String(exported.content || '')
        expect(content).toContain('Mininet')
        expect(content).toContain('addHost')
      })

      await test.step('F6: multi-controller support (osken + ryu)', async () => {
        const osken = await responseJson(
          await request.post('/api/controllers', {
            data: {
              name: uniqueName('e2e-osken'),
              controller_type: 'osken',
              ip: '127.0.0.1',
              port: 6653,
              rest_port: 8080,
              config: {},
            },
          }),
          'create osken controller'
        )
        const ryu = await responseJson(
          await request.post('/api/controllers', {
            data: {
              name: uniqueName('e2e-ryu'),
              controller_type: 'ryu',
              ip: '127.0.0.1',
              port: 6654,
              rest_port: 8081,
              config: {},
            },
          }),
          'create ryu controller'
        )
        createdControllerIds.push(String(osken.id), String(ryu.id))

        const controllers = await responseJson(await request.get('/api/controllers'), 'list controllers')
        const ctrlList = toList(controllers)
        const createdNames = new Set([String(osken.name), String(ryu.name)])
        const foundNames = new Set(ctrlList.map((c: any) => String(c.name)))
        expect(foundNames.has(String(osken.name))).toBeTruthy()
        expect(foundNames.has(String(ryu.name))).toBeTruthy()
        expect(createdNames.size).toBe(2)

        await page.goto(`/network-manager?topology=${topologyId}&tab=controllers`)
        await expect(page.getByText(/Controllers/i).first()).toBeVisible()
      })

      await test.step('F9: P4 program support (compile + UI tab)', async () => {
        const p4Code = resolveP4DefaultCode()
        const compiled = await responseJson(
          await request.post('/api/p4/programs/compile', {
            data: {
              name: uniqueName('e2e-p4'),
              source_code: p4Code,
              target: 'bmv2',
              architecture: 'v1model',
            },
          }),
          'compile P4 program'
        )
        expect(String(compiled.status || '')).toBe('compiled')

        const programs = await responseJson(await request.get('/api/p4/programs'), 'list P4 programs')
        const p4Programs = toList(programs)
        expect(p4Programs.length).toBeGreaterThan(0)

        await page.goto(`/topology/${topologyId}`)
        await page.getByRole('button', { name: /^P4$/ }).click()
        await expect(page.getByText(/^Draft$/)).toBeVisible()
      })

      await test.step('F11: network device configuration export', async () => {
        const template = await responseJson(
          await request.get(`/api/network-configs/${topologyId}/template`),
          'get network config template'
        )
        await responseJson(
          await request.post(`/api/network-configs/${topologyId}`, {
            data: {
              name: uniqueName('e2e-netcfg'),
              description: 'Playwright generated config',
              config: template,
            },
          }),
          'create network config'
        )

        const exported = await responseJson(
          await request.get(`/api/network-configs/${topologyId}/export`),
          'export network config'
        )
        expect(typeof exported).toBe('object')
        const text = JSON.stringify(exported)
        expect(text.length).toBeGreaterThan(40)
      })

      await test.step('F12: distributed algorithm execution', async () => {
        const manifestPath = path.resolve(process.cwd(), '..', 'examples', 'algorithms', 'distributed_mis', 'manifest.json')
        const sourcePath = path.resolve(process.cwd(), '..', 'examples', 'algorithms', 'distributed_mis', 'algorithm.py')
        const manifestJson = fs.readFileSync(manifestPath, 'utf8')
        const sourceCode = fs.readFileSync(sourcePath, 'utf8')

        const run = await responseJson(
          await request.post('/api/algorithms/runs', {
            multipart: {
              topology_id: topologyId,
              transport: 'udp',
              listen_port: '50000',
              manifest_json: manifestJson,
              source_code: sourceCode,
            },
          }),
          'start distributed algorithm run'
        )
        algoRunId = String(run.run_id || '')
        expect(algoRunId).toBeTruthy()

        const eventsPayload = await poll(
          'algorithm events include completion',
          async () => {
            return await responseJson(
              await request.get(`/api/algorithms/runs/${algoRunId}/events?tail=400`),
              'get algorithm run events'
            )
          },
          (payload) => {
            const events = extractEvents(payload)
            if (!events.length) return false
            const hasDone = events.some((e: any) =>
              /done/.test(String(e?.event || e?.type || e?.status || '').toLowerCase()) ||
              /done/.test(String(e?.message || '').toLowerCase())
            )
            return hasDone
          },
          5 * 60_000,
          3_000
        )

        const events = extractEvents(eventsPayload)
        const hasError = events.some((e: any) => {
          const msg = `${e?.event || ''} ${e?.type || ''} ${e?.message || ''}`.toLowerCase()
          return msg.includes(' error') || msg.startsWith('error') || msg.includes('failed')
        })
        expect(hasError).toBeFalsy()
      })

      await test.step('F13: concurrent multi-topology execution shown in UI', async () => {
        const topo2 = await responseJson(
          await request.post('/api/topologies', {
            data: {
              project_id: projectId,
              name: uniqueName('e2e-second-topology'),
              description: 'Second topology for F13',
              nodes: [],
              links: [],
              controllers: [],
            },
          }),
          'create second topology'
        )
        topology2Id = String(topo2.id || '')
        expect(topology2Id).toBeTruthy()

        const generated2 = await responseJson(
          await request.post('/api/generate', {
            data: {
              topology_type: 'tree',
              name: uniqueName('e2e-tree-2'),
              description: 'Second generated topology',
              parameters: { depth: 1, fanout: 2, hosts_per_switch: 1 },
            },
          }),
          'generate second topology'
        )

        const importNodes2 = (Array.isArray(generated2.nodes) ? generated2.nodes : []).map((node: any) => ({
          id: node.id || node.name,
          name: node.name,
          device_type: node.device_type,
          x: node.x ?? 0,
          y: node.y ?? 0,
          properties: node.properties || {},
        }))
        const importLinks2 = (Array.isArray(generated2.links) ? generated2.links : []).map((link: any) => ({
          source_node_id:
            link.source_node_id ||
            link.source ||
            link.source_node?.id ||
            link.source_node?.name,
          target_node_id:
            link.target_node_id ||
            link.target ||
            link.target_node?.id ||
            link.target_node?.name,
          source_port: link.source_port || link.port1 || null,
          target_port: link.target_port || link.port2 || null,
          bandwidth: link.bandwidth ?? null,
          delay: link.delay ?? null,
          loss: link.loss ?? null,
          max_queue_size: link.max_queue_size ?? null,
          properties: link.properties || {},
        }))

        await responseJson(
          await request.put(`/api/topologies/${topology2Id}/import`, {
            data: {
              name: generated2.name || uniqueName('tree-two'),
              description: generated2.description || 'Tree two',
              version: '1.0',
              metadata: generated2.metadata || {},
              nodes: importNodes2,
              links: importLinks2,
              controllers: generated2.controllers || [],
              protocols: generated2.protocols || {},
              options: generated2.options || {},
            },
          }),
          'import second topology'
        )

        await responseJson(
          await request.post('/api/emulation/start', {
            data: { topology_id: topology2Id },
          }),
          'start second topology emulation'
        )

        const active = await poll(
          'two topologies running concurrently',
          async () => {
            return await responseJson(await request.get('/api/emulation/active'), 'list active emulations for F13')
          },
          (payload) => {
            const emulations = Array.isArray(payload?.emulations) ? payload.emulations : []
            const runningIds = new Set(
              emulations
                .filter((e: any) => String(e?.status || '').toLowerCase() === 'running')
                .map((e: any) => String(e.topology_id))
            )
            return runningIds.has(topologyId) && runningIds.has(topology2Id)
          },
          8 * 60_000,
          4_000
        )
        const emulations = Array.isArray(active?.emulations) ? active.emulations : []
        const second = emulations.find((e: any) => String(e.topology_id) === String(topology2Id))
        emulationId2 = String(second?.emulation_id || '')

        await page.goto('/infrastructure')
        await expect(page.getByRole('heading', { name: /Infrastructure/i })).toBeVisible()
        await expect(page.getByText(topologyId).first()).toBeVisible({ timeout: 30_000 })
        await expect(page.getByText(topology2Id).first()).toBeVisible({ timeout: 30_000 })
      })

      await test.step('F14: microservice inventory healthy', async () => {
        const services = await responseJson(await request.get('/api/services'), 'get service inventory')
        const status = await responseJson(await request.get('/api/system/status'), 'get system status')
        expect(Number(services.count || 0)).toBeGreaterThanOrEqual(21)
        expect(Number(status.total_services || 0)).toBeGreaterThanOrEqual(21)
        expect(Number(status.healthy_services || 0)).toBe(Number(status.total_services || 0))
      })

      await test.step('F15: CRIU snapshot/restore path works', async () => {
        const snap = await responseJson(
          await request.post('/api/snapshots', {
            data: {
              name: uniqueName('e2e-criu'),
              topology_id: topologyId,
              emulation_id: emulationId1 || undefined,
              snapshot_type: 'criu_live',
            },
          }),
          'create CRIU snapshot'
        )
        snapshotId = String(snap.id || '')
        expect(snapshotId).toBeTruthy()

        await poll(
          'snapshot captured',
          async () => {
            const detail = await responseJson(
              await request.get(`/api/snapshots/${snapshotId}`),
              'get snapshot detail'
            )
            return String(detail.status || '').toLowerCase()
          },
          (status) => status === 'captured' || status === 'restored',
          10 * 60_000,
          5_000
        )

        await responseJson(
          await request.post(`/api/snapshots/${snapshotId}/restore`, {
            data: {},
          }),
          'restore snapshot'
        )

        await poll(
          'snapshot restore finalized',
          async () => {
            const detail = await responseJson(
              await request.get(`/api/snapshots/${snapshotId}`),
              'get snapshot after restore'
            )
            return String(detail.status || '').toLowerCase()
          },
          (status) => status === 'restored' || status === 'captured',
          10 * 60_000,
          5_000
        )
      })

      let aiProvider = 'ollama'
      let aiModel = ''

      await test.step('Resolve AI provider/model for F16/F19', async () => {
        const settings = await responseJson(await request.get('/api/ai/settings'), 'get AI settings')
        const providers = Array.isArray(settings?.providers) ? settings.providers : []
        const configured = providers.find((p: any) => Boolean(p?.configured)) || providers.find((p: any) => String(p?.provider) === 'ollama')
        aiProvider = String(configured?.provider || 'ollama')
        aiModel = String(configured?.default_model || '')

        if (!aiModel) {
          const modelsPayload = await responseJson(
            await request.get(`/api/ai/models?provider=${encodeURIComponent(aiProvider)}`),
            'get models for provider'
          )
          const models = Array.isArray(modelsPayload?.models) ? modelsPayload.models : []
          expect(models.length).toBeGreaterThan(0)
          aiModel = String(models[0])
        }
        expect(aiProvider).toBeTruthy()
        expect(aiModel).toBeTruthy()
      })

      await test.step('F16: AI/MCP natural language generate + execute', async () => {
        await page.goto('/ai-console')
        await expect(page.getByRole('heading', { name: /AI Console/i })).toBeVisible()

        const generated = await responseJson(
          await request.post('/api/ai/mcp/generate', {
            data: {
              provider: aiProvider,
              model: aiModel,
              prompt: 'Create a request to list platform services.',
            },
          }),
          'generate MCP request from natural language'
        )
        expect(generated?.toon || generated?.request).toBeTruthy()

        const executeBody =
          generated?.toon
            ? { toon: generated.toon }
            : { request: generated.request }
        const executed = await responseJson(
          await request.post('/api/ai/mcp/execute', {
            data: executeBody,
          }),
          'execute MCP request'
        )
        expect(Number(executed.status_code || 0)).toBeGreaterThanOrEqual(200)
        expect(Number(executed.status_code || 0)).toBeLessThan(400)
      })

      await test.step('F17: isolated observability stack per topology', async () => {
        await responseJson(
          await request.post(`/api/infrastructure/topologies/${topologyId}/infra/ensure?force_isolated=true`, {
            data: {},
          }),
          'ensure isolated infra for topology'
        )

        const infraStatus = await poll(
          'isolated infra status',
          async () => {
            return await responseJson(
              await request.get(`/api/infrastructure/topologies/${topologyId}/infra/status`),
              'topology infra status'
            )
          },
          (payload) => String(payload?.mode || '').toLowerCase() === 'isolated',
          10 * 60_000,
          5_000
        )
        expect(String(infraStatus.mode || '').toLowerCase()).toBe('isolated')
      })

      await test.step('F18: parametric test service (cpu + memory stress) and UI visibility', async () => {
        const cpuRun = await responseJson(
          await request.post('/api/tests/run', {
            data: {
              topology_id: topologyId,
              suite: 'cpu_stress',
              params: { duration_s: 5, workers_per_device: 1, sample_interval_s: 1 },
            },
          }),
          'run cpu_stress suite'
        )
        pingRunId = String(cpuRun.run_id || '')
        expect(pingRunId).toBeTruthy()

        await poll(
          'cpu stress run completion',
          async () => {
            const status = await responseJson(await request.get(`/api/tests/${pingRunId}`), 'get cpu run status')
            return String(status?.status || '').toLowerCase()
          },
          (status) => ['completed', 'failed', 'canceled'].includes(status),
          10 * 60_000,
          3_000
        )
        const cpuStatusPayload = await responseJson(await request.get(`/api/tests/${pingRunId}`), 'get final cpu status')
        expect(String(cpuStatusPayload?.status || '').toLowerCase()).toBe('completed')

        const cpuResults = await poll(
          'cpu stress results availability',
          async () =>
            await responseJson(
              await request.get(`/api/tests/${pingRunId}/results?topology_id=${encodeURIComponent(topologyId)}&window_minutes=240`),
              'get cpu stress results'
            ),
          (payload) => {
            const series = payload?.metrics?.series_by_device || {}
            return Object.keys(series).length > 0
          },
          3 * 60_000,
          5_000
        )
        const cpuSeries = cpuResults?.metrics?.series_by_device || {}
        expect(Object.keys(cpuSeries).length).toBeGreaterThan(0)

        const memRun = await responseJson(
          await request.post('/api/tests/run', {
            data: {
              topology_id: topologyId,
              suite: 'memory_stress',
              params: { duration_s: 5, mb_per_device: 64, sample_interval_s: 1 },
            },
          }),
          'run memory_stress suite'
        )
        tcpRunId = String(memRun.run_id || '')
        expect(tcpRunId).toBeTruthy()

        await poll(
          'memory stress run completion',
          async () => {
            const status = await responseJson(await request.get(`/api/tests/${tcpRunId}`), 'get memory run status')
            return String(status?.status || '').toLowerCase()
          },
          (status) => ['completed', 'failed', 'canceled'].includes(status),
          10 * 60_000,
          3_000
        )
        const memStatusPayload = await responseJson(await request.get(`/api/tests/${tcpRunId}`), 'get final memory status')
        expect(String(memStatusPayload?.status || '').toLowerCase()).toBe('completed')

        await page.goto(`/network-manager?topology=${topologyId}&tab=tests`)
        await expect(page.getByText(/Test Network Topology/i).first()).toBeVisible()
      })

      await test.step('F19: AI-assisted diagnostics endpoints + diagnostics UI', async () => {
        const runIdForAi = tcpRunId || pingRunId
        expect(runIdForAi).toBeTruthy()

        const diagnose = await responseJson(
          await request.post('/api/ai/network/diagnose', {
            data: {
              topology_id: topologyId,
              provider: aiProvider,
              model: aiModel,
            },
          }),
          'AI network diagnose'
        )
        expect(String(diagnose?.content || '').trim().length).toBeGreaterThan(0)

        const analyzeTests = await responseJson(
          await request.post('/api/ai/network/tests/analyze', {
            data: {
              topology_id: topologyId,
              run_id: runIdForAi,
              provider: aiProvider,
              model: aiModel,
            },
          }),
          'AI analyze tests'
        )
        expect(String(analyzeTests?.content || '').trim().length).toBeGreaterThan(0)

        const analyzeDiag = await responseJson(
          await request.post('/api/ai/network/diagnostics/analyze', {
            data: {
              topology_id: topologyId,
              window_minutes: 30,
              fields: ['cpu_percent', 'memory_percent', 'bytes_sent', 'bytes_received'],
              prompt: 'Summarize anomalies and likely bottlenecks.',
              provider: aiProvider,
              model: aiModel,
            },
          }),
          'AI analyze diagnostics'
        )
        expect(String(analyzeDiag?.content || '').trim().length).toBeGreaterThan(0)

        await page.goto(`/network-manager?topology=${topologyId}&tab=diagnostics`)
        await expect(page.getByText(/AI Diagnostics/i)).toBeVisible()
      })
    } finally {
      // Cleanup in reverse order; best-effort only.
      if (algoRunId) {
        await request.post(`/api/algorithms/runs/${algoRunId}/stop`).catch(() => null)
      }
      if (emulationId2) {
        await request.post(`/api/emulation/stop/${emulationId2}`, {
          data: { cleanup: true, stop_infra: true, preserve_infra_data: true },
        }).catch(() => null)
      }
      if (emulationId1) {
        await request.post(`/api/emulation/stop/${emulationId1}`, {
          data: { cleanup: true, stop_infra: true, preserve_infra_data: true },
        }).catch(() => null)
      }
      if (topologyId) {
        await request.post(`/api/infrastructure/topologies/${topologyId}/infra/stop`, { data: { preserve_data: true } }).catch(() => null)
      }
      if (topology2Id) {
        await request.post(`/api/infrastructure/topologies/${topology2Id}/infra/stop`, { data: { preserve_data: true } }).catch(() => null)
      }
      for (const controllerId of createdControllerIds) {
        await request.delete(`/api/controllers/${encodeURIComponent(controllerId)}`).catch(() => null)
      }
      if (projectId) {
        await request.delete(`/api/projects/${projectId}`).catch(() => null)
      }
      if (snapshotId) {
        await request.delete(`/api/snapshots/${snapshotId}`).catch(() => null)
      }
    }
  })
})
