import { expect, test } from '@playwright/test'

/**
 * T-0189 -- "At 1024 the Gantt timeline collapses to 151px and still truncates 88 labels".
 *
 * The card's acceptance, verbatim:
 *
 *   1. At 1024x800 the timeline is at least 300px wide and the label column is at
 *      most 40% of the canvas.
 *   2. No label loses more characters at 1024 than at 1440.
 *   3. A test measures both viewports and asserts the timeline fraction, so a fixed
 *      pixel gutter cannot come back.
 *
 * The defect is geometric, so the measurement is geometric: the numbers below are
 * read off the pixels the pane actually draws, not off the source that computed
 * them. `yAxis.axisLabel.width: 470` with `grid.left: 30` puts the plot's left edge
 * at canvas x ~503 at *both* viewports, so at 1024 the whole 15-day horizon is a
 * strip about a fifth as wide as the label gutter it sits beside.
 *
 * Instrument, and why it is this one: the pane draws ECharts' own dataZoom
 * *slider* (`{ type: 'slider', height: 18, bottom: 8 }`), whose track is aligned
 * with the grid, so the leftmost and rightmost drawn pixel in the bottom band are
 * the plot's left and right edges. That is the same quantity the reviewer measured
 * by hand ("timeline x 503 -> 1038"), taken from the same canvas. If the slider
 * band is empty the file falls back to the columns with the highest vertical
 * coverage (the day splitLines span the plot height; label text does not), and
 * says in the failure which instrument answered.
 *
 * Clause 2 is measured, not assumed, and it is the clause the naive fix breaks:
 * narrowing a *fixed* 470px gutter to a fraction of the canvas trades the timeline
 * back for characters, because ECharts truncates an axis label to the width it is
 * given. So the check is a comparison of the same label set at the two widths,
 * never a claim about one width alone. It depends on the pane's label form
 * (`   <id> · <title>`, no milestone glyph) and on titles of 61 characters or
 * fewer, which the fixture below guarantees; the same comparison holds under any
 * form as long as both viewports are given the same one.
 *
 * Revision measured for this file, `GET http://127.0.0.1:8777/api/revision`:
 * recorded in the report that carried this file, and re-read at the top of every
 * run by the first test rather than pinned here, because the served bundle moves.
 */

const LO = '2026-09-01'
const HI = '2026-09-14' // 13 day-units of horizon, the live board's span
const TITLE_PAD = 61 // <= the pane's own 62-character cut, so the cut is a no-op

const TITLE = (i) => {
  const head = `item ${i} of the plan`
  return head.padEnd(TITLE_PAD, ' .').slice(0, TITLE_PAD)
}

const STATUSES = ['backlog', 'ready', 'doing', 'review', 'done']

const tasks = {}
for (let i = 0; i < 14; i += 1) {
  const id = `T-10${String(i).padStart(2, '0')}`
  tasks[id] = {
    id,
    title: TITLE(i),
    owner: 'codex',
    status: STATUSES[i % STATUSES.length],
    priority: 'normal',
    estimate: 1,
    estimate_pts: 1,
    start: LO,
    due: i % 5 === 0 ? '2026-09-02' : HI,
    milestone: '',
    tags: [],
    accept: '',
    blocked_by: [],
    visibility: 'published',
    provenance: 'store only',
    events: [],
    comments: [],
  }
}

/** The label the pane builds for each row: three spaces, id, middot, title. */
const LABELS = Object.values(tasks).map((t) => `   ${t.id} · ${t.title}`)

export const STATE = {
  digest: 'gantt-1024-fixture',
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
  reports: { series: [], throughput: [], blocked: [], median_cycle: null, recorded: 14, seed_only: 0 },
  conversation: { channels: [], rooms: [], mail: [] },
  channels: [],
  unacked: [],
  drift: [],
  withheld_tasks: 0,
}

async function route(page) {
  await page.route('**/api/state**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify(STATE),
  }))
  await page.route('**/api/digest**', (r) => r.fulfill({
    contentType: 'application/json', body: JSON.stringify({ digest: STATE.digest }),
  }))
}

/**
 * The plot rectangle, in CSS pixels, from the pixels the pane drew.
 *
 * Returns `{ error }` rather than throwing so the caller can put the reason in
 * the assertion's message instead of in a timeout nobody can read.
 */
async function plot(page) {
  return page.evaluate(() => {
    const host = document.querySelector('[_echarts_instance_]')
    if (!host) return { error: 'no element carries _echarts_instance_ (the pane drew no chart)' }
    const canvases = [...host.querySelectorAll('canvas')]
    if (!canvases.length) return { error: 'the chart host holds no canvas' }
    const canvas = canvases.sort((a, b) => b.width * b.height - a.width * a.height)[0]
    const cssW = canvas.clientWidth || canvas.getBoundingClientRect().width
    if (!cssW) return { error: 'the canvas has no layout width' }
    const dpr = canvas.width / cssW
    const W = canvas.width
    const H = canvas.height
    let img
    try {
      img = canvas.getContext('2d').getImageData(0, 0, W, H)
    } catch (e) {
      return { error: `the canvas could not be read: ${e}` }
    }
    const alpha = (x, y) => img.data[(y * W + x) * 4 + 3]

    // Instrument 1: the dataZoom slider is drawn along the grid's own edges.
    const sy0 = Math.max(0, Math.round(H - 30 * dpr))
    const sy1 = Math.max(sy0 + 1, Math.round(H - 2 * dpr))
    let left = -1
    let right = -1
    for (let x = 0; x < W; x += 1) {
      let hit = false
      for (let y = sy0; y < sy1; y += 1) if (alpha(x, y) > 8) { hit = true; break }
      if (hit) { if (left < 0) left = x; if (x > right) right = x }
    }
    let instrument = 'dataZoom slider'
    if (left < 0) {
      // Instrument 2: the day splitLines span the plot height; label text does not.
      instrument = 'splitLine coverage'
      const gY0 = Math.round(H * 0.08)
      const gY1 = Math.round(H * 0.8)
      const cover = []
      for (let x = 0; x < W; x += 1) {
        let n = 0
        for (let y = gY0; y < gY1; y += 1) if (alpha(x, y) > 8) n += 1
        cover.push(n)
      }
      const peak = Math.max(...cover)
      if (peak < 8) return { error: `nothing is drawn in the plot band (peak column ${peak}px)` }
      const cols = cover.map((v, x) => ({ v, x })).filter((c) => c.v > 0.6 * peak).map((c) => c.x)
      left = cols[0]
      right = cols[cols.length - 1]
    }
    return {
      instrument,
      canvasCssWidth: cssW,
      dpr,
      plotLeft: left / dpr,
      plotRight: (right + 1) / dpr,
      timelineCss: (right + 1 - left) / dpr,
      labelColumnCss: left / dpr,
    }
  })
}

/** Characters the pane's own truncation would remove from a label set at a column width. */
async function truncation(page, columnCss) {
  return page.evaluate(({ labels, column }) => {
    const ctx = document.createElement('canvas').getContext('2d')
    ctx.font = '11.5px ui-monospace, monospace'
    const ellipsis = ctx.measureText('…').width
    const fits = (text) => {
      if (ctx.measureText(text).width + 2 <= column) return text.length
      for (let n = text.length; n > 0; n -= 1) {
        if (ctx.measureText(text.slice(0, n)).width + ellipsis + 2 <= column) return n
      }
      return 0
    }
    const lost = labels.map((l) => l.length - fits(l))
    return {
      column,
      font: ctx.font,
      labelsOversize: labels.filter((l) => ctx.measureText(l).width + 2 > column).length,
      maxLost: Math.max(...lost),
      lostTotal: lost.reduce((a, b) => a + b, 0),
    }
  }, { labels: LABELS, column: columnCss })
}

test.describe('T-0189 the Gantt timeline is made of the width the pane is given', () => {
  test.beforeEach(async ({ page }) => { await route(page) })

  test('1024x800 keeps a 300px timeline inside a 40% label column', async ({ page }) => {
    await page.setViewportSize({ width: 1024, height: 800 })
    await page.goto('/#/gantt')
    await expect(page.locator('.aim-sticky-head')).toBeVisible()
    await page.waitForTimeout(500)

    const p = await plot(page)
    expect(p.error, `1024x800: ${p.error}`).toBeUndefined()

    // The two numbers the card states, both in one failure.
    expect(p.timelineCss, `1024x800: timeline ${Math.round(p.timelineCss)}px of a `
      + `${Math.round(p.canvasCssWidth)}px canvas (plot x ${Math.round(p.plotLeft)} -> `
      + `${Math.round(p.plotRight)}, instrument: ${p.instrument}); the card asks for >= 300px`)
      .toBeGreaterThanOrEqual(300)

    const labelShare = p.labelColumnCss / p.canvasCssWidth
    expect(labelShare, `1024x800: the label column is ${Math.round(p.labelColumnCss)}px of `
      + `${Math.round(p.canvasCssWidth)}px = ${(100 * labelShare).toFixed(1)}% of the canvas; `
      + `the card asks for <= 40%`).toBeLessThanOrEqual(0.4)
  })

  test('1440x1000 keeps a 300px timeline inside a 40% label column', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 })
    await page.goto('/#/gantt')
    await expect(page.locator('.aim-sticky-head')).toBeVisible()
    await page.waitForTimeout(500)

    const p = await plot(page)
    expect(p.error, `1440x1000: ${p.error}`).toBeUndefined()

    expect(p.timelineCss, `1440x1000: timeline ${Math.round(p.timelineCss)}px of a `
      + `${Math.round(p.canvasCssWidth)}px canvas (plot x ${Math.round(p.plotLeft)} -> `
      + `${Math.round(p.plotRight)}, instrument: ${p.instrument}); the card asks for >= 300px`)
      .toBeGreaterThanOrEqual(300)

    const labelShare = p.labelColumnCss / p.canvasCssWidth
    expect(labelShare, `1440x1000: the label column is ${Math.round(p.labelColumnCss)}px of `
      + `${Math.round(p.canvasCssWidth)}px = ${(100 * labelShare).toFixed(1)}% of the canvas; `
      + `the card asks for <= 40%`).toBeLessThanOrEqual(0.4)
  })

  test('a label loses no more characters at 1024 than at 1440', async ({ page }) => {
    const widths = [1024, 1440]
    const measured = {}
    for (const width of widths) {
      await page.setViewportSize({ width, height: width === 1024 ? 800 : 1000 })
      await page.goto('/#/gantt')
      await expect(page.locator('.aim-sticky-head')).toBeVisible()
      await page.waitForTimeout(500)
      const p = await plot(page)
      expect(p.error, `${width}px: ${p.error}`).toBeUndefined()
      measured[width] = { p, t: await truncation(page, p.labelColumnCss) }
    }

    // The fixture has to be able to lose characters at all, or the comparison is
    // two zeroes agreeing.
    expect(measured[1024].t.labelsOversize,
      `fixture precondition: ${measured[1024].t.labelsOversize} of ${LABELS.length} labels exceed `
      + `the 1024px label column (${Math.round(measured[1024].t.column)}px)`)
      .toBeGreaterThan(0)

    expect(measured[1024].t.maxLost,
      `1024x800 loses up to ${measured[1024].t.maxLost} characters per label `
      + `(${measured[1024].t.lostTotal} over ${LABELS.length} labels in a `
      + `${Math.round(measured[1024].t.column)}px column); 1440x1000 loses up to `
      + `${measured[1440].t.maxLost} (${measured[1440].t.lostTotal} labels, `
      + `${Math.round(measured[1440].t.column)}px column); the card asks that 1024 lose no more`)
      .toBeLessThanOrEqual(measured[1440].t.maxLost)
  })
})
