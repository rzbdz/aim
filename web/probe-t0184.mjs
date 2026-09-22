import { chromium } from 'playwright'

const TASK = (id, title, extra = {}) => ({
  id, title, owner: 'codex', status: 'doing', priority: 'normal', milestone: '',
  tags: [], due: '', accept: 'a', blocked_by: [], visibility: 'published',
  provenance: 'store only', events: [], comments: [], ...extra,
})
const STATE = {
  digest: 'p', generated_at: '2026-09-22T00:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog','doing','review','done'], terminal: ['done'], phase: 'RESOLVE',
  milestones: {}, agents: { human: { kind: 'human', model: '' } }, register: {},
  tasks: { 'T-0001': TASK('T-0001','A record the drawer cannot draw',{ blocked_by: 'T-0002' }),
           'T-0002': TASK('T-0002','A record it can') },
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] }, channels: [], unacked: [],
  drift: [], withheld_tasks: 0, write: { enabled: false, as: '' },
}

const browser = await chromium.launch()
const page = await browser.newPage()
page.on('console', (m) => console.log('CONSOLE', m.type(), m.text().slice(0, 200)))
page.on('pageerror', (e) => console.log('PAGEERROR', String(e).slice(0, 300)))
await page.route('**/api/state**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify(STATE) }))
await page.route('**/api/digest**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }) }))
await page.goto('http://127.0.0.1:8777/#/kanban')
await page.waitForSelector('.aim-card[data-id="T-0001"]')
await page.locator('.aim-card[data-id="T-0001"]').click()
await page.waitForTimeout(1500)
console.log(await page.evaluate(() => {
  const o = [...document.querySelectorAll('.el-overlay')]
  return {
    overlays: o.length,
    display: o.map((e) => getComputedStyle(e).display),
    drawers: document.querySelectorAll('.el-drawer').length,
    atCentre: (() => { const el = document.elementFromPoint(120, 300); return el ? el.tagName + '.' + el.className : '' })(),
  }
}))
await page.locator('.aim-card[data-id="T-0002"]').click()
await page.waitForTimeout(1200)
console.log('after second click:', await page.evaluate(() => ({
  overlays: [...document.querySelectorAll('.el-overlay')].map((e) => getComputedStyle(e).display),
  drawers: document.querySelectorAll('.el-drawer').length,
  h3: [...document.querySelectorAll('.el-drawer h3')].map((e) => e.textContent),
})))
await browser.close()
