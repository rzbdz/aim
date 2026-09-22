/**
 * Standalone probe: run `tests/receipts.spec.js`'s assertions against a dist
 * snapshot, with `/api/state` and `/api/digest` stubbed exactly the way the
 * spec's fixture does.
 *
 * Usage:  node probe-receipts-verify.mjs <dist-dir>
 *
 * Nothing is written; the snapshot is served to the browser out of the local
 * directory through `page.route`, so no server is started and the record is
 * never touched.
 */
import { chromium } from 'playwright'
import { readFileSync, existsSync } from 'node:fs'
import { join, extname } from 'node:path'

const DIST = process.argv[2]
if (!DIST) throw new Error('usage: node probe-receipts-verify.mjs <dist-dir>')
const ORIGIN = 'http://aim-probe.invalid'

const MIME = {
  '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript',
  '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2', '.png': 'image/png',
}

const stamp = (ts) => ts.replace(/[-:]/g, '')

const receipt = (ts, { from = 'codex', to = 'claude-session1' } = {}) => ({
  from, to, ts,
  subject: `RECEIPT for ${stamp(ts)}-${to}`,
  body: `${from} received ${stamp(ts)}-${to} from ${to}.\nbytes: 100\n`,
  msg_id: `${stamp(ts)}-${from}-receipt`,
  ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const original = (ts, { from = 'claude-session1', to = 'codex' } = {}) => ({
  from, to, ts, subject: 'the message that gets receipted', body: 'a long message',
  msg_id: `${stamp(ts)}-${from}`,
  ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})
const note = (ts, i) => ({
  from: 'claude-session1', to: 'codex', ts, subject: `routine note ${i}`, body: 'nothing to do',
  msg_id: `${stamp(ts)}-note-${i}`, ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
})

const X = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z',
  '2026-09-22T00:03:00.000Z']
const Y = ['2026-09-22T00:03:30.000Z', '2026-09-22T00:03:40.000Z', '2026-09-22T00:03:50.000Z']

const SPLIT_WINDOW = [...X.map((ts) => receipt(ts)),
  note('2026-09-22T00:04:00.000Z', 1), note('2026-09-22T00:05:00.000Z', 2), note('2026-09-22T00:06:00.000Z', 3)]
const TAIL_BURST = [
  original('2026-09-21T23:57:00.000Z'), original('2026-09-21T23:58:00.000Z'), original('2026-09-21T23:59:00.000Z'),
  ...X.map((ts) => receipt(ts))]
const TWO_PAIRS = [...X.map((ts) => receipt(ts)),
  ...Y.map((ts) => receipt(ts, { from: 'codex-orangement', to: 'human' }))]
const QUIET_TAIL = [...X.map((ts) => receipt(ts)),
  ...Array.from({ length: 15 }, (_, i) => note(`2026-09-22T00:${String(10 + i).padStart(2, '0')}:00.000Z`, 100 + i))]

const STATE = (mail) => ({
  digest: 'receipts-fixture', generated_at: '2026-09-22T01:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'], phase: 'RESOLVE', milestones: {}, agents: {}, register: {},
  tasks: {}, reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { viewer: 'human', is_leader: false, channels: [], rooms: [], mail, withheld: 0 },
  channels: [], unacked: [], drift: [], withheld_tasks: 0, write: { enabled: true, as: 'human' },
})

const results = []
function record(label, ok, detail) {
  results.push({ label, ok })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}${detail ? `\n        ${detail}` : ''}`)
}
async function check(label, fn) {
  try {
    const detail = await fn()
    record(label, true, detail)
  } catch (err) {
    const msg = String(err && err.message ? err.message : err).split('\n').filter((l) => l.trim())[0]
    record(label, false, msg)
  }
}

const card = (page) => page.locator('.el-card').filter({ hasText: 'Latest conversation' })
const rows = (page) => card(page).locator('.aim-attention-row')
const collapsed = (page) => rows(page).filter({ hasText: 'receipts arrived' })

async function shownCount(page) {
  const text = await collapsed(page).first().innerText()
  const m = /(\d+) receipts arrived/.exec(text)
  if (!m) throw new Error(`no count in ${JSON.stringify(text)}`)
  return Number(m[1])
}
const dateSpan = (page) => collapsed(page).first()
  .locator('span').filter({ hasText: /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/ }).first()
const shownDate = (page) => dateSpan(page).first().innerText()

async function newPage(browser, getMail) {
  const page = await browser.newPage()
  // Registered first, so the two api stubs below (matched last-registered-first)
  // win for `/api/*`.
  await page.route(`${ORIGIN}/**`, (route) => {
    const url = new URL(route.request().url())
    const path = url.pathname === '/' ? '/index.html' : url.pathname
    const file = join(DIST, path)
    if (!existsSync(file)) return route.fulfill({ status: 404, contentType: 'text/plain', body: 'not found' })
    return route.fulfill({ contentType: MIME[extname(file)] || 'application/octet-stream', body: readFileSync(file) })
  })
  await page.route(`${ORIGIN}/api/state**`, (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE(getMail())),
  }))
  await page.route(`${ORIGIN}/api/digest**`, (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: 'receipts-fixture' }),
  }))
  return page
}

const browser = await chromium.launch()
console.log(`### probe of dist: ${DIST}`)
console.log(readFileSync(join(DIST, 'revision.json'), 'utf8').trim())

// ---------------------------------------------------------------- locator anatomy, SPLIT_WINDOW
{
  const page = await newPage(browser, () => SPLIT_WINDOW)
  await page.goto(`${ORIGIN}/#/attention`)
  await page.waitForTimeout(1500)

  await check('1. `.el-card` filtered by "Latest conversation" is unambiguous (strict mode)', async () => {
    const n = await card(page).count()
    if (n !== 1) throw new Error(`resolved to ${n} nodes`)
    return '1 node'
  })
  await check('2. rows count == 4 (spec asserts 4 on SPLIT_WINDOW)', async () => {
    const n = await rows(page).count()
    if (n !== 4) throw new Error(`got ${n}`)
    return '4'
  })
  await check('3. rows text on SPLIT_WINDOW', async () =>
    JSON.stringify(await rows(page).allInnerTexts()))
  await check('4. `collapsed` filter "receipts arrived" resolves to exactly 1', async () => {
    const n = await collapsed(page).count()
    if (n !== 1) throw new Error(`got ${n}`)
    return '1'
  })
  await check('5. shownCount == 7 on SPLIT_WINDOW (spec asserts 7)', async () => {
    const c = await shownCount(page)
    if (c !== 7) throw new Error(`got ${c}`)
    return '7'
  })
  await check('6. collapsed row contains "7 receipts arrived"', async () => {
    const t = await collapsed(page).first().innerText()
    if (!t.includes('7 receipts arrived')) throw new Error(JSON.stringify(t))
    return 'yes'
  })
  await check('7. rows filter "routine note" == 3', async () => {
    const n = await rows(page).filter({ hasText: 'routine note' }).count()
    if (n !== 3) throw new Error(`got ${n}`)
    return '3'
  })
  await check('8. drawn subjects do not contain "RECEIPT for"', async () => {
    const t = (await rows(page).allInnerTexts()).join(' ')
    if (t.includes('RECEIPT for')) throw new Error('present')
    return 'absent'
  })
  await check('9. `span` filtered by the date regex is unambiguous inside the collapsed row', async () => {
    const d = dateSpan(page)
    const n = await d.count()
    if (n !== 1) {
      const all = await collapsed(page).first().locator('span').allInnerTexts()
      throw new Error(`strict mode: ${n} nodes; row spans = ${JSON.stringify(all)}`)
    }
    return `1 node: ${JSON.stringify(await d.innerText())}`
  })
  await check('10. shownDate == "2026-09-22 00:03" on SPLIT_WINDOW', async () => {
    const d = await shownDate(page)
    if (d !== '2026-09-22 00:03') throw new Error(`got ${d}`)
    return d
  })
  await check('11. `getByRole("button")` inside the collapsed row is unambiguous', async () => {
    const b = collapsed(page).first().getByRole('button')
    const n = await b.count()
    if (n !== 1) throw new Error(`resolved to ${n} nodes`)
    return `1 node: ${JSON.stringify(await b.innerText())}`
  })
  await page.close()
}

// ---------------------------------------------------------------- popover
{
  const page = await newPage(browser, () => TAIL_BURST)
  await page.goto(`${ORIGIN}/#/attention`)
  await page.waitForTimeout(1200)
  await check('12. rows count == 1 on TAIL_BURST (spec asserts 1)', async () => {
    const n = await rows(page).count()
    if (n !== 1) throw new Error(`got ${n}`)
    return '1'
  })
  const urlBefore = page.url()
  await check('13. click the row button; `.el-popper:visible` becomes visible', async () => {
    await collapsed(page).first().getByRole('button').click({ timeout: 5000 })
    await page.waitForTimeout(400)
    const n = await page.locator('.el-popper:visible').count()
    if (n < 1) throw new Error('no visible .el-popper after the click')
    return `${n} visible popper(s)`
  })
  await check('14. the click did not navigate (URL unchanged)', async () => {
    if (page.url() !== urlBefore) throw new Error(`url changed: ${page.url()}`)
    return page.url()
  })
  await check('15. popper text (spec expects "7 receipts arrived in claude-session1 ⇄ codex")', async () => {
    const t = await page.locator('.el-popper:visible').first().innerText()
    if (!t.includes('7 receipts arrived in claude-session1 ⇄ codex')) {
      throw new Error(JSON.stringify(t.slice(0, 300)))
    }
    return JSON.stringify(t.slice(0, 400))
  })
  await check('16. popper names 7 ids matching /20260922T\\d{6}\\.\\d{3}Z-claude-session1/', async () => {
    const t = await page.locator('.el-popper:visible').first().innerText()
    const ids = t.match(/20260922T\d{6}\.\d{3}Z-claude-session1/g) || []
    if (ids.length !== 7) throw new Error(`got ${ids.length}: ${JSON.stringify(ids)}`)
    if (ids[0] !== `${stamp(X[6])}-claude-session1`) throw new Error(`ids[0]=${ids[0]}`)
    if (ids[6] !== `${stamp(X[0])}-claude-session1`) throw new Error(`ids[6]=${ids[6]}`)
    return JSON.stringify(ids)
  })
  await check('17. popper full text (to inspect its last line / close control)', async () => {
    const t = await page.locator('.el-popper:visible').first().innerText()
    return JSON.stringify(t)
  })
  await check('18. popover teleport: where does .el-popper live?', async () =>
    await page.evaluate(() => {
      const p = document.querySelector('.el-popper')
      return p ? `parent=${p.parentElement.tagName}.${p.parentElement.className}` : 'absent'
    }))
  await check('19. what sits over the row (click interception)', async () =>
    await page.evaluate(() => {
      const out = []
      for (const el of document.body.children) {
        const s = getComputedStyle(el)
        out.push(`${el.tagName}.${String(el.className).slice(0, 40)} pos=${s.position} z=${s.zIndex}`)
      }
      return out.join(' | ')
    }))
  await check('20. open popover count when there is no collapsed row (QUIET_TAIL regression of the click)', async () =>
    'see test 21')
  await page.close()
}

// ---------------------------------------------------------------- the two-count test
{
  const page = await newPage(browser, () => SPLIT_WINDOW)
  await page.goto(`${ORIGIN}/#/attention`)
  await page.waitForTimeout(800)
  const withNotes = await shownCount(page).catch(() => null)
  await check('21. count with SPLIT_WINDOW (spec asserts 7)', async () => {
    if (withNotes !== 7) throw new Error(`got ${withNotes}`)
    return '7'
  })
  await page.unroute(`${ORIGIN}/api/state**`)
  await page.route(`${ORIGIN}/api/state**`, (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE(TAIL_BURST)),
  }))
  await page.reload()
  await page.waitForTimeout(800)
  await check('22. rows count after reload with TAIL_BURST (spec asserts 1)', async () => {
    const n = await rows(page).count()
    if (n !== 1) throw new Error(`got ${n}`)
    return '1'
  })
  await check('23. count after reload with TAIL_BURST (spec asserts 7)', async () => {
    const c = await shownCount(page)
    if (c !== 7) throw new Error(`got ${c}`)
    return '7'
  })
  await page.close()
}

// ---------------------------------------------------------------- date test
{
  const page = await newPage(browser, () => TAIL_BURST)
  await page.goto(`${ORIGIN}/#/attention`)
  await page.waitForTimeout(1000)
  await check('24. shownDate on TAIL_BURST == "2026-09-22 00:03"', async () => {
    const d = await shownDate(page)
    if (d !== '2026-09-22 00:03') throw new Error(`got ${d}`)
    return d
  })
  await check('25. collapsed row does not contain "2026-09-22 00:00"', async () => {
    const t = await collapsed(page).first().innerText()
    if (t.includes('2026-09-22 00:00')) throw new Error(JSON.stringify(t))
    return 'absent'
  })
  await check('26. collapsed row on TAIL_BURST (raw text)', async () =>
    JSON.stringify(await collapsed(page).first().innerText()))
  await page.close()
}

// ---------------------------------------------------------------- two conversations
{
  const page = await newPage(browser, () => TWO_PAIRS)
  await page.goto(`${ORIGIN}/#/attention`)
  await page.waitForTimeout(1000)
  await check('27. collapsed count == 2 on TWO_PAIRS', async () => {
    const n = await collapsed(page).count()
    if (n !== 2) throw new Error(`got ${n}`)
    return '2'
  })
  await check('28. collapsed texts sorted == [3, 7]', async () => {
    const texts = (await collapsed(page).allInnerTexts()).map((t) => {
      const m = /\d+ receipts arrived/.exec(t)
      if (!m) throw new Error(`no count in ${JSON.stringify(t)}`)
      return m[0]
    }).sort()
    if (JSON.stringify(texts) !== JSON.stringify(['3 receipts arrived', '7 receipts arrived'])) {
      throw new Error(JSON.stringify(texts))
    }
    return JSON.stringify(texts)
  })
  await check('29. first collapsed row contains "codex-orangement ⇄ human"', async () => {
    const t = await collapsed(page).first().innerText()
    if (!t.includes('codex-orangement ⇄ human')) throw new Error(JSON.stringify(t))
    return 'yes'
  })
  await check('30. last collapsed row contains "claude-session1 ⇄ codex"', async () => {
    const t = await collapsed(page).last().innerText()
    if (!t.includes('claude-session1 ⇄ codex')) throw new Error(JSON.stringify(t))
    return 'yes'
  })
  await check('31. collapsed texts on TWO_PAIRS (raw)', async () =>
    JSON.stringify(await collapsed(page).allInnerTexts()))
  await page.close()
}

// ---------------------------------------------------------------- quiet tail
{
  const page = await newPage(browser, () => QUIET_TAIL)
  await page.goto(`${ORIGIN}/#/attention`)
  await page.waitForTimeout(1000)
  await check('32. rows count == 5 on QUIET_TAIL', async () => {
    const n = await rows(page).count()
    if (n !== 5) throw new Error(`got ${n}`)
    return '5'
  })
  await check('33. collapsed count == 0 on QUIET_TAIL', async () => {
    const n = await collapsed(page).count()
    if (n !== 0) throw new Error(`got ${n}`)
    return '0'
  })
  await check('34. QUIET_TAIL row texts do not contain "RECEIPT for" or "receipts arrived"', async () => {
    const t = (await rows(page).allInnerTexts()).join(' ')
    if (t.includes('RECEIPT for')) throw new Error('RECEIPT for present')
    if (t.includes('receipts arrived')) throw new Error('receipts arrived present')
    return 'absent'
  })
  await page.close()
}

console.log('\n=== summary ===')
for (const r of results) console.log(`${r.ok ? 'PASS' : 'FAIL'}  ${r.label.split('\n')[0]}`)
const failed = results.filter((r) => !r.ok).length
console.log(`${results.length - failed}/${results.length} passed`)
await browser.close()
