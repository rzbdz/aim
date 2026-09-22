/**
 * T-0182 "after", in the browser.
 *
 * The bundle 8777 serves is now built from the fixed pane (`/api/revision` at
 * 2026-09-22T08:27:59Z: `830dd79+dirty`, and its `dist/assets/OverviewPane-*.js`
 * contains `show them` and `receiptCount`), so unlike the earlier after-probe
 * this can read the rendered DOM. It relies on nothing stubbed: the live board
 * happens to hold a burst of 10 receipts of one conversation whose newest
 * receipt is inside the five-row window, which is exactly the case the fix is
 * for and exactly the case the old expression got wrong.
 *
 * It prints the rows, the date, the count, and what the expander opens.
 */
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:8777'
const receiptRe = /^RECEIPT for\s+/

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })
await page.goto(`${BASE}/#/attention`, { waitUntil: 'networkidle' })
await page.waitForSelector('.aim-attention')

const revision = await (await fetch(`${BASE}/api/revision`)).json()
console.log('bundle:', revision.bundle.revision, 'built', revision.bundle.built_at)

// The payload as the page sees it, read in the same breath as the DOM.
const payload = await page.evaluate(async () => {
  const doc = await (await fetch('/api/state')).json()
  const c = doc.conversation || {}
  const flat = []
  for (const ch of c.channels || []) for (const m of ch.messages || []) flat.push({ ts: m.ts, subject: m.subject || '', from: m.from, to: m.to, shape: 'channel', msg_id: m.msg_id || '' })
  for (const rm of c.rooms || []) for (const m of rm.messages || []) flat.push({ ts: m.ts, subject: m.subject || '', from: m.from, to: m.to, shape: 'room', msg_id: m.msg_id || '' })
  for (const m of c.mail || []) flat.push({ ts: m.ts, subject: m.subject || '', from: m.from, to: m.to, shape: 'direct', msg_id: m.msg_id || '' })
  flat.sort((a, b) => (a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0))
  return flat
})

const card = page.locator('.el-card').filter({ hasText: 'Latest conversation' })
const rows = card.locator('.aim-attention-row')
const collapsed = rows.filter({ hasText: 'receipts arrived' })

const readings = {
  rows: await rows.count(),
  collapsed: await collapsed.count(),
  texts: (await rows.allInnerTexts()).map((t) => t.replace(/\s+/g, ' ').slice(0, 110)),
}
console.log(JSON.stringify(readings, null, 1))

if (readings.collapsed) {
  const row = collapsed.first()
  const text = (await row.innerText()).replace(/\s+/g, ' ')
  const shown = Number(/(\d+) receipts arrived/.exec(text)[1])
  const date = await row.locator('span').filter({ hasText: /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/ }).first().innerText()
  const scope = /((?:[\w.-]+ ⇄ [\w.-]+))/i.exec(text.replace(/^.*?(\S+ ⇄ \S+)/, '$1'))?.[1] || ''
  const [a, b] = scope.split(' ⇄ ')
  const mine = payload.filter((r) => [r.from, r.to].map(String).sort().join(' ⇄ ') === [a, b].map(String).sort().join(' ⇄ '))
  const mineReceipts = mine.filter((r) => receiptRe.test(r.subject)).sort((x, y) => (x.ts < y.ts ? -1 : 1))
  console.log('row          :', text)
  console.log('shown count  :', shown, '| receipts this pair holds:', mineReceipts.length,
    '| receipts of this pair in the last 5 rows:',
    payload.slice(-5).filter((r) => [r.from, r.to].map(String).sort().join(' ⇄ ') === [a, b].map(String).sort().join(' ⇄ ') && receiptRe.test(r.subject)).length)
  console.log('shown date   :', date, '| newest receipt of this pair:', mineReceipts.at(-1)?.ts,
    '| oldest:', mineReceipts[0]?.ts)

  await row.getByRole('button').click()
  const popper = page.locator('.el-popper:visible')
  await popper.waitFor({ state: 'visible', timeout: 5000 })
  const body = await popper.innerText()
  const ids = body.match(/\S+/g)?.filter((w) => /^\d{8}T\d{6}\.\d{3}Z-/.test(w)) || []
  console.log('expander     :', (body.split('\n')[0] || '').slice(0, 120))
  console.log('ids listed   :', ids.length, '| first', ids[0], '| last', ids.at(-1))
  const live = new Set(payload.map((r) => r.msg_id).filter(Boolean))
  const subjects = new Set(payload.filter((r) => receiptRe.test(r.subject)).map((r) => r.subject.replace(receiptRe, '').trim()))
  console.log('ids that are a live msg_id:', ids.filter((id) => live.has(id)).length, 'of', ids.length,
    '| ids that a live receipt names:', ids.filter((id) => subjects.has(id)).length)
  console.log('newest-first order matches the payload:',
    JSON.stringify(ids) === JSON.stringify(mineReceipts.map((r) => r.subject.replace(receiptRe, '').trim()).reverse().slice(0, ids.length)))
} else {
  console.log('no collapsed row on this payload right now -- the live board moved;')
  console.log('newest 5 rows:', payload.slice(-5).map((r) => `${r.ts} ${(r.subject || '').slice(0, 40)}`))
}

await browser.close()
