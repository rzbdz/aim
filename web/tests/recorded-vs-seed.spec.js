/**
 * T-0188: the Gantt and the Plan pane count plan seeds as work.
 *
 * The measurement this file turns into assertions, taken on the live board on
 * 2026-09-22 (payload 159 tasks: 87 `seed only (not yet in the store)` + 72
 * `store only`):
 *
 *   #/gantt header, rendered:      timeline — 102 of 102 dated item(s), ...
 *   of those 102 dated rows:       87 seeds, 15 recorded
 *   bars painted the `done` green: 44, of which 42 were seeds with no events
 *   #/plan milestones:             124 items counted, 43 of the 45 counted "done"
 *                                  were seeds; M7 read 100% 2/2 with zero recorded
 *
 * A seed has **no events at all** -- its `status` and its dates are
 * `plan/plan.json`'s text -- so both numbers are statements about the plan file
 * rendered where a statement about work is expected. `board.recorded()` exists and
 * only `OverviewPane` uses it.
 *
 * The fixture below is built so the two authorities cannot be confused for each
 * other: **8 seeds and 3 dated recorded items, deliberately unequal**. Six seeds
 * carry plan-authored `done` and one recorded item carries a real `moved -> done`;
 * two seeds are `doing` and one recorded item is too. So
 *
 *   merged board  : 11 dated rows, 7 done
 *   the record    :  3 dated rows, 1 done
 *
 * and every assertion here is that difference or the sentence that states it.
 *
 * The fixture's ids are `T-9xxx`, and the range is the point rather than a
 * preference. The first version of this file used `T-0188`..`T-0198`, which is
 * *inside* the live range: `channels/hello/tasks.jsonl` names a task in the low
 * `T-01xx` and `T-02xx` hundreds, and the store mints ids sequentially from
 * `T-0001` in the order cards are created, so `T-9xxx` is the *shape* a live row
 * cannot occupy -- not a threshold this comment could write down, because any
 * literal maximum id here would be stale by the next card. The stubbed payload is
 * what the pane actually reads -- one `/api/state` request, one fixture -- but the
 * ids are the part of the fixture that has to be *out of reach* rather than merely
 * stubbed, because a surface that widens its own reading past the fixture would
 * otherwise pull a live row into a count this test believes it controls.
 */
import { expect, test } from '@playwright/test'

const SEED_PROV = 'seed only (not yet in the store)'

const SEED = (id, { status, start, due, milestone = 'M1' }) => ({
  id, title: `${id} plan row`, owner: 'codex', status, priority: 'normal', milestone,
  tags: [], start, due, accept: `acceptance for ${id}`, blocked_by: [], visibility: 'published',
  provenance: SEED_PROV, events: [], comments: [], estimate: 2,
})

/** A recorded item: it exists in the store, and a person moved it. */
const RECORDED = (id, { status, start, due, milestone = 'M2', moved = null }) => ({
  ...SEED(id, { status, start, due, milestone }),
  provenance: 'store only',
  created_at: '2026-09-24T00:00:00.000Z',
  prev_status: status === 'done' ? 'doing' : null,
  events: moved
    ? [{ at: '2026-09-24T01:00:00.000Z', event: 'created', to: 'doing' },
       { at: '2026-09-24T02:00:00.000Z', event: 'moved', from: 'doing', to: moved }]
    : [{ at: '2026-09-24T01:00:00.000Z', event: 'created', to: 'doing' }],
})

const STATE = {
  digest: 'recorded-vs-seed-fixture',
  generated_at: '2026-09-22T00:00:00.000Z',
  as_of: '2026-09-22',
  statuses: ['backlog', 'ready', 'doing', 'review', 'blocked', 'done', 'dropped'],
  terminal: ['done', 'dropped'],
  phase: 'RESOLVE',
  milestones: {
    M1: { id: 'M1', name: 'Planned work', due: '2026-09-26', accept: 'the promise turns into items' },
    M2: { id: 'M2', name: 'Recorded work', due: '2026-09-28', accept: 'the items were actually done' },
  },
  agents: { human: { kind: 'human', model: '' }, codex: { kind: 'agent', model: '' } },
  register: {},
  tasks: {
    // 8 seeds: 6 the plan file says are done, 2 it says are in progress. None of
    // them has an event, so nothing has ever moved one.
    'T-9001': SEED('T-9001', { status: 'done', start: '2026-09-21', due: '2026-09-22' }),
    'T-9002': SEED('T-9002', { status: 'done', start: '2026-09-21', due: '2026-09-22' }),
    'T-9003': SEED('T-9003', { status: 'done', start: '2026-09-21', due: '2026-09-22' }),
    'T-9004': SEED('T-9004', { status: 'done', start: '2026-09-21', due: '2026-09-22' }),
    'T-9005': SEED('T-9005', { status: 'done', start: '2026-09-21', due: '2026-09-22' }),
    'T-9006': SEED('T-9006', { status: 'done', start: '2026-09-21', due: '2026-09-22' }),
    'T-9007': SEED('T-9007', { status: 'doing', start: '2026-09-21', due: '2026-09-22' }),
    'T-9008': SEED('T-9008', { status: 'doing', start: '2026-09-21', due: '2026-09-22' }),
    // 3 recorded items, one genuinely completed, one in progress, one in review.
    // They are in M1, the milestone the plan pane's progress clause is about: a
    // milestone that holds *both* universes is the only one where "the merged board
    // would read 7/11 here" is a sentence with a referent. A milestone holding only
    // the record cannot show the difference this file asserts.
    'T-9009': RECORDED('T-9009', { status: 'done', start: '2026-09-24', due: '2026-09-25', milestone: 'M1', moved: 'done' }),
    'T-9010': RECORDED('T-9010', { status: 'doing', start: '2026-09-24', due: '2026-09-25', milestone: 'M1' }),
    'T-9011': RECORDED('T-9011', { status: 'review', start: '2026-09-24', due: '2026-09-25', milestone: 'M1' }),
    // M2's own three recorded items, and they carry **no dates on purpose**. The
    // date is what the Gantt counts, and the three tests on that pane are exact
    // counts over `board.dated` (11 dated bar(s), 3 on the record, 8 plan seeds).
    // A dated item here would move every one of them and the two clauses would
    // then be asserting different fixtures. An undated item draws no bar and is
    // counted by no dated number; it is still a row the plan pane's arithmetic is
    // over, which is the half of M2 this fixture needs.
    'T-9012': RECORDED('T-9012', { status: 'done', start: '', due: '', milestone: 'M2', moved: 'done' }),
    'T-9013': RECORDED('T-9013', { status: 'doing', start: '', due: '', milestone: 'M2' }),
    'T-9014': RECORDED('T-9014', { status: 'review', start: '', due: '', milestone: 'M2' }),
  },
  reports: {
    series: [], throughput: [], blocked: [], median_cycle: null,
    // Six recorded rows and eight dated seeds: the dated merge is 11 (the Gantt's
    // clause), the record over both milestones is 6 (the plan pane's).
    recorded: 6, seed_only: 8, with_history: 1,
  },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  drift: [],
  withheld_tasks: 0,
  write: { enabled: false, as: '' },
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/state**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE),
  }))
  await page.route('**/api/digest**', (route) => route.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
  }))
  await page.setViewportSize({ width: 1440, height: 1000 })
})

/**
 * The bars, found in the canvas rather than guessed at from the axis geometry.
 *
 * `#/gantt` draws into a `<canvas>`, so there is no DOM node per bar and no
 * `data-` hook this test could reach without the pane exporting one. The pixels are
 * the rendering, so the pixels are what gets read: for one status colour, group the
 * matching pixels into runs of consecutive rows (one run per bar), then classify
 * each run by the alpha its *interior* carries.
 *
 * The classification is the assertion, and it is the card's own distinction:
 *
 *   a recorded bar is `color(status)` at full alpha
 *   a promise is the same hue at 32% -- `fill-opacity="0.32"` plus a dashed 1px
 *   border, which is what ECharts writes for `borderType: [3, 3]`
 *
 * A run whose pixel count is mostly opaque was painted as an outcome; a run that is
 * mostly translucent was painted as a promise. Counting is done with a small
 * tolerance because every edge is antialiased, which is why the *interior* majority
 * decides the class rather than any single pixel.
 *
 * **The chart has to have stopped before any of this means anything.** ECharts
 * animates a bar in from the axis, so a census taken mid-ramp counts *partially
 * painted* bars: measured on the settled bundle with this file's fixture, the green
 * census reports a different chart at each step of the ramp (total 69 -> 2134 ->
 * 12050 -> 16648 -> 16937, where only from 16937 does the total repeat), and the
 * earlier readings differ in `bands` and `opaque` too. So `barsOfColour` waits for
 * the pixel total to repeat three times before it counts anything, and
 * `barsOfColourRaw` is the single read it then takes. A probe that asserts on the
 * first non-zero frame reports the frame it happened to sample; this file did that,
 * and three consecutive runs reporting `bands` 7, 7 and 11 is what it looked like.
 */
async function barsOfColour(page, rgb) {
  // "Settled" is measured on the same pixels the assertion is about -- this
  // colour's own total -- rather than on a total that a *different* bar could hold
  // constant while this one is still growing.
  const read = () => page.evaluate(([r, g, b]) => {
    const canvas = document.querySelector('canvas')
    if (!canvas) return { total: 0 }
    const { data, width, height } = canvas.getContext('2d')
      .getImageData(0, 0, canvas.width, canvas.height)
    const near = (i, want) => Math.abs(data[i] - want) <= 8
    let total = 0
    for (let i = 0; i < width * height * 4; i += 4) {
      if (data[i + 3] < 16) continue
      if (near(i, r) && near(i + 1, g) && near(i + 2, b)) total += 1
    }
    return { total }
  }, rgb)
  let last = -1
  let same = 0
  for (let i = 0; i < 120; i += 1) {
    const { total } = await read()
    if (total > 0 && total === last) {
      same += 1
      if (same >= 2) break            // three identical reads: the ramp has stopped
    } else {
      same = 0
    }
    last = total
    await page.waitForTimeout(100)
  }
  return barsOfColourRaw(page, rgb)
}

async function barsOfColourRaw(page, [r, g, b]) {
  return page.evaluate(([r, g, b]) => {
    const canvas = document.querySelector('canvas')
    if (!canvas) return { runs: [], bands: 0, opaque: 0, translucent: 0, total: 0 }
    const dpr = window.devicePixelRatio || 1
    const box = canvas.getBoundingClientRect()
    const { data, width, height } = canvas.getContext('2d')
      .getImageData(0, 0, canvas.width, canvas.height)
    const near = (i, want) => Math.abs(data[i] - want) <= 8
    const rows = new Map()   // y -> { opaque, translucent, x0, x1 }
    let total = 0
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        const i = (y * width + x) * 4
        if (data[i + 3] < 16) continue
        if (!near(i, r) || !near(i + 1, g) || !near(i + 2, b)) continue
        total += 1
        const row = rows.get(y) || { opaque: 0, translucent: 0, x0: x, x1: x }
        // A seed is the same hue at 32%; the gap between 32% and fully opaque is
        // wide enough that antialiased edges cannot cross it in either direction.
        if (data[i + 3] >= 200) row.opaque += 1
        else if (data[i + 3] <= 120) row.translucent += 1
        row.x0 = Math.min(row.x0, x); row.x1 = Math.max(row.x1, x)
        rows.set(y, row)
      }
    }
    // One bar per run of consecutive rows. A gap of more than 2px is the space
    // between two rows of the gantt, not a break inside one bar.
    const ys = [...rows.keys()].sort((a, b) => a - b)
    const runs = []
    for (const y of ys) {
      const last = runs.at(-1)
      if (last && y - last.y1 <= 2) {
        const row = rows.get(y)
        last.y1 = y
        last.opaque += row.opaque
        last.translucent += row.translucent
        last.x0 = Math.min(last.x0, row.x0)
        last.x1 = Math.max(last.x1, row.x1)
      } else {
        const row = rows.get(y)
        runs.push({ y0: y, y1: y, opaque: row.opaque, translucent: row.translucent, x0: row.x0, x1: row.x1 })
      }
    }
    return {
      total,
      bands: runs.length,
      opaque: runs.filter((run) => run.opaque > run.translucent).length,
      translucent: runs.filter((run) => run.translucent >= run.opaque).length,
      runs: runs.map((run) => ({
        ...run,
        x: box.left + ((run.x0 + run.x1) / 2) / dpr,
        y: box.top + ((run.y0 + run.y1) / 2) / dpr,
      })),
    }
  }, [r, g, b])
}

const DONE_GREEN = [52, 211, 153]     // theme.js STATUS_COLOR.done
const DOING_AMBER = [245, 158, 11]    // theme.js STATUS_COLOR.doing

/** The ECharts tooltip, which is the only rendered text a canvas bar has. */
const TOOLTIP = '.echarts-host div[style*="z-index: 9999999"]'

async function tooltipAt(page, point) {
  await page.mouse.move(point.x, point.y)
  const tip = page.locator(TOOLTIP).first()
  await expect(tip).toBeVisible()
  return tip.innerText()
}

test.describe('a plan seed is not work, on the two panes that draw the merge', () => {
  test('the Gantt header counts the record, and names both universes', async ({ page }) => {
    await page.goto('/#/gantt')
    const head = page.locator('.aim-sticky-head .el-card__header')
    await expect(head).toBeVisible()

    // Eleven dated rows are drawn -- this pane deliberately draws the merge, and
    // hiding eight of them would hide the plan. What changed is which authority
    // each number is about.
    await expect(head.locator('[data-drawn]')).toHaveAttribute('data-recorded', '3')
    await expect(head.locator('[data-drawn]')).toHaveAttribute('data-seeds', '8')
    await expect(head.locator('[data-drawn]')).toHaveAttribute('data-drawn', '11')

    // The rendered sentence says it in words, so a reader who never sees an
    // attribute still learns which half is which.
    await expect(head).toContainText('of 11 dated bar(s)')
    await expect(head).toContainText('3 on the record')
    await expect(head).toContainText('8 plan seeds')

    // The falsification: the old header read `11 of 11 dated item(s)` over the
    // merge, which is the number a pane that reads `board.tasks` produces. If the
    // fix is reverted this is what comes back, so the test asserts the difference
    // rather than the presence of a word.
    await expect(head).not.toContainText('11 of 11')
    await expect(head).not.toContainText('3 of 3 dated item(s)')
  })

  test('no seed bar is painted as a completed task', async ({ page }) => {
    await page.goto('/#/gantt')
    await expect(page.locator('canvas')).toBeVisible()
    // No gate here: `barsOfColour` settles the chart itself (three identical pixel
    // totals), so a `poll(total > 0)` in front of it would only be a second, earlier
    // reading of the same ramp -- and the earlier reading is the one this file used
    // to assert on.
    const green = await barsOfColour(page, DONE_GREEN)
    // `done`: six seeds (plan-authored text) and one recorded item that a person
    // actually moved. Only the last may be drawn as an outcome.
    expect(green.bands).toBe(7)
    expect(green.opaque).toBe(1)
    expect(green.translucent).toBe(6)

    // `doing`: two seeds and one recorded item, same split, a second status, so a
    // fix that special-cased `done` alone fails here.
    const amber = await barsOfColour(page, DOING_AMBER)
    expect(amber.bands).toBe(3)
    expect(amber.opaque).toBe(1)
    expect(amber.translucent).toBe(2)

    // And the legend decodes the mark, because a reader who has not hovered
    // anything has to be able to read the one non-status fill on the chart.
    await expect(page.locator('.aim-sticky-head .aim-filterbar .aim-chip.seed')).toHaveText('plan seed')
  })

  test('the tooltip says which authority the status and the dates came from', async ({ page }) => {
    await page.goto('/#/gantt')
    await expect(page.locator('canvas')).toBeVisible()
    const green = await barsOfColour(page, DONE_GREEN)
    // The bar the tooltip is read from is found in the *pixels*, not from the axis
    // geometry: a probe that guesses bar positions tests its guess, not the chart.
    // The fixture puts all six plan-authored `done` seeds and the one recorded item
    // a person moved into M1, so the green runs are the six promise bars plus the
    // record the tooltip clause is about -- and the clause is that the *last* one is
    // the record. Whether it is the last run is the product's ordering, not this
    // file's assumption.
    const seedTip = await tooltipAt(page, green.runs[0])
    expect(seedTip).toContain('T-9001')
    expect(seedTip).toContain('plan seed, not recorded')
    expect(seedTip).toContain('planned dates')
    // The recorded bar says the opposite, so "names provenance" is not a clause
    // that could be pasted onto every tooltip and still pass.
    const recordTip = await tooltipAt(page, green.runs.at(-1))
    expect(recordTip).toContain('T-9009')
    expect(recordTip).toContain('on the record')
    expect(recordTip).toContain('recorded dates')
  })

  test('the Plan pane computes milestone progress over the record, and says so', async ({ page }) => {
    await page.goto('/#/plan')
    const head = page.locator('.el-card__header', { hasText: 'milestones (' })
    await expect(head).toBeVisible()
    // The sentence names the authority, which is the card's own condition for
    // shipping the fix at all.
    await expect(head).toContainText('progress counts the record')

    const planned = page.locator('.el-table__row', { hasText: 'Planned work' })
    // Three recorded items in M1, one of them moved to done. The merged board
    // would read 7/11 here -- six of them seeds.
    await expect(planned).toContainText('1/3 recorded')
    await expect(planned.locator('.el-progress__text')).toHaveText('33%')
    await expect(planned).toContainText('8 planned')
    await expect(planned).not.toContainText('7/11')

    // A milestone whose items are all promises is a milestone with no recorded
    // work, and it must not be shown as progress either. M2 holds only recorded
    // items here, so the second assertion is the other direction: a milestone with
    // real completions still reads as complete.
    const recorded = page.locator('.el-table__row', { hasText: 'Recorded work' })
    await expect(recorded).toContainText('1/3 recorded')
    await expect(recorded).toContainText('0 planned')
  })

  test('a milestone made only of promises reads as no recorded work at all', async ({ page }) => {
    // The card's own example was `M7 100% 2/2` with zero recorded items. This is
    // that milestone: every item a seed, and the plan file calls one of them done.
    const onlyPromises = {
      ...STATE,
      digest: 'recorded-vs-seed-only-promises',
      milestones: { M7: { id: 'M7', name: 'Promises only', due: '2026-09-29', accept: 'nothing recorded yet' } },
      tasks: {
        'T-9001': SEED('T-9001', { status: 'done', start: '2026-09-21', due: '2026-09-22', milestone: 'M7' }),
        'T-9002': SEED('T-9002', { status: 'done', start: '2026-09-21', due: '2026-09-22', milestone: 'M7' }),
        'T-9003': SEED('T-9003', { status: 'doing', start: '2026-09-21', due: '2026-09-22', milestone: 'M7' }),
      },
    }
    await page.route('**/api/state**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify(onlyPromises),
    }))
    await page.route('**/api/digest**', (route) => route.fulfill({
      contentType: 'application/json', body: JSON.stringify({ digest: onlyPromises.digest }),
    }))
    await page.goto('/#/plan')
    const row = page.locator('.el-table__row', { hasText: 'Promises only' })
    await expect(row).toBeVisible()
    await expect(row.locator('.el-progress__text')).toHaveText('0%')
    await expect(row).toContainText('0/0 recorded')
    await expect(row).toContainText('3 planned')
    // The defect's exact rendering, asserted absent rather than merely unmentioned.
    await expect(row).not.toContainText('2/3')
    await expect(row).not.toContainText('67%')
  })
})
