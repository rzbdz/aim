/**
 * T-0182 "after", fixture-driven, in the browser.
 *
 * The bundle served on 8777 contains the fixed pane (`dist/assets/OverviewPane-*.js`
 * holds `show them`, `min(420px, 92vw)` and `receiptCount`), so unlike the
 * file-level probes this measures the rendered DOM. It reads the fixtures out of
 * `tests/receipts.spec.js` itself -- the spec's helper section is evaluated as
 * written -- so what is measured is what the spec asserts, and the live board's
 * own traffic cannot change the answer.
 *
 * It also checks the locators the spec uses, because Playwright strict mode
 * fails on an ambiguous locator and a probe can see that before the suite does.
 */
import { readFileSync } from 'node:fs'
import { chromium } from 'playwright'

const BASE = 'http://127.0.0.1:8777'
const source = readFileSync('/root/tmp/agent-im/web/tests/receipts.spec.js', 'utf8')
const helpers = source.slice(0, source.indexOf('test.describe(')).replace(/^import .*$/gm, '')
const fixtures = new Function('expect', 'test',
  `${helpers}\nreturn { SPLIT_WINDOW, TAIL_BURST, TWO_PAIRS, QUIET_TAIL, STATE }`)(() => {}, {})

const receiver = /^RECEIPT for\s+/
const expected = {
  SPLIT_WINDOW: { rows: 4, collapsed: 1, count: 7, date: '2026-09-22 00:03', receipts: 7 },
  TAIL_BURST: { rows: 1, collapsed: 1, count: 7, date: '2026-09-22 00:03', receipts: 7 },
  TWO_PAIRS: { rows: 2, collapsed: 2, count: null, date: null, receipts: 10 },
  QUIET_TAIL: { rows: 5, collapsed: 0, count: null, date: null, receipts: 0 },
}

const browser = await chromium.launch()
let failures = 0
const check = (ok, label, detail) => {
  if (!ok) failures += 1
  console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${label}${detail ? ` — ${detail}` : ''}`)
}

for (const width of [1440, 390]) {
  console.log(`\nviewport ${width}:`)
  const page = await browser.newPage({ viewport: { width, height: 900 } })
  let mail = []
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(fixtures.STATE(mail)),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: 'receipts-fixture' }),
  }))

  for (const name of Object.keys(expected)) {
    const want = expected[name]
    // A new fixture needs a real document load, not a route change: the app
    // fetches `/api/state` once at mount, so navigating to the same hash with a
    // different body leaves the previous fixture on screen. Measured the hard
    // way -- the first run of this probe reported TAIL_BURST with SPLIT_WINDOW's
    // four rows. `reload()` re-runs the app; the route handler then answers with
    // the new `mail`.
    mail = fixtures[name]
    await page.goto(`${BASE}/#/attention`, { waitUntil: 'networkidle' })
    await page.reload({ waitUntil: 'networkidle' })
    await page.waitForSelector('.aim-attention')
    const card = page.locator('.el-card').filter({ hasText: 'Latest conversation' })
    const rows = card.locator('.aim-attention-row')
    const collapsed = rows.filter({ hasText: 'receipts arrived' })
    const rowCount = await rows.count()
    const collapsedCount = await collapsed.count()
    check(rowCount === want.rows, `${name}: rows ${rowCount} == ${want.rows}`)
    check(collapsedCount === want.collapsed, `${name}: collapsed ${collapsedCount} == ${want.collapsed}`)
    if (!want.collapsed) continue

    const text = (await collapsed.first().innerText()).replace(/\s+/g, ' ')
    const count = Number(/(\d+) receipts arrived/.exec(text)?.[1])
    if (want.count) check(count === want.count, `${name}: count ${count} == ${want.count}`)
    const date = await collapsed.first()
      .locator('span').filter({ hasText: /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/ }).first().innerText()
    if (want.date) check(date === want.date, `${name}: date ${date} == ${want.date}`)
    check(!/RECEIPT for/.test(text), `${name}: no raw receipt subject in the collapsed row`)

    // The locators the spec uses, checked for strict-mode ambiguity.
    const buttons = await collapsed.first().getByRole('button').count()
    check(buttons === 1, `${name}: one button in the collapsed row (strict mode)`, `found ${buttons}`)

    await collapsed.first().getByRole('button').click()
    const popper = page.locator('.el-popper:visible')
    const visible = await popper.count()
    check(visible === 1, `${name}: one visible popper`, `found ${visible}`)
    if (visible !== 1) continue
    const box = await popper.boundingBox()
    const fitsX = box.x >= -1 && box.x + box.width <= width + 1
    check(fitsX, `${name}: panel inside a ${width}px viewport`,
      `x ${Math.round(box.x)}..${Math.round(box.x + box.width)}`)
    const body = await page.locator('body').evaluate((el) => [el.scrollWidth, el.clientWidth])
    check(body[0] <= body[1], `${name}: no page-level horizontal scroll`, body.join(' vs '))

    // The ids the panel lists are the ones the receipts of *that row's
    // conversation* name -- not every receipt in the payload: one row stands for
    // one conversation, and on TWO_PAIRS the other conversation has its own row.
    const ids = (await popper.innerText()).match(/\d{8}T\d{6}\.\d{3}Z-\S+/g) || []
    const scope = /\S+ ⇄ \S+/.exec(text)?.[0] || ''
    const payloadIds = fixtures[name]
      .filter((m) => receiver.test(m.subject || ''))
      .filter((m) => [m.from, m.to].map(String).sort().join(' ⇄ ') === scope.split(' ⇄ ').map(String).sort().join(' ⇄ '))
      .sort((a, b) => (a.ts < b.ts ? 1 : a.ts > b.ts ? -1 : 0))
      .map((m) => m.subject.replace(receiver, '').trim())
    check(ids.length === payloadIds.length && ids.length === count,
      `${name}: panel lists ${ids.length} ids for a count of ${count} (group ${scope})`)
    check(ids[0] === payloadIds[0] && ids.at(-1) === payloadIds.at(-1),
      `${name}: newest first`, `${ids[0]} … ${ids.at(-1)}`)

    // Dismissal: outside click (the trigger's own contract). The wait is longer
    // than the leave transition -- at 250ms the panel is still counted visible
    // while it animates out, which reads as "it did not close".
    await page.locator('.aim-attention-hero h3').click()
    await page.waitForTimeout(700)
    check(await page.locator('.el-popper:visible').count() === 0, `${name}: outside click closes it`)
  }
  await page.close()
}

console.log(failures ? `\n${failures} check(s) failed` : '\nevery check passed')
await browser.close()
