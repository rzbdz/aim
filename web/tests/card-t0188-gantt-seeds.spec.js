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
 * 2026-09-22:
 *
 *   fabric 1277f7e+dirty
 *   bundle 870b282+dirty, built 2026-09-22T08:40:07.787Z, source "vite build"
 *   stale: true
 *
 * `stale` is true, so every number below is a number about the bundle a reader
 * loads on 8777, not about the newer `web/src` behind it.
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
 * All three tests carry `test.fail()` with those measured reasons. Not a weakened
 * assertion: a rebuilt bundle that draws the chart, or a pane that switches to the
 * shared mark, turns the matching test into an *unexpected pass*, and the
 * annotation has to be removed deliberately.
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

/** The payload, split into the two universes the Gantt draws. */
async function datedSplit(page) {
  const response = await page.request.get('/api/state')
  expect(response.ok(), `GET /api/state answered ${response.status()}`).toBe(true)
  const state = await response.json()
  const tasks = Object.values(state.tasks || {})
  const dated = tasks.filter((task) => task.start || task.due)
  return {
    seeds: dated.filter(isPromise).map((task) => task.id),
    recorded: dated.filter((task) => !isPromise(task)).map((task) => task.id),
  }
}

/**
 * Every bar drawn in the chart card, split by whether it is marked.
 *
 * The mark is the one `GanttPane.vue` draws: the status colour at 32% with a
 * dashed 1px stroke, so a marked bar is a path whose fill is not fully opaque or
 * whose stroke is dashed. The stacked "offset" series is transparent and is not a
 * bar in any sense the reader sees, so it is not counted.
 */
async function ganttBars(page, errors) {
  await page.goto('/#/gantt')
  await page.waitForSelector('.aim-main', { state: 'visible' })
  // ECharts sizes itself after the pane mounts, so this waits for a bar to exist
  // rather than for a fixed number of milliseconds: a chart that never draws must
  // be measured as zero bars, not as a slow test.
  for (let attempt = 0; attempt < 12; attempt += 1) {
    const drawn = await page.evaluate(() => {
      const card = document.querySelector('.aim-sticky-head')
      return !!card && [...card.querySelectorAll('path')].some((path) => {
        const fill = path.getAttribute('fill')
        return !!fill && fill !== 'none' && fill !== 'transparent'
      })
    })
    if (drawn) break
    await page.waitForTimeout(500)
  }
  await page.waitForTimeout(300)
  return page.evaluate((collected) => {
    const card = document.querySelector('.aim-sticky-head')
    if (!card) return { card: false, bars: 0, marked: 0, plain: 0, errors: collected }
    const all = [...card.querySelectorAll('path')]
    const bars = all.filter((path) => {
      const fill = path.getAttribute('fill')
      return !!fill && fill !== 'none' && fill !== 'transparent'
    })
    const isMarked = (path) => Number(path.getAttribute('fill-opacity') ?? 1) < 1
      || !!path.getAttribute('stroke-dasharray')
    const marked = bars.filter(isMarked)
    const plain = bars.filter((path) => !isMarked(path))
    marked[0]?.setAttribute('data-t0188-marked', '1')
    plain[0]?.setAttribute('data-t0188-plain', '1')
    return {
      card: true,
      bars: bars.length,
      marked: marked.length,
      plain: plain.length,
      samples: bars.slice(0, 3).map((path) => [path.getAttribute('fill'), path.getAttribute('fill-opacity'),
        path.getAttribute('stroke-dasharray')].join(' / ')),
      header: (card.querySelector('.el-card__header')?.innerText || '').replace(/\s+/g, ' ').slice(0, 200),
      errors: collected,
    }
  }, errors)
}

/** The ECharts tooltip, as HTML in the chart card, after a hover. */
async function tooltipText(page, selector) {
  const target = page.locator(selector)
  if (!(await target.count())) return null
  await target.first().hover()
  await page.waitForTimeout(500)
  return page.evaluate(() => {
    const divs = [...document.querySelectorAll('.aim-sticky-head div')].filter((div) => {
      const style = getComputedStyle(div)
      return style.position === 'absolute' && div.offsetParent && /T-\d{4}/.test(div.textContent)
    })
    return divs.length ? divs[divs.length - 1].innerText.replace(/\s+/g, ' ').trim() : null
  })
}

/**
 * Clause 1. Exactly the dated seeds carry the mark, and exactly the dated recorded
 * items do not.
 *
 * Both numbers are read off `/api/state` in the same run, so "87" and "15" in the
 * card are the payload's counts today rather than constants in this file.
 */
test('T-0188: exactly the dated plan seeds carry the promise mark, and no recorded bar does', async ({ page }) => {
  test.fail(true, 'measured 2026-09-22 on bundle 870b282+dirty: the chart card draws 0 bars -- the pane throws ReferenceError: barTooltip is not defined and the shell\'s error handler aborts the card, so the 87 dated seeds and 20 dated records are neither marked nor unmarked')
  const errors = []
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text().slice(0, 300)) })

  const split = await datedSplit(page)
  const chart = await ganttBars(page, errors)

  expect(
    chart.card,
    'the Gantt pane rendered no chart card at all (.aim-sticky-head), so there is no chart to measure',
  ).toBe(true)

  expect(
    chart.errors,
    `${chart.bars} bar(s) drawn in the chart card (${chart.marked} marked, ${chart.plain} plain) while the page `
    + `logged: ${chart.errors.join(' | ') || 'nothing'}; header "${chart.header}"`,
  ).toEqual([])

  expect(
    chart.marked,
    `${chart.marked} bars carry the promise mark; /api/state has ${split.seeds.length} dated plan seeds `
    + `(provenance "seed only (not yet in the store)"), so ${Math.abs(chart.marked - split.seeds.length)} seed bars are unmarked `
    + `or wrongly marked (bars ${chart.bars}: marked ${chart.marked}, plain ${chart.plain}, e.g. ${JSON.stringify(chart.samples)})`,
  ).toBe(split.seeds.length)

  expect(
    chart.plain,
    `${chart.plain} bars carry no promise mark; /api/state has ${split.recorded.length} dated recorded items, `
    + `so ${Math.abs(chart.plain - split.recorded.length)} recorded bars are marked as promises`,
  ).toBe(split.recorded.length)
})

/**
 * Clause 2 (and the second half of clause 1). The mark is not only a count: a
 * marked bar's tooltip has to say the dates are planned, and an unmarked bar's has
 * to say they are recorded, which is the sentence the card measured as identical
 * for both.
 */
test('T-0188: a seed bar\'s tooltip says its dates are planned, a record\'s says recorded', async ({ page }) => {
  test.fail(true, 'measured 2026-09-22 on bundle 870b282+dirty: there are 0 bars to hover, so neither tooltip exists; the pane\'s chart never renders (ReferenceError: barTooltip is not defined)')
  const errors = []
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text().slice(0, 300)) })
  const chart = await ganttBars(page, errors)

  const seedTip = await tooltipText(page, 'path[data-t0188-marked]')
  expect(
    seedTip,
    `hovering a marked bar showed no tooltip (${chart.marked} marked of ${chart.bars} bars; `
    + `page errors: ${errors.join(' | ') || 'none'})`,
  ).toBeTruthy()
  expect(seedTip, `a seed bar's tooltip does not say the dates are planned: "${seedTip}"`).toMatch(/planned dates/)
  expect(seedTip, `a seed bar's tooltip does not say it is a promise and not a record: "${seedTip}"`)
    .toMatch(/plan seed, not recorded/)

  const recordTip = await tooltipText(page, 'path[data-t0188-plain]')
  expect(recordTip, 'hovering an unmarked bar showed no tooltip').toBeTruthy()
  expect(recordTip, `a recorded bar's tooltip does not say the dates are recorded: "${recordTip}"`)
    .toMatch(/recorded dates/)
  expect(recordTip, `a recorded bar's tooltip claims to be a plan seed: "${recordTip}"`)
    .not.toMatch(/plan seed/)
})

/**
 * Clause 3, narrowed to what a reader's browser can see: on the two panes that
 * draw one row per task, every row's mark agrees with `isPromise` on the payload,
 * and the mark is the shared `.aim-promise` component rather than a pane's own
 * chip.
 */
test('T-0188: Kanban and Items mark exactly the promise rows, with the shared mark', async ({ page }) => {
  test.fail(true, 'measured 2026-09-22 on bundle 870b282+dirty: Kanban marks 87 promise cards with its own `<span class="aim-chip seed">plan seed</span>` (0 `.aim-promise`), and Items marks 0 of its 87 promise rows; 174 of 175 rows on each pane disagree or agree vacuously')
  const response = await page.request.get('/api/state')
  const state = await response.json()
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
