/**
 * T-0182 -- "Latest conversation's receipt count is a five-row window, not the
 * record".
 *
 * Card text (channels/hello/tasks.jsonl, `created` 2026-09-22T03:49:30.009Z,
 * actor codex, owner claude-session1), verbatim acceptance:
 *
 *   "The receipt count is computed from the whole payload and does not change
 *    when the display window changes; the collapsed row is dated by the latest
 *    receipt and can be opened to see which messages it stands for"
 *
 * Only the first two clauses are asserted here. The third -- "can be opened to
 * see which messages it stands for" -- is asserted by `tests/receipts.spec.js`
 * (`the count opens: it names the messages that were receipted`); this file does
 * not restate another file's assertion, and does not depend on it either.
 *
 * Revision measured for this file -- `GET http://127.0.0.1:8777/api/revision`
 * on 2026-09-22:
 *
 *   fabric 59c319b+dirty
 *   bundle 59c319b+dirty, built 2026-09-22T08:20:23.487Z, source "vite build"
 *   stale: true
 *
 * `stale` is true, so the bundle answering 8777 was not built from the `web/src`
 * that is checked out beside it. What that means for the verdict is narrow and
 * worth stating: this file measures the bundle a reader actually loads, and the
 * bundle does contain the fix (measured, `dist/assets/OverviewPane-Du5hWr3R.js`
 * holds `receiptCount`, `show them` and `newest first`; the source it was built
 * from is the uncommitted `web/src/panes/OverviewPane.vue:102` `receiptGroups`
 * rewrite). A verdict here is a verdict about that bundle.
 *
 * What the defect was, so the fixture below is not arbitrary. `OverviewPane.vue`
 * drew `board.conversationRows.slice(-5)` -- the five newest rows of the whole
 * payload -- and took the count to print from that slice, so the number a reader
 * saw was the number of receipts that happened to be *visible*, not the number
 * that arrived. The count was capped at five and moved when the window moved.
 *
 * So the fixture is built to make those two numbers disagree on every case, and
 * the disagreement is asserted rather than assumed: `receiptsInWindow()` counts
 * the receipt rows inside the last five rows the card draws, `receiptsInPayload()`
 * counts the receipts in the payload, and a test below fails if a fixture stops
 * discriminating. Seven receipts arrive in one conversation three minutes apart;
 * the number of ordinary rows after them varies, which changes how many of those
 * seven sit inside the window -- five, then three, then one. A count taken from
 * the slice answers 5, 3 and 1. A count taken from the payload answers 7, three
 * times, and the row is dated 00:03 because that is the newest receipt, not
 * 00:00 because that is the earliest.
 *
 * That the fixture discriminates was measured rather than argued. The served
 * module was intercepted in flight (`page.route` on `**/assets/OverviewPane-*.js`)
 * and its printed count replaced with the pre-fix expression
 * `conversationRows.slice(-5).filter(isReceipt).length` -- same fixture, same
 * page, only that expression changed:
 *
 *   as served   BURST_ONLY -> "7 receipts arrived"   PLUS_TWO -> 7   PLUS_FOUR -> 7
 *   pre-fix     BURST_ONLY -> "5 receipts arrived"   PLUS_TWO -> 3   PLUS_FOUR -> 1
 *
 * 5, 3 and 1 are the window counts this fixture declares, so the assertion in
 * this file fails on the expression the card names and passes on the one that
 * ships. Nothing in the checkout was modified to take that measurement.
 */
import { expect, test } from '@playwright/test'

/** `2026-09-22T00:00:30.000Z` -> `20260922T000030.000Z`, the id shape `aim` writes. */
const stamp = (ts) => ts.replace(/[-:]/g, '')
const receiptRe = /^RECEIPT for\s+/

/**
 * A receipt announces the message it receipts in its subject (`RECEIPT for <id>`),
 * which is what the pane reads.
 */
const receipt = (ts, { from = 'codex', to = 'claude-session1' } = {}) => ({
  from, to, ts,
  subject: `RECEIPT for ${stamp(ts)}-${to}`,
  body: `${from} received ${stamp(ts)}-${to}.\nbytes: 100\n`,
  msg_id: `${stamp(ts)}-${from}-receipt`,
  ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})

/** An ordinary direct message in the same conversation, so the window holds non-receipts. */
const note = (ts, i) => ({
  from: 'claude-session1', to: 'codex', ts, subject: `routine note ${i}`, body: 'nothing to do',
  msg_id: `${stamp(ts)}-note-${i}`, ack_required: false, acked_at: '',
  claimed_at: '', bytes: 0, state: 'delivered',
})

/**
 * Seven receipts of one conversation (`codex ⇄ claude-session1`), 00:00:00 to
 * 00:03:00 at thirty-second steps. The card prints `ts` at minute resolution, so
 * the group's earliest member reads 00:00 and its newest reads 00:03: "dated by
 * the latest receipt" and "dated by the earliest" are different strings.
 */
const BURST = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z',
  '2026-09-22T00:03:00.000Z'].map((ts) => receipt(ts))

/** Ordinary rows after the burst: they push receipts out of the five-row window. */
const tail = (n) => Array.from({ length: n },
  (_, i) => note(`2026-09-22T00:${String(10 + i).padStart(2, '0')}:00.000Z`, 100 + i))

/**
 * One payload per window composition. All three hold the same seven receipts and
 * differ only in how many ordinary rows follow them.
 *
 *   BURST_ONLY  last 5 rows = 5 receipts, and the row drawn is the newest one
 *   PLUS_TWO    last 5 rows = 3 receipts + 2 notes
 *   PLUS_FOUR   last 5 rows = 1 receipt  + 4 notes
 *
 * A count read off `slice(-5)` prints 5, 3 and 1 for these; the record's count is
 * 7 for all three. The declared window counts are checked against the fixture
 * itself in the first test, so a future edit that flattens the difference is a
 * failure here rather than a silently weaker test.
 */
const PAYLOAD_RECEIPTS = 7
const FIXTURES = [
  { name: 'BURST_ONLY', mail: [...BURST], windowReceipts: 5 },
  { name: 'PLUS_TWO', mail: [...BURST, ...tail(2)], windowReceipts: 3 },
  { name: 'PLUS_FOUR', mail: [...BURST, ...tail(4)], windowReceipts: 1 },
]

/** Receipt rows inside the five newest rows -- the window the card draws. */
const receiptsInWindow = (mail) => mail.slice(-5).filter((row) => receiptRe.test(row.subject || '')).length
const receiptsInPayload = (mail) => mail.filter((row) => receiptRe.test(row.subject || '')).length

const STATE = (mail) => ({
  digest: 'card-t0182-fixture', generated_at: '2026-09-22T01:00:00.000Z', as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'], phase: 'RESOLVE', milestones: {}, agents: {}, register: {},
  tasks: {}, reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { viewer: 'human', is_leader: false, channels: [], rooms: [], mail, withheld: 0 },
  channels: [], unacked: [], drift: [], withheld_tasks: 0, write: { enabled: true, as: 'human' },
})

const card = (page) => page.locator('.el-card').filter({ hasText: 'Latest conversation' })
const rows = (page) => card(page).locator('.aim-attention-row')
const collapsed = (page) => rows(page).filter({ hasText: 'receipts arrived' })

/** The number the collapsed row prints, read as a number rather than as a string. */
async function shownCount(page) {
  const text = await collapsed(page).first().innerText()
  const match = /(\d+) receipts arrived/.exec(text)
  expect(match, `no receipt count in ${JSON.stringify(text)}`).not.toBeNull()
  return Number(match[1])
}

/** The date the collapsed row prints, read off the row rather than off a selector guess. */
async function shownDate(page) {
  const text = await collapsed(page).first().innerText()
  const match = /(\d{4}-\d{2}-\d{2} \d{2}:\d{2})/.exec(text)
  expect(match, `no timestamp in ${JSON.stringify(text)}`).not.toBeNull()
  return match[1]
}

test.describe('T-0182: a receipt count is a property of the record, not of the window', () => {
  let mail = []
  test.beforeEach(async ({ page }) => {
    // One handler reading `mail` at request time, so a test picks its fixture by
    // assigning before `goto`/`reload` rather than by stacking a second route.
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify(STATE(mail)),
    }))
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: 'card-t0182-fixture' }),
    }))
  })

  test('the fixture discriminates: the window count differs from the payload count', () => {
    // Not a UI assertion -- the precondition that makes the UI assertions mean
    // something. Seven receipts arrived; the five-row window holds five, three
    // and one of them across the three payloads. If any of those numbers ever
    // equals 7, or the three stop differing, the tests below would pass on a
    // count derived from the slice, and this test says so instead.
    const windows = []
    for (const fixture of FIXTURES) {
      expect(receiptsInPayload(fixture.mail),
        `${fixture.name} must hold ${PAYLOAD_RECEIPTS} receipts`).toBe(PAYLOAD_RECEIPTS)
      expect(receiptsInWindow(fixture.mail),
        `${fixture.name} must leave ${fixture.windowReceipts} receipts in the five-row window`)
        .toBe(fixture.windowReceipts)
      expect(fixture.windowReceipts,
        `${fixture.name}'s window count must differ from the payload count`).not.toBe(PAYLOAD_RECEIPTS)
      windows.push(fixture.windowReceipts)
    }
    expect(new Set(windows).size,
      'the three payloads must not all put the same number of receipts in the window').toBe(3)
  })

  test('the count is the number that arrived, and it does not move when the window does', async ({ page }) => {
    // Three payloads, one record. The number of receipt rows *visible* is 5, then
    // 3, then 1 -- an expression over `slice(-5)` prints three different numbers
    // here, and the smallest of them is not even close. The record's number is 7
    // every time.
    const seen = []
    for (const fixture of FIXTURES) {
      mail = fixture.mail
      if (seen.length) await page.reload()
      else await page.goto('/#/attention')

      // The card is still a five-row window (`rows` at most 5, and the collapse
      // is partial): that is the property the count must not inherit.
      await expect(rows(page), `${fixture.name}: the card must draw at most its five rows`)
        .toHaveCount(Math.min(5, fixture.mail.length))
      await expect(collapsed(page), `${fixture.name}: one collapsed receipt row`)
        .toHaveCount(1)
      await expect(collapsed(page).first(), `${fixture.name}: the arrived count`)
        .toContainText(`${PAYLOAD_RECEIPTS} receipts arrived`)
      seen.push(await shownCount(page))
    }
    expect(seen, 'seven receipts arrived in all three payloads').toEqual([7, 7, 7])
    expect(new Set(seen).size, 'the count must not vary with the window').toBe(1)
  })

  test('the collapsed row is dated by the latest receipt, not the earliest', async ({ page }) => {
    // The group runs 00:00 to 00:03. Dated by its earliest member this row reads
    // 00:00; dated by the latest it reads 00:03. Both are in the payload, and the
    // row that stands for all seven must carry the newest one.
    const dated = FIXTURES.filter((f) => f.windowReceipts > 1)
    for (const [i, fixture] of dated.entries()) {
      mail = fixture.mail
      if (i === 0) await page.goto('/#/attention')
      else await page.reload()
      const name = fixture.name

      expect(await shownDate(page), `${name}: dated by the latest receipt in the group`)
        .toBe('2026-09-22 00:03')
      // The counterexample, spelled out: the group's earliest receipt is a
      // different minute and is in the same payload, so a row carrying it would
      // be visibly wrong rather than accidentally right.
      await expect(collapsed(page).first()).not.toContainText('2026-09-22 00:00')
    }
  })
})
