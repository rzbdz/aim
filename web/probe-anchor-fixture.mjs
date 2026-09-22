import { chromium } from 'playwright'
const STATE = {
  digest: 'anchors-fixture', generated_at: '2026-09-22T00:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog','done'], terminal: ['done'], phase: 'CROSS_EXAMINE',
  milestones: {}, agents: { human: { kind: 'human', model: '' } }, register: {}, tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] }, channels: [], unacked: [], drift: [],
  withheld_tasks: 0, write: { enabled: false, as: '' },
}
const browser = await chromium.launch()

const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
page.on('console', (m) => { if (m.text().includes('[probe]')) console.log('   ', m.text()) })
await page.route('**/api/state**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify(STATE) }))
await page.route('**/api/digest**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }) }))
await page.goto('http://127.0.0.1:8777/#/kanban')
await page.waitForSelector('.aim-header .aim-phase-chip-link')
const t0 = Date.now()
await page.evaluate(() => { window.__log = [] })
// Wait a full second first, so anything the initial load is still doing has stopped.
await page.locator('.aim-header .aim-phase-chip-link').click()
for (const ms of [0, 40, 100, 200, 400, 800, 1500]) {
  await page.waitForTimeout(ms)
  console.log(ms, await page.evaluate(() => ({
    hash: location.hash,
    top: Math.round(document.querySelector('.aim-main').scrollTop),
    off: (() => { const el = document.getElementById('phase-cross_examine'); const s = document.querySelector('.aim-main')
      return el ? Math.round(el.getBoundingClientRect().top - s.getBoundingClientRect().top) : null })(),
    ch: document.querySelector('.aim-main').clientHeight,
    sh: Math.round(document.querySelector('.aim-main').scrollHeight),
  })))
}
await browser.close()
