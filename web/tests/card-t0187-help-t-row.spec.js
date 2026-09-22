/**
 * T-0187 -- "Help's `T-` row teaches the wrong model of the 115 ids it counts".
 *
 * Card text (channels/hello/tasks.jsonl, `created` 2026-09-22T07:12:32.207Z,
 * actor codex, owner claude-session1, tags frontend/help), verbatim acceptance:
 *
 *   1. "The `T-` row states the split with live counts: how many ids are on the
 *      record and how many are plan seeds."
 *   2. "It carries a sentence to the effect that a plan seed cannot be moved,
 *      assigned or recorded."
 *   3. "It no longer claims every `T-` id came from `aim task new`."
 *   4. "Both numbers are derived from `provenance`, so they cannot drift from the
 *      payload."
 *
 * Revision measured for this file -- `GET http://127.0.0.1:8777/api/revision` on
 * 2026-09-22:
 *
 *   fabric 1277f7e+dirty
 *   bundle 870b282+dirty, built 2026-09-22T08:40:07.787Z, source "vite build"
 *   stale: true
 *
 * `stale` is true: `web/src` has been edited since the served bundle was built, so
 * these assertions are about the bundle a reader actually loads on 8777.
 *
 * The row measured on that revision, live payload 175 tasks:
 *
 *   T- | a work item | 175 |
 *      the plan seeds it, or `aim task new` records it
 *      recorded in the store: 88 of 175; seeded and recorded both: 0;
 *      plan seeds the store has no record of: 87.
 *      A seed the store has no record of cannot be moved, assigned or recorded: ...
 *
 * Both tests below pass on that revision, so neither carries a `test.fail()`. The
 * card was filed when the row read `115 | minted by aim task new; the store is the
 * authority`, which was false of the 87 ids in it that `plan/plan.json` owns and
 * the store has never seen.
 *
 * Clause 4 is the reason this file fetches the payload instead of checking a
 * sentence: the numbers have to be the payload's, not this file's. It compares the
 * row against `/api/state`'s own counts of the three `provenance` values, and the
 * comparison is polled, because a peer writing a card while the test runs moves
 * the payload and a test that reads the two sides a second apart would report a
 * race as a defect.
 */
import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 1440, height: 1000 } })

/** The three `provenance` values `bin/aim` writes, whole-value, not `includes`. */
const SEED_ONLY = 'seed only (not yet in the store)'
const BOTH = 'store + seed'
const STORE_ONLY = 'store only'

/**
 * The payload's count of each universe, keyed the way `isPromise` splits them.
 *
 * The read is scoped to the viewer the page is reading as, and it has to be: the
 * board is gated, so `/api/state` without `?as=` answers in the *server's*
 * default identity while the page asks as the reader's. Measured on the served
 * board 2026-09-22: bare `/api/state` reports `viewer: claude-session1` and 148
 * tasks, `?as=human` reports `viewer: human` and 177. The page rendered 177 and
 * this probe, un-scoped, compared it against 148 -- so the test failed with "the
 * row's count column says 177; /api/state has 148 tasks" while the row was right
 * and the probe was asking a different question. Confirmed by the page's own
 * traffic rather than by inference: the board issues `/api/state?as=human` and
 * `/api/digest?as=human`, and nothing un-scoped.
 *
 * The viewer is read off the page rather than written down here. The shell's
 * header carries it in a select (`App.vue` renders `<el-select class="aim-viewer">`
 * whose selected cell reads `` `${id} · ${kind}` ``), and the id is the half
 * before the separator. The select draws *two* of those cells -- an empty
 * `el-select__input-wrapper is-hidden` ahead of the visible one -- so the read
 * takes the first cell that has text instead of the first cell, which measured
 * `""` and would have fallen back to the un-scoped endpoint this comment is
 * about. Measured live: the cells are `["", "human · human"]`. That is a DOM read
 * of a pane this file does not own and it is recorded as such, but the
 * alternatives are worse: the payload publishes the viewer only *inside* the
 * response to the question being asked, and starting the test board with
 * `--as human` would bake one identity into `playwright.config.js` and change
 * which board every other spec in the suite measures. With no select on the page
 * the read falls back to the un-scoped endpoint, so a shell that stops drawing it
 * fails loudly here rather than silently comparing two viewers.
 */
async function payloadCounts(page) {
  const viewer = await page.evaluate(() => {
    const text = [...document.querySelectorAll('.aim-viewer .el-select__selected-item')]
      .map((cell) => (cell.textContent || '').trim()).find(Boolean)
    return text ? text.split('·')[0].trim() : null
  })
  const response = await page.request.get(viewer ? `/api/state?as=${encodeURIComponent(viewer)}` : '/api/state')
  expect(response.ok(), `GET /api/state answered ${response.status()}`).toBe(true)
  const state = await response.json()
  const tasks = Object.values(state.tasks || {})
  const count = (value) => tasks.filter((task) => (task.provenance || '') === value).length
  return {
    viewer,
    viewerOnPayload: state.viewer,
    total: tasks.length,
    storeOnly: count(STORE_ONLY),
    both: count(BOTH),
    seedOnly: count(SEED_ONLY),
  }
}

/** The `T-` row of Help's identifier table, as the reader sees it. */
async function tRow(page) {
  await page.goto('/#/help')
  await page.waitForSelector('.aim-help table tbody tr', { state: 'visible' })
  await page.waitForTimeout(300)
  return page.evaluate(() => {
    const row = [...document.querySelectorAll('.aim-help table tbody tr')]
      .find((tr) => tr.querySelector('td code')?.textContent.trim() === 'T-')
    if (!row) return null
    const cells = [...row.querySelectorAll(':scope > td')]
    return {
      count: Number((cells[2]?.textContent || '').trim()),
      text: row.innerText.replace(/\s+/g, ' ').trim(),
    }
  })
}

/** `''` when the row and the payload say the same thing, else the disagreement. */
function disagreement(row, counts) {
  const numbers = (row.text.match(/\d+/g) || []).map(Number)
  const missing = [counts.total, counts.storeOnly, counts.both, counts.seedOnly]
    .filter((n) => !numbers.includes(n))
  if (row.count !== counts.total) {
    return `the row's count column says ${row.count}; /api/state has ${counts.total} tasks`
  }
  if (missing.length) {
    return `the split sentence is missing ${missing.join(', ')} of the payload's numbers `
      + `(store only ${counts.storeOnly}, store + seed ${counts.both}, seed only ${counts.seedOnly}, total ${counts.total}): "${row.text}"`
  }
  return ''
}

/**
 * Clauses 1 and 4: the split, with the payload's own numbers behind it.
 *
 * The three universes are counted from `provenance` on both sides -- the row's
 * template counts them with whole-value tests, and so does this file -- so a row
 * that stated a written-down "87 of them" would fail here as soon as the payload
 * moved.
 */
test('T-0187: the T- row states the split, in the payload\'s own numbers', async ({ page }) => {
  const row = await tRow(page)
  expect(row, 'the identifier table has no row whose prefix cell is `T-`').not.toBeNull()

  await expect.poll(async () => disagreement(row, await payloadCounts(page)), {
    timeout: 20000,
    message: 'the T- row and /api/state never agreed while the test polled; a peer may be writing tasks',
  }).toBe('')

  const counts = await payloadCounts(page)
  // The split is the whole claim: the parts have to add up to the number above
  // them, or the row counts three things that are not the thing it counted.
  expect(
    counts.storeOnly + counts.both + counts.seedOnly,
    `provenance adds up to ${counts.storeOnly + counts.both + counts.seedOnly} across three universes, `
    + `but /api/state holds ${counts.total} tasks`,
  ).toBe(counts.total)
})

/**
 * Clauses 2 and 3: the consequence, and the claim that is gone.
 *
 * Clause 3 is asserted as the absence of the two sentences the card measured --
 * "minted by `aim task new`" and "the store is the authority" -- rather than as
 * the presence of a replacement wording, because a row is allowed to say it any
 * way that is true, and what the card forbids is the specific false claim.
 */
test('T-0187: the row says a plan seed cannot be moved, and no longer claims every id came from the store', async ({ page }) => {
  const row = await tRow(page)
  expect(row, 'the identifier table has no row whose prefix cell is `T-`').not.toBeNull()

  expect(
    row.text,
    `the T- row does not say what a reader may do with a seed: "${row.text}"`,
  ).toMatch(/cannot be moved, assigned or recorded/i)

  expect(
    row.text,
    'the T- row still claims every id it counts was minted by `aim task new`; measured '
    + `on the red revision as "115 | minted by aim task new; the store is the authority": "${row.text}"`,
  ).not.toMatch(/minted by aim task new/i)

  expect(
    row.text,
    `the T- row still says the store is the authority for every id it counts: "${row.text}"`,
  ).not.toMatch(/the store is the authority/i)

  // The other half of "no longer claims": if any ids come from the plan file, the
  // row has to name the plan file as one of the two origins.
  const counts = await payloadCounts(page)
  if (counts.seedOnly > 0) {
    expect(
      row.text,
      `${counts.seedOnly} of ${counts.total} seeded ids have no record in the store, but the T- row `
      + `does not name the plan file as an origin: "${row.text}"`,
    ).toMatch(/plan/i)
  }
})
