import { expect, test } from '@playwright/test'

/**
 * T-0187: the identifier table has to be true of every id it counts.
 *
 * Measured live on 8777, 2026-09-22: the `T-` row rendered
 *
 *     T- | a work item | 161 | minted by aim task new; the store is the authority
 *
 * and 87 of those 161 carried `provenance: "seed only (not yet in the store)"`.
 * Both clauses of the sentence were false of those 87 ids, and the count had
 * moved 115 -> 151 -> 161 without the sentence becoming true -- so this is not a
 * number that drifted, it is a sentence about *which* ids are counted. The
 * consequence is not cosmetic: `aim task move --id T-0042` answers
 * `no such task: T-0042`, because the store folds events and there is no event
 * for an id that only the plan file has ever mentioned.
 *
 * So the assertion below is the card's acceptance, mechanised: every count the
 * row states, added up, equals the count at the top of the row -- the row is
 * true of every id it counts, or it fails.
 *
 * The numbers are computed from the fixture in this file, never written into the
 * test: a spec that hardcodes "87" is a second copy of the thing that was wrong.
 */

const TASK = (id, title, provenance, extra = {}) => ({
  id, title, owner: 'codex', status: 'backlog', priority: 'normal', milestone: '', tags: [],
  due: '', accept: '', blocked_by: [], visibility: 'published', provenance, events: [], comments: [],
  ...extra,
})

/**
 * Three universes, in the proportions the live board had, plus the shape that
 * does not exist yet.
 *
 * `store + seed` is a real value of `provenance` (`aimboard/fold.py:90`: an id
 * the plan seeded that the store also recorded) and it is countable today at 0
 * items. It is in the fixture because the sentence the row renders has to be
 * true for a board where it is not zero -- "a seed cannot be moved" is false for
 * that one, and a fixture of two universes cannot tell the two sentences apart.
 * The fourth class is not a value any code writes: it is here to pin what the
 * row does with a provenance it has never seen, which is the failure the card
 * names (a number that lands in a bucket by accident).
 */
const SEEDS = ['T-0001', 'T-0002', 'T-0003', 'T-0004']
const RECORDED = ['T-0156', 'T-0157', 'T-0158']
const BOTH = ['T-0200']
const STRANGE = { id: 'T-0900', provenance: 'imported from a spreadsheet' }

const tasks = {}
for (const id of SEEDS) tasks[id] = TASK(id, `${id} promised in the plan`, 'seed only (not yet in the store)')
for (const id of RECORDED) tasks[id] = TASK(id, `${id} recorded`, 'store only')
for (const id of BOTH) tasks[id] = TASK(id, `${id} seeded and recorded`, 'store + seed')
tasks[STRANGE.id] = TASK(STRANGE.id, 'an id from nowhere', STRANGE.provenance)

const STATE = {
  digest: 'help-identifiers-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'done'],
  terminal: ['done'],
  phase: 'RESOLVE',
  // Two sources on purpose: the M row used to say every milestone is written by
  // hand in plan/plan.json, and M6 in the live plan comes from dogfood.json.
  milestones: {
    M1: { id: 'M1', name: 'First', source: 'plan.json' },
    M6: { id: 'M6', name: 'Dogfooding', source: 'dogfood.json' },
  },
  agents: { human: { kind: 'human', model: '' } },
  register: {
    decisions: [{ id: 'D5', decision: 'a decision', because: 'a reason' }],
    risks: [{ id: 'R1', risk: 'a risk', owner: 'codex', kill_if: 'an observation' }],
  },
  tasks,
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: false, as: '' },
}

/** Every id whose provenance is exactly this value. */
const withProvenance = (value) => Object.values(tasks).filter((t) => t.provenance === value).map((t) => t.id)

async function serveHelp(page, state = STATE) {
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(state),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: state.digest }),
  }))
  await page.goto('/#/help')
  await expect(page.locator('.aim-page h2')).toHaveText('Help & concepts')
}

/**
 * The identifier table's rows, addressed by the card the table lives in.
 *
 * The row order is asserted rather than assumed: a test that silently reads the
 * wrong row would pass forever, and the whole defect here is a row that was read
 * as saying something it did not say.
 */
async function identifierRows(page) {
  const table = page.locator('.el-card').filter({ hasText: 'Identifiers — what a bare' })
    .locator('.aim-help-table')
  await expect(table).toHaveCount(1)
  const rows = table.locator('tbody tr')
  const prefixes = await rows.locator('td:first-child').allInnerTexts()
  expect(prefixes.map((p) => p.trim())).toEqual(['T-', 'M', 'D', 'R'])
  return rows
}

test.describe('the identifier table is true of every id it counts', () => {
  test('the T- row states the split, and the split adds up to the number it counts', async ({ page }) => {
    await serveHelp(page)
    const row = (await identifierRows(page)).first()
    const text = await row.innerText()

    const counted = Number(await row.locator('td').nth(2).innerText())
    expect(counted).toBe(Object.keys(tasks).length)

    // The acceptance, in one line: every clause the row states is a number, and
    // they account for the count above them. A row that is false of one id --
    // the old one was false of 87 -- cannot satisfy this.
    const stated = [...text.matchAll(/(\d+) of \d+|[a-z ]+: (\d+)/g)]
      .map((m) => Number(m[1] ?? m[2]))
    expect(stated.length).toBeGreaterThan(0)
    expect(stated.reduce((a, b) => a + b, 0)).toBe(counted)

    // And each clause is the count of its own provenance, not a coincidence of
    // totals that happen to add up.
    expect(text).toContain(`recorded in the store: ${withProvenance('store only').length} of ${counted}`)
    expect(text).toContain(`seeded and recorded both: ${withProvenance('store + seed').length}`)
    expect(text).toContain(
      `plan seeds the store has no record of: ${withProvenance('seed only (not yet in the store)').length}`)
    expect(text).toContain(`provenance this row does not know: 1`)
  })

  test('the T- row stops claiming every id came from aim task new', async ({ page }) => {
    await serveHelp(page)
    const text = await (await identifierRows(page)).first().innerText()

    // The sentence that was measured false: "the store is the authority" is a
    // promise about a record that does not exist for a plan seed.
    expect(text).not.toContain('the store is the authority')
    // The new `where` names both provenances, so the two clauses agree with the
    // split underneath them instead of contradicting it.
    expect(text).toContain('the plan seeds it, or `aim task new` records it')
  })

  test('the T- row says a plan seed cannot be moved, assigned or recorded', async ({ page }) => {
    await serveHelp(page)
    const text = await (await identifierRows(page)).first().innerText()
    expect(text).toContain('cannot be moved, assigned or recorded')
    // The condition is part of the sentence on purpose: a `store + seed` id is
    // movable, so "a plan seed cannot be moved" without it would be a new false
    // sentence in a test that exists to stop false sentences.
    expect(text).toContain('the store has no record of')
  })

  /**
   * The other direction, and the one a snapshot test would miss.
   *
   * A row whose counts are written down as "87 seeds, 63 recorded" is true today
   * and false the moment the board moves -- which is what happened between the
   * two measurements of this card (115 -> 151 -> 161). With every item on the
   * record, the same code path has to say so, and it has to say `0` out loud
   * rather than dropping the clause: `0` and "this row did not look" are
   * different facts and a reader cannot tell them apart from an absent clause.
   */
  test('on a board with no seeds, the row says zero rather than describing a board it is not on', async ({ page }) => {
    const allRecorded = {
      ...STATE,
      digest: 'help-identifiers-all-recorded',
      tasks: Object.fromEntries(Object.entries(tasks)
        .map(([id, t]) => [id, { ...t, provenance: 'store only' }])),
    }
    await serveHelp(page, allRecorded)
    const row = (await identifierRows(page)).first()
    const text = await row.innerText()

    expect(Number(await row.locator('td').nth(2).innerText())).toBe(Object.keys(tasks).length)
    expect(text).toContain(`recorded in the store: ${Object.keys(tasks).length} of ${Object.keys(tasks).length}`)
    expect(text).toContain('seeded and recorded both: 0')
    expect(text).toContain('plan seeds the store has no record of: 0')
  })

  /**
   * The same audit, applied to the row that was wrong for the same reason.
   *
   * The card names the `T-` row; the `M` row's sentence was "written by hand in
   * plan/plan.json" while one of the live ten milestones (M6, Dogfooding) is
   * written in plan/dogfood.json. A count is a claim about a file, so the file
   * has to come from the payload too.
   */
  test('the M- row names every plan file its count actually came from', async ({ page }) => {
    await serveHelp(page)
    const row = (await identifierRows(page)).nth(1)
    const text = await row.innerText()

    expect(Number(await row.locator('td').nth(2).innerText())).toBe(Object.keys(STATE.milestones).length)
    expect(text).toContain('plan/dogfood.json')
    expect(text).toContain('plan/plan.json')
  })
})
