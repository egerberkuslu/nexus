import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

function makeProjectName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`
}

async function forceEnglish(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem('i18nextLng', 'en')
  })
}

test.describe('UI + API smoke', () => {
  test.beforeEach(async ({ page }) => {
    await forceEnglish(page)
  })

  test('gateway health and service inventory are reachable', async ({ request }) => {
    const statusResp = await request.get('/api/system/status')
    expect(statusResp.ok()).toBeTruthy()
    const status = await statusResp.json()

    expect(typeof status.total_services).toBe('number')
    expect(status.total_services).toBeGreaterThanOrEqual(20)
    expect(status.healthy_services).toBe(status.total_services)

    const servicesResp = await request.get('/api/services')
    expect(servicesResp.ok()).toBeTruthy()
    const services = await servicesResp.json()
    expect(services.count).toBeGreaterThanOrEqual(20)
  })

  test('home + projects page render with backend data', async ({ page, request }) => {
    const projectName = makeProjectName('e2e-visible')

    const createResp = await request.post('/api/projects', {
      data: {
        name: projectName,
        description: 'playwright visibility smoke project',
      },
    })
    expect(createResp.ok()).toBeTruthy()
    const project = await createResp.json()

    try {
      await page.goto('/')
      await expect(page.getByText(/NEXUS/i).first()).toBeVisible()

      await page.goto('/projects')
      await expect(page.getByRole('heading', { name: /Projects/i })).toBeVisible()
      await expect(page.getByText(projectName)).toBeVisible({ timeout: 20_000 })
    } finally {
      await request.delete(`/api/projects/${project.id}`)
    }
  })

  test('project create from UI persists through API and topology page opens', async ({ page, request }) => {
    const projectName = makeProjectName('e2e-ui-create')
    const projectDescription = 'project created by playwright smoke test'
    let createdProjectId: string | null = null

    try {
      await page.goto('/projects')
      await expect(page.getByRole('heading', { name: /Projects/i })).toBeVisible()

      await page.getByRole('button', { name: /Create New Project/i }).first().click()
      await page.getByPlaceholder(/Enter project name/i).fill(projectName)
      await page.getByPlaceholder(/Enter project description/i).fill(projectDescription)
      await page.getByRole('button', { name: /^Create$/ }).click()

      await expect(page.getByText(projectName)).toBeVisible({ timeout: 20_000 })

      const listResp = await request.get('/api/projects')
      expect(listResp.ok()).toBeTruthy()
      const projects = await listResp.json()
      const created = (projects as Array<{ id: string; name: string }>).find((p) => p.name === projectName)
      expect(created).toBeTruthy()
      createdProjectId = created!.id

      const topologiesResp = await request.get(`/api/topologies?project_id=${createdProjectId}`)
      expect(topologiesResp.ok()).toBeTruthy()
      const topologies = await topologiesResp.json()
      const topologyId = (topologies as Array<{ id: string }>)[0]?.id
      expect(topologyId).toBeTruthy()

      await page.goto(`/topology/${topologyId}`)

      await expect(page).toHaveURL(/\/topology\/.+/)
      await expect(page.getByRole('button', { name: /^Save$/ })).toBeVisible({ timeout: 20_000 })
      await expect(page.getByRole('button', { name: /^Canvas$/ })).toBeVisible({ timeout: 20_000 })
    } finally {
      if (createdProjectId) {
        await request.delete(`/api/projects/${createdProjectId}`)
      }
    }
  })
})
