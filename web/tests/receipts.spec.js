/**
 * T-0182: "N receipts arrived" must count the record, not the five-row window.
 *
 * `recentConversations` in `OverviewPane.vue` drew its count from
 * `conversationRows.slice(-5)`, so the number on the card was `min(5, n)` over
 * the rows that happened to be newest, and it moved when the window moved.
 * Measured on the bundle already served on 8777 (`dist/assets/OverviewPane-*.js`
 * holds `slice(-5)` and `receipts arrived`) with seven receipts of one
 * conversation spread over three minutes:
 *
 *   - nothing after the burst          -> "5 receipts arrived"  (7 arrived)
 *   - three ordinary rows after it     -> "2 receipts arrived"  (7 arrived)
 *   - fifteen ordinary rows after it   -> no receipt row at all (7 arrived)
 *   - live payload, 197 rows, 53 receipts: the newest five rows hold 0 receipts,
 *     so the card drew no receipt row and the 53 were invisible on the page the
 *     leader opens first.
 *
 * The fixtures below are built so those four cases are distinguishable. Every
 * assertion is one of: the count is the payload's count (not the window's), or
 * the row's date is the group's newest receipt, or the count is a way in.
 *
 * The window is still a window: a conversation whose newest receipt is older than
 * the five rows the card draws gets no row, because there is no row to draw it
 * on. That is asserted explicitly (`the card is still a five-row window`) rather
 * than left implicit, so that a future change which fixes it by widening the card
 * has to say so here.
 */
import { expect, test } from '@playwright/test'

/** `2026-09-22T00:03:00.000Z` -> `20260922T000300.000Z`, the id format `aim` writes. */
const stamp = (ts) => ts.replace(/[-:]/g, '')

/**
 * A receipt announces the message it receipts in its subject, and repeats it in
 * its body -- the live shape (`conversation.mail`, 53 of them, and the subject's
 * id equals the body's id in all 53). The pane reads the subject.
 */
const receipt = (ts, { from = 'codex', to = 'claude-session1' } = {}) => ({
  from, to, ts,
  subject: `RECEIPT for ${stamp(ts)}-${to}`,
  body: `${from} received ${stamp(ts)}-${to} from ${to}.\nbytes: 100\n`,
  msg_id: `${stamp(ts)}-${from}-receipt`,
  ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})

/**
 * The message a receipt will name.
 *
 * The id `aim` writes is `<ts>-<sender>` (`20260921T081244.757Z-claude-session1`,
 * live), which is why the receipt's subject carries the *original's author* and
 * not the receipt's addressee. Measured over the live payload: 53 of 53 receipts
 * yield an id from the subject, all 53 are present as `msg_id` in the mail, and
 * the id's owner is the sender of the message that was receipted.
 */
const original = (ts, { from = 'claude-session1', to = 'codex' } = {}) => ({
  from, to, ts, subject: 'the message that gets receipted', body: 'a long message',
  msg_id: `${stamp(ts)}-${from}`,
  ack_required: false, acked_at: '', claimed_at: '', bytes: 0, state: 'delivered',
})

/** An ordinary direct message, so the window holds rows that are not receipts. */
const note = (ts, i) => ({
  from: 'claude-session1', to: 'codex', ts, subject: `routine note ${i}`, body: 'nothing to do',
  msg_id: `${stamp(ts)}-note-${i}`, ack_required: false, acked_at: '', bytes: 0, state: 'delivered',
})

// Seven receipts of one conversation, three minutes from first to last. The card
// prints `ts.slice(0, 16)`, minute resolution, so 00:00 and 00:03 are different
// dates to a reader and either can be asserted.
const BURST = ['2026-09-22T00:00:00.000Z', '2026-09-22T00:00:30.000Z', '2026-09-22T00:01:00.000Z',
  '2026-09-22T00:01:30.000Z', '2026-09-22T00:02:00.000Z', '2026-09-22T00:02:30.000Z',
  '2026-09-22T00:03:00.000Z']
// Three receipts of a second conversation, later than every receipt of the first.
const LATE = ['2026-09-22T00:03:30.000Z', '2026-09-22T00:03:40.000Z', '2026-09-22T00:03:50.000Z']

/** The window (the five newest rows) holds BURST's two newest receipts and three notes. */
const SPLIT_WINDOW = [...BURST.map((ts) => receipt(ts)),
  note('2026-09-22T00:04:00.000Z', 1), note('2026-09-22T00:05:00.000Z', 2), note('2026-09-22T00:06:00.000Z', 3)]

/** The window holds BURST's five newest receipts and no non-receipt row at all. */
const TAIL_BURST = [
  original('2026-09-21T23:57:00.000Z'), original('2026-09-21T23:58:00.000Z'), original('2026-09-21T23:59:00.000Z'),
  ...BURST.map((ts) => receipt(ts))]

/** Two conversations with receipts in the same window: 7 of BURST, 3 of LATE. */
const TWO_PAIRS = [...BURST.map((ts) => receipt(ts)),
  ...LATE.map((ts) => receipt(ts, { from: 'codex-orangement', to: 'human' }))]

/** The burst, then fifteen ordinary rows: no receipt is in the window at all. */
const QUIET_TAIL = [...BURST.map((ts) => receipt(ts)),
  ...Array.from({ length: 15 }, (_, i) => note(`2026-09-22T00:${String(10 + i).padStart(2, '0')}:00.000Z`, 100 + i))]

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

/** The number the collapsed row prints, read as a number rather than as a string. */
async function shownCount(page) {
  const text = await collapsed(page).first().innerText()
  const match = /(\d+) receipts arrived/.exec(text)
  expect(match).not.toBeNull()
  return Number(match[1])
}

/**
 * The date the row prints, matched by shape rather than by position: the row also
 * carries a shape tag and, when it is a count, an expander button, and a
 * positional locator would read whichever of those landed last.
 */
const shownDate = (page) => collapsed(page).first()
  .locator('span').filter({ hasText: /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/ }).first().innerText()

test.describe('T-0182: the count, the date, and the way into them', () => {
  let mail = []
  test.beforeEach(async ({ page }) => {
    // One handler reading `mail` at request time, so a test picks its fixture by
    // assigning before `goto` rather than by stacking a second route on top of a
    // rejected one.
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify(STATE(mail)),
    }))
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: 'receipts-fixture' }),
    }))
  })

  test('the count is how many receipts arrived, not how many are in the five-row window', async ({ page }) => {
    mail = SPLIT_WINDOW
    await page.goto('/#/attention')
    // Four rows: three ordinary messages that the window also holds, and the one
    // row the receipt conversation is drawn as. Seven receipts are in the payload
    // and only two of those are inside the window, so a count taken from the
    // window can only say 2; 5 is the window's own size, the cap that let seven
    // arrive as five. Neither 2 nor 5 is seven. The ordinary rows are asserted
    // because a fix that folds the whole conversation into its count would hide
    // them -- a card that draws one row where ten messages exist is the same
    // defect with the sign flipped.
    await expect(rows(page)).toHaveCount(4)
    await expect(collapsed(page)).toHaveCount(1)
    expect(await shownCount(page)).toBe(7)
    await expect(collapsed(page).first()).toContainText('7 receipts arrived')
    await expect(rows(page).filter({ hasText: 'routine note' })).toHaveCount(3)
    // And the raw subjects of the group are not drawn beside its count.
    const drawn = (await rows(page).allInnerTexts()).join(' ')
    expect(drawn).not.toContain('RECEIPT for')
  })

  test('the count does not move when the window holds a different number of non-receipt rows', async ({ page }) => {
    // This is the "not derived from a slice" assertion, and it is the one that
    // fails on `slice(-5)`: the two fixtures hold the same seven receipts and
    // differ only in what the window contains besides them -- three ordinary rows
    // here, none there. A count taken over the window answers 2 and 5; a count
    // taken over the payload answers 7 twice.
    mail = SPLIT_WINDOW
    await page.goto('/#/attention')
    const withNotes = await shownCount(page)

    mail = TAIL_BURST
    await page.reload()
    await expect(rows(page)).toHaveCount(1)
    const withoutNotes = await shownCount(page)

    expect(withNotes).toBe(7)
    expect(withoutNotes).toBe(7)
    expect(withNotes).toBe(withoutNotes)
  })

  test('the collapsed row is dated by the newest receipt in the group', async ({ page }) => {
    mail = TAIL_BURST
    await page.goto('/#/attention')
    // The group runs 00:00 to 00:03. Dated by its earliest member the row would
    // read 00:00; the page it renders must be the 00:03 end of the burst.
    expect(await shownDate(page)).toBe('2026-09-22 00:03')
    await expect(collapsed(page).first()).not.toContainText('2026-09-22 00:00')

    // And it stays the newest when the row sits among later ordinary rows: the
    // three notes after the burst are 00:04..00:06 and the row is still 00:03,
    // so the date is the group's, not the position's.
    mail = SPLIT_WINDOW
    await page.reload()
    expect(await shownDate(page)).toBe('2026-09-22 00:03')
  })

  test('two conversations in one window keep two counts', async ({ page }) => {
    mail = TWO_PAIRS
    await page.goto('/#/attention')
    // Seven receipts arrived in one conversation and three in another. The
    // expression this replaces collected every receipt row in the window into one
    // row -- five here -- so the second conversation lost its row entirely and the
    // first was reported as five instead of seven.
    await expect(collapsed(page)).toHaveCount(2)
    expect((await collapsed(page).allInnerTexts()).map((text) => /\d+ receipts arrived/.exec(text)[0]).sort())
      .toEqual(['3 receipts arrived', '7 receipts arrived'])
    await expect(collapsed(page).first()).toContainText('codex-orangement ⇄ human')
    await expect(collapsed(page).last()).toContainText('claude-session1 ⇄ codex')
  })

  test('the count opens: it names the messages that were receipted', async ({ page }) => {
    mail = TAIL_BURST
    await page.goto('/#/attention')
    const row = collapsed(page).first()
    // The row is a control, not a number with nothing behind it.
    await row.getByRole('button').click()
    const popper = page.locator('.el-popper:visible')
    await expect(popper).toBeVisible()
    await expect(popper).toContainText('7 receipts arrived in claude-session1 ⇄ codex')
    // Seven lines, newest first, each naming a message the payload actually holds
    // (`TAIL_BURST` ships those messages as the three `original` rows plus the
    // receipts' own subjects). The ids are the receipt subjects read back, and
    // the id's owner is the sender of the message that was receipted -- here
    // claude-session1, the author -- not the agent that receipted it.
    const text = await popper.innerText()
    const ids = text.match(/20260922T\d{6}\.\d{3}Z-claude-session1/g) || []
    expect(ids).toHaveLength(7)
    expect(ids[0]).toBe(`${stamp(BURST[6])}-claude-session1`)
    expect(ids[6]).toBe(`${stamp(BURST[0])}-claude-session1`)

    // And it closes: an outside click is the way out of an Element Plus popover.
    // Measured on the served bundle -- Escape does not close this one (after
    // 900ms the panel was still `:visible`, with focus anywhere), while a click
    // on the hero did (0 visible). The wait is longer than the leave transition;
    // at 250ms the panel still counts as visible while it animates out, which
    // reads as "it did not close".
    await page.locator('.aim-attention-hero h3').click()
    await expect(popper).toHaveCount(0)
  })

  test('the card is still a five-row window', async ({ page }) => {
    mail = QUIET_TAIL
    await page.goto('/#/attention')
    // Fifteen ordinary rows arrived after the burst, so no receipt is inside the
    // five rows this card draws and no receipt row is drawn -- the same silence
    // the old expression produced here, and the case the live payload is in
    // (measured: 197 rows, 53 receipts, 0 in the newest five). The fix is about
    // what a drawn row counts; the window still decides which rows exist.
    await expect(rows(page)).toHaveCount(5)
    await expect(collapsed(page)).toHaveCount(0)
    const drawn = (await rows(page).allInnerTexts()).join(' ')
    expect(drawn).not.toContain('RECEIPT for')
    expect(drawn).not.toContain('receipts arrived')
  })
})
