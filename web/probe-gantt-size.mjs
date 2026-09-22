/**
 * T-0189 geometry probe. Reads the live board on 8777 with a throwaway Chromium
 * from `playwright-core`. Nothing is served and nothing is built: the bundle
 * measured is whatever the board serves, which is the point -- these are the
 * numbers a reader gets.
 *
 * Geometry is read off the canvas' own pixels rather than from ECharts, because
 * the only thing that survives a rebuild is what got painted. A bar is the only
 * thing painted in a status colour at full alpha, so the first column carrying
 * >=8 such pixels is where the timeline starts (the "canvas x ~503" the card
 * measured by hand).
 *
 * The click is measured against the *tooltip*, which is the pane's own answer to
 * "which item is at this pixel" and needs no arithmetic of mine: hover a point,
 * read the id ECharts says is there, then click the same point and read the id
 * the drawer opens. Two answers to one question, from the same code path a
 * reader uses. If they disagree, the defect is measured, not inferred -- and no
 * row-order guess of mine can manufacture it.
 *
 * usage: node probe-gantt-size.mjs [label]
 */
import { chromium } from 'playwright-core'

const label = process.argv[2] || 'now'
const VIEWPORTS = [{ w: 1440, h: 1000 }, { w: 1024, h: 800 }]

const STATUS_RGB = [
  [148, 163, 184], [96, 165, 250], [245, 158, 11], [167, 139, 250],
  [52, 211, 153], [239, 68, 68], [156, 163, 175],
]
const RIGHT = 40 // grid.right

const geometry = ({ statusRgb, right }) => {
  const cv = document.querySelector('canvas')
  if (!cv) return { error: 'no canvas' }
  const r = cv.getBoundingClientRect()
  const ctx = cv.getContext('2d')
  const dpr = cv.width / r.width
  const rows = Math.floor(cv.height * 0.7) // the dataZoom slider owns the rest
  const img = ctx.getImageData(0, 0, cv.width, rows).data
  const near = (i, c) => Math.abs(img[i] - c[0]) < 12 && Math.abs(img[i + 1] - c[1]) < 12 && Math.abs(img[i + 2] - c[2]) < 12
  const hits = (x) => {
    let hit = 0
    for (let y = 0; y < rows; y++) {
      const i = (y * cv.width + x) * 4
      if (img[i + 3] < 250) continue
      for (const c of statusRgb) if (near(i, c)) { hit++; break }
    }
    return hit
  }
  let barStart = -1, barEnd = -1
  for (let x = 0; x < cv.width; x++) if (hits(x) >= 8) { barStart = x; break }
  for (let x = cv.width - 1; x >= 0; x--) if (hits(x) >= 8) { barEnd = x; break }

  // Day pitch: the x split lines are the only vertical lines drawn, and they are
  // the day grid. Read from the column profile of the timeline band.
  const timelineFrom = Math.max(0, barStart)
  const colRuns = []
  let c0 = null
  for (let x = timelineFrom; x < cv.width; x++) {
    if (hits(x) >= 4) {
      if (c0 === null) c0 = x
    } else if (c0 !== null) {
      colRuns.push({ from: c0, to: x - 1 })
      c0 = null
    }
  }
  if (c0 !== null) colRuns.push({ from: c0, to: cv.width - 1 })

  const main = document.querySelector('.el-main')
  const mb = main.getBoundingClientRect()
  const c2 = document.createElement('canvas').getContext('2d')
  c2.font = '11.5px ui-monospace, monospace'
  const charPx = c2.measureText('M').width
  const canvasTopInDoc = (r.top - mb.top) + main.scrollTop
  return {
    canvasCss: `${Math.round(r.width)}x${Math.round(r.height)}`,
    canvasBuf: `${cv.width}x${cv.height}`,
    dpr: +dpr.toFixed(2),
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    mainTop: +mb.top.toFixed(1),
    canvasTopInDoc: +canvasTopInDoc.toFixed(1),
    canvasBottomInDoc: +(canvasTopInDoc + r.height).toFixed(1),
    scrollTop: main.scrollTop,
    gutterPx: +(barStart / dpr).toFixed(1),
    gutterPct: +((barStart / dpr) / r.width * 100).toFixed(1),
    timelinePx: +((r.width - right - barStart / dpr)).toFixed(1),
    timelinePct: +(((r.width - right - barStart / dpr) / r.width) * 100).toFixed(1),
    barsRight: +(barEnd / dpr).toFixed(1),
    charPx: +charPx.toFixed(2),
    charsInGutter: Math.floor((barStart / dpr) / charPx),
    dayRunCount: colRuns.length,
    dayPitch: colRuns.length > 1 ? +(((colRuns[1].from - colRuns[0].from)) / dpr).toFixed(2) : null,
    scroller: { clientH: main.clientHeight, scrollH: main.scrollHeight },
    // Where the reader can put the pointer: the canvas' own box against the
    // viewport, and against the scroller's visible window (below the sticky head).
    visibleCanvasYFrom: Math.max(0, (mb.top - mb.top + main.scrollTop) - canvasTopInDoc + 96),
    midCanvasY: Math.round(r.height / 2),
    midInViewport: (mb.top + canvasTopInDoc + r.height / 2 - main.scrollTop) <= window.innerHeight,
  }
}

/** Tooltip id at a canvas point, then the drawer id for a click at the same point. */
const at = async (page, canvasY, barFrac) => {
  const p = await page.evaluate(({ y, bf }) => {
    const cv = document.querySelector('canvas')
    const r = cv.getBoundingClientRect()
    const main = document.querySelector('.el-main')
    const mb = main.getBoundingClientRect()
    const topInDoc = (r.top - mb.top) + main.scrollTop
    // The timeline starts at 44-70% of the canvas, so aim well inside it.
    const x = Math.round(r.left + r.width * bf)
    const clientY = Math.round(mb.top + topInDoc + y - main.scrollTop)
    const el = document.elementFromPoint(x, clientY)
    return { x, clientY, hit: el ? el.tagName : null, inViewport: clientY >= 0 && clientY <= window.innerHeight }
  }, { y: canvasY, bf: barFrac })

  await page.mouse.move(p.x, p.clientY)
  await page.waitForTimeout(320)
  const tip = await page.evaluate(() => {
    const els = [...document.querySelectorAll('div')].filter((d) => /^T-\d{4}$/.test((d.textContent || '').trim().slice(0, 6)) && d.children.length <= 3 && d.offsetParent !== null)
    const t = els[els.length - 1]
    const m = t && (t.textContent || '').match(/T-\d{4}/)
    return m ? m[0] : null
  })
  await page.mouse.click(p.x, p.clientY)
  await page.waitForTimeout(320)
  const drawer = await page.evaluate(() => {
    const d = document.querySelector('.el-drawer')
    if (!d || getComputedStyle(d).display === 'none' || d.getBoundingClientRect().height === 0) return null
    return {
      title: (d.querySelector('h3')?.textContent || '').trim(),
      bodyChars: (d.querySelector('.el-drawer__body')?.textContent || '').trim().length,
      id: ((d.querySelector('.el-drawer__body')?.textContent || '').match(/T-\d{4}/) || [])[0] || null,
    }
  })
  await page.keyboard.press('Escape')
  await page.waitForTimeout(180)
  return { canvasY, ...p, tooltipId: tip, drawer }
}

const browser = await chromium.launch({ channel: 'chromium-headless-shell' })
const revision = await (await fetch('http://127.0.0.1:8777/api/revision')).json()
const out = { label, when: new Date().toISOString(), revision, results: [] }
for (const vp of VIEWPORTS) {
  const context = await browser.newContext({ viewport: { width: vp.w, height: vp.h } })
  const page = await context.newPage()
  // The coordinator rebuilds `web/dist` while this runs, and a board caught
  // mid-swap serves an index.html whose chunks are not there yet. A retry is not
  // a retry of the measurement: it is the same page, loaded once it exists.
  let ok = false
  for (let attempt = 1; attempt <= 5 && !ok; attempt++) {
    try {
      await page.goto('http://127.0.0.1:8777/#/gantt', { waitUntil: 'networkidle' })
      await page.waitForSelector('canvas', { timeout: 8000 })
      ok = true
    } catch (e) {
      out.results.push({ viewport: `${vp.w}x${vp.h}`, attempt, error: String(e).slice(0, 160) })
      await page.waitForTimeout(2500)
    }
  }
  if (!ok) { await context.close(); continue }
  await page.waitForTimeout(1500)

  const top = await page.evaluate(geometry, { statusRgb: STATUS_RGB, right: RIGHT })
  const barFrac = 0.85
  const unscrolled = []
  for (const y of [24, 60, 96]) unscrolled.push(await at(page, y, barFrac))

  // The ordinary case for a 2377px canvas: the reader has scrolled to the middle
  // of the chart. Rows are visible from ~96px below the scroller's top.
  const scroll = await page.evaluate((y) => {
    const main = document.querySelector('.el-main')
    main.scrollTop = y
    return main.scrollTop
  }, Math.round(top.canvasCss.split('x')[1] / 2))
  await page.waitForTimeout(300)
  const scrolledGeom = await page.evaluate(geometry, { statusRgb: STATUS_RGB, right: RIGHT })
  const scrolled = []
  for (const y of [400, 800, 1100]) scrolled.push(await at(page, y, barFrac))

  // Is a click at the vertical middle of the canvas a click a reader can make?
  const notGrid = await page.evaluate((y) => {
    const cv = document.querySelector('canvas')
    const r = cv.getBoundingClientRect()
    const main = document.querySelector('.el-main')
    const mb = main.getBoundingClientRect()
    const topInDoc = (r.top - mb.top) + main.scrollTop
    const clientY = mb.top + topInDoc + y - main.scrollTop
    const el = document.elementFromPoint(Math.round(r.left + r.width * 0.85), Math.round(clientY))
    return { clientY: Math.round(clientY), elementAt: el ? `${el.tagName}.${el.className}` : null }
  }, top.midCanvasY)

  out.results.push({ viewport: `${vp.w}x${vp.h}`, top, scroll, scrolledGeom, unscrolled, scrolled, midCanvas: notGrid })
  await context.close()
}
await browser.close()
console.log(JSON.stringify(out, null, 1))
