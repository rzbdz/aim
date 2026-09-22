/**
 * The Reports flow chart, built the way the pane builds it and rendered through
 * the same ECharts modules the bundle ships -- in node, against the live payload.
 *
 * It answers three questions that a screenshot cannot: does `setOption` throw on
 * this option, are the curves and levels actually in the rendered SVG, and does
 * the store-wide curve end where the store's own fold says it does. Run it from
 * `web/` so `node_modules` resolves. It was written because the pane drew bars
 * and no curves at all: ECharts was throwing inside `renderSeries` on a markLine
 * whose target was `undefined`, which is what `{ yAxis: tally.undone }` becomes
 * when the payload has no `board_scope` -- and the throw is silent to a reader,
 * because the bars have already been painted by then.
 */
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, MarkLineComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

echarts.use([SVGRenderer, BarChart, LineChart, GridComponent, MarkLineComponent, LegendComponent, TooltipComponent])

const state = await (await fetch('http://127.0.0.1:8777/api/state')).json()
const tasks = Object.values(state.tasks || {})
const scope = state.reports.board_scope.visible
const BUCKET_MS = 60000
const minuteOf = (ms) => Math.floor(ms / BUCKET_MS) * BUCKET_MS
const clock = (ms) => new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

const events = []
for (const t of tasks) for (const ev of t.events || []) {
  if (!ev.ts) continue
  const kind = String(ev.event || ev.kind || '').replace(/^task\./, '')
  if (kind === 'created') events.push({ ts: Date.parse(ev.ts), kind: 'opened' })
  else if (kind === 'moved' && ev.to === 'done') events.push({ ts: Date.parse(ev.ts), kind: 'done' })
}
events.sort((a, b) => a.ts - b.ts)

function flow(windowMinutes) {
  const end = events.length ? events.at(-1).ts : Date.now()
  const endBucket = minuteOf(end) + BUCKET_MS
  const start = endBucket - windowMinutes * BUCKET_MS
  const cells = Array.from({ length: windowMinutes }, (_, i) => ({ t: start + i * BUCKET_MS, opened: 0, done: 0 }))
  for (const e of events) {
    if (e.ts < start || e.ts >= endBucket) continue
    cells[Math.floor((e.ts - start) / BUCKET_MS)][e.kind] += 1
  }
  const opened = cells.reduce((n, c) => n + c.opened, 0)
  const done = cells.reduce((n, c) => n + c.done, 0)
  let running = 0
  const cumulative = cells.map((c) => (running += c.done))
  const perDay = state.reports.series || []
  const storeCloses = perDay.reduce((n, row) => n + (row.done || 0), 0)
  const carries = Math.max(0, storeCloses - done)
  const closes = cumulative.map((n) => carries + n)
  const doneLevels = { done: scope.done, undone: scope.undone, gapped: Math.max(0, scope.done - storeCloses) }
  let opening = 0
  const openedCumulative = cells.map((c) => (opening += c.opened))
  return { cells, cumulative, openedCumulative, closes, storeCloses, carries, doneLevels, opened, done, start, end: endBucket }
}

function option(f, windowMinutes) {
  const labels = f.cells.map((c) => clock(c.t))
  const every = Math.max(0, Math.ceil(f.cells.length / 12) - 1)
  return {
    grid: { left: 52, right: 48, top: 30, bottom: 34 },
    tooltip: { trigger: 'axis' },
    legend: { data: ['opened', 'done', 'closes, the whole store', 'opened cumulative', 'closed cumulative'], top: 0, textStyle: { fontSize: 11 } },
    xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10, interval: every } },
    yAxis: { type: 'value', minInterval: 1, name: 'items / min', nameTextStyle: { fontSize: 10 },
             splitLine: { lineStyle: { opacity: 0.18 } } },
    series: [
      { name: 'opened', type: 'bar', stack: 'perbucket', symbol: 'circle', symbolSize: 6,
        itemStyle: { color: '#60a5fa' }, barMaxWidth: 10, data: f.cells.map((c) => c.opened) },
      { name: 'done', type: 'bar', stack: 'perbucket', symbol: 'rect', symbolSize: 6,
        itemStyle: { color: '#34d399' }, barMaxWidth: 10, data: f.cells.map((c) => c.done) },
      { name: 'closes, the whole store', type: 'line', step: 'end', symbol: 'none',
        lineStyle: { color: '#f59e0b', width: 2 }, z: 3, data: f.closes,
        markLine: { silent: true, symbol: 'none',
          lineStyle: { color: '#f59e0b', type: 'dotted', width: 1.5 },
          label: { formatter: `${f.carries} closed before this window`, fontSize: 10, position: 'insideStartTop' },
          data: [
            { yAxis: f.doneLevels.done, lineStyle: { color: '#34d399', type: 'dashed', width: 1.5 },
              label: { formatter: `done ${f.doneLevels.done}`, fontSize: 10, position: 'insideEndTop' } },
            { yAxis: f.doneLevels.undone, lineStyle: { color: '#f87171', type: 'dashed', width: 1.5 },
              label: { formatter: `undone ${f.doneLevels.undone}`, fontSize: 10, position: 'insideEndBottom' } },
            { yAxis: f.carries },
          ] } },
      { name: 'opened cumulative', type: 'line', step: 'end', symbol: 'none',
        lineStyle: { color: '#60a5fa', width: 1.5, type: 'dotted' }, data: f.openedCumulative },
      { name: 'closed cumulative', type: 'line', step: 'end', symbol: 'none',
        lineStyle: { color: '#34d399', width: 2 }, data: f.cumulative },
    ],
  }
}

let bad = 0
for (const w of [15, 60, 1440]) {
  const f = flow(w)
  let chart
  try {
    chart = echarts.init(null, null, { renderer: 'svg', ssr: true, width: 1138, height: 300 })
    chart.setOption(option(f, w))
    const svg = chart.renderToSVGString()
    const polylines = (svg.match(/<path /g) || []).length
    const label = f.carries
    console.log(`OK window=${w}: svg ${svg.length} B, ${polylines} path(s), ` +
      `curve ${f.closes[0]} -> ${f.closes.at(-1)}, levels done=${f.doneLevels.done} undone=${f.doneLevels.undone} carries=${f.doneLevels.gapped} gapped`)
    if (f.closes.at(-1) !== f.storeCloses) { console.log('  MISMATCH: last point != storeCloses'); bad += 1 }
    for (const [what, v] of [['done', f.doneLevels.done], ['undone', f.doneLevels.undone], ['curve end', f.storeCloses]]) {
      if (!svg.includes(String(v))) { console.log(`  MISSING TEXT: ${what}=${v} is not on the rendered chart`); bad += 1 }
    }
  } catch (e) {
    bad += 1
    console.log(`THROW window=${w}: ${e.constructor.name}: ${e.message}`)
  } finally { try { chart && chart.dispose() } catch {} }
}
console.log(bad ? `FAIL ${bad}` : 'all windows rendered')
