import { chromium } from 'playwright'
const STATE = {
  digest: 'anchors-fixture', generated_at: '2026-09-22T00:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog','done'], terminal: ['done'], phase: 'CROSS_EXAMINE',
  milestones: {}, agents: { human: { kind: 'human', model: '' } }, register: {}, tasks: {},
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] }, channels: [], unacked: [],
  drift: [{ id: 'T-0001', field: 'status', plan: 'doing', store: 'review' }],
  withheld_tasks: 0, write: { enabled: false, as: '' },
}
const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } })
await page.route('**/api/state**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify(STATE) }))
await page.route('**/api/digest**', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }) }))
await page.goto('http://127.0.0.1:8777/#/help')
await page.waitForSelector('#phase-cross_examine')
const read = (t) => page.evaluate((tag) => ({
  tag, top: Math.round(document.querySelector('.aim-main').scrollTop),
  sh: Math.round(document.querySelector('.aim-main').scrollHeight),
  ch: document.querySelector('.aim-main').clientHeight,
  at: (() => { const el = document.elementFromPoint(600, 400); return el ? el.tagName + '.' + String(el.className).slice(0,40) : '' })(),
}), t)
console.log(await read('loaded'))
await page.mouse.move(600, 400)
console.log(await read('moved'))
await page.mouse.wheel(0, 1400)
await page.waitForTimeout(400)
console.log(await read('wheel 1400'))
await page.mouse.wheel(0, 1400)
await page.waitForTimeout(400)
console.log(await read('wheel again'))
const table = page.locator('.aim-help-table').first()
console.log('table count', await page.locator('.aim-help-table').count())
await table.hover()
await page.mouse.wheel(0, 1400)
await page.waitForTimeout(400)
console.log(await read('hover table + wheel'))
await browser.close()
