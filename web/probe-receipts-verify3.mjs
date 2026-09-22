/**
 * Probe 3: what `.el-popper` nodes exist while the popover is open, and whether
 * `.el-popper:visible` can ever resolve to more than one node (strict mode).
 * Read-only; serves a dist snapshot to the browser.
 *
 * Usage: node probe-receipts-verify3.mjs <dist-dir>
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
  body: `x`, msg_id: `${stamp(ts)}-${from}-receipt`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const original = (ts, { from = 'claude-session1', to = 'codex' } = {}) => ({
  from, to, ts, subject: 'the message that gets receipted', body: 'a long message',
  msg_id: `${stamp(ts)}-${from}`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const X = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z', '2026-09-22T00:03:00.000Z']
const Y = ['2026-09-22T00:03:30.000Z', '2026-09-22T00:03:40.000Z', '2026-09-22T00:03:50.000Z']
const TAIL_BURST = [original('2026-09-21T23:57:00.000Z'), original('2026-09-21T23:58:00.000Z'), original('2026-09-21T23:59:00.000Z'), ...X.map((ts) => receipt(ts))]
const TWO_PAIRS = [...X.map((ts) => receipt(ts)), ...Y.map((ts) => receipt(ts, { from: 'codex-orangement', to: 'human' }))]
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
  await page.waitForTimeout(1200)
  return page
}

async function dumpPoppers(page, label) {
  console.log(`\n--- ${label} ---`)
  console.log(await page.evaluate(() => {
    const out = []
    for (const p of document.querySelectorAll('.el-popper')) {
      const s = getComputedStyle(p)
      out.push({ cls: p.className, display: s.display, visibility: s.visibility, opacity: s.opacity, role: p.getAttribute('role'), parent: `${p.parentElement.tagName}.${p.parentElement.className}` })
    }
    const vis = [...document.querySelectorAll('.el-popper')].filter((p) => !!(p.offsetWidth || p.offsetHeight || p.getClientRects().length))
    return { nodes: out, visibleByPlaywrightRule: vis.length }
  }))
}

// --- single popover
{
  const page = await open(TAIL_BURST)
  await dumpPoppers(page, 'TAIL_BURST: before any click')
  await collapsed(page).first().getByRole('button').click()
  await page.waitForTimeout(600)
  await dumpPoppers(page, 'TAIL_BURST: popover open')
  console.log('page.locator(".el-popper:visible").count() =', await page.locator('.el-popper:visible').count())
  console.log('page.locator(".el-popper").count() =', await page.locator('.el-popper').count())
  // hover over the row: does any tooltip popper appear?
  await rows(page).first().hover()
  await page.waitForTimeout(400)
  console.log('after hovering the row, .el-popper:visible =', await page.locator('.el-popper:visible').count())
  await page.close()
}

// --- two popovers, both opened (would the locator be ambiguous?)
{
  const page = await open(TWO_PAIRS)
  console.log('\n--- TWO_PAIRS: collapsed rows =', await collapsed(page).count(), '---')
  await collapsed(page).first().getByRole('button').click()
  await page.waitForTimeout(400)
  console.log('one open: .el-popper:visible =', await page.locator('.el-popper:visible').count())
  await collapsed(page).last().getByRole('button').click()
  await page.waitForTimeout(400)
  console.log('two open: .el-popper:visible =', await page.locator('.el-popper:visible').count())
  console.log('two open: .el-popper =', await page.locator('.el-popper').count())
  await dumpPoppers(page, 'TWO_PAIRS: both popovers clicked')
  await page.close()
}
await browser.close()
