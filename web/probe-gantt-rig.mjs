/**
 * T-0189 rule rig. Runs the *candidate* sizing rule against real ECharts, in a
 * page served by nothing: the HTML, the ECharts UMD bundle and (below) the
 * options are all handed to the browser through `page.route`, so no port is
 * opened and no build is run.
 *
 * The pane's own constants are read out of `src/panes/GanttPane.vue` by name, so
 * the numbers measured here are the numbers that ship; only the three lines of
 * arithmetic are restated, and `web/tests/gantt-size.spec.js` is what measures
 * the pane's wiring of them.
 *
 * `window.echarts.getInstanceByDom(...).getOption()` is ECharts' own answer to
 * "what did the axis draw", so the label truncation is read from the library and
 * not from a re-derivation of its rules.
 *
 * usage: node probe-gantt-rig.mjs [label]
 */
import { readFileSync } from 'node:fs'
import { chromium } from 'playwright-core'

const label = process.argv[2] || 'rig'
const src = readFileSync(new URL('./src/panes/GanttPane.vue', import.meta.url), 'utf8')
const num = (name) => {
  const m = src.match(new RegExp(`const\\s+${name}\\s*=\\s*([0-9.]+)`))
  if (!m) throw new Error(`constant ${name} not found in GanttPane.vue`)
  return Number(m[1])
}
const stripe = (name, fallback) => {
  const m = src.match(new RegExp(`const\\s+${name}\\s*=\\s*'([^']+)'`))
  return m ? m[1] : fallback
}
const K = {
  ROW_PX: num('ROW_PX'),
  MAX_GUTTER_FRACTION: num('MAX_GUTTER_FRACTION'),
  MIN_GUTTER_PX: num('MIN_GUTTER_PX'),
  TIMELINE_MIN_PX_PER_DAY: num('TIMELINE_MIN_PX_PER_DAY'),
  LABEL_TOP: num('LABEL_TOP'),
  LABEL_MARGIN: num('LABEL_MARGIN'),
  DESIGN_MIN_CANVAS_PX: num('DESIGN_MIN_CANVAS_PX'),
  TIMELINE_PAD_PX: num('TIMELINE_PAD_PX'),
  RIGHT: num('CHART_RIGHT_PX'),
  LABEL_FONT: stripe('LABEL_FONT'),
}
console.log('constants read from GanttPane.vue:', JSON.stringify(K))

const ECHARTS = readFileSync(new URL('./node_modules/echarts/dist/echarts.js', import.meta.url), 'utf8')

const state = await (await fetch('http://127.0.0.1:8777/api/state')).json()
const tasks = Object.values(state.tasks).filter((t) => t.start || t.due)
const STATUS_COLOR = {
  backlog: '#94a3b8', ready: '#60a5fa', doing: '#f59e0b', review: '#a78bfa',
  done: '#34d399', blocked: '#ef4444', dropped: '#9ca3af',
}
const DAY = 86400000
const days = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / DAY)
const sorted = tasks.slice().sort((a, b) => {
  const ka = `${a.milestone || 'zz'}|${a.start || a.due}`
  const kb = `${b.milestone || 'zz'}|${b.start || b.due}`
  return ka < kb ? -1 : ka > kb ? 1 : 0
})
const dates = tasks.flatMap((t) => [t.start, t.due]).filter(Boolean).sort()
const lo = dates[0]
const hi = dates[dates.length - 1]
const n = days(lo, hi) + 2
const labels = []
const seen = new Set()
for (const t of sorted) {
  const first = !seen.has(t.milestone)
  seen.add(t.milestone)
  const l = `${t.id} · ${t.title}`
  labels.push(first && t.milestone ? `${t.milestone} ▏${l}` : `   ${l}`)
}
const offsets = sorted.map((t) => Math.max(0, days(lo, t.start || t.due)))
const bars = sorted.map((t) => {
  const s = t.start || t.due
  const e = t.due || t.start
  return { value: Math.max(1, days(s, e) + 1), itemStyle: { color: STATUS_COLOR[t.status] || '#94a3b8', borderRadius: 3 } }
})

const PAGE = `<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;background:#eef2f7}</style></head>
<body><div id="host"></div><script src="https://rig.invalid/echarts.js"></script></body></html>`

const browser = await chromium.launch({ channel: 'chromium-headless-shell' })
const out = { label, when: new Date().toISOString(), constants: K, rows: labels.length, dayUnits: n, lo, hi, results: [] }

for (const paneW of [1200, 1080, 900, 784, 640]) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const page = await context.newPage()
  await page.route('https://rig.invalid/echarts.js', (r) => r.fulfill({ contentType: 'text/javascript', body: ECHARTS }))
  await page.route('https://rig.invalid/', (r) => r.fulfill({ contentType: 'text/html', body: PAGE }))
  await page.goto('https://rig.invalid/')
  await page.waitForFunction(() => !!window.echarts, null, { timeout: 20000 })

  const m = await page.evaluate(({ text, font }) => {
    const c = document.createElement('canvas').getContext('2d')
    c.font = font
    return { charPx: c.measureText('M').width, widest: Math.max(...text.map((s) => c.measureText(s).width)) }
  }, { text: labels, font: K.LABEL_FONT })

  // The rule under test -- the arithmetic only; the constants above are the
  // pane's own.
  const charsDesign = Math.max(8, Math.floor(
    (K.DESIGN_MIN_CANVAS_PX * K.MAX_GUTTER_FRACTION - K.LABEL_TOP - K.LABEL_MARGIN) / m.charPx))
  const timelineFloor = Math.min((n - K.TIMELINE_PAD_PX) * K.TIMELINE_MIN_PX_PER_DAY,
    Math.max(120, paneW - K.MIN_GUTTER_PX - K.RIGHT))
  const wanted = m.widest + K.LABEL_TOP + K.LABEL_MARGIN
  const gutter = Math.max(K.MIN_GUTTER_PX,
    Math.min(wanted, paneW * K.MAX_GUTTER_FRACTION, paneW - K.RIGHT - timelineFloor))
  const labelPx = Math.max(24, gutter - K.LABEL_TOP - K.LABEL_MARGIN)
  const timelinePx = paneW - gutter - K.RIGHT
  const timelineUnits = timelinePx - K.TIMELINE_PAD_PX

  const drawn = labels.map((l) => {
    if (m.charPx * l.length <= labelPx) return l
    let keep = Math.max(4, Math.floor(labelPx / m.charPx) - 1)
    while (keep > 4 && (l.slice(0, keep) + '…').length * m.charPx > labelPx) keep--
    return l.slice(0, keep)
  })

  const scrollerH = 951
  const wantedH = labels.length * K.ROW_PX + 130
  const height = Math.max(320, Math.min(wantedH, scrollerH - 144))
  const visibleRows = Math.max(4, Math.floor((height - K.CHART_TOP_PX - K.CHART_BOTTOM_PX) / K.ROW_PX))

  const painted = await page.evaluate(({ drawn, labels, lo, n, offsets, bars, gutter, labelPx, height, visibleRows, K, font }) => {
    const host = document.getElementById('host')
    host.style.width = '100%'
    host.style.height = height + 'px'
    const chart = window.echarts.init(host, null, { renderer: 'canvas' })
    chart.setOption({
      backgroundColor: 'transparent',
      grid: { left: 4, right: K.RIGHT, top: K.CHART_TOP_PX, bottom: K.CHART_BOTTOM_PX, containLabel: true },
      tooltip: { trigger: 'item' },
      xAxis: {
        type: 'value', min: 0, max: n, position: 'top',
        axisLabel: { formatter: (v) => { const d = new Date(Date.parse(lo) + v * 86400000); return `${d.getMonth() + 1}/${d.getDate()}` } },
        splitLine: { show: true, lineStyle: { opacity: 0.18 } },
      },
      yAxis: {
        type: 'category', inverse: true, data: drawn,
        axisLabel: { width: labelPx, overflow: 'truncate', fontSize: 11.5, fontFamily: font },
        axisTick: { show: false },
      },
      dataZoom: [
        { type: 'inside', xAxisIndex: 0, filterMode: 'weakFilter' },
        { type: 'slider', xAxisIndex: 0, height: 18, bottom: 8, filterMode: 'weakFilter' },
        ...(visibleRows < drawn.length ? [{ type: 'slider', yAxisIndex: 0, right: 0, width: 10, moveHandleSize: 0, showDataShadow: false, showDetail: false, brushSelect: false, startValue: 0, endValue: visibleRows - 1 }] : []),
      ],
      series: [
        { name: 'offset', type: 'bar', stack: 'gantt', silent: true, itemStyle: { color: 'transparent' }, data: offsets },
        { name: 'duration', type: 'bar', stack: 'gantt', barMaxWidth: 16, data: bars },
      ],
    })
    const cv = document.querySelector('canvas')
    const ctx = cv.getContext('2d')
    const rows = Math.floor(cv.height * 0.7)
    const img = ctx.getImageData(0, 0, cv.width, rows).data
    const pals = Object.values({ backlog: '#94a3b8', ready: '#60a5fa', doing: '#f59e0b', review: '#a78bfa', done: '#34d399', blocked: '#ef4444', dropped: '#9ca3af' })
      .map((h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)))
    const near = (i, c) => Math.abs(img[i] - c[0]) < 12 && Math.abs(img[i + 1] - c[1]) < 12 && Math.abs(img[i + 2] - c[2]) < 12
    let first = -1, last = -1
    for (let x = 0; x < cv.width; x++) {
      let k = 0
      for (let y = 0; y < rows; y++) { const i = (y * cv.width + x) * 4; if (img[i + 3] < 250) continue; if (pals.some((c) => near(i, c))) k++ }
      if (k >= 8) { if (first < 0) first = x; last = x }
    }
    // Band ink top: the first row carrying >=4 status pixels inside the timeline.
    let bandTop = -1
    for (let y = 0; y < rows && bandTop < 0; y++) {
      let k = 0
      for (let x = first; x < Math.min(cv.width, first + 80); x++) { const i = (y * cv.width + x) * 4; if (img[i + 3] < 250) continue; if (pals.some((c) => near(i, c))) k++ }
      if (k >= 4) bandTop = y
    }
    // One-day bar width: from the first column run to the last in the first band.
    let dayPx = 0
    if (bandTop >= 0) {
      let runStart = -1
      for (let y = bandTop; y < Math.min(rows, bandTop + 12); y++) {
        for (let x = first; x < cv.width; x++) {
          const i = (y * cv.width + x) * 4
          const on = img[i + 3] >= 250 && pals.some((c) => near(i, c))
          if (on && runStart < 0) runStart = x
        }
      }
      let runEnd = runStart
      for (let x = runStart; x < cv.width; x++) {
        let k = 0
        for (let y = bandTop; y < Math.min(rows, bandTop + 12); y++) { const i = (y * cv.width + x) * 4; if (img[i + 3] < 250) continue; if (pals.some((c) => near(i, c))) k++ }
        if (k > 0) runEnd = x
      }
      dayPx = runEnd - runStart + 1
    }
    const opt = chart.getOption()
    return {
      canvas: `${cv.width}x${cv.height}`,
      gutterPx: first, drawnRight: last,
      timelinePx: cv.width - K.RIGHT - first,
      bandTop,
      firstBandOneDayPx: dayPx,
      label0: opt.yAxis[0].data[0], label1: opt.yAxis[0].data[1],
      axisLabelWidth: opt.yAxis[0].axisLabel[0].width,
      hasYZoom: (opt.dataZoom || []).some((z) => z.yAxisIndex === 0),
      yZoomStart: ((opt.dataZoom || []).find((z) => z.yAxisIndex === 0) || {}).startValue,
    }
  }, { drawn, labels, lo, n, offsets, bars, gutter, labelPx, height, visibleRows, K, font: K.LABEL_FONT })

  out.results.push({
    paneW, charPx: +m.charPx.toFixed(2), widestRawLabelPx: +m.widest.toFixed(1), charsDesign,
    rule: {
      wantedGutterPx: +wanted.toFixed(1), timelineFloorPx: +timelineFloor.toFixed(1),
      gutterPx: +gutter.toFixed(1), gutterFraction: +(gutter / paneW).toFixed(3),
      labelPx: +labelPx.toFixed(1), timelinePx: +timelinePx.toFixed(1),
      timelineUnitsPx: +timelineUnits.toFixed(1), pxPerDay: +(timelineUnits / n).toFixed(1),
      labelChars: Math.floor(labelPx / m.charPx),
    },
    height: { wanted: wantedH, chosen: height, visibleRows, rows: labels.length },
    painted,
    truncatedLabels: drawn.filter((l, i) => l !== labels[i]).length,
  })
  await context.close()
}
await browser.close()
console.log(JSON.stringify(out, null, 1))
