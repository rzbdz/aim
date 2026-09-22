/**
 * T-0180: a promise is not work.
 *
 * These tests are the measurement from the task turned into an assertion. The
 * page's numbers were computed over `/api/state`'s merged `tasks` dict, which
 * holds two disjoint universes: the plan's static seeds and the items someone
 * actually recorded. Measured live before this: "4 overdue", none of them on the
 * record; "6 blocked", none of them; "1 in review", none of them.
 *
 * The fixture below is built so the two counts cannot coincide: six seeds that
 * look exactly like work (two overdue, two blocked, one in review) and three
 * recorded items (one genuinely overdue, one blocked, one in review). A page
 * that counts the merge shows 3 overdue / 3 blocked / 2 review; a page that
 * counts work shows 1 / 1 / 1. Every assertion here is that difference, or the
 * sentence that explains it to the reader.
 *
 * The recorded ids deliberately start at T-0181. T-0170..T-0179 are real ids in
 * the live store, so a pane whose rows widen their own reading -- Items lists
 * `board.tasks`, the whole merged board -- could pull a live card into a count
 * that this test believes it controls.
 */
import { expect, test } from '@playwright/test'

const SEED = (id, title, owner, status, priority, milestone, due, extra = {}) => ({
  id, title, owner, status, priority, milestone, tags: [], due,
  accept: `acceptance for ${id}`, blocked_by: [], visibility: 'published',
  provenance: 'seed only (not yet in the store)', events: [], comments: [], ...extra,
})

const RECORDED = (id, title, owner, status, priority, milestone, due, extra = {}) => ({
  ...SEED(id, title, owner, status, priority, milestone, due, extra),
  provenance: 'store only',
})

const STATE = {
  digest: 'records-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'],
  phase: 'RESOLVE',
  milestones: { M1: { id: 'M1', name: 'First milestone', due: '2026-10-01', accept: 'shipped' } },
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'agent', model: '' } },
  register: {},
  tasks: {
    // The plan's promises. T-0004 is the shape the leader pointed at: the plan
    // has parked a decision on them and dated it in the past.
    'T-0004': SEED('T-0004', 'Leader: approve the plan', 'human', 'ready', 'high', 'M1', '2026-09-15'),
    'T-0011': SEED('T-0011', 'Promised and already late', 'codex', 'doing', 'normal', 'M1', '2026-09-18'),
    'T-0012': SEED('T-0012', 'Promised and late too', 'codex', 'doing', 'normal', 'M1', '2026-09-19'),
    'T-0013': SEED('T-0013', 'Promised as blocked', 'codex', 'blocked', 'normal', 'M1', '2026-09-30'),
    'T-0014': SEED('T-0014', 'Promised as blocked too', 'codex', 'blocked', 'normal', 'M1', '2026-09-30'),
    'T-0015': SEED('T-0015', 'Promised as in review', 'codex', 'review', 'normal', 'M1', '2026-09-30'),
    // The record. One of each, so "counts only the recorded item" is checkable.
    'T-0181': RECORDED('T-0181', 'Recorded and genuinely late', 'codex', 'doing', 'normal', 'M1', '2026-09-18'),
    'T-0182': RECORDED('T-0182', 'Recorded and blocked', 'codex', 'blocked', 'normal', 'M1', '2026-09-30'),
    'T-0183': RECORDED('T-0183', 'Recorded and in review', 'codex', 'review', 'normal', 'M1', '2026-09-30'),
  },
  reports: {
    series: [], throughput: [], blocked: [], median_cycle: null,
    recorded: 3, with_history: 0, seed_only: 6,
  },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  // One fact, and it is a promise with nothing behind it -- the exact row the
  // drift card draws a `planned` mark on.
  drift: [{ id: 'T-0011', field: 'status', plan: 'doing', store: null }],
  withheld_tasks: 0,
  write: { enabled: false, as: '' },
}

test.describe('counts mean work, promises are promises', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify(STATE),
    }))
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
    }))
  })

  test('the Overdue signal counts the record, not the plan', async ({ page }) => {
    await page.goto('/#/attention')
    const overdue = page.locator('.aim-signal').filter({ hasText: 'Overdue' })
    // Nine items merged, three of them overdue. One is on the record.
    await expect(overdue.locator('span').first()).toHaveText('1')
    // The tile says the number is work, so a reader cannot read it as a promise.
    await expect(overdue).toContainText('on the record')
    // And the tile is still a way in: it lands on the filtered list, which holds
    // the item it counted. The list itself is the merged board -- `ItemsPane` is
    // another task's file, and it lists `board.tasks` (all nine here, four of them
    // late), so the count and the list disagree by the three seeded rows until
    // that pane derives the same way. It is asserted as "the counted item is
    // there" rather than as a row total, so the fix there does not have to be
    // written by this test.
    await overdue.click()
    await expect(page).toHaveURL(/#\/items\?onlyLate=1/)
    await expect(page.locator('.el-table__body')).toContainText('T-0181')
  })

  test('Blocked and Review count the record too, and the heading agrees', async ({ page }) => {
    await page.goto('/#/attention')
    const blocked = page.locator('.aim-signal').filter({ hasText: 'Blocked' })
    await expect(blocked.locator('span').first()).toHaveText('1')
    const review = page.locator('.aim-signal').filter({ hasText: 'Review' })
    await expect(review.locator('span').first()).toHaveText('1')

    // The hero's own sentence is a count over the same lists, so it moves with
    // them: a page whose summary says 3 and whose tile says 1 is two answers.
    const hero = page.locator('.aim-attention-hero')
    await expect(hero).toContainText('1 overdue')
    await expect(hero).toContainText('1 blocked')
    await expect(hero).toContainText('1 review')

    // The merged board holds 3 blocked and 2 review, and the promise card says so
    // out loud ("6 promises in the plan"), so "1" is a choice this page made and
    // not a fixture that forgot to seed anything.
    await expect(page.locator('.aim-promise-card')).toContainText('6 promises in the plan')
    await expect(page.locator('.aim-attention-columns .aim-attention-row')).toHaveCount(3)
  })

  test('the promise count is spoken out loud, separately from work', async ({ page }) => {
    await page.goto('/#/attention')
    const promises = page.locator('.aim-promise-card')
    await expect(promises).toBeVisible()
    // Six seeds, one of them addressed to the human.
    await expect(promises).toContainText('6 promises in the plan, 1 of them need you')
    // It says which row is the human's, and it does not call it work.
    await expect(promises.locator('.aim-attention-row')).toHaveCount(1)
    await expect(promises.locator('.aim-attention-row')).toContainText('T-0004')
    await expect(promises.locator('.aim-attention-row')).toContainText('decision for you')

    // The promise card is not one of the six work signals, and the promise rows
    // are not in "Work needing you now" -- that is the whole distinction.
    await expect(page.locator('.aim-attention-signals .aim-signal')).toHaveCount(6)
    // The list is the other half of the count: a signal of 1 over a list of four
    // is a page disagreeing with itself. Both are asserted as sets, not as single
    // nodes, because "does not contain" over a list of locators is a strict-mode
    // error rather than a check.
    const workIds = await page.locator('.aim-attention-columns .aim-attention-row .aim-mono').allTextContents()
    expect(workIds.sort()).toEqual(['T-0181', 'T-0182', 'T-0183'])
    const workText = (await page.locator('.aim-attention-columns .aim-attention-row').allTextContents()).join(' ')
    expect(workText).not.toContain('T-0011')
    expect(workText).not.toContain('Promised and already late')
  })

  test('a seed row wears the promise mark and a recorded row does not', async ({ page }) => {
    await page.goto('/#/attention')
    // The promise row.
    const promiseRow = page.locator('.aim-promise-card .aim-attention-row').first()
    await expect(promiseRow.locator('.aim-promise')).toHaveCount(1)
    await expect(promiseRow.locator('.aim-promise')).toHaveText('planned')
    // One mark, and it explains itself in a sentence rather than in a word.
    const title = await promiseRow.locator('.aim-promise').getAttribute('title')
    expect(title).toMatch(/not a recorded item/i)

    // The work row carries no promise mark at all.
    const workRow = page.locator('.aim-attention-columns .aim-attention-row').first()
    await expect(workRow).toContainText('T-0182')
    await expect(workRow.locator('.aim-promise')).toHaveCount(0)
  })

  test('the actable card comes before the diagnostics', async ({ page }) => {
    await page.goto('/#/attention')
    // Assert the reading order, not just the presence: the drift card used to sit
    // above the only card the leader could act on and push it below the fold.
    // Wait for the pane before measuring it: every other assertion in this file
    // auto-waits through `expect`, and an `evaluate` does not. Without this the
    // order check races the lazy route chunk and reads a null root, which is a
    // failure that says nothing about the order it is testing.
    await expect(page.locator('#drift')).toBeVisible()
    const order = await page.evaluate(() => {
      const doc = document.querySelector('.aim-attention')
      const at = (selector) => doc.querySelector(selector)
      // `compareDocumentPosition` is the cheap primitive for "which comes first";
      // indexing into every descendant instead would be quadratic on a page that
      // draws a hundred-odd rows.
      const before = (a, b) => a && b && Boolean(a.compareDocumentPosition(b) & 4)
      return {
        decisionsBeforePromises: before(at('#leader-decisions'), at('.aim-promise-card')),
        promisesBeforeWork: before(at('.aim-promise-card'), at('.aim-attention-columns')),
        workBeforeMilestones: before(at('.aim-attention-columns'), at('.aim-attention-milestones')),
        milestonesBeforeDrift: before(at('.aim-attention-milestones'), at('#drift')),
        present: Boolean(at('.aim-promise-card') && at('.aim-attention-columns')
          && at('#drift') && at('.aim-attention-milestones')),
      }
    })
    expect(order.present).toBe(true)
    expect(order.promisesBeforeWork).toBe(true)
    expect(order.workBeforeMilestones).toBe(true)
    // The drift card is the last thing on the page: it reports a disagreement
    // between the plan and the record, and the reader meets it after everything
    // they can act on and every report about the work itself.
    expect(order.milestonesBeforeDrift).toBe(true)
    // On this fixture there is no phase request, so the decisions card is absent
    // and the promise card is the first thing on the page.
    // The decisions card is absent on this fixture (no phase request), so the
    // comparison is unavailable rather than false -- asserted as such, because
    // "false" would also be what a bug that moved the card produced.
    await expect(page.locator('#leader-decisions')).toHaveCount(0)
    expect(order.decisionsBeforePromises).toBeNull()
  })

  test('a drift row with nothing in the store is marked as a promise', async ({ page }) => {
    await page.goto('/#/attention')
    const drift = page.locator('#drift')
    await expect(drift).toBeVisible()
    await expect(drift).toContainText('T-0011')
    await expect(drift).toContainText('not recorded')
    // The row says which of its two halves is the promise: the plan has one and
    // the store does not, so nothing about this row is work.
    await expect(drift.locator('.aim-attention-row').first().locator('.aim-promise')).toHaveCount(1)
  })
})
