/**
 * Probe 7: strict-mode uniqueness of `.el-card` filtered by 'Latest conversation'
 * across every fixture the spec uses (a second card carrying that text would make
 * every locator built on it throw), plus the spec's corrected id assertions run
 * verbatim against this bundle. Read-only.
 *
 * Usage: node probe-receipts-verify7.mjs <dist-dir>
 */
import { chromium } from 'playwright'
import { readFileSync, existsSync } from 'node:fs'
import { join, extname } from 'node:path'

const DIST = process.argv[2]
const ORIGIN = 'http://aim-probe.invalid'
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' }
const stamp = (ts) => ts.replace(/[-:]/g, '')
const receipt = (ts, { from = 'codex', to = 'claude-session1' } = {}) => ({
  from, to, ts, subject: `RECEIPT for ${stamp(ts)}-${to}`, body: `${from} received ${stamp(ts)}-${to}.`,
  msg_id: `${stamp(ts)}-${from}-receipt`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const original = (ts, { from = 'claude-session1', to = 'codex' } = {}) => ({
  from, to, ts, subject: 'the message that gets receipted', body: 'a long message',
  msg_id: `${stamp(ts)}-${from}`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const note = (ts, i) => ({
  from: 'claude-session1', to: 'codex', ts, subject: `routine note ${i}`, body: 'nothing to do',
  msg_id: `${stamp(ts)}-note-${i}`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const BURST = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z', '2026-09-22T00:03:00.000Z']
const LATE = ['2026-09-22T00:03:30.000Z', '2026-09-22T00:03:40.000Z', '2026-09-22T00:03:50.000Z']
const SPLIT_WINDOW = [...BURST.map((ts) => receipt(ts)), note('2026-09-22T00:04:00.000Z', 1), note('2026-09-22T00:05:00.000Z', 2), note('2026-09-22T00:06:00.000Z', 3)]
const TAIL_BURST = [original('2026-09-21T23:57:00.000Z'), original('2026-09-21T23:58:00.000Z'), original('2026-09-21T23:59:00.000Z'), ...BURST.map((ts) => receipt(ts))]
const TWO_PAIRS = [...BURST.map((ts) => receipt(ts)), ...LATE.map((ts) => receipt(ts, { from: 'codex-orangement', to: 'human' }))]
const QUIET_TAIL = [...BURST.map((ts) => receipt(ts)), ...Array.from({ length: 15 }, (_, i) => note(`2026-09-22T00:${String(10 + i).padStart(2, '0')}:00.000Z`, 100 + i))]
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
async function open(mail) {
  const page = await browser.newPage()
  await page.route(`${ORIGIN}/**`, (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname === '/' ? '/index.html' : url.pathname
    const file = join(DIST, path)
    if (!existsSync(file)) return route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' })
    return route.fulfill({ contentType: MIME[extname(file)] || 'application/octet-stream', body: readFileSync(file) })
  })
  await page.route(`${ORIGIN}/api/state**`, (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(STATE(mail)) }))
  await page.route(`${ORIGIN}/api/digest**`, (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ digest: 'receipts-fixture' }) }))
  await page.goto(`${ORIGIN}/#/attention`)
  return page
}

for (const [name, mail] of Object.entries({ SPLIT_WINDOW, TAIL_BURST, TWO_PAIRS, QUIET_TAIL })) {
  const page = await open(mail)
  await page.waitForTimeout(1200)
  const n = await card(page).count()
  console.log(`${name}: .el-card filter 'Latest conversation' -> ${n} node(s) ${n === 1 ? 'OK' : 'STRICT-MODE RISK'}`)
  await page.close()
}

// the corrected id assertions, verbatim from the spec
{
  const page = await open(TAIL_BURST)
  await page.waitForTimeout(1200)
  await collapsed(page).first().getByRole('button').click()
  const popper = page.locator('.el-popper:visible')
  const text = await popper.innerText()
  const ids = text.match(/20260922T\d{6}\.\d{3}Z-claude-session1/g) || []
  console.log('\ncorrected regex ids:', ids.length, 'expected 7 ->', ids.length === 7)
  console.log('ids[0] toBe stamp(BURST[6])-claude-session1:', ids[0] === `${stamp(BURST[6])}-claude-session1`)
  console.log('ids[6] toBe stamp(BURST[0])-claude-session1:', ids[6] === `${stamp(BURST[0])}-claude-session1`)
  await page.close()
}
await browser.close()
