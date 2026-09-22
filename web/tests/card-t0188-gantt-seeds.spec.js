/**
 * T-0188 -- "Gantt draws 87 plan promises as work and paints 42 of them done".
 *
 * Card text (channels/hello/tasks.jsonl, `created` 2026-09-22T07:12:42.076Z,
 * actor codex, owner claude-session1, tags frontend), verbatim acceptance:
 *
 *   1. "On `#/gantt`, exactly the 87 seed bars carry a mark, and their tooltips
 *      say the dates are planned rather than recorded. The 15 recorded bars carry
 *      no such mark."
 *   2. "A promise's bar is not coloured as though the status were an outcome."
 *   3. "One component renders this fact on every pane that draws a task -- Help,
 *      Kanban, Items, Gantt, Plan and Attention agree, and a test asserts the
 *      predicate is the same one (`isPromise`), not four copies of
 *      `provenance.includes('seed')`."
 *
 * Revision measured for this file -- `GET http://127.0.0.1:8777/api/revision` on
 * 2026-09-23, after the markers were removed and the census was rewritten:
 *
 *   fabric c2ad5cf+dirty
 *   bundle c2ad5cf+dirty, source "vite build"
 *   stale: false
 *
 * The 2026-09-22 measurement below is kept because it is what the two removed
 * markers were annotating, and because one of its own claims was wrong.
 *
 * Measurement on that revision, viewport 1440x1000:
 *
 *   `#/gantt` .......... 0 bars of any kind in the chart card. The pane logs
 *                        `ReferenceError: barTooltip is not defined` and the
 *                        shell's error handler aborts the card's render, so the
 *                        chart is not drawn and there is nothing to mark or hover.
 *                        /api/state has 87 dated plan seeds and 20 dated recorded
 *                        items, so the bars clause has no data to be right about.
 *   `#/kanban` ......... 87 cards carry `<span class="aim-chip seed">plan seed</span>`
 *                        -- a mark of the pane's own, not the shared component --
 *                        and 0 carry `.aim-promise`.
 *   `#/items` .......... 175 rows, all with an id, and 0 promise marks of any kind.
 *   `#/plan`, `#/attention` ... `.aim-promise` ("planned") is used, so the shared
 *                        mark exists; the two panes above are where it is missing.
 *
 * **Both the `test.fail()` markers on the two chart tests are gone, and the reason
 * they were lying is the reason the replacement helper reads pixels.** They scanned
 * `path` elements inside `.aim-sticky-head`; the chart is canvas-rendered, so there
 * are none, and `marked` was structurally 0 on every bundle -- the failure they
 * absorbed was the helper's, not the card's, and `test.fail()` passes on any
 * failure. Two of the claims those markers made about the product were also false:
 * `barTooltip` *is* defined (`GanttPane.vue`), and the chart did not draw "107
 * bars" -- 107 is the filter's total, while the chart draws the first `?per=` rows
 * (25 by default). The second claim was checked nowhere, and the pane published it
 * under the name `data-drawn`. Both are now measured: `ganttBands` censuses the
 * canvas by status colour and alpha, `bandTooltip` hovers each band's own pixels,
 * and the assertions are per bar against `/api/state?as=human`.
 *
 * Clause 3 is the one that has to be narrowed to be checkable from outside. "The
 * predicate is the same one, not four copies" is a claim about source; from the
 * DOM, the honest observable is agreement -- every row's mark matches what
 * `isPromise` (the store's own `provenance.includes('seed')`, `board.js:62`) says
 * about that id, and every mark is the one `.aim-promise` component. That is what
 * the third test asserts, on the two panes that draw one row per task.
 */
import { expect, test } from '@playwright/test'

test.use({ viewport: { width: 1440, height: 1000 } })
// A 175-row Items table, a 100-row chart and a live board that peers are writing
// to: the default 30s is a budget for reading a page, not for measuring three of
// them while a browser lays out an ECharts canvas.
test.describe.configure({ timeout: 120_000 })

/** The store's predicate, spelled as `board.js:62` spells it. */
const isPromise = (task) => (task?.provenance || '').includes('seed')

/**
 * The payload, split into the two universes the Gantt draws.
 *
 * The seat is named, and naming it is the whole of this helper's correctness.
 * `/api/state` is viewer-scoped (`aimboard/cli.py:490` reads `?as=`, falling back
 * to the server's own `--as`), and the page under test boots with
 * `board.viewer = 'human'` (`stores/board.js:521`, the `|| 'human'` default), so
 * the app asks for `?as=human`. `page.request` carries no such default. Measured
 * while the board was started `--as claude-session1`: a bare `/api/state` answers
 * `viewer: claude-session1`, 148 rows, `withheld_tasks: 29`; `?as=human` answers
 * 177 rows and withholds nothing. So a bare fetch hands this file a payload 29
 * rows smaller than the one the DOM was drawn from, and the two disagree about
 * whether rows like `T-0018` exist at all -- which reads, in an assertion, as the
 * pane marking a row the payload says is not a promise. It is not marking
 * anything wrong: the row is not *in* the smaller payload.
 */
const pageState = async (page) => {
  const response = await page.request.get('/api/state?as=human')
  expect(response.ok(), `GET /api/state?as=human answered ${response.status()}`).toBe(true)
  return response.json()
}

/**
 * Every bar drawn in the chart, found in the canvas, split by whether it is marked.
 *
 * **This read `path` elements until 2026-09-23, and there are none.** The chart is
 * canvas-rendered (`src/plugins/charts.js:12` registers `CanvasRenderer`; the host
 * is one `<div>` holding one `<canvas>`, 0 svg and 0 path). The 9 paths a
 * `.aim-sticky-head` scan finds are the filterbar's Element Plus icons -- two
 * `el-input__clear`, five `el-select__caret` -- plus the pager's prev/next arrows,
 * all `fill="currentColor"` with no `fill-opacity` and no `stroke-dasharray`. So
 * `marked` was structurally 0 and `plain` was 9 on *every* bundle, and the marker
 * both tests carried was absorbing the helper's own failure rather than the card's.
 *
 * The pixels are the rendering, so the pixels are what gets read -- the same
 * technique `recorded-vs-seed.spec.js:199` (`barsOfColourRaw`) uses. For one status
 * colour, group matching pixels into runs of consecutive rows (one run per bar,
 * the gaps between gantt rows being 24px) and classify each run by the alpha its
 * *interior* carries:
 *
 *   a recorded bar is `color(status)` at full alpha
 *   a promise is the same hue at 32% -- `fill-opacity="0.32"` plus a dashed 1px
 *   border, which is what ECharts writes for `borderType: [3, 3]`
 *
 * A run that is mostly opaque was painted as an outcome; a run that is mostly
 * translucent was painted as a promise. Tolerance is 4, not the 8
 * `recorded-vs-seed.spec.js` uses, because the two classes are far apart and 4 is
 * enough: `fade(#34d399, 0.32)` composited over the card ground (`#f6f7f9`) is
 * (184,236,218), while the recorded fill is (52,211,153) -- 132 apart on the red
 * channel, against a tolerance of 4.
 *
 * The census runs in the page, so it takes one argument and returns one object.
 */
const STATUS_COLOURS = {
  backlog: [148, 163, 184], ready: [96, 165, 250], doing: [245, 158, 11],
  review: [167, 139, 250], done: [52, 211, 153], blocked: [239, 68, 68],
  dropped: [156, 163, 175],
}

async function ganttBands(page, errors) {
  await page.goto('/#/gantt')
  await page.waitForSelector('.aim-main', { state: 'visible' })
  // ECharts animates a bar in from the axis, so a census taken mid-ramp counts
  // partially painted bars. Wait for the canvas's own painted-pixel total to
  // repeat three times, which is what "the animation stopped" looks like from
  // outside -- a fixed timeout samples whatever frame it happened to reach.
  let last = -1
  let same = 0
  for (let i = 0; i < 80; i += 1) {
    const painted = await page.evaluate(() => {
      const canvas = document.querySelector('canvas')
      if (!canvas) return 0
      const { data } = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height)
      let n = 0
      for (let k = 3; k < data.length; k += 4) if (data[k] >= 16) n += 1
      return n
    })
    if (painted > 0 && painted === last) {
      same += 1
      if (same >= 2) break
    } else same = 0
    last = painted
    await page.waitForTimeout(120)
  }
  const census = await page.evaluate((colours) => {
    const canvas = document.querySelector('canvas')
    if (!canvas) return { canvas: false, bands: [] }
    const { data, width, height } = canvas.getContext('2d')
      .getImageData(0, 0, canvas.width, canvas.height)
    const box = canvas.getBoundingClientRect()
    const bands = []
    for (const [status, [r, g, b]] of Object.entries(colours)) {
      const near = (i, want) => Math.abs(data[i] - want) <= 4
      const rows = new Map()
      for (let y = 0; y < height; y += 1) {
        for (let x = 0; x < width; x += 1) {
          const i = (y * width + x) * 4
          if (data[i + 3] < 16) continue
          if (!near(i, r) || !near(i + 1, g) || !near(i + 2, b)) continue
          const row = rows.get(y) || { opaque: 0, translucent: 0, x0: x, x1: x }
          // The gap between 32% and fully opaque is wide enough that antialiased
          // edges cannot cross it in either direction.
          if (data[i + 3] >= 200) row.opaque += 1
          else if (data[i + 3] <= 120) row.translucent += 1
          row.x0 = Math.min(row.x0, x)
          row.x1 = Math.max(row.x1, x)
          rows.set(y, row)
        }
      }
      const ys = [...rows.keys()].sort((a, b2) => a - b2)
      const runs = []
      for (const y of ys) {
        const run = runs.at(-1)
        if (run && y - run.y1 <= 2) {
          const row = rows.get(y)
          run.y1 = y
          run.opaque += row.opaque
          run.translucent += row.translucent
          run.x0 = Math.min(run.x0, row.x0)
          run.x1 = Math.max(run.x1, row.x1)
        } else {
          const row = rows.get(y)
          runs.push({ y0: y, y1: y, opaque: row.opaque, translucent: row.translucent, x0: row.x0, x1: row.x1 })
        }
      }
      for (const run of runs) {
        // A run shorter than a bar is an antialiased edge of the axis or a tick,
        // not a bar: the shortest bar drawn is 16px of a 21px row.
        if (run.y1 - run.y0 < 8) continue
        bands.push({
          status,
          marked: run.translucent >= run.opaque,
          cx: box.left + (run.x0 + run.x1) / 2,
          cy: box.top + (run.y0 + run.y1) / 2,
          x0: box.left + run.x0,
          x1: box.left + run.x1,
        })
      }
    }
    return { canvas: true, bands }
  }, STATUS_COLOURS)
  return {
    ...census,
    bars: census.bands.length,
    marked: census.bands.filter((band) => band.marked).length,
    plain: census.bands.filter((band) => !band.marked).length,
    header: await page.evaluate(() => (document.querySelector('.aim-sticky-head')?.innerText || '')
      .replace(/\s+/g, ' ').slice(0, 200)),
    drawn: await page.evaluate(() => document.querySelector('.aim-sticky-head [data-drawn]')
      ?.getAttribute('data-drawn')),
    matched: await page.evaluate(() => document.querySelector('.aim-sticky-head [data-drawn]')
      ?.getAttribute('data-matched')),
    errors: errors.slice(),
  }
}

/**
 * The ECharts tooltip for one band, read by hovering the band's own pixels.
 *
 * Hovering the band's rectangle rather than its centre: the centre can fall on a
 * neighbouring bar when two bars overlap in x, so the point is tried from the
 * middle outward and the first tooltip that names a task wins.
 */
async function bandTooltip(page, band) {
  for (const fraction of [0.5, 0.25, 0.75, 0.1, 0.9]) {
    const x = band.x0 + (band.x1 - band.x0) * fraction
    await page.mouse.move(x, band.cy)
    await page.waitForTimeout(200)
    const tip = await page.evaluate(() => {
      const boxes = [...document.querySelectorAll('.aim-sticky-head div')].filter((div) => {
        const style = getComputedStyle(div)
        return style.position === 'absolute' && div.offsetParent && /T-\d{4}/.test(div.textContent)
      })
      return boxes.length ? boxes[boxes.length - 1].innerText.replace(/\s+/g, ' ').trim() : null
    })
    if (tip) return tip
  }
  return null
}

/** The census, plus each band's tooltip, keyed by band. */
async function ganttBandsWithTooltips(page, errors) {
  const chart = await ganttBands(page, errors)
  const tips = []
  for (const band of chart.bands) tips.push({ band, tip: await bandTooltip(page, band) })
  return { chart, tips }
}

/**
 * Clause 1. Every bar the chart draws carries the mark its own payload says it
 * should: a promise is drawn as one and a record is not.
 *
 * The check is per bar rather than per count, because a count can agree for the
 * wrong reason. Each band in the census is hovered (on its own pixels, so the
 * tooltip is the bar's and not a neighbour's), the tooltip names the task, and the
 * band's class has to equal `isPromise` on that task in `/api/state?as=human`. A
 * bar painted with the wrong class, or a tooltip naming a different row than the
 * bar it is drawn over, fails on the bar itself.
 *
 * The counts are checked too, but only as bounds, and the reason is this pane's own
 * paging: the chart draws `shownRows` (`?per=`, first page 25) and not the filter's
 * total, so "87 marked bars" is a number this chart cannot show. The pane's own
 * `data-drawn` says what it was handed; the census has to reproduce *that*.
 *
 * The marker that stood here is gone. It said the helper could not see a bar --
 * true, and the replacement reads the canvas instead -- but the claim it made about
 * the *product* ("the chart draws 107 bars") was checked nowhere, and 107 was the
 * filter's total, not the drawing.
 */
test('T-0188: every bar the chart draws carries the mark its payload says it should', async ({ page }) => {
  const errors = []
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text().slice(0, 300)) })

  const { chart, tips } = await ganttBandsWithTooltips(page, errors)

  expect(
    chart.canvas,
    'the Gantt pane rendered no canvas at all, so there is no chart to measure',
  ).toBe(true)

  expect(
    chart.errors,
    `${chart.bars} bar(s) drawn in the chart (${chart.marked} marked, ${chart.plain} plain) while the page `
    + `logged: ${chart.errors.join(' | ') || 'nothing'}; header "${chart.header}"`,
  ).toEqual([])

  // What the chart was handed, from the pane's own attribute: the census has to
  // reproduce this, and it is the page's count, not the filter's.
  const drawn = Number(chart.drawn)
  expect(Number.isFinite(drawn), `the pane published no numeric data-drawn ("${chart.drawn}")`).toBe(true)
  expect(
    chart.bars,
    `the census found ${chart.bars} bars in the canvas while the pane says it drew ${drawn} `
    + `(data-matched ${chart.matched}; header "${chart.header}")`,
  ).toBe(drawn)
  expect(chart.marked, 'the census classified no bar as marked, so the mark is not drawn or not seen')
    .toBeGreaterThan(0)
  expect(chart.plain, `all ${chart.bars} bars were classified as marked`).toBeGreaterThan(0)

  // Per bar: the class the census read off the pixels against the class the payload
  // gives the task the bar's own tooltip names.
  const state = await pageState(page)
  const byId = new Map(Object.values(state.tasks || {}).map((task) => [task.id, task]))
  const disagreements = []
  const unnamed = []
  for (const { band, tip } of tips) {
    const id = (tip || '').match(/\bT-\d{4}\b/)?.[0]
    if (!id) { unnamed.push({ status: band.status, marked: band.marked, tip }); continue }
    const task = byId.get(id)
    if (!task) { disagreements.push(`${id}: the tooltip names a row /api/state does not have`); continue }
    const shouldBeMarked = isPromise(task)
    const saysMarked = /plan seed, not recorded/.test(tip)
    if (band.marked !== shouldBeMarked) {
      disagreements.push(`${id}: bar is ${band.marked ? 'marked' : 'plain'} but the payload says `
        + `provenance "${task.provenance}" (isPromise ${shouldBeMarked})`)
    } else if (saysMarked !== shouldBeMarked) {
      disagreements.push(`${id}: the bar is ${band.marked ? 'marked' : 'plain'} but its tooltip `
        + `${saysMarked ? 'claims a plan seed' : 'does not say plan seed'}`)
    }
  }
  expect(
    unnamed,
    `${unnamed.length} of ${chart.bars} bars could not be named by hovering their own pixels, so their class `
    + `was never checked against a payload row: ${JSON.stringify(unnamed.slice(0, 3))}`,
  ).toEqual([])
  expect(
    disagreements,
    `${disagreements.length} bar(s) disagree with the payload: ${disagreements.join(' | ')}`,
  ).toEqual([])

  // And the direction of the split, over the payload this run actually has.
  const dated = [...byId.values()].filter((task) => task.start || task.due)
  const seeds = dated.filter(isPromise).length
  const records = dated.length - seeds
  expect(chart.marked, `${chart.marked} marked bars exceed the ${seeds} dated seeds in the payload`)
    .toBeLessThanOrEqual(seeds)
  expect(chart.plain, `${chart.plain} unmarked bars exceed the ${records} dated records in the payload`)
    .toBeLessThanOrEqual(records)
})

/**
 * Clause 2 (and the second half of clause 1). The mark is not only a class: a
 * marked bar's tooltip has to say the dates are planned, and an unmarked bar's has
 * to say they are recorded, which is the sentence the card measured as identical
 * for both.
 *
 * Checked on every band, not on the first of each class, because "the first marked
 * bar" is a sample of one and this card's complaint was that the *bars* said the
 * same thing -- a tooltip that drifted on one lane would have passed a
 * first-of-class check.
 *
 * The marker that stood here is gone. It blamed the same helper as the test above
 * and it was right about the helper: `tooltipText(page, 'path[data-t0188-marked]')`
 * hovered an Element Plus icon, so it reported "no tooltip" on every bundle --
 * including the one it blamed, where the tooltips were in fact correct.
 */
test('T-0188: every bar\'s tooltip says which authority its dates came from', async ({ page }) => {
  const errors = []
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text().slice(0, 300)) })

  const { chart, tips } = await ganttBandsWithTooltips(page, errors)

  expect(chart.bars, 'no bar was drawn, so no tooltip could be read').toBeGreaterThan(0)

  const seedTips = tips.filter(({ band }) => band.marked)
  const recordTips = tips.filter(({ band }) => !band.marked)
  expect(seedTips.length, 'no marked bar was drawn, so clause 2 has no subject').toBeGreaterThan(0)
  expect(recordTips.length, 'no plain bar was drawn, so clause 2 has no subject').toBeGreaterThan(0)

  const noTooltip = tips.filter(({ tip }) => !tip)
  expect(
    noTooltip,
    `${noTooltip.length} of ${chart.bars} bands produced no tooltip when their own pixels were hovered, `
    + `so their class was never checked: ${JSON.stringify(noTooltip.slice(0, 3).map((t) => t.band))}`,
  ).toEqual([])

  const wrongSeed = seedTips.filter(({ tip }) => !/planned dates/.test(tip) || !/plan seed, not recorded/.test(tip))
  expect(
    wrongSeed.map(({ tip }) => tip),
    `${wrongSeed.length} marked bar(s) do not say their dates are planned rather than recorded`,
  ).toEqual([])

  const wrongRecord = recordTips.filter(({ tip }) => !/recorded dates/.test(tip) || /plan seed/.test(tip))
  expect(
    wrongRecord.map(({ tip }) => tip),
    `${wrongRecord.length} unmarked bar(s) do not say their dates are recorded, or claim to be a plan seed`,
  ).toEqual([])

  expect(
    errors,
    `the page logged errors while the tooltips were read: ${errors.join(' | ') || 'nothing'}`,
  ).toEqual([])
})

/**
 * Clause 3, narrowed to what a reader's browser can see: on the two panes that
 * draw one row per task, every row's mark agrees with `isPromise` on the payload,
 * and the mark is the shared `.aim-promise` component rather than a pane's own
 * chip.
 */
test('T-0188: Kanban and Items mark exactly the promise rows, with the shared mark', async ({ page }) => {
  // The marker that stood here is gone, and its reason was not what it said.
  // Measured 2026-09-22: the two rows it named (`T-0018`, `T-0027`) are marked on
  // screen *and* are genuine promises in the app's own payload
  // (`provenance: "seed only (not yet in the store)"`, `status: dropped`). The
  // disagreement was between the two seats, not between the pane and the
  // predicate: this file fetched the bare `/api/state` (the server's `--as
  // claude-session1`, 148 rows, `withheld_tasks: 29`) and compared it against a
  // DOM drawn from `?as=human` (177 rows, nothing withheld). With `pageState`
  // above, the comparison is seat-matched and the assertion is non-vacuous --
  // 40 marked of 40 promised on the kanban, 0 disagreements on either pane.
  const state = await pageState(page)
  const promiseIds = new Set(Object.values(state.tasks || {}).filter(isPromise).map((task) => task.id))

  const panes = [
    { name: 'kanban', hash: '#/kanban', row: '.aim-card' },
    { name: 'items', hash: '#/items', row: '.el-table__row' },
  ]
  const report = []
  for (const pane of panes) {
    await page.goto(`/${pane.hash}`)
    await page.waitForSelector(pane.row, { state: 'visible' })
    await page.waitForTimeout(1200)
    report.push(await page.evaluate(({ row, promiseIds: ids }) => {
      const promise = new Set(ids)
      const rows = [...document.querySelectorAll(row)]
      const withId = rows.filter((el) => /\bT-\d{4}\b/.test(el.innerText))
      const marked = (el) => !!el.querySelector('.aim-promise')
      const bespoke = (el) => !!el.querySelector('.aim-chip.seed:not(.aim-promise)')
      const wrongMark = withId.filter((el) => {
        const id = el.innerText.match(/\bT-\d{4}\b/)[0]
        return marked(el) !== promise.has(id)
      })
      const labels = new Set(withId.flatMap((el) => [...el.querySelectorAll('.aim-promise')]
        .map((m) => m.textContent.trim())))
      return {
        rows: rows.length,
        withId: withId.length,
        promises: withId.filter((el) => promise.has(el.innerText.match(/\bT-\d{4}\b/)[0])).length,
        marked: withId.filter(marked).length,
        bespoke: withId.filter(bespoke).length,
        markLabels: [...labels],
        wrong: wrongMark.slice(0, 5).map((el) => {
          const id = el.innerText.match(/\bT-\d{4}\b/)[0]
          return `${id}: promise=${promise.has(id)} marked=${marked(el)}`
        }),
        wrongCount: wrongMark.length,
      }
    }, { row: pane.row, promiseIds: [...promiseIds] }))
  }

  for (let index = 0; index < panes.length; index += 1) {
    const pane = panes[index]
    const found = report[index]
    expect(
      found.wrongCount,
      `${pane.name}: ${found.wrongCount} of ${found.withId} rows disagree with isPromise on the payload `
      + `(${found.promises} of them are promises; ${found.marked} carry .aim-promise, ${found.bespoke} carry a pane-local `
      + `.aim-chip.seed instead): ${found.wrong.join(', ')}`,
    ).toBe(0)
    expect(
      found.markLabels,
      `${pane.name}: the promise mark is not the shared component's one word ("planned"): ${JSON.stringify(found.markLabels)}`,
    ).toEqual(found.markLabels.length ? ['planned'] : [])
  }
})
