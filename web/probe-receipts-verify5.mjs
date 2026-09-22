/**
 * Probe 5: the popover's teleport parent, and whether the ids the popover names
 * are present as `msg_id` in the TAIL_BURST fixture (the spec's comment claims
 * they are). Read-only.
 *
 * Usage: node probe-receipts-verify5.mjs <dist-dir>
 */
import { chromium } from 'playwright'
import { readFileSync, existsSync } from 'node:fs'
import { join, extname } from 'node:path'

const DIST = process.argv[2]
const ORIGIN = 'http://aim-probe.invalid'
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml' }
const stamp = (ts) => ts.replace(/[-:]/g, '')
const receipt = (ts, { from = 'codex', to = 'claude-session1' } = {}) => ({
  from, to, ts, subject: `RECEIPT for ${stamp(ts)}-${to}`, body: 'x',
  msg_id: `${stamp(ts)}-${from}-receipt`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const original = (ts, { from = 'claude-session1', to = 'codex' } = {}) => ({
  from, to, ts, subject: 'the message that gets receipted', body: 'a long message',
  msg_id: `${stamp(ts)}-${from}`, ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const X = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z', '2026-09-22T00:03:00.000Z']
const TAIL_BURST = [original('2026-09-21T23:57:00.000Z'), original('2026-09-21T23:58:00.000Z'), original('2026-09-21T23:59:00.000Z'), ...X.map((ts) => receipt(ts))]
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
await page.waitForTimeout(1200)
await collapsed(page).first().getByRole('button').click()
await page.waitForTimeout(400)

console.log('--- teleport parent of the popover ---')
console.log(await page.evaluate(() => {
  const p = document.querySelector('.el-popper.el-popover')
  const chain = []
  let n = p
  while (n && chain.length < 4) { chain.push(`${n.tagName}${n.id ? '#' + n.id : ''}.${n.className}`); n = n.parentElement }
  return chain.join('  <-  ')
}))
console.log('body children:', await page.evaluate(() => [...document.body.children].map((e) => `${e.tagName}${e.id ? '#' + e.id : ''}`).join(', ')))

const text = await page.locator('.el-popper:visible').first().innerText()
const ids = text.match(/\d{8}T\d{6}\.\d{3}Z-[A-Za-z0-9-]+/g) || []
console.log('\n--- ids the popover names (full tokens) ---')
console.log(JSON.stringify(ids))
const payloadIds = TAIL_BURST.map((m) => m.msg_id)
console.log('\n--- payload msg_ids (TAIL_BURST) ---')
console.log(JSON.stringify(payloadIds))
console.log('\n--- each popover id present as msg_id in the fixture? ---')
console.log(JSON.stringify(ids.map((id) => [id, payloadIds.includes(id)])))
console.log('\n--- what the spec\'s line 220 regex matches: /20260921T\\d{6}\\.\\d{3}Z-codex/g ---')
console.log(JSON.stringify(text.match(/20260921T\d{6}\.\d{3}Z-codex/g) || []))
console.log('\n--- what a corrected regex /2026092[12]T\\d{6}\\.\\d{3}Z-claude-session1/g matches ---')
console.log(JSON.stringify(text.match(/2026092[12]T\d{6}\.\d{3}Z-claude-session1/g) || []))
console.log('\n--- line 222/223 counterparts ---')
console.log('expected ids[0] by spec:', `${stamp(X[6])}-codex`, '| actual ids[0]:', ids[0])
console.log('expected ids[6] by spec:', `${stamp(X[0])}-codex`, '| actual ids[6]:', ids[6])
console.log('actual ids[0] with correct owner:', `${stamp(X[6])}-claude-session1`)
console.log('actual ids[6] with correct owner:', `${stamp(X[0])}-claude-session1`)
await browser.close()
