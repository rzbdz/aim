import { expect, test } from '@playwright/test'

/**
 * T-0166 -- "All tag filters share multi-select AND semantics and URL round-tripping".
 *
 * Card text (channels/hello/tasks.jsonl, `created` 2026-09-22T03:02:32.182Z),
 * verbatim:
 *
 *   "Every surface with a tag filter uses the same multi-select behavior and AND
 *    semantics; selecting two tags narrows to items containing both; the URL
 *    round-trips repeated tag parameters and restores the selected set; clear
 *    resets the full array; Items and Gantt match Kanban instead of keeping a
 *    single tag value; tests cover two tags on each tag-filtering surface"
 *
 * The three surfaces that carry a tag filter are Items, Gantt and Kanban
 * (`web/src/panes/*.vue`, `useQueryFilters({...})` with a `tag` key). So one
 * file, one clause set per surface, and the verdict is per surface.
 *
 * VERDICT, re-measured 2026-09-22T11:50Z against bundle 9e6116d47ac1+dirty
 * (`/api/revision` stale false): all three surfaces pass. The measurement below
 * is kept as the card's history; each line says what the defect was and where it
 * went.
 *
 *   kanban  PASS  -- was already multi-select and AND; unchanged.
 *   items   PASS  -- was `tag: ''` with `includes(filters.tag)`, so a second pick
 *                    *replaced* the first and the AND step showed [T-A1, T-B1],
 *                    the two items carrying *either* tag. `ItemsPane.vue` holds
 *                    `tag: []` with `.every(...)` now.
 *   gantt   PASS  -- the same defect, plus a second one this file could not see
 *                    while it was red: `GanttPane.vue` also held a single value,
 *                    and its header had been rewritten by T-0188 from
 *                    `timeline — 2 of 4 dated item(s)` to a sentence that states
 *                    the filter count apart from the board's own split. So this
 *                    file's `ganttCount` was throwing `gantt header did not name a
 *                    count` on its first assertion, which is a copy change and not
 *                    a filter defect. The instrument reads the sentence the pane
 *                    renders now; see it for the shape.
 *
 * Both `test.fail()` markers are gone, on the JSON reporter's own evidence
 * (`expectedStatus: 'passed'` / `status: 'passed'`), and no assertion in this file
 * was relaxed: the clause set is the one that was written when the card was
 * filed, and the header pattern now captures the same two numbers it always did.
 *
 * This file drives the *served* board -- the bundle a reader actually loads --
 * and stubs `/api/state` with `page.route` so the tag combination under test is
 * the fixture's and not whatever the live fabric happens to hold today.
 *
 * Revision measured at `GET http://127.0.0.1:8777/api/revision`, twice -- before
 * writing and at the final run, because a peer committed and rebuilt this tree
 * while the file was being measured:
 *
 *   first  fabric 830dd79+dirty, bundle 830dd79+dirty built 2026-09-22T08:27:38.609Z,
 *          source_sha256 34d4255feff1d4a6cb6b3265da7583bc6ef6163b7dd7f7b64c620f1fcba62232,
 *          stale true, front_end_sha256 4cd14431602ba5d9b32e9ac37d619b8c11340689c417d32a30c588dd6cf208d9
 *   final  fabric f0c4d64+dirty, bundle f0c4d64+dirty built 2026-09-22T08:33:19.792Z,
 *          source_sha256 b7985a7370ad528fdf4d218019252dd139f409c805ca234e1accbd49393971ef,
 *          stale true, front_end_sha256 4826813988038af7a859b69ff606f9adb856815c83b0afee24a11cfb948ab0d7
 *
 * `stale` is true in both readings: the front-end source was edited after the
 * build, so the bytes the browser runs are not exactly the checked-out `web/src`.
 * That does not change the verdict, because the checked-out source says the same
 * thing the bundle does. `ItemsPane.vue:13,88` and `GanttPane.vue:11,86` still
 * default `tag: ''` and filter with `(t.tags || []).includes(filters.tag)`, while
 * `KanbanPane.vue:16,54,143` uses `tag: []` with `.every(...)`. The served chunks
 * say it directly: `web/dist/assets/ItemsPane-Bsgd_fAw.js` and
 * `GanttPane-D4t8A8Pk.js` hold `tag:""`, `KanbanPane-DZuTmPxk.js` holds `tag:[]`
 * with `.every(t => e.tags.includes(t))`. The fabric HEAD moved again while the
 * final run was in flight; the served bundle did not.
 */

/**
 * The fixture makes the three predicates answer differently, so an AND assertion
 * cannot pass by coincidence:
 *
 *   tag=alpha        -> T-A1, T-A2                    (one tag narrows to two)
 *   tag=beta         -> T-A1, T-B1
 *   tag=alpha&tag=beta -> T-A1 only                   (the AND)
 *
 * All four carry `start`/`due` so Gantt draws them all; the Gantt count in its
 * header is the only DOM readout of its filtered rows (the bars are canvas), and
 * the fixture guarantees "1 of 4" can only mean T-A1.
 */
const TASK = (id, tags, extra = {}) => ({
  id, title: `placeholder ${id}`, owner: 'codex', status: 'backlog', priority: 'normal',
  milestone: '', tags, due: '', start: '', accept: `acceptance for ${id}`, blocked_by: [],
  visibility: 'published', provenance: 'seed', events: [], comments: [],
  channel: 'dev', context_id: 'dev', ...extra,
})

const STATE = {
  digest: 't0166-tag-and',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'doing', 'done'],
  terminal: ['done'],
  phase: 'CROSS_EXAMINE',
  milestones: {},
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'codex', model: 'gpt-5' } },
  register: {},
  tasks: {
    'T-A1': TASK('T-A1', ['alpha', 'beta'], { start: '2026-09-01', due: '2026-09-10' }),
    'T-A2': TASK('T-A2', ['alpha'], { start: '2026-09-02', due: '2026-09-11' }),
    'T-B1': TASK('T-B1', ['beta'], { start: '2026-09-03', due: '2026-09-12' }),
    'T-N1': TASK('T-N1', ['gamma'], { start: '2026-09-04', due: '2026-09-13' }),
  },
  reports: { series: [], throughput: [], blocked: [], median_cycle: null },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: true, as: 'human' },
  read: { as: 'human', borrowed: false },
  viewer: 'human',
  viewer_kind: 'human',
}

const ALL = ['T-A1', 'T-A2', 'T-B1', 'T-N1']
const ONE_TAG = ['T-A1', 'T-A2']
const AND = ['T-A1']

async function stub(page, state) {
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(state),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: state.digest }),
  }))
}

/** The tag control, addressed by what it offers: the filter select whose
 *  placeholder is the surface's own word for tags. Positional afterwards is
 *  safe -- adding a filter moves no select, it only renumbers this one. */
async function tagControl(page, placeholder) {
  const selects = page.locator('.aim-filterbar .el-select')
  const count = await selects.count()
  for (let i = 0; i < count; i += 1) {
    if ((await selects.nth(i).innerText()).trim() === placeholder) return selects.nth(i)
  }
  throw new Error(`no filter select labelled "${placeholder}"`)
}

/** Choose one tag through the control. Element Plus keeps a multi-select's
 *  dropdown open across a pick and closes a single-select's; the Escape makes
 *  both end in the same place. */
async function pickTag(page, control, tag) {
  await control.click()
  await page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
    .filter({ hasText: new RegExp(`^${tag}$`) }).click()
  await page.keyboard.press('Escape')
}

/**
 * The selected set, read off the control's own option list rather than its chips.
 *
 * A chip count would be a lie on Kanban: the picker is `multiple collapse-tags`,
 * so two tags draw as `alpha` plus a `+ 1` overflow chip and the second name is
 * not in the DOM. The option elements carry `is-selected`, which is the control's
 * actual state on every surface -- and on a single-value control holding a
 * two-tag URL that was coerced to one string, none of the options matches, so the
 * readout is empty. The dropdown is addressed by the id the combobox declares
 * (`aria-controls`), not by `:visible`, so a dropdown still animating out of a
 * neighbouring select cannot contribute its own selections.
 */
async function selectedTags(page, control) {
  const id = await control.locator('input[role="combobox"]').first().getAttribute('aria-controls')
  await control.click()
  const dropdown = page.locator(`#${id}`)
  await dropdown.waitFor({ state: 'visible' })
  const texts = await dropdown.locator('.el-select-dropdown__item.is-selected').allInnerTexts()
  await page.keyboard.press('Escape')
  return texts.map((t) => t.trim()).sort()
}

/** The `tag` parameters the URL actually carries, as a list -- repeated keys are
 *  the whole point, and `?tag=alpha,beta` is one parameter, not two. */
function urlTags(page) {
  const { hash } = new URL(page.url())
  const qs = hash.includes('?') ? hash.slice(hash.indexOf('?') + 1) : ''
  return new URLSearchParams(qs).getAll('tag')
}

/** Items: one table row per work item, the id in the first cell. */
const itemIds = (page) => page.locator('.el-table__body tr td:first-child').allInnerTexts()

/** Gantt: the header count is the only DOM readout of the filtered rows.
 *
 *  The pattern is the sentence the pane actually renders, not the one this file
 *  was written against. `GanttPane.vue`'s header used to read
 *  `timeline — 2 of 4 dated item(s)`; it now states the bars it drew apart from
 *  the set the filter leaves (`timeline — 2 drawn of 4 dated bar(s) the filter
 *  leaves; 0 on the record and 4 plan seeds (promises, not work), …`). Two
 *  changes, and this instrument has now been re-pointed for both:
 *
 *   - T-0188 first found the old sentence counting one universe and describing
 *     another, and the copy became `2 shown; of 4 dated bar(s)`.
 *   - The 2026-09-23 audit found `shown` was the *filter's* total and not the
 *     drawing: this pane pages (`?per=`, 25 by default) and the chart draws the
 *     page, so the header said 107 beside a canvas holding 25. The copy now names
 *     the page (`N drawn of M dated bar(s) the filter leaves`).
 *
 *  Both times the old pattern threw `gantt header did not name a count` on the
 *  very first assertion, so this instrument was reporting the pane's copy change
 *  rather than a filter defect. Only the two numbers this file is about are
 *  captured -- what is *drawn* and what the *filter left* -- and the trailing
 *  halves are not asserted here.
 *
 *  The two numbers coincide on this fixture, and that is a property of the fixture
 *  rather than a loss: `STATE` has 4 dated rows and the default page size is 25, so
 *  the page *is* the filter's set and `[drawn, left]` collapses to `[n, n]`. The
 *  pair still discriminates -- 4, then 2, then 1 -- which is the clause this file
 *  runs. What it no longer reads is the whole board's dated total, which the pane
 *  stopped printing here on purpose: it was the denominator of a sentence whose
 *  numerator was the page.
 */
async function ganttCount(page) {
  const text = await page.locator('.aim-filterbar > span').first().innerText()
  const m = text.match(/timeline\s*—\s*(\d+)\s+drawn of\s+(\d+)\s+dated bar/)
  if (!m) throw new Error(`gantt header did not name a count: ${JSON.stringify(text)}`)
  return [Number(m[1]), Number(m[2])]
}

/** Kanban: one card per work item, the id on the card. */
const cardIds = (page) => page.locator('.aim-card .aim-id').allInnerTexts()

/**
 * One clause set, run against one surface's own readout.
 *
 * The order matters: the AND narrowing is asserted first, because it is the
 * clause the card names, and it fails with the row that should not be there
 * rather than with a count. Then the URL write, then the URL restore, then
 * clear -- the same three-loop `useQueryFilters` contract on every surface.
 */
async function assertSurface(page, { hash, placeholder, shown, all, one, and }) {
  await page.goto(hash)
  const tag = await tagControl(page, placeholder)
  await expect.poll(() => shown(page)).toEqual(all)

  // One tag narrows to the two that carry it. This is the control for the AND
  // below: without it, "narrows to one" could be a filter that matches nothing.
  await pickTag(page, tag, 'alpha')
  await expect.poll(() => shown(page)).toEqual(one)

  // The second tag narrows further -- to the item that carries both.
  await pickTag(page, tag, 'beta')
  await expect.poll(() => shown(page)).toEqual(and)
  await expect.poll(() => urlTags(page)).toEqual(['alpha', 'beta'])
  expect(await selectedTags(page, tag)).toEqual(['alpha', 'beta'])

  // The URL is the state: a link that repeats the parameter restores the set.
  await page.goto(`${hash}?tag=alpha&tag=beta`)
  await expect.poll(() => shown(page)).toEqual(and)
  expect(await selectedTags(page, tag)).toEqual(['alpha', 'beta'])

  // Clear resets the whole array, not one element of it.
  await tag.locator('.el-select__clear').click()
  await expect.poll(() => urlTags(page)).toEqual([])
  expect(await selectedTags(page, tag)).toEqual([])
  await expect.poll(() => shown(page)).toEqual(all)
}

test.describe('T-0166 tag filters: two tags are an AND on every surface', () => {
  test('items', async ({ page }) => {
    // Measured green on the served bundle 2026-09-22 (bundle 9e6116d47ac1+dirty,
    // /api/revision stale false): Items carries a `multiple` tag select and
    // `filters.tag.every(...)`, so the AND step shows T-A1. The two `test.fail()`
    // markers this file opened with are gone for the reason Playwright reports
    // for any annotated test whose body now passes -- "Expected to fail, but
    // passed" -- and no assertion below was touched to get there.
    await stub(page, STATE)
    await assertSurface(page, {
      hash: '#/items', placeholder: 'tag', shown: itemIds, all: ALL, one: ONE_TAG, and: AND,
    })
  })

  test('gantt', async ({ page }) => {
    await stub(page, STATE)
    // `[drawn, left]` on every step, because that is the pair the header prints.
    // The two numbers coincide here -- 4 dated rows against a default page size of
    // 25 -- so this fixture cannot tell a page count from a filter count, and the
    // instrument does not pretend otherwise. The pair is still what is read, so a
    // pane that paged this fixture would show it rather than hide it behind a
    // single number.
    await assertSurface(page, {
      hash: '#/gantt', placeholder: 'tag', shown: ganttCount, all: [4, 4], one: [2, 2], and: [1, 1],
    })
  })

  test('kanban', async ({ page }) => {
    await stub(page, STATE)
    await assertSurface(page, {
      hash: '#/kanban', placeholder: 'any tag', shown: cardIds, all: ALL, one: ONE_TAG, and: AND,
    })
  })
})
