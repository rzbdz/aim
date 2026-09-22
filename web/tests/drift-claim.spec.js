import { expect, test } from '@playwright/test'

/**
 * T-0190: the plan page's resolution rule has to be true of every element it counts.
 *
 * Measured on the live board before this: `#/plan` rendered
 *
 *   ... where the two disagree the store wins, and the 87 disagreement(s) are on
 *   the attention page. 57 item(s) have no due date, which in a plan is a sentence
 *   without a verb.
 *
 * and all 87 entries in `/api/state.drift` are `{field: "status", plan: <status>,
 * store: null}` -- every one a plan seed with no record at all, so there is no
 * store value for the store to win with. The sentence stated a resolution rule
 * for 100% of the count it carried, and the rule had never applied to any of
 * them; the payload's `store: null` was never surfaced as the fact it is. The
 * page also drew 0 of the rows the number was about, so the only evidence was a
 * link into another pane.
 *
 * The fixture below is the discriminating one, and the numbers are chosen so that
 * no wrong implementation passes by coincidence:
 *
 *   never-recorded rows  24    (a count reading the whole drift prints 26)
 *   differing rows        2    (a count reading the never-recorded list prints 24)
 *   undated items        11    (a count over the merged board prints 11, of which
 *                              7 seeds and 4 recorded items -- one number cannot
 *                              say both, which is the second half of the defect)
 *
 * What would falsify this file: a `store` value of `""` being treated as a value
 * rather than as absence (the row filter would then move a real row into the
 * "differ" list), or a drift row for an id the board does not hold (the fixture
 * keeps every id on the board, so the row renderer is exercised but the missing-id
 * path is not -- that belongs to T-0159's TaskLink).
 */

const SEED = 'seed only (fixture)'
const RECORDED = 'store only'

const TASK = (id, status, extra = {}) => ({
  id, title: `item ${id}`, owner: 'codex', status, priority: 'normal', milestone: '',
  tags: [], accept: `acceptance for ${id}`, blocked_by: [], visibility: 'published',
  provenance: RECORDED, events: [], comments: [], ...extra,
})

/** 24 seeds the store has never seen -- the shape of all 87 live rows. One of them
 *  carries `plan: null`, which `aimboard/fold.py:126` emits for a seed with no
 *  status, so the pane has to say "the plan says nothing" rather than draw a
 *  blank cell that reads as a value. */
const NEVER = Array.from({ length: 24 }, (_, i) => ({
  id: `T-01${String(i).padStart(2, '0')}`,
  field: 'status',
  plan: i === 3 ? null : ['backlog', 'ready', 'doing'][i % 3],
  store: null,
}))

/** Two rows where both sides hold a value and the values differ. These are the
 *  only rows on which "the store wins" is a statement about anything. */
const DIFFER = [
  { id: 'T-0201', field: 'status', plan: 'ready', store: 'doing' },
  { id: 'T-0202', field: 'owner', plan: 'codex', store: 'human' },
]

/** The seeds without a due date. `plan/plan.json` is what dates a seed, so an
 *  undated seed is a hole in the plan rather than a task someone forgot. */
const UNDATED_SEEDS = 7
const UNDATED_RECORDED = 4

const tasks = {}
NEVER.forEach((row, i) => {
  tasks[row.id] = TASK(row.id, row.plan || 'backlog', {
    provenance: SEED, due: i < UNDATED_SEEDS ? '' : '2026-10-01',
  })
})
tasks['T-0201'] = TASK('T-0201', 'doing', { due: '2026-09-30' })
tasks['T-0202'] = TASK('T-0202', 'backlog', { owner: 'human', due: '2026-09-30' })
for (let i = 0; i < UNDATED_RECORDED; i += 1) tasks[`T-03${i}`] = TASK(`T-03${i}`, 'ready')

export const COUNTS = {
  neverRecorded: NEVER.length,
  differing: DIFFER.length,
  total: NEVER.length + DIFFER.length,
  undated: UNDATED_SEEDS + UNDATED_RECORDED,
  undatedSeeds: UNDATED_SEEDS,
  undatedRecorded: UNDATED_RECORDED,
}

export const STATE = {
  digest: 'drift-claim-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'done'],
  terminal: ['done'],
  phase: 'RESOLVE',
  milestones: {},
  agents: { human: { kind: 'human', model: '' } },
  register: {},
  tasks,
  reports: { series: [], throughput: [], blocked: [], median_cycle: null, recorded: 6, seed_only: 24,
             with_history: 0 },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  drift: [...NEVER, ...DIFFER],
  withheld_tasks: 0,
  write: { enabled: false, as: '' },
}

test.describe('the drift claim is true of every row it counts', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify(STATE),
    }))
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
    }))
    await page.goto('/#/plan')
  })

  /** The sentence, found by what it says rather than by its position: another
   *  alert anywhere in the shell would make `.first()` an assertion about the
   *  shell's layout instead of about this claim. */
  const claim = (page) => page.locator('.el-alert').filter({ hasText: 'plan/*.json is the leader' })

  test('an absent record is named as absent, not resolved by a comparison', async ({ page }) => {
    await expect(claim(page)).toBeVisible()
    const text = (await claim(page).innerText()).replace(/\s+/g, ' ')

    // The two facts, in the sentence's own words: the store has no value for these
    // rows, and the count it names is the count of those rows -- not the drift total.
    expect(text).toContain('not recorded')
    expect(text).toContain(`${COUNTS.neverRecorded} plan item(s) are in the plan and not in the store yet`)
    expect(text).not.toContain(`${COUNTS.total} plan item(s)`)

    // The old wording, which this card exists to remove. Both of these fail against
    // `PlanPane.vue` at git HEAD.
    expect(text).not.toMatch(/disagreement\(s\)/)
    expect(text).not.toMatch(/where the two disagree the store wins/)

    // The store-wins rule is stated, and it is stated about the rows that have two
    // values -- one number, matching the list that is drawn, and not the 24.
    expect(text).toContain(`both sides hold a value and differ on ${COUNTS.differing} field(s)`)
    expect(text).not.toContain(`${COUNTS.neverRecorded} field(s)`)
  })

  test('the undated count is split by what the count is about', async ({ page }) => {
    const text = (await claim(page).innerText()).replace(/\s+/g, ' ')

    // An undated seed is a plan with a hole in it; an undated recorded item is a
    // task nobody scheduled. One number over the merged board says neither, and
    // the old sentence collected the noun "in a plan" from one universe and the
    // count from the other.
    expect(text).toContain(
      `Of the ${COUNTS.undated} item(s) with no due date, ${COUNTS.undatedSeeds} are plan promises `
      + `waiting on a date and ${COUNTS.undatedRecorded} are recorded items with a date nobody set`)
    expect(text).not.toMatch(/have no due date, which in a plan is a sentence without a verb/)
  })

  test('the rows the count is about are drawn where the count is stated', async ({ page }) => {
    // On this page: the number and its rows are one thing, and the reader is not
    // sent to another pane to find out what was counted (T-0183 measured that link
    // landing without scrolling, which is the weaker version of the same dead end).
    await expect(page).toHaveURL(/#\/plan/)
    const card = page.locator('#plan-drift')
    await expect(card).toBeVisible()
    await expect(card.locator('article')).toHaveCount(20)
    await expect(card).toContainText('24 plan item(s) are not in the store yet')

    // Bounded, with the remainder stated as a number -- "more" is not a number.
    // Found by name: every row's id is a TaskLink button, so a bare `getByRole`
    // would be ambiguous with the 20 rows.
    await card.getByRole('button', { name: /show all 24 \(4 more\)/ }).click()
    await expect(card.locator('article')).toHaveCount(COUNTS.neverRecorded)
    await expect(card).toContainText('show only the first 20')
  })

  test('every drawn row says the store has no record, and none of them claim a rule', async ({ page }) => {
    const card = page.locator('#plan-drift')
    const rows = card.locator('article')
    await expect(rows).toHaveCount(20)

    for (let i = 0; i < 5; i += 1) {
      await expect(rows.nth(i)).toContainText('store has')
      await expect(rows.nth(i)).toContainText('not recorded')
    }
    // The store-wins rule belongs to the rows that have two values, so it must not
    // appear in this card at all.
    await expect(card).not.toContainText('the store wins')
    // And the card's number is its own list: 26 rows exist in the payload, 24 of
    // them belong here, and a header that printed the total would be the same
    // defect one level down.
    await expect(card).not.toContainText(`${COUNTS.total} plan item(s) are`)
  })

  test('PromiseTag marks the seed rows, the same mark the rest of the board draws', async ({ page }) => {
    const card = page.locator('#plan-drift')
    await expect(card.locator('article .aim-promise')).toHaveCount(20)
    const tag = card.locator('article').first().locator('.aim-promise')
    await expect(tag).toHaveText('planned')
    await expect(tag).toHaveAttribute('title', /store has never seen/)
  })

  test('the rows where the store does hold a value are drawn as their own list', async ({ page }) => {
    const differs = page.locator('#plan-drift-differs')
    await expect(differs).toBeVisible()
    await expect(differs.locator('article')).toHaveCount(COUNTS.differing)
    // Both values on the row, and no promise mark: this row is a disagreement
    // between two records, not a seed.
    await expect(differs.locator('article').first()).toContainText('doing')
    await expect(differs.locator('article .aim-promise')).toHaveCount(0)

    // And the never-recorded list does not absorb them: 24 rows there, 2 here, 26
    // in the payload.
    await expect(page.locator('#plan-drift article')).toHaveCount(20)
    await expect(page.locator('#plan-drift .aim-promise')).toHaveCount(20)
  })
})
