/**
 * Probe 4: flake check on the click -> popover path, and the timing between the
 * click resolving and `.el-popper:visible` having a node. Read-only.
 *
 * Usage: node probe-receipts-verify4.mjs <dist-dir>
 */
import { chromium } from 'playwright'
import { readFileSync, existsSync } from 'node:fs'
import { join, extname } from 'node:path'

const DIST = process.argv[2]
const ORIGIN = 'http://aim-probe.invalid'
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' }
const stamp = (ts) => ts.replace(/[-:]/g, '')
const receipt = (ts) => ({
  from: 'codex', to: 'claude-session1', ts, subject: `RECEIPT for ${stamp(ts)}-claude-session1`, body: 'x',
  msg_id: `${stamp(ts)}-codex-receipt`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const original = (ts) => ({
  from: 'claude-session1', to: 'codex', ts, subject: 'the message that gets receipted', body: 'a long message',
  msg_id: `${stamp(ts)}-claude-session1`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const X = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z', '2026-09-22T00:03:00.000Z']
const TAIL_BURST = [original('2026-09-21T23:57:00.000Z'), original('2026-09-21T23:58:00.000Z'), original('2026-09-21T23:59:00.000Z'), ...X.map(receipt)]
const STATE = (mail) => ({
  digest: 'receipts-fixture', generated_at: '2026-09-22T01:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'], phase: 'RESOLVE', milestones: {}, agents: {}, register: {},
  tasks: {}, reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { viewer: 'human', is_leader: false, channels: [], rooms: [], mail, withheld: 0 },
  channels: [], unacked: [], drift: [], withheld_tasks: 0, write: { enabled: true, as: 'human' },
})
const card = (page) => page.locator('.el-card').filter({ hasText: 'Latest conversation' })
const collapsed = (page) => card(page).locator('.aim-attention-row').filter({ hasText: 'receipts arrived' })

const browser = await chromium.launch()
for (let i = 1; i <= 5; i++) {
  const page = await browser.newPage()
  await page.route(`${ORIGIN}/**`, (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname === '/' ? '/index.html' : url.pathname
    const file = join(DIST, path)
    if (!existsSync(file)) return route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' })
    return route.fulfill({ contentType: MIME[extname(file)] || 'application/octet-stream', body: readFileSync(file) })
  })
  await page.route(`${ORIGIN}/api/state**`, (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(STATE(TAIL_BURST)) }))
  await page.route(`${ORIGIN}/api/digest**`, (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ digest: 'receipts-fixture' }) }))
  await page.goto(`${ORIGIN}/#/attention`)
  const row = collapsed(page).first()
  await row.waitFor({ state: 'visible' })
  const t0 = Date.now()
  await row.getByRole('button').click()
  const t1 = Date.now()
  const popper = page.locator('.el-popper:visible')
  const immediately = await popper.count()
  let waited = 0
  while (await popper.count() === 0 && waited < 3000) { await page.waitForTimeout(25); waited += 25 }
  const text = await popper.first().innerText()
  const visible = text.includes('7 receipts arrived in claude-session1 ⇄ codex')
  console.log(`run ${i}: click ${t1 - t0}ms; popper visible immediately after click=${immediately}; after ${waited}ms; text ok=${visible}; popperCount=${await popper.count()}`)
  await page.close()
}
await browser.close()
