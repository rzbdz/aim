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
for (let round = 0; round < 5; round += 1) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 700 } })
  const logs = []
  page.on('console', (m) => { if (m.text().includes('[probe]')) logs.push(m.text()) })
  await page.route('**/api/state**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify(STATE) }))
  await page.route('**/api/digest**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }) }))
  await page.goto('http://127.0.0.1:8777/#/kanban')
  await page.waitForSelector('.aim-header .aim-phase-chip-link')
  await page.locator('.aim-header .aim-phase-chip-link').click()
  await page.waitForTimeout(1200)
  const out = await page.evaluate(() => ({
    top: Math.round(document.querySelector('.aim-main').scrollTop),
    off: (() => { const el = document.getElementById('phase-cross_examine'); const s = document.querySelector('.aim-main')
      return el ? Math.round(el.getBoundingClientRect().top - s.getBoundingClientRect().top) : null })(),
  }))
  console.log(`round ${round}`, out, out.off !== null && out.off < 671 ? 'OK' : 'FAIL')
  for (const l of logs) console.log('    ', l)
  await page.close()
}
await browser.close()
