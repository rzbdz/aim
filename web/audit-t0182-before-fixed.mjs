/**
 * T-0182 "before" probe, run against the live board on 8777.
 *
 * Three measurements of `recentConversations` in OverviewPane.vue, taken against
 * the bundle already served on 8777 (revision `dbdd04e+dirty`, which contains
 * `slice(-5)` and `receipts arrived` -- grep of dist/assets/OverviewPane-*.js):
 *
 *  1. Fixture: seven receipts in one pair, spread over three minutes, with 15
 *     non-receipt rows after them. Prints what the card renders and what it does
 *     not render.
 *  2. The same seven receipts with the later rows removed: only the window
 *     changed, so a number that moves between run 1 and run 2 is a number about
 *     the window.
 *  3. Where the collapsed row's timestamp and link come from.
 *
 * Nothing here asserts. It prints what the rendered page says.
 */
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:8777'
const receiptRe = /^RECEIPT for\s+/

const RE = (ts, i) => ({
  from: 'codex', to: 'claude-session1', ts,
  subject: `RECEIPT for 20260922T00${i}000.000Z-claude-session1`,
  body: `codex received 20260922T00${i}000.000Z-claude-session1 from claude-session1.\nbytes: 100\n`,
  msg_id: `20260922T00${i}000.000Z-codex-receipt`,
  ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
})
const NOISE = (ts, i) => ({
  from: 'claude-session1', to: 'codex', ts, subject: `routine note ${i}`, body: 'nothing to do',
  msg_id: `${ts}-noise-${i}`, ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
})

// Seven receipts across three minutes. The card prints `ts.slice(0, 16)`, i.e.
// minute resolution, so 00:00 vs 00:03 is a date a reader can be wrong about.
const RECEIPTS = [
  '2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z',
  '2026-09-22T00:03:00.000Z',
].map(RE)
const OLD_NOISE = Array.from({ length: 3 }, (_, i) => NOISE(`2026-09-21T23:5${i}:00.000Z`, i))
// Fifteen rows after the burst: the last five rows are all noise, so the window
// holds zero receipts while the payload holds seven.
const NEW_NOISE = Array.from({ length: 15 }, (_, i) =>
  NOISE(`2026-09-22T00:1${String(i).padStart(2, '0')}:00.000Z`, i + 100))

const state = (mail) => ({
  digest: 't0182-before', generated_at: '2026-09-22T00:20:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'], phase: 'RESOLVE', milestones: {}, agents: {}, register: {},
  tasks: {}, reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { viewer: 'human', is_leader: false, channels: [], rooms: [], mail, withheld: 0 },
  channels: [], unacked: [], drift: [], withheld_tasks: 0, write: { enabled: true, as: 'human' },
})

const card = (page) => page.locator('.el-card').filter({ hasText: 'Latest conversation' })
const rows = (page) => card(page).locator('.aim-attention-row')

async function readCard(page, mail) {
  if (mail) {
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify(state(mail)),
    }))
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: 't0182-before' }),
    }))
  }
  await page.goto(`${BASE}/#/attention`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.aim-attention')
  await page.waitForTimeout(400)
  const collapsed = rows(page).filter({ hasText: /\d+ receipts arrived/ })
  return {
    rowCount: await rows(page).count(),
    subjects: await rows(page).locator('.aim-row-link').allInnerTexts(),
    stamps: (await rows(page).locator('span:last-child').allInnerTexts()).filter((t) => /^\d{4}-/.test(t)),
    collapsedRows: await collapsed.count(),
    collapsedText: await collapsed.count() ? (await collapsed.first().innerText()).replace(/\s+/g, ' ') : '',
    collapsedStamp: await collapsed.count()
      ? (await collapsed.first().locator('span:not(.el-tag__content)').last().innerText())
      : '',
    collapsedHref: await collapsed.count()
      ? await collapsed.first().locator('a').first().getAttribute('href').catch(() => '(NO <a> in this row)')
      : '',
    rawReceiptRows: await rows(page).filter({ hasText: 'RECEIPT for' }).count(),
    cardText: (await card(page).innerText()).replace(/\s+/g, ' ').slice(0, 300),
  }
}

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })

console.log('== 1. seven receipts, then 15 non-receipt rows (window = the 15) ==')
const buried = await readCard(await context.newPage(), [...OLD_NOISE, ...RECEIPTS, ...NEW_NOISE])
console.log('   rows rendered          :', buried.rowCount)
console.log('   collapsed rows         :', buried.collapsedRows)
console.log('   rows showing "RECEIPT for" text raw:', buried.rawReceiptRows)
console.log('   subjects               :', JSON.stringify(buried.subjects))

console.log('== 2. the same seven receipts, nothing after them (window = the burst) ==')
const tailed = await readCard(await context.newPage(), [...OLD_NOISE, ...RECEIPTS])
console.log('   rows rendered          :', tailed.rowCount)
console.log('   collapsed text         :', JSON.stringify(tailed.collapsedText))
console.log('   collapsed row stamp    :', JSON.stringify(tailed.collapsedStamp),
  '<- latest receipt is 00:03, earliest is 00:00')
console.log('   collapsed row link href:', JSON.stringify(tailed.collapsedHref))
console.log('   subjects               :', JSON.stringify(tailed.subjects))

console.log('== 3. live payload on 8777 ==')
const livePage = await context.newPage()
await livePage.goto(`${BASE}/#/attention`, { waitUntil: 'networkidle' })
await livePage.waitForSelector('.aim-attention')
const live = await livePage.evaluate(async () => {
  const doc = await (await fetch('/api/state')).json()
  const c = doc.conversation || {}
  const re = /^RECEIPT for\s+/
  const flat = []
  for (const ch of c.channels || []) for (const m of ch.messages || []) flat.push({ ts: m.ts, subject: m.subject || '' })
  for (const rm of c.rooms || []) for (const m of rm.messages || []) flat.push({ ts: m.ts, subject: m.subject || '' })
  for (const m of c.mail || []) flat.push({ ts: m.ts, subject: m.subject || '' })
  flat.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
  const byScope = new Map()
  for (const m of c.mail || []) {
    if (!re.test(m.subject || '')) continue
    const k = [m.from, m.to].map(String).sort().join(' ⇄ ')
    byScope.set(k, (byScope.get(k) || 0) + 1)
  }
  return {
    rows: flat.length,
    receipts: flat.filter((r) => re.test(r.subject)).length,
    windowReceipts: flat.slice(-5).filter((r) => re.test(r.subject)).length,
    byScope: [...byScope].sort((a, b) => b[1] - a[1]),
  }
})
const liveRead = await readCard(livePage, null, true)
console.log('   flattened rows:', live.rows, '| receipts in payload:', live.receipts,
  '| receipts in the last 5 rows:', live.windowReceipts)
console.log('   receipts per conversation:', JSON.stringify(live.byScope))
console.log('   rows rendered          :', liveRead.rowCount)
console.log('   collapsed rows         :', liveRead.collapsedRows)
console.log('   subjects               :', JSON.stringify(liveRead.subjects))

await browser.close()
