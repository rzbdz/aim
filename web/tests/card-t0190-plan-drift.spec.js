import { expect, test } from '@playwright/test'

/**
 * T-0190 -- "Plan claims the store wins about 87 disagreements that have no store value".
 *
 * The card's acceptance, verbatim:
 *
 *   1. The wording distinguishes an absent record from a disagreeing value:
 *      `store = not recorded` for a null store, and the sentence no longer claims the
 *      store overrode a value that does not exist.
 *   2. The rows are readable where the count is stated -- on `#/plan` itself, bounded
 *      with a stated "M more" if needed -- rather than only behind a link.
 *   3. `PromiseTag` marks the seed rows, so the page agrees with the rest of the board.
 *
 * What was measured on the live board before this file: `/api/state.drift` held 87
 * rows, every one `{field: "status", plan: <status>, store: null}`, and `#/plan`
 * rendered a sentence about those 87 that ended "where the two disagree the store
 * wins" -- a resolution rule stated for a comparison that had never happened for any
 * of them, because the store had no value on any row. The pane drew zero of the rows
 * and offered a link into the attention page instead.
 *
 * The two fixtures below are chosen so that a wrong implementation cannot pass by
 * coincidence. The first is all-null (the live shape); the second adds three rows
 * that genuinely hold two values, so a page that prints one number for both kinds of
 * row is caught: a count over the whole drift prints 27, a count over the
 * never-recorded rows prints 24, and the two numbers the page must state are 24 and 3.
 *
 * Revision measured for this file: recorded in the report that carried it, and read
 * from `GET http://127.0.0.1:8777/api/revision` at run time by the first test, because
 * the served bundle moves.
 */

const SEED = 'seed only (not yet in the store)'
const RECORDED = 'store only'
const NEVER = 24
const DIFFER = 3

const task = (id, extra = {}) => ({
  id, title: `item ${id}`, owner: 'codex', status: 'backlog', priority: 'normal',
  milestone: '', tags: [], accept: `acceptance for ${id}`, blocked_by: [],
  visibility: 'published', provenance: RECORDED, events: [], comments: [], ...extra,
})

/** 24 seeds with no record at all: `store: null` is the whole population. */
const neverRows = Array.from({ length: NEVER }, (_, i) => ({
  id: `T-11${String(i).padStart(2, '0')}`, field: 'status',
  plan: ['backlog', 'ready', 'doing'][i % 3], store: null,
}))

/** Three rows where both sides genuinely hold a value, which is the only condition
 *  under which "the store wins" is a statement about anything. */
const differRows = [
  { id: 'T-1201', field: 'status', plan: 'ready', store: 'doing' },
  { id: 'T-1202', field: 'owner', plan: 'codex', store: 'human' },
  { id: 'T-1203', field: 'due', plan: '2026-09-21', store: '2026-09-20' },
]

const tasks = {}
neverRows.forEach((row) => { tasks[row.id] = task(row.id, { provenance: SEED, due: '2026-10-01' }) })
tasks['T-1201'] = task('T-1201', { status: 'doing' })
tasks['T-1202'] = task('T-1202', { owner: 'human' })
tasks['T-1203'] = task('T-1203', { due: '2026-09-20' })

const state = (drift) => ({
  digest: `plan-drift-${drift.length}`,
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'done'],
  terminal: ['done'],
  phase: 'CROSS_EXAMINE',
  viewer: 'human',
  viewer_kind: 'human',
  write: { enabled: false, as: '' },
  milestones: {},
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'codex', model: '' } },
  register: {},
  tasks,
  reports: { series: [], throughput: [], blocked: [], median_cycle: null, recorded: 3, seed_only: NEVER },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  drift,
  withheld_tasks: 0,
})

const ALL_NULL = state(neverRows)
const MIXED = state([...neverRows, ...differRows])

async function open(page, doc = ALL_NULL) {
  await page.route('**/api/state**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify(doc),
  }))
  await page.route('**/api/digest**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: doc.digest }),
  }))
  await page.goto('/#/plan')
  await expect(page.locator('.el-alert')).toBeVisible()
}

const text = (page) => page.evaluate(() => document.body.innerText.replace(/\s+/g, ' '))

/** The card that states the never-recorded count, found by what it says. */
const neverCard = (page) => page.locator('.el-card').filter({ hasText: /not in the store yet/ }).first()

/** The card that draws the rows where the store does hold a value, if there is one. */
const differCard = (page) => page.locator('.el-card').filter({ hasText: /store wins/ }).first()

test.describe('T-0190 the plan page states a rule only about rows it holds a value for', () => {
  test('revision: the served bundle is named', async ({ page }) => {
    const rev = await page.request.get('http://127.0.0.1:8777/api/revision')
    expect(rev.ok()).toBe(true)
    const body = await rev.json()
    // Not an assertion about the bundle's content: a measurement that cannot say
    // which revision produced it is the card's own subject.
    console.log(`measured bundle ${JSON.stringify(body.bundle)} stale=${body.stale}`)
    expect(body.bundle && body.bundle.revision, 'the board must name the revision it serves').toBeTruthy()
  })

  test('a null store is "not recorded", and the count is never called a disagreement', async ({ page }) => {
    await open(page)
    const body = await text(page)

    // Clause 1, stated positively: the population is named as absent, not as a
    // conflict, and the number beside it is the number of such rows.
    expect(body).toContain('not recorded')
    expect(body, 'the never-recorded count must be the drift population with store: null (24)')
      .toContain(`${NEVER} plan item(s)`)

    // Clause 1, stated negatively: the two phrases the card exists to remove.
    expect(body).not.toMatch(/disagreement\(s\)/)
    expect(body).not.toMatch(/where the two disagree the store wins/)

    // And the rule must not be attached to this count: a page that says the store
    // wins over the 24 rows is the defect, whatever words it uses.
    expect(body).not.toMatch(new RegExp(`\\b${NEVER}\\b[^.]{0,120}store wins`, 'i'))
    expect(body).not.toMatch(new RegExp(`store wins[^.]{0,120}\\b${NEVER}\\b`, 'i'))
  })

  test('the store-wins rule is stated about the rows that hold two values, not the whole drift', async ({ page }) => {
    await open(page, MIXED)
    const body = await text(page)

    // The two numbers, both stated, and neither standing for the other.
    expect(body, 'the absent-record count must be 24, not the drift total (27)').toContain(`${NEVER} plan item(s)`)
    expect(body, 'the drift total must not be printed as the never-recorded count').not.toContain(`${NEVER + DIFFER} plan item(s)`)

    const card = differCard(page)
    await expect(card, 'rows where both sides hold a value must be drawn as their own list').toBeVisible()
    const differText = (await card.innerText()).replace(/\s+/g, ' ')
    expect(differText, `the store-wins list must be the ${DIFFER} rows that hold a value on both sides`)
      .toMatch(new RegExp(`\\b${DIFFER}\\b`))
    expect(differText).not.toMatch(new RegExp(`\\b${NEVER}\\b`))

    // The rule itself, where it can apply.
    expect(differText).toMatch(/store wins/i)
  })

  test('the rows the count is about are drawn on #/plan itself, bounded, with the remainder stated', async ({ page }) => {
    await open(page)
    await expect(page).toHaveURL(/#\/plan/)

    const card = neverCard(page)
    await expect(card).toBeVisible()
    // "where the count is stated": the sentence and its rows are one card, not a link.
    const header = (await card.innerText()).replace(/\s+/g, ' ')
    expect(header).toContain(`${NEVER} plan item(s)`)

    const drawn = await card.locator('article').count()
    expect(drawn, 'the card stating the count must draw rows of its own').toBeGreaterThan(0)
    expect(drawn, `the card must be bounded: ${drawn} rows drawn for ${NEVER} rows counted`)
      .toBeLessThan(NEVER)
    // The remainder is a number, not the word "more": a reader told 4 can decide.
    const remainder = NEVER - drawn
    expect(header, `the card must state "${remainder} more"`).toMatch(new RegExp(`\\b${remainder}\\b\\s*more`))

    // And the first drawn row says what the store holds, in the store's own words.
    expect(await card.locator('article').first().innerText()).toContain('not recorded')
  })

  test('the seed rows carry the promise mark the rest of the board draws', async ({ page }) => {
    await open(page)
    const card = neverCard(page)
    const drawn = await card.locator('article').count()
    const marks = card.locator('article .aim-promise')
    await expect(marks).toHaveCount(drawn)

    // The same mark, not a per-pane look-alike: the landing page's promise card
    // draws the same component, so the class list and the visible word must match.
    await page.goto('/#/')
    const reference = page.locator('.aim-promise').first()
    await expect(reference).toBeVisible()
    const referenceText = (await reference.innerText()).trim()
    const referenceClass = await reference.getAttribute('class')

    await page.goto('/#/plan')
    const inCard = neverCard(page).locator('article .aim-promise').first()
    await expect(inCard).toBeVisible()
    expect((await inCard.innerText()).trim()).toBe(referenceText)
    expect(await inCard.getAttribute('class')).toBe(referenceClass)
  })
})
