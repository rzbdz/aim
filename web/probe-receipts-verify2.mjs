/**
 * Probe 2: the specific questions the id assertion, the click, and the strict
 * mode raise. Read-only; serves a dist snapshot to the browser.
 *
 * Usage: node probe-receipts-verify2.mjs <dist-dir>
 */
import { chromium } from 'playwright'
import { readFileSync, existsSync } from 'node:fs'
import { join, extname } from 'node:path'

const DIST = process.argv[2]
const ORIGIN = 'http://aim-probe.invalid'
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' }

const stamp = (ts) => ts.replace(/[-:]/g, '')
const receipt = (ts, { from = 'codex', to = 'claude-session1' } = {}) => ({
  from, to, ts, subject: `RECEIPT for ${stamp(ts)}-${to}`,
  body: `${from} received ${stamp(ts)}-${to} from ${to}.\nbytes: 100\n`,
  msg_id: `${stamp(ts)}-${from}-receipt`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const original = (ts, { from = 'claude-session1', to = 'codex' } = {}) => ({
  from, to, ts, subject: 'the message that gets receipted', body: 'a long message',
  msg_id: `${stamp(ts)}-${from}`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const X = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z', '2026-09-22T00:03:00.000Z']
const TAIL_BURST = [
  original('2026-09-21T23:57:00.000Z'), original('2026-09-21T23:58:00.000Z'), original('2026-09-21T23:59:00.000Z'),
  ...X.map((ts) => receipt(ts))]
const STATE = (mail) => ({
  digest: 'receipts-fixture', generated_at: '2026-09-22T01:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'], phase: 'RESOLVE', milestones: {}, agents: {}, register: {},
  tasks: {}, reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { viewer: 'human', is_leader: false, channels: [], rooms: [], mail, withheld: 0 },
  channels: [], unacked: [], drift: [], withheld_tasks: 0, write: { enabled: true, as: 'human' },
})

const card = (page) => page.locator('.el-card').filter({ hasText: 'Latest conversation' })
const rows = (page) => card(page).locator('.aim-attention-row')
const collapsed = (page) => rows(page).filter({ hasText: 'receipts arrived' })

const browser = await chromium.launch()
const page = await browser.newPage()
await page.route(`${ORIGIN}/**`, (route) => {
  const url = new URL(route.request().url())
  const path = url.pathname === '/' ? '/index.html' : url.pathname
  const file = join(DIST, path)
  if (!existsSync(file)) return route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' })
  return route.fulfill({ contentType: MIME[extname(file)] || 'application/octet-stream', body: readFileSync(file) })
})
await page.route(`${ORIGIN}/api/state**`, (route) => route.fulfill({
  contentType: 'application/json', body: JSON.stringify(STATE(TAIL_BURST)),
}))
await page.route(`${ORIGIN}/api/digest**`, (route) => route.fulfill({
  contentType: 'application/json', body: JSON.stringify({ digest: 'receipts-fixture' }),
}))
await page.goto(`${ORIGIN}/#/attention`)
await page.waitForTimeout(1200)

console.log('--- rows on TAIL_BURST ---')
console.log(JSON.stringify(await rows(page).allInnerTexts(), null, 1))

console.log('--- payload msg_ids (what the record holds) ---')
const payloadIds = TAIL_BURST.map((m) => m.msg_id)
console.log(JSON.stringify(payloadIds))

// --- click WITHOUT any explicit wait, exactly as the spec does
const t0 = Date.now()
await collapsed(page).first().getByRole('button').click()
const popper = page.locator('.el-popper:visible')
await popper.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
console.log(`--- popper visible after ${Date.now() - t0}ms (no explicit wait) ---`)
console.log('visible count:', await popper.count())

const text = await popper.first().innerText()
console.log('--- popper ids, spec regex /20260921T\\d{6}\\.\\d{3}Z-codex/g ---')
console.log(JSON.stringify(text.match(/20260921T\d{6}\.\d{3}Z-codex/g) || []))
console.log('--- popper ids, /20260922T\\d{6}\\.\\d{3}Z-claude-session1/g ---')
console.log(JSON.stringify(text.match(/20260922T\d{6}\.\d{3}Z-claude-session1/g) || []))
console.log('--- all id-shaped tokens in the popper ---')
const ids = text.match(/\d{8}T\d{6}\.\d{3}Z-[a-z-]+/g) || []
console.log(JSON.stringify(ids))
console.log('--- are those ids present as msg_id in the payload? ---')
console.log(JSON.stringify(ids.map((id) => [id, payloadIds.includes(id)])))
console.log('--- spec assertions against the popper ---')
console.log('ids.length === 7 ?', ids.length === 7)
console.log('ids[0] ===', JSON.stringify(`${stamp(X[6])}-codex`), '? actual first id:', JSON.stringify(ids[0]))
console.log('ids[6] ===', JSON.stringify(`${stamp(X[0])}-codex`), '? actual last id:', JSON.stringify(ids[6]))

// --- what does the popper text contain for the other assertion?
console.log('--- line 215 substring present? ---')
console.log(JSON.stringify(text.includes('7 receipts arrived in claude-session1 ⇄ codex')))

// --- second click toggles; a stale popper could double-match
await collapsed(page).first().getByRole('button').click()
await page.waitForTimeout(500)
console.log('--- after a second click: visible poppers =', await page.locator('.el-popper:visible').count())
console.log('--- all .el-popper nodes (visible or not) =', await page.locator('.el-popper').count())

console.log('--- where the popper lives ---')
console.log(await page.evaluate(() => {
  const p = document.querySelector('.el-popper')
  if (!p) return 'absent'
  return `parent=${p.parentElement.tagName}("${p.parentElement.className}") isBody=${p.parentElement === document.body}`
}))

await browser.close()
